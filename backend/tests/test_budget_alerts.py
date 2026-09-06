"""Tests del motor de evaluación de umbrales de presupuesto (Fase 13 §13.3).

Este es código que decide si notificar a un usuario sobre dinero — mismo criterio de
riesgo que los tests de Fase 7 sobre el módulo contable. Los casos exigidos por la
spec (líneas 414-421) se cubren vía el flujo real: el hook post-commit de
`crear_transaccion` dispara `evaluate_budget_thresholds_for_category` y el test
verifica el resultado en la bandeja (`GET /api/v1/notifications/`).
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal


def _now_month_year() -> tuple[int, int]:
    now = datetime.now(UTC)
    return now.month, now.year


def _next_month_year() -> tuple[int, int]:
    next_month = datetime.now(UTC) + timedelta(days=32)
    return next_month.month, next_month.year


def _notificaciones(client, headers: dict) -> list[dict]:
    response = client.get("/api/v1/notifications/", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["items"]


def _crear_presupuesto(
    client, headers: dict, categoria_id: int, amount: str, currency: str, month: int, year: int
) -> dict:
    response = client.post(
        "/api/v1/budgets/",
        json={
            "amount_limit": amount,
            "currency": currency,
            "month": month,
            "year": year,
            "category_id": categoria_id,
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


def _crear_gasto(
    client, headers: dict, account_id: int, category_id: int, amount: str, date: str | None = None
) -> dict:
    payload = {
        "amount": amount,
        "type": "expense",
        "account_id": account_id,
        "category_id": category_id,
    }
    if date:
        payload["date"] = date
    response = client.post("/api/v1/transactions/", json=payload, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


class TestBudgetAlertsEngine:
    def test_crossing_80_percent_generates_exactly_one_threshold_80_notification(
        self, client, auth_headers, make_account, make_category
    ):
        cuenta = make_account(auth_headers, balance="100000.00")
        categoria = make_category(auth_headers, name="Comida", type="expense")
        month, year = _now_month_year()
        presupuesto = _crear_presupuesto(client, auth_headers, categoria["id"], "1000.00", "COP", month, year)

        # 800/1000 = 80% exacto → cruza el umbral de 80
        _crear_gasto(client, auth_headers, cuenta["id"], categoria["id"], "800.00")

        notificaciones = _notificaciones(client, auth_headers)
        assert len(notificaciones) == 1
        assert notificaciones[0]["type"] == "budget_threshold_80"
        assert notificaciones[0]["budget_id"] == presupuesto["id"]

        # Una segunda transacción (90% acumulado) mantiene el aviso en UNO — no repite
        _crear_gasto(client, auth_headers, cuenta["id"], categoria["id"], "100.00")

        notificaciones = _notificaciones(client, auth_headers)
        assert len(notificaciones) == 1
        assert notificaciones[0]["type"] == "budget_threshold_80"

    def test_crossing_100_percent_in_single_transaction_generates_only_threshold_100(
        self, client, auth_headers, make_account, make_category
    ):
        cuenta = make_account(auth_headers, balance="100000.00")
        categoria = make_category(auth_headers, name="Transporte", type="expense")
        month, year = _now_month_year()
        presupuesto = _crear_presupuesto(client, auth_headers, categoria["id"], "1000.00", "COP", month, year)

        # De una pasada: 0% → 130% — el `break` de la Decisión 13.3.2 deja SOLO el de 100
        _crear_gasto(client, auth_headers, cuenta["id"], categoria["id"], "1300.00")

        notificaciones = _notificaciones(client, auth_headers)
        assert len(notificaciones) == 1
        assert notificaciones[0]["type"] == "budget_threshold_100"
        assert notificaciones[0]["budget_id"] == presupuesto["id"]

    def test_second_transaction_over_100_percent_does_not_duplicate_notification(
        self, client, auth_headers, make_account, make_category
    ):
        cuenta = make_account(auth_headers, balance="100000.00")
        categoria = make_category(auth_headers, name="Vivienda", type="expense")
        month, year = _now_month_year()
        _crear_presupuesto(client, auth_headers, categoria["id"], "1000.00", "COP", month, year)

        _crear_gasto(client, auth_headers, cuenta["id"], categoria["id"], "1100.00")
        _crear_gasto(client, auth_headers, cuenta["id"], categoria["id"], "300.00")

        # Unicidad (budget_id, type): sigue habiendo UNA sola notificación de 100
        notificaciones = _notificaciones(client, auth_headers)
        assert len(notificaciones) == 1
        assert notificaciones[0]["type"] == "budget_threshold_100"

    def test_expense_in_category_without_budget_generates_nothing(
        self, client, auth_headers, make_account, make_category
    ):
        cuenta = make_account(auth_headers, balance="100000.00")
        categoria = make_category(auth_headers, name="Sin presupuesto", type="expense")

        _crear_gasto(client, auth_headers, cuenta["id"], categoria["id"], "5000.00")

        notificaciones = _notificaciones(client, auth_headers)
        assert notificaciones == []

    def test_two_budgets_same_category_different_currencies_evaluate_own_spent_by_currency(
        self, client, auth_headers, make_account, make_category
    ):
        """Hallazgo 5 del spec: el motor respeta `Budget.currency` — cada presupuesto
        evalúa contra el gasto de SU moneda, no la suma (corrección de Fase 11 §11.1
        aplicada a la escritura). Nota: el índice único parcial `uq_budgets_user_
        category_period_active` impide dos presupuestos activos de la misma categoría en
        el MISMO período, así que el par vive en meses distintos, con gastos trampa de
        la otra moneda DENTRO de cada período evaluado para detectar el bug de mezclar."""
        cuenta_cop = make_account(auth_headers, name="COP", currency="COP", balance="1000000.00")
        cuenta_usd = make_account(auth_headers, name="USD", currency="USD", balance="1000000.00")
        categoria = make_category(auth_headers, name="Mercado", type="expense")

        month, year = _now_month_year()
        next_month, next_year = _next_month_year()
        presupuesto_cop = _crear_presupuesto(client, auth_headers, categoria["id"], "1000.00", "COP", month, year)
        presupuesto_usd = _crear_presupuesto(
            client, auth_headers, categoria["id"], "1000.00", "USD", next_month, next_year
        )

        # Gasto TRAMPA: 5000 USD en el mes del presupuesto COP (no debe contar)
        _crear_gasto(client, auth_headers, cuenta_usd["id"], categoria["id"], "5000.00")
        # COP 850/1000 = 85% → umbral 80 (si el motor mezclara monedas: 585% → umbral 100)
        _crear_gasto(client, auth_headers, cuenta_cop["id"], categoria["id"], "850.00")

        # Gasto TRAMPA: 5000 COP en el mes del presupuesto USD (no debe contar)
        fecha_usd = datetime(next_year, next_month, 1).isoformat()
        _crear_gasto(client, auth_headers, cuenta_cop["id"], categoria["id"], "5000.00", date=fecha_usd)
        # USD 900/1000 = 90% → umbral 80
        _crear_gasto(client, auth_headers, cuenta_usd["id"], categoria["id"], "900.00", date=fecha_usd)

        notificaciones = _notificaciones(client, auth_headers)
        assert len(notificaciones) == 2

        por_budget = {n["budget_id"]: n["type"] for n in notificaciones}
        assert por_budget[presupuesto_cop["id"]] == "budget_threshold_80"
        assert por_budget[presupuesto_usd["id"]] == "budget_threshold_80"

    def test_engine_failure_does_not_block_transaction_save(
        self, client, auth_headers, make_account, make_category, monkeypatch
    ):
        """Decisión 13.3.4: un fallo del motor de alertas NUNCA revierte la transacción
        contable ya confirmada ni tumba el request."""
        cuenta = make_account(auth_headers, balance="1000.00")
        categoria = make_category(auth_headers, name="Comida", type="expense")

        def _booom(*args, **kwargs):
            raise RuntimeError("fallo interno del motor de alertas (mock)")

        monkeypatch.setattr("app.core.budget_alerts.evaluate_budget_thresholds_for_category", _booom)

        response = client.post(
            "/api/v1/transactions/",
            json={
                "amount": "100.00",
                "type": "expense",
                "account_id": cuenta["id"],
                "category_id": categoria["id"],
            },
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text

        cuenta_final = client.get(f"/api/v1/accounts/{cuenta['id']}", headers=auth_headers).json()
        assert Decimal(str(cuenta_final["balance"])) == Decimal("900.00")

        # El motor no corrió: la bandeja quedó vacía
        assert _notificaciones(client, auth_headers) == []

    def test_reclassifying_expense_evaluates_old_category_against_its_original_period(
        self, client, auth_headers, make_account, make_category
    ):
        """Regresión: al reclasificar un gasto a otra categoría, la categoría de ORIGEN
        debe re-evaluarse contra el período al que pertenecía la transacción ANTES del
        cambio, nunca contra el período de la fecha nueva (bug encontrado en code review
        de Fase 13: `actualizar_transaccion` usaba `transaccion_db.date` ya mutado para
        ambas evaluaciones). Para detectarlo se deja la categoría de origen con gasto sin
        notificar aún en OTRO período (el de la fecha nueva) — si el motor mirara ese
        período por error, dispararía un aviso disparado por una acción que no tiene nada
        que ver con ese presupuesto."""
        cuenta = make_account(auth_headers, balance="1000000.00")
        categoria_a = make_category(auth_headers, name="Origen", type="expense")
        categoria_b = make_category(auth_headers, name="Destino", type="expense")

        mes_actual, anio_actual = _now_month_year()
        mes_siguiente, anio_siguiente = _next_month_year()
        fecha_siguiente = datetime(anio_siguiente, mes_siguiente, 1).isoformat()

        _crear_presupuesto(client, auth_headers, categoria_a["id"], "1000.00", "COP", mes_actual, anio_actual)

        # Gasto sin relación, en el mes SIGUIENTE, ANTES de que exista presupuesto ahí:
        # el motor no notifica nada porque no hay presupuesto contra qué evaluar todavía.
        _crear_gasto(client, auth_headers, cuenta["id"], categoria_a["id"], "95.00", date=fecha_siguiente)
        presupuesto_a_siguiente = _crear_presupuesto(
            client, auth_headers, categoria_a["id"], "100.00", "COP", mes_siguiente, anio_siguiente
        )
        # 95/100 = 95% ya cruzado, pero aún sin notificar (el presupuesto llegó después).

        # Gasto a reclasificar: categoría A, mes ACTUAL, monto bajo (no cruza el 80% de
        # su propio presupuesto).
        gasto = _crear_gasto(client, auth_headers, cuenta["id"], categoria_a["id"], "50.00")
        assert _notificaciones(client, auth_headers) == []

        # Reclasificación: se mueve a categoría B, con fecha nueva en el mes SIGUIENTE.
        response = client.put(
            f"/api/v1/transactions/{gasto['id']}",
            json={
                "amount": "50.00",
                "currency": "COP",
                "type": "expense",
                "account_id": cuenta["id"],
                "category_id": categoria_b["id"],
                "date": fecha_siguiente,
            },
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text

        # La categoría de origen (A) se re-evalúa contra su período ORIGINAL (mes actual,
        # donde ahora no le queda ningún gasto) — nunca contra el mes siguiente, así que
        # el 95%-sin-notificar de A/mes-siguiente no debe dispararse por esta acción.
        budget_ids_notificados = {n["budget_id"] for n in _notificaciones(client, auth_headers)}
        assert presupuesto_a_siguiente["id"] not in budget_ids_notificados
