"""API de CDT (Fase 38 T2-T5, T7).

El "hoy" se fija con `freeze_time` (zona del usuario: America/Bogota por defecto, UTC-5).
`HOY` = 2026-03-15 10:00 hora de Bogotá.
"""

from datetime import date
from decimal import Decimal

import pytest
from freezegun import freeze_time

from app.core.user_deletion import delete_user_cascade
from app.models import models

D = Decimal
URL = "/api/v1/cdts/"
SUMMARY = "/api/v1/dashboard/summary"
AHORA = "2026-03-15T15:00:00Z"  # 10:00 en Bogotá

pytestmark = pytest.mark.usefixtures("_congelar")


@pytest.fixture
def _congelar():
    with freeze_time(AHORA):
        yield


def _money(valor) -> Decimal:
    return Decimal(str(valor))


@pytest.fixture
def crear_cdt(client, auth_headers):
    def _factory(headers: dict | None = None, **extra) -> dict:
        body = {
            "name": "CDT Bancolombia",
            "currency": "COP",
            "principal": "1000.00",
            "rate_ea": "10",
            "opened_on": "2025-03-15",  # hoy = 365 días transcurridos
            "maturity_on": "2026-09-15",
        }
        body.update(extra)
        resp = client.post(URL, json=body, headers=headers or auth_headers)
        assert resp.status_code == 200, resp.text
        return resp.json()

    return _factory


