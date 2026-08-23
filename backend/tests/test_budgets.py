"""Tests de presupuestos: la unique constraint (§1.4 del spec) y el cálculo de progreso
(`spent`/`percentage`) que consume `dashboard.py::obtener_progreso_presupuestos`.
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import models


def _now_month_year() -> tuple[int, int]:
    now = datetime.now(UTC)
    return now.month, now.year


def _previous_month_year() -> tuple[int, int]:
    now = datetime.now(UTC)
    if now.month == 1:
        return 12, now.year - 1
    return now.month - 1, now.year


class TestBudgetUniqueConstraint:
    def test_duplicate_budget_via_api_returns_400_not_500_and_no_duplicate_row(
        self, client, auth_headers, make_category
    ):
        categoria = make_category(auth_headers, name="Ocio", type="expense")
        month, year = _now_month_year()
        payload = {
            "amount_limit": "500000.00",
            "currency": "COP",
            "month": month,
            "year": year,
            "category_id": categoria["id"],
        }

        first = client.post("/api/v1/budgets/", json=payload, headers=auth_headers)
        assert first.status_code == 200, first.text

        second = client.post("/api/v1/budgets/", json=payload, headers=auth_headers)
        assert second.status_code == 400
        assert second.status_code != 500

        listado = client.get("/api/v1/budgets/", params={"month": month, "year": year}, headers=auth_headers)
        assert listado.status_code == 200
        coincidencias = [b for b in listado.json() if b["category_id"] == categoria["id"]]
        assert len(coincidencias) == 1

    def test_db_level_unique_constraint_rejects_duplicate_row(self, db_session, client, auth_headers, make_category):
        """Prueba la constraint de la base en sí (no solo el chequeo en Python de
        `crear_presupuesto`), insertando directo con la sesión de test — así el test sigue
        siendo válido aunque el pre-chequeo de la app cambie o se retire."""
        categoria = make_category(auth_headers, name="Transporte", type="expense")
        month, year = _now_month_year()
        user_id = client.get("/api/v1/users/me", headers=auth_headers).json()["id"]

        db_session.add(
            models.Budget(
                amount_limit=Decimal("100.00"),
                currency="COP",
                month=month,
                year=year,
                user_id=user_id,
                category_id=categoria["id"],
            )
        )
        db_session.commit()

        db_session.add(
            models.Budget(
                amount_limit=Decimal("200.00"),
                currency="COP",
                month=month,
                year=year,
                user_id=user_id,
                category_id=categoria["id"],
            )
        )
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()


class TestBudgetProgress:
    def test_spent_and_percentage_calculated_against_real_transactions(
        self, client, auth_headers, make_account, make_category
    ):
        cuenta = make_account(auth_headers, balance="10000.00")
        categoria = make_category(auth_headers, name="Comida", type="expense")
        month, year = _now_month_year()

        budget_response = client.post(
            "/api/v1/budgets/",
            json={
                "amount_limit": "1000.00",
                "currency": "COP",
                "month": month,
                "year": year,
                "category_id": categoria["id"],
            },
            headers=auth_headers,
        )
        assert budget_response.status_code == 200, budget_response.text
        budget_id = budget_response.json()["id"]

        for amount in ("100.00", "200.00"):
            tx_response = client.post(
                "/api/v1/transactions/",
                json={
                    "amount": amount,
                    "type": "expense",
                    "account_id": cuenta["id"],
                    "category_id": categoria["id"],
                },
                headers=auth_headers,
            )
            assert tx_response.status_code == 200, tx_response.text

        progress_response = client.get("/api/v1/dashboard/budgets-progress", headers=auth_headers)
        assert progress_response.status_code == 200, progress_response.text

        progreso = next(p for p in progress_response.json() if p["budget_id"] == budget_id)
        assert Decimal(str(progreso["spent"])) == Decimal("300.00")
        assert progreso["percentage"] == pytest.approx(30.0)

    def test_budget_without_transactions_has_zero_spent(self, client, auth_headers, make_category):
        categoria = make_category(auth_headers, name="Salud", type="expense")
        month, year = _now_month_year()

        budget_response = client.post(
            "/api/v1/budgets/",
            json={
                "amount_limit": "500.00",
                "currency": "COP",
                "month": month,
                "year": year,
                "category_id": categoria["id"],
            },
            headers=auth_headers,
        )
        budget_id = budget_response.json()["id"]

        progress_response = client.get("/api/v1/dashboard/budgets-progress", headers=auth_headers)
        progreso = next(p for p in progress_response.json() if p["budget_id"] == budget_id)
        assert Decimal(str(progreso["spent"])) == Decimal("0.00")
        assert progreso["percentage"] == 0


class TestRecurringBudgets:
    """Fase 8 §3: generación perezosa por fila (Decisión 3.1).

    Los tests de generación usan períodos fijos (2030) para ser deterministas; el único
    test anclado a "hoy" es el del dashboard, que por diseño siempre opera sobre el
    período actual.
    """

    def _crear_presupuesto(self, client, auth_headers, categoria, month, year, amount="800.00", recurring=True):
        response = client.post(
            "/api/v1/budgets/",
            json={
                "amount_limit": amount,
                "currency": "COP",
                "month": month,
                "year": year,
                "category_id": categoria["id"],
                "is_recurring": recurring,
            },
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        return response.json()

    def test_recurring_template_generates_period_via_list_endpoint(self, client, auth_headers, make_category):
        categoria = make_category(auth_headers, name="Mercado", type="expense")
        self._crear_presupuesto(client, auth_headers, categoria, month=1, year=2030)

        generados = client.get("/api/v1/budgets/", params={"month": 2, "year": 2030}, headers=auth_headers)
        assert generados.status_code == 200, generados.text

        filas = [b for b in generados.json() if b["category_id"] == categoria["id"]]
        assert len(filas) == 1
        assert Decimal(str(filas[0]["amount_limit"])) == Decimal("800.00")
        assert filas[0]["is_recurring"] is True  # la copia también es plantilla

    def test_recurring_template_generates_current_period_via_dashboard_progress(
        self, client, auth_headers, make_category
    ):
        categoria = make_category(auth_headers, name="Transporte", type="expense")
        prev_month, prev_year = _previous_month_year()
        self._crear_presupuesto(client, auth_headers, categoria, month=prev_month, year=prev_year)

        # El dashboard genera el período actual antes de consultar (página de aterrizaje)
        progress_response = client.get("/api/v1/dashboard/budgets-progress", headers=auth_headers)
        assert progress_response.status_code == 200, progress_response.text
        progreso = [p for p in progress_response.json() if p["category_name"] == categoria["name"]]
        assert len(progreso) == 1
        assert Decimal(str(progreso[0]["amount_limit"])) == Decimal("800.00")

        month, year = _now_month_year()
        listado = client.get("/api/v1/budgets/", params={"month": month, "year": year}, headers=auth_headers)
        fila_actual = [b for b in listado.json() if b["category_id"] == categoria["id"]]
        assert len(fila_actual) == 1
        assert fila_actual[0]["is_recurring"] is True

    def test_repeated_requests_for_same_period_do_not_duplicate_generated_budget(
        self, client, auth_headers, make_category
    ):
        categoria = make_category(auth_headers, name="Salud", type="expense")
        self._crear_presupuesto(client, auth_headers, categoria, month=1, year=2030)

        for _ in range(2):
            response = client.get("/api/v1/budgets/", params={"month": 2, "year": 2030}, headers=auth_headers)
            assert response.status_code == 200, response.text

        filas = [b for b in response.json() if b["category_id"] == categoria["id"]]
        assert len(filas) == 1

    def test_non_recurring_budget_does_not_regenerate_next_period(self, client, auth_headers, make_category):
        categoria = make_category(auth_headers, name="Suscripciones", type="expense")
        self._crear_presupuesto(client, auth_headers, categoria, month=1, year=2030, recurring=False)

        response = client.get("/api/v1/budgets/", params={"month": 2, "year": 2030}, headers=auth_headers)
        assert response.status_code == 200, response.text

        filas = [b for b in response.json() if b["category_id"] == categoria["id"]]
        assert filas == []

    def test_edited_amount_limit_is_used_as_new_template(self, client, auth_headers, make_category):
        categoria = make_category(auth_headers, name="Educación", type="expense")
        self._crear_presupuesto(client, auth_headers, categoria, month=1, year=2030)

        febrero = client.get("/api/v1/budgets/", params={"month": 2, "year": 2030}, headers=auth_headers).json()
        fila_febrero = next(b for b in febrero if b["category_id"] == categoria["id"])

        edicion = client.put(
            f"/api/v1/budgets/{fila_febrero['id']}",
            json={
                "amount_limit": "1200.00",
                "currency": "COP",
                "month": 2,
                "year": 2030,
                "category_id": categoria["id"],
                "is_recurring": True,
            },
            headers=auth_headers,
        )
        assert edicion.status_code == 200, edicion.text

        marzo = client.get("/api/v1/budgets/", params={"month": 3, "year": 2030}, headers=auth_headers).json()
        fila_marzo = next(b for b in marzo if b["category_id"] == categoria["id"])
        assert Decimal(str(fila_marzo["amount_limit"])) == Decimal("1200.00")

    def test_is_recurring_defaults_to_false_when_omitted(self, client, auth_headers, make_category):
        categoria = make_category(auth_headers, name="Ocio", type="expense")

        response = client.post(
            "/api/v1/budgets/",
            json={
                "amount_limit": "800.00",
                "currency": "COP",
                "month": 5,
                "year": 2030,
                "category_id": categoria["id"],
            },
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["is_recurring"] is False
