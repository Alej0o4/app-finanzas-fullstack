"""Tests de cuentas (Fase 11 §11.5 + Fase 16 §16.4).

Fase 11: el endpoint GET /api/v1/accounts/summary. Fase 16: `opening_balance` en la
creación y el endpoint POST /api/v1/accounts/{id}/reconcile (Decisión 16.4.2).
"""

from decimal import Decimal

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
