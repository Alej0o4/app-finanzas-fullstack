"""Tests de autenticación y ciclo de vida de cuenta (Fase 7, §4.2 del spec).

Cubre: registro, login, refresh, logout, rate limiting, `get_current_user`, y — dado que ya
están implementados — password reset, verificación de email, el TTL de 15 min del access
token (§2.1/§2.2/§2.5) y el login con Google (Fase 20 §20.3).
"""

import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from freezegun import freeze_time
from jose import jwt

from app.core import security
from app.models import models


def _extract_token_from_email(html_body: str) -> str:
    match = re.search(r"token=([^\"&\s]+)", html_body)
    assert match, f"No se encontró un token en el cuerpo del email: {html_body!r}"
    return match.group(1)


# --- Registro ---------------------------------------------------------------


class TestRegistro:
    def test_duplicate_email_returns_400(self, client, register_and_login):
        user = register_and_login(email="duplicado@example.com")
        response = client.post(
            "/api/v1/users/",
            json={"email": user["email"], "full_name": "Otro Nombre", "password": "OtraClave10"},
        )
        assert response.status_code == 400

    def test_weak_password_all_digits_returns_422(self, client):
        response = client.post(
            "/api/v1/users/",
            json={"email": "debil1@example.com", "full_name": "Alguien", "password": "1234567890"},
        )
        assert response.status_code == 422

    def test_weak_password_all_letters_returns_422(self, client):
        response = client.post(
            "/api/v1/users/",
            json={"email": "debil2@example.com", "full_name": "Alguien", "password": "sololetras"},
        )
        assert response.status_code == 422

    def test_common_password_returns_422(self, client):
        response = client.post(
            "/api/v1/users/",
            json={"email": "debil3@example.com", "full_name": "Alguien", "password": "password123"},
        )
        assert response.status_code == 422

    def test_valid_password_is_accepted(self, client):
        response = client.post(
            "/api/v1/users/",
            json={"email": "valida@example.com", "full_name": "Alguien", "password": "Contrasena10"},
        )
        assert response.status_code == 200


# --- Login --------------------------------------------------------------------


