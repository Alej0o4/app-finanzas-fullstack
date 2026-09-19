"""Tests unit-level directos de `ensure_recurring_budgets_for_period` (Fase 25 §25.7 R1-R4).

Complementan, no reemplazan, los tests HTTP de `TestRecurringBudgets` (test_budgets.py:152-271,
Hallazgo 12): esos cubren la generación end-to-end vía `GET /budgets/` y
`GET /dashboard/budgets-progress`; este archivo llama la función directamente (db_session +
models.Budget insertados a mano, sin pasar por HTTP) y cierra las dos brechas reales que el
Hallazgo 12 identificó: el salto de año diciembre→enero y la rama de `IntegrityError`/rollback
bajo carrera (budget_recurrence.py:66-73, nunca ejercitada antes).
"""

from decimal import Decimal

from app.core.budget_recurrence import ensure_recurring_budgets_for_period
from app.models import models


class TestEnsureRecurringBudgetsForPeriod:
    def _crear_categoria(self, db_session, test_user, name="Categoría de prueba"):
        """Categoría propia del usuario insertada directo en la sesión de test.

        Alternativa a `make_category` (que pasa por HTTP): como estos tests llaman la
        función directamente, la categoría solo necesita existir — `Budget.category_id`
        es FK a `categories.id` — y el insert directo evita el round-trip HTTP.
        """
        categoria = models.Category(name=name, type="expense", user_id=test_user["id"])
        db_session.add(categoria)
        db_session.commit()
        return categoria

    def _filas_del_periodo(self, db_session, test_user, month, year):
        return (
            db_session.query(models.Budget)
            .filter(
                models.Budget.user_id == test_user["id"],
                models.Budget.month == month,
                models.Budget.year == year,
            )
            .all()
        )

    def test_year_rollover_generates_row_in_january_from_december_template(self, db_session, test_user):
        """Salto de año: la plantilla de dic 2029 genera la fila de ene 2030.

        `budget_recurrence.py:28` filtra con `(month != month) | (year != year)`, agnóstico
        de año — el test confirma el comportamiento correcto que el código ya tiene pero que
        ningún test (ni siquiera HTTP) ejercitaba (Hallazgo 12).
        """
        categoria = self._crear_categoria(db_session, test_user, name="Mercado")
        db_session.add(
            models.Budget(
                amount_limit=Decimal("500.00"),
                currency="COP",
                month=12,
                year=2029,
                is_recurring=True,
                user_id=test_user["id"],
                category_id=categoria.id,
            )
        )
        db_session.commit()

        ensure_recurring_budgets_for_period(db_session, test_user["id"], month=1, year=2030)

        generado = self._filas_del_periodo(db_session, test_user, month=1, year=2030)
        assert len(generado) == 1
        assert generado[0].amount_limit == Decimal("500.00")
        assert generado[0].is_recurring is True  # la copia también es plantilla (Decisión 3.1)

    def test_most_recent_template_wins_across_a_gap_of_several_months(self, db_session, test_user):
        """La plantilla "más reciente" no tiene que ser la del mes inmediatamente anterior —
        si el usuario no abrió la app en varios meses, la más reciente sigue siendo la correcta
        (`mas_reciente_por_categoria` ordena por (year, month))."""
        categoria = self._crear_categoria(db_session, test_user, name="Educación")
        db_session.add_all(
            [
                models.Budget(
                    amount_limit=Decimal("800.00"),
                    currency="COP",
                    month=1,
                    year=2030,
                    is_recurring=True,
                    user_id=test_user["id"],
                    category_id=categoria.id,
                ),
                models.Budget(
                    amount_limit=Decimal("1200.00"),
                    currency="COP",
                    month=3,
                    year=2030,
                    is_recurring=True,
                    user_id=test_user["id"],
                    category_id=categoria.id,
                ),
            ]
        )
        db_session.commit()

        ensure_recurring_budgets_for_period(db_session, test_user["id"], month=6, year=2030)

        generado = self._filas_del_periodo(db_session, test_user, month=6, year=2030)
        assert len(generado) == 1
        assert generado[0].amount_limit == Decimal("1200.00")  # la de marzo, no la de enero

    def test_category_with_existing_non_recurring_row_in_target_period_is_skipped(self, db_session, test_user):
        """Si ya existe CUALQUIER fila (recurrente o no) para (categoría, período), no se
        genera una segunda — `categorias_con_fila` (budget_recurrence.py:39-48) no distingue
        el origen de la fila."""
        categoria = self._crear_categoria(db_session, test_user, name="Suscripciones")
        db_session.add_all(
            [
                models.Budget(
                    amount_limit=Decimal("800.00"),
                    currency="COP",
                    month=1,
                    year=2030,
                    is_recurring=True,
                    user_id=test_user["id"],
                    category_id=categoria.id,
                ),
                models.Budget(
                    amount_limit=Decimal("50.00"),
                    currency="COP",
                    month=2,
                    year=2030,
                    is_recurring=False,
                    user_id=test_user["id"],
                    category_id=categoria.id,
                ),
            ]
        )
        db_session.commit()

        ensure_recurring_budgets_for_period(db_session, test_user["id"], month=2, year=2030)

        filas = self._filas_del_periodo(db_session, test_user, month=2, year=2030)
        assert len(filas) == 1
        assert filas[0].amount_limit == Decimal("50.00")  # la manual, sin pisarla
        assert filas[0].is_recurring is False

    def test_two_categories_each_generate_independently_in_the_same_call(self, db_session, test_user):
        """Dos categorías con plantilla recurrente → una sola llamada genera la fila del
        período objetivo para cada una (una por categoría, sin mezclarse)."""
        mercado = self._crear_categoria(db_session, test_user, name="Mercado")
        transporte = self._crear_categoria(db_session, test_user, name="Transporte")
        db_session.add_all(
            [
                models.Budget(
                    amount_limit=Decimal("800.00"),
                    currency="COP",
                    month=1,
                    year=2030,
                    is_recurring=True,
                    user_id=test_user["id"],
                    category_id=mercado.id,
                ),
                models.Budget(
                    amount_limit=Decimal("300.00"),
                    currency="COP",
                    month=2,
                    year=2030,
                    is_recurring=True,
                    user_id=test_user["id"],
                    category_id=transporte.id,
                ),
            ]
        )
        db_session.commit()

        ensure_recurring_budgets_for_period(db_session, test_user["id"], month=3, year=2030)

        generadas = self._filas_del_periodo(db_session, test_user, month=3, year=2030)
        assert len(generadas) == 2
        assert {f.amount_limit for f in generadas} == {Decimal("800.00"), Decimal("300.00")}
        assert all(f.is_recurring for f in generadas)
        assert {f.category_id for f in generadas} == {mercado.id, transporte.id}

    def test_race_condition_integrity_error_rolls_back_without_raising(self, db_session, test_user, monkeypatch):
        """Simula la carrera de budget_recurrence.py:66-73: otra petición insertó la fila del
        período entre nuestra query de guard y nuestro commit. No debe propagar la excepción —
        el caller depende de que esto nunca tumbe una evaluación en curso (Decisión 3.1)."""
        categoria = self._crear_categoria(db_session, test_user, name="Salud")
        db_session.add(
            models.Budget(
                amount_limit=Decimal("800.00"),
                currency="COP",
                month=1,
                year=2030,
                is_recurring=True,
                user_id=test_user["id"],
                category_id=categoria.id,
            )
        )
        db_session.commit()

        # Mecanismo (limitación documentada — R4):
        # No se puede pre-insertar la ganadora ANTES de llamar: `categorias_con_fila`
        # (budget_recurrence.py:39-48) la vería y `nuevos` quedaría vacío → return temprano
        # sin llegar nunca al commit. Ese montaje "pasaría" el test sin ejercitar la rama
        # (falso positivo). En su lugar se intercala la petición concurrente DENTRO del
        # commit parcheado, entre la query de guard y nuestro flush:
        #   1) nuestro lote sale temporalmente del session (expunge, sin tocar la DB),
        #   2) la ganadora se inserta y comitea de verdad (savepoint liberado: queda durable
        #      y sobrevive al rollback posterior — como la transacción real del otro request),
        #   3) nuestro lote vuelve y el commit real choca contra el índice único parcial
        #      `uq_budgets_user_category_period_active` — IntegrityError GENUINO de SQLite,
        #      el mismo que produce el `db.commit()` de la línea 68 en producción.
        commit_real = db_session.commit
        llamadas = {"n": 0}

        def commit_que_pierde_la_carrera():
            llamadas["n"] += 1
            if llamadas["n"] == 1:
                lote = list(db_session.new)
                for fila in lote:
                    db_session.expunge(fila)
                ganadora = models.Budget(
                    amount_limit=Decimal("999.00"),
                    currency="COP",
                    month=2,
                    year=2030,
                    is_recurring=True,
                    user_id=test_user["id"],
                    category_id=categoria.id,
                )
                db_session.add(ganadora)
                commit_real()  # solo la ganadora pendiente → commit exitoso y durable
                db_session.add_all(lote)  # nuestro lote vuelve al session
                commit_real()  # flush del lote → choque real contra el índice único
            commit_real()

        monkeypatch.setattr(db_session, "commit", commit_que_pierde_la_carrera)

        # No debe lanzar: el except IntegrityError de budget_recurrence.py:69-73 absorbe el
        # choque y hace rollback de NUESTRO lote, sin propagar.
        ensure_recurring_budgets_for_period(db_session, test_user["id"], month=2, year=2030)

        assert llamadas["n"] == 1  # la función SÍ llegó a su commit interno (rama ejercitada)
        filas = self._filas_del_periodo(db_session, test_user, month=2, year=2030)
        assert len(filas) == 1
        assert filas[0].amount_limit == Decimal("999.00")  # la ganadora, sin duplicado
