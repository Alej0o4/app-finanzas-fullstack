"""Tests del módulo contable: transacciones y su impacto en `Account.balance`.

Alcance de Fase 7 §4.2: "solo la lógica que mueve dinero" — no cobertura completa de
`transactions.py` (paginación, filtros de fecha, etc. quedan fuera), más lo que añadieron
los fixes de QA: `PUT` parcial (QA-026), moneda y paginación (QA-025) y el `PUT` con la
cuenta de origen ya borrada (QA-031).
"""

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal

import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy import event, update

from app.models import models
from app.schemas import schemas


def _get_account(client: TestClient, headers: dict, account_id: int) -> dict:
    response = client.get(f"/api/v1/accounts/{account_id}", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _saldo_crudo(db_session, account_id: int) -> Decimal:
    """Saldo leído por SQL crudo. Necesario para filas soft-deleted: el filtro global de
    `core/database.py` las esconde tanto a las queries ORM como a un `select()` Core
    (con `with_loader_criteria`acting sobre cualquier statement con entidades ORM), y el
    objeto del identity map guarda el valor anterior al UPDATE — el ledger muta por Core
    SQL. Mismo patrón que `tests/test_ledger.py::_raw_balance`."""
    balance = db_session.execute(sa.text("SELECT balance FROM accounts WHERE id = :id"), {"id": account_id}).scalar()
    return Decimal(str(balance))


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


class TestConcurrencyGuardsSqlite:
    """T2 — QA-003 (B1, B2): regresión de `PUT`/`DELETE /transactions/{id}` bajo
    concurrencia. SQLite no soporta `FOR UPDATE` (Further Notes de la spec: "B1 solo
    protege de verdad en Postgres"); la protección real la prueba
    `tests/test_concurrency.py`, marcado `concurrencia` (Fase 32, B4). Acá se prueban dos guardas sin
    carrera real y una reproducción determinista del borrado condicional (segunda
    defensa, Q2) vía intercalado de sesión — mismo mecanismo que
    `test_race_condition_integrity_error_rolls_back_without_raising`
    (`tests/test_budget_recurrence.py`)."""

    def test_second_delete_on_same_transaction_returns_404_and_does_not_touch_balance(
        self, client, auth_headers, make_account, make_category
    ):
        """Guarda, NO reproduce el bug de QA-003: sin carrera real, el filtro global de
        `core/database.py` ya oculta la fila soft-deleted en el segundo DELETE — este
        test pasa también antes del fix de B1."""
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

        primero = client.delete(f"/api/v1/transactions/{creada['id']}", headers=auth_headers)
        assert primero.status_code == 200, primero.text

        segundo = client.delete(f"/api/v1/transactions/{creada['id']}", headers=auth_headers)
        assert segundo.status_code == 404

        cuenta_final = _get_account(client, auth_headers, cuenta["id"])
        assert Decimal(str(cuenta_final["balance"])) == Decimal("1000.00")

    def test_update_on_deleted_transaction_returns_404_and_does_not_touch_balance(
        self, client, auth_headers, make_account, make_category
    ):
        """Guarda, NO reproduce el bug de QA-003 — pasa también antes del fix de B1."""
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
        client.delete(f"/api/v1/transactions/{creada['id']}", headers=auth_headers)

        update_payload = {
            "amount": "500.00",
            "currency": "COP",
            "type": "expense",
            "description": "intento de editar lo borrado",
            "account_id": cuenta["id"],
            "category_id": categoria["id"],
        }
        response = client.put(f"/api/v1/transactions/{creada['id']}", json=update_payload, headers=auth_headers)
        assert response.status_code == 404

        cuenta_final = _get_account(client, auth_headers, cuenta["id"])
        assert Decimal(str(cuenta_final["balance"])) == Decimal("1000.00")

    def test_delete_intercalated_with_winning_concurrent_delete_returns_404_and_reverts_once(
        self, client, db_session, auth_headers, make_account, make_category
    ):
        """Reproducción determinista del borrado condicional (B1, segunda defensa, Q2).

        Un listener sobre `db_session` intercepta el UPDATE condicional de
        `eliminar_transaccion` justo antes de que se ejecute — el punto exacto "entre
        la lectura de la transacción y la escritura" — y en su lugar simula que OTRA
        petición ya ganó la carrera: revierte el saldo y marca la transacción borrada,
        con un commit real (mismos savepoints que usa `db_session`, no hace falta
        threading para esta parte). Cuando el UPDATE condicional de nuestra propia
        petición se ejecuta después, `rowcount == 0` (la fila ya no cumple
        `deleted_at IS NULL`).

        Falla antes del fix: el código viejo revertía el saldo sin condición (sin este
        UPDATE condicional en absoluto) y devolvía `200` sin importar lo que hiciera la
        "otra" petición — el saldo se revertía dos veces."""
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

        disparado = {"n": 0}

        def _delete_ganador(execute_state):
            stmt = execute_state.statement
            if (
                disparado["n"] == 0
                and getattr(stmt, "is_update", False)
                and getattr(getattr(stmt, "table", None), "name", None) == "transactions"
            ):
                disparado["n"] += 1
                db_session.execute(
                    update(models.Account)
                    .where(models.Account.id == cuenta["id"])
                    .values(balance=models.Account.balance + Decimal("300.00"))
                )
                db_session.execute(
                    update(models.Transaction)
                    .where(models.Transaction.id == creada["id"])
                    .values(deleted_at=datetime.now(UTC))
                )
                db_session.commit()

        event.listen(db_session, "do_orm_execute", _delete_ganador)
        try:
            response = client.delete(f"/api/v1/transactions/{creada['id']}", headers=auth_headers)
        finally:
            event.remove(db_session, "do_orm_execute", _delete_ganador)

        assert disparado["n"] == 1  # la intercalación sí ocurrió (rama ejercitada)
        assert response.status_code == 404, response.text

        # El saldo se revirtió UNA sola vez (por el "ganador" simulado), no dos.
        cuenta_final = _get_account(client, auth_headers, cuenta["id"])
        assert Decimal(str(cuenta_final["balance"])) == Decimal("1000.00")


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


class TestUpdateParcialOpcionales:
    """QA-026: `PUT /transactions/{id}` actualiza de verdad solo los campos presentes en el
    body — ausente conserva, `null` explícito limpia. Antes `description` se asignaba siempre
    (`transaccion_db.description = transaccion_actualizada.description`), así que un cliente
    API que mandara un payload parcial —un atajo móvil, una captura por nombre— borraba la
    descripción sin querer. `payment_method` conservaba pero no limpiaba: el `null` explícito
    se ignoraba en silencio."""

    def _creada(self, client, headers, cuenta, categoria, **overrides) -> dict:
        payload = {
            "amount": "100.00",
            "type": "expense",
            "description": "descripción original",
            "payment_method": "card",
            "account_id": cuenta["id"],
            "category_id": categoria["id"],
        }
        payload.update(overrides)
        creada = _create_transaction(client, headers, **payload).json()
        assert creada["description"] == "descripción original"
        assert creada["payment_method"] == "card"
        return creada

    def _put(self, client, headers, transaction_id: int, cuenta, categoria, **overrides):
        payload = {
            "amount": "150.00",
            "type": "expense",
            "currency": "COP",
            "account_id": cuenta["id"],
            "category_id": categoria["id"],
        }
        payload.update(overrides)
        return client.put(f"/api/v1/transactions/{transaction_id}", json=payload, headers=headers)

    def test_put_sin_description_conserva_la_descripcion(self, client, auth_headers, make_account, make_category):
        cuenta = make_account(auth_headers, balance="1000.00")
        categoria = make_category(auth_headers, name="Comida", type="expense")
        creada = self._creada(client, auth_headers, cuenta, categoria)

        response = self._put(client, auth_headers, creada["id"], cuenta, categoria)

        assert response.status_code == 200, response.text
        assert response.json()["description"] == "descripción original"

    def test_put_con_description_null_la_limpia(self, client, auth_headers, make_account, make_category):
        cuenta = make_account(auth_headers, balance="1000.00")
        categoria = make_category(auth_headers, name="Comida", type="expense")
        creada = self._creada(client, auth_headers, cuenta, categoria)

        response = self._put(client, auth_headers, creada["id"], cuenta, categoria, description=None)

        assert response.status_code == 200, response.text
        assert response.json()["description"] is None

    def test_put_sin_payment_method_lo_conserva(self, client, auth_headers, make_account, make_category):
        cuenta = make_account(auth_headers, balance="1000.00")
        categoria = make_category(auth_headers, name="Comida", type="expense")
        creada = self._creada(client, auth_headers, cuenta, categoria)

        response = self._put(client, auth_headers, creada["id"], cuenta, categoria)

        assert response.status_code == 200, response.text
        assert response.json()["payment_method"] == "card"

    def test_put_con_payment_method_null_lo_limpia(self, client, auth_headers, make_account, make_category):
        cuenta = make_account(auth_headers, balance="1000.00")
        categoria = make_category(auth_headers, name="Comida", type="expense")
        creada = self._creada(client, auth_headers, cuenta, categoria)

        response = self._put(client, auth_headers, creada["id"], cuenta, categoria, payment_method=None)

        assert response.status_code == 200, response.text
        assert response.json()["payment_method"] is None

    def test_put_sin_description_no_toca_la_fecha_ni_el_saldo(self, client, auth_headers, make_account, make_category):
        """El resto del PUT sigue siendo un PUT completo: lo que no se toca es solo lo que
        el cliente no mandó. El saldo se recalcula contra el monto nuevo (100 → 150)."""
        cuenta = make_account(auth_headers, balance="1000.00")
        categoria = make_category(auth_headers, name="Comida", type="expense")
        creada = self._creada(client, auth_headers, cuenta, categoria)
        fecha_original = creada["date"]

        response = self._put(client, auth_headers, creada["id"], cuenta, categoria)

        assert response.status_code == 200, response.text
        assert response.json()["date"] == fecha_original
        assert Decimal(str(_get_account(client, auth_headers, cuenta["id"])["balance"])) == Decimal("850.00")


class TestPutConCuentaAnteriorBorrada:
    """QA-031: `PUT /transactions/{id}` con la cuenta de ORIGEN ya borrada (soft-delete).

    Hoy es inalcanzable por la API —`eliminar_cuenta` bloquea borrar una cuenta con
    transacciones— pero la fila se puede llegar a tener así (un borrado manual, un script, o
    el futuro de la fila si el guard cambia). El código viejo hacía una query para traer la
    cuenta vieja y usaba `cuenta_vieja.id`: con la fila borrada devolvía `None` y el `.id`
    reventaba con `AttributeError` → 500. El fix pasa `transaccion_db.account_id` directo,
    que por construcción ES el mismo id, así que el saldo de la cuenta desaparecida
    conserva su valor obsoleto (filtro `deleted_at IS NULL` de `ledger.aplicar_delta`,
    Decisión 6.1) y el saldo de la cuenta destino se calcula de verdad."""

    def test_put_con_cuenta_anterior_borrada_no_revienta(
        self, client, db_session, auth_headers, make_account, make_category
    ):
        cuenta_vieja = make_account(auth_headers, name="Cuenta que desaparece", balance="1000.00")
        cuenta_nueva = make_account(auth_headers, name="Cuenta destino", balance="500.00")
        categoria = make_category(auth_headers, name="Comida", type="expense")

        creada = _create_transaction(
            client,
            auth_headers,
            amount="100.00",
            type="expense",
            description="gasto que se mueve de cuenta",
            account_id=cuenta_vieja["id"],
            category_id=categoria["id"],
        ).json()

        # Se fuerza el invariante por SQL crudo (el filtro global de soft-delete oculta la
        # fila a las queries ORM, y la API no tiene ruta para llegar acá) — mismo patrón que
        # `tests/test_ledger.py::TestAplicarDelta.test_cuenta_soft_deleted_no_cambia_su_balance`.
        db_session.execute(
            sa.text("UPDATE accounts SET deleted_at = CURRENT_TIMESTAMP WHERE id = :id"), {"id": cuenta_vieja["id"]}
        )
        db_session.commit()

        response = client.put(
            f"/api/v1/transactions/{creada['id']}",
            json={
                "amount": "100.00",
                "currency": "COP",
                "type": "expense",
                "description": "gasto que se mueve de cuenta",
                "account_id": cuenta_nueva["id"],
                "category_id": categoria["id"],
            },
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["account_id"] == cuenta_nueva["id"]

        # El saldo de la cuenta nueva se aplicó de verdad (500 - 100), y el de la borrada
        # quedó con su valor obsoleto (1000 - 100), sin reventar.
        assert Decimal(str(_get_account(client, auth_headers, cuenta_nueva["id"])["balance"])) == Decimal("400.00")
        assert _saldo_crudo(db_session, cuenta_vieja["id"]) == Decimal("900.00")


class TestCurrencyInvalida:
    """QA-025 (moneda): `TransactionBase.currency` es `String(3)` en el modelo, así que un
    valor más largo llegaba al INSERT y volvía como 500 (`StringDataRightTruncation` es un
    `DataError`). Ahora el patrón `^[A-Z]{3}$` vive en el schema de REQUEST."""

    @staticmethod
    def _payload(cuenta, categoria, **overrides) -> dict:
        payload = {
            "amount": "100.00",
            "type": "expense",
            "account_id": cuenta["id"],
            "category_id": categoria["id"],
        }
        payload.update(overrides)
        return payload

    def test_currency_invalida_devuelve_422(self, client, auth_headers, make_account, make_category):
        cuenta = make_account(auth_headers, balance="1000.00")
        categoria = make_category(auth_headers, name="Comida", type="expense")

        for currency in ("zzzzzz", "", "cop", "XX"):
            response = client.post(
                "/api/v1/transactions/",
                json=self._payload(cuenta, categoria, currency=currency),
                headers=auth_headers,
            )
            assert response.status_code == 422, f"{currency!r} → {response.status_code} {response.text}"

    def test_cuenta_con_moneda_rara_no_rompe_el_get(
        self, client, db_session, auth_headers, make_account, make_category
    ):
        """El response NO revalida el patrón: una cuenta con `currency="ZZ"` (que `String(3)`
        acepta) tiene que poder listarse y leerse, no devolver 500. Regresión del modo de
        falla de QA-023 con los budgets: un `ResponseValidationError` deja el endpoint
        caído para siempre."""
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

        # Moneda fuera de patrón por SQL crudo: la API ya no la acepta, pero la fila puede
        # existir (importación, seed viejo, edition directa).
        db_session.execute(sa.text("UPDATE accounts SET currency = 'ZZ' WHERE id = :id"), {"id": cuenta["id"]})
        db_session.execute(sa.text("UPDATE transactions SET currency = 'ZZ' WHERE id = :id"), {"id": creada["id"]})
        db_session.commit()

        detalle = client.get(f"/api/v1/accounts/{cuenta['id']}", headers=auth_headers)
        assert detalle.status_code == 200, detalle.text
        assert detalle.json()["currency"] == "ZZ"

        listado = client.get("/api/v1/transactions/", headers=auth_headers)
        assert listado.status_code == 200, listado.text
        assert listado.json()["items"][0]["currency"] == "ZZ"


class TestPaginacionInvalida:
    """QA-025 (paginación): `OFFSET -1` / `LIMIT -1` son error de sintaxis en Postgres, así
    que un `skip`/`limit` negativo devolvía un 500 en texto plano. Ahora ambos tienen
    `ge`, y `limit` además un tope."""

    def test_paginacion_invalida_devuelve_422(self, client, auth_headers):
        for params in ("skip=-1", "limit=-1", "limit=0", "limit=1001"):
            response = client.get(f"/api/v1/transactions/?{params}", headers=auth_headers)
            assert response.status_code == 422, f"{params} → {response.status_code} {response.text}"

    def test_limit_en_el_tope_sigue_funcionando(self, client, auth_headers):
        response = client.get("/api/v1/transactions/?limit=1000", headers=auth_headers)
        assert response.status_code == 200, response.text
        assert response.json()["page_size"] == 1000
        assert response.json()["page"] == 1


def test_update_moving_to_different_currency_account_updates_currency(
    client, auth_headers, make_account, make_category
):
    """Fase 11 §11.2: mover una transacción a una cuenta de otra moneda hereda la moneda
    de la cuenta destino, igual que en la creación (antes quedaba con el valor viejo —
    bug documentado en docs/TODO.md y resuelto en esta fase)."""
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

    # La transacción hereda la moneda de su nueva cuenta (USD), igual que hace al crearse.
    assert update_response.json()["currency"] == "USD"


class TestIdempotencyKeyHeader:
    """Fase 10 §10.4: header `Idempotency-Key` en POST /transactions.

    La clave viaja como header HTTP (no como campo del body); el constraint de
    unicidad en DB es `(user_id, key)`, no global.
    """

    def _post(self, client: TestClient, headers: dict, payload: dict):
        return client.post("/api/v1/transactions/", json=payload, headers=headers)

    def test_replay_same_key_same_payload_returns_same_transaction_and_moves_balance_once(
        self, client, auth_headers, make_account, make_category
    ):
        """Caso central del ítem: el reintento NO crea una segunda transacción ni vuelve
        a mover el saldo — ambas respuestas comparten id y el delta se aplicó UNA vez."""
        cuenta = make_account(auth_headers, balance="1000.00")
        categoria = make_category(auth_headers, name="Comida", type="expense")
        payload = {
            "amount": "100.00",
            "type": "expense",
            "description": "compra con posible reintento",
            "account_id": cuenta["id"],
            "category_id": categoria["id"],
        }
        headers = {**auth_headers, "Idempotency-Key": "01890c5a-d6de-7de1-a3f2-clave-de-prueba"}

        primera = self._post(client, headers, payload)
        segunda = self._post(client, headers, payload)  # reintento con la misma clave

        assert primera.status_code == 200, primera.text
        assert segunda.status_code == 200, segunda.text
        assert segunda.json()["id"] == primera.json()["id"]

        cuenta_final = _get_account(client, auth_headers, cuenta["id"])
        # Delta exacto aplicado una sola vez: 1000 - 100 = 900 (un doble cobro daría 800)
        assert Decimal(str(cuenta_final["balance"])) == Decimal("900.00")

    def test_replay_same_key_different_amount_returns_409(self, client, auth_headers, make_account, make_category):
        """Decisión 10.4.3: clave conocida + hash distinto → 409 Conflict (no replay
        silencioso ni segunda transacción)."""
        cuenta = make_account(auth_headers, balance="1000.00")
        categoria = make_category(auth_headers, name="Comida", type="expense")
        payload = {
            "amount": "100.00",
            "type": "expense",
            "description": "compra original",
            "account_id": cuenta["id"],
            "category_id": categoria["id"],
        }
        headers = {**auth_headers, "Idempotency-Key": "clave-reusada-con-otro-payload"}

        primera = self._post(client, headers, payload)
        assert primera.status_code == 200, primera.text

        conflicto = self._post(client, headers, {**payload, "amount": "250.00"})
        assert conflicto.status_code == 409

        # Y el saldo solo se movió por la transacción original (no se creó la segunda)
        cuenta_final = _get_account(client, auth_headers, cuenta["id"])
        assert Decimal(str(cuenta_final["balance"])) == Decimal("900.00")

    def test_same_key_across_two_users_is_independent(
        self, client, auth_headers, other_user, make_account, make_category
    ):
        """El constraint es `(user_id, key)`, no global: dos usuarios pueden usar el
        mismo string literal como clave sin interferirse (cliente descuidado con clave
        constante en vez de UUID)."""
        cuenta_a = make_account(auth_headers, name="Cuenta A", balance="1000.00")
        categoria_a = make_category(auth_headers, name="Comida A", type="expense")
        cuenta_b = make_account(other_user["headers"], name="Cuenta B", balance="2000.00")
        categoria_b = make_category(other_user["headers"], name="Comida B", type="expense")

        payload_a = {
            "amount": "100.00",
            "type": "expense",
            "description": "gasto usuario A",
            "account_id": cuenta_a["id"],
            "category_id": categoria_a["id"],
        }
        payload_b = {
            "amount": "50.00",
            "type": "expense",
            "description": "gasto usuario B",
            "account_id": cuenta_b["id"],
            "category_id": categoria_b["id"],
        }
        headers_a = {**auth_headers, "Idempotency-Key": "clave-literal-compartida"}
        headers_b = {**other_user["headers"], "Idempotency-Key": "clave-literal-compartida"}

        respuesta_a = self._post(client, headers_a, payload_a)
        respuesta_b = self._post(client, headers_b, payload_b)

        assert respuesta_a.status_code == 200, respuesta_a.text
        assert respuesta_b.status_code == 200, respuesta_b.text
        assert respuesta_a.json()["id"] != respuesta_b.json()["id"]

        saldo_a = _get_account(client, auth_headers, cuenta_a["id"])
        saldo_b = _get_account(client, other_user["headers"], cuenta_b["id"])
        assert Decimal(str(saldo_a["balance"])) == Decimal("900.00")
        assert Decimal(str(saldo_b["balance"])) == Decimal("1950.00")

    @staticmethod
    def _hash_payload(payload: dict) -> str:
        """Replica exactamente el hash que calcula `crear_transaccion` (mismo
        `TransactionCreate.model_dump(mode="json")` + `sha256` + `sort_keys=True`)
        ANTES de resolver `account_id`/`category_id` — por eso el payload de este
        helper debe traer `account_id`/`category_id` explícitos, igual que el que se
        manda por HTTP."""
        modelo = schemas.TransactionCreate(**payload)
        return hashlib.sha256(json.dumps(modelo.model_dump(mode="json"), sort_keys=True).encode()).hexdigest()

    def test_replay_key_losing_race_with_different_payload_returns_409(
        self, client, db_session, test_user, make_account, make_category
    ):
        """T6 — QA-020 (B7): reproduce la carrera intercalando DENTRO del `commit`
        parcheado, mismo mecanismo que
        `test_race_condition_integrity_error_rolls_back_without_raising`
        (`tests/test_budget_recurrence.py`): la "otra" petición inserta y comitea de
        verdad su propia `IdempotencyKey` con la MISMA clave y OTRO hash antes de que
        la nuestra intente insertar la suya — nuestro `db.commit()` final choca contra
        el índice único `(user_id, key)` con un `IntegrityError` GENUINO.

        Falla antes del fix: la rama `except IntegrityError` de `crear_transaccion`
        devolvía la transacción de la clave ganadora SIN comparar el hash — un
        payload distinto se colaba en silencio en vez de responder 409."""
        headers = test_user["headers"]
        cuenta = make_account(headers, balance="1000.00")
        categoria = make_category(headers, name="Comida", type="expense")
        key = "carrera-payload-distinto"
        payload = {
            "amount": "100.00",
            "type": "expense",
            "description": "compra con posible carrera",
            "account_id": cuenta["id"],
            "category_id": categoria["id"],
        }

        commit_real = db_session.commit
        llamadas = {"n": 0}

        def commit_que_pierde_la_carrera():
            llamadas["n"] += 1
            if llamadas["n"] == 1:
                lote = list(db_session.new)
                for fila in lote:
                    db_session.expunge(fila)
                ganadora_tx = models.Transaction(
                    amount=Decimal("999.00"),
                    type="expense",
                    currency="COP",
                    account_id=cuenta["id"],
                    category_id=categoria["id"],
                    user_id=test_user["id"],
                )
                db_session.add(ganadora_tx)
                db_session.flush()  # asigna ganadora_tx.id
                db_session.add(
                    models.IdempotencyKey(
                        user_id=test_user["id"],
                        key=key,
                        request_hash="hash-totalmente-distinto-de-otro-payload",
                        transaction_id=ganadora_tx.id,
                    )
                )
                commit_real()  # la ganadora queda durable
                db_session.add_all(lote)
                commit_real()  # nuestra propia clave choca contra el índice único
            commit_real()

        monkeypatch_target = db_session
        original_commit = monkeypatch_target.commit
        monkeypatch_target.commit = commit_que_pierde_la_carrera
        try:
            response = self._post(client, {**headers, "Idempotency-Key": key}, payload)
        finally:
            monkeypatch_target.commit = original_commit

        assert llamadas["n"] >= 1  # la rama SÍ se ejercitó
        assert response.status_code == 409, response.text
        assert "datos distintos" in response.json()["detail"]

    def test_replay_key_losing_race_with_original_already_deleted_returns_409(
        self, client, db_session, test_user, make_account, make_category
    ):
        """T6 — QA-020 (B7), la otra rama del mismo `except IntegrityError`: la clave
        ganadora tiene el MISMO hash que la nuestra (el mismo payload, dos clientes
        reintentando a la vez) pero su transacción original ya está soft-deleted para
        cuando resolvemos la carrera.

        Falla antes del fix: la rama vieja devolvía
        `db.query(...).first()` sin chequear `None` — un `500` de validación de
        respuesta (Pydantic no puede serializar `None` como `TransactionResponse`) en
        vez de un 409 de dominio legible."""
        headers = test_user["headers"]
        cuenta = make_account(headers, balance="1000.00")
        categoria = make_category(headers, name="Comida", type="expense")
        key = "carrera-original-ya-borrada"
        payload = {
            "amount": "100.00",
            "type": "expense",
            "description": "compra que se reintenta",
            "account_id": cuenta["id"],
            "category_id": categoria["id"],
        }
        hash_real = self._hash_payload(payload)

        commit_real = db_session.commit
        llamadas = {"n": 0}

        def commit_que_pierde_la_carrera():
            llamadas["n"] += 1
            if llamadas["n"] == 1:
                lote = list(db_session.new)
                for fila in lote:
                    db_session.expunge(fila)
                ganadora_tx = models.Transaction(
                    amount=Decimal("100.00"),
                    type="expense",
                    currency="COP",
                    account_id=cuenta["id"],
                    category_id=categoria["id"],
                    user_id=test_user["id"],
                    deleted_at=datetime.now(UTC),  # ya borrada para cuando la resolvemos
                )
                db_session.add(ganadora_tx)
                db_session.flush()
                db_session.add(
                    models.IdempotencyKey(
                        user_id=test_user["id"],
                        key=key,
                        request_hash=hash_real,  # MISMO payload — el hash sí coincide
                        transaction_id=ganadora_tx.id,
                    )
                )
                commit_real()
                db_session.add_all(lote)
                commit_real()
            commit_real()

        original_commit = db_session.commit
        db_session.commit = commit_que_pierde_la_carrera
        try:
            response = self._post(client, {**headers, "Idempotency-Key": key}, payload)
        finally:
            db_session.commit = original_commit

        assert llamadas["n"] >= 1
        assert response.status_code == 409, response.text
        assert "ya no existe" in response.json()["detail"]


class TestCapturaRapidaPorNombre:
    """Fase 16 §16.2 (Decisiones 16.2.1/16.2.2/16.2.4): `category` alternativo por nombre
    y `account_id` opcional en el MISMO endpoint de creación (y actualización)."""

    def _cuenta_por_defecto(self, client: TestClient, headers: dict) -> dict:
        """La cuenta única que el registro crea por defecto (Fase 8 §5)."""
        cuentas = client.get("/api/v1/accounts/", headers=headers).json()
        assert len(cuentas) == 1
        return cuentas[0]

    def test_category_name_resolves_case_and_accent_insensitive(
        self, client, auth_headers, make_account, make_category
    ):
        cuenta = make_account(auth_headers, balance="1000.00")
        categoria = make_category(auth_headers, name="Alimentación", type="expense")

        response = _create_transaction(
            client,
            auth_headers,
            amount="100.00",
            type="expense",
            account_id=cuenta["id"],
            category="alimentacion",  # sin acento y en minúsculas
        )
        assert response.status_code == 200, response.text
        # Se resolvió a la categoría "Alimentación" propia (id conocido).
        assert response.json()["category_id"] == categoria["id"]
        # La respuesta serializa bien pese a que `category` no es un atributo escalar
        # del ORM (regresión de la relación Transaction.category vs el campo nuevo).
        assert response.json()["category"] is None

    def test_update_with_category_name_resolves_case_insensitive(
        self, client, auth_headers, make_account, make_category
    ):
        """La resolución por nombre aplica TAMBIÉN en actualizar_transaccion (mismo body
        TransactionBase/TransactionCreate — XOR idéntico)."""
        cuenta = make_account(auth_headers, balance="1000.00")
        categoria_vieja = make_category(auth_headers, name="Comida", type="expense")
        categoria_nueva = make_category(auth_headers, name="Transporte", type="expense")

        creada = _create_transaction(
            client,
            auth_headers,
            amount="100.00",
            type="expense",
            account_id=cuenta["id"],
            category_id=categoria_vieja["id"],
        ).json()

        update_payload = {
            "amount": "100.00",
            "currency": "COP",
            "type": "expense",
            "description": "reclasificada por nombre",
            "account_id": cuenta["id"],
            "category": "TRANSPORTE",
        }
        update_response = client.put(f"/api/v1/transactions/{creada['id']}", json=update_payload, headers=auth_headers)
        assert update_response.status_code == 200, update_response.text
        assert update_response.json()["category_id"] == categoria_nueva["id"]

    def test_unknown_category_name_returns_404_with_valid_names_of_right_type(
        self, client, auth_headers, make_account, make_category
    ):
        cuenta = make_account(auth_headers, balance="1000.00")
        # Sin fuzzy match (Decisión 16.2.2): el 404 lista los nombres válidos del mismo
        # tipo. Las categorías de sistema no existen en tests (el lifespan no corre),
        # así que "válidas" son las propias del tipo pedido.
        make_category(auth_headers, name="Comida", type="expense")
        make_category(auth_headers, name="Salario", type="income")

        response = _create_transaction(
            client,
            auth_headers,
            amount="100.00",
            type="expense",
            account_id=cuenta["id"],
            category="Inexistente",
        )
        assert response.status_code == 404
        assert "Categoría 'Inexistente' no encontrada" in response.json()["detail"]
        assert "Válidas para expense" in response.json()["detail"]
        # Solo categorías del tipo correcto se ofrecen como alternativas.
        assert "Comida" in response.json()["detail"]
        assert "Salario" not in response.json()["detail"]

    def test_category_name_of_wrong_type_returns_404(self, client, auth_headers, make_account, make_category):
        """El filtro por `type` elimina la ambigüedad cruzada gasto/ingreso: una categoría
        de ingreso llamada igual que el nombre pedido (expense) NO matchea."""
        cuenta = make_account(auth_headers, balance="1000.00")
        make_category(auth_headers, name="Salario", type="income")

        response = _create_transaction(
            client,
            auth_headers,
            amount="100.00",
            type="expense",
            account_id=cuenta["id"],
            category="Salario",
        )
        assert response.status_code == 404

    def test_duplicate_own_categories_api_rechaza_400(self, client, auth_headers, make_account, make_category):
        """QA-028: la API rechaza crear dos categorías propias con el mismo nombre+tipo (400)."""
        make_account(auth_headers, balance="1000.00")
        make_category(auth_headers, name="Comida", type="expense")
        # Usamos client directo porque el fixture asertea 200
        respuesta = client.post(
            "/api/v1/categories/",
            json={"name": "Comida", "type": "expense"},
            headers=auth_headers,
        )
        assert respuesta.status_code == 400
        assert "Ya existe una categoría de tipo expense llamada 'Comida'" in respuesta.json()["detail"]

    def test_resolucion_por_nombre_con_duplicado_en_db_devuelve_409(
        self, client, auth_headers, make_account, db_session, test_user
    ):
        """Si de algún modo existen dos categorías propias con el mismo nombre+tipo en la DB
        (p.ej. insert directo, migración antigua, o antes de QA-028), el resolver por nombre
        devuelve 409 y no adivina (Decisión 16.2.2)."""
        cuenta = make_account(auth_headers, balance="1000.00")
        cat = models.Category(name="Comida", type="expense", user_id=test_user["id"])
        cat2 = models.Category(name="Comida", type="expense", user_id=test_user["id"])
        db_session.add_all([cat, cat2])
        db_session.commit()

        response = _create_transaction(
            client,
            auth_headers,
            amount="100.00",
            type="expense",
            account_id=cuenta["id"],
            category="comida",
        )
        assert response.status_code == 409
        assert "Usá category_id" in response.json()["detail"]

    def test_own_category_precedes_system_category(self, client, auth_headers, db_session, make_account, make_category):
        """Decisión 16.2.2: la categoría propia reemplaza/oculta la de sistema con el
        mismo nombre (no es un error de ambigüedad entre ambas)."""
        cuenta = make_account(auth_headers, balance="1000.00")
        # Categoría de sistema sembrada directo en la sesión (no hay ruta API para ellas).
        db_session.add(models.Category(name="Alimentación", type="expense", user_id=None))
        db_session.commit()
        propia = make_category(auth_headers, name="Alimentación", type="expense")

        response = _create_transaction(
            client,
            auth_headers,
            amount="100.00",
            type="expense",
            account_id=cuenta["id"],
            category="ALIMENTACIÓN",
        )
        assert response.status_code == 200, response.text
        assert response.json()["category_id"] == propia["id"]

    def test_account_id_omitted_resolves_to_single_account(self, client, test_user, make_category):
        """Decisión 16.2.4: sin account_id, se usa la única cuenta del usuario (la
        "Cuenta principal" que crea el registro)."""
        user = test_user
        categoria = make_category(user["headers"], name="Comida", type="expense")
        cuenta_por_defecto = self._cuenta_por_defecto(client, user["headers"])

        response = _create_transaction(
            client,
            user["headers"],
            amount="100.00",
            type="expense",
            category_id=categoria["id"],
            # sin account_id
        )
        assert response.status_code == 200, response.text
        assert response.json()["account_id"] == cuenta_por_defecto["id"]

        saldo = _get_account(client, user["headers"], cuenta_por_defecto["id"])
        assert Decimal(str(saldo["balance"])) == Decimal("-100.00")

    def test_account_id_omitted_with_multiple_accounts_returns_400(
        self, client, auth_headers, make_account, make_category
    ):
        make_account(auth_headers, balance="1000.00")  # la 2ª cuenta (la 1ª es la default)
        categoria = make_category(auth_headers, name="Comida", type="expense")

        response = _create_transaction(
            client,
            auth_headers,
            amount="100.00",
            type="expense",
            category_id=categoria["id"],
        )
        assert response.status_code == 400
        assert "Especificá account_id" in response.json()["detail"]

    def test_update_with_account_id_omitted_resolves_to_single_account(self, client, auth_headers, make_category):
        """Mismo fallback de cuenta única en actualizar_transaccion."""
        # Sin make_account: el usuario solo tiene la cuenta por defecto del registro.
        cuentas = client.get("/api/v1/accounts/", headers=auth_headers).json()
        assert len(cuentas) == 1
        cuenta = cuentas[0]
        categoria = make_category(auth_headers, name="Comida", type="expense")

        creada = _create_transaction(
            client,
            auth_headers,
            amount="100.00",
            type="expense",
            account_id=cuenta["id"],
            category_id=categoria["id"],
        ).json()

        update_payload = {
            "amount": "150.00",
            "currency": "COP",
            "type": "expense",
            "description": "solo monto, sin account_id",
            "category_id": categoria["id"],
        }
        update_response = client.put(f"/api/v1/transactions/{creada['id']}", json=update_payload, headers=auth_headers)
        assert update_response.status_code == 200, update_response.text
        assert update_response.json()["account_id"] == cuenta["id"]

    def test_xor_rejects_both_category_id_and_category_name(self, client, auth_headers, make_account, make_category):
        cuenta = make_account(auth_headers, balance="1000.00")
        categoria = make_category(auth_headers, name="Comida", type="expense")

        response = _create_transaction(
            client,
            auth_headers,
            amount="100.00",
            type="expense",
            account_id=cuenta["id"],
            category_id=categoria["id"],
            category="Comida",
        )
        assert response.status_code == 422

    def test_xor_rejects_neither_category_id_nor_category_name(self, client, auth_headers, make_account):
        cuenta = make_account(auth_headers, balance="1000.00")

        response = _create_transaction(
            client,
            auth_headers,
            amount="100.00",
            type="expense",
            account_id=cuenta["id"],
        )
        assert response.status_code == 422
        assert "Especificar exactamente uno" in response.text


class TestFechaSoloDiaFase34:
    """Fase 34 (B9): `date` como `YYYY-MM-DD` se convierte en la zona del usuario (Bogotá por
    defecto): día pasado → 12:00 locales (17:00Z); datetime completo → tal cual. Los casos de
    otras zonas (Tokyo/New York) los agrega el paso de tests de integración."""

    def _crear(self, client, headers, make_account, make_category, **extra):
        cuenta = make_account(headers, balance="1000.00")
        categoria = make_category(headers, name="Comida", type="expense")
        return _create_transaction(client, headers, account_id=cuenta["id"], category_id=categoria["id"], **extra)

    def test_solo_dia_pasado_se_guarda_a_las_12_locales(self, client, auth_headers, make_account, make_category):
        response = self._crear(client, auth_headers, make_account, make_category, date="2026-03-10")
        assert response.status_code == 200, response.text
        assert response.json()["date"].startswith("2026-03-10T17:00:00")

    def test_datetime_completo_se_guarda_tal_cual(self, client, auth_headers, make_account, make_category):
        response = self._crear(client, auth_headers, make_account, make_category, date="2026-03-10T00:00:00-05:00")
        assert response.status_code == 200, response.text
        assert response.json()["date"].startswith("2026-03-10T05:00:00")

    def test_solo_dia_de_hoy_conserva_la_hora_real(self, client, auth_headers, make_account, make_category):
        from zoneinfo import ZoneInfo

        hoy = datetime.now(ZoneInfo("America/Bogota")).date().isoformat()
        response = self._crear(client, auth_headers, make_account, make_category, date=hoy)
        assert response.status_code == 200, response.text
        guardada = datetime.fromisoformat(response.json()["date"]).replace(tzinfo=UTC)
        assert abs((datetime.now(UTC) - guardada).total_seconds()) < 60