class TestLogin:
    def test_correct_credentials_return_access_and_refresh_tokens(self, client, register_and_login):
        user = register_and_login(email="login-ok@example.com", password="Contrasena10")
        response = client.post(
            "/api/v1/auth/login",
            data={"username": user["email"], "password": user["password"]},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["access_token"]
        assert body["refresh_token"]
        assert body["token_type"] == "bearer"

    def test_incorrect_password_returns_403(self, client, register_and_login):
        user = register_and_login(email="login-mal@example.com")
        response = client.post(
            "/api/v1/auth/login",
            data={"username": user["email"], "password": "ClaveIncorrecta10"},
        )
        # Así está hoy en auth.py:24-27 — 403, no 401. Documentado, no "corregido" en el test.
        assert response.status_code == 403

    def test_nonexistent_email_returns_403(self, client):
        response = client.post(
            "/api/v1/auth/login",
            data={"username": "no-existe@example.com", "password": "Contrasena10"},
        )
        assert response.status_code == 403

    def test_sixth_login_request_in_a_minute_returns_429(self, client, register_and_login):
        # `register_and_login` ya hace un login (1/5). Cuatro más completan el límite de
        # 5/minute; el sexto debe rebotar.
        user = register_and_login(email="rate-limit@example.com", password="Contrasena10")
        credentials = {"username": user["email"], "password": user["password"]}

        for _ in range(4):
            response = client.post("/api/v1/auth/login", data=credentials)
            assert response.status_code == 200

        sixth_response = client.post("/api/v1/auth/login", data=credentials)
        assert sixth_response.status_code == 429


# --- Refresh --------------------------------------------------------------------


class TestRefresh:
    def test_refresh_rotates_token(self, client, register_and_login, db_session):
        user = register_and_login(email="refresh-ok@example.com")
        original_refresh = user["refresh_token"]

        response = client.post("/api/v1/auth/refresh", json={"refresh_token": original_refresh})
        assert response.status_code == 200, response.text
        new_tokens = response.json()
        assert new_tokens["refresh_token"] != original_refresh

        stored_old = (
            db_session.query(models.RefreshToken)
            .filter(models.RefreshToken.token_hash == security.hash_token(original_refresh))
            .first()
        )
        assert stored_old is not None
        assert stored_old.revoked_at is not None

    def test_used_refresh_token_cannot_be_reused(self, client, register_and_login):
        user = register_and_login(email="refresh-reuso@example.com")
        original_refresh = user["refresh_token"]

        first = client.post("/api/v1/auth/refresh", json={"refresh_token": original_refresh})
        assert first.status_code == 200

        second = client.post("/api/v1/auth/refresh", json={"refresh_token": original_refresh})
        assert second.status_code == 401

    def test_invalid_refresh_token_returns_401(self, client):
        response = client.post("/api/v1/auth/refresh", json={"refresh_token": "token-inventado"})
        assert response.status_code == 401


# --- Logout --------------------------------------------------------------------


class TestLogout:
    def test_logout_revokes_refresh_token(self, client, register_and_login):
        user = register_and_login(email="logout-ok@example.com")

        logout_response = client.post("/api/v1/auth/logout", json={"refresh_token": user["refresh_token"]})
        assert logout_response.status_code == 200

        refresh_response = client.post("/api/v1/auth/refresh", json={"refresh_token": user["refresh_token"]})
        assert refresh_response.status_code == 401

    def test_logout_with_already_invalid_token_is_a_silent_no_op(self, client):
        # auth.py:105-107 — si `stored` es None, no hace nada y responde 200 igual.
        # Documentado como comportamiento actual, no un bug a corregir en Fase 7.
        response = client.post("/api/v1/auth/logout", json={"refresh_token": "esto-nunca-existió"})
        assert response.status_code == 200
        assert response.json()["estado"] == "OK"


# --- get_current_user ------------------------------------------------------------


class TestGetCurrentUser:
    def test_rejects_token_with_invalid_signature(self, client, register_and_login):
        user = register_and_login(email="firma-invalida@example.com")
        tampered = user["access_token"][:-4] + ("aaaa" if not user["access_token"].endswith("aaaa") else "bbbb")

        response = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {tampered}"})
        assert response.status_code == 401

    def test_rejects_expired_token(self, client, register_and_login):
        user = register_and_login(email="expirado@example.com")
        expired_token = security.create_access_token(data={"sub": str(user["id"])}, expires_delta=timedelta(minutes=-1))

        response = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {expired_token}"})
        assert response.status_code == 401

    def test_rejects_token_with_nonexistent_user_sub(self, client):
        token = security.create_access_token(data={"sub": "999999"})
        response = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401

    def test_access_token_actually_expires_after_15_minutes(self, client, register_and_login):
        user = register_and_login(email="ttl@example.com")
        headers = {"Authorization": f"Bearer {user['access_token']}"}

        now = datetime.now(UTC)
        with freeze_time(now + timedelta(minutes=14, seconds=30)):
            still_valid = client.get("/api/v1/users/me", headers=headers)
        assert still_valid.status_code == 200

        with freeze_time(now + timedelta(minutes=16)):
            expired = client.get("/api/v1/users/me", headers=headers)
        assert expired.status_code == 401

        # Confirma también la constante en sí, no solo el comportamiento observado end-to-end.
        assert security.ACCESS_TOKEN_EXPIRE_MINUTES == 15


# --- Password reset ---------------------------------------------------------------


class TestPasswordReset:
    def test_request_does_not_reveal_whether_email_exists(self, client, register_and_login, captured_emails):
        user = register_and_login(email="reset-existe@example.com")
        captured_emails.clear()  # descarta el email de verificación disparado por el registro

        registered_response = client.post("/api/v1/auth/password-reset/request", json={"email": user["email"]})
        unregistered_response = client.post(
            "/api/v1/auth/password-reset/request", json={"email": "no-registrado@example.com"}
        )

        assert registered_response.status_code == 200
        assert unregistered_response.status_code == 200
        assert registered_response.json()["mensaje"] == unregistered_response.json()["mensaje"]
        # Solo el email registrado dispara un envío real.
        assert len(captured_emails) == 1
        assert captured_emails[0]["to"] == user["email"]

    def test_confirm_with_valid_token_changes_password_and_revokes_refresh_tokens(
        self, client, register_and_login, captured_emails
    ):
        user = register_and_login(email="reset-confirm@example.com", password="Contrasena10")

        client.post("/api/v1/auth/password-reset/request", json={"email": user["email"]})
        raw_token = _extract_token_from_email(captured_emails[-1]["html_body"])

        confirm_response = client.post(
            "/api/v1/auth/password-reset/confirm",
            json={"token": raw_token, "new_password": "NuevaClave10"},
        )
        assert confirm_response.status_code == 200, confirm_response.text

        # La contraseña vieja ya no sirve, la nueva sí.
        old_login = client.post("/api/v1/auth/login", data={"username": user["email"], "password": user["password"]})
        assert old_login.status_code == 403

        new_login = client.post("/api/v1/auth/login", data={"username": user["email"], "password": "NuevaClave10"})
        assert new_login.status_code == 200

        # El refresh token emitido antes del reset queda revocado.
        refresh_after_reset = client.post("/api/v1/auth/refresh", json={"refresh_token": user["refresh_token"]})
        assert refresh_after_reset.status_code == 401

    def test_confirm_with_invalid_token_returns_400(self, client):
        response = client.post(
            "/api/v1/auth/password-reset/confirm",
            json={"token": "token-que-no-existe", "new_password": "NuevaClave10"},
        )
        assert response.status_code == 400

    def test_confirm_with_expired_token_returns_400(self, client, register_and_login, db_session):
        user = register_and_login(email="reset-expirado@example.com")
        raw_token = security.generate_refresh_token()
        db_session.add(
            models.PasswordResetToken(
                token_hash=security.hash_token(raw_token),
                user_id=user["id"],
                expires_at=datetime.now(UTC) - timedelta(minutes=1),
            )
        )
        db_session.commit()

        response = client.post(
            "/api/v1/auth/password-reset/confirm",
            json={"token": raw_token, "new_password": "NuevaClave10"},
        )
        assert response.status_code == 400

    def test_confirm_with_already_used_token_returns_400(self, client, register_and_login, captured_emails):
        user = register_and_login(email="reset-reusado@example.com")
        client.post("/api/v1/auth/password-reset/request", json={"email": user["email"]})
        raw_token = _extract_token_from_email(captured_emails[-1]["html_body"])

        first = client.post(
            "/api/v1/auth/password-reset/confirm",
            json={"token": raw_token, "new_password": "NuevaClave10"},
        )
        assert first.status_code == 200

        second = client.post(
            "/api/v1/auth/password-reset/confirm",
            json={"token": raw_token, "new_password": "OtraClaveMas10"},
        )
        assert second.status_code == 400

    def test_confirm_rejects_weak_new_password(self, client, register_and_login, captured_emails):
        user = register_and_login(email="reset-debil@example.com")
        client.post("/api/v1/auth/password-reset/request", json={"email": user["email"]})
        raw_token = _extract_token_from_email(captured_emails[-1]["html_body"])

        response = client.post(
            "/api/v1/auth/password-reset/confirm",
            json={"token": raw_token, "new_password": "12345678900"},
        )
        assert response.status_code == 422


# --- Verificación de email ---------------------------------------------------------


class TestEmailVerification:
    def test_registration_sends_a_verification_email(self, client, captured_emails):
        response = client.post(
            "/api/v1/users/",
            json={"email": "verificar@example.com", "full_name": "Alguien", "password": "Contrasena10"},
        )
        assert response.status_code == 200
        assert len(captured_emails) == 1
        assert captured_emails[0]["to"] == "verificar@example.com"

    def test_valid_token_marks_email_verified(self, client, captured_emails):
        client.post(
            "/api/v1/users/",
            json={"email": "verificar-ok@example.com", "full_name": "Alguien", "password": "Contrasena10"},
        )
        raw_token = _extract_token_from_email(captured_emails[-1]["html_body"])

        response = client.get("/api/v1/auth/verify-email", params={"token": raw_token})
        assert response.status_code == 200

        login = client.post(
            "/api/v1/auth/login", data={"username": "verificar-ok@example.com", "password": "Contrasena10"}
        )
        me_response = client.get(
            "/api/v1/users/me", headers={"Authorization": f"Bearer {login.json()['access_token']}"}
        )
        # UserResponse no expone email_verified hoy — se confirma indirectamente vía el 200
        # del endpoint de verificación; el chequeo directo del flag se hace vía sesión de DB
        # en el test de abajo.
        assert me_response.status_code == 200

    def test_invalid_token_does_not_verify(self, client):
        response = client.get("/api/v1/auth/verify-email", params={"token": "token-inventado"})
        assert response.status_code == 400

    def test_expired_token_does_not_verify(self, client, captured_emails, db_session):
        client.post(
            "/api/v1/users/",
            json={"email": "verificar-expirado@example.com", "full_name": "Alguien", "password": "Contrasena10"},
        )
        user = db_session.query(models.User).filter(models.User.email == "verificar-expirado@example.com").first()

        raw_token = security.generate_refresh_token()
        db_session.add(
            models.EmailVerificationToken(
                token_hash=security.hash_token(raw_token),
                user_id=user.id,
                expires_at=datetime.now(UTC) - timedelta(hours=1),
            )
        )
        db_session.commit()

        response = client.get("/api/v1/auth/verify-email", params={"token": raw_token})
        assert response.status_code == 400

        db_session.refresh(user)
        assert user.email_verified is False

    def test_login_before_verifying_email_returns_403(self, client):
        # No usa `register_and_login`: esa factory marca email_verified=True a propósito
        # para no obligar a cada otro test a pasar por el flujo real de verificación.
        client.post(
            "/api/v1/users/",
            json={"email": "sin-verificar@example.com", "full_name": "Alguien", "password": "Contrasena10"},
        )
        response = client.post(
            "/api/v1/auth/login",
            data={"username": "sin-verificar@example.com", "password": "Contrasena10"},
        )
        assert response.status_code == 403
        assert response.json()["detail"]["code"] == "EMAIL_NOT_VERIFIED"

    def test_login_after_verifying_email_succeeds(self, client, captured_emails):
        client.post(
            "/api/v1/users/",
            json={"email": "verificado-login@example.com", "full_name": "Alguien", "password": "Contrasena10"},
        )
        raw_token = _extract_token_from_email(captured_emails[-1]["html_body"])
        client.get("/api/v1/auth/verify-email", params={"token": raw_token})

        response = client.post(
            "/api/v1/auth/login",
            data={"username": "verificado-login@example.com", "password": "Contrasena10"},
        )
        assert response.status_code == 200

    def test_resend_verification_sends_new_token_for_unverified_user(self, client, captured_emails):
        client.post(
            "/api/v1/users/",
            json={"email": "reenviar@example.com", "full_name": "Alguien", "password": "Contrasena10"},
        )
        assert len(captured_emails) == 1

        response = client.post("/api/v1/auth/resend-verification", json={"email": "reenviar@example.com"})
        assert response.status_code == 200
        assert len(captured_emails) == 2

        raw_token = _extract_token_from_email(captured_emails[-1]["html_body"])
        client.get("/api/v1/auth/verify-email", params={"token": raw_token})
        login = client.post("/api/v1/auth/login", data={"username": "reenviar@example.com", "password": "Contrasena10"})
        assert login.status_code == 200

    def test_resend_verification_does_not_reveal_nonexistent_email(self, client, captured_emails):
        response = client.post("/api/v1/auth/resend-verification", json={"email": "no-existe@example.com"})
        assert response.status_code == 200
        assert len(captured_emails) == 0

    def test_resend_verification_is_noop_for_already_verified_user(self, client, register_and_login, captured_emails):
        user = register_and_login(email="ya-verificado@example.com")
        emails_before = len(captured_emails)  # el registro ya mandó 1 (usuario luego marcado verificado por la fixture)
        response = client.post("/api/v1/auth/resend-verification", json={"email": user["email"]})
        assert response.status_code == 200
        assert len(captured_emails) == emails_before


# --- Cuenta por defecto al registrarse (Fase 8 §5) -------------------------------


class TestCuentaPorDefecto:
    def test_registration_creates_default_debit_account(self, client, register_and_login):
        user = register_and_login(email="cuenta-default@example.com")

        response = client.get("/api/v1/accounts/", headers=user["headers"])
        assert response.status_code == 200, response.text
        cuentas = response.json()

        assert len(cuentas) == 1
        cuenta_principal = cuentas[0]
        assert cuenta_principal["name"] == "Cuenta principal"
        assert cuenta_principal["type"] == "debit"
        assert Decimal(str(cuenta_principal["balance"])) == Decimal("0.00")
        # UserCreate no pide moneda; se hereda de preferred_currency (default COP)
        assert cuenta_principal["currency"] == "COP"
        assert cuenta_principal["highlighted"] is True

    def test_transaction_can_be_created_against_default_account_immediately(
        self, client, register_and_login, make_category
    ):
        """El síntoma exacto del bug original: un usuario nuevo con 0 cuentas no podía
        transaccionar (QuickTransactionModal fallaba en silencio)."""
        user = register_and_login(email="tx-inmediata@example.com")
        cuenta_efectivo = next(
            c
            for c in client.get("/api/v1/accounts/", headers=user["headers"]).json()
            if c["name"] == "Cuenta principal"
        )
        categoria = make_category(user["headers"], name="Salario", type="income")

        response = client.post(
            "/api/v1/transactions/",
            json={
                "amount": "50000.00",
                "type": "income",
                "account_id": cuenta_efectivo["id"],
                "category_id": categoria["id"],
            },
            headers=user["headers"],
        )
        assert response.status_code == 200, response.text

        saldo = client.get(f"/api/v1/accounts/{cuenta_efectivo['id']}", headers=user["headers"]).json()
        assert Decimal(str(saldo["balance"])) == Decimal("50000.00")


# --- Login con Google (Fase 20 §20.3) -------------------------------------------


class TestLoginGoogle:
    """Login/registro con ID token de Google (Decisión 20.3.5).

    La única pieza que se mockea es la llamada de red a Google
    (`verify_oauth2_token`) vía monkeypatch — misma política de la suite offline
    contra SQLite en memoria. Todo lo demás (creación de usuario, auto-link,
    emisión de tokens, rate limiting) se prueba contra el flujo real.
    """

    GOOGLE_CLIENT_ID = "test-client-id.apps.googleusercontent.com"

    def _login_google(self, client, monkeypatch, *, email="nueva@example.com", email_verified=True):
        monkeypatch.setattr(security, "GOOGLE_CLIENT_ID", self.GOOGLE_CLIENT_ID)
        claims = {
            "email": email,
            "email_verified": email_verified,
            "sub": f"google-sub:{email}",
            "name": "Persona de Google",
        }
        monkeypatch.setattr(
            "app.api.auth.google_id_token.verify_oauth2_token",
            lambda token, request, audience: claims,
        )
        return client.post("/api/v1/auth/google", json={"id_token": "idtoken-falso"})

    def test_new_email_creates_verified_user_with_default_account(self, client, monkeypatch, db_session):
        response = self._login_google(client, monkeypatch, email="google-nueva@example.com")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["access_token"]
        assert body["refresh_token"]
        assert body["token_type"] == "bearer"

        user = db_session.query(models.User).filter(models.User.email == "google-nueva@example.com").first()
        assert user is not None
        assert user.email_verified is True  # Google ya verificó el correo (Decisión P4)
        assert user.password_hash is None  # cuenta solo-Google: no hay hash que fabricar
        assert user.google_id == "google-sub:google-nueva@example.com"
        assert user.full_name == "Persona de Google"

        # Regresión Hallazgo 4/Decisión 20.3.3: el helper compartido crea la cuenta por
        # defecto — exactamente 1, no 0 (bug de "usuario nuevo con 0 cuentas") ni 2.
        cuentas = client.get("/api/v1/accounts/", headers={"Authorization": f"Bearer {body['access_token']}"})
        assert cuentas.status_code == 200, cuentas.text
        assert len(cuentas.json()) == 1
        assert cuentas.json()[0]["name"] == "Cuenta principal"

    def test_existing_unverified_password_account_is_autolinked(self, client, monkeypatch, db_session):
        # Cuenta con contraseña y email sin verificar (estado de un registro real).
        register_response = client.post(
            "/api/v1/users/",
            json={"email": "auto-link@example.com", "full_name": "Contraseña", "password": "Contrasena10"},
        )
        assert register_response.status_code == 200, register_response.text

        user = db_session.query(models.User).filter(models.User.email == "auto-link@example.com").first()
        assert user.email_verified is False
        user_id_before = user.id
        users_before = db_session.query(models.User).count()

        response = self._login_google(client, monkeypatch, email="auto-link@example.com")
        assert response.status_code == 200, response.text

        db_session.refresh(user)
        # P3: no se creó un segundo usuario — se vinculó el existente.
        assert user.id == user_id_before
        assert db_session.query(models.User).count() == users_before
        assert user.google_id == "google-sub:auto-link@example.com"
        # P4: el correo de Google ya estaba verificado por Google → la cuenta queda activa.
        assert user.email_verified is True
        # Fase 23 (Decisión G1, corrige el bug de la auditoría 2026-09-15): la cuenta estaba
        # SIN verificar antes de este login — cualquier password_hash preexistente nunca fue
        # probado contra el dueño real del email (pudo ser plantado por un atacante), así que
        # se anula al vincular. La cuenta queda Google-only hasta que su dueño fije una
        # contraseña nueva (Settings/forgot-password, mismo flujo que Fase 22 ya construyó
        # para cuentas Google-only puras).
        assert user.password_hash is None

    def test_autolink_on_unverified_account_nullifies_attacker_planted_password(self, client, monkeypatch, db_session):
        """Escenario hostil completo (Fase 23, Decisión G1): un atacante se pre-registra
        con el email de la víctima y su propia contraseña, nunca verifica el correo (un
        solo POST, rate-limitado pero no bloqueado). Cuando la víctima real hace login con
        Google con ese mismo correo, el auto-link debe anular esa contraseña plantada — si
        no, quedaría válida para el atacante contra POST /auth/login (el bug original)."""
        victim_email = "victima@example.com"
        register_response = client.post(
            "/api/v1/users/",
            json={"email": victim_email, "full_name": "Atacante", "password": "PasswordDelAtacante1"},
        )
        assert register_response.status_code == 200, register_response.text

        # La cuenta plantada por el atacante nunca se verifica.
        user = db_session.query(models.User).filter(models.User.email == victim_email).first()
        assert user.email_verified is False

        # La víctima real hace login con Google usando el mismo correo.
        response = self._login_google(client, monkeypatch, email=victim_email)
        assert response.status_code == 200, response.text

        db_session.refresh(user)
        assert user.email_verified is True
        assert user.password_hash is None  # Fase 23 (G1): contraseña plantada, anulada
        assert user.google_id == f"google-sub:{victim_email}"

        # La contraseña que el atacante plantó ya NO sirve contra esta cuenta.
        ataque_login = client.post(
            "/api/v1/auth/login",
            data={"username": victim_email, "password": "PasswordDelAtacante1"},
        )
        assert ataque_login.status_code == 403
        assert ataque_login.json()["detail"] == "Credenciales Inválidas"

    def test_existing_verified_password_account_is_idempotent_and_autolinked(
        self, client, monkeypatch, db_session, register_and_login
    ):
        user = register_and_login(email="auto-link-verificado@example.com")
        stored = db_session.query(models.User).filter(models.User.email == user["email"]).one()
        assert stored.email_verified is True

        response = self._login_google(client, monkeypatch, email=user["email"])
        assert response.status_code == 200, response.text

        stored = db_session.query(models.User).filter(models.User.email == user["email"]).one()
        assert stored.google_id == f"google-sub:{user['email']}"  # se setea igual
        assert stored.email_verified is True
        assert db_session.query(models.User).count() == 1  # sin duplicados, sin romper nada
        # Fase 23 (Decisión G1, regresión): la cuenta YA estaba verificada antes de este
        # login de Google — su password_hash ya era confiable (probado por el dueño real
        # vía el flujo normal de verificación), así que vincular Google no debe tocarlo.
        assert stored.password_hash is not None
        # La contraseña original sigue funcionando end-to-end, no solo el hash intacto.
        login_con_password = client.post(
            "/api/v1/auth/login",
            data={"username": user["email"], "password": user["password"]},
        )
        assert login_con_password.status_code == 200, login_con_password.text

    def test_unverified_email_claim_returns_403_and_creates_no_user(self, client, monkeypatch, db_session):
        response = self._login_google(client, monkeypatch, email="no-verificado@example.com", email_verified=False)
        assert response.status_code == 403
        # Google reportó el correo como no verificado → no se confía en el token ni se
        # registra nada (Historia de usuario 13).
        assert db_session.query(models.User).filter(models.User.email == "no-verificado@example.com").first() is None

    def test_password_login_against_google_only_account_returns_403(self, client, monkeypatch, db_session):
        google_login = self._login_google(client, monkeypatch, email="solo-google@example.com")
        assert google_login.status_code == 200

        # Guard nuevo en login() (Fase 20 §20.3): password_hash=None → 403 genérico,
        # no 500 de passlib (que lanza excepción sobre un hash nulo, no devuelve False).
        response = client.post(
            "/api/v1/auth/login",
            data={"username": "solo-google@example.com", "password": "Contrasena10"},
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "Credenciales Inválidas"

    def test_missing_google_client_id_returns_503(self, client, monkeypatch):
        monkeypatch.setattr(security, "GOOGLE_CLIENT_ID", None)
        response = client.post("/api/v1/auth/google", json={"id_token": "idtoken-falso"})
        assert response.status_code == 503
        assert "no está configurado" in response.json()["detail"]

    def test_invalid_id_token_returns_401(self, client, monkeypatch):
        monkeypatch.setattr(security, "GOOGLE_CLIENT_ID", self.GOOGLE_CLIENT_ID)

        def _reject(token, request, audience):
            raise ValueError("firma o audiencia inválida")

        monkeypatch.setattr("app.api.auth.google_id_token.verify_oauth2_token", _reject)
        response = client.post("/api/v1/auth/google", json={"id_token": "idtoken-malo"})
        assert response.status_code == 401
        assert response.json()["detail"] == "Token de Google inválido."

    def test_sixth_google_login_request_in_a_minute_returns_429(self, client, monkeypatch):
        # Mismo patrón que test_sixth_login_request_in_a_minute_returns_429: 5 llamadas
        # completan el límite de 5/minute; la sexta rebota. Emails distintos por llamada
        # para no chocar contra la unicidad de google_id.
        for i in range(5):
            response = self._login_google(client, monkeypatch, email=f"rate-google-{i}@example.com")
            assert response.status_code == 200, response.text

        sixth_response = client.post("/api/v1/auth/google", json={"id_token": "idtoken-falso"})
        assert sixth_response.status_code == 429


# --- Cookies de sesión (Fase 26, Decisiones B1/B2/B6/B7/B8) -------------------


class TestCookiesDeSesion:
    """Fase 26: `login`/`refresh` setean los tokens como cookies httpOnly, `get_current_user`
    acepta el cookie como fallback, y `logout`/baja de cuenta los limpian en su respuesta.

    Hallazgo 13 de docs/specs/fase_26_spec.md: el TestClient de httpx mantiene un cookie-jar
    real por instancia — se loguea y el jar hace el resto, sin simular un navegador a mano.

    COOKIE_SECURE se fuerza a False: el TestClient habla por `http://testserver` y un cookie
    Secure jamás viaja sobre http (regla del navegador y de httpx) — sin este monkeypatch
    ningún test llegaría a ver el cookie en la request.
    """

    @pytest.fixture(autouse=True)
    def _cookies_viajan_sobre_http(self, monkeypatch):
        monkeypatch.setattr(security, "COOKIE_SECURE", False)

    def test_login_sets_httponly_access_and_refresh_cookies(self, client, db_session):
        email = "cookies-set@example.com"
        register = client.post(
            "/api/v1/users/",
            json={"email": email, "full_name": "Usuaria Cookies", "password": "Contrasena10"},
        )
        assert register.status_code == 200, register.text
        db_session.query(models.User).filter(models.User.email == email).update({"email_verified": True})
        db_session.commit()

        response = client.post("/api/v1/auth/login", data={"username": email, "password": "Contrasena10"})
        assert response.status_code == 200, response.text

        set_cookies = response.headers.get_list("set-cookie")
        por_nombre = {linea.split("=", 1)[0]: linea for linea in set_cookies}

        access = por_nombre["access_token"]
        assert "HttpOnly" in access
        assert "Max-Age=900" in access  # 15 min = TTL del access token (Decisión B2)
        assert "Path=/" in access
        assert "SameSite=lax" in access

        refresh = por_nombre["refresh_token"]
        assert "HttpOnly" in refresh
        assert "Max-Age=2592000" in refresh  # 30 días
        assert "Path=/api/v1/auth" in refresh  # angosto pero cubre /logout (Decisión B2, corregida)

        csrf = por_nombre["csrf_token"]
        assert "HttpOnly" not in csrf  # el frontend lo lee por JS (double-submit, B5)
        assert "Path=/" in csrf
        assert "Max-Age=2592000" in csrf

        # El cookie-jar del propio TestClient adoptó los tres (Hallazgo 13).
        assert client.cookies.get("access_token") is not None
        assert client.cookies.get("refresh_token") is not None
        assert client.cookies.get("csrf_token") is not None

    def test_refresh_rotates_cookie_without_body(self, client, register_and_login):
        register_and_login(email="cookies-refresh@example.com")
        access_antes = client.cookies.get("access_token")
        refresh_antes = client.cookies.get("refresh_token")
        assert access_antes is not None

        # Sin body: el cookie refresh_token (jar de httpx, Path angosto) viaja solo.
        response = client.post("/api/v1/auth/refresh")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["access_token"]
        assert body["refresh_token"]

        access_despues = client.cookies.get("access_token")
        assert access_despues is not None
        assert access_despues != access_antes  # el access token se rotó
        assert client.cookies.get("refresh_token") != refresh_antes

    def test_protected_route_authenticates_via_cookie_without_header(self, client, register_and_login):
        user = register_and_login(email="cookies-me@example.com")

        # Sin Authorization a mano: el cookie access_token viaja solo y autentica.
        response = client.get("/api/v1/users/me")
        assert response.status_code == 200, response.text
        assert response.json()["id"] == user["id"]

    def test_logout_clears_all_three_cookies(self, client, register_and_login):
        register_and_login(email="cookies-logout@example.com")
        assert client.cookies.get("access_token") is not None

        # Logout es una mutación con cookie de sesión presente y no está exenta del
        # middleware CSRF — el frontend (Decisión F1) manda X-CSRF-Token en todo no-GET.
        response = client.post(
            "/api/v1/auth/logout",
            headers={"X-CSRF-Token": client.cookies.get("csrf_token")},
        )
        assert response.status_code == 200, response.text

        # limpiar_cookies_de_sesion manda Max-Age=0 para los tres (mismos paths que al setear).
        assert client.cookies.get("access_token") is None
        assert client.cookies.get("refresh_token") is None
        assert client.cookies.get("csrf_token") is None

    def test_logout_via_cookie_only_revokes_refresh_token_server_side(self, client, register_and_login):
        """Regresión: con el Path angosto original (/api/v1/auth/refresh) el cookie
        refresh_token nunca llegaba a /auth/logout (ruta hermana, no subruta) y el logout
        por navegador no revocaba nada server-side — corregido ampliando el Path a
        /api/v1/auth. Se captura el valor del cookie ANTES de logout (que lo limpia) y se
        lo reusa a mano en /refresh después, para verificar la revocación en DB
        independientemente de que el cookie ya no esté en el jar."""
        register_and_login(email="cookies-logout-revoke@example.com")
        refresh_token_value = client.cookies.get("refresh_token")
        assert refresh_token_value is not None

        response = client.post(
            "/api/v1/auth/logout",
            headers={"X-CSRF-Token": client.cookies.get("csrf_token")},
        )
        assert response.status_code == 200, response.text

        refresh_after_logout = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token_value})
        assert refresh_after_logout.status_code == 401

    def test_delete_account_clears_cookies(self, client, register_and_login):
        # Hallazgo 6 / Decisión B8: borrar la cuenta también debe limpiar los cookies en la
        # misma respuesta (el frontend ya no puede tocar cookies httpOnly).
        user = register_and_login(email="cookies-borrar-cuenta@example.com")
        assert client.cookies.get("access_token") is not None

        response = client.request(
            "DELETE",
            "/api/v1/users/me",
            json={"password": user["password"]},
            headers={"X-CSRF-Token": client.cookies.get("csrf_token")},
        )
        assert response.status_code == 204, response.text

        assert client.cookies.get("access_token") is None
        assert client.cookies.get("refresh_token") is None
        assert client.cookies.get("csrf_token") is None


def test_jwt_created_with_expired_delta_is_rejected_by_jose_directly():
    """Chequeo de nivel más bajo, sin pasar por HTTP: un token ya vencido no pasa `jwt.decode`."""
    token = security.create_access_token(data={"sub": "1"}, expires_delta=timedelta(seconds=-1))
    try:
        jwt.decode(token, security.SECRET_KEY, algorithms=[security.ALGORITHM])
    except Exception as exc:  # jose.JWTError
        assert "expired" in str(exc).lower() or "signature" in str(exc).lower()
    else:
        raise AssertionError("Se esperaba que jwt.decode rechazara un token expirado")
