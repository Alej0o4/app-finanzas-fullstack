"""Tests de preferencias con cascada a la cuenta por defecto (Fase 22 §22.1, Decisión A5).

`PATCH /api/v1/users/me/preferences` ganó un campo de instrucción
`apply_to_default_account`: cuando viene en `true` junto con `preferred_currency`, el
handler también actualiza la moneda de la cuenta por defecto que crea el registro
(`inicializar_datos_usuario_nuevo`) — pero solo si la cuenta sigue "virgen" (mismo
nombre `"Cuenta principal"`, `balance == 0`, sin transacciones asociadas), para no tocar
jamás una cuenta que el usuario ya haya usado entre el registro y este paso (Decisión A2).

El selector de Settings (Fase 21) llama este mismo endpoint SIN el campo, así que por
default (`False`) su comportamiento no cambia — el test de "regresión Settings" lo cubre
explícitamente.
"""

from decimal import Decimal

from fastapi.testclient import TestClient

from app.models import models


class TestApplyToDefaultAccount:
    """Los 6 casos de la spec §22.1 (Backend, Testing), todos contra un usuario recién
    registrado cuya cuenta por defecto arranca virgen."""

    @staticmethod
    def _get_default_account(client: TestClient, headers: dict) -> dict:
        response = client.get("/api/v1/accounts/", headers=headers)
        assert response.status_code == 200, response.text
        for cuenta in response.json():
            if cuenta["name"] == "Cuenta principal":
                return cuenta
        raise AssertionError("No existe la cuenta por defecto 'Cuenta principal'")

    def test_cascade_changes_default_account_currency_when_virgin(self, client, register_and_login):
        """Caso feliz de la cascada: cuenta virgen + los dos campos en el body."""
        user = register_and_login(email="cascada-virgen@example.com")
        headers = user["headers"]

        response = client.patch(
            "/api/v1/users/me/preferences",
            json={"preferred_currency": "USD", "apply_to_default_account": True},
            headers=headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["preferred_currency"] == "USD"

        principal = self._get_default_account(client, headers)
        assert principal["currency"] == "USD"

    def test_cascade_skipped_when_default_account_was_renamed(self, client, register_and_login):
        """Guard de nombre: renombrar la cuenta por defecto la saca del criterio
        `name == "Cuenta principal"` — la moneda no se toca y el PATCH igual responde 200
        con `preferred_currency` actualizado (Decisión A2: el usuario la corrige en
        Cuentas, no se informa error)."""
        user = register_and_login(email="cascada-renombrada@example.com")
        headers = user["headers"]
        cuenta = self._get_default_account(client, headers)

        renombrada = client.put(
            f"/api/v1/accounts/{cuenta['id']}",
            json={"name": "Cuenta guardado", "type": "debit"},
            headers=headers,
        )
        assert renombrada.status_code == 200, renombrada.text

        response = client.patch(
            "/api/v1/users/me/preferences",
            json={"preferred_currency": "USD", "apply_to_default_account": True},
            headers=headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["preferred_currency"] == "USD"

        me = client.get("/api/v1/users/me", headers=headers)
        assert me.status_code == 200, me.text
        assert me.json()["preferred_currency"] == "USD"

        cuentas = client.get("/api/v1/accounts/", headers=headers).json()
        assert len(cuentas) == 1
        assert cuentas[0]["name"] == "Cuenta guardado"
        assert cuentas[0]["currency"] == "COP"

    def test_cascade_skipped_when_default_account_has_transactions(self, client, register_and_login, make_category):
        """Guard de transacciones: una transacción asociada (aunque la cuenta siga con el
        nombre original) bloquea la cascada."""
        user = register_and_login(email="cascada-con-tx@example.com")
        headers = user["headers"]
        cuenta = self._get_default_account(client, headers)
        categoria = make_category(headers, name="Gasto cascada", type="expense")

        tx = client.post(
            "/api/v1/transactions/",
            json={
                "amount": "100.00",
                "type": "expense",
                "description": "transacción en la cuenta por defecto",
                "account_id": cuenta["id"],
                "category_id": categoria["id"],
            },
            headers=headers,
        )
        assert tx.status_code == 200, tx.text

        response = client.patch(
            "/api/v1/users/me/preferences",
            json={"preferred_currency": "USD", "apply_to_default_account": True},
            headers=headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["preferred_currency"] == "USD"

        principal = self._get_default_account(client, headers)
        assert principal["currency"] == "COP"

    def test_cascade_skipped_when_default_account_has_nonzero_balance(self, client, register_and_login, db_session):
        """Guard de `balance == 0`: con saldo distinto de cero (y sin transacciones), la
        cuenta por defecto no se toca aunque conserve su nombre original.

        El ejemplo de la spec (crear un gasto y borrarlo) NO deja `balance != 0` contra el
        código real: `eliminar_transaccion` revierte el impacto contable (el saldo vuelve
        a 0) y el filtro global `_filtrar_borrados_logicos` (database.py) oculta la fila
        soft-deleted del guard — una cuenta usada y limpiada por la API vuelve a ser
        "virgen" a los ojos de la cascada. Para aislar la condición de saldo sin
        transacciones de por medio, se ajusta el balance directo en la sesión de test
        (mismo precedente de manipulación directa que test_users.py)."""
        user = register_and_login(email="cascada-balance-roto@example.com")
        headers = user["headers"]
        cuenta = self._get_default_account(client, headers)

        cuenta_orm = db_session.get(models.Account, cuenta["id"])
        cuenta_orm.balance = Decimal("500.00")
        db_session.commit()

        response = client.patch(
            "/api/v1/users/me/preferences",
            json={"preferred_currency": "USD", "apply_to_default_account": True},
            headers=headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["preferred_currency"] == "USD"

        principal = self._get_default_account(client, headers)
        assert principal["currency"] == "COP"

    def test_default_account_never_changes_without_apply_flag(self, client, register_and_login):
        """Regresión explícita del caso Settings: sin `apply_to_default_account` (o en
        `false`), aunque la cuenta cumpla el guard, la cascada nunca se dispara."""
        user = register_and_login(email="cascada-settings@example.com")
        headers = user["headers"]

        response = client.patch(
            "/api/v1/users/me/preferences",
            json={"preferred_currency": "USD"},
            headers=headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["preferred_currency"] == "USD"

        principal = self._get_default_account(client, headers)
        assert principal["currency"] == "COP"

    def test_apply_flag_without_preferred_currency_is_noop(self, client, register_and_login):
        """`apply_to_default_account` sin `preferred_currency`: no revienta ni hace nada
        (el `if prefs.preferred_currency` de la Decisión 22.1.2 lo cubre)."""
        user = register_and_login(email="cascada-noop@example.com")
        headers = user["headers"]

        response = client.patch(
            "/api/v1/users/me/preferences",
            json={"apply_to_default_account": True},
            headers=headers,
        )
        assert response.status_code == 200, response.text

        principal = self._get_default_account(client, headers)
        assert principal["currency"] == "COP"
