"""Tests de cuentas (Fase 11 §11.5 + Fase 16 §16.4).

Fase 11: el endpoint GET /api/v1/accounts/summary. Fase 16: `opening_balance` en la
creación y el endpoint POST /api/v1/accounts/{id}/reconcile (Decisión 16.4.2). QA-025:
validación de la moneda y de la paginación del listado; QA-028: nombre en blanco.
"""

from calendar import monthrange
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
import sqlalchemy as sa

from app.models import models


class TestAccountsSummary:
    def test_sums_all_accounts_including_non_highlighted(self, client, auth_headers, make_account):
        """Decisión 11.5.1: /accounts/summary suma TODAS las cuentas — a diferencia de
        /dashboard/summary, que filtra por destacadas cuando existe al menos una."""
        make_account(auth_headers, name="Destacada", currency="COP", balance="1000.00", highlighted=True)
        make_account(auth_headers, name="No destacada", currency="COP", balance="500.00", highlighted=False)

        resumen_resp = client.get("/api/v1/accounts/summary", headers=auth_headers)
        assert resumen_resp.status_code == 200, resumen_resp.text
        resumen = resumen_resp.json()
        assert len(resumen) == 1  # una sola moneda → una sola fila
        assert resumen[0]["currency"] == "COP"
        # Incluye la cuenta no destacada (y la cuenta por defecto del registro, saldo 0)
        assert Decimal(str(resumen[0]["total"])) == Decimal("1500.00")

        contraste_resp = client.get("/api/v1/dashboard/summary", headers=auth_headers)
        assert contraste_resp.status_code == 200, contraste_resp.text
        balances_dashboard = {b["currency"]: Decimal(str(b["total"])) for b in contraste_resp.json()["balances"]}
        # El dashboard solo ve las destacadas: 0 (default) + 1000
        assert balances_dashboard["COP"] == Decimal("1000.00")

    def test_groups_balances_by_currency(self, client, auth_headers, make_account):
        make_account(auth_headers, name="Ahorros COP", currency="COP", balance="2000.00")
        make_account(auth_headers, name="Efectivo COP", currency="COP", balance="1000.00", highlighted=True)
        make_account(auth_headers, name="Ahorros USD", currency="USD", balance="500.00")

        resumen_resp = client.get("/api/v1/accounts/summary", headers=auth_headers)
        assert resumen_resp.status_code == 200, resumen_resp.text

        totales = {fila["currency"]: Decimal(str(fila["total"])) for fila in resumen_resp.json()}
        assert len(totales) == 2
        assert totales["COP"] == Decimal("3000.00")
        assert totales["USD"] == Decimal("500.00")

    def test_route_summary_does_not_collide_with_account_id(self, client, auth_headers):
        """⚠️ Ruta declarada antes de GET /{account_id}: si quedara después, FastAPI
        interpretaría "summary" como account_id y respondería 422 en vez de 200."""
        response = client.get("/api/v1/accounts/summary", headers=auth_headers)
        assert response.status_code == 200, response.text

        resumen = response.json()
        assert isinstance(resumen, list)
        for fila in resumen:
            assert set(fila.keys()) == {"currency", "total"}


class TestOpeningBalance:
    def test_opening_balance_set_equal_to_balance_on_creation(self, client, auth_headers, make_account):
        """Fase 16 §16.4 (Decisión 16.4.1): `AccountCreate.balance` alimenta AMBAS
        columnas al crear la cuenta; `opening_balance` queda inmutable tras eso."""
        cuenta = make_account(auth_headers, name="Ahorros", balance="2500.50")

        detalle = client.get(f"/api/v1/accounts/{cuenta['id']}", headers=auth_headers).json()
        assert Decimal(str(detalle["opening_balance"])) == Decimal("2500.50")
        assert Decimal(str(detalle["balance"])) == Decimal("2500.50")

    def test_default_account_creation_has_zero_opening_balance(self, client, register_and_login):
        user = register_and_login(email="opening-default@example.com")
        cuentas = client.get("/api/v1/accounts/", headers=user["headers"]).json()
        assert len(cuentas) == 1
        assert Decimal(str(cuentas[0]["opening_balance"])) == Decimal("0.00")


