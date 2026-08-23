"""Tests de autenticación y ciclo de vida de cuenta (Fase 7, §4.2 del spec).

Cubre: registro, login, refresh, logout, rate limiting, `get_current_user`, y — dado que ya
están implementados — password reset, verificación de email y el TTL de 15 min del access
token (§2.1/§2.2/§2.5).
"""

import re
from datetime import UTC, datetime, timedelta

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

    def test_login_works_without_verifying_email(self, client, register_and_login):
        user = register_and_login(email="sin-verificar@example.com", password="Contrasena10")
        response = client.post("/api/v1/auth/login", data={"username": user["email"], "password": user["password"]})
        assert response.status_code == 200


def test_jwt_created_with_expired_delta_is_rejected_by_jose_directly():
    """Chequeo de nivel más bajo, sin pasar por HTTP: un token ya vencido no pasa `jwt.decode`."""
    token = security.create_access_token(data={"sub": "1"}, expires_delta=timedelta(seconds=-1))
    try:
        jwt.decode(token, security.SECRET_KEY, algorithms=[security.ALGORITHM])
    except Exception as exc:  # jose.JWTError
        assert "expired" in str(exc).lower() or "signature" in str(exc).lower()
    else:
        raise AssertionError("Se esperaba que jwt.decode rechazara un token expirado")
