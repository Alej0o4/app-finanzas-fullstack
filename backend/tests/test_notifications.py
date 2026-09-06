"""Tests de la bandeja de notificaciones (Fase 13 §13.5).

Los endpoints de `/api/v1/notifications` (listar, unread-count, marcar leída,
marcar todo leído) se prueban sobre el flujo real: se crea un presupuesto y un
gasto que cruza el umbral del 80 % para que el motor de §13.3 produzca la
notificación, y luego se ejercita la bandeja.
"""

from datetime import UTC, datetime


def _now_month_year() -> tuple[int, int]:
    now = datetime.now(UTC)
    return now.month, now.year


def _crear_notificacion_via_umbral(client, headers: dict, make_account, make_category) -> dict:
    """Crea presupuesto + gasto de 850/1000 (85 %) y devuelve la notificación generada."""
    cuenta = make_account(headers, balance="100000.00")
    categoria = make_category(headers, name="Ocio", type="expense")
    month, year = _now_month_year()
    response = client.post(
        "/api/v1/budgets/",
        json={
            "amount_limit": "1000.00",
            "currency": "COP",
            "month": month,
            "year": year,
            "category_id": categoria["id"],
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text

    response = client.post(
        "/api/v1/transactions/",
        json={
            "amount": "850.00",
            "type": "expense",
            "account_id": cuenta["id"],
            "category_id": categoria["id"],
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text

    items = client.get("/api/v1/notifications/", headers=headers).json()["items"]
    assert len(items) == 1
    return items[0]


class TestNotificationsBandeja:
    def test_list_is_paginated_shape_with_most_recent_first(self, client, auth_headers, make_account, make_category):
        primera = _crear_notificacion_via_umbral(client, auth_headers, make_account, make_category)

        # Segunda notificación del mismo presupuesto: segundo umbral imposible por mes,
        # así que se fuerza un segundo par presupuesto/gasto en otra categoría
        categoria2 = make_category(auth_headers, name="Ropa", type="expense")
        cuenta = make_account(auth_headers, name="Cuenta 2", balance="100000.00")
        month, year = _now_month_year()
        client.post(
            "/api/v1/budgets/",
            json={
                "amount_limit": "1000.00",
                "currency": "COP",
                "month": month,
                "year": year,
                "category_id": categoria2["id"],
            },
            headers=auth_headers,
        )
        client.post(
            "/api/v1/transactions/",
            json={
                "amount": "900.00",
                "type": "expense",
                "account_id": cuenta["id"],
                "category_id": categoria2["id"],
            },
            headers=auth_headers,
        )

        response = client.get("/api/v1/notifications/", headers=auth_headers)
        assert response.status_code == 200
        bandeja = response.json()
        assert set(bandeja.keys()) == {"items", "total", "page", "page_size"}
        assert bandeja["total"] == 2
        assert bandeja["page"] == 1
        assert bandeja["page_size"] == 50
        # Más recientes primero: la del 90 % se creó después de la del 85 %
        assert bandeja["items"][0]["id"] > bandeja["items"][1]["id"]
        assert bandeja["items"][1]["id"] == primera["id"]

    def test_unread_count_starts_at_one_and_read_clears_it(self, client, auth_headers, make_account, make_category):
        notificacion = _crear_notificacion_via_umbral(client, auth_headers, make_account, make_category)

        assert client.get("/api/v1/notifications/unread-count", headers=auth_headers).json() == {"count": 1}

        response = client.patch(f"/api/v1/notifications/{notificacion['id']}/read", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["read_at"] is not None
        assert response.json()["id"] == notificacion["id"]

        # Leer una notificación ya leída es idempotente
        response = client.patch(f"/api/v1/notifications/{notificacion['id']}/read", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["read_at"] is not None

        assert client.get("/api/v1/notifications/unread-count", headers=auth_headers).json() == {"count": 0}

    def test_read_all_marks_everything_and_is_idempotent(self, client, auth_headers, make_account, make_category):
        _crear_notificacion_via_umbral(client, auth_headers, make_account, make_category)
        categoria2 = make_category(auth_headers, name="Ropa", type="expense")
        cuenta = make_account(auth_headers, name="Cuenta 2", balance="100000.00")
        month, year = _now_month_year()
        client.post(
            "/api/v1/budgets/",
            json={
                "amount_limit": "1000.00",
                "currency": "COP",
                "month": month,
                "year": year,
                "category_id": categoria2["id"],
            },
            headers=auth_headers,
        )
        client.post(
            "/api/v1/transactions/",
            json={
                "amount": "900.00",
                "type": "expense",
                "account_id": cuenta["id"],
                "category_id": categoria2["id"],
            },
            headers=auth_headers,
        )

        assert client.get("/api/v1/notifications/unread-count", headers=auth_headers).json() == {"count": 2}
        # La respuesta es el NUEVO conteo de no leídas (0 tras marcar todo)
        response = client.patch("/api/v1/notifications/read-all", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == {"count": 0}

        assert client.get("/api/v1/notifications/unread-count", headers=auth_headers).json() == {"count": 0}
        # Idempotente: no hay leídas nuevas que marcar
        assert client.patch("/api/v1/notifications/read-all", headers=auth_headers).json() == {"count": 0}

    def test_users_cannot_mark_or_list_foreign_notifications(
        self, client, auth_headers, other_user, make_account, make_category
    ):
        notificacion = _crear_notificacion_via_umbral(client, auth_headers, make_account, make_category)

        # PATCH con token ajeno → 404 (mismo criterio que el resto del API: no filtrar por ownership)
        response = client.patch(f"/api/v1/notifications/{notificacion['id']}/read", headers=other_user["headers"])
        assert response.status_code == 404

        # La bandeja ajena no ve las notificaciones del otro usuario
        bandeja = client.get("/api/v1/notifications/", headers=other_user["headers"]).json()
        assert bandeja == {"items": [], "total": 0, "page": 1, "page_size": 50}

        # El leído ajeno no alteró el estado del dueño
        assert client.get("/api/v1/notifications/unread-count", headers=auth_headers).json() == {"count": 1}
