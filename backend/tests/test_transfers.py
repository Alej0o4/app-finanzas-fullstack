"""API de transferencias (Fase 39 T2, T3, T4, T6, T7). Seam: `TestClient` sobre Postgres.

El "hoy" se fija con `freeze_time` (zona del usuario: America/Bogota, UTC-5): 2026-03-15 10:00 Bogotá.
"""

from decimal import Decimal

import pytest
from freezegun import freeze_time
from sqlalchemy import func

from app.core.user_deletion import delete_user_cascade
from app.models import models

D = Decimal
URL = "/api/v1/transfers/"
AHORA = "2026-03-15T15:00:00Z"

pytestmark = pytest.mark.usefixtures("_congelar")


@pytest.fixture
def _congelar():
    with freeze_time(AHORA):
        yield


def _m(valor) -> Decimal:
    return Decimal(str(valor))


@pytest.fixture
def cuentas(make_account, auth_headers):
    return {
        "banco": make_account(auth_headers, name="Banco", type="debit", balance="1000000.00", highlighted=True),
        "efectivo": make_account(auth_headers, name="Efectivo", type="cash", balance="50000.00", highlighted=True),
        "usd": make_account(auth_headers, name="Plenti", type="debit", currency="USD", balance="10.00"),
        "tarjeta": make_account(auth_headers, name="Tarjeta", type="credit", balance="0.00"),
    }


@pytest.fixture
def saldo(client, auth_headers):
    def _saldo(cuenta_id: int) -> Decimal:
        return _m(client.get(f"/api/v1/accounts/{cuenta_id}", headers=auth_headers).json()["balance"])

    return _saldo


@pytest.fixture
def transferir(client, auth_headers):
    def _factory(origen: dict, destino: dict, monto: str, *, status: int = 200, **extra):
        body = {"from_account_id": origen["id"], "to_account_id": destino["id"], "amount_out": monto}
        body.update(extra)
        resp = client.post(URL, json=body, headers=auth_headers)
        assert resp.status_code == status, resp.text
        return resp.json()

    return _factory