class TestReconcile:
    def _crear_transaccion(self, client, headers, **overrides) -> dict:
        payload = {"amount": "100.00", "type": "expense", "description": "tx reconcile"}
        payload.update(overrides)
        response = client.post("/api/v1/transactions/", json=payload, headers=headers)
        assert response.status_code == 200, response.text
        return response.json()

    def test_reconcile_without_deviation_returns_zero_discrepancy(
        self, client, auth_headers, make_account, make_category
    ):
        cuenta = make_account(auth_headers, balance="1000.00")
        categoria_ingreso = make_category(auth_headers, name="Salario", type="income")
        categoria_gasto = make_category(auth_headers, name="Comida", type="expense")

        self._crear_transaccion(
            client,
            auth_headers,
            amount="200.00",
            type="income",
            account_id=cuenta["id"],
            category_id=categoria_ingreso["id"],
        )
        self._crear_transaccion(
            client,
            auth_headers,
            amount="50.00",
            type="expense",
            account_id=cuenta["id"],
            category_id=categoria_gasto["id"],
        )
        # balance: 1000 + 200 - 50 = 1150 (mutado correctamente por las rutas contables)

        response = client.post(f"/api/v1/accounts/{cuenta['id']}/reconcile", headers=auth_headers)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["account_id"] == cuenta["id"]
        assert Decimal(str(body["previous_balance"])) == Decimal("1150.00")
        assert Decimal(str(body["recalculated_balance"])) == Decimal("1150.00")
        assert Decimal(str(body["discrepancy"])) == Decimal("0.00")
        assert Decimal(str(body["opening_balance"])) == Decimal("1000.00")

    def test_reconcile_corrects_forced_deviation_and_reports_discrepancy(
        self, client, auth_headers, db_session, make_account, make_category
    ):
        """Simula el bug que §16.4 previene: una intervención externa muta `balance` sin
        pasar por las tres rutas contables (hallazgo 2 del spec) — el reconcile debe
        detectar la desviación, corregir el saldo y reportar la discrepancia."""
        cuenta = make_account(auth_headers, balance="1000.00")
        categoria = make_category(auth_headers, name="Comida", type="expense")
        self._crear_transaccion(
            client,
            auth_headers,
            amount="100.00",
            type="expense",
            account_id=cuenta["id"],
            category_id=categoria["id"],
        )
        # balance real: 900. La cuenta "debería" decir 900.

        # Intervención foránea: balance pasa a 500 sin pasar por el código contable.
        account_db = db_session.query(models.Account).filter(models.Account.id == cuenta["id"]).first()
        account_db.balance = Decimal("500.00")
        db_session.commit()

        desviada = client.get(f"/api/v1/accounts/{cuenta['id']}", headers=auth_headers).json()
        assert Decimal(str(desviada["balance"])) == Decimal("500.00")

        response = client.post(f"/api/v1/accounts/{cuenta['id']}/reconcile", headers=auth_headers)
        assert response.status_code == 200, response.text
        body = response.json()
        assert Decimal(str(body["previous_balance"])) == Decimal("500.00")
        assert Decimal(str(body["discrepancy"])) == Decimal("400.00")
        assert Decimal(str(body["opening_balance"])) == Decimal("1000.00")

        # El saldo quedó corregido al valor matemáticamente correcto.
        corregida = client.get(f"/api/v1/accounts/{cuenta['id']}", headers=auth_headers).json()
        assert Decimal(str(corregida["balance"])) == Decimal("900.00")

    def test_reconcile_foreign_account_returns_404(self, client, auth_headers, other_user, make_account):
        cuenta_ajena = make_account(other_user["headers"], balance="1000.00")

        response = client.post(f"/api/v1/accounts/{cuenta_ajena['id']}/reconcile", headers=auth_headers)
        assert response.status_code == 404

    def test_reconcile_nonexistent_account_returns_404(self, client, auth_headers):
        response = client.post("/api/v1/accounts/999999/reconcile", headers=auth_headers)
        assert response.status_code == 404

    def test_reconcile_ignores_soft_deleted_transactions(self, client, auth_headers, make_account, make_category):
        """El recálculo suma solo transacciones no eliminadas — una transacción borrada
        (soft-delete) no debe inflar el neto (ya revirtió su impacto contable)."""
        cuenta = make_account(auth_headers, balance="1000.00")
        categoria = make_category(auth_headers, name="Comida", type="expense")

        creada = self._crear_transaccion(
            client,
            auth_headers,
            amount="100.00",
            type="expense",
            account_id=cuenta["id"],
            category_id=categoria["id"],
        )
        # balance: 900; se elimina la transacción → balance vuelve a 1000.
        delete = client.delete(f"/api/v1/transactions/{creada['id']}", headers=auth_headers)
        assert delete.status_code == 200, delete.text

        response = client.post(f"/api/v1/accounts/{cuenta['id']}/reconcile", headers=auth_headers)
        assert response.status_code == 200, response.text
        body = response.json()
        assert Decimal(str(body["discrepancy"])) == Decimal("0.00")
        assert Decimal(str(body["recalculated_balance"])) == Decimal("1000.00")


