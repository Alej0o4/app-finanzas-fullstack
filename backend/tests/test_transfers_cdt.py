"""CDT vinculado a cuentas (Fase 39 T5): constitución, edición, redención con interés "Rendimientos",
borrado y patrimonio. Seam: API con `TestClient`.

`HOY` = 2026-03-15 10:00 hora de Bogotá, como `test_cdt.py`.
"""

from decimal import Decimal

import pytest
from freezegun import freeze_time

from app.models import models

D = Decimal
CDTS = "/api/v1/cdts/"
SUMMARY = "/api/v1/dashboard/summary"
AHORA = "2026-03-15T15:00:00Z"

pytestmark = pytest.mark.usefixtures("_congelar")


@pytest.fixture
def _congelar():
    with freeze_time(AHORA):
        yield


def _m(valor) -> Decimal:
    return Decimal(str(valor))


@pytest.fixture
def banco(make_account, auth_headers):
    return make_account(auth_headers, name="Bancolombia", type="debit", balance="10000000.00", highlighted=True)


@pytest.fixture
def saldo(client, auth_headers):
    def _saldo(cuenta_id: int) -> Decimal:
        return _m(client.get(f"/api/v1/accounts/{cuenta_id}", headers=auth_headers).json()["balance"])

    return _saldo


@pytest.fixture
def crear(client, auth_headers):
    def _factory(*, status: int = 200, **extra) -> dict:
        body = {
            "name": "CDT Bancolombia",
            "currency": "COP",
            "principal": "2000000.00",
            "rate_ea": "10",
            "opened_on": "2026-02-15",
            "maturity_on": "2026-08-15",
        }
        body.update(extra)
        resp = client.post(CDTS, json=body, headers=auth_headers)
        assert resp.status_code == status, resp.text
        return resp.json()

    return _factory


def _transferencias(db_session, cdt_id=None):
    consulta = db_session.query(models.Transfer)
    if cdt_id is not None:
        consulta = consulta.filter(models.Transfer.cdt_id == cdt_id)
    return consulta.order_by(models.Transfer.id).all()


class TestCrear:
    def test_con_cuenta_crea_la_constitucion_y_descuenta_el_capital(self, crear, banco, saldo, db_session):
        cdt = crear(source_account_id=banco["id"])
        assert cdt["source_account_id"] == banco["id"]
        assert cdt["source_transfer_id"] is not None
        assert cdt["redeem_account_id"] is None
        assert saldo(banco["id"]) == D("8000000.00")
        (t,) = _transferencias(db_session, cdt["id"])
        assert (t.from_account_id, t.to_account_id) == (banco["id"], None)
        assert t.amount_out == t.amount_in == D("2000000.00")
        assert t.date.date().isoformat() == "2026-02-15"  # 12:00 Bogotá de la apertura

    def test_sin_cuenta_queda_aislado_como_en_la_fase_38(self, crear, banco, saldo, db_session):
        cdt = crear()
        assert cdt["source_account_id"] is None and cdt["source_transfer_id"] is None
        assert saldo(banco["id"]) == D("10000000.00")
        assert _transferencias(db_session) == []

    def test_moneda_de_la_cuenta_distinta_es_422_y_no_crea_nada(self, crear, banco, saldo, client, auth_headers):
        crear(source_account_id=banco["id"], currency="USD", status=422)
        assert saldo(banco["id"]) == D("10000000.00")
        assert client.get(CDTS, headers=auth_headers).json()["items"] == []

    def test_cuenta_ajena_o_inexistente_es_404(self, crear, make_account, other_user):
        ajena = make_account(other_user["headers"], name="Ajena")
        crear(source_account_id=ajena["id"], status=404)
        crear(source_account_id=999999, status=404)

    def test_el_patrimonio_no_cuenta_dos_veces_el_capital(self, client, auth_headers, crear, banco):
        antes = {r["currency"]: _m(r["total"]) for r in client.get(SUMMARY, headers=auth_headers).json()["net_worth"]}
        cdt = crear(source_account_id=banco["id"], rate_ea="10")
        resumen = client.get(SUMMARY, headers=auth_headers).json()
        neto = {r["currency"]: _m(r["total"]) for r in resumen["net_worth"]}
        # Solo suma el interés causado (capital sale de la cuenta y entra al CDT).
        assert neto["COP"] - antes["COP"] == _m(cdt["accrued_interest"])
        # El disponible real sigue siendo cuentas - comprometido: baja con el capital.
        libre = {r["currency"]: _m(r["total"]) for r in resumen["free_to_spend"]}
        assert libre["COP"] == D("8000000.00")
        cuentas = {r["currency"]: _m(r["total"]) for r in resumen["accounts_total"]}
        assert cuentas["COP"] == D("8000000.00")


