"""Tests de presupuestos: la unique constraint (§1.4 del spec), el cálculo de progreso
(`spent`/`percentage`) que consume `dashboard.py::obtener_progresos`, la recurrencia
(Fase 8 §3) y los límites de entrada del período y de la moneda (QA-023 y QA-025).
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

    @pytest.mark.parametrize(
        ("month_plantilla", "month_objetivo", "year"),
        [
            (1, 2, 2030),  # enero → febrero
            (11, 12, 2030),  # el mes 12 es el borde superior de `month`
            (12, 1, 2031),  # salto de año, con enero como borde inferior
            (5, 6, 2020),  # 2020 es el borde inferior de `year`
        ],
        ids=["febrero", "diciembre", "salto-de-ano", "year-2020"],
    )
    def test_periodo_valido_sigue_generando(
        self, client, auth_headers, make_category, month_plantilla, month_objetivo, year
    ):
        """Regresión de QA-023: el `Query(ge=1, le=12)` / `(ge=2020, le=2100)` del listado no
        puede haberorado los períodos legítimos. Casos borde a propósito (mes 1, mes 12 y el
        año más bajo permitido), porque un `ge`/`le` mal puesto solo se nota en los bordes.
        """
        categoria = make_category(auth_headers, name="Mercado", type="expense")
        anio_plantilla = year - 1 if month_objetivo < month_plantilla else year
        self._crear_presupuesto(
            client, auth_headers, categoria, month=month_plantilla, year=anio_plantilla, amount="750.00"
        )

        response = client.get("/api/v1/budgets/", params={"month": month_objetivo, "year": year}, headers=auth_headers)
        assert response.status_code == 200, response.text

        filas = [b for b in response.json() if b["category_id"] == categoria["id"]]
        assert len(filas) == 1
        assert filas[0]["month"] == month_objetivo
        assert filas[0]["year"] == year
        assert Decimal(str(filas[0]["amount_limit"])) == Decimal("750.00")
        assert filas[0]["is_recurring"] is True

    def test_presupuesto_recurrente_borrado_no_reaparece_al_recargar(self, client, auth_headers, make_category):
        """QA-024 end-to-end: borrar un recurrente del mes en curso tiene que aguantar la recarga.

        Sin la lápida (el chequeo de "esta categoría ya tiene fila en este período" ahora
        incluye las filas soft-deleted), la fila borrada dejaba de bloquear la generación
        perezosa y el presupuesto volvía a aparecer en la siguiente carga de la página.
        """
        categoria = make_category(auth_headers, name="Ocio", type="expense")
        prev_month, prev_year = _previous_month_year()
        self._crear_presupuesto(client, auth_headers, categoria, month=prev_month, year=prev_year)
        month, year = _now_month_year()

        generado = client.get("/api/v1/budgets/", params={"month": month, "year": year}, headers=auth_headers)
        assert generado.status_code == 200, generado.text
        fila = next(b for b in generado.json() if b["category_id"] == categoria["id"])
        budget_id = fila["id"]

        borrado = client.delete(f"/api/v1/budgets/{budget_id}", headers=auth_headers)
        assert borrado.status_code == 200, borrado.text

        # La recarga de la página (misma consulta con período, que es la que regenera):
        # sigue sin aparecer.
        despues = client.get("/api/v1/budgets/", params={"month": month, "year": year}, headers=auth_headers)
        assert despues.status_code == 200, despues.text
        assert [b for b in despues.json() if b["category_id"] == categoria["id"]] == []

        # Y tampoco en el listado sin filtros (el historial completo tampoco lo lista).
        historial = client.get("/api/v1/budgets/", headers=auth_headers)
        assert historial.status_code == 200, historial.text
        assert [b for b in historial.json() if b["id"] == budget_id] == []


class TestPresupuestosPeriodoInvalido:
    """QA-023: el query param de `GET /budgets/` es frontera de confianza.

    `?month=13&year=99999` pasaba sin validar, la generación perezosa clonaba las plantillas
    recurrentes a ese período basura y —como `BudgetResponse` heredaba el `ge/le` del
    request— esas filas no se podían serializar: `ResponseValidationError` → **500
    permanente** de `GET /budgets/`, con la página de presupuestos en skeleton para siempre.
    """

    def _plantilla_recurrente(self, client, auth_headers, categoria):
        response = client.post(
            "/api/v1/budgets/",
            json={
                "amount_limit": "500000.00",
                "currency": "COP",
                "month": 1,
                "year": 2030,
                "category_id": categoria["id"],
                "is_recurring": True,
            },
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        return response.json()

    @pytest.mark.parametrize(
        ("month", "year"),
        [(13, 2026), (10, 99999)],
        ids=["month-13", "year-99999"],
    )
    def test_periodo_invalido_devuelve_422_y_no_crea_presupuestos(
        self, client, auth_headers, make_category, db_session, test_user, month, year
    ):
        """El corazón de QA-023: 422 y, sobre todo, CERO filas basura en la base.

        El assert de `db_session` es el que importa: sin él, un 422 ""arreglado" que igual
        alcanzara a clonar la plantilla dejaría la fila imposible metida en la base, y esa
        fila sola basta para volver a dejar el listado en 500 (mitad del bug).
        """
        categoria = make_category(auth_headers, name="Mercado", type="expense")
        self._plantilla_recurrente(client, auth_headers, categoria)

        response = client.get("/api/v1/budgets/", params={"month": month, "year": year}, headers=auth_headers)
        assert response.status_code == 422, response.text

        filas = db_session.query(models.Budget).filter(models.Budget.user_id == test_user["id"]).all()
        assert [(f.month, f.year) for f in filas] == [(1, 2030)]  # solo la plantilla, intacta

    def test_fila_heredada_fuera_de_rango_no_rompe_el_listado(
        self, client, auth_headers, make_category, db_session, test_user
    ):
        """La otra mitad de QA-023: una fila imposible YA existente no puede tumbar el listado.

        `BudgetResponse` dejó de heredar de `BudgetBase` justamente para esto: los `ge/le`
        del período son validación de request, y en response convertían cualquier fila
        heredada (de una versión que no validaba el query param) en un 500 permanente. La
        fila se inserta a mano, imitando la basura que dejó esa versión.
        """
        categoria = make_category(auth_headers, name="Ocio", type="expense")

        db_session.add(
            models.Budget(
                amount_limit=Decimal("123456.00"),
                currency="COP",
                month=13,
                year=99999,
                user_id=test_user["id"],
                category_id=categoria["id"],
            )
        )
        db_session.commit()

        response = client.get("/api/v1/budgets/", headers=auth_headers)
        assert response.status_code == 200, response.text

        basura = [b for b in response.json() if b["category_id"] == categoria["id"]]
        assert len(basura) == 1
        assert basura[0]["month"] == 13
        assert basura[0]["year"] == 99999
        assert Decimal(str(basura[0]["amount_limit"])) == Decimal("123456.00")


class TestBudgetCurrencyPattern:
    """QA-025: `Budget.currency` es `String(3)` en `models.py` y no lo validaba nadie.

    Un `"zzzzzz"` llegaba al INSERT y volvía como un 500 en texto plano
    (`StringDataRightTruncation` es un `DataError`), no como un 422 — el mismo modo de fallo
    que el rango de los campos de dinero (QA-015). `CURRENCY_PATTERN` va solo en los schemas
    de request; los de response se quedan sin validar a propósito (ver `schemas/common.py`).
    """

    def _payload(self, categoria, currency):
        month, year = _now_month_year()
        return {
            "amount_limit": "50000.00",
            "currency": currency,
            "month": month,
            "year": year,
            "category_id": categoria["id"],
        }

    @pytest.mark.parametrize("currency", ["zzzzzz", "", "cop"], ids=["larga", "vacia", "minusculas"])
    def test_currency_invalida_devuelve_422(self, client, auth_headers, make_category, currency):
        categoria = make_category(auth_headers, name="Mercado", type="expense")

        response = client.post("/api/v1/budgets/", json=self._payload(categoria, currency), headers=auth_headers)
        assert response.status_code == 422, response.text
        assert response.status_code != 500

    @pytest.mark.parametrize("currency", ["USD", "EUR"], ids=["usd", "eur"])
    def test_currency_valida_seguida_de_aceptarse(self, client, auth_headers, make_category, currency):
        """Contracara del patrón: una ISO de 3 letras en mayúsculas entra normal."""
        categoria = make_category(auth_headers, name="Ocio", type="expense")

        response = client.post("/api/v1/budgets/", json=self._payload(categoria, currency), headers=auth_headers)
        assert response.status_code == 200, response.text
        assert response.json()["currency"] == currency

    def test_put_con_currency_invalida_devuelve_422(self, client, auth_headers, make_category):
        """El `PUT /budgets/{id}` toma `BudgetBase` directo, así que comparte la validación."""
        categoria = make_category(auth_headers, name="Suscripciones", type="expense")
        creado = client.post("/api/v1/budgets/", json=self._payload(categoria, "COP"), headers=auth_headers)
        assert creado.status_code == 200, creado.text

        edicion = client.put(
            f"/api/v1/budgets/{creado.json()['id']}",
            json={**self._payload(categoria, "zzzzzz"), "amount_limit": "60000.00"},
            headers=auth_headers,
        )
        assert edicion.status_code == 422, edicion.text
        assert edicion.status_code != 500


class TestBudgetMultiCurrency:
    """Fase 17 §17.2: presupuestos multi-moneda.

    El índice único ensanchado a `(user_id, category_id, month, year, currency)`
    (§17.2.2) permite un presupuesto por (categoría, período) POR moneda; el PUT
    asigna `currency` y gana try/except IntegrityError (§17.2.5).
    """

    def test_same_category_and_period_in_different_currencies_both_allowed(self, client, auth_headers, make_category):
        """Dos presupuestos de la misma categoría/mes/año en monedas distintas → ambos
        200 (hoy el segundo choca con el 400 del duplicado)."""
        categoria = make_category(auth_headers, name="Mercado", type="expense")
        month, year = _now_month_year()
        payload_base = {
            "amount_limit": "500000.00",
            "month": month,
            "year": year,
            "category_id": categoria["id"],
        }

        cop = client.post(
            "/api/v1/budgets/",
            json={**payload_base, "currency": "COP"},
            headers=auth_headers,
        )
        assert cop.status_code == 200, cop.text

        usd = client.post(
            "/api/v1/budgets/",
            json={**payload_base, "currency": "USD"},
            headers=auth_headers,
        )
        assert usd.status_code == 200, usd.text

        listado = client.get("/api/v1/budgets/", params={"month": month, "year": year}, headers=auth_headers)
        assert listado.status_code == 200
        coincidencias = [b for b in listado.json() if b["category_id"] == categoria["id"]]
        assert len(coincidencias) == 2
        assert {b["currency"] for b in coincidencias} == {"COP", "USD"}

    def test_identical_budget_in_all_four_dimensions_still_400(self, client, auth_headers, make_category):
        """Presupuesto idéntico en las 4 dimensiones (categoría/mes/año/moneda):
        sigue siendo 400 — no se rompe el caso de duplicado real."""
        categoria = make_category(auth_headers, name="Ocio", type="expense")
        month, year = _now_month_year()
        payload = {
            "amount_limit": "200000.00",
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

    def test_edit_budget_to_already_occupied_currency_returns_400_not_500(self, client, auth_headers, make_category):
        """Editar `currency` a una que YA tiene otro presupuesto para esa
        categoría/período → 400, no 500 (ejercita el try/except nuevo del PUT)."""
        categoria = make_category(auth_headers, name="Gimnasio", type="expense")
        month, year = _now_month_year()
        payload_base = {
            "amount_limit": "100000.00",
            "month": month,
            "year": year,
            "category_id": categoria["id"],
        }

        cop = client.post(
            "/api/v1/budgets/",
            json={**payload_base, "currency": "COP"},
            headers=auth_headers,
        )
        assert cop.status_code == 200, cop.text
        usd = client.post(
            "/api/v1/budgets/",
            json={**payload_base, "currency": "USD"},
            headers=auth_headers,
        )
        assert usd.status_code == 200, usd.text

        edicion = client.put(
            f"/api/v1/budgets/{usd.json()['id']}",
            json={**payload_base, "amount_limit": "120000.00", "currency": "COP"},
            headers=auth_headers,
        )
        assert edicion.status_code == 400
        assert edicion.status_code != 500

    def test_edit_budget_without_changing_currency_persists_value(self, client, auth_headers, make_category):
        """Editar SIN cambiar `currency` (se envía el mismo valor): persiste sin
        cambios — regresión de la línea `presupuesto_db.currency = ...` nueva."""
        categoria = make_category(auth_headers, name="Suscripciones", type="expense")
        month, year = _now_month_year()

        creado = client.post(
            "/api/v1/budgets/",
            json={
                "amount_limit": "50000.00",
                "currency": "COP",
                "month": month,
                "year": year,
                "category_id": categoria["id"],
            },
            headers=auth_headers,
        )
        assert creado.status_code == 200, creado.text
        budget_id = creado.json()["id"]

        edicion = client.put(
            f"/api/v1/budgets/{budget_id}",
            json={
                "amount_limit": "60000.00",
                "currency": "COP",
                "month": month,
                "year": year,
                "category_id": categoria["id"],
            },
            headers=auth_headers,
        )
        assert edicion.status_code == 200, edicion.text
        assert edicion.json()["currency"] == "COP"
        assert Decimal(str(edicion.json()["amount_limit"])) == Decimal("60000.00")


class TestApagarRecurrencia:
    """Flujo corto (spec `corto_recurrencia_presupuestos_spec.md`): desmarcar "Repetir cada
    mes" corta la serie (categoría + moneda) hacia adelante, sin tocar meses anteriores."""

    def _post(self, client, headers, categoria, month, year, amount="800.00", currency="COP", recurring=True):
        response = client.post(
            "/api/v1/budgets/",
            json={
                "amount_limit": amount,
                "currency": currency,
                "month": month,
                "year": year,
                "category_id": categoria["id"],
                "is_recurring": recurring,
            },
            headers=headers,
        )
        assert response.status_code == 200, response.text
        return response.json()

    def _put(self, client, headers, fila, **cambios):
        cuerpo = {
            "amount_limit": fila["amount_limit"],
            "currency": fila["currency"],
            "month": fila["month"],
            "year": fila["year"],
            "category_id": fila["category_id"],
            "is_recurring": fila["is_recurring"],
        } | cambios
        response = client.put(f"/api/v1/budgets/{fila['id']}", json=cuerpo, headers=headers)
        assert response.status_code == 200, response.text
        return response.json()

    def _fila(self, client, headers, categoria, month, year, currency="COP"):
        listado = client.get("/api/v1/budgets/", params={"month": month, "year": year}, headers=headers).json()
        return next(
            (b for b in listado if b["category_id"] == categoria["id"] and b["currency"] == currency),
            None,
        )

    def _serie_de_tres(self, client, headers, categoria):
        self._post(client, headers, categoria, 1, 2030)
        for mes in (2, 3):
            assert self._fila(client, headers, categoria, mes, 2030)

    def test_desmarcar_corta_el_mes_siguiente_y_conserva_pasado_y_actual(self, client, auth_headers, make_category):
        categoria = make_category(auth_headers, name="Mercado", type="expense")
        self._serie_de_tres(client, auth_headers, categoria)
        marzo = self._fila(client, auth_headers, categoria, 3, 2030)

        editada = self._put(client, auth_headers, marzo, is_recurring=False)

        assert editada["is_recurring"] is False
        assert Decimal(str(editada["amount_limit"])) == Decimal("800.00")
        assert self._fila(client, auth_headers, categoria, 4, 2030) is None
        assert self._fila(client, auth_headers, categoria, 1, 2030)["is_recurring"] is True
        assert self._fila(client, auth_headers, categoria, 2, 2030)["is_recurring"] is True

    def test_mes_futuro_ya_generado_pasa_a_no_recurrente_con_su_monto(self, client, auth_headers, make_category):
        categoria = make_category(auth_headers, name="Mercado", type="expense")
        self._serie_de_tres(client, auth_headers, categoria)
        febrero = self._fila(client, auth_headers, categoria, 2, 2030)

        self._put(client, auth_headers, febrero, is_recurring=False)

        marzo = self._fila(client, auth_headers, categoria, 3, 2030)
        assert marzo["is_recurring"] is False
        assert Decimal(str(marzo["amount_limit"])) == Decimal("800.00")
        assert self._fila(client, auth_headers, categoria, 4, 2030) is None

    def test_no_toca_otra_categoria_ni_otra_moneda(self, client, auth_headers, make_category):
        cat_a = make_category(auth_headers, name="A", type="expense")
        cat_b = make_category(auth_headers, name="B", type="expense")
        self._post(client, auth_headers, cat_a, 1, 2030)
        self._post(client, auth_headers, cat_b, 1, 2030)
        self._post(client, auth_headers, cat_a, 1, 2030, currency="USD", amount="50.00")
        febrero_cop = self._fila(client, auth_headers, cat_a, 2, 2030)
        assert self._fila(client, auth_headers, cat_a, 2, 2030, currency="USD")

        self._put(client, auth_headers, febrero_cop, is_recurring=False)

        assert self._fila(client, auth_headers, cat_a, 3, 2030) is None
        assert self._fila(client, auth_headers, cat_a, 3, 2030, currency="USD")["is_recurring"] is True
        assert self._fila(client, auth_headers, cat_b, 3, 2030)["is_recurring"] is True

    def test_remarcar_reinicia_la_serie(self, client, auth_headers, make_category):
        categoria = make_category(auth_headers, name="Mercado", type="expense")
        self._serie_de_tres(client, auth_headers, categoria)
        self._put(client, auth_headers, self._fila(client, auth_headers, categoria, 2, 2030), is_recurring=False)
        marzo = self._fila(client, auth_headers, categoria, 3, 2030)

        self._put(client, auth_headers, marzo, is_recurring=True)
        assert self._fila(client, auth_headers, categoria, 4, 2030)["is_recurring"] is True

        self._post(client, auth_headers, categoria, 8, 2030)
        assert self._fila(client, auth_headers, categoria, 9, 2030)["is_recurring"] is True

    def test_put_ya_no_recurrente_no_toca_filas_posteriores(self, client, auth_headers, make_category):
        categoria = make_category(auth_headers, name="Mercado", type="expense")
        self._post(client, auth_headers, categoria, 1, 2030, recurring=False)
        posterior = self._post(client, auth_headers, categoria, 3, 2030, recurring=True)
        enero = self._fila(client, auth_headers, categoria, 1, 2030)

        self._put(client, auth_headers, enero, amount_limit="900.00")

        assert self._fila(client, auth_headers, categoria, 3, 2030)["id"] == posterior["id"]
        assert self._fila(client, auth_headers, categoria, 3, 2030)["is_recurring"] is True

    def test_borrar_sigue_saltando_solo_ese_mes(self, client, auth_headers, make_category):
        categoria = make_category(auth_headers, name="Mercado", type="expense")
        self._serie_de_tres(client, auth_headers, categoria)
        marzo = self._fila(client, auth_headers, categoria, 3, 2030)
        assert client.delete(f"/api/v1/budgets/{marzo['id']}", headers=auth_headers).status_code == 200

        assert self._fila(client, auth_headers, categoria, 3, 2030) is None
        assert self._fila(client, auth_headers, categoria, 4, 2030)["is_recurring"] is True

    def test_pedir_mes_anterior_al_inicio_de_la_serie_no_genera(self, client, auth_headers, make_category):
        categoria = make_category(auth_headers, name="Mercado", type="expense")
        self._post(client, auth_headers, categoria, 5, 2030)

        assert self._fila(client, auth_headers, categoria, 3, 2030) is None

    def test_fila_manual_no_recurrente_posterior_corta_la_serie(self, client, auth_headers, make_category):
        categoria = make_category(auth_headers, name="Mercado", type="expense")
        self._post(client, auth_headers, categoria, 1, 2030)
        self._post(client, auth_headers, categoria, 4, 2030, recurring=False)

        assert self._fila(client, auth_headers, categoria, 5, 2030) is None

    def test_fila_de_otra_moneda_no_bloquea_la_serie(self, client, auth_headers, make_category):
        categoria = make_category(auth_headers, name="Mercado", type="expense")
        self._post(client, auth_headers, categoria, 1, 2030)
        self._post(client, auth_headers, categoria, 2, 2030, currency="USD", amount="50.00", recurring=False)

        assert self._fila(client, auth_headers, categoria, 2, 2030)["currency"] == "COP"

    def test_cambiar_moneda_al_desmarcar_corta_la_serie_resultante(self, client, auth_headers, make_category):
        categoria = make_category(auth_headers, name="Mercado", type="expense")
        self._post(client, auth_headers, categoria, 1, 2030)
        self._post(client, auth_headers, categoria, 1, 2030, currency="USD", amount="50.00")
        assert self._fila(client, auth_headers, categoria, 3, 2030, currency="USD")
        assert self._fila(client, auth_headers, categoria, 3, 2030)
        usd_enero = self._fila(client, auth_headers, categoria, 1, 2030, currency="USD")
        cop_enero = self._fila(client, auth_headers, categoria, 1, 2030)
        # Sacar la de COP de enero hacia otra categoría y moneda no corta la serie de origen.
        otra = make_category(auth_headers, name="Otra", type="expense")
        self._put(client, auth_headers, cop_enero, category_id=otra["id"], is_recurring=False)
        assert self._fila(client, auth_headers, categoria, 3, 2030)["is_recurring"] is True
        assert self._fila(client, auth_headers, categoria, 3, 2030, currency="USD")["is_recurring"] is True
        assert usd_enero["is_recurring"] is True

    def test_no_toca_presupuestos_de_otro_usuario(self, client, auth_headers, make_category, other_user):
        categoria = make_category(auth_headers, name="Mercado", type="expense")
        self._post(client, auth_headers, categoria, 1, 2030)
        febrero = self._fila(client, auth_headers, categoria, 2, 2030)
        self._put(client, auth_headers, febrero, is_recurring=False)

        ajeno = client.get("/api/v1/budgets/", params={"month": 3, "year": 2030}, headers=other_user["headers"])
        assert ajeno.status_code == 200
        assert ajeno.json() == []