class TestCrear:
    def test_crea_y_calcula_las_cifras(self, crear_cdt):
        cdt = crear_cdt(name="  CDT Nu  ")
        assert cdt["name"] == "CDT Nu"
        assert cdt["status"] == "active"
        assert cdt["term_days"] == 549
        assert cdt["elapsed_days"] == 365
        assert _money(cdt["accrued_interest"]) == D("100.00")
        assert _money(cdt["current_value"]) == D("1100.00")
        assert cdt["days_to_maturity"] == 184
        assert cdt["alert"] == "ok"
        assert cdt["redeemed_on"] is None
        assert cdt["final_amount"] is None
        assert cdt["realized_interest"] is None
        assert _money(cdt["maturity_value"]) == _money(cdt["principal"]) + _money(cdt["maturity_interest"])

    def test_moneda_por_defecto_cop(self, client, auth_headers):
        resp = client.post(
            URL,
            json={
                "name": "X",
                "principal": "10",
                "rate_ea": "5",
                "opened_on": "2026-03-01",
                "maturity_on": "2026-09-01",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["currency"] == "COP"

    @pytest.mark.parametrize(
        "extra",
        [
            {"rate_ea": "0"},
            {"rate_ea": "101"},
            {"rate_ea": "-1"},
            {"rate_ea": "10.12345"},
            {"principal": "0"},
            {"principal": "-5"},
            {"principal": "1.234"},
            {"principal": "1000000000000"},  # 13 dígitos enteros: desborda Numeric(14,2)
            {"currency": "pesos"},
            {"currency": "cop"},
            {"name": "   "},
            {"name": "x" * 101},
            {"maturity_on": "2025-03-15"},  # == opened_on
            {"maturity_on": "2025-01-01"},  # < opened_on
            {"maturity_on": "2035-03-16"},  # plazo > 10 años
            {"opened_on": "2016-03-14", "maturity_on": "2017-03-14"},  # apertura hace > 10 años
            {"opened_on": "2027-03-16", "maturity_on": "2028-03-16"},  # apertura > 1 año en el futuro
        ],
    )
    def test_validaciones_422(self, client, auth_headers, extra):
        body = {
            "name": "CDT",
            "currency": "COP",
            "principal": "1000.00",
            "rate_ea": "10",
            "opened_on": "2025-03-15",
            "maturity_on": "2026-09-15",
        }
        body.update(extra)
        assert client.post(URL, json=body, headers=auth_headers).status_code == 422

    def test_borde_permitido_apertura_manana_y_plazo_diez_anios(self, client, auth_headers):
        body = {
            "name": "Largo",
            "principal": "1000.00",
            "rate_ea": "100",
            "opened_on": "2026-03-16",
            "maturity_on": "2036-03-16",
        }
        assert client.post(URL, json=body, headers=auth_headers).status_code == 200

    def test_tope_de_50(self, client, auth_headers, crear_cdt):
        for i in range(50):
            crear_cdt(name=f"CDT {i}")
        resp = client.post(
            URL,
            json={
                "name": "51",
                "principal": "1",
                "rate_ea": "5",
                "opened_on": "2026-03-01",
                "maturity_on": "2026-09-01",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_requiere_autenticacion(self, client):
        assert client.get(URL).status_code == 401


class TestEditar:
    def test_edita_un_vigente(self, client, auth_headers, crear_cdt):
        cdt = crear_cdt()
        resp = client.put(
            f"{URL}{cdt['id']}",
            json={"name": "Corregido", "rate_ea": "12.5", "principal": "2000.00"},
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        cuerpo = resp.json()
        assert cuerpo["name"] == "Corregido"
        assert _money(cuerpo["rate_ea"]) == D("12.5")
        assert _money(cuerpo["principal"]) == D("2000.00")
        assert cuerpo["maturity_on"] == "2026-09-15"  # lo no enviado no cambia

    def test_validacion_de_fechas_con_el_resultado_combinado(self, client, auth_headers, crear_cdt):
        cdt = crear_cdt()
        resp = client.put(f"{URL}{cdt['id']}", json={"maturity_on": "2025-01-01"}, headers=auth_headers)
        assert resp.status_code == 422

    @pytest.mark.parametrize("body", [{"status": "redeemed"}, {"id": 5}, {"name": None}, {"rate_ea": 0}])
    def test_campos_desconocidos_nulos_o_invalidos_son_422(self, client, auth_headers, crear_cdt, body):
        cdt = crear_cdt()
        assert client.put(f"{URL}{cdt['id']}", json=body, headers=auth_headers).status_code == 422

    def test_redimido_responde_409(self, client, auth_headers, crear_cdt):
        cdt = crear_cdt()
        assert client.post(f"{URL}{cdt['id']}/redeem", json={}, headers=auth_headers).status_code == 200
        assert client.put(f"{URL}{cdt['id']}", json={"name": "Otro"}, headers=auth_headers).status_code == 409


class TestAislamiento:
    def test_otro_usuario_recibe_404(self, client, auth_headers, other_user, crear_cdt):
        cdt = crear_cdt()
        otro = other_user["headers"]
        assert client.put(f"{URL}{cdt['id']}", json={"name": "x"}, headers=otro).status_code == 404
        assert client.post(f"{URL}{cdt['id']}/redeem", json={}, headers=otro).status_code == 404
        assert client.delete(f"{URL}{cdt['id']}", headers=otro).status_code == 404
        assert client.get(URL, headers=otro).json() == {"items": [], "totals": []}
        # El dueño sigue viéndolo intacto.
        assert len(client.get(URL, headers=auth_headers).json()["items"]) == 1

    def test_inexistente_404(self, client, auth_headers):
        assert client.delete(f"{URL}999999", headers=auth_headers).status_code == 404


class TestRedimir:
    def test_defaults_hoy_y_capital_mas_interes(self, client, auth_headers, crear_cdt):
        cdt = crear_cdt()
        resp = client.post(f"{URL}{cdt['id']}/redeem", json={}, headers=auth_headers)
        assert resp.status_code == 200, resp.text
        r = resp.json()
        assert r["status"] == "redeemed"
        assert r["redeemed_on"] == "2026-03-15"
        assert _money(r["final_amount"]) == D("1100.00")
        assert _money(r["realized_interest"]) == D("100.00")
        assert _money(r["current_value"]) == D("1100.00")
        assert r["days_to_maturity"] is None
        assert r["alert"] == "ok"

    def test_final_amount_explicito_y_fecha_anterior(self, client, auth_headers, crear_cdt):
        cdt = crear_cdt()
        resp = client.post(
            f"{URL}{cdt['id']}/redeem",
            json={"redeemed_on": "2026-01-10", "final_amount": "1050.50"},
            headers=auth_headers,
        )
        r = resp.json()
        assert r["redeemed_on"] == "2026-01-10"
        assert _money(r["final_amount"]) == D("1050.50")
        assert _money(r["realized_interest"]) == D("50.50")

    def test_redencion_anticipada_con_penalizacion_puede_dar_rendimiento_negativo(
        self, client, auth_headers, crear_cdt
    ):
        cdt = crear_cdt()
        r = client.post(f"{URL}{cdt['id']}/redeem", json={"final_amount": "980.00"}, headers=auth_headers).json()
        assert _money(r["realized_interest"]) == D("-20.00")

    def test_default_por_fecha_usa_los_dias_de_esa_fecha(self, client, auth_headers, crear_cdt):
        cdt = crear_cdt()
        r = client.post(f"{URL}{cdt['id']}/redeem", json={"redeemed_on": "2025-03-15"}, headers=auth_headers).json()
        assert _money(r["final_amount"]) == D("1000.00")

    @pytest.mark.parametrize(
        "body", [{"redeemed_on": "2026-03-16"}, {"redeemed_on": "2025-03-14"}, {"final_amount": "-1"}, {"x": 1}]
    )
    def test_invalidos_422(self, client, auth_headers, crear_cdt, body):
        cdt = crear_cdt()
        assert client.post(f"{URL}{cdt['id']}/redeem", json=body, headers=auth_headers).status_code == 422
        assert client.get(URL, headers=auth_headers).json()["items"][0]["status"] == "active"

    def test_doble_redencion_409(self, client, auth_headers, crear_cdt):
        cdt = crear_cdt()
        assert client.post(f"{URL}{cdt['id']}/redeem", json={}, headers=auth_headers).status_code == 200
        assert client.post(f"{URL}{cdt['id']}/redeem", json={}, headers=auth_headers).status_code == 409

    def test_no_crea_transaccion_ni_mueve_saldo(self, client, auth_headers, make_account, db_session, crear_cdt):
        cuenta = make_account(auth_headers, balance="5000.00")
        cdt = crear_cdt()
        client.post(f"{URL}{cdt['id']}/redeem", json={}, headers=auth_headers)
        assert db_session.query(models.Transaction).count() == 0
        saldo = client.get(f"/api/v1/accounts/{cuenta['id']}", headers=auth_headers).json()["balance"]
        assert _money(saldo) == D("5000.00")

    def test_borrar_redimido_es_real(self, client, auth_headers, crear_cdt, db_session):
        cdt = crear_cdt()
        client.post(f"{URL}{cdt['id']}/redeem", json={}, headers=auth_headers)
        assert client.delete(f"{URL}{cdt['id']}", headers=auth_headers).status_code == 204
        assert db_session.query(models.Cdt).count() == 0


class TestListaYTotales:
    def test_orden_vigentes_por_vencimiento_luego_redimidos_recientes_primero(self, client, auth_headers, crear_cdt):
        tarde = crear_cdt(name="Tarde", maturity_on="2027-01-01")
        temprano = crear_cdt(name="Temprano", maturity_on="2026-06-01")
        viejo = crear_cdt(name="Redimido viejo")
        nuevo = crear_cdt(name="Redimido nuevo")
        client.post(f"{URL}{viejo['id']}/redeem", json={"redeemed_on": "2026-01-01"}, headers=auth_headers)
        client.post(f"{URL}{nuevo['id']}/redeem", json={"redeemed_on": "2026-02-01"}, headers=auth_headers)
        items = client.get(URL, headers=auth_headers).json()["items"]
        assert [i["name"] for i in items] == ["Temprano", "Tarde", "Redimido nuevo", "Redimido viejo"]
        assert tarde["id"] != temprano["id"]

    def test_filtro_por_estado(self, client, auth_headers, crear_cdt):
        crear_cdt(name="Vigente")
        redimido = crear_cdt(name="Redimido")
        client.post(f"{URL}{redimido['id']}/redeem", json={}, headers=auth_headers)
        activos = client.get(f"{URL}?status=active", headers=auth_headers).json()
        assert [i["name"] for i in activos["items"]] == ["Vigente"]
        redimidos = client.get(f"{URL}?status=redeemed", headers=auth_headers).json()
        assert [i["name"] for i in redimidos["items"]] == ["Redimido"]
        assert client.get(f"{URL}?status=otro", headers=auth_headers).status_code == 422

    def test_totales_por_moneda_solo_de_vigentes(self, client, auth_headers, crear_cdt):
        crear_cdt(principal="1000.00")
        crear_cdt(principal="500.00")
        crear_cdt(principal="200.00", currency="USD")
        redimido = crear_cdt(principal="9999.00")
        client.post(f"{URL}{redimido['id']}/redeem", json={}, headers=auth_headers)
        totales = {t["currency"]: t for t in client.get(URL, headers=auth_headers).json()["totals"]}
        assert set(totales) == {"COP", "USD"}
        cop = totales["COP"]
        assert _money(cop["principal"]) == D("1500.00")
        assert _money(cop["accrued_interest"]) == D("150.00")
        assert _money(cop["current_value"]) == D("1650.00")
        assert _money(cop["maturity_value"]) > _money(cop["current_value"])
        assert _money(totales["USD"]["principal"]) == D("200.00")

    def test_orden_de_monedas_prefiere_la_moneda_del_usuario(self, client, auth_headers, crear_cdt):
        crear_cdt(currency="USD")
        crear_cdt(currency="COP")
        crear_cdt(currency="EUR")
        monedas = [t["currency"] for t in client.get(URL, headers=auth_headers).json()["totals"]]
        assert monedas == ["COP", "EUR", "USD"]

    @pytest.mark.parametrize(
        ("vence", "esperado", "dias"),
        [
            ("2026-03-31", "ok", 16),
            ("2026-03-30", "due_soon", 15),
            ("2026-03-15", "matured", 0),
            ("2026-03-10", "matured", -5),
        ],
    )
    def test_alerta_y_dias_para_vencer(self, crear_cdt, vence, esperado, dias):
        cdt = crear_cdt(maturity_on=vence)
        assert cdt["alert"] == esperado
        assert cdt["days_to_maturity"] == dias

    def test_vencido_deja_de_causar_interes(self, crear_cdt):
        cdt = crear_cdt(opened_on="2025-03-15", maturity_on="2025-09-15")
        assert cdt["elapsed_days"] == cdt["term_days"] == 184
        assert cdt["accrued_interest"] == cdt["maturity_interest"]


class TestZonaHoraria:
    """A las 15:00Z es 10:00 del 15 en Bogotá, pero ya es 05:00 del 16 en Kiritimati (UTC+14): el
    "hoy" local difiere del UTC y de la zona por defecto."""

    def _zona(self, client, headers, tz: str) -> None:
        r = client.patch("/api/v1/users/me/preferences", json={"timezone": tz}, headers=headers)
        assert r.status_code == 200, r.text

    def test_dias_para_vencer_usan_la_zona_y_no_mueven_las_fechas(self, client, auth_headers, crear_cdt):
        crear_cdt(maturity_on="2026-03-15")
        item = client.get(URL, headers=auth_headers).json()["items"][0]
        assert (item["days_to_maturity"], item["alert"]) == (0, "matured")
        self._zona(client, auth_headers, "Pacific/Kiritimati")
        item = client.get(URL, headers=auth_headers).json()["items"][0]
        assert item["maturity_on"] == "2026-03-15"
        assert (item["days_to_maturity"], item["alert"]) == (-1, "matured")

    def test_redimir_por_defecto_usa_el_dia_local(self, client, auth_headers, crear_cdt):
        cdt = crear_cdt()
        self._zona(client, auth_headers, "Pacific/Kiritimati")
        r = client.post(f"{URL}{cdt['id']}/redeem", json={}, headers=auth_headers).json()
        assert r["redeemed_on"] == "2026-03-16"  # el 15 en UTC y en Bogotá

    def test_no_se_puede_redimir_con_el_dia_utc_si_el_local_va_atras(self, client, auth_headers, crear_cdt):
        cdt = crear_cdt()
        # En Bogotá hoy es el 15: el 16 es futuro.
        resp = client.post(f"{URL}{cdt['id']}/redeem", json={"redeemed_on": "2026-03-16"}, headers=auth_headers)
        assert resp.status_code == 422


class TestDashboard:
    def _resumen(self, client, headers) -> dict:
        resp = client.get(SUMMARY, headers=headers)
        assert resp.status_code == 200, resp.text
        return resp.json()

    @staticmethod
    def _por_moneda(lista) -> dict:
        return {x["currency"]: _money(x["total"]) for x in lista}

    def test_sin_cdt_net_worth_es_accounts_total(self, client, auth_headers, make_account):
        make_account(auth_headers, balance="5000.00")
        r = self._resumen(client, auth_headers)
        assert self._por_moneda(r["cdt_total"]) == {"COP": D("0.00")}
        assert self._por_moneda(r["net_worth"]) == self._por_moneda(r["accounts_total"])

    def test_cdt_total_y_net_worth_por_moneda(self, client, auth_headers, make_account, crear_cdt):
        make_account(auth_headers, balance="5000.00")
        make_account(auth_headers, name="USD", currency="USD", balance="100.00")
        crear_cdt()  # COP 1000 + 100 de interés
        crear_cdt(currency="EUR", principal="300.00")  # moneda sin cuenta
        r = self._resumen(client, auth_headers)
        assert self._por_moneda(r["cdt_total"]) == {"COP": D("1100.00"), "EUR": D("330.00"), "USD": D("0.00")}
        assert self._por_moneda(r["net_worth"]) == {"COP": D("6100.00"), "EUR": D("330.00"), "USD": D("100.00")}
        assert r["net_worth"][0]["currency"] == "COP"  # la preferida va primero

    def test_redimido_no_cuenta(self, client, auth_headers, make_account, crear_cdt):
        make_account(auth_headers, balance="5000.00")
        cdt = crear_cdt()
        client.post(f"{URL}{cdt['id']}/redeem", json={}, headers=auth_headers)
        r = self._resumen(client, auth_headers)
        assert self._por_moneda(r["cdt_total"]) == {"COP": D("0.00")}
        assert self._por_moneda(r["net_worth"]) == {"COP": D("5000.00")}

    def test_contrato_el_cdt_no_cambia_disponible_comprometido_saldos_ni_sobres(
        self, client, auth_headers, make_account, crear_cdt
    ):
        cuenta = make_account(auth_headers, balance="5000.00")
        sobre = client.post(
            "/api/v1/funds/",
            json={"name": "Meta", "kind": "goal", "account_id": cuenta["id"], "target_amount": "1200.00"},
            headers=auth_headers,
        )
        assert sobre.status_code == 200, sobre.text
        aporte = client.post(
            f"/api/v1/funds/{sobre.json()['id']}/contributions", json={"amount": "700"}, headers=auth_headers
        )
        assert aporte.status_code == 200, aporte.text

        antes = self._resumen(client, auth_headers)
        sobres_antes = client.get("/api/v1/funds/", headers=auth_headers).json()
        cuentas_antes = client.get("/api/v1/accounts/", headers=auth_headers).json()

        cdt = crear_cdt(principal="900000.00")
        client.put(f"{URL}{cdt['id']}", json={"principal": "950000.00"}, headers=auth_headers)
        client.post(f"{URL}{cdt['id']}/redeem", json={}, headers=auth_headers)
        crear_cdt(principal="123.00")

        despues = self._resumen(client, auth_headers)
        for campo in (
            "free_to_spend",
            "committed",
            "accounts_total",
            "balances",
            "monthly_income_by_currency",
            "monthly_expense_by_currency",
            "monthly_flow_balance",
        ):
            assert despues[campo] == antes[campo], campo
        assert client.get("/api/v1/funds/", headers=auth_headers).json() == sobres_antes
        assert client.get("/api/v1/accounts/", headers=auth_headers).json() == cuentas_antes

    def test_ignora_year_month(self, client, auth_headers, make_account, crear_cdt):
        make_account(auth_headers, balance="5000.00")
        crear_cdt()
        r = client.get(f"{SUMMARY}?year=2026&month=1", headers=auth_headers).json()
        assert self._por_moneda(r["cdt_total"]) == {"COP": D("1100.00")}


class TestBorradoDeUsuario:
    def test_borrar_usuario_borra_sus_cdt(self, crear_cdt, db_session, test_user):
        crear_cdt()
        user = db_session.query(models.User).filter(models.User.id == test_user["id"]).one()
        delete_user_cascade(db_session, user)
        db_session.commit()
        assert db_session.query(models.Cdt).count() == 0


class TestRestriccionesDeBaseDeDatos:
    def test_check_de_coherencia_de_redencion(self, db_session, test_user):
        from sqlalchemy.exc import IntegrityError

        db_session.add(
            models.Cdt(
                user_id=test_user["id"],
                name="Incoherente",
                currency="COP",
                principal=D("10"),
                rate_ea=D("5"),
                opened_on=date(2026, 1, 1),
                maturity_on=date(2026, 6, 1),
                status="redeemed",  # sin redeemed_on ni final_amount
            )
        )
        with pytest.raises(IntegrityError):
            db_session.flush()
        db_session.rollback()
