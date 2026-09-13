"""Tests del perfil de usuario: `PATCH /api/v1/users/me` con `monthly_income` (Fase 8 §1).

Primer test de `users.py` fuera del registro. `UserProfileUpdate` es un schema separado de
`PreferencesUpdate` por ser un dato financiero de dominio, no cosmético (Decisión 1.1).
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.models import models


class TestActualizarPerfil:
    def test_patch_me_monthly_income_persists_and_returns_in_get_me(self, client, register_and_login):
        user = register_and_login(email="perfil-ok@example.com")
        headers = user["headers"]

        response = client.patch("/api/v1/users/me", json={"monthly_income": "3500000.50"}, headers=headers)
        assert response.status_code == 200, response.text
        assert Decimal(str(response.json()["monthly_income"])) == Decimal("3500000.50")

        me = client.get("/api/v1/users/me", headers=headers)
        assert me.status_code == 200, me.text
        assert Decimal(str(me.json()["monthly_income"])) == Decimal("3500000.50")

    def test_get_me_returns_null_monthly_income_when_never_set(self, client, register_and_login):
        user = register_and_login(email="perfil-sin-ingreso@example.com")
        me = client.get("/api/v1/users/me", headers=user["headers"])
        assert me.status_code == 200, me.text
        assert me.json()["monthly_income"] is None

    def test_patch_me_negative_monthly_income_returns_422(self, client, register_and_login):
        user = register_and_login(email="perfil-negativo@example.com")
        response = client.patch("/api/v1/users/me", json={"monthly_income": "-100.00"}, headers=user["headers"])
        assert response.status_code == 422

    def test_patch_me_without_token_returns_401(self, client):
        response = client.patch("/api/v1/users/me", json={"monthly_income": "100.00"})
        assert response.status_code == 401


class TestHasTransactionHistory:
    """Fase 19 §19.1: `has_transaction_history` en GET /users/me.

    El umbral de "usuario recurrente" es 2 o más transacciones, no 1 (Decisión 19.1.1,
    resuelve la Decisión 10.1.4 de Fase 10). El campo es un atributo calculado solo en
    `obtener_usuario_actual` — no es una columna, y el `default=False` del schema es lo
    que se serializa en `crear_usuario`/`actualizar_perfil` (Decisión 19.1.3).
    """

    def _create_transaction(self, client, headers, account_id, category_id, **overrides) -> dict:
        payload = {
            "amount": "100.00",
            "type": "expense",
            "description": "tx para el historial",
            "account_id": account_id,
            "category_id": category_id,
        }
        payload.update(overrides)
        response = client.post("/api/v1/transactions/", json=payload, headers=headers)
        assert response.status_code == 200, response.text
        return response.json()

    def test_no_transactions_returns_false(self, client, register_and_login):
        user = register_and_login(email="historial-vacio@example.com")

        me = client.get("/api/v1/users/me", headers=user["headers"])
        assert me.status_code == 200, me.text
        assert me.json()["has_transaction_history"] is False

    def test_exactly_one_transaction_returns_false(self, client, register_and_login, make_account, make_category):
        user = register_and_login(email="historial-una-tx@example.com")
        headers = user["headers"]
        cuenta = make_account(headers, name="Cuenta historial", currency="COP", balance="1000.00")
        categoria = make_category(headers, name="Comida", type="expense")

        self._create_transaction(client, headers, cuenta["id"], categoria["id"])

        me = client.get("/api/v1/users/me", headers=headers)
        assert me.status_code == 200, me.text
        assert me.json()["has_transaction_history"] is False

    def test_two_transactions_returns_true(self, client, register_and_login, make_account, make_category):
        user = register_and_login(email="historial-dos-tx@example.com")
        headers = user["headers"]
        cuenta = make_account(headers, name="Cuenta historial", currency="COP", balance="1000.00")
        categoria = make_category(headers, name="Comida", type="expense")

        self._create_transaction(client, headers, cuenta["id"], categoria["id"])
        self._create_transaction(client, headers, cuenta["id"], categoria["id"])

        me = client.get("/api/v1/users/me", headers=headers)
        assert me.status_code == 200, me.text
        assert me.json()["has_transaction_history"] is True

    def test_has_transaction_history_uses_limit_not_count_semantics(
        self, client, register_and_login, make_account, make_category
    ):
        """50 transacciones → `true`. El nombre documenta la intención de la query
        (Decisión 19.1.2): es un `LIMIT 2` que solo pregunta "¿hay 2 o más?", no un
        `COUNT(*)` que recorra todas las filas para responder lo mismo."""
        user = register_and_login(email="historial-largo@example.com")
        headers = user["headers"]
        cuenta = make_account(headers, name="Cuenta historial", currency="COP", balance="1000.00")
        categoria = make_category(headers, name="Comida", type="expense")

        for i in range(50):
            self._create_transaction(client, headers, cuenta["id"], categoria["id"], description=f"tx {i}")

        me = client.get("/api/v1/users/me", headers=headers)
        assert me.status_code == 200, me.text
        assert me.json()["has_transaction_history"] is True


class TestEliminarCuenta:
    """Fase 21 §21.2 — `DELETE /api/v1/users/me`: baja de cuenta self-service (Decisión A4).

    Hard delete físico compartido con el script de limpieza (`delete_user_cascade`). Cubre
    los 5 casos de la spec: contraseña correcta/incorrecta, cascada completa sobre todas las
    tablas hijas, re-registro con el mismo email (cierra el Hallazgo 2) y guard sin token.
    """

    def test_delete_me_with_correct_password_returns_204_and_token_stops_working(self, client, register_and_login):
        user = register_and_login(email="baja-correcta@example.com")

        response = client.request(
            "DELETE",
            "/api/v1/users/me",
            json={"password": user["password"]},
            headers=user["headers"],
        )
        assert response.status_code == 204, response.text

        # El usuario ya no existe → get_current_user lanza 401 con el mismo token (spec
        # §21.2, security.py:120-122).
        me = client.get("/api/v1/users/me", headers=user["headers"])
        assert me.status_code == 401

    def test_delete_me_with_wrong_password_returns_403_and_keeps_the_account(self, client, register_and_login):
        user = register_and_login(email="baja-incorrecta@example.com")

        response = client.request(
            "DELETE",
            "/api/v1/users/me",
            json={"password": "ClaveErronea99"},
            headers=user["headers"],
        )
        assert response.status_code == 403, response.text

        me = client.get("/api/v1/users/me", headers=user["headers"])
        assert me.status_code == 200, me.text

    def test_delete_me_removes_every_child_row_across_all_tables(
        self, client, register_and_login, make_account, make_category, db_session
    ):
        """Usuario con datos en TODAS las tablas que referencian users.id (las 12 del
        Hallazgo 3) — DELETE no lanza IntegrityError y ninguna fila hija sobrevive."""
        user = register_and_login(email="baja-cascada@example.com")
        uid = user["id"]
        headers = user["headers"]
        hoy = datetime.now(UTC)

        cuenta = make_account(headers, name="Cuenta cascada")
        categoria_propia = make_category(headers, name="Cascada", type="expense")

        tx = client.post(
            "/api/v1/transactions/",
            json={
                "amount": "100.00",
                "type": "expense",
                "description": "tx para la cascada",
                "account_id": cuenta["id"],
                "category_id": categoria_propia["id"],
            },
            headers=headers,
        )
        assert tx.status_code == 200, tx.text
        tx_id = tx.json()["id"]

        budget = client.post(
            "/api/v1/budgets/",
            json={
                "amount_limit": "200000.00",
                "currency": "COP",
                "month": hoy.month,
                "year": hoy.year,
                "category_id": categoria_propia["id"],
                "is_recurring": False,
            },
            headers=headers,
        )
        assert budget.status_code == 200, budget.text

        api_key = client.post("/api/v1/api-keys/", json={"name": "cascada"}, headers=headers)
        assert api_key.status_code == 200, api_key.text

        hidden = client.post(f"/api/v1/categories/{categoria_propia['id']}/hide", headers=headers)
        assert hidden.status_code == 204, hidden.text

        # Tablas técnicas sin endpoint de creación en este flujo: insert directo en la
        # sesión de test (mismo patrón que conftest.py) y commit para que la cascada del
        # endpoint las encuentre en la base (el session de la app no autoflushea).
        expires = hoy + timedelta(days=30)
        db_session.add(models.RefreshToken(token_hash="abc", user_id=uid, expires_at=expires))
        db_session.add(models.PasswordResetToken(token_hash="def", user_id=uid, expires_at=expires))
        db_session.add(models.EmailVerificationToken(token_hash="ghi", user_id=uid, expires_at=expires))
        db_session.add(models.IdempotencyKey(user_id=uid, key="k-cascada", request_hash="h" * 64, transaction_id=tx_id))
        db_session.add(models.Notification(user_id=uid, type="budget_threshold_80", title="T", body="B"))
        db_session.add(
            models.PushSubscription(
                user_id=uid,
                endpoint=f"https://push.example.com/{uid}",
                p256dh_key="clave",
                auth_key="auth",
            )
        )
        db_session.commit()

        response = client.request("DELETE", "/api/v1/users/me", json={"password": user["password"]}, headers=headers)
        assert response.status_code == 204, response.text

        tablas_con_user_id = [
            models.Account,
            models.Category,
            models.Transaction,
            models.Budget,
            models.HiddenCategory,
            models.RefreshToken,
            models.PasswordResetToken,
            models.EmailVerificationToken,
            models.IdempotencyKey,
            models.Notification,
            models.PushSubscription,
            models.ApiKey,
        ]
        for tabla in tablas_con_user_id:
            sobrevivientes = db_session.query(tabla).filter(tabla.user_id == uid).count()
            assert sobrevivientes == 0, f"Quedaron {sobrevivientes} filas en {tabla.__tablename__}"
        assert db_session.query(models.User).filter(models.User.id == uid).count() == 0

    def test_same_email_can_register_again_after_deletion(self, client, register_and_login):
        """Cierra el Hallazgo 2 de la spec: el hard delete libera el email — re-registrarse
        con el mismo email tiene éxito (antes habría colisionado contra el índice único).

        SQLite con INTEGER PRIMARY KEY sin AUTOINCREMENT reutiliza el id=1 tras un DELETE
        de la tabla vacía (max+1 = 1), así que no se verifica unicidad de id — solo que el
        segundo registro y login funcionan sin IntegrityError y GET /me responde 200."""
        email = "baja-re-registro@example.com"
        user = register_and_login(email=email)

        response = client.request(
            "DELETE", "/api/v1/users/me", json={"password": user["password"]}, headers=user["headers"]
        )
        assert response.status_code == 204, response.text

        nuevo = register_and_login(email=email)
        me = client.get("/api/v1/users/me", headers=nuevo["headers"])
        assert me.status_code == 200, me.text
        assert me.json()["email"] == email

    def test_delete_me_without_token_returns_401(self, client):
        response = client.request("DELETE", "/api/v1/users/me", json={"password": "Cualquiera99"})
        assert response.status_code == 401
