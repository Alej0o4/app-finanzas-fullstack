"""Feed `GET /movements` (Fase 39 T11): UNION ALL de transacciones y transferencias, ordenado por
fecha y paginado en la base. Seam: `TestClient` sobre Postgres."""

from decimal import Decimal

import pytest
from freezegun import freeze_time

D = Decimal
URL = "/api/v1/movements/"
TX = "/api/v1/transactions/"
TR = "/api/v1/transfers/"

pytestmark = pytest.mark.usefixtures("_congelar")


@pytest.fixture
def _congelar():
    with freeze_time("2026-03-15T15:00:00Z"):
        yield


@pytest.fixture
def escenario(client, auth_headers, make_account, make_category):
    """4 transacciones y 3 transferencias intercaladas por fecha (una por día)."""
    a = make_account(auth_headers, name="A", balance="1000000.00")
    b = make_account(auth_headers, name="B", balance="1000000.00")
    c = make_account(auth_headers, name="C", balance="1000000.00")
    gasto = make_category(auth_headers, name="Mercado", type="expense")
    ingreso = make_category(auth_headers, name="Sueldo", type="income")

    def tx(dia, tipo, cat, monto, cuenta=a, desc=None):
        body = {"amount": monto, "type": tipo, "account_id": cuenta["id"], "category_id": cat["id"], "date": dia}
        if desc:
            body["description"] = desc
        r = client.post(TX, json=body, headers=auth_headers)
        assert r.status_code == 200, r.text
        return r.json()

    def tr(dia, origen, destino, monto):
        body = {"from_account_id": origen["id"], "to_account_id": destino["id"], "amount_out": monto, "date": dia}
        r = client.post(TR, json=body, headers=auth_headers)
        assert r.status_code == 200, r.text
        return r.json()

    return {
        "a": a,
        "b": b,
        "c": c,
        "gasto": gasto,
        "ingreso": ingreso,
        "tx1": tx("2026-03-01", "expense", gasto, "10.00", desc="Pan integral"),
        "tr1": tr("2026-03-02", a, b, "20.00"),
        "tx2": tx("2026-03-03", "income", ingreso, "30.00"),
        "tr2": tr("2026-03-04", b, c, "40.00"),
        "tx3": tx("2026-03-05", "expense", gasto, "50.00", cuenta=b),
        "tr3": tr("2026-03-06", c, a, "60.00"),
        "tx4": tx("2026-03-07", "expense", gasto, "70.00", cuenta=c, desc="Cena"),
    }


