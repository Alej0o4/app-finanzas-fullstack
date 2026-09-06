"""Tests de API keys personales revocables (Fase 16 §16.1).

Cubre: creación con exposición única de la key en texto plano (Decisión 16.1.5),
listado que nunca expone `key`/`key_hash`, revocación efectiva en el siguiente request
(Decisión 16.1.4), 404 en DELETE de key ajena/ya revocada, regresión del flujo JWT, y el
rate limit por usuario de `POST /transactions` cuando la auth es API key (Decisión
16.1.7 — keyed por hash del token, no por IP).
"""

from fastapi.testclient import TestClient

API_KEYS_URL = "/api/v1/api-keys"


def _crear_api_key(client: TestClient, headers: dict, name: str = "Shortcut iPhone") -> dict:
    response = client.post(API_KEYS_URL, json={"name": name}, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


class TestCreacionYListado:
    def test_create_returns_plaintext_key_and_prefix(self, client, test_user):
        body = _crear_api_key(client, test_user["headers"], name="Shortcut iPhone")
        assert body["key"].startswith("oikos_pat_")
        assert body["name"] == "Shortcut iPhone"
        assert body["key_prefix"] == body["key"][:12]
        assert body["id"] > 0

    def test_list_never_exposes_key_or_key_hash(self, client, test_user):
        creada = _crear_api_key(client, test_user["headers"], name="Automatización")
        otra = _crear_api_key(client, test_user["headers"], name="Segunda key")

        lista = client.get(API_KEYS_URL, headers=test_user["headers"])
        assert lista.status_code == 200, lista.text
        items = lista.json()
        assert len(items) == 2
        for item in items:
            assert "key" not in item
            assert "key_hash" not in item
        prefijos = {item["key_prefix"] for item in items}
        assert prefijos == {creada["key_prefix"], otra["key_prefix"]}

    def test_list_only_shows_own_keys(self, client, test_user, other_user):
        _crear_api_key(client, test_user["headers"], name="Mía")

        lista_ajena = client.get(API_KEYS_URL, headers=other_user["headers"])
        assert lista_ajena.status_code == 200
        assert lista_ajena.json() == []

        lista_propia = client.get(API_KEYS_URL, headers=test_user["headers"])
        assert len(lista_propia.json()) == 1

    def test_create_requires_nonempty_name(self, client, test_user):
        response = client.post(API_KEYS_URL, json={"name": ""}, headers=test_user["headers"])
        assert response.status_code == 422


class TestAutenticacionConApiKey:
    def test_valid_api_key_authenticates(self, client, test_user):
        creada = _crear_api_key(client, test_user["headers"])
        headers = {"Authorization": f"Bearer {creada['key']}"}

        response = client.get("/api/v1/users/me", headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["id"] == test_user["id"]

    def test_invalid_api_key_returns_401(self, client, test_user):
        response = client.get(
            "/api/v1/users/me",
            headers={"Authorization": "Bearer oikos_pat_token-que-no-existe"},
        )
        assert response.status_code == 401

    def test_jwt_auth_still_works_as_regression(self, client, test_user):
        response = client.get("/api/v1/users/me", headers=test_user["headers"])
        assert response.status_code == 200


class TestRevocacion:
    def test_revoked_key_returns_401_on_next_request(self, client, test_user):
        creada = _crear_api_key(client, test_user["headers"])
        key_headers = {"Authorization": f"Bearer {creada['key']}"}

        # Funciona antes de revocar.
        assert client.get("/api/v1/users/me", headers=key_headers).status_code == 200

        revoke = client.delete(f"{API_KEYS_URL}/{creada['id']}", headers=test_user["headers"])
        assert revoke.status_code == 200
        assert revoke.json()["estado"] == "OK"

        # El siguiente request con la key revocada falla con 401 (Decisión 16.1.4:
        # revocación efectiva sin ventana de gracia).
        revoked = client.get("/api/v1/users/me", headers=key_headers)
        assert revoked.status_code == 401

    def test_revoke_keeps_row_for_audit_with_revoked_at(self, client, test_user):
        creada = _crear_api_key(client, test_user["headers"])
        client.delete(f"{API_KEYS_URL}/{creada['id']}", headers=test_user["headers"])

        lista = client.get(API_KEYS_URL, headers=test_user["headers"]).json()
        assert len(lista) == 1
        assert lista[0]["revoked_at"] is not None
        assert lista[0]["key_prefix"] == creada["key_prefix"]

    def test_revoke_foreign_key_returns_404(self, client, test_user, other_user):
        creada = _crear_api_key(client, other_user["headers"])

        response = client.delete(f"{API_KEYS_URL}/{creada['id']}", headers=test_user["headers"])
        assert response.status_code == 404

    def test_revoke_already_revoked_key_returns_404(self, client, test_user):
        creada = _crear_api_key(client, test_user["headers"])
        first = client.delete(f"{API_KEYS_URL}/{creada['id']}", headers=test_user["headers"])
        assert first.status_code == 200

        second = client.delete(f"{API_KEYS_URL}/{creada['id']}", headers=test_user["headers"])
        assert second.status_code == 404

    def test_revoke_nonexistent_key_returns_404(self, client, test_user):
        response = client.delete(f"{API_KEYS_URL}/999999", headers=test_user["headers"])
        assert response.status_code == 404


class TestRateLimitPorUsuario:
    def test_post_transactions_with_api_key_hits_limit_at_61st_call(
        self, client, test_user, make_account, make_category
    ):
        """Decisión 16.1.7: `POST /transactions` lleva `60/minute` keyed por usuario
        (hash del token de la API key) cuando la auth es API key. El límite por IP no
        protege una automatización que corre desde una IP estable.

        Patrón de testa igual que test_auth.py:TestLogin.test_sixth_login_request...
        — N requests permitidos, el N+1 rebota con 429 (sin freezegun: 61 llamadas
        rápidas caben holgadas en la ventana de 1 minuto).
        """
        user = test_user
        cuenta = make_account(user["headers"], balance="1000.00")
        categoria = make_category(user["headers"], name="Ingreso automático", type="income")

        creada = _crear_api_key(client, user["headers"], name="rate-limit")
        key_headers = {"Authorization": f"Bearer {creada['key']}"}

        payload = {
            "amount": "10.00",
            "type": "income",
            "account_id": cuenta["id"],
            "category_id": categoria["id"],
        }
        for _ in range(60):
            response = client.post("/api/v1/transactions/", json=payload, headers=key_headers)
            assert response.status_code == 200, response.text

        sixty_first = client.post("/api/v1/transactions/", json=payload, headers=key_headers)
        assert sixty_first.status_code == 429

    def test_rate_limit_counter_is_per_api_key(self, client, test_user, make_account, make_category):
        """Dos keys distintas (dos usuarios distintos a efectos prácticos: cada key
        pertenece a un usuario) no comparten contador — el key_func clavea por el hash
        del token, no por IP."""
        cuenta = make_account(test_user["headers"], balance="1000.00")
        categoria = make_category(test_user["headers"], name="Ingreso B", type="income")

        key_a = _crear_api_key(client, test_user["headers"], name="key A")
        key_b = _crear_api_key(client, test_user["headers"], name="key B")
        headers_a = {"Authorization": f"Bearer {key_a['key']}"}
        headers_b = {"Authorization": f"Bearer {key_b['key']}"}

        payload = {
            "amount": "1.00",
            "type": "income",
            "account_id": cuenta["id"],
            "category_id": categoria["id"],
        }

        # key A consume 60 de su propio contador.
        for _ in range(60):
            response = client.post("/api/v1/transactions/", json=payload, headers=headers_a)
            assert response.status_code == 200, response.text
        assert client.post("/api/v1/transactions/", json=payload, headers=headers_a).status_code == 429

        # key B (token distinto → contra distinto) sigue sin tocar su límite.
        first_b = client.post("/api/v1/transactions/", json=payload, headers=headers_b)
        assert first_b.status_code == 200, first_b.text