class TestCrear:
    def test_misma_moneda_mueve_ambos_saldos(self, cuentas, transferir, saldo):
        t = transferir(cuentas["banco"], cuentas["efectivo"], "200000.00", description="Retiro")
        assert t["currency_out"] == t["currency_in"] == "COP"
        assert _m(t["amount_in"]) == D("200000.00")
        assert t["exchange_rate"] is None
        assert t["warnings"] == []
        assert t["description"] == "Retiro"
        assert saldo(cuentas["banco"]["id"]) == D("800000.00")
        assert saldo(cuentas["efectivo"]["id"]) == D("250000.00")

    def test_cambio_de_moneda_con_amount_in_deriva_la_tasa(self, cuentas, transferir, saldo):
        t = transferir(cuentas["banco"], cuentas["usd"], "642000.00", amount_in="200.00", date="2026-03-10")
        assert t["currency_in"] == "USD"
        assert _m(t["exchange_rate"]) == D("3210")
        assert saldo(cuentas["banco"]["id"]) == D("358000.00")
        assert saldo(cuentas["usd"]["id"]) == D("210.00")

    def test_cambio_de_moneda_con_tasa_calcula_amount_in(self, cuentas, transferir, saldo):
        t = transferir(cuentas["banco"], cuentas["usd"], "642000.00", exchange_rate="3210")
        assert _m(t["amount_in"]) == D("200.00")
        assert _m(t["exchange_rate"]) == D("3210")
        assert saldo(cuentas["usd"]["id"]) == D("210.00")

    def test_usd_a_cop_con_tasa(self, cuentas, transferir, saldo):
        t = transferir(cuentas["usd"], cuentas["banco"], "5.00", exchange_rate="4000")
        assert _m(t["amount_in"]) == D("20000.00")
        assert saldo(cuentas["usd"]["id"]) == D("5.00")
        assert saldo(cuentas["banco"]["id"]) == D("1020000.00")

    @pytest.mark.parametrize(
        "extra",
        [
            {"amount_in": "100.00", "exchange_rate": "3210"},  # ambos
            {"amount_in": "1.00"},  # misma moneda con monto distinto -> ver test aparte
        ],
    )
    def test_validaciones_422(self, cuentas, transferir, extra):
        destino = cuentas["usd"] if "exchange_rate" in extra else cuentas["efectivo"]
        transferir(cuentas["banco"], destino, "100.00", status=422, **extra)

    def test_monedas_distintas_sin_amount_in_ni_tasa_es_422(self, cuentas, transferir):
        transferir(cuentas["banco"], cuentas["usd"], "100.00", status=422)

    def test_misma_moneda_rechaza_tasa(self, cuentas, transferir):
        transferir(cuentas["banco"], cuentas["efectivo"], "100.00", exchange_rate="1", status=422)

    def test_misma_cuenta_es_422(self, cuentas, transferir):
        transferir(cuentas["banco"], cuentas["banco"], "100.00", status=422)

    def test_monto_cero_y_campos_extra_son_422(self, cuentas, transferir):
        transferir(cuentas["banco"], cuentas["efectivo"], "0", status=422)
        transferir(cuentas["banco"], cuentas["efectivo"], "10", status=422, currency="USD")

    def test_cuenta_de_otro_usuario_es_404_y_no_toca_saldos(
        self, client, cuentas, other_user, make_account, transferir, saldo
    ):
        ajena = make_account(other_user["headers"], name="Ajena", balance="100.00")
        transferir(cuentas["banco"], ajena, "10.00", status=404)
        assert saldo(cuentas["banco"]["id"]) == D("1000000.00")

    def test_otro_usuario_no_ve_ni_edita_ni_borra(self, client, cuentas, other_user, transferir):
        t = transferir(cuentas["banco"], cuentas["efectivo"], "10.00")
        h = other_user["headers"]
        assert client.get(f"{URL}{t['id']}", headers=h).status_code == 404
        assert client.delete(f"{URL}{t['id']}", headers=h).status_code == 404
        body = {
            "from_account_id": cuentas["banco"]["id"],
            "to_account_id": cuentas["efectivo"]["id"],
            "amount_out": "1",
        }
        assert client.put(f"{URL}{t['id']}", json=body, headers=h).status_code == 404

    def test_cuentas_de_credito_sin_reglas_especiales(self, cuentas, transferir, saldo):
        # Pagar la tarjeta: el saldo de la tarjeta (negativo por el consumo) sube, el banco baja.
        transferir(cuentas["banco"], cuentas["tarjeta"], "30000.00")
        assert saldo(cuentas["tarjeta"]["id"]) == D("30000.00")
        assert saldo(cuentas["banco"]["id"]) == D("970000.00")
        # Y la inversa: una tarjeta como origen resta (queda en negativo).
        transferir(cuentas["tarjeta"], cuentas["efectivo"], "50000.00")
        assert saldo(cuentas["tarjeta"]["id"]) == D("-20000.00")

    def test_fecha_solo_dia_sigue_las_reglas_de_transacciones(self, cuentas, transferir):
        hoy = transferir(cuentas["banco"], cuentas["efectivo"], "1.00", date="2026-03-15")
        assert hoy["date"].startswith("2026-03-15T15:00:00")  # hoy conserva la hora real
        otro = transferir(cuentas["banco"], cuentas["efectivo"], "1.00", date="2026-03-10")
        assert otro["date"].startswith("2026-03-10T17:00:00")  # 12:00 Bogotá
        sin = transferir(cuentas["banco"], cuentas["efectivo"], "1.00")
        assert sin["date"].startswith("2026-03-15T15:00:00")


