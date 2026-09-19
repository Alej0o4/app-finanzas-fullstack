"""Tests del middleware CSRF double-submit cookie (Fase 26, Decisión B5).

Reglas que se prueban:
- Una mutación autenticada POR COOKIE sin header `X-CSRF-Token` → 403.
- Una mutación autenticada por cookie con header que no matchea el cookie `csrf_token` → 403.
- Una mutación autenticada por cookie con header matching → 200.
- Una mutación autenticada por header JWT SIN cookie de sesión está exenta (Hallazgo 10:
  clientes header-only — curl, Shortcuts de iOS — no deberían tener que simular CSRF).
- GET/HEAD/OPTIONS nunca exigen el header (métodos seguros).

COOKIE_SECURE se fuerza a False por la misma razón que en TestCookiesDeSesion: el TestClient
habla por http://testserver y un cookie Secure jamás viaja sobre http.
"""

import pytest

from app.core import security
from app.models import models

_CUENTA_PAYLOAD = {
    "name": "Cuenta CSRF",
    "type": "cash",
    "currency": "COP",
    "balance": "100.00",
    "highlighted": False,
}


class TestCsrfDoubleSubmit:
    @pytest.fixture(autouse=True)
    def _cookies_viajan_sobre_http(self, monkeypatch):
        monkeypatch.setattr(security, "COOKIE_SECURE", False)

    def _login(self, client, register_and_login, email="csrf-login@example.com"):
        register_and_login(email=email)
        assert client.cookies.get("access_token") is not None
        assert client.cookies.get("csrf_token") is not None

    def test_mutation_via_cookie_without_csrf_header_returns_403(self, client, register_and_login):
        self._login(client, register_and_login)

        response = client.post("/api/v1/auth/logout")
        assert response.status_code == 403
        assert response.json() == {"detail": "Token CSRF inválido o ausente."}

    def test_mutation_via_cookie_with_mismatched_csrf_header_returns_403(self, client, register_and_login):
        self._login(client, register_and_login)

        response = client.post(
            "/api/v1/auth/logout",
            headers={"X-CSRF-Token": "token-que-no-coincide-con-el-cookie"},
        )
        assert response.status_code == 403
        assert response.json() == {"detail": "Token CSRF inválido o ausente."}

    def test_mutation_via_cookie_with_matching_csrf_header_succeeds(self, client, register_and_login):
        self._login(client, register_and_login)

        response = client.post(
            "/api/v1/accounts/",
            json=_CUENTA_PAYLOAD,
            headers={"X-CSRF-Token": client.cookies.get("csrf_token")},
        )
        assert response.status_code == 200, response.text

    def test_mutation_via_jwt_header_without_any_cookie_is_exempt(self, client, db_session):
        """Regresión directa del Hallazgo 10: un cliente header-only (curl, un test de
        integración externo) no debería necesitar simular CSRF — el middleware solo protege
        el camino de cookie, y este cliente nunca pasó por login, así que no tiene cookies."""
        email = "csrf-header-only@example.com"
        register = client.post(
            "/api/v1/users/",
            json={"email": email, "full_name": "Header Only", "password": "Contrasena10"},
        )
        assert register.status_code == 200, register.text
        user_id = register.json()["id"]
        db_session.query(models.User).filter(models.User.id == user_id).update({"email_verified": True})
        db_session.commit()

        jwt_token = security.create_access_token(data={"sub": str(user_id)})
        response = client.post(
            "/api/v1/accounts/",
            json=_CUENTA_PAYLOAD,
            headers={"Authorization": f"Bearer {jwt_token}"},
        )
        assert response.status_code == 200, response.text
        assert client.cookies.get("access_token") is None  # sigue sin cookies el jar

    def test_get_request_never_requires_csrf_header(self, client, register_and_login):
        self._login(client, register_and_login)

        response = client.get("/api/v1/users/me")
        assert response.status_code == 200, response.text
