"""Tests de `app/core/periods.py` (Fase 29, Decisión T1).

Excepción justificada a la convención de la suite: se prueban por call directo y no vía
`TestClient` porque no hay endpoint detrás — los bordes de calendario (bisiesto, cruce
diciembre→enero, techo del mes en curso) se leen mucho mejor sobre funciones puras que
sobre un JSON de respuesta. Precedente: `test_weekly_summary.py`.

`ahora` va inyectado, así que ninguno de estos tests necesita `freeze_time` (que además
rompería el JWT de 15 minutos de `auth_headers` si se usara sobre el suite HTTP).
"""

from datetime import UTC, date, datetime

import pytest

from app.core.exceptions import ValidationError as DomainValidationError
from app.core.periods import limites_mes_utc, resolver_mes

# Momento de referencia inyectado en todos los casos: 15 de marzo de 2026, 10:30 UTC.
AHORA = datetime(2026, 3, 15, 10, 30, 0, tzinfo=UTC)


class TestResolverMes:
    def test_sin_parametros_devuelve_el_mes_actual(self):
        assert resolver_mes(None, None, AHORA) == (2026, 3, True)

    def test_solo_year_es_422(self):
        with pytest.raises(DomainValidationError) as exc:
            resolver_mes(2026, None, AHORA)
        assert exc.value.status_code == 422
        assert str(exc.value.detail) == "Se deben enviar `year` y `month`, o ninguno."

    def test_solo_month_es_422(self):
        with pytest.raises(DomainValidationError) as exc:
            resolver_mes(None, 3, AHORA)
        assert exc.value.status_code == 422
        assert str(exc.value.detail) == "Se deben enviar `year` y `month`, o ninguno."

    def test_mes_actual_explicito_no_es_error(self):
        assert resolver_mes(2026, 3, AHORA) == (2026, 3, True)

    def test_mes_pasado_no_es_mes_actual(self):
        assert resolver_mes(2026, 2, AHORA) == (2026, 2, False)

    def test_mes_pasado_que_cruza_diciembre_enero(self):
        """Enero: el mes anterior es diciembre del año anterior (rollover de año)."""
        enero = datetime(2026, 1, 9, 8, 0, 0, tzinfo=UTC)
        assert resolver_mes(2025, 12, enero) == (2025, 12, False)

    def test_diciembre_como_mes_actual(self):
        diciembre = datetime(2026, 12, 31, 23, 0, 0, tzinfo=UTC)
        assert resolver_mes(None, None, diciembre) == (2026, 12, True)
        # Enero del año siguiente ya es futuro
        with pytest.raises(DomainValidationError):
            resolver_mes(2027, 1, diciembre)

    @pytest.mark.parametrize("month", [0, 13, -1, 100])
    def test_month_fuera_de_rango_es_422(self, month):
        with pytest.raises(DomainValidationError) as exc:
            resolver_mes(2026, month, AHORA)
        assert exc.value.status_code == 422
        assert "1 y 12" in str(exc.value.detail)

    def test_year_cero_es_422_y_no_un_500(self):
        """H13: sin el chequeo, `datetime(0, ...)` de `limites_mes_utc` lanzaría
        `ValueError` y el usuario vería un 500."""
        with pytest.raises(DomainValidationError) as exc:
            resolver_mes(0, 3, AHORA)
        assert exc.value.status_code == 422
        assert "year" in str(exc.value.detail)

    @pytest.mark.parametrize("year", [10_000, 99_999])
    def test_year_sobre_el_maximo_de_datetime_es_422_y_no_un_500(self, year):
        """El otro lado del mismo hueco que H13: `datetime(99999, 1, 1)` también lanza
        `ValueError`. La spec solo blindaba el piso, pero el modo de fallo es idéntico —
        un 500 por un query param."""
        with pytest.raises(DomainValidationError) as exc:
            resolver_mes(year, 3, AHORA)
        assert exc.value.status_code == 422
        assert "year" in str(exc.value.detail)

    def test_mes_futuro_es_422(self):
        with pytest.raises(DomainValidationError) as exc:
            resolver_mes(2026, 4, AHORA)
        assert exc.value.status_code == 422
        assert "futuro" in str(exc.value.detail)

    def test_mismo_mes_de_otro_anio_futuro_es_422(self):
        """Marzo de 2027 es posterior a marzo de 2026 aunque el número de mes coincida —
        por eso la comparación es de tuplas `(year, month)` y no aritmética de días."""
        with pytest.raises(DomainValidationError):
            resolver_mes(2027, 3, AHORA)

    def test_todo_422_de_este_modulo_lleva_detail_string_explicito(self):
        """`DomainError` sin argumento cae al default `"Error de dominio."` de la clase
        base: cada raise de este módulo pasa su mensaje."""
        for year, month in [(2026, None), (None, 3), (2026, 13), (0, 3), (10_000, 3), (2026, 4)]:
            with pytest.raises(DomainValidationError) as exc:
                resolver_mes(year, month, AHORA)
            assert isinstance(exc.value.detail, str)
            assert exc.value.detail != "Error de dominio."