class TestEditar:
    def test_cambiar_capital_actualiza_transferencia_y_saldo(
        self, client, auth_headers, crear, banco, saldo, db_session
    ):
        cdt = crear(source_account_id=banco["id"])
        resp = client.put(f"{CDTS}{cdt['id']}", json={"principal": "3000000.00"}, headers=auth_headers)
        assert resp.status_code == 200, resp.text
        assert saldo(banco["id"]) == D("7000000.00")
        (t,) = _transferencias(db_session, cdt["id"])
        assert t.amount_out == t.amount_in == D("3000000.00")

    def test_cambiar_apertura_actualiza_la_fecha_de_la_transferencia(
        self, client, auth_headers, crear, banco, db_session
    ):
        cdt = crear(source_account_id=banco["id"])
        resp = client.put(f"{CDTS}{cdt['id']}", json={"opened_on": "2026-02-01"}, headers=auth_headers)
        assert resp.status_code == 200, resp.text
        (t,) = _transferencias(db_session, cdt["id"])
        assert t.date.date().isoformat() == "2026-02-01"

    def test_cambiar_cuenta_de_origen_mueve_el_capital(self, client, auth_headers, crear, banco, saldo, make_account):
        otra = make_account(auth_headers, name="Nu", balance="5000000.00")
        cdt = crear(source_account_id=banco["id"])
        resp = client.put(f"{CDTS}{cdt['id']}", json={"source_account_id": otra["id"]}, headers=auth_headers)
        assert resp.status_code == 200, resp.text
        assert resp.json()["source_account_id"] == otra["id"]
        assert saldo(banco["id"]) == D("10000000.00")
        assert saldo(otra["id"]) == D("3000000.00")

    def test_vincular_un_cdt_aislado_crea_la_constitucion(self, client, auth_headers, crear, banco, saldo):
        cdt = crear()
        resp = client.put(f"{CDTS}{cdt['id']}", json={"source_account_id": banco["id"]}, headers=auth_headers)
        assert resp.status_code == 200, resp.text
        assert resp.json()["source_transfer_id"] is not None
        assert saldo(banco["id"]) == D("8000000.00")

    def test_editar_solo_el_nombre_no_toca_saldos(self, client, auth_headers, crear, banco, saldo):
        cdt = crear(source_account_id=banco["id"])
        resp = client.put(f"{CDTS}{cdt['id']}", json={"name": "Otro"}, headers=auth_headers)
        assert resp.status_code == 200
        assert saldo(banco["id"]) == D("8000000.00")

    def test_cambiar_moneda_con_vinculo_es_422_sin_efectos(self, client, auth_headers, crear, banco, saldo):
        cdt = crear(source_account_id=banco["id"])
        resp = client.put(f"{CDTS}{cdt['id']}", json={"currency": "USD"}, headers=auth_headers)
        assert resp.status_code == 422
        assert saldo(banco["id"]) == D("8000000.00")
        assert client.get(CDTS, headers=auth_headers).json()["items"][0]["currency"] == "COP"

    def test_source_account_null_es_422(self, client, auth_headers, crear, banco):
        cdt = crear(source_account_id=banco["id"])
        assert (
            client.put(f"{CDTS}{cdt['id']}", json={"source_account_id": None}, headers=auth_headers).status_code == 422
        )