class TestEditarYBorrar:
    def test_editar_monto_reajusta_los_saldos(self, client, auth_headers, cuentas, transferir, saldo):
        t = transferir(cuentas["banco"], cuentas["efectivo"], "100000.00")
        body = {
            "from_account_id": cuentas["banco"]["id"],
            "to_account_id": cuentas["efectivo"]["id"],
            "amount_out": "30000.00",
        }
        resp = client.put(f"{URL}{t['id']}", json=body, headers=auth_headers)
        assert resp.status_code == 200, resp.text
        assert _m(resp.json()["amount_in"]) == D("30000.00")
        assert saldo(cuentas["banco"]["id"]) == D("970000.00")
        assert saldo(cuentas["efectivo"]["id"]) == D("80000.00")

    def test_editar_cuenta_destino_y_moneda(self, client, auth_headers, cuentas, transferir, saldo):
        t = transferir(cuentas["banco"], cuentas["efectivo"], "100000.00", description="Orig")
        body = {
            "from_account_id": cuentas["banco"]["id"],
            "to_account_id": cuentas["usd"]["id"],
            "amount_out": "100000.00",
            "exchange_rate": "4000",
        }
        resp = client.put(f"{URL}{t['id']}", json=body, headers=auth_headers)
        assert resp.status_code == 200, resp.text
        assert saldo(cuentas["efectivo"]["id"]) == D("50000.00")  # revertido
        assert saldo(cuentas["usd"]["id"]) == D("35.00")
        assert saldo(cuentas["banco"]["id"]) == D("900000.00")
        assert resp.json()["description"] == "Orig"  # ausente conserva

    def test_editar_con_origen_y_destino_intercambiados(self, client, auth_headers, cuentas, transferir, saldo):
        t = transferir(cuentas["banco"], cuentas["efectivo"], "100.00")
        body = {
            "from_account_id": cuentas["efectivo"]["id"],
            "to_account_id": cuentas["banco"]["id"],
            "amount_out": "100.00",
        }
        assert client.put(f"{URL}{t['id']}", json=body, headers=auth_headers).status_code == 200
        assert saldo(cuentas["banco"]["id"]) == D("1000100.00")
        assert saldo(cuentas["efectivo"]["id"]) == D("49900.00")

    def test_description_null_explicito_la_limpia(self, client, auth_headers, cuentas, transferir):
        t = transferir(cuentas["banco"], cuentas["efectivo"], "5.00", description="Hola")
        body = {
            "from_account_id": cuentas["banco"]["id"],
            "to_account_id": cuentas["efectivo"]["id"],
            "amount_out": "5.00",
            "description": None,
        }
        assert client.put(f"{URL}{t['id']}", json=body, headers=auth_headers).json()["description"] is None

    def test_borrar_revierte_ambos_saldos(self, client, auth_headers, cuentas, transferir, saldo):
        t = transferir(cuentas["banco"], cuentas["usd"], "642000.00", exchange_rate="3210")
        assert client.delete(f"{URL}{t['id']}", headers=auth_headers).status_code == 204
        assert saldo(cuentas["banco"]["id"]) == D("1000000.00")
        assert saldo(cuentas["usd"]["id"]) == D("10.00")
        assert client.get(f"{URL}{t['id']}", headers=auth_headers).status_code == 404
        assert client.delete(f"{URL}{t['id']}", headers=auth_headers).status_code == 404


class TestListar:
    def test_filtra_por_cuenta_origen_o_destino_y_rango(self, client, auth_headers, cuentas, transferir):
        transferir(cuentas["banco"], cuentas["efectivo"], "1.00", date="2026-03-01")
        transferir(cuentas["efectivo"], cuentas["banco"], "2.00", date="2026-03-05")
        transferir(cuentas["banco"], cuentas["usd"], "4000.00", exchange_rate="4000", date="2026-03-10")
        todas = client.get(URL, headers=auth_headers).json()
        assert todas["total"] == 3
        assert [_m(i["amount_out"]) for i in todas["items"]] == [D("4000.00"), D("2.00"), D("1.00")]
        por_efectivo = client.get(URL, params={"account_id": cuentas["efectivo"]["id"]}, headers=auth_headers).json()
        assert por_efectivo["total"] == 2
        rango = client.get(URL, params={"start_date": "2026-03-04", "end_date": "2026-03-06"}, headers=auth_headers)
        assert [_m(i["amount_out"]) for i in rango.json()["items"]] == [D("2.00")]

    def test_rango_invertido_es_400(self, client, auth_headers):
        resp = client.get(URL, params={"start_date": "2026-03-06", "end_date": "2026-03-04"}, headers=auth_headers)
        assert resp.status_code == 400


class TestReconciliacion:
    def test_balance_es_opening_mas_transacciones_mas_transferencias(
        self, client, auth_headers, cuentas, transferir, make_category, saldo
    ):
        banco = cuentas["banco"]
        cat = make_category(auth_headers, name="Mercado", type="expense")
        client.post(
            "/api/v1/transactions/",
            json={"amount": "1000.00", "type": "expense", "account_id": banco["id"], "category_id": cat["id"]},
            headers=auth_headers,
        )
        t1 = transferir(banco, cuentas["efectivo"], "100000.00")
        t2 = transferir(cuentas["efectivo"], banco, "30000.00")
        transferir(banco, cuentas["usd"], "400000.00", exchange_rate="4000")
        # editar y borrar también tienen que dejarlo consistente
        body = {"from_account_id": banco["id"], "to_account_id": cuentas["efectivo"]["id"], "amount_out": "70000.00"}
        client.put(f"{URL}{t1['id']}", json=body, headers=auth_headers)
        client.delete(f"{URL}{t2['id']}", headers=auth_headers)

        for c in (banco, cuentas["efectivo"], cuentas["usd"]):
            antes = saldo(c["id"])
            resp = client.post(f"/api/v1/accounts/{c['id']}/reconcile", headers=auth_headers)
            assert resp.status_code == 200, resp.text
            assert _m(resp.json()["discrepancy"]) == D("0.00"), c
            assert saldo(c["id"]) == antes


