"""API de recurrentes (Fase 37 T2-T8, T10).

El "hoy" se fija con `freeze_time` (zona del usuario: America/Bogota por defecto, UTC-5).
`HOY` = 2026-03-15 10:00 hora de Bogotá.
"""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from freezegun import freeze_time

from app.core.user_deletion import delete_user_cascade
from app.models import models

D = Decimal
URL = "/api/v1/recurring/"
AHORA = "2026-03-15T15:00:00Z"  # 10:00 en Bogotá
HOY = date(2026, 3, 15)

pytestmark = pytest.mark.usefixtures("_congelar")


@pytest.fixture
def _congelar():
    with freeze_time(AHORA):
        yield


def _money(valor) -> Decimal:
    return Decimal(str(valor))


@pytest.fixture
def cuenta(make_account, auth_headers):
    return make_account(auth_headers, balance="5000.00")


@pytest.fixture
def cat_gasto(make_category, auth_headers):
    return make_category(auth_headers, name="Vivienda", type="expense")


@pytest.fixture
def cat_ingreso(make_category, auth_headers):
    return make_category(auth_headers, name="Salario", type="income")


@pytest.fixture
def crear_regla(client, auth_headers, cuenta, cat_gasto):
    def _factory(headers: dict | None = None, **extra) -> dict:
        body = {
            "name": "Arriendo",
            "type": "expense",
            "amount": "1500.00",
            "account_id": cuenta["id"],
            "category_id": cat_gasto["id"],
            "frequency": "monthly",
            "start_date": "2026-03-01",
        }
        body.update(extra)
        resp = client.post(URL, json=body, headers=headers or auth_headers)
        assert resp.status_code == 200, resp.text
        return resp.json()

    return _factory


def _borrar_en_db(db_session, modelo, id_: int) -> None:
    """Soft-delete directo: la API ya no deja borrar una cuenta/categoría con reglas (409), pero la
    defensa `account_missing`/`category_missing` sigue cubriendo borrados por otras vías."""
    db_session.query(modelo).filter(modelo.id == id_).update({"deleted_at": datetime.now(UTC)})
    db_session.commit()


def _relogin(client, usuario: dict) -> dict:
    """Headers nuevos: el access token (15 min) del fixture caduca si se adelanta el reloj."""
    resp = client.post("/api/v1/auth/login", data={"username": usuario["email"], "password": usuario["password"]})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _saldo(client, headers, account_id) -> Decimal:
    resp = client.get(f"/api/v1/accounts/{account_id}", headers=headers)
    assert resp.status_code == 200, resp.text
    return _money(resp.json()["balance"])


def _confirmar(client, headers, rule_id, dia: str, **extra):
    return client.post(f"{URL}{rule_id}/confirm", json={"occurrence_date": dia, **extra}, headers=headers)


def _saltar(client, headers, rule_id, dia: str):
    return client.post(f"{URL}{rule_id}/skip", json={"occurrence_date": dia}, headers=headers)


