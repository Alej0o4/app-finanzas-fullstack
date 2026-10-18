"""Gasto contra sobre (Fase 36 T2-T8): `fund_id` en crear/editar/borrar/listar transacciones, el
desglose `planned_expense` del dashboard, la exclusión del promedio de emergencia y borrar un
sobre con gastos enlazados. Seam: API con `TestClient`, como `test_funds.py`."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
import sqlalchemy as sa

from app.core.timezones import get_zoneinfo
from app.models import models
from app.services import funds as funds_service

D = Decimal
FUNDS = "/api/v1/funds/"
TX = "/api/v1/transactions/"


def _m(valor) -> Decimal:
    return Decimal(str(valor))


@pytest.fixture
def categoria(make_category, auth_headers):
    return make_category(auth_headers, name="Seguros", type="expense")


@pytest.fixture
def cuenta(make_account, auth_headers):
    # Destacada: el resumen del dashboard solo suma las cuentas destacadas (si hay alguna).
    return make_account(auth_headers, balance="5000.00", highlighted=True)


@pytest.fixture
def sobre(client, auth_headers, cuenta):
    """Sobre de 1.000 con 600 apartados en `cuenta`."""

    def _factory(saldo: str = "600.00", account_id: int | None = None, **extra) -> dict:
        body = {
            "name": "Seguro",
            "kind": "goal",
            "account_id": account_id or cuenta["id"],
            "target_amount": "1000.00",
        }
        body.update(extra)
        resp = client.post(FUNDS, json=body, headers=auth_headers)
        assert resp.status_code == 200, resp.text
        fondo = resp.json()
        if D(saldo) > 0:
            r = client.post(f"{FUNDS}{fondo['id']}/contributions", json={"amount": saldo}, headers=auth_headers)
            assert r.status_code == 200, r.text
        return fondo

    return _factory


def _gasto(client, headers, cuenta_id, categoria_id, amount, **extra):
    body = {"amount": amount, "type": "expense", "account_id": cuenta_id, "category_id": categoria_id}
    body.update(extra)
    return client.post(TX, json=body, headers=headers)


def _fondo(client, headers, fund_id) -> dict:
    resp = client.get(f"{FUNDS}{fund_id}", headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _saldo_cuenta(client, headers, account_id) -> Decimal:
    return _m(client.get(f"/api/v1/accounts/{account_id}", headers=headers).json()["balance"])


def _resumen(client, headers) -> dict:
    resp = client.get("/api/v1/dashboard/summary", headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _total(lista: list[dict], moneda="COP") -> Decimal:
    return next((_m(i["total"]) for i in lista if i["currency"] == moneda), D("0"))


class TestCrear:
    def test_gasto_menor_al_saldo_sale_completo_del_sobre(self, client, auth_headers, cuenta, categoria, sobre):
        fondo = sobre("600.00")
        resp = _gasto(client, auth_headers, cuenta["id"], categoria["id"], "250.00", fund_id=fondo["id"])
        assert resp.status_code == 200, resp.text
        cuerpo = resp.json()
        assert cuerpo["fund_id"] == fondo["id"]
        assert _m(cuerpo["fund_applied_amount"]) == D("250.00")
        assert _m(_fondo(client, auth_headers, fondo["id"])["balance"]) == D("350.00")
        assert _saldo_cuenta(client, auth_headers, cuenta["id"]) == D("4750.00")  # el gasto es real

    def test_gasto_mayor_al_saldo_se_topa_y_el_resto_es_gasto_normal(
        self, client, auth_headers, cuenta, categoria, sobre
    ):
        fondo = sobre("600.00")
        resp = _gasto(client, auth_headers, cuenta["id"], categoria["id"], "900.00", fund_id=fondo["id"])
        assert resp.status_code == 200, resp.text
        assert _m(resp.json()["fund_applied_amount"]) == D("600.00")
        assert _m(_fondo(client, auth_headers, fondo["id"])["balance"]) == D("0")
        assert _saldo_cuenta(client, auth_headers, cuenta["id"]) == D("4100.00")
        resumen = _resumen(client, auth_headers)
        assert _total(resumen["committed"]) == D("0")
        assert _total(resumen["free_to_spend"]) == D("4100.00")

    def test_sobre_en_cero_no_enlaza(self, client, auth_headers, cuenta, categoria, sobre):
        fondo = sobre("0")
        resp = _gasto(client, auth_headers, cuenta["id"], categoria["id"], "100.00", fund_id=fondo["id"])
        assert resp.status_code == 200, resp.text
        cuerpo = resp.json()
        assert cuerpo["fund_id"] is None
        assert _m(cuerpo["fund_applied_amount"]) == D("0")
        assert _fondo(client, auth_headers, fondo["id"])["linked_expenses_count"] == 0

    def test_libro_registra_un_retiro_enlazado(self, client, auth_headers, cuenta, categoria, sobre, db_session):
        fondo = sobre("600.00")
        tx = _gasto(client, auth_headers, cuenta["id"], categoria["id"], "250.00", fund_id=fondo["id"]).json()
        entrada = db_session.query(models.FundEntry).filter(models.FundEntry.transaction_id == tx["id"]).one()
        assert entrada.type == "withdrawal"
        assert entrada.amount == D("-250.00")
        assert entrada.fund_id == fondo["id"]

    def test_cuenta_distinta_422(self, client, auth_headers, make_account, categoria, sobre):
        fondo = sobre("600.00")
        otra = make_account(auth_headers, name="Otra", balance="900.00")
        resp = _gasto(client, auth_headers, otra["id"], categoria["id"], "50.00", fund_id=fondo["id"])
        assert resp.status_code == 422
        assert _saldo_cuenta(client, auth_headers, otra["id"]) == D("900.00")  # nada se escribió

    def test_ingreso_con_fund_id_422(self, client, auth_headers, cuenta, make_category, sobre):
        fondo = sobre("600.00")
        sueldo = make_category(auth_headers, name="Sueldo", type="income")
        resp = client.post(
            TX,
            json={
                "amount": "50.00",
                "type": "income",
                "account_id": cuenta["id"],
                "category_id": sueldo["id"],
                "fund_id": fondo["id"],
            },
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_sobre_inexistente_o_ajeno_404(self, client, auth_headers, cuenta, categoria, sobre, other_user):
        fondo = sobre("600.00")
        assert _gasto(client, auth_headers, cuenta["id"], categoria["id"], "5.00", fund_id=99999).status_code == 404
        # el sobre es del dueño; el otro usuario no lo puede usar ni siquiera con su propia cuenta
        cuenta_otro = client.post(
            "/api/v1/accounts/",
            json={"name": "X", "type": "cash", "currency": "COP", "balance": "100.00"},
            headers=other_user["headers"],
        ).json()
        cat_otro = client.post(
            "/api/v1/categories/", json={"name": "Z", "type": "expense"}, headers=other_user["headers"]
        ).json()
        resp = _gasto(client, other_user["headers"], cuenta_otro["id"], cat_otro["id"], "5.00", fund_id=fondo["id"])
        assert resp.status_code == 404
        assert _saldo_cuenta(client, other_user["headers"], cuenta_otro["id"]) == D("100.00")

    def test_sobre_archivado_409(self, client, auth_headers, cuenta, categoria, sobre):
        fondo = sobre("0")
        assert client.post(f"{FUNDS}{fondo['id']}/archive", headers=auth_headers).status_code == 200
        resp = _gasto(client, auth_headers, cuenta["id"], categoria["id"], "5.00", fund_id=fondo["id"])
        assert resp.status_code == 409

    def test_idempotency_replay_devuelve_el_enlace_y_no_aplica_dos_veces(
        self, client, auth_headers, cuenta, categoria, sobre
    ):
        fondo = sobre("600.00")
        cabeceras = {**auth_headers, "Idempotency-Key": "k-fase36-1"}
        cuerpo = {
            "amount": "100.00",
            "type": "expense",
            "account_id": cuenta["id"],
            "category_id": categoria["id"],
            "fund_id": fondo["id"],
        }
        primera = client.post(TX, json=cuerpo, headers=cabeceras)
        segunda = client.post(TX, json=cuerpo, headers=cabeceras)
        assert primera.status_code == segunda.status_code == 200
        assert segunda.json()["id"] == primera.json()["id"]
        assert segunda.json()["fund_id"] == fondo["id"]
        assert _m(_fondo(client, auth_headers, fondo["id"])["balance"]) == D("500.00")

    def test_api_key_acepta_fund_id(self, client, auth_headers, cuenta, categoria, sobre):
        fondo = sobre("600.00")
        key = client.post("/api/v1/api-keys/", json={"name": "Atajo"}, headers=auth_headers).json()["key"]
        resp = _gasto(
            client,
            {"Authorization": f"Bearer {key}"},
            cuenta["id"],
            categoria["id"],
            "100.00",
            fund_id=fondo["id"],
        )
        assert resp.status_code == 200, resp.text
        assert _m(resp.json()["fund_applied_amount"]) == D("100.00")

    def test_sin_fund_id_no_hay_enlace(self, client, auth_headers, cuenta, categoria, sobre):
        fondo = sobre("600.00")
        cuerpo = _gasto(client, auth_headers, cuenta["id"], categoria["id"], "100.00").json()
        assert cuerpo["fund_id"] is None and cuerpo["fund_applied_amount"] is None
        assert _m(_fondo(client, auth_headers, fondo["id"])["balance"]) == D("600.00")


def _put(client, headers, tx, **cambios):
    cuerpo = {
        "amount": tx["amount"],
        "type": "expense",
        "account_id": tx["account_id"],
        "category_id": tx["category_id"],
    }
    cuerpo.update(cambios)
    return client.put(f"{TX}{tx['id']}", json=cuerpo, headers=headers)


class TestEditar:
    @pytest.fixture
    def enlazado(self, client, auth_headers, cuenta, categoria, sobre):
        fondo = sobre("600.00")
        tx = _gasto(client, auth_headers, cuenta["id"], categoria["id"], "250.00", fund_id=fondo["id"]).json()
        return fondo, tx

    def test_subir_el_monto_aplica_la_diferencia(self, client, auth_headers, enlazado):
        fondo, tx = enlazado
        resp = _put(client, auth_headers, tx, amount="300.00")
        assert resp.status_code == 200, resp.text
        assert _m(resp.json()["fund_applied_amount"]) == D("300.00")
        assert _m(_fondo(client, auth_headers, fondo["id"])["balance"]) == D("300.00")

    def test_subir_mas_que_el_saldo_se_topa(self, client, auth_headers, enlazado):
        fondo, tx = enlazado
        resp = _put(client, auth_headers, tx, amount="900.00")
        assert _m(resp.json()["fund_applied_amount"]) == D("600.00")
        assert _m(_fondo(client, auth_headers, fondo["id"])["balance"]) == D("0")

    def test_bajar_el_monto_devuelve_la_diferencia(self, client, auth_headers, enlazado):
        fondo, tx = enlazado
        resp = _put(client, auth_headers, tx, amount="100.00")
        assert _m(resp.json()["fund_applied_amount"]) == D("100.00")
        assert _m(_fondo(client, auth_headers, fondo["id"])["balance"]) == D("500.00")

    def test_fund_id_ausente_conserva_el_enlace(self, client, auth_headers, enlazado):
        fondo, tx = enlazado
        resp = _put(client, auth_headers, tx, description="solo cambio el texto")
        assert resp.json()["fund_id"] == fondo["id"]
        assert _m(_fondo(client, auth_headers, fondo["id"])["balance"]) == D("350.00")

    def test_fund_id_null_desvincula_y_devuelve(self, client, auth_headers, enlazado):
        fondo, tx = enlazado
        resp = _put(client, auth_headers, tx, fund_id=None)
        assert resp.status_code == 200, resp.text
        assert resp.json()["fund_id"] is None
        assert _m(_fondo(client, auth_headers, fondo["id"])["balance"]) == D("600.00")
        assert _fondo(client, auth_headers, fondo["id"])["linked_expenses_count"] == 0
        # y se puede volver a enlazar
        resp = _put(client, auth_headers, tx, fund_id=fondo["id"])
        assert _m(resp.json()["fund_applied_amount"]) == D("250.00")

    def test_cambiar_de_sobre_devuelve_al_viejo_y_aplica_al_nuevo(self, client, auth_headers, cuenta, enlazado, sobre):
        viejo, tx = enlazado
        nuevo = sobre("400.00", name="Computador")
        resp = _put(client, auth_headers, tx, fund_id=nuevo["id"])
        assert resp.status_code == 200, resp.text
        assert resp.json()["fund_id"] == nuevo["id"]
        assert _m(_fondo(client, auth_headers, viejo["id"])["balance"]) == D("600.00")
        assert _m(_fondo(client, auth_headers, nuevo["id"])["balance"]) == D("150.00")

    def test_enlazar_una_transaccion_existente(self, client, auth_headers, cuenta, categoria, sobre):
        fondo = sobre("600.00")
        tx = _gasto(client, auth_headers, cuenta["id"], categoria["id"], "200.00").json()
        resp = _put(client, auth_headers, tx, fund_id=fondo["id"])
        assert resp.status_code == 200, resp.text
        assert _m(resp.json()["fund_applied_amount"]) == D("200.00")
        assert _m(_fondo(client, auth_headers, fondo["id"])["balance"]) == D("400.00")

    def test_cambiar_de_cuenta_un_enlazado_409(self, client, auth_headers, make_account, enlazado):
        _, tx = enlazado
        otra = make_account(auth_headers, name="Otra", balance="900.00")
        assert _put(client, auth_headers, tx, account_id=otra["id"]).status_code == 409

    def test_pasar_a_ingreso_un_enlazado_409(self, client, auth_headers, make_category, enlazado):
        _, tx = enlazado
        sueldo = make_category(auth_headers, name="Sueldo", type="income")
        assert _put(client, auth_headers, tx, type="income", category_id=sueldo["id"]).status_code == 409

    def test_cambiar_de_cuenta_desvinculando_en_el_mismo_put(self, client, auth_headers, make_account, enlazado):
        fondo, tx = enlazado
        otra = make_account(auth_headers, name="Otra", balance="900.00")
        resp = _put(client, auth_headers, tx, account_id=otra["id"], fund_id=None)
        assert resp.status_code == 200, resp.text
        assert resp.json()["fund_id"] is None
        assert _m(_fondo(client, auth_headers, fondo["id"])["balance"]) == D("600.00")

    def test_sobre_archivado_no_recibe_ajustes_pero_el_monto_se_edita(
        self, client, auth_headers, cuenta, categoria, sobre
    ):
        fondo = sobre("100.00")
        tx = _gasto(client, auth_headers, cuenta["id"], categoria["id"], "100.00", fund_id=fondo["id"]).json()
        assert client.post(f"{FUNDS}{fondo['id']}/archive", headers=auth_headers).status_code == 200
        resp = _put(client, auth_headers, tx, amount="40.00")
        assert resp.status_code == 200, resp.text
        assert _m(_fondo(client, auth_headers, fondo["id"])["balance"]) == D("0")
        assert _saldo_cuenta(client, auth_headers, cuenta["id"]) == D("4960.00")
        # quitar el enlace de un archivado no se puede (D16)
        assert _put(client, auth_headers, tx, amount="40.00", fund_id=None).status_code == 409


class TestBorrar:
    def test_devuelve_lo_aplicado_al_sobre(self, client, auth_headers, cuenta, categoria, sobre, db_session):
        fondo = sobre("600.00")
        tx = _gasto(client, auth_headers, cuenta["id"], categoria["id"], "250.00", fund_id=fondo["id"]).json()
        assert client.delete(f"{TX}{tx['id']}", headers=auth_headers).status_code == 200
        assert _m(_fondo(client, auth_headers, fondo["id"])["balance"]) == D("600.00")
        assert _saldo_cuenta(client, auth_headers, cuenta["id"]) == D("5000.00")
        tipos = [
            e.type
            for e in db_session.query(models.FundEntry)
            .filter(models.FundEntry.transaction_id == tx["id"])
            .order_by(models.FundEntry.id)
        ]
        assert tipos == ["withdrawal", "adjustment"]  # append-only: no se borra la original

    def test_con_exceso_devuelve_solo_lo_aplicado(self, client, auth_headers, cuenta, categoria, sobre):
        fondo = sobre("600.00")
        tx = _gasto(client, auth_headers, cuenta["id"], categoria["id"], "900.00", fund_id=fondo["id"]).json()
        client.delete(f"{TX}{tx['id']}", headers=auth_headers)
        assert _m(_fondo(client, auth_headers, fondo["id"])["balance"]) == D("600.00")

    def test_sobre_ya_borrado_se_ignora(self, client, auth_headers, cuenta, categoria, sobre):
        fondo = sobre("600.00")
        tx = _gasto(client, auth_headers, cuenta["id"], categoria["id"], "250.00", fund_id=fondo["id"]).json()
        assert client.delete(f"{FUNDS}{fondo['id']}", headers=auth_headers).status_code == 204
        assert client.delete(f"{TX}{tx['id']}", headers=auth_headers).status_code == 200
        assert _saldo_cuenta(client, auth_headers, cuenta["id"]) == D("5000.00")

    def test_sobre_archivado_no_recibe_devolucion(self, client, auth_headers, cuenta, categoria, sobre):
        fondo = sobre("100.00")
        tx = _gasto(client, auth_headers, cuenta["id"], categoria["id"], "100.00", fund_id=fondo["id"]).json()
        client.post(f"{FUNDS}{fondo['id']}/archive", headers=auth_headers)
        assert client.delete(f"{TX}{tx['id']}", headers=auth_headers).status_code == 200
        assert _m(_fondo(client, auth_headers, fondo["id"])["balance"]) == D("0")
        assert _saldo_cuenta(client, auth_headers, cuenta["id"]) == D("5000.00")

    def test_borrar_una_transaccion_sin_enlace_no_toca_sobres(self, client, auth_headers, cuenta, categoria, sobre):
        fondo = sobre("600.00")
        tx = _gasto(client, auth_headers, cuenta["id"], categoria["id"], "50.00").json()
        client.delete(f"{TX}{tx['id']}", headers=auth_headers)
        assert _m(_fondo(client, auth_headers, fondo["id"])["balance"]) == D("600.00")


class TestListado:
    def test_campos_de_enlace_en_el_listado(self, client, auth_headers, cuenta, categoria, sobre):
        fondo = sobre("600.00")
        enlazada = _gasto(client, auth_headers, cuenta["id"], categoria["id"], "250.00", fund_id=fondo["id"]).json()
        libre = _gasto(client, auth_headers, cuenta["id"], categoria["id"], "10.00").json()
        items = {i["id"]: i for i in client.get(TX, headers=auth_headers).json()["items"]}
        assert items[enlazada["id"]]["fund_id"] == fondo["id"]
        assert _m(items[enlazada["id"]]["fund_applied_amount"]) == D("250.00")
        assert items[libre["id"]]["fund_id"] is None
        assert items[libre["id"]]["fund_applied_amount"] is None

    def test_el_listado_calcula_los_enlaces_en_una_sola_consulta(
        self, client, auth_headers, cuenta, categoria, sobre, db_session
    ):
        fondo = sobre("900.00")
        for _ in range(5):
            _gasto(client, auth_headers, cuenta["id"], categoria["id"], "10.00", fund_id=fondo["id"])
        consultas: list[str] = []

        def _contar(conn, cursor, statement, *a):
            if "fund_entries" in statement:
                consultas.append(statement)

        sa.event.listen(db_session.get_bind(), "before_cursor_execute", _contar)
        try:
            assert client.get(TX, headers=auth_headers).status_code == 200
        finally:
            sa.event.remove(db_session.get_bind(), "before_cursor_execute", _contar)
        assert len(consultas) == 1, consultas


class TestDashboard:
    def test_planeado_es_un_desglose_que_no_cambia_el_gasto(self, client, auth_headers, cuenta, categoria, sobre):
        fondo = sobre("600.00")
        _gasto(client, auth_headers, cuenta["id"], categoria["id"], "250.00", fund_id=fondo["id"])
        _gasto(client, auth_headers, cuenta["id"], categoria["id"], "40.00")
        resumen = _resumen(client, auth_headers)
        assert _total(resumen["monthly_expense_by_currency"]) == D("290.00")  # real, enlazado o no (D1)
        assert _total(resumen["planned_expense"]) == D("250.00")
        assert _m(resumen["monthly_flow_balance"]) == D("-290.00")

    def test_planeado_es_el_monto_total_aunque_exceda_el_sobre(self, client, auth_headers, cuenta, categoria, sobre):
        fondo = sobre("600.00")
        _gasto(client, auth_headers, cuenta["id"], categoria["id"], "900.00", fund_id=fondo["id"])
        resumen = _resumen(client, auth_headers)
        assert _total(resumen["planned_expense"]) == D("900.00")  # D9: monto total de la transacción
        assert _total(resumen["monthly_expense_by_currency"]) == D("900.00")

    def test_planeado_desaparece_al_borrar_o_desvincular(self, client, auth_headers, cuenta, categoria, sobre):
        fondo = sobre("600.00")
        tx = _gasto(client, auth_headers, cuenta["id"], categoria["id"], "250.00", fund_id=fondo["id"]).json()
        _put(client, auth_headers, tx, fund_id=None)
        assert _total(_resumen(client, auth_headers)["planned_expense"]) == D("0")

    def test_cashflow_series_trae_planned_expense_sin_alterar_totales(
        self, client, auth_headers, cuenta, categoria, sobre
    ):
        fondo = sobre("600.00")
        _gasto(client, auth_headers, cuenta["id"], categoria["id"], "250.00", fund_id=fondo["id"])
        _gasto(client, auth_headers, cuenta["id"], categoria["id"], "40.00")
        # Ventana de tres días: el "hoy" local del usuario puede ser el día UTC anterior o siguiente.
        ahora = datetime.now(UTC)
        resp = client.get(
            "/api/v1/dashboard/cashflow-series",
            params={
                "start_date": (ahora - timedelta(days=1)).strftime("%Y-%m-%d"),
                "end_date": (ahora + timedelta(days=1)).strftime("%Y-%m-%d"),
                "period": "day",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        cuerpo = resp.json()
        assert _m(cuerpo["total_expense"]) == D("290.00")
        assert _m(cuerpo["planned_expense"]) == D("250.00")
        assert _m(cuerpo["net"]) == D("-290.00")

    def test_planeado_sin_enlaces_es_cero(self, client, auth_headers, cuenta, categoria):
        _gasto(client, auth_headers, cuenta["id"], categoria["id"], "40.00")
        assert _resumen(client, auth_headers)["planned_expense"] == []

    def test_presupuestos_cuentan_el_gasto_enlazado(self, client, auth_headers, cuenta, categoria, sobre):
        """D8: el progreso de presupuesto incluye lo pagado con sobre, sin excepciones."""
        fondo = sobre("600.00")
        ahora = datetime.now(UTC)
        r = client.post(
            "/api/v1/budgets/",
            json={
                "amount_limit": "1000.00",
                "currency": "COP",
                "month": ahora.month,
                "year": ahora.year,
                "category_id": categoria["id"],
            },
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        _gasto(client, auth_headers, cuenta["id"], categoria["id"], "250.00", fund_id=fondo["id"])
        progreso = client.get("/api/v1/dashboard/budgets-progress", headers=auth_headers).json()
        assert _m(progreso[0]["spent"]) == D("250.00")


class TestEmergencia:
    def test_el_promedio_excluye_lo_pagado_con_sobre(
        self, client, auth_headers, db_session, test_user, cuenta, categoria, sobre
    ):
        """D11: jul-sep completos (N = 3). 300 de gasto normal + 900 pagados con sobre → el
        promedio es 300 / 3 = 100, no 1.200 / 3 = 400."""
        fondo = sobre("1000.00")
        casos = [("2026-07-10", "300.00", False), ("2026-09-06", "900.00", True)]
        for dia, monto, con_sobre in casos:
            extra = {"fund_id": fondo["id"]} if con_sobre else {}
            resp = _gasto(client, auth_headers, cuenta["id"], categoria["id"], monto, date=dia, **extra)
            assert resp.status_code == 200, resp.text
        usuario = db_session.get(models.User, test_user["id"])
        ahora = datetime(2026, 10, 17, 15, tzinfo=UTC)
        promedio = funds_service.promedio_gasto_mensual(
            db_session, usuario.id, "COP", ahora, get_zoneinfo(usuario.timezone)
        )
        assert promedio == D("100.00")


class TestBorrarSobreConGastos:
    def test_borrar_se_permite_y_las_transacciones_quedan_intactas(
        self, client, auth_headers, cuenta, categoria, sobre
    ):
        fondo = sobre("600.00")
        tx = _gasto(client, auth_headers, cuenta["id"], categoria["id"], "250.00", fund_id=fondo["id"]).json()
        detalle = _fondo(client, auth_headers, fondo["id"])
        assert detalle["linked_expenses_count"] == 1
        assert _m(detalle["linked_expenses_total"]) == D("250.00")
        assert detalle["linked_expenses"][0]["transaction_id"] == tx["id"]
        assert _m(detalle["linked_expenses"][0]["applied_amount"]) == D("250.00")
        saldo_antes = _saldo_cuenta(client, auth_headers, cuenta["id"])

        assert client.delete(f"{FUNDS}{fondo['id']}", headers=auth_headers).status_code == 204

        assert _saldo_cuenta(client, auth_headers, cuenta["id"]) == saldo_antes
        items = {i["id"]: i for i in client.get(TX, headers=auth_headers).json()["items"]}
        assert items[tx["id"]]["fund_id"] is None  # quedó como gasto normal, sin marca de planeado
        assert _m(_resumen(client, auth_headers)["monthly_expense_by_currency"][0]["total"]) == D("250.00")
        assert _resumen(client, auth_headers)["planned_expense"] == []

    def test_listado_de_sobres_trae_el_conteo(self, client, auth_headers, cuenta, categoria, sobre):
        fondo = sobre("600.00")
        _gasto(client, auth_headers, cuenta["id"], categoria["id"], "100.00", fund_id=fondo["id"])
        _gasto(client, auth_headers, cuenta["id"], categoria["id"], "50.00", fund_id=fondo["id"])
        lista = client.get(FUNDS, headers=auth_headers).json()
        assert lista[0]["linked_expenses_count"] == 2
        assert _m(lista[0]["linked_expenses_total"]) == D("150.00")

    def test_un_gasto_borrado_deja_de_contar_como_enlazado(self, client, auth_headers, cuenta, categoria, sobre):
        fondo = sobre("600.00")
        tx = _gasto(client, auth_headers, cuenta["id"], categoria["id"], "100.00", fund_id=fondo["id"]).json()
        client.delete(f"{TX}{tx['id']}", headers=auth_headers)
        assert _fondo(client, auth_headers, fondo["id"])["linked_expenses_count"] == 0


class TestCambiarCuentaDelSobre:
    """QA 2026-10-18: mover un sobre con gastos enlazados rompía "el gasto sale de la cuenta del sobre"."""

    def test_con_gastos_enlazados_409_y_no_cambia_nada(
        self, client, auth_headers, cuenta, categoria, sobre, make_account
    ):
        otra = make_account(auth_headers, name="Otra", balance="5000.00")
        fondo = sobre("600.00")
        assert (
            _gasto(client, auth_headers, cuenta["id"], categoria["id"], "100.00", fund_id=fondo["id"]).status_code
            == 200
        )
        resp = client.put(f"{FUNDS}{fondo['id']}", json={"account_id": otra["id"]}, headers=auth_headers)
        assert resp.status_code == 409, resp.text
        despues = _fondo(client, auth_headers, fondo["id"])
        assert despues["account_id"] == cuenta["id"]
        assert despues["linked_expenses_count"] == 1

    def test_tras_desvincular_o_borrar_el_gasto_si_se_puede_mover(
        self, client, auth_headers, cuenta, categoria, sobre, make_account
    ):
        otra = make_account(auth_headers, name="Otra", balance="5000.00")
        fondo = sobre("600.00")
        gasto = _gasto(client, auth_headers, cuenta["id"], categoria["id"], "100.00", fund_id=fondo["id"]).json()
        assert client.delete(f"{TX}{gasto['id']}", headers=auth_headers).status_code == 200
        resp = client.put(f"{FUNDS}{fondo['id']}", json={"account_id": otra["id"]}, headers=auth_headers)
        assert resp.status_code == 200, resp.text
        assert resp.json()["account_id"] == otra["id"]

    def test_sin_gastos_enlazados_sigue_permitido(self, client, auth_headers, sobre, make_account):
        otra = make_account(auth_headers, name="Otra", balance="5000.00")
        fondo = sobre("600.00")
        resp = client.put(f"{FUNDS}{fondo['id']}", json={"account_id": otra["id"]}, headers=auth_headers)
        assert resp.status_code == 200, resp.text
