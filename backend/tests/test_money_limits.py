"""T3 — QA-015 (B3, B4): rango de los cuatro campos de entrada con dinero.

Archivo nuevo para no chocar con los cambios de `test_transactions.py` (Orden de
ejecución de la spec, pasos 3-4 vs. 5). Los primeros casos (SQLite) prueban el 422 de
Pydantic (`detail` en lista) que produce B3. Los casos Postgres, al final del archivo y
marcados `postgres`, usan el seam de `pg_client` (`conftest.py`, compartido con
`tests/test_concurrency_pg.py`) para reproducir el desborde REAL del saldo de una
cuenta (B4: `NumericValueOutOfRange` → 422 de dominio con `detail` string) — SQLite no
aplica `Numeric`, así que no puede reproducir esta parte.
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

TRECE_DIGITOS = "1000000000000.00"  # 13 dígitos enteros — uno más del máximo permitido
DOCE_DIGITOS_DOS_DECIMALES = "999999999999.99"  # el máximo exacto que acepta Numeric(14,2)


def _month_year() -> tuple[int, int]:
    now = datetime.now(UTC)
    return now.month, now.year


class TestTransactionAmountRange:
    """`TransactionBase.amount` — `POST`/`PUT /transactions`."""

    def test_create_with_13_digits_returns_422_with_list_detail(
        self, client, auth_headers, make_account, make_category
    ):
        cuenta = make_account(auth_headers, balance="1000.00")
        categoria = make_category(auth_headers, name="Comida", type="expense")

        response = client.post(
            "/api/v1/transactions/",
            json={
                "amount": TRECE_DIGITOS,
                "type": "expense",
                "account_id": cuenta["id"],
                "category_id": categoria["id"],
            },
            headers=auth_headers,
        )
        assert response.status_code == 422, response.text
        assert isinstance(response.json()["detail"], list)

    def test_create_with_12_digits_two_decimals_is_accepted(self, client, auth_headers, make_account, make_category):
        cuenta = make_account(auth_headers, balance="0.00")
        categoria = make_category(auth_headers, name="Salario", type="income")

        response = client.post(
            "/api/v1/transactions/",
            json={
                "amount": DOCE_DIGITOS_DOS_DECIMALES,
                "type": "income",
                "account_id": cuenta["id"],
                "category_id": categoria["id"],
            },
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text

    def test_update_with_13_digits_returns_422_with_list_detail(
        self, client, auth_headers, make_account, make_category
    ):
        cuenta = make_account(auth_headers, balance="1000.00")
        categoria = make_category(auth_headers, name="Comida", type="expense")
        creada = client.post(
            "/api/v1/transactions/",
            json={
                "amount": "100.00",
                "type": "expense",
                "account_id": cuenta["id"],
                "category_id": categoria["id"],
            },
            headers=auth_headers,
        ).json()

        response = client.put(
            f"/api/v1/transactions/{creada['id']}",
            json={
                "amount": TRECE_DIGITOS,
                "currency": "COP",
                "type": "expense",
                "account_id": cuenta["id"],
                "category_id": categoria["id"],
            },
            headers=auth_headers,
        )
        assert response.status_code == 422, response.text
        assert isinstance(response.json()["detail"], list)


class TestAccountBalanceRange:
    """`AccountCreate.balance` — `POST /accounts`."""

    def test_13_digits_returns_422_with_list_detail(self, client, auth_headers):
        response = client.post(
            "/api/v1/accounts/",
            json={"name": "Cuenta enorme", "type": "cash", "currency": "COP", "balance": TRECE_DIGITOS},
            headers=auth_headers,
        )
        assert response.status_code == 422, response.text
        assert isinstance(response.json()["detail"], list)

    def test_12_digits_two_decimals_is_accepted(self, client, auth_headers):
        response = client.post(
            "/api/v1/accounts/",
            json={
                "name": "Cuenta enorme válida",
                "type": "cash",
                "currency": "COP",
                "balance": DOCE_DIGITOS_DOS_DECIMALES,
            },
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text


class TestMonthlyIncomeRange:
    """`UserProfileUpdate.monthly_income` — `PATCH /users/me`."""

    def test_13_digits_returns_422_with_list_detail(self, client, auth_headers):
        response = client.patch("/api/v1/users/me", json={"monthly_income": TRECE_DIGITOS}, headers=auth_headers)
        assert response.status_code == 422, response.text
        assert isinstance(response.json()["detail"], list)

    def test_12_digits_two_decimals_is_accepted(self, client, auth_headers):
        response = client.patch(
            "/api/v1/users/me", json={"monthly_income": DOCE_DIGITOS_DOS_DECIMALES}, headers=auth_headers
        )
        assert response.status_code == 200, response.text


class TestBudgetAmountLimitRange:
    """`BudgetBase.amount_limit` — `POST`/`PUT /budgets` (H8: el cuarto campo de dinero
    que la QA no había probado — misma forma exacta que los otros tres)."""

    def test_create_with_13_digits_returns_422_with_list_detail(self, client, auth_headers, make_category):
        categoria = make_category(auth_headers, name="Comida presupuesto", type="expense")
        month, year = _month_year()

        response = client.post(
            "/api/v1/budgets/",
            json={
                "amount_limit": TRECE_DIGITOS,
                "currency": "COP",
                "month": month,
                "year": year,
                "category_id": categoria["id"],
            },
            headers=auth_headers,
        )
        assert response.status_code == 422, response.text
        assert isinstance(response.json()["detail"], list)

    def test_create_with_12_digits_two_decimals_is_accepted(self, client, auth_headers, make_category):
        categoria = make_category(auth_headers, name="Comida presupuesto válido", type="expense")
        month, year = _month_year()

        response = client.post(
            "/api/v1/budgets/",
            json={
                "amount_limit": DOCE_DIGITOS_DOS_DECIMALES,
                "currency": "COP",
                "month": month,
                "year": year,
                "category_id": categoria["id"],
            },
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text

    def test_update_with_13_digits_returns_422_with_list_detail(self, client, auth_headers, make_category):
        categoria = make_category(auth_headers, name="Comida presupuesto editar", type="expense")
        month, year = _month_year()
        creado = client.post(
            "/api/v1/budgets/",
            json={
                "amount_limit": "500.00",
                "currency": "COP",
                "month": month,
                "year": year,
                "category_id": categoria["id"],
            },
            headers=auth_headers,
        ).json()

        response = client.put(
            f"/api/v1/budgets/{creado['id']}",
            json={
                "amount_limit": TRECE_DIGITOS,
                "currency": "COP",
                "month": month,
                "year": year,
                "category_id": categoria["id"],
                "is_recurring": False,
            },
            headers=auth_headers,
        )
        assert response.status_code == 422, response.text
        assert isinstance(response.json()["detail"], list)


@pytest.mark.postgres
class TestAccountBalanceOverflowIsA422OfDomain:
    """T3 (Postgres) — QA-015 (B4): con B3 el monto en sí ya es válido, así que el
    único `DataError` posible en `POST`/`PUT`/`DELETE /transactions` es el desborde
    real del `UPDATE` de `Account.balance` (`NumericValueOutOfRange`) — un `422` de
    dominio con `detail` string, sin tocar el saldo. Usa el seam de `pg_client`
    (`conftest.py`, compartido con `tests/test_concurrency_pg.py`): SQLite no aplica
    `Numeric`, así que estos tres casos solo pueden reproducirse contra Postgres.
    """

    MAXIMO = "999999999999.99"  # el máximo exacto que acepta Numeric(14,2)

    def test_income_that_would_overflow_the_balance_returns_422_and_balance_intact(
        self, pg_client, pg_register_and_login, pg_make_account, pg_make_category
    ):
        user = pg_register_and_login(email="overflow-post@example.com")
        cuenta = pg_make_account(user["headers"], balance=self.MAXIMO)
        categoria = pg_make_category(user["headers"], name="Salario", type="income")

        response = pg_client.post(
            "/api/v1/transactions/",
            json={
                "amount": "1.00",
                "type": "income",
                "account_id": cuenta["id"],
                "category_id": categoria["id"],
            },
            headers=user["headers"],
        )
        assert response.status_code == 422, response.text
        assert isinstance(response.json()["detail"], str)

        cuenta_final = pg_client.get(f"/api/v1/accounts/{cuenta['id']}", headers=user["headers"])
        assert Decimal(str(cuenta_final.json()["balance"])) == Decimal(self.MAXIMO)

    def test_update_that_would_overflow_the_balance_returns_422_and_balance_intact(
        self, pg_client, pg_register_and_login, pg_make_account, pg_make_category
    ):
        user = pg_register_and_login(email="overflow-put@example.com")
        cuenta = pg_make_account(user["headers"], balance=self.MAXIMO)
        categoria = pg_make_category(user["headers"], name="Comida", type="expense")

        creada = pg_client.post(
            "/api/v1/transactions/",
            json={
                "amount": "500.00",
                "type": "expense",
                "account_id": cuenta["id"],
                "category_id": categoria["id"],
            },
            headers=user["headers"],
        ).json()
        # balance: MAXIMO - 500.00

        # Cambiar de expense a income con el MISMO monto duplica el impacto en el
        # signo (delta neto = +1000.00) y desborda de nuevo hacia arriba.
        response = pg_client.put(
            f"/api/v1/transactions/{creada['id']}",
            json={
                "amount": "500.00",
                "currency": "COP",
                "type": "income",
                "description": "cambio de signo que desborda",
                "account_id": cuenta["id"],
                "category_id": categoria["id"],
            },
            headers=user["headers"],
        )
        assert response.status_code == 422, response.text
        assert isinstance(response.json()["detail"], str)

        cuenta_final = pg_client.get(f"/api/v1/accounts/{cuenta['id']}", headers=user["headers"])
        assert Decimal(str(cuenta_final.json()["balance"])) == Decimal(self.MAXIMO) - Decimal("500.00")

    def test_delete_of_an_expense_that_would_overflow_the_balance_returns_422_and_balance_intact(
        self, pg_client, pg_register_and_login, pg_make_account, pg_make_category
    ):
        user = pg_register_and_login(email="overflow-delete@example.com")
        cuenta = pg_make_account(user["headers"], balance=self.MAXIMO)
        categoria_gasto = pg_make_category(user["headers"], name="Comida", type="expense")
        categoria_ingreso = pg_make_category(user["headers"], name="Salario", type="income")

        tx_gasto = pg_client.post(
            "/api/v1/transactions/",
            json={
                "amount": "500.00",
                "type": "expense",
                "account_id": cuenta["id"],
                "category_id": categoria_gasto["id"],
            },
            headers=user["headers"],
        ).json()
        # balance: MAXIMO - 500.00

        ingreso = pg_client.post(
            "/api/v1/transactions/",
            json={
                "amount": "500.00",
                "type": "income",
                "account_id": cuenta["id"],
                "category_id": categoria_ingreso["id"],
            },
            headers=user["headers"],
        )
        assert ingreso.status_code == 200, ingreso.text
        # balance: de vuelta en MAXIMO

        # Revertir (borrar) el gasto original suma +500.00 de nuevo → desborda.
        response = pg_client.delete(f"/api/v1/transactions/{tx_gasto['id']}", headers=user["headers"])
        assert response.status_code == 422, response.text
        assert isinstance(response.json()["detail"], str)

        cuenta_final = pg_client.get(f"/api/v1/accounts/{cuenta['id']}", headers=user["headers"])
        assert Decimal(str(cuenta_final.json()["balance"])) == Decimal(self.MAXIMO)
