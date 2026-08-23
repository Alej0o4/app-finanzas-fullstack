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
