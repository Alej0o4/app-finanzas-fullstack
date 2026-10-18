"""API de sobres virtuales y disponible real (Fase 35 T2-T4, T7)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.core.user_deletion import delete_user_cascade
from app.models import models

D = Decimal
URL = "/api/v1/funds/"


def _money(valor) -> Decimal:
    return Decimal(str(valor))


@pytest.fixture
def crear_sobre(client, auth_headers):
    def _factory(account_id: int, headers: dict | None = None, **extra) -> dict:
        body = {"name": "Seguro", "kind": "goal", "account_id": account_id, "target_amount": "1200.00"}
        body.update(extra)
        resp = client.post(URL, json=body, headers=headers or auth_headers)
        assert resp.status_code == 200, resp.text
        return resp.json()

    return _factory


@pytest.fixture
def cuenta(make_account, auth_headers):
    return make_account(auth_headers, balance="5000.00")


def _aportar(client, headers, fund_id, amount, **extra):
    return client.post(f"{URL}{fund_id}/contributions", json={"amount": amount, **extra}, headers=headers)


def _retirar(client, headers, fund_id, amount):
    return client.post(f"{URL}{fund_id}/withdrawals", json={"amount": amount}, headers=headers)


class TestCrear:
    def test_crea_con_la_moneda_de_la_cuenta(self, crear_sobre, make_account, auth_headers):
        usd = make_account(auth_headers, name="Dólares", currency="USD", balance="100.00")
        fondo = crear_sobre(usd["id"], name="  Viaje  ", kind="goal")
        assert fondo["currency"] == "USD"
        assert fondo["name"] == "Viaje"
        assert fondo["status"] == "active"
        assert _money(fondo["balance"]) == D("0")
        assert fondo["backing_shortfall"] is not None

    def test_ruta_sin_trailing_slash_no_existe_pero_lista_vacia(self, client, auth_headers):
        resp = client.get(URL, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.parametrize(
        "extra",
        [
            {"name": "   "},
            {"name": "x" * 101},
            {"target_amount": "0"},
            {"target_amount": "-5"},
            {"target_amount": "1.234"},
            {"target_amount": "1000000000000"},  # 13 dígitos enteros: desborda Numeric(14,2)
            {"kind": "otra"},
            {"target_amount": None},  # ni monto ni meses
            {"target_months": 3},  # monto Y meses
            {"target_amount": None, "target_months": 3},  # meses en un kind que no es emergencia
            {"target_amount": None, "target_months": 0, "kind": "emergency"},
            {"target_amount": None, "target_months": 61, "kind": "emergency"},
        ],
    )
    def test_validaciones_422(self, client, auth_headers, cuenta, extra):
        body = {"name": "Seguro", "kind": "goal", "account_id": cuenta["id"], "target_amount": "1200.00"}
        body.update(extra)
        assert client.post(URL, json=body, headers=auth_headers).status_code == 422

    def test_emergencia_acepta_meses(self, crear_sobre, cuenta):
        fondo = crear_sobre(cuenta["id"], kind="emergency", target_amount=None, target_months=3)
        assert fondo["target_months"] == 3
        # Sin historial de gasto no hay meta efectiva (D3)
        assert fondo["target_amount"] is None
        assert fondo["pace"] is None
        assert fondo["runway_months"] is None

    def test_emergencia_sobre_tarjeta_de_credito_422(self, client, auth_headers, make_account):
        tarjeta = make_account(auth_headers, name="Tarjeta", type="credit", balance="0.00")
        resp = client.post(
            URL,
            json={"name": "Colchón", "kind": "emergency", "account_id": tarjeta["id"], "target_months": 3},
            headers=auth_headers,
        )
        assert resp.status_code == 422
        assert "líquido" in resp.json()["detail"]

    @pytest.mark.parametrize("kind", ["goal", "annual_expense"])
    def test_otros_tipos_si_aceptan_tarjeta_de_credito(self, client, auth_headers, make_account, kind):
        tarjeta = make_account(auth_headers, name="Tarjeta", type="credit", balance="0.00")
        body = {"name": "Meta", "kind": kind, "account_id": tarjeta["id"], "target_amount": "100.00"}
        if kind == "annual_expense":
            body["target_date"] = (datetime.now(UTC) + timedelta(days=60)).date().isoformat()
        assert client.post(URL, json=body, headers=auth_headers).status_code == 200

    def test_put_mover_emergencia_a_tarjeta_de_credito_422(self, client, auth_headers, make_account, crear_sobre):
        normal = make_account(auth_headers, name="Débito", type="debit", balance="900.00")
        tarjeta = make_account(auth_headers, name="Tarjeta", type="credit", balance="0.00")
        fondo = crear_sobre(normal["id"], kind="emergency", target_amount=None, target_months=3)
        resp = client.put(f"{URL}{fondo['id']}", json={"account_id": tarjeta["id"]}, headers=auth_headers)
        assert resp.status_code == 422
        assert client.get(f"{URL}{fondo['id']}", headers=auth_headers).json()["account_id"] == normal["id"]

    def test_fecha_objetivo_pasada_422(self, client, auth_headers, cuenta):
        ayer = (datetime.now(UTC) - timedelta(days=3)).date().isoformat()
        resp = client.post(
            URL,
            json={"name": "x", "kind": "goal", "account_id": cuenta["id"], "target_amount": "10", "target_date": ayer},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_cuenta_ajena_404(self, client, auth_headers, other_user, make_account, crear_sobre):
        ajena = make_account(other_user["headers"])
        resp = client.post(
            URL,
            json={"name": "x", "kind": "goal", "account_id": ajena["id"], "target_amount": "10"},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_requiere_autenticacion(self, client):
        assert client.get(URL).status_code == 401


class TestMetricas:
    def test_aporte_requerido_y_ritmo(self, client, auth_headers, cuenta, crear_sobre):
        dentro_de_dos_meses = (datetime.now(UTC) + timedelta(days=75)).date().isoformat()
        fondo = crear_sobre(cuenta["id"], target_amount="1000.00", target_date=dentro_de_dos_meses)
        assert fondo["months_remaining"] in (2, 3)
        assert fondo["pace"] == "on_track"
        esperado = (D("1000.00") / fondo["months_remaining"]).quantize(D("0.01"), rounding="ROUND_CEILING")
        assert _money(fondo["required_contribution"]) == esperado

        _aportar(client, auth_headers, fondo["id"], "400.00")
        actualizado = client.get(f"{URL}{fondo['id']}", headers=auth_headers).json()
        assert _money(actualizado["balance"]) == D("400.00")
        assert _money(actualizado["remaining"]) == D("600.00")
        assert actualizado["progress_pct"] == 40.0

    def test_cumplido(self, client, auth_headers, cuenta, crear_sobre):
        fondo = crear_sobre(cuenta["id"], target_amount="100.00")
        _aportar(client, auth_headers, fondo["id"], "100.00")
        detalle = client.get(f"{URL}{fondo['id']}", headers=auth_headers).json()
        assert detalle["pace"] == "completed"
        assert detalle["required_contribution"] is None

    def test_sin_fecha_no_hay_ritmo(self, crear_sobre, cuenta):
        fondo = crear_sobre(cuenta["id"])
        assert fondo["pace"] is None
        assert fondo["required_contribution"] is None
        assert fondo["months_remaining"] is None


class TestMovimientos:
    def test_aportar_y_retirar_no_tocan_la_cuenta_ni_crean_transacciones(
        self, client, auth_headers, cuenta, crear_sobre, db_session
    ):
        fondo = crear_sobre(cuenta["id"])
        antes = client.get(f"/api/v1/accounts/{cuenta['id']}", headers=auth_headers).json()["balance"]

        assert _aportar(client, auth_headers, fondo["id"], "300.50", note="  enero ").status_code == 200
        resp = _retirar(client, auth_headers, fondo["id"], "100.25")
        assert resp.status_code == 200
        assert _money(resp.json()["amount"]) == D("-100.25")
        assert resp.json()["type"] == "withdrawal"

        detalle = client.get(f"{URL}{fondo['id']}", headers=auth_headers).json()
        assert _money(detalle["balance"]) == D("200.25")
        assert [e["type"] for e in detalle["entries"]] == ["withdrawal", "contribution"]
        assert detalle["entries"][1]["note"] == "enero"
        assert len(detalle["entries"][0]["period"]) == 7
        despues = client.get(f"/api/v1/accounts/{cuenta['id']}", headers=auth_headers).json()["balance"]
        assert _money(despues) == _money(antes)
        assert db_session.query(models.Transaction).count() == 0
        assert db_session.query(models.FundEntry).filter(models.FundEntry.transaction_id.isnot(None)).count() == 0

    def test_retiro_mayor_al_saldo_422(self, client, auth_headers, cuenta, crear_sobre):
        fondo = crear_sobre(cuenta["id"])
        _aportar(client, auth_headers, fondo["id"], "100.00")
        assert _retirar(client, auth_headers, fondo["id"], "100.01").status_code == 422
        assert _retirar(client, auth_headers, fondo["id"], "100.00").status_code == 200

    @pytest.mark.parametrize("monto", ["0", "-1", "1.005", "abc"])
    def test_monto_invalido_422(self, client, auth_headers, cuenta, crear_sobre, monto):
        fondo = crear_sobre(cuenta["id"])
        assert _aportar(client, auth_headers, fondo["id"], monto).status_code == 422

    def test_aporte_mayor_al_saldo_de_la_cuenta_no_bloquea(self, client, auth_headers, cuenta, crear_sobre):
        fondo = crear_sobre(cuenta["id"])
        assert _aportar(client, auth_headers, fondo["id"], "999999.00").status_code == 200
        detalle = client.get(f"{URL}{fondo['id']}", headers=auth_headers).json()
        assert _money(detalle["backing_shortfall"]) == D("994999.00")

    def test_aporte_a_archivado_409(self, client, auth_headers, cuenta, crear_sobre):
        fondo = crear_sobre(cuenta["id"])
        assert client.post(f"{URL}{fondo['id']}/archive", headers=auth_headers).status_code == 200
        assert _aportar(client, auth_headers, fondo["id"], "10.00").status_code == 409
        assert _retirar(client, auth_headers, fondo["id"], "10.00").status_code == 409


class TestEditarYArchivar:
    def test_put_parcial(self, client, auth_headers, cuenta, crear_sobre):
        fondo = crear_sobre(cuenta["id"])
        resp = client.put(f"{URL}{fondo['id']}", json={"name": "Seguro 2027"}, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["name"] == "Seguro 2027"
        assert _money(resp.json()["target_amount"]) == D("1200.00")

    def test_put_cambia_la_meta_y_quita_la_fecha(self, client, auth_headers, cuenta, crear_sobre):
        futura = (datetime.now(UTC) + timedelta(days=90)).date().isoformat()
        fondo = crear_sobre(cuenta["id"], target_date=futura)
        resp = client.put(
            f"{URL}{fondo['id']}", json={"target_amount": "2000.00", "target_date": None}, headers=auth_headers
        )
        assert resp.status_code == 200
        assert _money(resp.json()["target_amount"]) == D("2000.00")
        assert resp.json()["target_date"] is None

    def test_put_meses_en_un_sobre_que_no_es_emergencia_422(self, client, auth_headers, cuenta, crear_sobre):
        fondo = crear_sobre(cuenta["id"])
        resp = client.put(f"{URL}{fondo['id']}", json={"target_months": 3}, headers=auth_headers)
        assert resp.status_code == 422

    def test_put_otra_moneda_422(self, client, auth_headers, cuenta, crear_sobre, make_account):
        usd = make_account(auth_headers, name="USD", currency="USD")
        fondo = crear_sobre(cuenta["id"])
        resp = client.put(f"{URL}{fondo['id']}", json={"account_id": usd["id"]}, headers=auth_headers)
        assert resp.status_code == 422

    def test_put_misma_moneda_mueve_el_sobre(self, client, auth_headers, cuenta, crear_sobre, make_account):
        otra = make_account(auth_headers, name="Otra COP")
        fondo = crear_sobre(cuenta["id"])
        resp = client.put(f"{URL}{fondo['id']}", json={"account_id": otra["id"]}, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["account_id"] == otra["id"]

    def test_archivar_con_saldo_409_y_luego_ok(self, client, auth_headers, cuenta, crear_sobre):
        fondo = crear_sobre(cuenta["id"])
        _aportar(client, auth_headers, fondo["id"], "50.00")
        assert client.post(f"{URL}{fondo['id']}/archive", headers=auth_headers).status_code == 409
        _retirar(client, auth_headers, fondo["id"], "50.00")
        resp = client.post(f"{URL}{fondo['id']}/archive", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "archived"

        assert client.get(URL, headers=auth_headers).json() == []
        assert len(client.get(f"{URL}?include_archived=true", headers=auth_headers).json()) == 1
        assert client.post(f"{URL}{fondo['id']}/unarchive", headers=auth_headers).json()["status"] == "active"
        assert len(client.get(URL, headers=auth_headers).json()) == 1

    def test_borrar_cuenta_con_sobre_activo_400(self, client, auth_headers, cuenta, crear_sobre):
        fondo = crear_sobre(cuenta["id"])
        assert client.delete(f"/api/v1/accounts/{cuenta['id']}", headers=auth_headers).status_code == 400
        client.post(f"{URL}{fondo['id']}/archive", headers=auth_headers)
        assert client.delete(f"/api/v1/accounts/{cuenta['id']}", headers=auth_headers).status_code == 200


class TestAislamiento:
    """T4: un usuario no ve, edita, aporta, retira ni archiva sobres ajenos."""

    def test_sobre_ajeno_es_404_en_todo(self, client, other_user, cuenta, crear_sobre, auth_headers):
        fondo = crear_sobre(cuenta["id"])
        otro = other_user["headers"]
        base = f"{URL}{fondo['id']}"
        assert client.get(base, headers=otro).status_code == 404
        assert client.put(base, json={"name": "hack"}, headers=otro).status_code == 404
        assert _aportar(client, otro, fondo["id"], "10.00").status_code == 404
        assert _retirar(client, otro, fondo["id"], "10.00").status_code == 404
        assert client.post(f"{base}/archive", headers=otro).status_code == 404
        assert client.post(f"{base}/unarchive", headers=otro).status_code == 404
        assert client.get(URL, headers=otro).json() == []
        assert client.get(base, headers=auth_headers).json()["name"] == "Seguro"

    def test_el_disponible_de_otro_usuario_no_se_ve_afectado(
        self, client, other_user, cuenta, crear_sobre, auth_headers, make_account
    ):
        make_account(other_user["headers"], balance="700.00")
        fondo = crear_sobre(cuenta["id"])
        _aportar(client, auth_headers, fondo["id"], "1000.00")
        resumen = client.get("/api/v1/dashboard/summary", headers=other_user["headers"]).json()
        assert {c["currency"]: _money(c["total"]) for c in resumen["committed"]}.get("COP", D(0)) == D(0)


class TestDisponibleReal:
    """T3: committed / free_to_spend / accounts_total del summary del dashboard."""

    def _resumen(self, client, headers, query=""):
        resp = client.get(f"/api/v1/dashboard/summary{query}", headers=headers)
        assert resp.status_code == 200, resp.text
        return resp.json()

    @staticmethod
    def _por_moneda(lista):
        return {c["currency"]: _money(c["total"]) for c in lista}

    def test_resta_lo_apartado_de_todas_las_cuentas(self, client, auth_headers, make_account, crear_sobre):
        destacada = make_account(auth_headers, name="Destacada", balance="1000.00", highlighted=True)
        no_destacada = make_account(auth_headers, name="No destacada", balance="500.00")
        s1 = crear_sobre(destacada["id"], name="A")
        s2 = crear_sobre(no_destacada["id"], name="B")
        _aportar(client, auth_headers, s1["id"], "300.00")
        _aportar(client, auth_headers, s2["id"], "200.00")

        resumen = self._resumen(client, auth_headers)
        assert self._por_moneda(resumen["accounts_total"])["COP"] == D("1500.00")
        assert self._por_moneda(resumen["committed"])["COP"] == D("500.00")
        assert self._por_moneda(resumen["free_to_spend"])["COP"] == D("1000.00")
        # `balances` sigue filtrando por destacadas: no cambia con los sobres
        assert self._por_moneda(resumen["balances"])["COP"] == D("1000.00")

    def test_retirar_devuelve_el_disponible(self, client, auth_headers, cuenta, crear_sobre):
        fondo = crear_sobre(cuenta["id"])
        _aportar(client, auth_headers, fondo["id"], "1000.00")
        assert self._por_moneda(self._resumen(client, auth_headers)["free_to_spend"])["COP"] == D("4000.00")
        _retirar(client, auth_headers, fondo["id"], "400.00")
        assert self._por_moneda(self._resumen(client, auth_headers)["free_to_spend"])["COP"] == D("4400.00")

    def test_negativo_no_bloquea(self, client, auth_headers, cuenta, crear_sobre):
        fondo = crear_sobre(cuenta["id"])
        assert _aportar(client, auth_headers, fondo["id"], "7000.00").status_code == 200
        resumen = self._resumen(client, auth_headers)
        assert self._por_moneda(resumen["free_to_spend"])["COP"] == D("-2000.00")

    def test_multi_moneda_preferida_primero(self, client, auth_headers, make_account, crear_sobre):
        cop = make_account(auth_headers, name="COP", currency="COP", balance="1000.00")
        usd = make_account(auth_headers, name="USD", currency="USD", balance="50.00")
        _aportar(client, auth_headers, crear_sobre(usd["id"], target_amount="40.00")["id"], "20.00")
        resumen = self._resumen(client, auth_headers)
        assert resumen["free_to_spend"][0]["currency"] == "COP"
        libre = self._por_moneda(resumen["free_to_spend"])
        assert libre["COP"] == D("1000.00")  # la cuenta por defecto del registro tiene saldo 0
        assert libre["USD"] == D("30.00")
        assert self._por_moneda(resumen["committed"])["USD"] == D("20.00")
        assert cop["currency"] == "COP"

    def test_no_depende_del_mes_consultado(self, client, auth_headers, cuenta, crear_sobre, db_session):
        fondo = crear_sobre(cuenta["id"])
        _aportar(client, auth_headers, fondo["id"], "100.00")
        hoy = datetime.now(UTC)
        mes_anterior = hoy.replace(day=1) - timedelta(days=1)
        # un mes anterior a la primera transacción igual responde (es solo el summary del mes)
        actual = self._resumen(client, auth_headers)
        historico = self._resumen(client, auth_headers, f"?year={mes_anterior.year}&month={mes_anterior.month}")
        assert actual["free_to_spend"] == historico["free_to_spend"]
        assert actual["committed"] == historico["committed"]

    def test_sin_sobres_free_es_el_total(self, client, auth_headers, cuenta):
        resumen = self._resumen(client, auth_headers)
        assert self._por_moneda(resumen["free_to_spend"]) == self._por_moneda(resumen["accounts_total"])
        assert self._por_moneda(resumen["committed"])["COP"] == D("0")

    def test_sobre_archivado_no_compromete(self, client, auth_headers, cuenta, crear_sobre):
        fondo = crear_sobre(cuenta["id"])
        client.post(f"{URL}{fondo['id']}/archive", headers=auth_headers)
        assert self._por_moneda(self._resumen(client, auth_headers)["committed"])["COP"] == D("0")


class TestSinRespaldo:
    def test_faltante_cuando_la_cuenta_baja_de_lo_apartado(
        self, client, auth_headers, make_account, make_category, crear_sobre
    ):
        cuenta = make_account(auth_headers, balance="1000.00")
        cat = make_category(auth_headers)
        a = crear_sobre(cuenta["id"], name="A")
        b = crear_sobre(cuenta["id"], name="B")
        _aportar(client, auth_headers, a["id"], "600.00")
        _aportar(client, auth_headers, b["id"], "300.00")
        assert _money(client.get(f"{URL}{a['id']}", headers=auth_headers).json()["backing_shortfall"]) == D("0")

        # gasta 500 de la cuenta (queda 500 vs 900 apartados)
        resp = client.post(
            "/api/v1/transactions/",
            json={"amount": "500.00", "type": "expense", "account_id": cuenta["id"], "category_id": cat["id"]},
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        for fondo in (a, b):
            detalle = client.get(f"{URL}{fondo['id']}", headers=auth_headers).json()
            assert _money(detalle["backing_shortfall"]) == D("400.00")


class TestSinRespaldoCuentaNegativa:
    def test_sobre_vacio_en_cuenta_con_saldo_negativo_no_esta_sin_respaldo(
        self, client, auth_headers, make_account, make_category, crear_sobre
    ):
        cuenta = make_account(auth_headers, balance="100.00")
        cat = make_category(auth_headers)
        client.post(
            "/api/v1/transactions/",
            json={"amount": "300.00", "type": "expense", "account_id": cuenta["id"], "category_id": cat["id"]},
            headers=auth_headers,
        )  # saldo -200
        fondo = crear_sobre(cuenta["id"])
        assert _money(client.get(f"{URL}{fondo['id']}", headers=auth_headers).json()["backing_shortfall"]) == D("0")
        _aportar(client, auth_headers, fondo["id"], "50.00")
        # con 50 apartados y saldo -200, faltan los 50 completos (no 250)
        assert _money(client.get(f"{URL}{fondo['id']}", headers=auth_headers).json()["backing_shortfall"]) == D("50.00")


class TestHallazgosDeRevision:
    def test_no_se_cambia_la_moneda_de_una_cuenta_con_sobres(self, client, auth_headers, make_account, crear_sobre):
        cuenta = make_account(auth_headers, balance="0.00")
        crear_sobre(cuenta["id"])
        resp = client.put(
            f"/api/v1/accounts/{cuenta['id']}",
            json={"name": cuenta["name"], "type": cuenta["type"], "currency": "USD"},
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert client.get(f"/api/v1/accounts/{cuenta['id']}", headers=auth_headers).json()["currency"] == "COP"

    def test_un_archivado_no_hereda_el_faltante_de_la_cuenta(self, client, auth_headers, make_account, crear_sobre):
        cuenta = make_account(auth_headers, balance="100.00")
        activo = crear_sobre(cuenta["id"], name="Activo")
        viejo = crear_sobre(cuenta["id"], name="Viejo")
        client.post(f"{URL}{viejo['id']}/archive", headers=auth_headers)
        _aportar(client, auth_headers, activo["id"], "500.00")
        lista = client.get(f"{URL}?include_archived=true", headers=auth_headers).json()
        faltantes = {f["name"]: _money(f["backing_shortfall"]) for f in lista}
        assert faltantes == {"Activo": D("400.00"), "Viejo": D("0.00")}

    def test_un_archivado_no_se_edita(self, client, auth_headers, cuenta, crear_sobre):
        fondo = crear_sobre(cuenta["id"])
        client.post(f"{URL}{fondo['id']}/archive", headers=auth_headers)
        resp = client.put(f"{URL}{fondo['id']}", json={"name": "otro"}, headers=auth_headers)
        assert resp.status_code == 409


class TestAporteSugeridoDelMes:
    def test_lo_aportado_este_mes_descuenta_la_cuota(self, client, auth_headers, cuenta, crear_sobre):
        """Meta 1000 en ~2 meses: cuota 500. Tras aportar 500 ya no se sugiere nada este mes."""
        fecha = (datetime.now(UTC) + timedelta(days=75)).date().isoformat()
        fondo = crear_sobre(cuenta["id"], target_amount="1000.00", target_date=fecha)
        meses = fondo["months_remaining"]
        cuota = _money(fondo["required_contribution"])
        assert cuota == (D("1000.00") / meses).quantize(D("0.01"), rounding="ROUND_CEILING")

        _aportar(client, auth_headers, fondo["id"], str(cuota))
        tras = client.get(f"{URL}{fondo['id']}", headers=auth_headers).json()
        assert tras["required_contribution"] is None  # cuota del mes cumplida

        _retirar(client, auth_headers, fondo["id"], "10.00")
        tras = client.get(f"{URL}{fondo['id']}", headers=auth_headers).json()
        assert _money(tras["required_contribution"]) == D("10.00")  # repone lo retirado


class TestEmergenciaConHistorial:
    def test_meta_en_meses_usa_el_promedio(
        self, client, auth_headers, test_user, cuenta, make_category, crear_sobre, db_session
    ):
        cat = make_category(auth_headers)
        ahora = datetime.now(UTC)
        for meses_atras in (1, 2, 3):
            primero = ahora.replace(day=1, hour=17, minute=0, second=0, microsecond=0)
            fecha = primero
            for _ in range(meses_atras):
                fecha = (fecha - timedelta(days=1)).replace(day=1)  # primer día del mes anterior
            fecha = fecha.replace(day=15)
            db_session.add(
                models.Transaction(
                    user_id=test_user["id"],
                    account_id=cuenta["id"],
                    category_id=cat["id"],
                    amount=D("1000.00"),
                    currency="COP",
                    type="expense",
                    date=fecha,
                )
            )
        db_session.commit()

        fondo = crear_sobre(cuenta["id"], kind="emergency", target_amount=None, target_months=3)
        assert _money(fondo["monthly_expense_avg"]) == D("1000.00")
        assert _money(fondo["target_amount"]) == D("3000.00")
        _aportar(client, auth_headers, fondo["id"], "1500.00")
        detalle = client.get(f"{URL}{fondo['id']}", headers=auth_headers).json()
        assert _money(detalle["runway_months"]) == D("1.5")
        assert detalle["progress_pct"] == 50.0


class TestCascadaYDB:
    def test_borrar_usuario_con_sobres(self, client, test_user, auth_headers, cuenta, crear_sobre, db_session):
        fondo = crear_sobre(cuenta["id"])
        _aportar(client, auth_headers, fondo["id"], "10.00")
        usuario = db_session.query(models.User).filter(models.User.id == test_user["id"]).one()
        delete_user_cascade(db_session, usuario)
        db_session.commit()
        assert db_session.query(models.Fund).count() == 0
        assert db_session.query(models.FundEntry).count() == 0

    def test_checks_de_base_de_datos(self, db_session, test_user, cuenta):
        """Los CHECK son garantía de DB, no solo de aplicación (B1, B2)."""
        import sqlalchemy as sa

        def _fund(**kw):
            base = {
                "user_id": test_user["id"],
                "account_id": cuenta["id"],
                "name": "x",
                "kind": "goal",
                "currency": "COP",
                "target_amount": D("10"),
                "status": "active",
            }
            base.update(kw)
            return models.Fund(**base)

        for malo in (
            {"target_amount": None},  # ni monto ni meses
            {"target_months": 3},  # ambos
            {"kind": "otro"},
            {"target_amount": D("0")},
        ):
            db_session.add(_fund(**malo))
            with pytest.raises(sa.exc.IntegrityError):
                db_session.flush()
            db_session.rollback()

        ok = _fund()
        db_session.add(ok)
        db_session.flush()
        for tipo, monto in (("contribution", D("-1")), ("withdrawal", D("1")), ("contribution", D("0"))):
            db_session.add(
                models.FundEntry(fund_id=ok.id, user_id=test_user["id"], amount=monto, type=tipo, period="2026-10")
            )
            with pytest.raises(sa.exc.IntegrityError):
                db_session.flush()
            db_session.rollback()


class TestGastoAnualExigeFecha:
    """A4: un gasto anual sin vencimiento no es un gasto anual (sin CHECK ni migración)."""

    def _futura(self) -> str:
        return (datetime.now(UTC) + timedelta(days=90)).date().isoformat()

    def test_crear_sin_fecha_422(self, client, auth_headers, cuenta):
        body = {"name": "Seguro", "kind": "annual_expense", "account_id": cuenta["id"], "target_amount": "1200.00"}
        assert client.post(URL, json=body, headers=auth_headers).status_code == 422

    def test_crear_con_fecha_ok(self, crear_sobre, cuenta):
        fondo = crear_sobre(cuenta["id"], kind="annual_expense", target_date=self._futura())
        assert fondo["kind"] == "annual_expense"
        assert fondo["target_date"] == self._futura()

    @pytest.mark.parametrize("kind", ["goal", "emergency"])
    def test_goal_y_emergencia_siguen_con_fecha_opcional(self, client, auth_headers, cuenta, kind):
        body = {"name": "X", "kind": kind, "account_id": cuenta["id"], "target_amount": "500.00"}
        assert client.post(URL, json=body, headers=auth_headers).status_code == 200

    def test_put_con_fecha_null_en_gasto_anual_422(self, client, auth_headers, cuenta, crear_sobre):
        fondo = crear_sobre(cuenta["id"], kind="annual_expense", target_date=self._futura())
        resp = client.put(f"{URL}{fondo['id']}", json={"target_date": None}, headers=auth_headers)
        assert resp.status_code == 422
        # la fecha sigue ahí
        assert client.get(f"{URL}{fondo['id']}", headers=auth_headers).json()["target_date"] == self._futura()

    def test_put_con_fecha_null_en_goal_ok(self, client, auth_headers, cuenta, crear_sobre):
        fondo = crear_sobre(cuenta["id"], target_date=self._futura())
        resp = client.put(f"{URL}{fondo['id']}", json={"target_date": None}, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["target_date"] is None

    def test_put_solo_nombre_en_sobre_legado_sin_fecha_ok(self, client, auth_headers, cuenta, crear_sobre, db_session):
        fondo = crear_sobre(cuenta["id"], kind="annual_expense", target_date=self._futura())
        # Fila legada de antes de A4: gasto anual sin fecha.
        db_session.query(models.Fund).filter(models.Fund.id == fondo["id"]).update({"target_date": None})
        db_session.commit()
        resp = client.put(f"{URL}{fondo['id']}", json={"name": "Seguro 2027"}, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["name"] == "Seguro 2027"
        assert resp.json()["target_date"] is None


class TestProximaCuotaAPI:
    """A2: `next_month_contribution` convive con `required_contribution` (que no cambia)."""

    def _fecha_en_meses(self, meses: int) -> str:
        return (datetime.now(UTC) + timedelta(days=30 * meses + 10)).date().isoformat()

    def test_cuota_cumplida_expone_la_proxima(self, client, auth_headers, cuenta, crear_sobre):
        fondo = crear_sobre(cuenta["id"], target_amount="2000.00", target_date=self._fecha_en_meses(3))
        meses = fondo["months_remaining"]
        assert meses >= 3
        assert fondo["next_month_contribution"] is not None
        _aportar(client, auth_headers, fondo["id"], "2000.00")
        _retirar(client, auth_headers, fondo["id"], "1000.00")  # neto del mes 1000, faltan 1000
        detalle = client.get(f"{URL}{fondo['id']}", headers=auth_headers).json()
        esperado = (D("1000.00") / (meses - 1)).quantize(D("0.01"), rounding="ROUND_CEILING")
        assert _money(detalle["next_month_contribution"]) == esperado

    def test_aporte_grande_cumple_la_cuota_y_deja_la_proxima(self, client, auth_headers, cuenta, crear_sobre):
        fondo = crear_sobre(cuenta["id"], target_amount="2000.00", target_date=self._fecha_en_meses(2))
        meses = fondo["months_remaining"]
        _aportar(client, auth_headers, fondo["id"], "1000.00")
        detalle = client.get(f"{URL}{fondo['id']}", headers=auth_headers).json()
        assert detalle["required_contribution"] is None  # la de este mes quedó cumplida
        assert _money(detalle["remaining"]) == D("1000.00")
        esperado = (D("1000.00") / (meses - 1)).quantize(D("0.01"), rounding="ROUND_CEILING")
        assert _money(detalle["next_month_contribution"]) == esperado

    def test_sin_fecha_es_null(self, crear_sobre, cuenta):
        assert crear_sobre(cuenta["id"])["next_month_contribution"] is None

    def test_meta_cumplida_es_null(self, client, auth_headers, cuenta, crear_sobre):
        fondo = crear_sobre(cuenta["id"], target_amount="100.00", target_date=self._fecha_en_meses(3))
        _aportar(client, auth_headers, fondo["id"], "100.00")
        assert client.get(f"{URL}{fondo['id']}", headers=auth_headers).json()["next_month_contribution"] is None

    def test_ultimo_mes_es_null(self, crear_sobre, cuenta):
        hoy_mas_dos_dias = (datetime.now(UTC) + timedelta(days=1)).date().isoformat()
        fondo = crear_sobre(cuenta["id"], target_amount="100.00", target_date=hoy_mas_dos_dias)
        assert fondo["months_remaining"] in (1, 2)
        if fondo["months_remaining"] == 1:
            assert fondo["next_month_contribution"] is None


class TestBorrarSobre:
    """A1: DELETE borra el sobre y sus movimientos, en cualquier estado y con cualquier saldo."""

    def test_borrar_con_saldo_libera_el_disponible(self, client, auth_headers, cuenta, crear_sobre, db_session):
        fondo = crear_sobre(cuenta["id"])
        _aportar(client, auth_headers, fondo["id"], "300.00")
        antes = client.get("/api/v1/dashboard/summary", headers=auth_headers).json()
        assert _money(antes["committed"][0]["total"]) == D("300.00")

        resp = client.delete(f"{URL}{fondo['id']}", headers=auth_headers)
        assert resp.status_code == 204
        assert resp.content == b""

        despues = client.get("/api/v1/dashboard/summary", headers=auth_headers).json()
        assert despues["committed"] == [] or _money(despues["committed"][0]["total"]) == D("0.00")
        assert _money(despues["free_to_spend"][0]["total"]) == D("5000.00")
        assert client.get(f"{URL}{fondo['id']}", headers=auth_headers).status_code == 404
        assert client.get(URL, headers=auth_headers).json() == []
        # movimientos borrados, sin huérfanos
        assert db_session.query(models.FundEntry).filter(models.FundEntry.fund_id == fondo["id"]).count() == 0

    def test_la_cuenta_y_las_transacciones_quedan_intactas(self, client, auth_headers, cuenta, crear_sobre, db_session):
        fondo = crear_sobre(cuenta["id"])
        _aportar(client, auth_headers, fondo["id"], "300.00")
        saldo_antes = client.get(f"/api/v1/accounts/{cuenta['id']}", headers=auth_headers).json()["balance"]
        assert client.delete(f"{URL}{fondo['id']}", headers=auth_headers).status_code == 204
        saldo_despues = client.get(f"/api/v1/accounts/{cuenta['id']}", headers=auth_headers).json()["balance"]
        assert _money(saldo_antes) == _money(saldo_despues) == D("5000.00")

    def test_borrar_un_archivado(self, client, auth_headers, cuenta, crear_sobre):
        fondo = crear_sobre(cuenta["id"])
        assert client.post(f"{URL}{fondo['id']}/archive", headers=auth_headers).status_code == 200
        assert client.delete(f"{URL}{fondo['id']}", headers=auth_headers).status_code == 204
        assert client.get(f"{URL}?include_archived=true", headers=auth_headers).json() == []

    def test_sobre_inexistente_404(self, client, auth_headers):
        assert client.delete(f"{URL}999999", headers=auth_headers).status_code == 404

    def test_sobre_ajeno_404_y_sigue_existiendo(self, client, other_user, auth_headers, cuenta, crear_sobre):
        fondo = crear_sobre(cuenta["id"])
        _aportar(client, auth_headers, fondo["id"], "50.00")
        resp = client.delete(f"{URL}{fondo['id']}", headers=other_user["headers"])
        assert resp.status_code == 404
        assert resp.json()["detail"] == "El sobre no existe o no tienes permisos."
        assert _money(client.get(f"{URL}{fondo['id']}", headers=auth_headers).json()["balance"]) == D("50.00")

    def test_requiere_autenticacion(self, client):
        assert client.delete(f"{URL}1").status_code in (401, 403)

    def test_borrar_la_cuenta_despues_de_borrar_su_sobre(self, client, auth_headers, cuenta, crear_sobre):
        fondo = crear_sobre(cuenta["id"])
        assert client.delete(f"/api/v1/accounts/{cuenta['id']}", headers=auth_headers).status_code == 400
        assert client.delete(f"{URL}{fondo['id']}", headers=auth_headers).status_code == 204
        assert client.delete(f"/api/v1/accounts/{cuenta['id']}", headers=auth_headers).status_code == 200