class TestMonthlySummary:
    """Fase 17 §17.1.4: GET /accounts/{id}/monthly-summary.

    Balance del mes de una sola cuenta, derivado íntegramente de transacciones reales
    de esa cuenta en el mes en curso — a diferencia de `/dashboard/summary`, no usa
    ningún valor declarado, así que `monthly_flow_balance` nunca es `null`.
    """

    def _crear_transaccion(self, client, headers, **overrides) -> dict:
        payload = {"amount": "100.00", "type": "expense", "description": "tx monthly summary"}
        payload.update(overrides)
        response = client.post("/api/v1/transactions/", json=payload, headers=headers)
        assert response.status_code == 200, response.text
        return response.json()

    def test_flow_balance_equals_income_minus_expense_in_account_currency(
        self, client, auth_headers, make_account, make_category
    ):
        cuenta = make_account(auth_headers, name="Ahorros USD", currency="USD", balance="1000.00")
        categoria_ingreso = make_category(auth_headers, name="Salario", type="income")
        categoria_gasto = make_category(auth_headers, name="Comida", type="expense")

        self._crear_transaccion(
            client,
            auth_headers,
            amount="500.00",
            type="income",
            account_id=cuenta["id"],
            category_id=categoria_ingreso["id"],
        )
        self._crear_transaccion(
            client,
            auth_headers,
            amount="120.00",
            type="expense",
            account_id=cuenta["id"],
            category_id=categoria_gasto["id"],
        )

        response = client.get(f"/api/v1/accounts/{cuenta['id']}/monthly-summary", headers=auth_headers)
        assert response.status_code == 200, response.text
        resumen = response.json()

        assert resumen["currency"] == "USD"
        assert Decimal(str(resumen["monthly_income"])) == Decimal("500.00")
        assert Decimal(str(resumen["monthly_expense"])) == Decimal("120.00")
        assert Decimal(str(resumen["monthly_flow_balance"])) == Decimal("380.00")
        assert Decimal(str(resumen["monthly_flow_balance"])) == Decimal(str(resumen["monthly_income"])) - Decimal(
            str(resumen["monthly_expense"])
        )

    def test_account_without_transactions_this_month_returns_zeros(self, client, auth_headers, make_account):
        cuenta = make_account(auth_headers, name="Sin movimientos", currency="COP", balance="1000.00")

        response = client.get(f"/api/v1/accounts/{cuenta['id']}/monthly-summary", headers=auth_headers)
        assert response.status_code == 200, response.text

        resumen = response.json()
        assert resumen["currency"] == "COP"
        for campo in ("monthly_income", "monthly_expense", "monthly_flow_balance"):
            assert Decimal(str(resumen[campo])) == Decimal("0.00")
        assert resumen["monthly_flow_balance"] is not None

    def test_foreign_account_returns_404(self, client, auth_headers, other_user, make_account):
        cuenta_ajena = make_account(other_user["headers"], balance="1000.00")

        response = client.get(f"/api/v1/accounts/{cuenta_ajena['id']}/monthly-summary", headers=auth_headers)
        assert response.status_code == 404

    def test_nonexistent_account_returns_404(self, client, auth_headers):
        response = client.get("/api/v1/accounts/999999/monthly-summary", headers=auth_headers)
        assert response.status_code == 404


