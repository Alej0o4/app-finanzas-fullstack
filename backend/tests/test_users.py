"""Tests del perfil de usuario: `PATCH /api/v1/users/me` con `monthly_income` (Fase 8 §1).

Primer test de `users.py` fuera del registro. `UserProfileUpdate` es un schema separado de
`PreferencesUpdate` por ser un dato financiero de dominio, no cosmético (Decisión 1.1).
"""

from decimal import Decimal


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