class TestInvarianteDeFlujo:
    """T3: las transferencias no son flujo. Ninguna cifra de flujo cambia al crearlas."""

    def _foto(self, client, headers, cuenta_id):
        rango = {"start_date": "2026-03-01", "end_date": "2026-03-31"}
        resumen = client.get("/api/v1/dashboard/summary", headers=headers).json()
        return {
            "ingreso": resumen["monthly_income_by_currency"],
            "gasto": resumen["monthly_expense_by_currency"],
            "flujo": resumen["monthly_flow_balance"],
            "primer_mes": resumen["first_transaction_month"],
            "dona": client.get("/api/v1/dashboard/category-distribution", params=rango, headers=headers).json(),
            "serie": client.get("/api/v1/dashboard/cashflow-series", params=rango, headers=headers).json(),
            "presupuestos": client.get("/api/v1/dashboard/budgets-progress", headers=headers).json(),
            "mes_cuenta": client.get(f"/api/v1/accounts/{cuenta_id}/monthly-summary", headers=headers).json(),
            "transacciones": client.get("/api/v1/transactions/", headers=headers).json(),
        }

    def test_kpis_dona_serie_presupuestos_y_transacciones_no_cambian(
        self, client, auth_headers, cuentas, transferir, make_category
    ):
        banco = cuentas["banco"]
        cat = make_category(auth_headers, name="Mercado", type="expense")
        client.post(
            "/api/v1/budgets/",
            json={"category_id": cat["id"], "amount_limit": "5000.00", "currency": "COP", "month": 3, "year": 2026},
            headers=auth_headers,
        )
        client.post(
            "/api/v1/transactions/",
            json={"amount": "4000.00", "type": "expense", "account_id": banco["id"], "category_id": cat["id"]},
            headers=auth_headers,
        )
        antes = self._foto(client, auth_headers, banco["id"])
        transferir(banco, cuentas["efectivo"], "300000.00")
        transferir(banco, cuentas["usd"], "642000.00", exchange_rate="3210")
        transferir(cuentas["tarjeta"], banco, "1000.00")
        assert self._foto(client, auth_headers, banco["id"]) == antes

    def test_no_dispara_notificaciones_de_presupuesto(self, client, auth_headers, cuentas, transferir, db_session):
        antes = db_session.query(models.Notification).count()
        transferir(cuentas["banco"], cuentas["efectivo"], "900000.00")
        assert db_session.query(models.Notification).count() == antes

    def test_resumen_semanal_no_lee_transferencias(self, db_session, test_user, cuentas, transferir):
        from app.core.weekly_summary import build_weekly_summary

        user = db_session.query(models.User).filter(models.User.id == test_user["id"]).one()
        from datetime import UTC, datetime

        ref = datetime(2026, 3, 22, 15, 0, tzinfo=UTC)
        antes = build_weekly_summary(db_session, user, ref)
        transferir(cuentas["banco"], cuentas["efectivo"], "300000.00", date="2026-03-10")
        assert build_weekly_summary(db_session, user, ref) == antes
        assert db_session.query(func.count(models.Transaction.id)).scalar() == 0


