"""Fase 40 (D9, D13, D16): `category_id` en budgets-progress y filtros `currency`/`type` en
`GET /transactions/`. Seam: `TestClient`. "Hoy" congelado: 2026-03-15 10:00 Bogotá."""

from decimal import Decimal

import pytest
from freezegun import freeze_time

D = Decimal
TX = "/api/v1/transactions/"
AHORA = "2026-03-15T15:00:00Z"

pytestmark = pytest.mark.usefixtures("_congelar")


@pytest.fixture
def _congelar():
    with freeze_time(AHORA):
        yield


@pytest.fixture
def escenario(client, auth_headers, make_account, make_category):
    """Categoría con gastos COP (marzo y febrero), gasto USD y un reembolso (income) COP."""
    cop = make_account(auth_headers, name="COP", currency="COP", balance="1000000.00")
    usd = make_account(auth_headers, name="USD", currency="USD", balance="1000.00")
    cat = make_category(auth_headers, name="Comida", type="expense")
    otra = make_category(auth_headers, name="Otra", type="expense")

    def tx(cuenta, monto, tipo="expense", fecha="2026-03-10", categoria=cat):
        r = client.post(
            TX,
            json={
                "amount": monto,
                "type": tipo,
                "account_id": cuenta["id"],
                "category_id": categoria["id"],
                "date": fecha,
            },
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text

    tx(cop, "100.00")
    tx(cop, "200.00", fecha="2026-03-11")
    tx(cop, "300.00", fecha="2026-03-12")
    tx(cop, "50.00", tipo="income", fecha="2026-03-13")  # reembolso
    tx(usd, "7.00")
    tx(cop, "999.00", fecha="2026-02-10")
    tx(cop, "11.00", categoria=otra)
    return {"cat": cat, "otra": otra}


def _listar(client, headers, **params):
    r = client.get(TX, params=params, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def _presupuesto(client, headers, categoria_id, limite, mes):
    r = client.post(
        "/api/v1/budgets/",
        json={"category_id": categoria_id, "amount_limit": limite, "currency": "COP", "month": mes, "year": 2026},
        headers=headers,
    )
    assert r.status_code == 200, r.text


class TestBudgetsProgressCategoryId:
    def test_mes_actual_incluye_category_id(self, client, auth_headers, escenario):
        cat = escenario["cat"]
        _presupuesto(client, auth_headers, cat["id"], "1000.00", 3)
        r = client.get("/api/v1/dashboard/budgets-progress", headers=auth_headers)
        assert r.status_code == 200, r.text
        [fila] = r.json()
        assert fila["category_id"] == cat["id"]
        assert D(fila["spent"]) == D("600.00")

    def test_mes_pasado_incluye_category_id(self, client, auth_headers, escenario):
        cat = escenario["cat"]
        _presupuesto(client, auth_headers, cat["id"], "5000.00", 2)
        r = client.get("/api/v1/dashboard/budgets-progress", params={"year": 2026, "month": 2}, headers=auth_headers)
        assert r.status_code == 200, r.text
        [fila] = r.json()
        assert fila["category_id"] == cat["id"]
        assert D(fila["spent"]) == D("999.00")


class TestFiltrosTransacciones:
    def test_sin_filtros_no_cambia(self, client, auth_headers, escenario):
        assert _listar(client, auth_headers)["total"] == 7

    def test_currency(self, client, auth_headers, escenario):
        data = _listar(client, auth_headers, currency="USD")
        assert data["total"] == 1
        assert {t["currency"] for t in data["items"]} == {"USD"}

    def test_currency_paginado_total_cuenta_solo_lo_filtrado(self, client, auth_headers, escenario):
        cat = escenario["cat"]["id"]
        p1 = _listar(client, auth_headers, currency="COP", category_id=cat, skip=0, limit=2)
        p2 = _listar(client, auth_headers, currency="COP", category_id=cat, skip=2, limit=2)
        assert p1["total"] == p2["total"] == 5  # 4 en marzo + 1 en febrero, sin la de USD
        assert len(p1["items"]) == 2 and len(p2["items"]) == 2
        assert p2["page"] == 2
        assert {t["currency"] for t in p1["items"] + p2["items"]} == {"COP"}

    def test_type(self, client, auth_headers, escenario):
        data = _listar(client, auth_headers, type="income")
        assert data["total"] == 1
        assert data["items"][0]["type"] == "income"

    def test_combinados_con_category_id(self, client, auth_headers, escenario):
        data = _listar(
            client, auth_headers, category_id=escenario["cat"]["id"], currency="COP", type="expense", limit=2
        )
        assert data["total"] == 4
        assert all(t["type"] == "expense" and t["currency"] == "COP" for t in data["items"])

    def test_valores_invalidos_son_422(self, client, auth_headers, escenario):
        assert client.get(TX, params={"type": "transfer"}, headers=auth_headers).status_code == 422
        assert client.get(TX, params={"currency": "cop"}, headers=auth_headers).status_code == 422
        assert client.get(TX, params={"currency": "COPX"}, headers=auth_headers).status_code == 422


class TestInvarianteDistribucionVsLista:
    def test_distribucion_igual_a_suma_de_lista_con_reembolso_fuera(self, client, auth_headers, escenario):
        cat = escenario["cat"]["id"]
        mes = {"start_date": "2026-03-01", "end_date": "2026-03-31"}
        dist = client.get(
            "/api/v1/dashboard/category-distribution",
            params={**mes, "type": "expense", "currency": "COP"},
            headers=auth_headers,
        ).json()
        total_dist = next(Decimal(d["total"]) for d in dist if d["category_id"] == cat)
        lista = _listar(client, auth_headers, category_id=cat, currency="COP", type="expense", limit=1000, **mes)
        assert total_dist == sum(Decimal(t["amount"]) for t in lista["items"]) == D("600.00")
        # el reembolso (income) no entra en ninguno de los dos
        assert all(t["type"] == "expense" for t in lista["items"])
        assert lista["total"] == 3