class TestLimitesMesUtc:
    def test_mes_actual_se_acota_a_ahora(self):
        inicio, limite = limites_mes_utc(2026, 3, AHORA)
        assert inicio == datetime(2026, 3, 1)
        assert limite == datetime(2026, 3, 15, 10, 30, 0)  # naive, sin tzinfo

    def test_mes_actual_devuelve_limite_naive_aunque_ahora_venga_tz_aware(self):
        """Los callers pasan `datetime.now(UTC)` y las columnas `Transaction.date` son
        naive en SQLite: comparar tz-aware contra naive revienta en el filter."""
        inicio, limite = limites_mes_utc(2026, 3, AHORA)
        assert limite.tzinfo is None
        assert inicio.tzinfo is None

    def test_mes_actual_con_ahora_naive_no_lo_rompe(self):
        ahora_naive = datetime(2026, 3, 15, 10, 30, 0)
        inicio, limite = limites_mes_utc(2026, 3, ahora_naive)
        assert limite == ahora_naive
        assert limite.tzinfo is None

    def test_mes_pasado_no_se_acota_a_ahora(self):
        inicio, limite = limites_mes_utc(2026, 2, AHORA)
        assert inicio == datetime(2026, 2, 1)
        assert limite == datetime(2026, 2, 28, 23, 59, 59)

    def test_febrero_bisiesto_29_dias(self):
        inicio, limite = limites_mes_utc(2024, 2, datetime(2026, 3, 15, tzinfo=UTC))
        assert inicio == datetime(2024, 2, 1)
        assert limite == datetime(2024, 2, 29, 23, 59, 59)

    def test_febrero_no_bisiesto_28_dias(self):
        inicio, limite = limites_mes_utc(2026, 2, datetime(2026, 3, 15, tzinfo=UTC))
        assert limite == datetime(2026, 2, 28, 23, 59, 59)

    def test_mes_pasado_que_cruza_diciembre_enero(self):
        inicio, limite = limites_mes_utc(2025, 12, datetime(2026, 1, 9, tzinfo=UTC))
        assert inicio == datetime(2025, 12, 1)
        assert limite == datetime(2025, 12, 31, 23, 59, 59)

    def test_mes_futuro_devuelve_el_mes_completo_sin_excepcion(self):
        """Regresión del motivo de la separación: `budget_alerts.spent_por_categoria_y_
        moneda` se llama legítimamente con meses futuros (presupuestos anticipados) y su
        llamador se traga las excepciones. Si esto levantara, el motor de alertas
        moriría en silencio."""
        inicio, limite = limites_mes_utc(2026, 4, AHORA)
        assert inicio == datetime(2026, 4, 1)
        assert limite == datetime(2026, 4, 30, 23, 59, 59)
        assert limite.date() == date(2026, 4, 30)