class TestMonthlySummaryCurrentMonthCeiling:
    """T2 — Fase 30 B2: `monthly-summary` usa `limites_mes_utc` (techo = "ahora" en mes en curso).

    Mismo helper y mismo `skip` que `TestFutureDatedTransactionExcludedFromCurrentMonth
    ._fecha_futura_mismo_mes`: el último día del mes no hay "futuro dentro del mes".
    """

    def _crear_transaccion(self, client, headers, **overrides) -> dict:
        payload = {"amount": "100.00", "type": "expense", "description": "tx monthly summary"}
        payload.update(overrides)
        response = client.post("/api/v1/transactions/", json=payload, headers=headers)
        assert response.status_code == 200, response.text
        return response.json()

    @staticmethod
    def _fecha_futura_mismo_mes() -> str | None:
        hoy = datetime.now(UTC)
        ultimo_dia_mes = monthrange(hoy.year, hoy.month)[1]
        if hoy.day >= ultimo_dia_mes:
            return None  # hoy es el último día del mes: no hay "futuro" dentro del mismo mes
        manana = hoy + timedelta(days=1)
        return datetime(manana.year, manana.month, manana.day, tzinfo=UTC).isoformat()

    def test_excludes_future_dated_transaction_in_current_month(
        self, client, auth_headers, make_account, make_category
    ):
        """Una transacción con fecha futura DENTRO del mes en curso NO cuenta en
        monthly_income ni monthly_expense (techo = ahora)."""
        fecha_futura = self._fecha_futura_mismo_mes()
        if fecha_futura is None:
            pytest.skip("hoy es el último día del mes")

        cuenta = make_account(auth_headers, currency="COP", balance="1000000.00")
        categoria_gasto = make_category(auth_headers, name="Comida", type="expense")
        categoria_ingreso = make_category(auth_headers, name="Salario", type="income")

        # Transacción de HOY (debe contar)
        self._crear_transaccion(
            client,
            auth_headers,
            amount="10000.00",
            type="expense",
            account_id=cuenta["id"],
            category_id=categoria_gasto["id"],
        )
        # Transacción MAÑANA (futuro dentro del mes — NO debe contar)
        self._crear_transaccion(
            client,
            auth_headers,
            amount="50000.00",
            type="expense",
            account_id=cuenta["id"],
            category_id=categoria_gasto["id"],
            date=fecha_futura,
        )
        # Ingreso de HOY (debe contar)
        self._crear_transaccion(
            client,
            auth_headers,
            amount="20000.00",
            type="income",
            account_id=cuenta["id"],
            category_id=categoria_ingreso["id"],
        )
        # Ingreso MAÑANA (futuro — NO debe contar)
        self._crear_transaccion(
            client,
            auth_headers,
            amount="100000.00",
            type="income",
            account_id=cuenta["id"],
            category_id=categoria_ingreso["id"],
            date=fecha_futura,
        )

        response = client.get(f"/api/v1/accounts/{cuenta['id']}/monthly-summary", headers=auth_headers)
        assert response.status_code == 200, response.text
        resumen = response.json()

        # Solo la transacción de HOY debe contar
        assert Decimal(str(resumen["monthly_expense"])) == Decimal("10000.00")
        assert Decimal(str(resumen["monthly_income"])) == Decimal("20000.00")
        assert Decimal(str(resumen["monthly_flow_balance"])) == Decimal("10000.00")

    def test_today_transaction_still_counts(self, client, auth_headers, make_account, make_category):
        """Regresión: una transacción de HOY SÍ cuenta en la tarjeta de la cuenta."""
        cuenta = make_account(auth_headers, currency="COP", balance="1000000.00")
        categoria = make_category(auth_headers, name="Comida", type="expense")

        self._crear_transaccion(
            client, auth_headers, amount="7500.00", type="expense", account_id=cuenta["id"], category_id=categoria["id"]
        )

        response = client.get(f"/api/v1/accounts/{cuenta['id']}/monthly-summary", headers=auth_headers)
        assert response.status_code == 200, response.text
        resumen = response.json()

        assert Decimal(str(resumen["monthly_expense"])) == Decimal("7500.00")
        assert Decimal(str(resumen["monthly_flow_balance"])) == Decimal("-7500.00")


