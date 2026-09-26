"""Tests de dashboard (Fase 11): corrección de los 3 bugs multi-moneda restantes
(budgets-progress, cashflow-series, category-distribution) y del nuevo campo
monthly_flow_balance en /summary.

Hasta Fase 11 no existía ningún test de app/api/dashboard.py (hallazgo 11 del spec
de Fase 11) — este archivo cierra esa deuda además de cubrir los fixes.

Fase 29 (Decisiones B2/B3/B6/B7, T2-T5/T7) suma la navegación por mes: los tests
nuevos viven al final del archivo y las clases de Fase 11 quedan intactas como
regresión de "sin parámetros se comporta igual que hoy" (User Story 47).
"""

from calendar import monthrange
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from app.models import models


def _now_month_year() -> tuple[int, int]:
    now = datetime.now(UTC)
    return now.month, now.year


def _previous_month_year() -> tuple[int, int]:
    """Mes anterior con rollover de enero (mismo patrón que tests/test_budgets.py)."""
    now = datetime.now(UTC)
    if now.month == 1:
        return 12, now.year - 1
    return now.month - 1, now.year


def _fecha_en_mes(year: int, month: int, dia: int) -> str:
    """Fecha ISO naive a las 00:00 dentro del mes pedido — el mismo formato que usan los
    helpers de `test_budget_alerts.py`. El día 10 nunca cae en el borde del cambio de mes,
    que es el riesgo al que sí está expuesto el día 1."""
    return datetime(year, month, dia).isoformat()


def _soft_delete_via_raw_sql(db_session, tabla: str, fila_id: int) -> None:
    """Fabrica el estado 'fila borrada' por SQL crudo, fuera del alcance del filtro ORM
    (mismo helper que tests/test_soft_delete.py: los endpoints DELETE tienen guards,
    p. ej. cuenta con transacciones, que impiden llegar a este estado intermedio)."""
    db_session.execute(sa.text(f"UPDATE {tabla} SET deleted_at = CURRENT_TIMESTAMP WHERE id = :id"), {"id": fila_id})
    db_session.commit()


def _current_month_range_params() -> dict:
    """Rango del mes en curso (mismas cotas que usa el backend internamente) para los
    endpoints que reciben start_date/end_date por query."""
    hoy = datetime.now(UTC)
    primer_dia = datetime(hoy.year, hoy.month, 1, tzinfo=UTC)
    if hoy.month == 12:
        siguiente = datetime(hoy.year + 1, 1, 1, tzinfo=UTC)
    else:
        siguiente = datetime(hoy.year, hoy.month + 1, 1, tzinfo=UTC)
    # retrocede lo justo para quedar dentro del mes aunque la creación de la tx y el
    # fin de mes coincidan al segundo
    ultimo_momento = siguiente.timestamp() - 1
    ultimo_dia = datetime.fromtimestamp(ultimo_momento, tz=UTC)
    return {
        "start_date": primer_dia.isoformat(),
        "end_date": ultimo_dia.isoformat(),
    }