class TestSobresYAvisos:
    def _sobre(self, client, headers, cuenta, aporte: str):
        r = client.post(
            "/api/v1/funds/",
            json={"name": "Seguro", "kind": "goal", "account_id": cuenta["id"], "target_amount": "900000.00"},
            headers=headers,
        )
        assert r.status_code == 200, r.text
        f = r.json()
        r = client.post(f"/api/v1/funds/{f['id']}/contributions", json={"amount": aporte}, headers=headers)
        assert r.status_code == 200, r.text
        return f

    def test_transferir_bajo_lo_comprometido_se_permite_y_avisa(self, client, auth_headers, cuentas, transferir):
        banco = cuentas["banco"]
        self._sobre(client, auth_headers, banco, "600000.00")
        t = transferir(banco, cuentas["efectivo"], "700000.00")  # banco queda en 300.000 < 600.000
        assert len(t["warnings"]) == 1
        w = t["warnings"][0]
        assert w["code"] == "BELOW_COMMITTED"
        assert w["account_id"] == banco["id"]
        assert w["currency"] == "COP"
        assert _m(w["committed"]) == D("600000.00")
        assert _m(w["balance_after"]) == D("300000.00")
        resumen = client.get("/api/v1/dashboard/summary", headers=auth_headers).json()
        libre = {r["currency"]: _m(r["total"]) for r in resumen["free_to_spend"]}
        # Cuentas COP: banco 300.000 + efectivo 750.000 + tarjeta 0 = 1.050.000; menos 600.000 comprometidos.
        assert libre["COP"] == D("450000.00")

    def test_sin_aviso_si_queda_por_encima_o_no_hay_sobres(self, client, auth_headers, cuentas, transferir):
        banco = cuentas["banco"]
        assert transferir(banco, cuentas["efectivo"], "100.00")["warnings"] == []
        self._sobre(client, auth_headers, banco, "600000.00")
        assert transferir(banco, cuentas["efectivo"], "100000.00")["warnings"] == []

    def test_put_tambien_devuelve_warnings_del_origen(self, client, auth_headers, cuentas, transferir):
        banco = cuentas["banco"]
        self._sobre(client, auth_headers, banco, "600000.00")
        t = transferir(banco, cuentas["efectivo"], "100000.00")
        body = {"from_account_id": banco["id"], "to_account_id": cuentas["efectivo"]["id"], "amount_out": "800000.00"}
        resp = client.put(f"{URL}{t['id']}", json=body, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["warnings"][0]["code"] == "BELOW_COMMITTED"
        assert client.get(f"{URL}{t['id']}", headers=auth_headers).json()["warnings"] == []

    def test_el_destino_no_genera_aviso(self, client, auth_headers, cuentas, transferir):
        self._sobre(client, auth_headers, cuentas["efectivo"], "40000.00")
        assert transferir(cuentas["banco"], cuentas["efectivo"], "10000.00")["warnings"] == []


class TestCuentas:
    def test_borrar_cuenta_con_transferencias_es_409(self, client, auth_headers, cuentas, transferir):
        transferir(cuentas["banco"], cuentas["efectivo"], "100.00")
        for clave in ("banco", "efectivo"):
            resp = client.delete(f"/api/v1/accounts/{cuentas[clave]['id']}", headers=auth_headers)
            assert resp.status_code == 409, resp.text
        # la cuenta sin transferencias sí se borra
        assert client.delete(f"/api/v1/accounts/{cuentas['tarjeta']['id']}", headers=auth_headers).status_code == 200

    def test_cuenta_vuelve_a_poder_borrarse_al_borrar_la_transferencia(self, client, auth_headers, cuentas, transferir):
        t = transferir(cuentas["banco"], cuentas["efectivo"], "100.00")
        client.delete(f"{URL}{t['id']}", headers=auth_headers)
        assert client.delete(f"/api/v1/accounts/{cuentas['banco']['id']}", headers=auth_headers).status_code == 200

    def test_no_se_cambia_la_moneda_de_una_cuenta_con_transferencias(self, client, auth_headers, cuentas, transferir):
        transferir(cuentas["banco"], cuentas["efectivo"], "100.00")
        cuenta = cuentas["efectivo"]
        resp = client.put(
            f"/api/v1/accounts/{cuenta['id']}",
            json={"name": cuenta["name"], "type": cuenta["type"], "currency": "USD"},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_borrar_usuario_borra_sus_transferencias(self, db_session, test_user, cuentas, transferir):
        transferir(cuentas["banco"], cuentas["efectivo"], "100.00")
        assert db_session.query(models.Transfer).count() == 1
        user = db_session.query(models.User).filter(models.User.id == test_user["id"]).one()
        delete_user_cascade(db_session, user)
        db_session.commit()
        assert db_session.query(models.Transfer).count() == 0


class TestRestriccionesDeBaseDeDatos:
    def test_check_de_extremos(self, db_session, test_user, cuentas):
        from sqlalchemy.exc import IntegrityError

        base = {
            "user_id": test_user["id"],
            "amount_out": D("1"),
            "amount_in": D("1"),
            "currency_out": "COP",
            "currency_in": "COP",
            "date": "2026-03-15T15:00:00Z",
        }
        for extra in (
            {"from_account_id": cuentas["banco"]["id"], "to_account_id": cuentas["banco"]["id"]},  # misma cuenta
            {"from_account_id": cuentas["banco"]["id"]},  # sin destino ni CDT
            {"from_account_id": None, "to_account_id": None},
        ):
            db_session.add(models.Transfer(**base, **extra))
            with pytest.raises(IntegrityError):
                db_session.flush()
            db_session.rollback()