class TestRedimir:
    def test_con_cuenta_devuelve_el_capital_y_registra_el_interes_como_ingreso(
        self, client, auth_headers, crear, banco, saldo, db_session
    ):
        cdt = crear(source_account_id=banco["id"])
        resp = client.post(
            f"{CDTS}{cdt['id']}/redeem",
            json={"account_id": banco["id"], "final_amount": "2150000.00"},
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        r = resp.json()
        assert r["status"] == "redeemed" and r["redeem_account_id"] == banco["id"]
        assert r["redeem_transfer_id"] is not None and r["source_transfer_id"] is not None
        assert saldo(banco["id"]) == D("10150000.00")  # 10M - 2M + 2M + 150k de interés
        redencion = [t for t in _transferencias(db_session, cdt["id"]) if t.to_account_id is not None]
        assert len(redencion) == 1 and redencion[0].amount_in == D("2000000.00")
        (ingreso,) = db_session.query(models.Transaction).all()
        assert (ingreso.type, ingreso.amount, ingreso.account_id) == ("income", D("150000.00"), banco["id"])
        categoria = db_session.get(models.Category, ingreso.category_id)
        assert categoria.name == "Rendimientos" and categoria.user_id is None and categoria.type == "income"
        assert ingreso.date == redencion[0].date
        assert ingreso.currency == "COP"

    def test_el_interes_cuenta_como_ingreso_del_flujo_y_el_capital_no(self, client, auth_headers, crear, banco):
        cdt = crear(source_account_id=banco["id"])
        client.post(
            f"{CDTS}{cdt['id']}/redeem",
            json={"account_id": banco["id"], "final_amount": "2150000.00", "redeemed_on": "2026-03-14"},
            headers=auth_headers,
        )
        resumen = client.get(SUMMARY, headers=auth_headers).json()
        ingreso = {r["currency"]: _m(r["total"]) for r in resumen["monthly_income_by_currency"]}
        assert ingreso["COP"] == D("150000.00")
        assert _m(resumen["monthly_flow_balance"]) == D("150000.00")

    def test_sin_final_amount_usa_el_interes_calculado(self, client, auth_headers, crear, banco, saldo):
        cdt = crear(source_account_id=banco["id"])
        resp = client.post(f"{CDTS}{cdt['id']}/redeem", json={"account_id": banco["id"]}, headers=auth_headers)
        assert resp.status_code == 200, resp.text
        final = _m(resp.json()["final_amount"])
        assert final > D("2000000.00")
        assert saldo(banco["id"]) == D("8000000.00") + final

    def test_sin_interes_no_crea_ingreso(self, client, auth_headers, crear, banco, db_session):
        cdt = crear(source_account_id=banco["id"])
        client.post(
            f"{CDTS}{cdt['id']}/redeem",
            json={"account_id": banco["id"], "final_amount": "2000000.00"},
            headers=auth_headers,
        )
        assert db_session.query(models.Transaction).count() == 0

    def test_puede_redimirse_a_otra_cuenta_de_la_misma_moneda(
        self, client, auth_headers, crear, banco, saldo, make_account
    ):
        otra = make_account(auth_headers, name="Nu", balance="0.00")
        cdt = crear(source_account_id=banco["id"])
        resp = client.post(
            f"{CDTS}{cdt['id']}/redeem",
            json={"account_id": otra["id"], "final_amount": "2100000.00"},
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        assert saldo(otra["id"]) == D("2100000.00")
        assert saldo(banco["id"]) == D("8000000.00")

    def test_final_menor_que_el_capital_con_cuenta_es_422(self, client, auth_headers, crear, banco, saldo):
        cdt = crear(source_account_id=banco["id"])
        resp = client.post(
            f"{CDTS}{cdt['id']}/redeem",
            json={"account_id": banco["id"], "final_amount": "1900000.00"},
            headers=auth_headers,
        )
        assert resp.status_code == 422
        assert saldo(banco["id"]) == D("8000000.00")
        assert client.get(CDTS, headers=auth_headers).json()["items"][0]["status"] == "active"

    def test_moneda_de_la_cuenta_distinta_es_422(self, client, auth_headers, crear, make_account):
        usd = make_account(auth_headers, name="USD", currency="USD", balance="0.00")
        cdt = crear()
        resp = client.post(f"{CDTS}{cdt['id']}/redeem", json={"account_id": usd["id"]}, headers=auth_headers)
        assert resp.status_code == 422

    def test_cuenta_ajena_es_404(self, client, auth_headers, crear, make_account, other_user):
        ajena = make_account(other_user["headers"], name="Ajena")
        cdt = crear()
        assert (
            client.post(f"{CDTS}{cdt['id']}/redeem", json={"account_id": ajena["id"]}, headers=auth_headers).status_code
            == 404
        )

    def test_sin_cuenta_se_comporta_como_hoy(self, client, auth_headers, crear, banco, saldo, db_session):
        cdt = crear(source_account_id=banco["id"])
        resp = client.post(f"{CDTS}{cdt['id']}/redeem", json={"final_amount": "2100000.00"}, headers=auth_headers)
        assert resp.status_code == 200, resp.text
        assert resp.json()["redeem_transfer_id"] is None
        assert saldo(banco["id"]) == D("8000000.00")
        assert db_session.query(models.Transaction).count() == 0
        assert len(_transferencias(db_session, cdt["id"])) == 1  # solo la constitución

    def test_redimir_dos_veces_es_409_sin_duplicar_efectos(self, client, auth_headers, crear, banco, saldo):
        cdt = crear(source_account_id=banco["id"])
        body = {"account_id": banco["id"], "final_amount": "2100000.00"}
        assert client.post(f"{CDTS}{cdt['id']}/redeem", json=body, headers=auth_headers).status_code == 200
        assert client.post(f"{CDTS}{cdt['id']}/redeem", json=body, headers=auth_headers).status_code == 409
        assert saldo(banco["id"]) == D("10100000.00")

    def test_siembra_la_categoria_si_la_base_no_la_tiene(self, client, auth_headers, crear, banco, db_session):
        assert db_session.query(models.Category).filter(models.Category.name == "Rendimientos").count() == 0
        cdt = crear()
        client.post(
            f"{CDTS}{cdt['id']}/redeem",
            json={"account_id": banco["id"], "final_amount": "2100000.00"},
            headers=auth_headers,
        )
        assert db_session.query(models.Category).filter(models.Category.name == "Rendimientos").count() == 1


class TestBorrar:
    def test_borrar_vigente_vinculado_devuelve_el_dinero(self, client, auth_headers, crear, banco, saldo, db_session):
        cdt = crear(source_account_id=banco["id"])
        assert client.delete(f"{CDTS}{cdt['id']}", headers=auth_headers).status_code == 204
        assert saldo(banco["id"]) == D("10000000.00")
        assert _transferencias(db_session) == []
        # y la cuenta vuelve a poder borrarse
        assert client.delete(f"/api/v1/accounts/{banco['id']}", headers=auth_headers).status_code == 200

    def test_borrar_redimido_con_transferencias_es_409(self, client, auth_headers, crear, banco, saldo, db_session):
        cdt = crear(source_account_id=banco["id"])
        client.post(
            f"{CDTS}{cdt['id']}/redeem",
            json={"account_id": banco["id"], "final_amount": "2100000.00"},
            headers=auth_headers,
        )
        resp = client.delete(f"{CDTS}{cdt['id']}", headers=auth_headers)
        assert resp.status_code == 409, resp.text
        assert saldo(banco["id"]) == D("10100000.00")
        assert len(_transferencias(db_session, cdt["id"])) == 2

    def test_borrar_redimido_solo_con_constitucion_tambien_es_409(self, client, auth_headers, crear, banco):
        cdt = crear(source_account_id=banco["id"])
        client.post(f"{CDTS}{cdt['id']}/redeem", json={}, headers=auth_headers)
        assert client.delete(f"{CDTS}{cdt['id']}", headers=auth_headers).status_code == 409

    def test_borrar_redimido_sin_vinculo_funciona_como_antes(self, client, auth_headers, crear):
        cdt = crear()
        client.post(f"{CDTS}{cdt['id']}/redeem", json={}, headers=auth_headers)
        assert client.delete(f"{CDTS}{cdt['id']}", headers=auth_headers).status_code == 204

    def test_borrar_aislado_vigente_no_toca_saldos(self, client, auth_headers, crear, banco, saldo):
        cdt = crear()
        assert client.delete(f"{CDTS}{cdt['id']}", headers=auth_headers).status_code == 204
        assert saldo(banco["id"]) == D("10000000.00")


class TestTransferenciasDeCdtDesdeTransfers:
    def test_no_se_editan_ni_borran_desde_transfers(self, client, auth_headers, crear, banco):
        cdt = crear(source_account_id=banco["id"])
        tid = cdt["source_transfer_id"]
        body = {"from_account_id": banco["id"], "to_account_id": banco["id"] + 1000, "amount_out": "1"}
        assert client.put(f"/api/v1/transfers/{tid}", json=body, headers=auth_headers).status_code in (409, 422)
        assert client.delete(f"/api/v1/transfers/{tid}", headers=auth_headers).status_code == 409
        got = client.get(f"/api/v1/transfers/{tid}", headers=auth_headers).json()
        assert got["cdt_id"] == cdt["id"] and got["cdt_name"] == "CDT Bancolombia"
        assert got["to_account_id"] is None

    def test_aparecen_en_el_feed_de_movimientos(self, client, auth_headers, crear, banco):
        cdt = crear(source_account_id=banco["id"])
        items = client.get("/api/v1/movements/", headers=auth_headers).json()["items"]
        assert [(i["kind"], i["id"]) for i in items] == [("transfer", cdt["source_transfer_id"])]

    def test_reconciliacion_incluye_las_transferencias_de_cdt(self, client, auth_headers, crear, banco):
        cdt = crear(source_account_id=banco["id"])
        client.post(
            f"{CDTS}{cdt['id']}/redeem",
            json={"account_id": banco["id"], "final_amount": "2100000.00"},
            headers=auth_headers,
        )
        resp = client.post(f"/api/v1/accounts/{banco['id']}/reconcile", headers=auth_headers).json()
        assert _m(resp["discrepancy"]) == D("0.00")


class TestListado:
    def test_el_listado_expone_los_vinculos(self, client, auth_headers, crear, banco):
        a = crear(source_account_id=banco["id"], name="Vinculado")
        b = crear(name="Aislado")
        items = {i["id"]: i for i in client.get(CDTS, headers=auth_headers).json()["items"]}
        assert items[a["id"]]["source_account_id"] == banco["id"]
        assert items[b["id"]]["source_account_id"] is None
