"""Tests del módulo contable: transacciones y su impacto en `Account.balance`.

Alcance de Fase 7 §4.2: "solo la lógica que mueve dinero" — no cobertura completa de
`transactions.py` (paginación, filtros de fecha, etc. quedan fuera).
"""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient


def _get_account(client: TestClient, headers: dict, account_id: int) -> dict:
    response = client.get(f"/api/v1/accounts/{account_id}", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _create_transaction(client: TestClient, headers: dict, **overrides) -> dict:
    payload = {
        "amount": "100.00",
        "type": "expense",
        "description": "tx de prueba",
    }
    payload.update(overrides)
    response = client.post("/api/v1/transactions/", json=payload, headers=headers)
    return response


class TestCreateTransactionAdjustsBalance:
    def test_income_increments_balance_by_exact_amount(self, client, auth_headers, make_account, make_category):
        cuenta = make_account(auth_headers, balance="1000.00")
        categoria = make_category(auth_headers, name="Salario", type="income")

        response = _create_transaction(
            client,
            auth_headers,
            amount="250.50",
            type="income",
            account_id=cuenta["id"],
            category_id=categoria["id"],
        )
        assert response.status_code == 200, response.text

        cuenta_actualizada = _get_account(client, auth_headers, cuenta["id"])
        assert Decimal(str(cuenta_actualizada["balance"])) == Decimal("1250.50")

    def test_expense_decrements_balance_by_exact_amount(self, client, auth_headers, make_account, make_category):
        cuenta = make_account(auth_headers, balance="1000.00")
        categoria = make_category(auth_headers, name="Comida", type="expense")

        response = _create_transaction(
            client,
            auth_headers,
            amount="150.25",
            type="expense",
            account_id=cuenta["id"],
            category_id=categoria["id"],
        )
        assert response.status_code == 200, response.text

        cuenta_actualizada = _get_account(client, auth_headers, cuenta["id"])
        assert Decimal(str(cuenta_actualizada["balance"])) == Decimal("849.75")

    def test_new_transaction_inherits_account_currency(self, client, auth_headers, make_account, make_category):
        cuenta = make_account(auth_headers, currency="USD", balance="500.00")
        categoria = make_category(auth_headers, name="Freelance", type="income")

        response = _create_transaction(
            client,
            auth_headers,
            amount="10.00",
            type="income",
            account_id=cuenta["id"],
            category_id=categoria["id"],
        )
        assert response.status_code == 200, response.text
        assert response.json()["currency"] == "USD"

    def test_foreign_account_returns_404(self, client, auth_headers, other_user, make_account, make_category):
        cuenta_ajena = make_account(other_user["headers"], balance="1000.00")
        categoria = make_category(auth_headers, name="Comida", type="expense")

        response = _create_transaction(
            client,
            auth_headers,
            amount="50.00",
            type="expense",
            account_id=cuenta_ajena["id"],
            category_id=categoria["id"],
        )
        assert response.status_code == 404

    def test_foreign_category_returns_404(self, client, auth_headers, other_user, make_account, make_category):
        cuenta = make_account(auth_headers, balance="1000.00")
        categoria_ajena = make_category(other_user["headers"], name="Categoría ajena", type="expense")

        response = _create_transaction(
            client,
            auth_headers,
            amount="50.00",
            type="expense",
            account_id=cuenta["id"],
            category_id=categoria_ajena["id"],
        )
        assert response.status_code == 404


class TestDeleteTransactionRevertsBalance:
    def test_delete_expense_reverts_exact_impact(self, client, auth_headers, make_account, make_category):
        cuenta = make_account(auth_headers, balance="1000.00")
        categoria = make_category(auth_headers, name="Comida", type="expense")

        creada = _create_transaction(
            client,
            auth_headers,
            amount="300.00",
            type="expense",
            account_id=cuenta["id"],
            category_id=categoria["id"],
        ).json()

        cuenta_tras_crear = _get_account(client, auth_headers, cuenta["id"])
        assert Decimal(str(cuenta_tras_crear["balance"])) == Decimal("700.00")

        delete_response = client.delete(f"/api/v1/transactions/{creada['id']}", headers=auth_headers)
        assert delete_response.status_code == 200, delete_response.text

        cuenta_final = _get_account(client, auth_headers, cuenta["id"])
        assert Decimal(str(cuenta_final["balance"])) == Decimal("1000.00")

    def test_delete_income_reverts_exact_impact(self, client, auth_headers, make_account, make_category):
        cuenta = make_account(auth_headers, balance="1000.00")
        categoria = make_category(auth_headers, name="Salario", type="income")

        creada = _create_transaction(
            client,
            auth_headers,
            amount="400.00",
            type="income",
            account_id=cuenta["id"],
            category_id=categoria["id"],
        ).json()

        client.delete(f"/api/v1/transactions/{creada['id']}", headers=auth_headers)

        cuenta_final = _get_account(client, auth_headers, cuenta["id"])
        assert Decimal(str(cuenta_final["balance"])) == Decimal("1000.00")

    def test_delete_foreign_transaction_returns_404(
        self, client, auth_headers, other_user, make_account, make_category
    ):
        cuenta = make_account(auth_headers, balance="1000.00")
        categoria = make_category(auth_headers, name="Comida", type="expense")
        creada = _create_transaction(
            client,
            auth_headers,
            amount="100.00",
            type="expense",
            account_id=cuenta["id"],
            category_id=categoria["id"],
        ).json()

        response = client.delete(f"/api/v1/transactions/{creada['id']}", headers=other_user["headers"])
        assert response.status_code == 404

        # y el saldo no debe haberse tocado
        cuenta_final = _get_account(client, auth_headers, cuenta["id"])
        assert Decimal(str(cuenta_final["balance"])) == Decimal("900.00")


class TestUpdateTransactionAdjustsBalance:
    def test_update_same_account_applies_net_delta(self, client, auth_headers, make_account, make_category):
        cuenta = make_account(auth_headers, balance="1000.00")
        categoria = make_category(auth_headers, name="Comida", type="expense")

        creada = _create_transaction(
            client,
            auth_headers,
            amount="200.00",
            type="expense",
            account_id=cuenta["id"],
            category_id=categoria["id"],
        ).json()
        # balance: 1000 - 200 = 800

        update_payload = {
            "amount": "500.00",
            "currency": "COP",
            "type": "expense",
            "description": "monto editado",
            "account_id": cuenta["id"],
            "category_id": categoria["id"],
        }
        update_response = client.put(f"/api/v1/transactions/{creada['id']}", json=update_payload, headers=auth_headers)
        assert update_response.status_code == 200, update_response.text

        # net_delta = (-500) - (-200) = -300 -> 800 - 300 = 500 (no 1000 - 500*2)
        cuenta_final = _get_account(client, auth_headers, cuenta["id"])
        assert Decimal(str(cuenta_final["balance"])) == Decimal("500.00")

    def test_update_moving_to_different_account_reverts_old_and_applies_new(
        self, client, auth_headers, make_account, make_category
    ):
        cuenta_a = make_account(auth_headers, name="Cuenta A", balance="1000.00")
        cuenta_b = make_account(auth_headers, name="Cuenta B", balance="500.00")
        categoria = make_category(auth_headers, name="Comida", type="expense")

        creada = _create_transaction(
            client,
            auth_headers,
            amount="200.00",
            type="expense",
            account_id=cuenta_a["id"],
            category_id=categoria["id"],
        ).json()
        # A: 1000 - 200 = 800, B: 500

        update_payload = {
            "amount": "200.00",
            "currency": "COP",
            "type": "expense",
            "description": "movida de cuenta",
            "account_id": cuenta_b["id"],
            "category_id": categoria["id"],
        }
        update_response = client.put(f"/api/v1/transactions/{creada['id']}", json=update_payload, headers=auth_headers)
        assert update_response.status_code == 200, update_response.text

        cuenta_a_final = _get_account(client, auth_headers, cuenta_a["id"])
        cuenta_b_final = _get_account(client, auth_headers, cuenta_b["id"])
        # A revertida por completo, B con el impacto completo aplicado
        assert Decimal(str(cuenta_a_final["balance"])) == Decimal("1000.00")
        assert Decimal(str(cuenta_b_final["balance"])) == Decimal("300.00")

    def test_update_with_foreign_account_returns_404(
        self, client, auth_headers, other_user, make_account, make_category
    ):
        cuenta = make_account(auth_headers, balance="1000.00")
        cuenta_ajena = make_account(other_user["headers"], balance="1000.00")
        categoria = make_category(auth_headers, name="Comida", type="expense")

        creada = _create_transaction(
            client,
            auth_headers,
            amount="200.00",
            type="expense",
            account_id=cuenta["id"],
            category_id=categoria["id"],
        ).json()

        update_payload = {
            "amount": "200.00",
            "currency": "COP",
            "type": "expense",
            "description": "intento mover a cuenta ajena",
            "account_id": cuenta_ajena["id"],
            "category_id": categoria["id"],
        }
        response = client.put(f"/api/v1/transactions/{creada['id']}", json=update_payload, headers=auth_headers)
        assert response.status_code == 404

    def test_update_with_foreign_category_returns_404(
        self, client, auth_headers, other_user, make_account, make_category
    ):
        cuenta = make_account(auth_headers, balance="1000.00")
        categoria = make_category(auth_headers, name="Comida", type="expense")
        categoria_ajena = make_category(other_user["headers"], name="Categoría ajena", type="expense")

        creada = _create_transaction(
            client,
            auth_headers,
            amount="200.00",
            type="expense",
            account_id=cuenta["id"],
            category_id=categoria["id"],
        ).json()

        update_payload = {
            "amount": "200.00",
            "currency": "COP",
            "type": "expense",
            "description": "intento con categoría ajena",
            "account_id": cuenta["id"],
            "category_id": categoria_ajena["id"],
        }
        response = client.put(f"/api/v1/transactions/{creada['id']}", json=update_payload, headers=auth_headers)
        assert response.status_code == 404


class TestPaymentMethod:
    """Fase 8 §2: tag opcional cash/card/transfer. Validación de valores en el schema
    Pydantic (`PaymentMethod`), no como constraint de DB."""

    def test_create_with_payment_method_persists_and_returns_it(
        self, client, auth_headers, make_account, make_category
    ):
        cuenta = make_account(auth_headers, balance="1000.00")
        categoria = make_category(auth_headers, name="Comida", type="expense")

        creada = _create_transaction(
            client,
            auth_headers,
            amount="100.00",
            type="expense",
            account_id=cuenta["id"],
            category_id=categoria["id"],
            payment_method="card",
        )
        assert creada.status_code == 200, creada.text
        assert creada.json()["payment_method"] == "card"

    def test_update_changes_payment_method(self, client, auth_headers, make_account, make_category):
        """Cubre la línea explícita de `actualizar_transaccion`: sin ella, el PUT borraría
        silenciosamente el payment_method no reenviado (bug-clase AccountUpdate.currency)."""
        cuenta = make_account(auth_headers, balance="1000.00")
        categoria = make_category(auth_headers, name="Comida", type="expense")

        creada = _create_transaction(
            client,
            auth_headers,
            amount="100.00",
            type="expense",
            account_id=cuenta["id"],
            category_id=categoria["id"],
            payment_method="card",
        ).json()
        assert creada["payment_method"] == "card"

        update_payload = {
            "amount": "100.00",
            "currency": "COP",
            "type": "expense",
            "description": "cambio de método",
            "account_id": cuenta["id"],
            "category_id": categoria["id"],
            "payment_method": "transfer",
        }
        update_response = client.put(f"/api/v1/transactions/{creada['id']}", json=update_payload, headers=auth_headers)
        assert update_response.status_code == 200, update_response.text
        assert update_response.json()["payment_method"] == "transfer"

    def test_update_without_resending_payment_method_keeps_it(self, client, auth_headers, make_account, make_category):
        cuenta = make_account(auth_headers, balance="1000.00")
        categoria = make_category(auth_headers, name="Comida", type="expense")

        creada = _create_transaction(
            client,
            auth_headers,
            amount="100.00",
            type="expense",
            account_id=cuenta["id"],
            category_id=categoria["id"],
            payment_method="cash",
        ).json()

        update_payload = {
            "amount": "150.00",
            "currency": "COP",
            "type": "expense",
            "description": "solo monto editado",
            "account_id": cuenta["id"],
            "category_id": categoria["id"],
        }
        update_response = client.put(f"/api/v1/transactions/{creada['id']}", json=update_payload, headers=auth_headers)
        assert update_response.status_code == 200, update_response.text
        assert update_response.json()["payment_method"] == "cash"

    def test_invalid_payment_method_value_returns_422(self, client, auth_headers, make_account, make_category):
        cuenta = make_account(auth_headers, balance="1000.00")
        categoria = make_category(auth_headers, name="Comida", type="expense")

        response = _create_transaction(
            client,
            auth_headers,
            amount="100.00",
            type="expense",
            account_id=cuenta["id"],
            category_id=categoria["id"],
            payment_method="criptomoneda",
        )
        assert response.status_code == 422

    def test_transaction_without_payment_method_is_valid(self, client, auth_headers, make_account, make_category):
        cuenta = make_account(auth_headers, balance="1000.00")
        categoria = make_category(auth_headers, name="Comida", type="expense")

        creada = _create_transaction(
            client,
            auth_headers,
            amount="100.00",
            type="expense",
            account_id=cuenta["id"],
            category_id=categoria["id"],
        )
        assert creada.status_code == 200, creada.text
        assert creada.json()["payment_method"] is None


@pytest.mark.xfail(
    reason=(
        "Bug conocido documentado en docs/TODO.md (' actualizar_transaccion no actualiza "
        "currency'): mover una transacción a una cuenta de otra moneda deja transaccion.currency "
        "con el valor viejo en vez de heredar la moneda de la cuenta nueva. Fix planeado para "
        "Fase 10, no en el alcance de Fase 7 — este test debe seguir fallando hasta entonces."
    ),
    strict=True,
)
def test_update_moving_to_different_currency_account_updates_currency(
    client, auth_headers, make_account, make_category
):
    cuenta_cop = make_account(auth_headers, name="Cuenta COP", currency="COP", balance="1000.00")
    cuenta_usd = make_account(auth_headers, name="Cuenta USD", currency="USD", balance="500.00")
    categoria = make_category(auth_headers, name="Comida", type="expense")

    creada = _create_transaction(
        client,
        auth_headers,
        amount="100.00",
        type="expense",
        account_id=cuenta_cop["id"],
        category_id=categoria["id"],
    ).json()
    assert creada["currency"] == "COP"

    update_payload = {
        "amount": "100.00",
        "currency": "COP",
        "type": "expense",
        "description": "movida a cuenta en otra moneda",
        "account_id": cuenta_usd["id"],
        "category_id": categoria["id"],
    }
    update_response = client.put(f"/api/v1/transactions/{creada['id']}", json=update_payload, headers=auth_headers)
    assert update_response.status_code == 200, update_response.text

    # Comportamiento correcto esperado: la transacción debería heredar la moneda de su
    # nueva cuenta (USD), igual que hace al crearse (transactions.py:52). Hoy no ocurre.
    assert update_response.json()["currency"] == "USD"