def _listar(client, headers, **params):
    resp = client.get(URL, params=params, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _claves(data):
    return [(i["kind"], i["id"]) for i in data["items"]]


class TestOrdenYForma:
    def test_mezcla_por_fecha_descendente_con_discriminador(self, client, auth_headers, escenario):
        data = _listar(client, auth_headers)
        e = escenario
        assert data["total"] == 7
        assert _claves(data) == [
            ("transaction", e["tx4"]["id"]),
            ("transfer", e["tr3"]["id"]),
            ("transaction", e["tx3"]["id"]),
            ("transfer", e["tr2"]["id"]),
            ("transaction", e["tx2"]["id"]),
            ("transfer", e["tr1"]["id"]),
            ("transaction", e["tx1"]["id"]),
        ]
        tx = data["items"][0]
        assert D(str(tx["amount"])) == D("70.00")
        assert tx["category_id"] == e["gasto"]["id"] and tx["fund_id"] is None
        tr = data["items"][1]
        assert tr["from_account_id"] == e["c"]["id"] and tr["to_account_id"] == e["a"]["id"]
        assert D(str(tr["amount_out"])) == D("60.00") and tr["currency_in"] == "COP"

    def test_transacciones_borradas_no_aparecen_ni_cuentan(self, client, auth_headers, escenario):
        assert client.delete(f"{TX}{escenario['tx2']['id']}", headers=auth_headers).status_code == 200
        data = _listar(client, auth_headers)
        assert data["total"] == 6
        assert ("transaction", escenario["tx2"]["id"]) not in _claves(data)

    def test_otro_usuario_no_ve_nada(self, client, other_user, escenario):
        data = _listar(client, other_user["headers"])
        assert data["total"] == 0 and data["items"] == []


class TestPaginacion:
    def test_paginas_sin_duplicados_ni_saltos_al_cruzar_tipos(self, client, auth_headers, escenario):
        completo = _claves(_listar(client, auth_headers))
        paginas = []
        for skip in range(0, 7, 3):
            data = _listar(client, auth_headers, skip=skip, limit=3)
            assert data["total"] == 7 and data["page_size"] == 3 and data["page"] == skip // 3 + 1
            paginas += _claves(data)
        assert paginas == completo
        assert len(set(paginas)) == 7

    def test_empate_de_fecha_e_id_entre_tablas_es_determinista(self, client, auth_headers, make_account, make_category):
        # Una transacción y una transferencia con la misma fecha: el orden no puede depender del plan.
        a = make_account(auth_headers, name="A", balance="100.00")
        b = make_account(auth_headers, name="B", balance="100.00")
        cat = make_category(auth_headers, name="Mercado", type="expense")
        for _ in range(3):
            client.post(
                TX,
                json={
                    "amount": "1.00",
                    "type": "expense",
                    "account_id": a["id"],
                    "category_id": cat["id"],
                    "date": "2026-03-10",
                },
                headers=auth_headers,
            )
            client.post(
                TR,
                json={"from_account_id": a["id"], "to_account_id": b["id"], "amount_out": "1.00", "date": "2026-03-10"},
                headers=auth_headers,
            )
        ref = _claves(_listar(client, auth_headers, limit=100))
        por_pagina = []
        for skip in range(6):
            por_pagina += _claves(_listar(client, auth_headers, skip=skip, limit=1))
        assert por_pagina == ref and len(set(ref)) == 6

    def test_limit_fuera_de_rango_es_422(self, client, auth_headers):
        assert client.get(URL, params={"limit": 0}, headers=auth_headers).status_code == 422
        assert client.get(URL, params={"limit": 1001}, headers=auth_headers).status_code == 422


class TestFiltros:
    def test_include_transfers_false(self, client, auth_headers, escenario):
        data = _listar(client, auth_headers, include_transfers="false")
        assert data["total"] == 4 and {i["kind"] for i in data["items"]} == {"transaction"}

    def test_account_id_incluye_transferencias_como_origen_o_destino(self, client, auth_headers, escenario):
        e = escenario
        data = _listar(client, auth_headers, account_id=e["a"]["id"])
        # A: tx1 (A), tr1 (origen), tr3 (destino). tx2 también es de A.
        assert set(_claves(data)) == {
            ("transaction", e["tx1"]["id"]),
            ("transaction", e["tx2"]["id"]),
            ("transfer", e["tr1"]["id"]),
            ("transfer", e["tr3"]["id"]),
        }
        assert data["total"] == 4

    @pytest.mark.parametrize(
        "params",
        [{"category_id": "gasto"}, {"type": "expense"}, {"type": "income"}, {"search": "pan"}],
    )
    def test_categoria_tipo_y_texto_excluyen_transferencias(self, client, auth_headers, escenario, params):
        params = {k: (escenario[v]["id"] if v in escenario else v) for k, v in params.items()}
        data = _listar(client, auth_headers, **params)
        assert data["items"] and {i["kind"] for i in data["items"]} == {"transaction"}
        assert data["total"] == len(data["items"])

    def test_texto_busca_en_la_descripcion_sin_distinguir_mayusculas(self, client, auth_headers, escenario):
        data = _listar(client, auth_headers, search="CENA")
        assert _claves(data) == [("transaction", escenario["tx4"]["id"])]

    def test_rango_de_fechas_en_zona_del_usuario(self, client, auth_headers, escenario):
        e = escenario
        data = _listar(client, auth_headers, start_date="2026-03-02", end_date="2026-03-04")
        assert _claves(data) == [
            ("transfer", e["tr2"]["id"]),
            ("transaction", e["tx2"]["id"]),
            ("transfer", e["tr1"]["id"]),
        ]

    def test_rango_invertido_es_400(self, client, auth_headers):
        assert _listar_status(client, auth_headers, start_date="2026-03-05", end_date="2026-03-01") == 400


def _listar_status(client, headers, **params) -> int:
    return client.get(URL, params=params, headers=headers).status_code


class TestKpisNoCambian:
    def test_get_transactions_sigue_sin_transferencias(self, client, auth_headers, escenario):
        data = client.get(TX, headers=auth_headers).json()
        assert data["total"] == 4