class TestCrear:
    def test_crea_con_la_moneda_de_la_cuenta_y_el_ancla(self, crear_regla, make_account, auth_headers, cat_gasto):
        usd = make_account(auth_headers, name="Dólares", currency="USD", balance="100.00")
        regla = crear_regla(
            account_id=usd["id"], name="  Seguro  ", frequency="yearly", amount="1200.00", start_date="2026-03-20"
        )
        assert regla["currency"] == "USD"
        assert regla["name"] == "Seguro"
        assert regla["status"] == "active"
        assert regla["next_date"] == "2026-03-20" == regla["start_date"]
        assert _money(regla["monthly_equivalent"]) == D("100.00")
        assert regla["is_annual"] is True
        assert regla["is_due"] is False
        assert regla["account_missing"] is False and regla["category_missing"] is False

    def test_is_due_cuando_la_proxima_ya_vencio(self, crear_regla):
        assert crear_regla(start_date="2026-03-15")["is_due"] is True

    def test_cuenta_ajena_404(self, client, crear_regla, other_user, make_account, auth_headers, cat_gasto):
        ajena = make_account(other_user["headers"], name="Ajena")
        resp = client.post(
            URL,
            json={
                "name": "X",
                "type": "expense",
                "amount": "10.00",
                "account_id": ajena["id"],
                "category_id": cat_gasto["id"],
                "frequency": "monthly",
                "start_date": "2026-03-15",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_categoria_ajena_404(self, client, cuenta, other_user, make_category, auth_headers):
        ajena = make_category(other_user["headers"], name="Privada")
        resp = client.post(
            URL,
            json={
                "name": "X",
                "type": "expense",
                "amount": "10.00",
                "account_id": cuenta["id"],
                "category_id": ajena["id"],
                "frequency": "monthly",
                "start_date": "2026-03-15",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_categoria_de_tipo_distinto_se_acepta(self, crear_regla, cat_ingreso):
        # Reembolsos por categoría cruzada son intencionales (Fase 31).
        assert crear_regla(category_id=cat_ingreso["id"])["category_id"] == cat_ingreso["id"]

    @pytest.mark.parametrize("amount", ["0", "-5.00", "10.123", "100000000000000.00"])
    def test_monto_invalido_422(self, client, auth_headers, cuenta, cat_gasto, amount):
        resp = client.post(
            URL,
            json={
                "name": "X",
                "type": "expense",
                "amount": amount,
                "account_id": cuenta["id"],
                "category_id": cat_gasto["id"],
                "frequency": "monthly",
                "start_date": "2026-03-15",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 422

    @pytest.mark.parametrize(
        "extra", [{"frequency": "daily"}, {"type": "transfer"}, {"name": "   "}, {"start_date": "no-es-fecha"}]
    )
    def test_esquema_invalido_422(self, client, auth_headers, cuenta, cat_gasto, extra):
        body = {
            "name": "X",
            "type": "expense",
            "amount": "10.00",
            "account_id": cuenta["id"],
            "category_id": cat_gasto["id"],
            "frequency": "monthly",
            "start_date": "2026-03-15",
        }
        body.update(extra)
        assert client.post(URL, json=body, headers=auth_headers).status_code == 422

    def test_start_date_mas_de_un_anio_atras_422(self, client, auth_headers, cuenta, cat_gasto):
        body = {
            "name": "X",
            "type": "expense",
            "amount": "10.00",
            "account_id": cuenta["id"],
            "category_id": cat_gasto["id"],
            "frequency": "monthly",
        }
        assert client.post(URL, json={**body, "start_date": "2025-03-14"}, headers=auth_headers).status_code == 422
        assert client.post(URL, json={**body, "start_date": "2025-03-15"}, headers=auth_headers).status_code == 200

    def test_start_date_demasiado_futura_422(self, client, auth_headers, cuenta, cat_gasto):
        resp = client.post(
            URL,
            json={
                "name": "X",
                "type": "expense",
                "amount": "10.00",
                "account_id": cuenta["id"],
                "category_id": cat_gasto["id"],
                "frequency": "yearly",
                "start_date": "9999-12-31",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_tope_de_100_reglas(self, client, crear_regla, db_session, auth_headers, test_user, cuenta, cat_gasto):
        for i in range(100):
            db_session.add(
                models.RecurringRule(
                    user_id=test_user["id"],
                    account_id=cuenta["id"],
                    category_id=cat_gasto["id"],
                    name=f"R{i}",
                    type="expense",
                    amount=D("1.00"),
                    frequency="monthly",
                    start_date=HOY,
                    next_date=HOY,
                )
            )
        db_session.commit()
        resp = client.post(
            URL,
            json={
                "name": "Una más",
                "type": "expense",
                "amount": "1.00",
                "account_id": cuenta["id"],
                "category_id": cat_gasto["id"],
                "frequency": "monthly",
                "start_date": "2026-03-15",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 422


class TestEditarBorrarYAislamiento:
    def test_put_cambia_nombre_monto_y_no_el_calendario(self, client, crear_regla, auth_headers):
        regla = crear_regla()
        resp = client.put(f"{URL}{regla['id']}", json={"name": "Renta", "amount": "1600.00"}, headers=auth_headers)
        assert resp.status_code == 200, resp.text
        cuerpo = resp.json()
        assert cuerpo["name"] == "Renta" and _money(cuerpo["amount"]) == D("1600.00")
        assert cuerpo["start_date"] == regla["start_date"] and cuerpo["next_date"] == regla["next_date"]

    @pytest.mark.parametrize("campo", [{"frequency": "yearly"}, {"start_date": "2026-04-01"}, {"type": "income"}])
    def test_put_rechaza_campos_no_editables(self, client, crear_regla, auth_headers, campo):
        regla = crear_regla()
        assert client.put(f"{URL}{regla['id']}", json=campo, headers=auth_headers).status_code == 422

    def test_put_cambia_cuenta_y_categoria(self, client, crear_regla, make_account, make_category, auth_headers):
        regla = crear_regla()
        otra = make_account(auth_headers, name="Otra COP", currency="COP")
        cat = make_category(auth_headers, name="Otra")
        resp = client.put(
            f"{URL}{regla['id']}", json={"account_id": otra["id"], "category_id": cat["id"]}, headers=auth_headers
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["account_id"] == otra["id"] and resp.json()["category_id"] == cat["id"]

    def test_put_cuenta_de_otra_moneda_422_y_misma_moneda_ok(self, client, crear_regla, make_account, auth_headers):
        regla = crear_regla()  # cuenta COP
        usd = make_account(auth_headers, name="USD", currency="USD")
        otra_cop = make_account(auth_headers, name="Otra COP", currency="COP")
        resp = client.put(f"{URL}{regla['id']}", json={"account_id": usd["id"]}, headers=auth_headers)
        assert resp.status_code == 422
        assert "moneda" in resp.json()["detail"]
        assert client.get(URL, headers=auth_headers).json()[0]["account_id"] == regla["account_id"]
        resp = client.put(f"{URL}{regla['id']}", json={"account_id": otra_cop["id"]}, headers=auth_headers)
        assert resp.status_code == 200 and resp.json()["account_id"] == otra_cop["id"]

    def test_put_cuenta_ajena_404(self, client, crear_regla, make_account, other_user, auth_headers):
        regla = crear_regla()
        ajena = make_account(other_user["headers"], name="Ajena")
        resp = client.put(f"{URL}{regla['id']}", json={"account_id": ajena["id"]}, headers=auth_headers)
        assert resp.status_code == 404

    def test_borrar_y_luego_404(self, client, crear_regla, auth_headers):
        regla = crear_regla()
        assert client.delete(f"{URL}{regla['id']}", headers=auth_headers).status_code == 204
        assert client.delete(f"{URL}{regla['id']}", headers=auth_headers).status_code == 404
        assert client.get(URL, headers=auth_headers).json() == []

    def test_borrar_no_toca_transacciones_confirmadas(self, client, crear_regla, auth_headers, cuenta):
        regla = crear_regla()
        assert _confirmar(client, auth_headers, regla["id"], "2026-03-01").status_code == 200
        assert client.delete(f"{URL}{regla['id']}", headers=auth_headers).status_code == 204
        txs = client.get("/api/v1/transactions/", headers=auth_headers).json()["items"]
        assert len(txs) == 1
        assert _saldo(client, auth_headers, cuenta["id"]) == D("3500.00")

    def test_aislamiento_entre_usuarios(self, client, crear_regla, other_user, auth_headers):
        regla = crear_regla()
        otro = other_user["headers"]
        assert client.get(URL, headers=otro).json() == []
        assert client.put(f"{URL}{regla['id']}", json={"name": "Hack"}, headers=otro).status_code == 404
        assert client.delete(f"{URL}{regla['id']}", headers=otro).status_code == 404
        assert _confirmar(client, otro, regla["id"], "2026-03-01").status_code == 404
        assert _saltar(client, otro, regla["id"], "2026-03-01").status_code == 404
        assert client.get(f"{URL}pending", headers=otro).json() == []
        assert len(client.get(URL, headers=auth_headers).json()) == 1

    def test_sin_autenticacion_401(self, client):
        assert client.get(URL).status_code == 401

    def test_cuenta_borrada_se_marca_missing_y_confirm_404(self, client, crear_regla, auth_headers, cuenta, db_session):
        regla = crear_regla()
        _borrar_en_db(db_session, models.Account, cuenta["id"])
        listada = client.get(URL, headers=auth_headers).json()[0]
        assert listada["account_missing"] is True and listada["currency"] is None
        assert _confirmar(client, auth_headers, regla["id"], "2026-03-01").status_code == 404

    def test_categoria_borrada_se_marca_missing_y_confirm_404(
        self, client, crear_regla, auth_headers, make_category, db_session
    ):
        cat = make_category(auth_headers, name="Temporal")
        regla = crear_regla(category_id=cat["id"])
        _borrar_en_db(db_session, models.Category, cat["id"])
        assert client.get(URL, headers=auth_headers).json()[0]["category_missing"] is True
        assert _confirmar(client, auth_headers, regla["id"], "2026-03-01").status_code == 404

    def test_no_se_borra_cuenta_ni_categoria_con_reglas_409(self, client, crear_regla, auth_headers, cuenta, cat_gasto):
        regla = crear_regla()
        resp = client.delete(f"/api/v1/accounts/{cuenta['id']}", headers=auth_headers)
        assert resp.status_code == 409 and "recurrentes" in resp.json()["detail"]
        resp = client.delete(f"/api/v1/categories/{cat_gasto['id']}", headers=auth_headers)
        assert resp.status_code == 409 and "recurrentes" in resp.json()["detail"]
        # Una regla pausada también cuenta; al borrar la regla ya se puede.
        client.put(f"{URL}{regla['id']}", json={"status": "paused"}, headers=auth_headers)
        assert client.delete(f"/api/v1/accounts/{cuenta['id']}", headers=auth_headers).status_code == 409
        client.delete(f"{URL}{regla['id']}", headers=auth_headers)
        assert client.delete(f"/api/v1/accounts/{cuenta['id']}", headers=auth_headers).status_code == 200
        assert client.delete(f"/api/v1/categories/{cat_gasto['id']}", headers=auth_headers).status_code == 200

    def test_no_se_cambia_la_moneda_de_una_cuenta_con_reglas(self, client, crear_regla, auth_headers, cuenta):
        regla = crear_regla()
        resp = client.put(
            f"/api/v1/accounts/{cuenta['id']}",
            json={"name": cuenta["name"], "type": cuenta["type"], "currency": "USD"},
            headers=auth_headers,
        )
        assert resp.status_code == 400 and "recurrentes" in resp.json()["detail"]
        assert client.get(f"/api/v1/accounts/{cuenta['id']}", headers=auth_headers).json()["currency"] == "COP"
        # Una regla pausada también cuenta; reenviar la misma moneda nunca bloquea.
        client.put(f"{URL}{regla['id']}", json={"status": "paused"}, headers=auth_headers)
        mismo = {"name": cuenta["name"], "type": cuenta["type"], "currency": "COP"}
        assert client.put(f"/api/v1/accounts/{cuenta['id']}", json=mismo, headers=auth_headers).status_code == 200
        # Sin reglas ni transacciones el cambio vuelve a ser posible.
        client.delete(f"{URL}{regla['id']}", headers=auth_headers)
        usd = {**mismo, "currency": "USD"}
        assert client.put(f"/api/v1/accounts/{cuenta['id']}", json=usd, headers=auth_headers).status_code == 200

    def test_is_due_false_si_la_regla_esta_huerfana(self, client, crear_regla, auth_headers, cuenta, db_session):
        crear_regla(start_date="2026-03-01")
        assert client.get(URL, headers=auth_headers).json()[0]["is_due"] is True
        _borrar_en_db(db_session, models.Account, cuenta["id"])
        regla = client.get(URL, headers=auth_headers).json()[0]
        assert regla["account_missing"] is True and regla["is_due"] is False

    def test_borrar_usuario_borra_sus_reglas(self, client, crear_regla, db_session, test_user):
        crear_regla()
        user = db_session.query(models.User).filter(models.User.id == test_user["id"]).one()
        delete_user_cascade(db_session, user)
        db_session.commit()
        assert db_session.query(models.RecurringRule).count() == 0


class TestPendientes:
    def test_solo_vencidas_hoy_o_antes(self, client, crear_regla, auth_headers):
        crear_regla(name="Vence hoy", start_date="2026-03-15")
        crear_regla(name="Vencida", start_date="2026-03-01")
        crear_regla(name="Mañana", start_date="2026-03-16")
        pend = client.get(f"{URL}pending", headers=auth_headers).json()
        assert [p["name"] for p in pend] == ["Vencida", "Vence hoy"]
        assert all(p["is_next"] for p in pend)

    def test_acumula_atrasos_en_orden_y_solo_la_primera_es_resoluble(self, client, crear_regla, auth_headers):
        crear_regla(start_date="2026-01-01")  # ene, feb, mar
        pend = client.get(f"{URL}pending", headers=auth_headers).json()
        assert [p["occurrence_date"] for p in pend] == ["2026-01-01", "2026-02-01", "2026-03-01"]
        assert [p["is_next"] for p in pend] == [True, False, False]

    def test_tope_de_12_por_regla(self, client, crear_regla, auth_headers):
        crear_regla(frequency="weekly", start_date="2025-03-15")  # ~52 vencidas
        pend = client.get(f"{URL}pending", headers=auth_headers).json()
        assert len(pend) == 12
        assert pend[0]["occurrence_date"] == "2025-03-15"

    def test_usa_la_zona_del_usuario_no_utc(self, client, crear_regla, auth_headers):
        # 15:00Z del 15: en UTC y en Bogotá es el 15; en Kiritimati (UTC+14) ya es el 16 a las 05:00.
        crear_regla(start_date="2026-03-16")
        assert client.get(f"{URL}pending", headers=auth_headers).json() == []
        r = client.patch("/api/v1/users/me/preferences", json={"timezone": "Pacific/Kiritimati"}, headers=auth_headers)
        assert r.status_code == 200, r.text
        assert len(client.get(f"{URL}pending", headers=auth_headers).json()) == 1

    def test_pausadas_y_cuenta_borrada_excluidas(
        self, client, crear_regla, make_account, auth_headers, cat_gasto, db_session
    ):
        pausada = crear_regla(name="Pausada", start_date="2026-03-01")
        client.put(f"{URL}{pausada['id']}", json={"status": "paused"}, headers=auth_headers)
        sin_cuenta = make_account(auth_headers, name="Se va")
        crear_regla(name="Huérfana", start_date="2026-03-01", account_id=sin_cuenta["id"])
        crear_regla(name="Viva", start_date="2026-03-01")
        _borrar_en_db(db_session, models.Account, sin_cuenta["id"])
        assert [p["name"] for p in client.get(f"{URL}pending", headers=auth_headers).json()] == ["Viva"]


class TestConfirmar:
    def test_gasto_crea_transaccion_mueve_saldo_y_avanza(self, client, crear_regla, auth_headers, cuenta, cat_gasto):
        regla = crear_regla(start_date="2026-03-01")
        resp = _confirmar(client, auth_headers, regla["id"], "2026-03-01")
        assert resp.status_code == 200, resp.text
        tx = resp.json()
        assert tx["type"] == "expense" and _money(tx["amount"]) == D("1500.00")
        assert tx["description"] == "Arriendo" and tx["currency"] == "COP"
        assert tx["category_id"] == cat_gasto["id"] and tx["account_id"] == cuenta["id"]
        assert _saldo(client, auth_headers, cuenta["id"]) == D("3500.00")
        siguiente = client.get(URL, headers=auth_headers).json()[0]
        assert siguiente["next_date"] == "2026-04-01"

    def test_misma_variacion_de_saldo_que_post_transactions(
        self, client, crear_regla, auth_headers, make_account, cat_gasto
    ):
        a = make_account(auth_headers, name="A", balance="1000.00")
        b = make_account(auth_headers, name="B", balance="1000.00")
        regla = crear_regla(account_id=a["id"], amount="250.50", start_date="2026-03-01")
        _confirmar(client, auth_headers, regla["id"], "2026-03-01")
        client.post(
            "/api/v1/transactions/",
            json={"amount": "250.50", "type": "expense", "account_id": b["id"], "category_id": cat_gasto["id"]},
            headers=auth_headers,
        )
        assert _saldo(client, auth_headers, a["id"]) == _saldo(client, auth_headers, b["id"]) == D("749.50")

    def test_ingreso_suma_y_moneda_de_la_cuenta(self, client, crear_regla, auth_headers, make_account, cat_ingreso):
        usd = make_account(auth_headers, name="USD", currency="USD", balance="10.00")
        regla = crear_regla(
            name="Salario",
            type="income",
            amount="90.00",
            account_id=usd["id"],
            category_id=cat_ingreso["id"],
            start_date="2026-03-01",
        )
        tx = _confirmar(client, auth_headers, regla["id"], "2026-03-01").json()
        assert tx["type"] == "income" and tx["currency"] == "USD"
        assert _saldo(client, auth_headers, usd["id"]) == D("100.00")

    def test_monto_editado(self, client, crear_regla, auth_headers, cuenta):
        regla = crear_regla(start_date="2026-03-01")
        tx = _confirmar(client, auth_headers, regla["id"], "2026-03-01", amount="1234.56").json()
        assert _money(tx["amount"]) == D("1234.56")
        assert _saldo(client, auth_headers, cuenta["id"]) == D("3765.44")
        # La regla conserva su monto.
        assert _money(client.get(URL, headers=auth_headers).json()[0]["amount"]) == D("1500.00")

    @pytest.mark.parametrize("amount", ["0", "-1.00", "1.234"])
    def test_monto_editado_invalido_422(self, client, crear_regla, auth_headers, amount):
        regla = crear_regla(start_date="2026-03-01")
        assert _confirmar(client, auth_headers, regla["id"], "2026-03-01", amount=amount).status_code == 422

    def test_fecha_de_otro_dia_a_las_12_locales_y_hoy_con_hora_real(self, client, crear_regla, auth_headers):
        pasada = crear_regla(name="Pasada", start_date="2026-03-01")
        hoy = crear_regla(name="Hoy", start_date="2026-03-15")
        tx_pasada = _confirmar(client, auth_headers, pasada["id"], "2026-03-01").json()
        tx_hoy = _confirmar(client, auth_headers, hoy["id"], "2026-03-15").json()
        assert tx_pasada["date"].startswith("2026-03-01T17:00:00")  # 12:00 Bogotá
        assert tx_hoy["date"].startswith("2026-03-15T15:00:00")  # `ahora`

    def test_fecha_equivocada_409(self, client, crear_regla, auth_headers, cuenta):
        regla = crear_regla(start_date="2026-01-01")
        assert _confirmar(client, auth_headers, regla["id"], "2026-02-01").status_code == 409
        assert _confirmar(client, auth_headers, regla["id"], "2025-12-01").status_code == 409
        assert _saldo(client, auth_headers, cuenta["id"]) == D("5000.00")

    def test_futura_409(self, client, crear_regla, auth_headers, cuenta):
        regla = crear_regla(start_date="2026-03-16")
        assert _confirmar(client, auth_headers, regla["id"], "2026-03-16").status_code == 409
        assert _saldo(client, auth_headers, cuenta["id"]) == D("5000.00")

    def test_hay_que_resolver_en_orden(self, client, crear_regla, auth_headers):
        regla = crear_regla(start_date="2026-01-01")
        assert _confirmar(client, auth_headers, regla["id"], "2026-01-01").status_code == 200
        assert _confirmar(client, auth_headers, regla["id"], "2026-01-01").status_code == 409  # ya resuelta
        assert _confirmar(client, auth_headers, regla["id"], "2026-02-01").status_code == 200

    def test_pausada_409(self, client, crear_regla, auth_headers):
        regla = crear_regla(start_date="2026-03-01")
        client.put(f"{URL}{regla['id']}", json={"status": "paused"}, headers=auth_headers)
        assert _confirmar(client, auth_headers, regla["id"], "2026-03-01").status_code == 409

    def test_fecha_con_formato_invalido_422(self, client, crear_regla, auth_headers):
        regla = crear_regla(start_date="2026-03-01")
        assert _confirmar(client, auth_headers, regla["id"], "ayer").status_code == 422

    def test_dispara_alertas_de_presupuesto(self, client, crear_regla, auth_headers, cat_gasto):
        client.post(
            "/api/v1/budgets/",
            json={
                "amount_limit": "1000.00",
                "currency": "COP",
                "month": 3,
                "year": 2026,
                "category_id": cat_gasto["id"],
                "is_recurring": False,
            },
            headers=auth_headers,
        ).raise_for_status()
        antes = client.get("/api/v1/notifications/", headers=auth_headers).json()["items"]
        regla = crear_regla(amount="1500.00", start_date="2026-03-01")
        assert _confirmar(client, auth_headers, regla["id"], "2026-03-01").status_code == 200
        despues = client.get("/api/v1/notifications/", headers=auth_headers).json()["items"]
        assert len(despues) > len(antes)

    def test_confirmar_no_cambia_la_regla_de_otro_mes(self, client, crear_regla, auth_headers):
        # Día 31 sigue anclado: confirmar enero deja febrero 28 y luego marzo 31.
        regla = crear_regla(start_date="2026-01-31")
        _confirmar(client, auth_headers, regla["id"], "2026-01-31")
        assert client.get(URL, headers=auth_headers).json()[0]["next_date"] == "2026-02-28"
        _confirmar(client, auth_headers, regla["id"], "2026-02-28")
        assert client.get(URL, headers=auth_headers).json()[0]["next_date"] == "2026-03-31"


class TestSaltar:
    def test_avanza_sin_transaccion_ni_saldo(self, client, crear_regla, auth_headers, cuenta):
        regla = crear_regla(start_date="2026-03-01")
        resp = _saltar(client, auth_headers, regla["id"], "2026-03-01")
        assert resp.status_code == 200, resp.text
        assert resp.json()["next_date"] == "2026-04-01"
        assert client.get("/api/v1/transactions/", headers=auth_headers).json()["items"] == []
        assert _saldo(client, auth_headers, cuenta["id"]) == D("5000.00")

    def test_mismas_validaciones_de_fecha(self, client, crear_regla, auth_headers):
        regla = crear_regla(start_date="2026-01-01")
        assert _saltar(client, auth_headers, regla["id"], "2026-02-01").status_code == 409
        futura = crear_regla(name="Futura", start_date="2026-03-16")
        assert _saltar(client, auth_headers, futura["id"], "2026-03-16").status_code == 409

    def test_pausada_409(self, client, crear_regla, auth_headers):
        regla = crear_regla(start_date="2026-03-01")
        client.put(f"{URL}{regla['id']}", json={"status": "paused"}, headers=auth_headers)
        assert _saltar(client, auth_headers, regla["id"], "2026-03-01").status_code == 409


class TestPausarReanudar:
    def test_reanudar_salta_los_meses_de_la_pausa(self, client, crear_regla, auth_headers, test_user):
        regla = crear_regla(start_date="2026-03-01")  # next_date = 2026-03-01
        pausada = client.put(f"{URL}{regla['id']}", json={"status": "paused"}, headers=auth_headers).json()
        assert pausada["status"] == "paused" and pausada["next_date"] == "2026-03-01"  # pausar no toca next_date
        with freeze_time("2026-08-20T15:00:00Z"):
            auth_headers = _relogin(client, test_user)
            reanudada = client.put(f"{URL}{regla['id']}", json={"status": "active"}, headers=auth_headers).json()
            assert reanudada["status"] == "active"
            assert reanudada["next_date"] == "2026-09-01"
            assert client.get(f"{URL}pending", headers=auth_headers).json() == []

    def test_reanudar_el_mismo_dia_conserva_la_ocurrencia_de_hoy(self, client, crear_regla, auth_headers):
        regla = crear_regla(start_date="2026-03-15")
        client.put(f"{URL}{regla['id']}", json={"status": "paused"}, headers=auth_headers)
        reanudada = client.put(f"{URL}{regla['id']}", json={"status": "active"}, headers=auth_headers).json()
        assert reanudada["next_date"] == "2026-03-15"

    def test_pausada_fuera_de_pendientes_y_calendario_pero_en_la_lista(self, client, crear_regla, auth_headers):
        regla = crear_regla(start_date="2026-03-01")
        client.put(f"{URL}{regla['id']}", json={"status": "paused"}, headers=auth_headers)
        assert client.get(f"{URL}pending", headers=auth_headers).json() == []
        cal = client.get(f"{URL}calendar", headers=auth_headers).json()
        assert all(m["items"] == [] for m in cal["months"]) and cal["monthly_commitment"] == []
        assert len(client.get(URL, headers=auth_headers).json()) == 1


class TestCalendario:
    def test_doce_meses_exactos(self, client, auth_headers):
        meses = [m["month"] for m in client.get(f"{URL}calendar", headers=auth_headers).json()["months"]]
        assert meses == [f"2026-{m:02d}" for m in range(3, 13)] + ["2027-01", "2027-02"]

    def test_ocurrencias_totales_por_moneda_y_compromiso(
        self, client, crear_regla, auth_headers, make_account, cat_ingreso
    ):
        usd = make_account(auth_headers, name="USD", currency="USD", balance="0.00")
        crear_regla(name="Arriendo", amount="1500.00", start_date="2026-04-01")
        crear_regla(name="Seguro", frequency="yearly", amount="1200.00", start_date="2026-06-10")
        crear_regla(
            name="Salario", type="income", amount="3000.00", category_id=cat_ingreso["id"], start_date="2026-04-05"
        )
        crear_regla(name="Hosting", amount="20.00", account_id=usd["id"], start_date="2026-04-02")
        cal = client.get(f"{URL}calendar", headers=auth_headers).json()
        por_mes = {m["month"]: m for m in cal["months"]}
        assert por_mes["2026-03"]["items"] == []
        abril = por_mes["2026-04"]
        assert {i["name"] for i in abril["items"]} == {"Arriendo", "Salario", "Hosting"}
        totales = {t["currency"]: t for t in abril["totals"]}
        assert _money(totales["COP"]["expense"]) == D("1500.00")
        assert _money(totales["COP"]["income"]) == D("3000.00")
        assert _money(totales["COP"]["net"]) == D("1500.00")
        assert _money(totales["USD"]["net"]) == D("-20.00")
        junio = por_mes["2026-06"]
        seguro = next(i for i in junio["items"] if i["name"] == "Seguro")
        assert seguro["is_annual"] is True and seguro["is_overdue"] is False
        assert not any(i["name"] == "Seguro" for i in por_mes["2026-07"]["items"])
        # Arriendo mensual: 1500 x 10 meses (abr 2026 - ene 2027 ... feb 2027 = 11) dentro de la ventana.
        assert sum(1 for m in cal["months"] for i in m["items"] if i["name"] == "Arriendo") == 11
        compromiso = {c["currency"]: _money(c["amount"]) for c in cal["monthly_commitment"]}
        assert compromiso == {"COP": D("1600.00"), "USD": D("20.00")}  # 1500 + 1200/12; el ingreso no cuenta

    def test_vencidas_del_mes_actual_se_muestran_y_las_de_meses_anteriores_no(self, client, crear_regla, auth_headers):
        crear_regla(name="Vencida", start_date="2026-01-10")  # ene, feb: pendientes; mar 10 vencida
        cal = client.get(f"{URL}calendar", headers=auth_headers).json()
        marzo = cal["months"][0]
        assert [(i["date"], i["is_overdue"]) for i in marzo["items"]] == [("2026-03-10", True)]
        crear_regla(name="Hoy", start_date="2026-03-15")  # cae hoy: no es "vencida" en el calendario
        hoy = client.get(f"{URL}calendar", headers=auth_headers).json()["months"][0]["items"]
        assert [i["is_overdue"] for i in hoy if i["name"] == "Hoy"] == [False]
        assert cal["months"][1]["items"][0]["is_overdue"] is False

    def test_borde_de_mes_en_la_zona_del_usuario(self, client, crear_regla, auth_headers, test_user):
        # 2026-04-01T03:00Z sigue siendo el 31 de marzo en Bogotá: el primer mes es marzo.
        crear_regla(name="Fin de mes", start_date="2026-03-31")
        with freeze_time("2026-04-01T03:00:00Z"):
            auth_headers = _relogin(client, test_user)
            cal = client.get(f"{URL}calendar", headers=auth_headers).json()
        assert cal["months"][0]["month"] == "2026-03"
        assert cal["months"][0]["items"][0]["date"] == "2026-03-31"

    def test_cuenta_borrada_no_se_proyecta(self, client, crear_regla, make_account, auth_headers, db_session):
        sin_cuenta = make_account(auth_headers, name="Se va")
        crear_regla(account_id=sin_cuenta["id"], start_date="2026-04-01")
        _borrar_en_db(db_session, models.Account, sin_cuenta["id"])
        cal = client.get(f"{URL}calendar", headers=auth_headers).json()
        assert all(m["items"] == [] for m in cal["months"]) and cal["monthly_commitment"] == []


class TestSugerencias:
    def _gasto(self, client, headers, cuenta, categoria, dia: str, monto: str, descripcion: str | None):
        body = {
            "amount": monto,
            "type": "expense",
            "account_id": cuenta["id"],
            "category_id": categoria["id"],
            "date": dia,
        }
        if descripcion is not None:
            body["description"] = descripcion
        resp = client.post("/api/v1/transactions/", json=body, headers=headers)
        assert resp.status_code == 200, resp.text

    def test_detecta_el_par_a_un_anio(self, client, auth_headers, cuenta, cat_gasto):
        self._gasto(client, auth_headers, cuenta, cat_gasto, "2025-03-10", "1000.00", "Seguro del carro")
        self._gasto(client, auth_headers, cuenta, cat_gasto, "2026-03-08", "1100.00", "  seguro  DEL carro ")
        sug = client.get(f"{URL}suggestions", headers=auth_headers).json()
        assert len(sug) == 1
        s = sug[0]
        assert s["name"] == "seguro  DEL carro"  # descripción de la última, recortada
        assert _money(s["amount"]) == D("1100.00") and s["currency"] == "COP"
        assert s["last_date"] == "2026-03-08" and s["suggested_start_date"] == "2027-03-08"
        assert s["occurrences"] == 2
        assert s["account_id"] == cuenta["id"] and s["category_id"] == cat_gasto["id"]

    def test_cargo_duplicado_cercano_no_tapa_el_patron_anual(self, client, auth_headers, cuenta, cat_gasto):
        self._gasto(client, auth_headers, cuenta, cat_gasto, "2025-03-10", "1000.00", "Seguro")
        self._gasto(client, auth_headers, cuenta, cat_gasto, "2026-03-08", "1000.00", "Seguro")
        self._gasto(client, auth_headers, cuenta, cat_gasto, "2026-03-12", "50.00", "Seguro")  # duplicado/otro monto
        sug = client.get(f"{URL}suggestions", headers=auth_headers).json()
        assert len(sug) == 1
        assert sug[0]["last_date"] == "2026-03-08" and _money(sug[0]["amount"]) == D("1000.00")
        assert sug[0]["suggested_start_date"] == "2027-03-08"

    def test_ignora_sin_descripcion_y_otro_monto(self, client, auth_headers, cuenta, cat_gasto):
        self._gasto(client, auth_headers, cuenta, cat_gasto, "2025-03-10", "1000.00", None)
        self._gasto(client, auth_headers, cuenta, cat_gasto, "2026-03-08", "1000.00", None)
        self._gasto(client, auth_headers, cuenta, cat_gasto, "2025-03-10", "1000.00", "Tolerancia")
        self._gasto(client, auth_headers, cuenta, cat_gasto, "2026-03-08", "1300.00", "Tolerancia")  # +30 %
        assert client.get(f"{URL}suggestions", headers=auth_headers).json() == []

    def test_descarta_si_ya_hay_regla_aunque_este_pausada(self, client, crear_regla, auth_headers, cuenta, cat_gasto):
        self._gasto(client, auth_headers, cuenta, cat_gasto, "2025-03-10", "1000.00", "Seguro")
        self._gasto(client, auth_headers, cuenta, cat_gasto, "2026-03-08", "1000.00", "Seguro")
        regla = crear_regla(name="SEGURO", frequency="yearly", start_date="2027-03-08")
        assert client.get(f"{URL}suggestions", headers=auth_headers).json() == []
        client.put(f"{URL}{regla['id']}", json={"status": "paused"}, headers=auth_headers)
        assert client.get(f"{URL}suggestions", headers=auth_headers).json() == []

    def test_otra_cuenta_no_cuenta_como_ya_recurrente(
        self, client, crear_regla, make_account, auth_headers, cuenta, cat_gasto
    ):
        otra = make_account(auth_headers, name="Otra")
        crear_regla(name="Seguro", account_id=otra["id"], frequency="yearly", start_date="2027-03-08")
        self._gasto(client, auth_headers, cuenta, cat_gasto, "2025-03-10", "1000.00", "Seguro")
        self._gasto(client, auth_headers, cuenta, cat_gasto, "2026-03-08", "1000.00", "Seguro")
        assert len(client.get(f"{URL}suggestions", headers=auth_headers).json()) == 1

    def test_descarta_si_la_ultima_tiene_mas_de_13_meses(self, client, auth_headers, cuenta, cat_gasto):
        self._gasto(client, auth_headers, cuenta, cat_gasto, "2024-01-20", "1000.00", "Dejó de repetirse")
        self._gasto(client, auth_headers, cuenta, cat_gasto, "2025-01-15", "1000.00", "Dejó de repetirse")
        assert client.get(f"{URL}suggestions", headers=auth_headers).json() == []

    def test_ignora_ingresos_y_otro_usuario(self, client, auth_headers, other_user, make_account, make_category):
        ajena = make_account(other_user["headers"], name="Ajena")
        cat = make_category(other_user["headers"], name="Ajena cat")
        self._gasto(client, other_user["headers"], ajena, cat, "2025-03-10", "1000.00", "Seguro")
        self._gasto(client, other_user["headers"], ajena, cat, "2026-03-08", "1000.00", "Seguro")
        assert client.get(f"{URL}suggestions", headers=auth_headers).json() == []
        assert len(client.get(f"{URL}suggestions", headers=other_user["headers"]).json()) == 1


class TestContratoSinCambios:
    """T10: tener reglas no cambia ninguna cifra existente."""

    def test_dashboard_y_presupuestos_no_cambian(self, client, crear_regla, auth_headers, cuenta, cat_gasto):
        client.post(
            "/api/v1/transactions/",
            json={"amount": "100.00", "type": "expense", "account_id": cuenta["id"], "category_id": cat_gasto["id"]},
            headers=auth_headers,
        ).raise_for_status()
        rutas = [
            "/api/v1/dashboard/summary",
            "/api/v1/dashboard/budgets-progress",
            "/api/v1/dashboard/cashflow-series",
            "/api/v1/dashboard/category-distribution",
            "/api/v1/accounts/",
            "/api/v1/funds/",
        ]
        antes = {r: client.get(r, headers=auth_headers).json() for r in rutas}
        crear_regla(start_date="2026-03-01")
        crear_regla(name="Anual", frequency="yearly", start_date="2026-03-15", amount="999.00")
        client.get(f"{URL}pending", headers=auth_headers).raise_for_status()
        client.get(f"{URL}calendar", headers=auth_headers).raise_for_status()
        despues = {r: client.get(r, headers=auth_headers).json() for r in rutas}
        assert despues == antes
