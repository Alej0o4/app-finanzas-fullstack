"""Tests de la infraestructura de push web (Fase 13 §13.2).

Suscribir/desuscribir, upsert por endpoint (multi-dispositivo, Decisión 13.2.3) y el
cleanup de suscripciones caducadas (WebPushException 404/410) sin romper el resto del
flujo. El envío real a un navegador real queda fuera de lo que pytest puede cubrir
(misma limitación que el email real de Fase 7, ver docs/TODO.md) — aquí se mockea
`pywebpush.webpush` en `app.core.notification_dispatch` (donde vive el helper compartido
tras la extracción de Fase 14 §14.2).
"""

from datetime import UTC, datetime

from app.models import models


def _payload(endpoint: str, p256dh: str = "clave-p256dh-1", auth: str = "clave-auth-1") -> dict:
    return {"endpoint": endpoint, "keys": {"p256dh": p256dh, "auth": auth}}


def _contar_suscripciones(db_session, user_id: int | None = None) -> int:
    query = db_session.query(models.PushSubscription)
    if user_id is not None:
        query = query.filter(models.PushSubscription.user_id == user_id)
    return query.count()


class TestPushSubscriptionEndpoints:
    def test_subscribe_creates_row_and_returns_it(self, client, auth_headers, db_session):
        endpoint = "https://push.example.com/fcm/suscripcion-1"

        response = client.post("/api/v1/push/subscribe", json=_payload(endpoint), headers=auth_headers)
        assert response.status_code == 200, response.text
        assert response.json()["endpoint"] == endpoint

        assert _contar_suscripciones(db_session) == 1

    def test_vapid_public_key_endpoint_is_public(self, client):
        # No requiere autenticación: sin headers debe responder (200 o 503 si no hay key)
        response = client.get("/api/v1/push/vapid-public-key")
        assert response.status_code in (200, 503)

    def test_duplicate_endpoint_upserts_instead_of_duplicating(self, client, auth_headers, db_session):
        endpoint = "https://push.example.com/fcm/suscripcion-mismo-navegador"

        primera = client.post(
            "/api/v1/push/subscribe",
            json=_payload(endpoint, p256dh="p256dh-v1", auth="auth-v1"),
            headers=auth_headers,
        )
        assert primera.status_code == 200, primera.text

        segunda = client.post(
            "/api/v1/push/subscribe",
            json=_payload(endpoint, p256dh="p256dh-v2", auth="auth-v2"),
            headers=auth_headers,
        )
        assert segunda.status_code == 200, segunda.text

        # Misma fila (mismo id), claves actualizadas, UNA sola fila para el endpoint
        assert segunda.json()["id"] == primera.json()["id"]
        assert _contar_suscripciones(db_session) == 1
        fila = db_session.query(models.PushSubscription).filter(models.PushSubscription.endpoint == endpoint).first()
        assert fila.p256dh_key == "p256dh-v2"
        assert fila.auth_key == "auth-v2"

    def test_unsubscribe_deletes_row(self, client, auth_headers, db_session):
        endpoint = "https://push.example.com/fcm/suscripcion-para-borrar"
        subscript = client.post("/api/v1/push/subscribe", json=_payload(endpoint), headers=auth_headers)
        assert subscript.status_code == 200, subscript.text
        assert _contar_suscripciones(db_session) == 1

        borrado = client.request("DELETE", "/api/v1/push/subscribe", json={"endpoint": endpoint}, headers=auth_headers)
        assert borrado.status_code == 200, borrado.text
        assert _contar_suscripciones(db_session) == 0

    def test_unsubscribe_foreign_subscription_returns_404(self, client, auth_headers, other_user, db_session):
        endpoint = "https://push.example.com/fcm/suscripcion-ajena"
        subscript = client.post("/api/v1/push/subscribe", json=_payload(endpoint), headers=auth_headers)
        assert subscript.status_code == 200, subscript.text

        response = client.request(
            "DELETE", "/api/v1/push/subscribe", json={"endpoint": endpoint}, headers=other_user["headers"]
        )
        assert response.status_code == 404

        # La fila sigue existiendo, sin tocar
        assert _contar_suscripciones(db_session) == 1


