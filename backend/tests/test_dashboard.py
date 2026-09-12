"""Tests de dashboard (Fase 11): corrección de los 3 bugs multi-moneda restantes
(budgets-progress, cashflow-series, category-distribution) y del nuevo campo
monthly_flow_balance en /summary.

Hasta Fase 11 no existía ningún test de app/api/dashboard.py (hallazgo 11 del spec
de Fase 11) — este archivo cierra esa deuda además de cubrir los fixes.
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient


def _now_month_year() -> tuple[int, int]:
    now = datetime.now(UTC)
    return now.month, now.year


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
