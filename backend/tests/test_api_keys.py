"""Tests de API keys personales revocables (Fase 16 §16.1).

Cubre: creación con exposición única de la key en texto plano (Decisión 16.1.5),
listado que nunca expone `key`/`key_hash`, revocación efectiva en el siguiente request
(Decisión 16.1.4), 404 en DELETE de key ajena/ya revocada, regresión del flujo JWT, el
rate limit por usuario de `POST /transactions` cuando la auth es API key (Decisión
16.1.7, corregida en la revisión de seguridad post-16.1 — keyed por `user_id` resuelto en
DB, no por hash del token crudo), y las correcciones de la revisión de seguridad
(Decisión 16.1.8 / docs/TODO.md): revocación de API keys al confirmar un reset de
contraseña, y el tope + rate limit sobre la creación de API keys.
"""

import re

from fastapi.testclient import TestClient

API_KEYS_URL = "/api/v1/api-keys"


def _crear_api_key(client: TestClient, headers: dict, name: str = "Shortcut iPhone") -> dict:
    response = client.post(API_KEYS_URL, json={"name": name}, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _extract_token_from_email(html_body: str) -> str:
    match = re.search(r"token=([^\"&\s]+)", html_body)
    assert match, f"No se encontró un token en el cuerpo del email: {html_body!r}"
    return match.group(1)


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

    def test_rate_limit_counter_is_per_user_shared_across_own_keys(
        self, client, test_user, make_account, make_category
    ):
        """Revisión de seguridad post-16.1 (docs/TODO.md): la primera versión clavaba el
        contador por hash de la key, así que dos keys del mismo usuario tenían contadores
        independientes — un usuario podía crear N keys y multiplicar por N su cuota real
        de 60/min, justo la automatización sin freno que la Decisión 16.1.7 buscaba evitar.
        Corregido: el `key_func` resuelve el `user_id` real contra la DB, así que dos keys
        del MISMO usuario comparten un único balde."""
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

        # key A consume las 60 del balde... que es el balde del USUARIO, no de la key.
        for _ in range(60):
            response = client.post("/api/v1/transactions/", json=payload, headers=headers_a)
            assert response.status_code == 200, response.text
        assert client.post("/api/v1/transactions/", json=payload, headers=headers_a).status_code == 429

        # key B es una key DISTINTA pero del MISMO usuario → mismo balde, ya agotado.
        # Antes del fix esto devolvía 200 (bug: multiplicaba la cuota real por N keys).
        also_limited = client.post("/api/v1/transactions/", json=payload, headers=headers_b)
        assert also_limited.status_code == 429, also_limited.text

    def test_rate_limit_counter_is_independent_across_different_users(
        self, client, test_user, other_user, make_account, make_category
    ):
        """Dos usuarios distintos (cada uno con su propia key) sí tienen baldes
        independientes — el fix clavea por usuario, no colapsa a un balde global."""
        cuenta = make_account(test_user["headers"], balance="1000.00")
        categoria = make_category(test_user["headers"], name="Ingreso A", type="income")
        cuenta_otro = make_account(other_user["headers"], balance="1000.00")
        categoria_otro = make_category(other_user["headers"], name="Ingreso ajeno", type="income")

        key_propia = _crear_api_key(client, test_user["headers"], name="propia")
        key_ajena = _crear_api_key(client, other_user["headers"], name="ajena")
        headers_propia = {"Authorization": f"Bearer {key_propia['key']}"}
        headers_ajena = {"Authorization": f"Bearer {key_ajena['key']}"}

        payload_propio = {
            "amount": "1.00",
            "type": "income",
            "account_id": cuenta["id"],
            "category_id": categoria["id"],
        }
        payload_ajeno = {
            "amount": "1.00",
            "type": "income",
            "account_id": cuenta_otro["id"],
            "category_id": categoria_otro["id"],
        }

        for _ in range(60):
            response = client.post("/api/v1/transactions/", json=payload_propio, headers=headers_propia)
            assert response.status_code == 200, response.text
        assert client.post("/api/v1/transactions/", json=payload_propio, headers=headers_propia).status_code == 429

        # El otro usuario no comparte balde — su primera llamada sigue pasando.
        first_ajeno = client.post("/api/v1/transactions/", json=payload_ajeno, headers=headers_ajena)
        assert first_ajeno.status_code == 200, first_ajeno.text


class TestRevisionSeguridadPost161:
    """Hallazgos de la revisión de seguridad de la Decisión 16.1.8 (ver docs/TODO.md),
    corregidos directamente en el código en vez de quedar solo documentados."""

    def test_password_reset_confirm_revokes_active_api_keys(self, client, register_and_login, captured_emails):
        """Antes de este fix, confirmar un reset de contraseña revocaba los refresh
        tokens del usuario pero dejaba viva cualquier API key existente — una key
        minteada durante una ventana de compromiso (p. ej. un JWT robado, válido 15 min)
        sobrevivía indefinidamente a la acción que el usuario toma específicamente para
        recuperar el control de su cuenta, contradiciendo la razón de ser del bloque que
        ya revocaba los refresh tokens ("dejar sesiones viejas vivas sería
        contradictorio", `auth.py`)."""
        user = register_and_login(email="con-api-key@example.com")
        captured_emails.clear()  # descarta el email de verificación del registro

        creada = _crear_api_key(client, user["headers"], name="Shortcut comprometido")
        key_headers = {"Authorization": f"Bearer {creada['key']}"}
        assert client.get("/api/v1/users/me", headers=key_headers).status_code == 200

        client.post("/api/v1/auth/password-reset/request", json={"email": user["email"]})
        raw_token = _extract_token_from_email(captured_emails[-1]["html_body"])
        confirm = client.post(
            "/api/v1/auth/password-reset/confirm",
            json={"token": raw_token, "new_password": "OtraContrasena99"},
        )
        assert confirm.status_code == 200, confirm.text

        # La API key minteada antes del reset ya no debería autenticar.
        after_reset = client.get("/api/v1/users/me", headers=key_headers)
        assert after_reset.status_code == 401

        # Y queda marcada como revocada en el listado (login nuevo con la contraseña
        # actualizada, ya que el reset también invalidó los refresh tokens viejos).
        login = client.post(
            "/api/v1/auth/login",
            data={"username": user["email"], "password": "OtraContrasena99"},
        )
        assert login.status_code == 200, login.text
        nuevo_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        lista = client.get(API_KEYS_URL, headers=nuevo_headers).json()
        assert len(lista) == 1
        assert lista[0]["revoked_at"] is not None

    def test_password_reset_confirm_does_not_touch_other_users_api_keys(
        self, client, register_and_login, other_user, captured_emails
    ):
        """La revocación masiva del fix anterior está filtrada por `user_id` — un reset de
        contraseña de un usuario no debe tocar las keys de otro."""
        user = register_and_login(email="con-api-key-2@example.com")
        captured_emails.clear()
        key_ajena = _crear_api_key(client, other_user["headers"], name="No debería tocarse")

        client.post("/api/v1/auth/password-reset/request", json={"email": user["email"]})
        raw_token = _extract_token_from_email(captured_emails[-1]["html_body"])
        client.post(
            "/api/v1/auth/password-reset/confirm",
            json={"token": raw_token, "new_password": "OtraContrasena99"},
        )

        lista_ajena = client.get(API_KEYS_URL, headers=other_user["headers"]).json()
        assert len(lista_ajena) == 1
        assert lista_ajena[0]["id"] == key_ajena["id"]
        assert lista_ajena[0]["revoked_at"] is None

    def test_create_api_key_endpoint_is_rate_limited(self, client, test_user):
        """`POST /api-keys/` no tenía ningún rate limit: con un JWT válido (p. ej. uno
        robado, de 15 min de vida) se podían mintear tantas API keys de larga vida como se
        quisiera, sin fricción. Ahora lleva el mismo `5/minute` que login/registro/reset."""
        for _ in range(5):
            response = client.post(API_KEYS_URL, json={"name": "key"}, headers=test_user["headers"])
            assert response.status_code == 200, response.text

        sexta = client.post(API_KEYS_URL, json={"name": "key"}, headers=test_user["headers"])
        assert sexta.status_code == 429

    def test_create_api_key_enforces_max_active_keys_per_user(self, client, test_user, monkeypatch):
        """Tope defensivo sobre el número de API keys activas por usuario — sin él, minteo
        masivo de keys (dentro de la ventana del rate limit de creación, o a lo largo del
        tiempo) multiplica sin límite la cantidad de credenciales de larga vida que
        sobreviven incluso a un reset de contraseña si el usuario no las revoca a mano una
        por una. Se baja el tope a 2 vía monkeypatch para no chocar con el rate limit de
        creación (5/minute) probado aparte."""
        monkeypatch.setattr("app.api.api_keys.MAX_ACTIVE_API_KEYS_POR_USUARIO", 2)

        _crear_api_key(client, test_user["headers"], name="uno")
        _crear_api_key(client, test_user["headers"], name="dos")

        tercera = client.post(API_KEYS_URL, json={"name": "tres"}, headers=test_user["headers"])
        assert tercera.status_code == 400
        assert "máximo" in tercera.json()["detail"] or "2" in tercera.json()["detail"]

    def test_revoking_a_key_frees_a_slot_under_the_cap(self, client, test_user, monkeypatch):
        """Revocar una key libera cupo bajo el tope — el tope cuenta keys ACTIVAS, no el
        histórico total creado."""
        monkeypatch.setattr("app.api.api_keys.MAX_ACTIVE_API_KEYS_POR_USUARIO", 1)

        primera = _crear_api_key(client, test_user["headers"], name="uno")
        bloqueada = client.post(API_KEYS_URL, json={"name": "dos"}, headers=test_user["headers"])
        assert bloqueada.status_code == 400

        client.delete(f"{API_KEYS_URL}/{primera['id']}", headers=test_user["headers"])

        despues_de_revocar = client.post(API_KEYS_URL, json={"name": "dos"}, headers=test_user["headers"])
        assert despues_de_revocar.status_code == 200, despues_de_revocar.text