class TestPushSendFromBudgetAlerts:
    def test_push_410_cleans_up_that_subscription_and_continues_with_the_rest(
        self, client, auth_headers, make_account, make_category, monkeypatch, db_session
    ):
        """Decisión 13.2.3: una suscripción caducada (410 Gone) se borra y el envío
        continúa con las demás — sin romper la transacción ni el aviso en la bandeja."""
        from pywebpush import WebPushException

        # VAPID configurado para que el motor intente enviar
        monkeypatch.setenv("VAPID_PUBLIC_KEY", "clave-publica-test")
        monkeypatch.setenv("VAPID_PRIVATE_KEY", "clave-privada-test")
        monkeypatch.setenv("VAPID_SUBJECT", "mailto:dev@oikos.app")

        endpoint_caduca = "https://push.example.com/fcm/suscripcion-caducada"
        endpoint_viva = "https://push.example.com/fcm/suscripcion-viva"
        suscripcion_caducada = client.post(
            "/api/v1/push/subscribe", json=_payload(endpoint_caduca), headers=auth_headers
        ).json()
        suscripcion_viva = client.post(
            "/api/v1/push/subscribe", json=_payload(endpoint_viva), headers=auth_headers
        ).json()

        envios: list[str] = []

        class _FakeResponse:
            status_code = 410

        def _fake_webpush(subscription_info, data, vapid_private_key, vapid_claims, **kwargs):
            envios.append(subscription_info["endpoint"])
            if subscription_info["endpoint"] == endpoint_caduca:
                raise WebPushException("Suscripción receptora no encontrada (410)", response=_FakeResponse())
            return None

        monkeypatch.setattr("app.core.notification_dispatch.webpush", _fake_webpush)

        cuenta = make_account(auth_headers, balance="100000.00")
        categoria = make_category(auth_headers, name="Comida", type="expense")
        now = datetime.now(UTC)
        presupuesto = client.post(
            "/api/v1/budgets/",
            json={
                "amount_limit": "1000.00",
                "currency": "COP",
                "month": now.month,
                "year": now.year,
                "category_id": categoria["id"],
            },
            headers=auth_headers,
        ).json()

        # Cruza el 80% → el motor crea el aviso y dispara el push a ambas suscripciones
        response = client.post(
            "/api/v1/transactions/",
            json={
                "amount": "820.00",
                "type": "expense",
                "account_id": cuenta["id"],
                "category_id": categoria["id"],
            },
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text

        # Ambas suscripciones recibieron el intento de envío
        assert set(envios) == {endpoint_caduca, endpoint_viva}

        # La caducada se borró; la viva sigue
        assert db_session.get(models.PushSubscription, suscripcion_caducada["id"]) is None
        assert db_session.get(models.PushSubscription, suscripcion_viva["id"]) is not None

        # El aviso quedó en la bandeja in-app (el push es canal adicional, no alternativo)
        bandeja = client.get("/api/v1/notifications/", headers=auth_headers).json()
        assert len(bandeja["items"]) == 1
        assert bandeja["items"][0]["budget_id"] == presupuesto["id"]

    def test_without_vapid_config_transaction_and_inapp_notification_still_work(
        self, client, auth_headers, make_account, make_category, monkeypatch, db_session
    ):
        """Criterio de aceptación: sin VAPID configurado, el flujo no se rompe — el aviso
        queda en la bandeja y la transacción se guarda (fallo silencioso con log, mismo
        criterio que app/core/email.py con SMTP)."""
        monkeypatch.delenv("VAPID_PUBLIC_KEY", raising=False)
        monkeypatch.delenv("VAPID_PRIVATE_KEY", raising=False)
        monkeypatch.delenv("VAPID_SUBJECT", raising=False)

        cuenta = make_account(auth_headers, balance="100000.00")
        categoria = make_category(auth_headers, name="Comida", type="expense")
        now = datetime.now(UTC)
        client.post(
            "/api/v1/budgets/",
            json={
                "amount_limit": "1000.00",
                "currency": "COP",
                "month": now.month,
                "year": now.year,
                "category_id": categoria["id"],
            },
            headers=auth_headers,
        )

        response = client.post(
            "/api/v1/transactions/",
            json={
                "amount": "850.00",
                "type": "expense",
                "account_id": cuenta["id"],
                "category_id": categoria["id"],
            },
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text

        bandeja = client.get("/api/v1/notifications/", headers=auth_headers).json()
        assert len(bandeja["items"]) == 1
        assert bandeja["items"][0]["type"] == "budget_threshold_80"