class TestUpdateAccount:
    def test_updates_name_and_type_without_touching_currency_or_highlighted(self, client, auth_headers, make_account):
        """Fase 24 §24.3 (Decisión C1): un PUT que omite currency/highlighted no los
        resetea a los defaults del schema — regresión directa del bug confirmado para
        `highlighted` (Hallazgo 4)."""
        cuenta = make_account(auth_headers, name="Original", type="cash", currency="USD", highlighted=True)

        response = client.put(
            f"/api/v1/accounts/{cuenta['id']}",
            json={"name": "Renombrada", "type": "debit"},
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        actualizada = response.json()
        assert actualizada["name"] == "Renombrada"
        assert actualizada["type"] == "debit"
        assert actualizada["currency"] == "USD"  # sin tocar
        assert actualizada["highlighted"] is True  # sin tocar (antes: se reseteaba a False)

    def test_applies_currency_change_when_account_has_no_transactions(self, client, auth_headers, make_account):
        """Fase 24 §24.3 (Decisión C2): el caso feliz — cuenta recién creada, sin
        historial, el cambio de moneda se aplica de verdad (antes: se ignoraba en
        silencio, 200 sin efecto)."""
        cuenta = make_account(auth_headers, currency="COP")

        response = client.put(
            f"/api/v1/accounts/{cuenta['id']}",
            json={"name": cuenta["name"], "type": cuenta["type"], "currency": "USD"},
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["currency"] == "USD"

    def test_blocks_currency_change_when_account_has_active_transaction(
        self, client, auth_headers, make_account, make_category
    ):
        """Fase 24 §24.3 (Decisión C2): el guard real — mismo status/estilo de mensaje
        que eliminar_cuenta (accounts.py:231-233), mismo criterio de 'operación que no
        tiene sentido con historial existente'."""
        cuenta = make_account(auth_headers, currency="COP")
        categoria = make_category(auth_headers, name="Comida", type="expense")
        tx = client.post(
            "/api/v1/transactions/",
            json={"amount": "50.00", "type": "expense", "account_id": cuenta["id"], "category_id": categoria["id"]},
            headers=auth_headers,
        )
        assert tx.status_code == 200, tx.text

        response = client.put(
            f"/api/v1/accounts/{cuenta['id']}",
            json={"name": cuenta["name"], "type": cuenta["type"], "currency": "USD"},
            headers=auth_headers,
        )
        assert response.status_code == 400
        assert "moneda" in response.json()["detail"].lower()

        # La cuenta conserva su moneda original — el bloqueo es real, no cosmético.
        sin_cambios = client.get(f"/api/v1/accounts/{cuenta['id']}", headers=auth_headers).json()
        assert sin_cambios["currency"] == "COP"

    def test_allows_update_with_same_currency_even_with_transactions(
        self, client, auth_headers, make_account, make_category
    ):
        """Fase 24 §24.3 (Decisión C2): el guard solo dispara si el valor cambia de
        verdad — renombrar/retipear una cuenta con transacciones sigue funcionando
        igual que hoy, incluso si el body reenvía la misma moneda."""
        cuenta = make_account(auth_headers, currency="COP")
        categoria = make_category(auth_headers, name="Comida", type="expense")
        client.post(
            "/api/v1/transactions/",
            json={"amount": "50.00", "type": "expense", "account_id": cuenta["id"], "category_id": categoria["id"]},
            headers=auth_headers,
        )

        response = client.put(
            f"/api/v1/accounts/{cuenta['id']}",
            json={"name": "Otro nombre", "type": cuenta["type"], "currency": "COP"},
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["name"] == "Otro nombre"
        assert response.json()["currency"] == "COP"


def test_foreign_account_returns_404(client, auth_headers, other_user, make_account):
    cuenta_ajena = make_account(other_user["headers"])

    response = client.put(
        f"/api/v1/accounts/{cuenta_ajena['id']}",
        json={"name": "x", "type": "cash"},
        headers=auth_headers,
    )
    assert response.status_code == 404


class TestCurrencyInvalida:
    """QA-025 (moneda): `Account.currency` es `String(3)` en el modelo, así que un valor más
    largo ("zzzzzz") llegaba hasta el INSERT y volvía como 500 (`StringDataRightTruncation` es
    un `DataError`, sin capturar). Ahora `^[A-Z]{3}$` vive en el schema de REQUEST."""

    @staticmethod
    def _payload(**overrides) -> dict:
        payload = {"name": "Cuenta de prueba", "type": "cash", "balance": "100.00"}
        payload.update(overrides)
        return payload

    def test_currency_invalida_devuelve_422(self, client, auth_headers, make_account):
        for currency in ("zzzzzz", "", "cop", "XX"):
            create = client.post("/api/v1/accounts/", json=self._payload(currency=currency), headers=auth_headers)
            assert create.status_code == 422, f"POST {currency!r} → {create.status_code} {create.text}"

        cuenta = make_account(auth_headers, name="Para editar")
        update = client.put(
            f"/api/v1/accounts/{cuenta['id']}",
            json={"name": cuenta["name"], "type": cuenta["type"], "currency": "zzzzzz"},
            headers=auth_headers,
        )
        assert update.status_code == 422, update.text

    def test_cuenta_con_moneda_rara_no_rompe_el_get(self, client, db_session, auth_headers, make_account):
        """El response NO revalida el patrón: una cuenta con `currency="ZZ"` (que `String(3)`
        acepta sin problema) tiene que poder listarse y leerse, no devolver 500. Regresión
        del modo de falla de QA-023: un `ResponseValidationError` deja el endpoint caído
        para siempre, sin nada que el cliente pueda corregir."""
        cuenta = make_account(auth_headers, name="Moneda rara")

        # Por SQL crudo: la API ya no acepta una moneda fuera de patrón, pero la fila puede
        # existir (importación, seed viejo, edición directa en la base).
        db_session.execute(sa.text("UPDATE accounts SET currency = 'ZZ' WHERE id = :id"), {"id": cuenta["id"]})
        db_session.commit()

        detalle = client.get(f"/api/v1/accounts/{cuenta['id']}", headers=auth_headers)
        assert detalle.status_code == 200, detalle.text
        assert detalle.json()["currency"] == "ZZ"

        listado = client.get("/api/v1/accounts/", headers=auth_headers)
        assert listado.status_code == 200, listado.text
        assert next(c for c in listado.json() if c["id"] == cuenta["id"])["currency"] == "ZZ"


class TestNombreEnBlanco:
    """QA-028: `min_length=1` no alcanza — `"   "` tiene longitud 3 y pasaba el filtro,
    dejando una cuenta cuyo nombre en la UI es indistinguible de otro."""

    def test_nombre_en_blanco_devuelve_422(self, client, auth_headers, make_account):
        create = client.post(
            "/api/v1/accounts/", json={"name": "   ", "type": "cash", "balance": "100.00"}, headers=auth_headers
        )
        assert create.status_code == 422, create.text

        cuenta = make_account(auth_headers, name="Cuenta real")
        update = client.put(
            f"/api/v1/accounts/{cuenta['id']}",
            json={"name": "   ", "type": cuenta["type"]},
            headers=auth_headers,
        )
        assert update.status_code == 422, update.text
        # El nombre no se tocó (la validación es previo al handler).
        detalle = client.get(f"/api/v1/accounts/{cuenta['id']}", headers=auth_headers)
        assert detalle.json()["name"] == "Cuenta real"


class TestPaginacionInvalida:
    """QA-025 (paginación): `OFFSET -1` / `LIMIT -1` son error de sintaxis en Postgres, así
    que un `skip`/`limit` negativo devolvía 500 en texto plano."""

    def test_paginacion_invalida_devuelve_422(self, client, auth_headers):
        for params in ("skip=-1", "limit=-1", "limit=0", "limit=201"):
            response = client.get(f"/api/v1/accounts/?{params}", headers=auth_headers)
            assert response.status_code == 422, f"{params} → {response.status_code} {response.text}"

    def test_limit_en_el_tope_sigue_funcionando(self, client, auth_headers, make_account):
        make_account(auth_headers, name="Cuenta con historial largo")

        response = client.get("/api/v1/accounts/?limit=200", headers=auth_headers)
        assert response.status_code == 200, response.text
        # Trae la cuenta del registro + la recién creada: el tope no recorta el uso real.
        assert len(response.json()) == 2