def _create_transaction(client: TestClient, headers: dict, **overrides) -> dict:
    payload = {
        "amount": "100.00",
        "type": "expense",
        "description": "tx de prueba",
    }
    payload.update(overrides)
    response = client.post("/api/v1/transactions/", json=payload, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _create_budget(client: TestClient, headers: dict, **overrides) -> dict:
    """Presupuesto vía `POST /budgets/`, por defecto en el mes EN CURSO (el período por
    defecto de la app). Los tests de mes pasado sobrescriben `month`/`year`."""
    month, year = _now_month_year()
    payload = {"amount_limit": "200000.00", "currency": "COP", "month": month, "year": year}
    payload.update(overrides)
    response = client.post("/api/v1/budgets/", json=payload, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _get_summary(client: TestClient, headers: dict, year=None, month=None) -> dict:
    params = {k: v for k, v in {"year": year, "month": month}.items() if v is not None}
    response = client.get("/api/v1/dashboard/summary", params=params, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _set_monthly_income(client: TestClient, headers: dict, amount: str) -> None:
    response = client.patch("/api/v1/users/me", json={"monthly_income": amount}, headers=headers)
    assert response.status_code == 200, response.text


def _create_cop_and_usd_accounts(make_account, auth_headers: dict) -> tuple[dict, dict]:
    cuenta_cop = make_account(auth_headers, name="Cuenta COP", currency="COP", balance="1000000.00")
    cuenta_usd = make_account(auth_headers, name="Cuenta USD", currency="USD", balance="1000.00")
    return cuenta_cop, cuenta_usd


class TestBudgetsProgressCurrency:
    def test_budget_in_cop_only_counts_cop_expenses_of_same_category(
        self, client, auth_headers, make_account, make_category
    ):
        """Fase 11 §11.1: gastos en USD de la misma categoría no contaminan el progreso
        de un presupuesto denominado en COP (antes se sumaban todas las monedas)."""
        cuenta_cop, cuenta_usd = _create_cop_and_usd_accounts(make_account, auth_headers)
        categoria = make_category(auth_headers, name="Comida", type="expense")
        month, year = _now_month_year()

        budget_response = client.post(
            "/api/v1/budgets/",
            json={
                "amount_limit": "200000.00",
                "currency": "COP",
                "month": month,
                "year": year,
                "category_id": categoria["id"],
            },
            headers=auth_headers,
        )
        assert budget_response.status_code == 200, budget_response.text
        budget_id = budget_response.json()["id"]

        _create_transaction(
            client,
            auth_headers,
            amount="50000.00",
            type="expense",
            account_id=cuenta_cop["id"],
            category_id=categoria["id"],
        )
        _create_transaction(
            client,
            auth_headers,
            amount="100.00",
            type="expense",
            account_id=cuenta_usd["id"],
            category_id=categoria["id"],
        )

        progress_response = client.get("/api/v1/dashboard/budgets-progress", headers=auth_headers)
        assert progress_response.status_code == 200, progress_response.text

        progreso = next(p for p in progress_response.json() if p["budget_id"] == budget_id)
        # Solo el gasto COP: los 100 USD de la misma categoría quedan fuera del balde
        assert Decimal(str(progreso["spent"])) == Decimal("50000.00")
        assert progreso["percentage"] == pytest.approx(25.0)
        # Y la fila expone la moneda real del presupuesto (Decisión 11.1.2)
        assert progreso["currency"] == "COP"

    def test_currency_param_filters_rows_without_recalculating_spent(
        self, client, auth_headers, make_account, make_category
    ):
        """Fase 17 §17.2.3 (Decisión P4): `currency` SOLO filtra filas — NO recalcula
        `spent`. Dos presupuestos de la misma categoría en monedas distintas con gastos
        en ambas: `?currency=USD` devuelve solo la fila USD, con el mismo `spent` que la
        misma fila sin filtro."""
        cuenta_cop, cuenta_usd = _create_cop_and_usd_accounts(make_account, auth_headers)
        categoria = make_category(auth_headers, name="Comida", type="expense")
        month, year = _now_month_year()

        cop = client.post(
            "/api/v1/budgets/",
            json={
                "amount_limit": "200000.00",
                "currency": "COP",
                "month": month,
                "year": year,
                "category_id": categoria["id"],
            },
            headers=auth_headers,
        )
        usd = client.post(
            "/api/v1/budgets/",
            json={
                "amount_limit": "1000.00",
                "currency": "USD",
                "month": month,
                "year": year,
                "category_id": categoria["id"],
            },
            headers=auth_headers,
        )
        assert cop.status_code == 200, cop.text
        assert usd.status_code == 200, usd.text
        budget_usd_id = usd.json()["id"]

        _create_transaction(
            client,
            auth_headers,
            amount="50000.00",
            type="expense",
            account_id=cuenta_cop["id"],
            category_id=categoria["id"],
        )
        _create_transaction(
            client,
            auth_headers,
            amount="300.00",
            type="expense",
            account_id=cuenta_usd["id"],
            category_id=categoria["id"],
        )

        # Sin filtro: ambas filas, cada una con el spent de SU moneda
        completo = client.get("/api/v1/dashboard/budgets-progress", headers=auth_headers)
        assert completo.status_code == 200, completo.text
        assert len(completo.json()) == 2
        fila_usd_sin_filtro = next(p for p in completo.json() if p["budget_id"] == budget_usd_id)
        assert Decimal(str(fila_usd_sin_filtro["spent"])) == Decimal("300.00")

        # Con filtro USD: solo la fila USD, con el MISMO spent (sin recálculo)
        filtrado = client.get("/api/v1/dashboard/budgets-progress", params={"currency": "USD"}, headers=auth_headers)
        assert filtrado.status_code == 200, filtrado.text
        filas = filtrado.json()
        assert len(filas) == 1
        assert filas[0]["budget_id"] == budget_usd_id
        assert Decimal(str(filas[0]["spent"])) == Decimal("300.00")
        assert filas[0]["spent"] == fila_usd_sin_filtro["spent"]


class TestCashflowSeriesCurrency:
    def test_default_series_corresponds_only_to_preferred_currency(
        self, client, auth_headers, make_account, make_category
    ):
        """Sin pasar `currency`, la serie corresponde solo a la moneda preferida
        (default COP) — las transacciones USD del mismo día no se mezclan."""
        cuenta_cop, cuenta_usd = _create_cop_and_usd_accounts(make_account, auth_headers)
        categoria_gasto = make_category(auth_headers, name="Comida", type="expense")
        categoria_ingreso = make_category(auth_headers, name="Salario", type="income")

        _create_transaction(
            client,
            auth_headers,
            amount="200000.00",
            type="income",
            account_id=cuenta_cop["id"],
            category_id=categoria_ingreso["id"],
        )
        _create_transaction(
            client,
            auth_headers,
            amount="50000.00",
            type="expense",
            account_id=cuenta_cop["id"],
            category_id=categoria_gasto["id"],
        )
        _create_transaction(
            client,
            auth_headers,
            amount="100.00",
            type="expense",
            account_id=cuenta_usd["id"],
            category_id=categoria_gasto["id"],
        )

        response = client.get(
            "/api/v1/dashboard/cashflow-series",
            params=_current_month_range_params(),
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text

        serie = response.json()
        assert len(serie) == 1  # mismo día → una sola entrada, sin duplicar por moneda
        assert Decimal(str(serie[0]["income"])) == Decimal("200000.00")
        # Pre-fix aquí se verían 50100.00 (los 100 USD sumados al gasto COP)
        assert Decimal(str(serie[0]["expense"])) == Decimal("50000.00")

    def test_explicit_currency_param_filters_to_that_currency(self, client, auth_headers, make_account, make_category):
        cuenta_cop, cuenta_usd = _create_cop_and_usd_accounts(make_account, auth_headers)
        categoria_gasto = make_category(auth_headers, name="Comida", type="expense")
        categoria_ingreso = make_category(auth_headers, name="Salario", type="income")

        _create_transaction(
            client,
            auth_headers,
            amount="200000.00",
            type="income",
            account_id=cuenta_cop["id"],
            category_id=categoria_ingreso["id"],
        )
        _create_transaction(
            client,
            auth_headers,
            amount="100.00",
            type="expense",
            account_id=cuenta_usd["id"],
            category_id=categoria_gasto["id"],
        )

        response = client.get(
            "/api/v1/dashboard/cashflow-series",
            params={**_current_month_range_params(), "currency": "USD"},
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text

        serie = response.json()
        assert len(serie) == 1
        assert Decimal(str(serie[0]["expense"])) == Decimal("100.00")
        assert Decimal(str(serie[0]["income"])) == Decimal("0")


class TestCashflowSeriesAccountFilter:
    """Corrección UX post-Fase 19: analítica no tenía forma de ver el flujo de una sola
    cuenta. `account_id` opcional en cashflow-series, mismo patrón de ownership que
    category-distribution (Fase 17 §17.1.3) — 404 si la cuenta es ajena."""

    def test_account_id_returns_only_that_account_series(self, client, auth_headers, make_account, make_category):
        cuenta_a = make_account(auth_headers, name="Cuenta A", currency="COP", balance="1000000.00")
        cuenta_b = make_account(auth_headers, name="Cuenta B", currency="COP", balance="1000000.00")
        categoria = make_category(auth_headers, name="Comida", type="expense")

        _create_transaction(
            client,
            auth_headers,
            amount="70000.00",
            type="expense",
            account_id=cuenta_a["id"],
            category_id=categoria["id"],
        )
        _create_transaction(
            client,
            auth_headers,
            amount="20000.00",
            type="expense",
            account_id=cuenta_b["id"],
            category_id=categoria["id"],
        )

        rango = _current_month_range_params()

        solo_a = client.get(
            "/api/v1/dashboard/cashflow-series",
            params={**rango, "account_id": cuenta_a["id"]},
            headers=auth_headers,
        )
        assert solo_a.status_code == 200, solo_a.text
        serie_a = solo_a.json()
        assert len(serie_a) == 1
        assert Decimal(str(serie_a[0]["expense"])) == Decimal("70000.00")

        solo_b = client.get(
            "/api/v1/dashboard/cashflow-series",
            params={**rango, "account_id": cuenta_b["id"]},
            headers=auth_headers,
        )
        assert solo_b.status_code == 200, solo_b.text
        serie_b = solo_b.json()
        assert len(serie_b) == 1
        assert Decimal(str(serie_b[0]["expense"])) == Decimal("20000.00")

    def test_foreign_account_id_returns_404(self, client, auth_headers, other_user, make_account):
        cuenta_ajena = make_account(other_user["headers"], balance="1000.00")
        rango = _current_month_range_params()

        response = client.get(
            "/api/v1/dashboard/cashflow-series",
            params={**rango, "account_id": cuenta_ajena["id"]},
            headers=auth_headers,
        )
        assert response.status_code == 404


class TestCategoryDistributionCurrency:
    def test_neto_false_default_filters_to_preferred_currency(self, client, auth_headers, make_account, make_category):
        cuenta_cop, cuenta_usd = _create_cop_and_usd_accounts(make_account, auth_headers)
        categoria_comida = make_category(auth_headers, name="Comida", type="expense")
        categoria_transporte = make_category(auth_headers, name="Transporte", type="expense")

        _create_transaction(
            client,
            auth_headers,
            amount="70000.00",
            type="expense",
            account_id=cuenta_cop["id"],
            category_id=categoria_comida["id"],
        )
        _create_transaction(
            client,
            auth_headers,
            amount="300.00",
            type="expense",
            account_id=cuenta_usd["id"],
            category_id=categoria_comida["id"],
        )
        _create_transaction(
            client,
            auth_headers,
            amount="20000.00",
            type="expense",
            account_id=cuenta_cop["id"],
            category_id=categoria_transporte["id"],
        )

        response = client.get(
            "/api/v1/dashboard/category-distribution",
            params=_current_month_range_params(),
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text

        filas = response.json()
        assert len(filas) == 2
        # Orden descendente por monto; Comida solo refleja su gasto COP (pre-fix: 70300.00)
        assert filas[0]["category_name"] == "Comida"
        assert Decimal(str(filas[0]["total"])) == Decimal("70000.00")
        assert Decimal(str(filas[1]["total"])) == Decimal("20000.00")

    def test_neto_false_explicit_currency_param(self, client, auth_headers, make_account, make_category):
        cuenta_cop, cuenta_usd = _create_cop_and_usd_accounts(make_account, auth_headers)
        categoria_comida = make_category(auth_headers, name="Comida", type="expense")

        _create_transaction(
            client,
            auth_headers,
            amount="70000.00",
            type="expense",
            account_id=cuenta_cop["id"],
            category_id=categoria_comida["id"],
        )
        _create_transaction(
            client,
            auth_headers,
            amount="300.00",
            type="expense",
            account_id=cuenta_usd["id"],
            category_id=categoria_comida["id"],
        )

        response = client.get(
            "/api/v1/dashboard/category-distribution",
            params={**_current_month_range_params(), "currency": "USD"},
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text

        filas = response.json()
        assert len(filas) == 1
        assert filas[0]["category_name"] == "Comida"
        assert Decimal(str(filas[0]["total"])) == Decimal("300.00")

    def test_neto_true_default_filters_to_preferred_currency(self, client, auth_headers, make_account, make_category):
        """Rama neto=true: gasto neto (expense - income) calculado solo con la moneda
        preferida; categorías con neto negativo o cero en esa moneda no aparecen."""
        cuenta_cop, cuenta_usd = _create_cop_and_usd_accounts(make_account, auth_headers)
        categoria_comida = make_category(auth_headers, name="Comida", type="expense")
        categoria_servicios = make_category(auth_headers, name="Servicios", type="expense")

        # Comida en COP: neto 50000 - 10000 = 40000 (el neto es por categoría)
        _create_transaction(
            client,
            auth_headers,
            amount="50000.00",
            type="expense",
            account_id=cuenta_cop["id"],
            category_id=categoria_comida["id"],
        )
        _create_transaction(
            client,
            auth_headers,
            amount="10000.00",
            type="income",
            account_id=cuenta_cop["id"],
            category_id=categoria_comida["id"],
        )
        # Comida en USD: neto 300 - 250 = 50 (debe quedar fuera del default COP)
        _create_transaction(
            client,
            auth_headers,
            amount="300.00",
            type="expense",
            account_id=cuenta_usd["id"],
            category_id=categoria_comida["id"],
        )
        _create_transaction(
            client,
            auth_headers,
            amount="250.00",
            type="income",
            account_id=cuenta_usd["id"],
            category_id=categoria_comida["id"],
        )
        # Servicios en COP: neto negativo (8000 - 90000) → excluida por HAVING > 0
        _create_transaction(
            client,
            auth_headers,
            amount="8000.00",
            type="expense",
            account_id=cuenta_cop["id"],
            category_id=categoria_servicios["id"],
        )
        _create_transaction(
            client,
            auth_headers,
            amount="90000.00",
            type="income",
            account_id=cuenta_cop["id"],
            category_id=categoria_servicios["id"],
        )

        response = client.get(
            "/api/v1/dashboard/category-distribution",
            params={**_current_month_range_params(), "neto": True},
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text

        filas = response.json()
        # Pre-fix el neto de Comida habría sido 50300 - 100250 = -49950 (mezclado) y
        # Servicios habría absorbido los movimientos USD; con el filtro queda solo Comida.
        assert len(filas) == 1
        assert filas[0]["category_name"] == "Comida"
        assert Decimal(str(filas[0]["total"])) == Decimal("40000.00")

    def test_neto_true_explicit_currency_param(self, client, auth_headers, make_account, make_category):
        cuenta_cop, cuenta_usd = _create_cop_and_usd_accounts(make_account, auth_headers)
        categoria_comida = make_category(auth_headers, name="Comida", type="expense")

        _create_transaction(
            client,
            auth_headers,
            amount="50000.00",
            type="expense",
            account_id=cuenta_cop["id"],
            category_id=categoria_comida["id"],
        )
        _create_transaction(
            client,
            auth_headers,
            amount="300.00",
            type="expense",
            account_id=cuenta_usd["id"],
            category_id=categoria_comida["id"],
        )
        _create_transaction(
            client,
            auth_headers,
            amount="250.00",
            type="income",
            account_id=cuenta_usd["id"],
            category_id=categoria_comida["id"],
        )

        response = client.get(
            "/api/v1/dashboard/category-distribution",
            params={**_current_month_range_params(), "neto": True, "currency": "USD"},
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text

        filas = response.json()
        assert len(filas) == 1
        assert Decimal(str(filas[0]["total"])) == Decimal("50.00")

    def test_response_includes_category_icon(self, client, auth_headers, db_session, make_account, make_category):
        """Fase 24 §24.4: category-distribution expone category_icon, igual que
        BudgetProgress. El endpoint POST /categories/ no acepta icon en el body
        (CategoryCreate no tiene ese campo, ver categories.py:22-41), así que el icon
        se fija directo en la sesión de test — mismo criterio que register_and_login
        fija email_verified directo (conftest.py:130)."""
        cuenta = make_account(auth_headers, currency="COP")
        categoria = make_category(auth_headers, name="Comida", type="expense")
        db_session.query(models.Category).filter(models.Category.id == categoria["id"]).update({"icon": "Utensils"})
        db_session.commit()

        _create_transaction(
            client,
            auth_headers,
            amount="10000.00",
            type="expense",
            account_id=cuenta["id"],
            category_id=categoria["id"],
        )

        response = client.get(
            "/api/v1/dashboard/category-distribution",
            params=_current_month_range_params(),
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        fila = response.json()[0]
        assert fila["category_icon"] == "Utensils"


class TestCategoryDistributionAccountFilter:
    """Fase 17 §17.1.3: `account_id` opcional en category-distribution, validado
    contra la propiedad de la cuenta (404 si es ajena). `currency` y `account_id`
    son ortogonales; los tests usan transacciones de la MISMA moneda para aislar
    el filtro por cuenta sin tocar el de moneda."""

    def test_account_id_returns_only_that_account_total(self, client, auth_headers, make_account, make_category):
        cuenta_a = make_account(auth_headers, name="Cuenta A", currency="COP", balance="1000000.00")
        cuenta_b = make_account(auth_headers, name="Cuenta B", currency="COP", balance="1000000.00")
        categoria = make_category(auth_headers, name="Comida", type="expense")

        _create_transaction(
            client,
            auth_headers,
            amount="70000.00",
            type="expense",
            account_id=cuenta_a["id"],
            category_id=categoria["id"],
        )
        _create_transaction(
            client,
            auth_headers,
            amount="20000.00",
            type="expense",
            account_id=cuenta_b["id"],
            category_id=categoria["id"],
        )

        rango = _current_month_range_params()

        solo_a = client.get(
            "/api/v1/dashboard/category-distribution",
            params={**rango, "account_id": cuenta_a["id"]},
            headers=auth_headers,
        )
        assert solo_a.status_code == 200, solo_a.text
        filas_a = solo_a.json()
        assert len(filas_a) == 1
        assert filas_a[0]["category_name"] == "Comida"
        assert Decimal(str(filas_a[0]["total"])) == Decimal("70000.00")

        solo_b = client.get(
            "/api/v1/dashboard/category-distribution",
            params={**rango, "account_id": cuenta_b["id"]},
            headers=auth_headers,
        )
        assert solo_b.status_code == 200, solo_b.text
        filas_b = solo_b.json()
        assert len(filas_b) == 1
        assert filas_b[0]["category_name"] == "Comida"
        assert Decimal(str(filas_b[0]["total"])) == Decimal("20000.00")

    def test_foreign_account_id_returns_404(self, client, auth_headers, other_user, make_account):
        cuenta_ajena = make_account(other_user["headers"], balance="1000.00")
        rango = _current_month_range_params()

        response = client.get(
            "/api/v1/dashboard/category-distribution",
            params={**rango, "account_id": cuenta_ajena["id"]},
            headers=auth_headers,
        )
        assert response.status_code == 404


class TestMonthlyFlowBalance:
    """Fase 11 §11.3: monthly_flow_balance en GET /dashboard/summary."""

    def test_user_without_monthly_income_gets_null(self, client, auth_headers, make_account):
        make_account(auth_headers, balance="1000.00")

        response = client.get("/api/v1/dashboard/summary", headers=auth_headers)
        assert response.status_code == 200, response.text

        resumen = response.json()
        assert resumen["monthly_flow_balance"] is None

    def test_with_income_and_no_expenses_returns_declared_income(self, client, auth_headers, make_account):
        make_account(auth_headers, balance="1000.00")
        _set_monthly_income(client, auth_headers, "1000000.00")

        response = client.get("/api/v1/dashboard/summary", headers=auth_headers)
        assert response.status_code == 200, response.text

        resumen = response.json()
        assert Decimal(str(resumen["monthly_flow_balance"])) == Decimal("1000000.00")

    def test_expenses_in_preferred_currency_are_subtracted(self, client, auth_headers, make_account, make_category):
        # Cuenta destacada: /summary agrega transacciones solo de cuentas destacadas
        # cuando existe al menos una (la cuenta por defecto del registro lo es).
        cuenta_cop = make_account(
            auth_headers, name="Cuenta COP", currency="COP", balance="1000000.00", highlighted=True
        )
        categoria = make_category(auth_headers, name="Comida", type="expense")
        _set_monthly_income(client, auth_headers, "1000000.00")

        _create_transaction(
            client,
            auth_headers,
            amount="250000.00",
            type="expense",
            account_id=cuenta_cop["id"],
            category_id=categoria["id"],
        )

        response = client.get("/api/v1/dashboard/summary", headers=auth_headers)
        assert response.status_code == 200, response.text

        resumen = response.json()
        assert Decimal(str(resumen["monthly_flow_balance"])) == Decimal("750000.00")

    def test_expenses_only_in_other_currency_do_not_subtract(self, client, auth_headers, make_account, make_category):
        """Limitación documentada en el spec (Decisión 11.3.1): el balance de flujo solo
        resta el gasto del mes en la moneda preferida."""
        # Destacada: el gasto USD SÍ entra al agregado del mes (bucket USD) y aun así
        # no debe restar del balance de flujo.
        cuenta_usd = make_account(auth_headers, name="Cuenta USD", currency="USD", balance="1000.00", highlighted=True)
        categoria = make_category(auth_headers, name="Comida", type="expense")
        _set_monthly_income(client, auth_headers, "1000000.00")

        _create_transaction(
            client,
            auth_headers,
            amount="500.00",
            type="expense",
            account_id=cuenta_usd["id"],
            category_id=categoria["id"],
        )

        response = client.get("/api/v1/dashboard/summary", headers=auth_headers)
        assert response.status_code == 200, response.text

        resumen = response.json()
        assert Decimal(str(resumen["monthly_flow_balance"])) == Decimal("1000000.00")


class TestMonoCurrencyRegression:
    """Regresión §11.1: para un usuario con una sola moneda (la mayoría), los tres
    endpoints corregidos deben comportarse exactamente igual que antes del fix."""

    def test_single_currency_user_sees_identical_results(self, client, auth_headers, make_account, make_category):
        # Usuario nuevo ya trae una cuenta destacada COP (saldo 0) por el registro;
        # todo lo creado abajo también es COP → un solo balde de moneda.
        cuenta_cop = make_account(auth_headers, name="Única cuenta", currency="COP", balance="500000.00")
        categoria_gasto = make_category(auth_headers, name="Comida", type="expense")
        categoria_ingreso = make_category(auth_headers, name="Salario", type="income")
        month, year = _now_month_year()

        budget_response = client.post(
            "/api/v1/budgets/",
            json={
                "amount_limit": "1000.00",
                "currency": "COP",
                "month": month,
                "year": year,
                "category_id": categoria_gasto["id"],
            },
            headers=auth_headers,
        )
        assert budget_response.status_code == 200, budget_response.text
        budget_id = budget_response.json()["id"]

        _create_transaction(
            client,
            auth_headers,
            amount="1000.00",
            type="income",
            account_id=cuenta_cop["id"],
            category_id=categoria_ingreso["id"],
        )
        _create_transaction(
            client,
            auth_headers,
            amount="100.00",
            type="expense",
            account_id=cuenta_cop["id"],
            category_id=categoria_gasto["id"],
        )
        _create_transaction(
            client,
            auth_headers,
            amount="200.00",
            type="expense",
            account_id=cuenta_cop["id"],
            category_id=categoria_gasto["id"],
        )

        rango = _current_month_range_params()

        # 1. budgets-progress: mismos números que el test pre-fix de test_budgets.py
        progreso_resp = client.get("/api/v1/dashboard/budgets-progress", headers=auth_headers)
        assert progreso_resp.status_code == 200, progreso_resp.text
        progreso = next(p for p in progreso_resp.json() if p["budget_id"] == budget_id)
        assert Decimal(str(progreso["spent"])) == Decimal("300.00")
        assert progreso["percentage"] == pytest.approx(30.0)

        # 2. cashflow-series: default y currency explícita devuelven exactamente lo mismo
        serie_default = client.get("/api/v1/dashboard/cashflow-series", params=rango, headers=auth_headers).json()
        serie_explicita = client.get(
            "/api/v1/dashboard/cashflow-series", params={**rango, "currency": "COP"}, headers=auth_headers
        ).json()
        assert serie_default == serie_explicita
        assert len(serie_default) == 1
        assert Decimal(str(serie_default[0]["income"])) == Decimal("1000.00")
        assert Decimal(str(serie_default[0]["expense"])) == Decimal("300.00")

        # 3. category-distribution: totales íntegros, sin pérdida ni mezcla
        distribucion = client.get("/api/v1/dashboard/category-distribution", params=rango, headers=auth_headers).json()
        assert len(distribucion) == 1
        assert distribucion[0]["category_name"] == "Comida"
        assert Decimal(str(distribucion[0]["total"])) == Decimal("300.00")


class TestCategoryDistributionCashflowEquivalence:
    """Fase 19 §19.3.5 (Decisión 19.3.4): invariante de equivalencia de agregados.

    `category-distribution` (con `type=income`) y `cashflow-series` filtran por los
    MISMOS tres predicados (user_id, currency, rango de fechas) — ver Hallazgo 10 de
    `docs/specs/fase_19_spec.md`. Para los mismos parámetros debe cumplirse:

        sum(item.total de category-distribution, type=income)
        == sum(item.income de cashflow-series)

    La métrica "% del ingreso por categoría" (Decisión 19.3.4) divide cada categoría
    contra `totals.totalIncome`, sumado en cliente desde `cashflow-series` — comparte
    denominador con `category-distribution` solo si esta igualdad se mantiene. Este
    test convierte una igualdad hoy accidental en un invariante probado: si un cambio
    futuro toca el filtro de un endpoint sin tocar el otro, esto lo señala.
    """

    def test_category_distribution_income_total_equals_cashflow_series_income_total(
        self, client, auth_headers, make_account, make_category
    ):
        # Ingresos en ≥2 categorías distintas (misma moneda/mismo rango) + un gasto:
        # la suma de incomes no es 0 y no es trivial (un solo bucket).
        cuenta_cop = make_account(auth_headers, name="Cuenta COP", currency="COP", balance="1000000.00")
        categoria_salario = make_category(auth_headers, name="Salario", type="income")
        categoria_freelance = make_category(auth_headers, name="Freelance", type="income")
        categoria_gasto = make_category(auth_headers, name="Comida", type="expense")

        _create_transaction(
            client,
            auth_headers,
            amount="2000000.00",
            type="income",
            account_id=cuenta_cop["id"],
            category_id=categoria_salario["id"],
        )
        _create_transaction(
            client,
            auth_headers,
            amount="500000.00",
            type="income",
            account_id=cuenta_cop["id"],
            category_id=categoria_freelance["id"],
        )
        _create_transaction(
            client,
            auth_headers,
            amount="300000.00",
            type="expense",
            account_id=cuenta_cop["id"],
            category_id=categoria_gasto["id"],
        )

        rango = _current_month_range_params()

        # cashflow-series sin `currency` → default COP (moneda preferida)
        serie = client.get("/api/v1/dashboard/cashflow-series", params=rango, headers=auth_headers)
        assert serie.status_code == 200, serie.text
        total_income_serie = sum(Decimal(str(item["income"])) for item in serie.json())

        # category-distribution con type=income, mismo rango y misma moneda default
        distribucion = client.get(
            "/api/v1/dashboard/category-distribution",
            params={**rango, "type": "income"},
            headers=auth_headers,
        )
        assert distribucion.status_code == 200, distribucion.text
        total_income_categorias = sum(Decimal(str(item["total"])) for item in distribucion.json())

        assert total_income_categorias == total_income_serie
        # Sanidad del test: la igualdad no es trivial (0 == 0)
        assert total_income_serie == Decimal("2500000.00")


class TestFutureDatedTransactionExcludedFromCurrentMonth:
    """Bug encontrado en verificación manual (2026-09-13): una transacción con fecha
    futura DENTRO del mes en curso contaba como "ya gastado/recibido" en /summary y en
    budgets-progress (que acotaban a fin de mes calendario), pero quedaba afuera de
    category-distribution/cashflow-series (que ya acotaban a `hoy`, Fase 11 §11.4) — el
    dashboard mostraba un total distinto al de sus propios gráficos de desglose para el
    mismo período. Ambos ahora acotan a `hoy` cuando el mes consultado es el mes en
    curso (ver `dashboard.obtener_resumen` y `budget_alerts.spent_por_categoria_y_moneda`)."""

    @staticmethod
    def _fecha_futura_mismo_mes() -> str | None:
        hoy = datetime.now(UTC)
        ultimo_dia_mes = monthrange(hoy.year, hoy.month)[1]
        if hoy.day >= ultimo_dia_mes:
            return None  # hoy es el último día del mes: no hay "futuro" dentro del mismo mes
        manana = hoy + timedelta(days=1)
        return datetime(manana.year, manana.month, manana.day, tzinfo=UTC).isoformat()

    def test_summary_excludes_future_dated_expense_in_current_month(
        self, client, auth_headers, make_account, make_category
    ):
        fecha_futura = self._fecha_futura_mismo_mes()
        if fecha_futura is None:
            pytest.skip("hoy es el último día del mes")

        # `highlighted=True`: si el usuario ya tiene alguna cuenta destacada (p. ej. la
        # cuenta por defecto que crea el onboarding), /summary solo agrega destacadas —
        # sin esto, las transacciones de esta cuenta quedarían afuera del resumen por
        # ese filtro y no por el bug bajo prueba.
        cuenta = make_account(auth_headers, currency="COP", balance="1000000.00", highlighted=True)
        categoria = make_category(auth_headers, name="Comida", type="expense")

        _create_transaction(
            client,
            auth_headers,
            amount="30000.00",
            type="expense",
            account_id=cuenta["id"],
            category_id=categoria["id"],
        )
        _create_transaction(
            client,
            auth_headers,
            amount="500000.00",
            type="expense",
            account_id=cuenta["id"],
            category_id=categoria["id"],
            date=fecha_futura,
        )

        resumen = client.get("/api/v1/dashboard/summary", headers=auth_headers)
        assert resumen.status_code == 200, resumen.text
        gasto_cop = next(
            item["total"] for item in resumen.json()["monthly_expense_by_currency"] if item["currency"] == "COP"
        )
        assert Decimal(str(gasto_cop)) == Decimal("30000.00")

        # category-distribution no calcula "hoy" internamente — recibe start/end del
        # caller. El frontend real pasa `end_date=hoy` (accounts/[id]/page.tsx,
        # dashboard/page.tsx, analytics/page.tsx) — mismo rango acá, para comparar contra
        # el mismo período que /summary de arriba.
        hoy = datetime.now(UTC)
        distribucion = client.get(
            "/api/v1/dashboard/category-distribution",
            params={
                "start_date": datetime(hoy.year, hoy.month, 1, tzinfo=UTC).isoformat(),
                "end_date": hoy.isoformat(),
            },
            headers=auth_headers,
        )
        assert Decimal(str(distribucion.json()[0]["total"])) == Decimal("30000.00")

    def test_budgets_progress_excludes_future_dated_expense_in_current_month(
        self, client, auth_headers, make_account, make_category
    ):
        fecha_futura = self._fecha_futura_mismo_mes()
        if fecha_futura is None:
            pytest.skip("hoy es el último día del mes")

        cuenta = make_account(auth_headers, currency="COP", balance="1000000.00")
        categoria = make_category(auth_headers, name="Mercado", type="expense")
        month, year = _now_month_year()
        presupuesto = client.post(
            "/api/v1/budgets/",
            json={
                "category_id": categoria["id"],
                "amount_limit": "100000.00",
                "currency": "COP",
                "month": month,
                "year": year,
            },
            headers=auth_headers,
        )
        assert presupuesto.status_code == 200, presupuesto.text

        _create_transaction(
            client,
            auth_headers,
            amount="500000.00",
            type="expense",
            account_id=cuenta["id"],
            category_id=categoria["id"],
            date=fecha_futura,
        )

        progreso = client.get("/api/v1/dashboard/budgets-progress", headers=auth_headers)
        assert progreso.status_code == 200, progreso.text
        fila = next(p for p in progreso.json() if p["budget_id"] == presupuesto.json()["id"])
        assert Decimal(str(fila["spent"])) == Decimal("0.00")


# =============================================================================
# Fase 29 — navegación por mes en el dashboard (Decisiones B2, B3, B6, B7; T2-T5, T7)
#
# Ninguno de estos tests usa `freeze_time`: congelar el reloj invalidaría el JWT de 15
# minutos de `auth_headers` (conftest.py). Las fechas son relativas a `datetime.now(UTC)`,
# el patrón ya existente en este archivo.
# =============================================================================


class TestSummaryPeriodParams:
    """T2 — validación de `year`/`month` en GET /dashboard/summary."""

    @pytest.mark.parametrize(
        "params",
        [
            pytest.param({"year": 2026}, id="solo-year"),
            pytest.param({"month": 3}, id="solo-month"),
            pytest.param({"year": 2026, "month": 13}, id="month-13"),
            pytest.param({"year": 2026, "month": 0}, id="month-0"),
            pytest.param({"year": 0, "month": 3}, id="year-0"),
            pytest.param({"year": 2999, "month": 12}, id="mes-futuro"),
        ],
    )
    def test_periodo_invalido_devuelve_422_con_detail_string(self, client, auth_headers, params):
        """User Story 48: un período inválido se reporta con un 422 de detalle legible.
        El `detail` es un STRING (decisión de dominio, `DomainValidationError`), no la
        lista de FastAPI — esa otra forma la produce `year=abc`, que ni llega al handler."""
        response = client.get("/api/v1/dashboard/summary", params=params, headers=auth_headers)
        assert response.status_code == 422, response.text
        detail = response.json()["detail"]
        assert isinstance(detail, str)
        assert detail

    def test_mes_futuro_por_un_dia_es_422(self, client, auth_headers):
        """El mes siguiente al actual es futuro aunque falte un solo día para que llegue."""
        ahora = datetime.now(UTC)
        mes_siguiente = 1 if ahora.month == 12 else ahora.month + 1
        anio_siguiente = ahora.year + 1 if ahora.month == 12 else ahora.year
        response = client.get(
            "/api/v1/dashboard/summary",
            params={"year": anio_siguiente, "month": mes_siguiente},
            headers=auth_headers,
        )
        assert response.status_code == 422, response.text
        assert "futuro" in response.json()["detail"]

    def test_no_enteros_es_422_de_fastapi_otra_forma(self, client, auth_headers):
        """La otra forma de 422: `year=abc` lo rechaza FastAPI antes del handler, con
        `detail` como lista. Documenta la distinción del contrato de la spec."""
        response = client.get("/api/v1/dashboard/summary", params={"year": "abc", "month": 3}, headers=auth_headers)
        assert response.status_code == 422, response.text
        assert isinstance(response.json()["detail"], list)

    def test_mes_actual_explicito_es_identico_a_sin_parametros(self, client, auth_headers, make_account, make_category):
        """User Story 47 + 49: el dashboard de siempre no cambia. `year`/`month` del mes en
        curso explícitos dan byte a byte la misma respuesta que no mandarlos, y el rótulo
        del balance es "declared"."""
        cuenta = make_account(auth_headers, name="Cuenta COP", currency="COP", balance="1000000.00", highlighted=True)
        categoria = make_category(auth_headers, name="Comida", type="expense")
        _set_monthly_income(client, auth_headers, "1000000.00")
        _create_transaction(
            client,
            auth_headers,
            amount="250000.00",
            type="expense",
            account_id=cuenta["id"],
            category_id=categoria["id"],
        )

        sin_parametros = _get_summary(client, auth_headers)
        month, year = _now_month_year()
        explicito = _get_summary(client, auth_headers, year=year, month=month)

        assert explicito == sin_parametros
        assert explicito["monthly_flow_basis"] == "declared"
        assert Decimal(str(explicito["monthly_flow_balance"])) == Decimal("750000.00")

    def test_mes_pasado_es_mes_pasado_no_actual(self, client, auth_headers):
        mes_pasado, anio_pasado = _previous_month_year()
        resumen = _get_summary(client, auth_headers, year=anio_pasado, month=mes_pasado)
        assert resumen["monthly_flow_basis"] == "actual"


class TestSummaryPreviousMonth:
    """T3 — `monthly_flow_basis="actual"`: ingresos reales - gastos reales del mes cerrado."""

    def test_ingresos_menos_gastos_en_moneda_preferida(self, client, auth_headers, make_account, make_category):
        mes_pasado, anio_pasado = _previous_month_year()
        fecha = _fecha_en_mes(anio_pasado, mes_pasado, 10)

        cuenta = make_account(auth_headers, name="Cuenta COP", currency="COP", balance="1000000.00", highlighted=True)
        categoria_gasto = make_category(auth_headers, name="Comida", type="expense")
        categoria_ingreso = make_category(auth_headers, name="Salario", type="income")

        # Ingreso declarado enorme: el mes cerrado NO lo usa (User Story 11).
        _set_monthly_income(client, auth_headers, "9000000.00")

        _create_transaction(
            client,
            auth_headers,
            amount="2000000.00",
            type="income",
            account_id=cuenta["id"],
            category_id=categoria_ingreso["id"],
            date=fecha,
        )
        _create_transaction(
            client,
            auth_headers,
            amount="500000.00",
            type="expense",
            account_id=cuenta["id"],
            category_id=categoria_gasto["id"],
            date=fecha,
        )

        resumen = _get_summary(client, auth_headers, year=anio_pasado, month=mes_pasado)
        assert resumen["monthly_flow_basis"] == "actual"
        assert Decimal(str(resumen["monthly_flow_balance"])) == Decimal("1500000.00")

    def test_otras_monedas_se_ignoran(self, client, auth_headers, make_account, make_category):
        """Misma limitación documentada en la Decisión 11.3.1 para el balance declarado: sin
        conversión de moneda, los buckets USD no entran al balance COP."""
        mes_pasado, anio_pasado = _previous_month_year()
        fecha = _fecha_en_mes(anio_pasado, mes_pasado, 10)

        cuenta_cop = make_account(auth_headers, name="COP", currency="COP", balance="1000000.00", highlighted=True)
        # Destacada a propósito: el gasto USD SÍ entra al agregado del mes (bucket USD) y
        # aun así no debe alterar el balance de flujo.
        cuenta_usd = make_account(auth_headers, name="USD", currency="USD", balance="1000.00", highlighted=True)
        categoria_gasto = make_category(auth_headers, name="Comida", type="expense")
        categoria_ingreso = make_category(auth_headers, name="Salario", type="income")

        _create_transaction(
            client,
            auth_headers,
            amount="1000000.00",
            type="income",
            account_id=cuenta_cop["id"],
            category_id=categoria_ingreso["id"],
            date=fecha,
        )
        _create_transaction(
            client,
            auth_headers,
            amount="100.00",
            type="expense",
            account_id=cuenta_cop["id"],
            category_id=categoria_gasto["id"],
            date=fecha,
        )
        _create_transaction(
            client,
            auth_headers,
            amount="900.00",
            type="expense",
            account_id=cuenta_usd["id"],
            category_id=categoria_gasto["id"],
            date=fecha,
        )
        _create_transaction(
            client,
            auth_headers,
            amount="800.00",
            type="income",
            account_id=cuenta_usd["id"],
            category_id=categoria_ingreso["id"],
            date=fecha,
        )

        resumen = _get_summary(client, auth_headers, year=anio_pasado, month=mes_pasado)
        # 1000000 - 100, no 1000000 - 100 - 900 + 800
        assert Decimal(str(resumen["monthly_flow_balance"])) == Decimal("999900.00")
        # El bucket USD sí está en el desglose por moneda
        assert {i["currency"] for i in resumen["monthly_expense_by_currency"]} == {"COP", "USD"}

    def test_solo_cuentas_destacadas(self, client, auth_headers, make_account, make_category):
        """Q16: se mantiene el universo de cuentas destacadas del summary, también para el
        balance de un mes pasado. `make_account` nace SIN destacar, y la cuenta por defecto
        del registro nace destacada (users.py:58-65) — de ahí que el filtro siga activo."""
        mes_pasado, anio_pasado = _previous_month_year()
        fecha = _fecha_en_mes(anio_pasado, mes_pasado, 10)

        cuenta_destacada = make_account(
            auth_headers, name="Destacada", currency="COP", balance="1000000.00", highlighted=True
        )
        cuenta_no_destacada = make_account(
            auth_headers, name="No destacada", currency="COP", balance="1000000.00", highlighted=False
        )
        categoria_gasto = make_category(auth_headers, name="Comida", type="expense")
        categoria_ingreso = make_category(auth_headers, name="Salario", type="income")

        _create_transaction(
            client,
            auth_headers,
            amount="100000.00",
            type="income",
            account_id=cuenta_destacada["id"],
            category_id=categoria_ingreso["id"],
            date=fecha,
        )
        _create_transaction(
            client,
            auth_headers,
            amount="40000.00",
            type="expense",
            account_id=cuenta_destacada["id"],
            category_id=categoria_gasto["id"],
            date=fecha,
        )
        # Trampa: mismo mes, cuenta no destacada. Si el filtro no se respetara, el balance
        # sería -30000 en vez de 60000.
        _create_transaction(
            client,
            auth_headers,
            amount="90000.00",
            type="expense",
            account_id=cuenta_no_destacada["id"],
            category_id=categoria_gasto["id"],
            date=fecha,
        )

        resumen = _get_summary(client, auth_headers, year=anio_pasado, month=mes_pasado)
        assert Decimal(str(resumen["monthly_flow_balance"])) == Decimal("60000.00")

    def test_sin_transacciones_devuelve_cero_string_no_null(self, client, auth_headers):
        """User Story 12 + Decisión 15.6: el histórico siempre tiene un número, y los Decimal
        se serializan como strings en JSON."""
        mes_pasado, anio_pasado = _previous_month_year()
        resumen = _get_summary(client, auth_headers, year=anio_pasado, month=mes_pasado)

        assert resumen["monthly_flow_balance"] is not None
        assert resumen["monthly_flow_balance"] == "0.00"
        assert resumen["monthly_expense_by_currency"] == []
        assert resumen["monthly_income_by_currency"] == []

    def test_no_es_null_sin_monthly_income_declarado(self, client, auth_headers, make_account, make_category):
        """`null` solo es posible con basis "declared". En un mes cerrado el balance se
        deriva de transacciones reales, así que no depende de que el usuario haya fijado
        ingreso mensual."""
        mes_pasado, anio_pasado = _previous_month_year()
        fecha = _fecha_en_mes(anio_pasado, mes_pasado, 10)
        cuenta = make_account(auth_headers, name="Cuenta COP", currency="COP", balance="1000000.00", highlighted=True)
        categoria = make_category(auth_headers, name="Comida", type="expense")

        _create_transaction(
            client,
            auth_headers,
            amount="75000.00",
            type="expense",
            account_id=cuenta["id"],
            category_id=categoria["id"],
            date=fecha,
        )

        # El usuario nunca fijó monthly_income: en el mes EN CURSO eso da null...
        assert _get_summary(client, auth_headers)["monthly_flow_balance"] is None

        # ...pero en el mes cerrado el balance sale de transacciones reales y nunca es null.
        resumen = _get_summary(client, auth_headers, year=anio_pasado, month=mes_pasado)
        assert resumen["monthly_flow_balance"] is not None
        assert Decimal(str(resumen["monthly_flow_balance"])) == Decimal("-75000.00")

    def test_transaccion_borrada_logicamente_no_cuenta(
        self, client, auth_headers, db_session, make_account, make_category
    ):
        mes_pasado, anio_pasado = _previous_month_year()
        fecha = _fecha_en_mes(anio_pasado, mes_pasado, 10)
        cuenta = make_account(auth_headers, name="Cuenta COP", currency="COP", balance="1000000.00", highlighted=True)
        categoria_ingreso = make_category(auth_headers, name="Salario", type="income")
        categoria_gasto = make_category(auth_headers, name="Comida", type="expense")

        borrada = _create_transaction(
            client,
            auth_headers,
            amount="5000000.00",
            type="income",
            account_id=cuenta["id"],
            category_id=categoria_ingreso["id"],
            date=fecha,
        )
        _create_transaction(
            client,
            auth_headers,
            amount="1000000.00",
            type="income",
            account_id=cuenta["id"],
            category_id=categoria_ingreso["id"],
            date=fecha,
        )
        _create_transaction(
            client,
            auth_headers,
            amount="300000.00",
            type="expense",
            account_id=cuenta["id"],
            category_id=categoria_gasto["id"],
            date=fecha,
        )
        _soft_delete_via_raw_sql(db_session, "transactions", borrada["id"])

        resumen = _get_summary(client, auth_headers, year=anio_pasado, month=mes_pasado)
        # 1000000 - 300000; los 5000000 borrados lógicamente quedan fuera
        assert Decimal(str(resumen["monthly_flow_balance"])) == Decimal("700000.00")

    def test_gasto_del_mes_actual_no_cuenta_en_el_mes_pasado(self, client, auth_headers, make_account, make_category):
        """El filtro de período es el que separa los meses: el mismo gasto registrado hoy
        no aparece al pedir el mes anterior."""
        mes_pasado, anio_pasado = _previous_month_year()
        cuenta = make_account(auth_headers, name="Cuenta COP", currency="COP", balance="1000000.00", highlighted=True)
        categoria_gasto = make_category(auth_headers, name="Comida", type="expense")

        _create_transaction(
            client,
            auth_headers,
            amount="50000.00",
            type="expense",
            account_id=cuenta["id"],
            category_id=categoria_gasto["id"],
        )

        resumen = _get_summary(client, auth_headers, year=anio_pasado, month=mes_pasado)
        assert resumen["monthly_expense_by_currency"] == []
        assert resumen["monthly_flow_balance"] == "0.00"


class TestFirstTransactionMonth:
    """T4 — `first_transaction_month`: límite inferior del `◀` del dashboard."""

    def test_null_sin_transacciones(self, client, auth_headers, make_account):
        make_account(auth_headers, balance="1000.00")
        assert _get_summary(client, auth_headers)["first_transaction_month"] is None

    def test_gana_la_mas_antigua_incluso_en_cuenta_no_destacada(
        self, client, auth_headers, make_account, make_category
    ):
        """El `◀` gobierna la página entera, y barras, presupuestos y lista de
        transacciones usan TODAS las cuentas — el campo no puede restringirse a las
        destacadas. Fechas fijas y lejanas para no depender del reloj ni del borde de mes."""
        cuenta_no_destacada = make_account(
            auth_headers, name="Ahorro", currency="COP", balance="1000000.00", highlighted=False
        )
        cuenta_destacada = make_account(
            auth_headers, name="Corriente", currency="COP", balance="1000000.00", highlighted=True
        )
        categoria = make_category(auth_headers, name="Comida", type="expense")

        _create_transaction(
            client,
            auth_headers,
            amount="1000.00",
            type="expense",
            account_id=cuenta_destacada["id"],
            category_id=categoria["id"],
            date="2024-06-10T00:00:00",
        )
        _create_transaction(
            client,
            auth_headers,
            amount="2000.00",
            type="expense",
            account_id=cuenta_no_destacada["id"],
            category_id=categoria["id"],
            date="2023-02-10T00:00:00",
        )

        assert _get_summary(client, auth_headers)["first_transaction_month"] == "2023-02"

    def test_transaccion_mas_antigua_borrada_logicamente_se_ignora(
        self, client, auth_headers, db_session, make_account, make_category
    ):
        cuenta = make_account(auth_headers, name="Cuenta COP", currency="COP", balance="1000000.00")
        categoria = make_category(auth_headers, name="Comida", type="expense")

        borrada = _create_transaction(
            client,
            auth_headers,
            amount="1000.00",
            type="expense",
            account_id=cuenta["id"],
            category_id=categoria["id"],
            date="2019-03-10T00:00:00",
        )
        _create_transaction(
            client,
            auth_headers,
            amount="2000.00",
            type="expense",
            account_id=cuenta["id"],
            category_id=categoria["id"],
            date="2020-05-10T00:00:00",
        )
        _soft_delete_via_raw_sql(db_session, "transactions", borrada["id"])

        assert _get_summary(client, auth_headers)["first_transaction_month"] == "2020-05"

    def test_no_depende_del_mes_pedido(self, client, auth_headers, make_account, make_category):
        """`first_transaction_month` es del USUARIO, no del período pedido: gobierna el `◀`
        en cualquier mes en el que se esté mirando."""
        cuenta = make_account(auth_headers, name="Cuenta COP", currency="COP", balance="1000000.00")
        categoria = make_category(auth_headers, name="Comida", type="expense")
        _create_transaction(
            client,
            auth_headers,
            amount="1000.00",
            type="expense",
            account_id=cuenta["id"],
            category_id=categoria["id"],
            date="2021-11-10T00:00:00",
        )

        mes_pasado, anio_pasado = _previous_month_year()
        resumen = _get_summary(client, auth_headers, year=anio_pasado, month=mes_pasado)
        assert resumen["first_transaction_month"] == "2021-11"


class TestBudgetsProgressPreviousMonth:
    """T5 / B3 — budgets-progress en un mes pasado: muestra lo que existió, no lo que la
    plantilla recurrente habría generado."""

    def test_mes_pasado_sin_presupuestos_devuelve_lista_vacia_sin_crear_filas(
        self, client, auth_headers, db_session, test_user, make_category
    ):
        """User Story 17 y 18: `[]` sin crear nada, aunque haya una plantilla recurrente
        vigente. El conteo de filas de `Budget` es la aserción que importa — el `[]` solo
        podría venir de un filtro posterior, que sí dejaría filas nuevas."""
        categoria = make_category(auth_headers, name="Comida", type="expense")
        month, year = _now_month_year()
        _create_budget(client, auth_headers, category_id=categoria["id"], month=month, year=year, is_recurring=True)

        mes_pasado, anio_pasado = _previous_month_year()
        antes = db_session.query(models.Budget).filter(models.Budget.user_id == test_user["id"]).count()

        response = client.get(
            "/api/v1/dashboard/budgets-progress",
            params={"year": anio_pasado, "month": mes_pasado},
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        assert response.json() == []

        despues = db_session.query(models.Budget).filter(models.Budget.user_id == test_user["id"]).count()
        assert despues == antes

    def test_presupuesto_que_si_existio_muestra_el_gasto_de_ese_mes(
        self, client, auth_headers, make_account, make_category
    ):
        mes_pasado, anio_pasado = _previous_month_year()
        fecha_pasada = _fecha_en_mes(anio_pasado, mes_pasado, 10)
        cuenta = make_account(auth_headers, balance="1000000.00")
        categoria = make_category(auth_headers, name="Comida", type="expense")

        presupuesto = _create_budget(
            client,
            auth_headers,
            category_id=categoria["id"],
            month=mes_pasado,
            year=anio_pasado,
            amount_limit="200000.00",
        )
        _create_transaction(
            client,
            auth_headers,
            amount="120000.00",
            type="expense",
            account_id=cuenta["id"],
            category_id=categoria["id"],
            date=fecha_pasada,
        )
        # Gasto del mes EN CURSO: fuera del período pedido, no puede contaminar el `spent`.
        _create_transaction(
            client,
            auth_headers,
            amount="90000.00",
            type="expense",
            account_id=cuenta["id"],
            category_id=categoria["id"],
        )

        response = client.get(
            "/api/v1/dashboard/budgets-progress",
            params={"year": anio_pasado, "month": mes_pasado},
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        filas = response.json()
        assert len(filas) == 1
        assert filas[0]["budget_id"] == presupuesto["id"]
        assert Decimal(str(filas[0]["spent"])) == Decimal("120000.00")
        assert filas[0]["percentage"] == pytest.approx(60.0)

    def test_mes_actual_explicito_sigue_generando_los_recurrentes(
        self, client, auth_headers, db_session, test_user, make_category
    ):
        """Contracara del `if es_mes_actual`: la generación perezosa del mes en curso
        (Fase 8 §3, Decisión 3.1) sigue intacta, y ahora también vía year/month explícitos."""
        categoria = make_category(auth_headers, name="Comida", type="expense")
        mes_pasado, anio_pasado = _previous_month_year()
        _create_budget(
            client, auth_headers, category_id=categoria["id"], month=mes_pasado, year=anio_pasado, is_recurring=True
        )
        month, year = _now_month_year()
        antes = db_session.query(models.Budget).filter(models.Budget.user_id == test_user["id"]).count()

        response = client.get(
            "/api/v1/dashboard/budgets-progress",
            params={"year": year, "month": month},
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        assert len(response.json()) == 1

        despues = db_session.query(models.Budget).filter(models.Budget.user_id == test_user["id"]).count()
        assert despues == antes + 1

    def test_mes_pasado_invalido_tambien_es_422(self, client, auth_headers):
        response = client.get("/api/v1/dashboard/budgets-progress", params={"month": 12}, headers=auth_headers)
        assert response.status_code == 422, response.text
        assert isinstance(response.json()["detail"], str)


class TestExpenseCurrencies:
    """T7 / B7 — monedas que ofrecen los chips de "Gastos por categoría"."""

    def test_incluye_la_moneda_de_una_cuenta_no_destacada(self, client, auth_headers, make_account, make_category):
        """H1 — el caso que motivó la decisión: una cuenta USD creada después del onboarding
        NO es destacada, y sin esto su chip no aparecería aunque las barras tengan datos en
        USD (las barras cuentan todas las cuentas)."""
        cuenta_cop = make_account(auth_headers, name="COP", currency="COP", balance="1000000.00", highlighted=True)
        cuenta_usd = make_account(auth_headers, name="USD", currency="USD", balance="1000.00", highlighted=False)
        categoria = make_category(auth_headers, name="Comida", type="expense")

        _create_transaction(
            client,
            auth_headers,
            amount="50000.00",
            type="expense",
            account_id=cuenta_cop["id"],
            category_id=categoria["id"],
        )
        _create_transaction(
            client,
            auth_headers,
            amount="100.00",
            type="expense",
            account_id=cuenta_usd["id"],
            category_id=categoria["id"],
        )

        resumen = _get_summary(client, auth_headers)
        assert "USD" in resumen["expense_currencies"]
        # Y el agregado de la tarjeta sigue siendo solo de destacadas (Q16 sin cambios): el
        # universo de `expense_currencies` es deliberadamente otro.
        assert {i["currency"] for i in resumen["monthly_expense_by_currency"]} == {"COP"}

    def test_excluye_una_moneda_sin_gasto_en_el_mes(self, client, auth_headers, make_account, make_category):
        """La cuenta USD existe y tuvo ACTIVIDAD en el mes, pero del tipo equivocado: un
        ingreso no genera chip de gasto (si no, el chip llevaría a una sección vacía)."""
        mes_pasado, anio_pasado = _previous_month_year()
        fecha = _fecha_en_mes(anio_pasado, mes_pasado, 10)
        cuenta_cop = make_account(auth_headers, name="COP", currency="COP", balance="1000000.00", highlighted=True)
        # Destacada a propósito: así el ingreso USD entra al agregado de la tarjeta y la
        # exclusión de `expense_currencies` queda probada como "por tipo", no "por cuenta".
        cuenta_usd = make_account(auth_headers, name="USD", currency="USD", balance="1000.00", highlighted=True)
        categoria_gasto = make_category(auth_headers, name="Comida", type="expense")
        categoria_ingreso = make_category(auth_headers, name="Salario", type="income")

        _create_transaction(
            client,
            auth_headers,
            amount="50000.00",
            type="expense",
            account_id=cuenta_cop["id"],
            category_id=categoria_gasto["id"],
            date=fecha,
        )
        _create_transaction(
            client,
            auth_headers,
            amount="800.00",
            type="income",
            account_id=cuenta_usd["id"],
            category_id=categoria_ingreso["id"],
            date=fecha,
        )

        resumen = _get_summary(client, auth_headers, year=anio_pasado, month=mes_pasado)
        assert resumen["expense_currencies"] == ["COP"]
        # El ingreso USD sí aparece en su propio agregado: lo que se excluye es el gasto
        assert {i["currency"] for i in resumen["monthly_income_by_currency"]} == {"USD"}

    def test_orden_preferida_primero_y_resto_alfabetico(self, client, auth_headers, make_account, make_category):
        """Mismo `sort_key` que `monthly_expense_by_currency`: la preferida primero, el resto
        alfabético. Tres monedas para que el orden alfabético sea observable."""
        categoria = make_category(auth_headers, name="Comida", type="expense")
        for nombre, moneda in [("Peso argentino", "ARS"), ("Dólar", "USD"), ("Peso colombiano", "COP")]:
            cuenta = make_account(auth_headers, name=nombre, currency=moneda, balance="1000000.00")
            _create_transaction(
                client,
                auth_headers,
                amount="1000.00",
                type="expense",
                account_id=cuenta["id"],
                category_id=categoria["id"],
            )

        resumen = _get_summary(client, auth_headers)
        # La preferida del usuario es COP (default del registro)
        assert resumen["expense_currencies"] == ["COP", "ARS", "USD"]

    def test_es_lista_vacia_en_un_mes_sin_gasto(self, client, auth_headers, make_account, make_category):
        mes_pasado, anio_pasado = _previous_month_year()
        cuenta = make_account(auth_headers, name="COP", currency="COP", balance="1000000.00")
        categoria = make_category(auth_headers, name="Comida", type="expense")
        _create_transaction(
            client, auth_headers, amount="1000.00", type="expense", account_id=cuenta["id"], category_id=categoria["id"]
        )

        # El gasto es de HOY, el mes pasado está vacío
        resumen = _get_summary(client, auth_headers, year=anio_pasado, month=mes_pasado)
        assert resumen["expense_currencies"] == []
