"""Tests de `app/core/periods.py` (Fase 29, Decisión T1; Fase 34, T1).

Excepción justificada a la convención de la suite: se prueban por call directo y no vía
`TestClient` porque no hay endpoint detrás — los bordes de calendario (bisiesto, cruce
diciembre→enero, techo del mes en curso) se leen mucho mejor sobre funciones puras que
sobre un JSON de respuesta. Precedente: `test_weekly_summary.py`.

`ahora` va inyectado, así que ninguno de estos tests necesita `freeze_time` (que además
rompería el JWT de 15 minutos de `auth_headers` si se usara sobre el suite HTTP).
"""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest

from app.core.exceptions import ValidationError as DomainValidationError
from app.core.periods import dia_local, instante_de_dia, limites_semana, rango_dias, rango_mes, resolver_mes

# Momento de referencia inyectado en todos los casos: 15 de marzo de 2026, 10:30 UTC.
AHORA = datetime(2026, 3, 15, 10, 30, 0, tzinfo=UTC)

BOGOTA = ZoneInfo("America/Bogota")
TOKYO = ZoneInfo("Asia/Tokyo")
NEW_YORK = ZoneInfo("America/New_York")
UTC_TZ = ZoneInfo("UTC")


class TestResolverMes:
    def test_sin_parametros_devuelve_el_mes_actual(self):
        assert resolver_mes(None, None, AHORA, UTC_TZ) == (2026, 3, True)

    def test_solo_year_es_422(self):
        with pytest.raises(DomainValidationError) as exc:
            resolver_mes(2026, None, AHORA, UTC_TZ)
        assert exc.value.status_code == 422
        assert str(exc.value.detail) == "Se deben enviar `year` y `month`, o ninguno."

    def test_solo_month_es_422(self):
        with pytest.raises(DomainValidationError) as exc:
            resolver_mes(None, 3, AHORA, UTC_TZ)
        assert exc.value.status_code == 422
        assert str(exc.value.detail) == "Se deben enviar `year` y `month`, o ninguno."

    def test_mes_actual_explicito_no_es_error(self):
        assert resolver_mes(2026, 3, AHORA, UTC_TZ) == (2026, 3, True)

    def test_mes_pasado_no_es_mes_actual(self):
        assert resolver_mes(2026, 2, AHORA, UTC_TZ) == (2026, 2, False)

    def test_mes_pasado_que_cruza_diciembre_enero(self):
        """Enero: el mes anterior es diciembre del año anterior (rollover de año)."""
        enero = datetime(2026, 1, 9, 8, 0, 0, tzinfo=UTC)
        assert resolver_mes(2025, 12, enero, UTC_TZ) == (2025, 12, False)

    def test_diciembre_como_mes_actual(self):
        diciembre = datetime(2026, 12, 31, 23, 0, 0, tzinfo=UTC)
        assert resolver_mes(None, None, diciembre, UTC_TZ) == (2026, 12, True)
        # Enero del año siguiente ya es futuro
        with pytest.raises(DomainValidationError):
            resolver_mes(2027, 1, diciembre, UTC_TZ)

    @pytest.mark.parametrize("month", [0, 13, -1, 100])
    def test_month_fuera_de_rango_es_422(self, month):
        with pytest.raises(DomainValidationError) as exc:
            resolver_mes(2026, month, AHORA, UTC_TZ)
        assert exc.value.status_code == 422
        assert "1 y 12" in str(exc.value.detail)

    def test_year_cero_es_422_y_no_un_500(self):
        """H13: sin el chequeo, `datetime(0, ...)` de `limites_mes_utc` lanzaría
        `ValueError` y el usuario vería un 500."""
        with pytest.raises(DomainValidationError) as exc:
            resolver_mes(0, 3, AHORA, UTC_TZ)
        assert exc.value.status_code == 422
        assert "year" in str(exc.value.detail)

    @pytest.mark.parametrize("year", [10_000, 99_999])
    def test_year_sobre_el_maximo_de_datetime_es_422_y_no_un_500(self, year):
        """El otro lado del mismo hueco que H13: `datetime(99999, 1, 1)` también lanza
        `ValueError`. La spec solo blindaba el piso, pero el modo de fallo es idéntico —
        un 500 por un query param."""
        with pytest.raises(DomainValidationError) as exc:
            resolver_mes(year, 3, AHORA, UTC_TZ)
        assert exc.value.status_code == 422
        assert "year" in str(exc.value.detail)

    def test_mes_futuro_es_422(self):
        with pytest.raises(DomainValidationError) as exc:
            resolver_mes(2026, 4, AHORA, UTC_TZ)
        assert exc.value.status_code == 422
        assert "futuro" in str(exc.value.detail)

    def test_mismo_mes_de_otro_anio_futuro_es_422(self):
        """Marzo de 2027 es posterior a marzo de 2026 aunque el número de mes coincida —
        por eso la comparación es de tuplas `(year, month)` y no aritmética de días."""
        with pytest.raises(DomainValidationError):
            resolver_mes(2027, 3, AHORA, UTC_TZ)

    def test_todo_422_de_este_modulo_lleva_detail_string_explicito(self):
        """`DomainError` sin argumento cae al default `"Error de dominio."` de la clase
        base: cada raise de este módulo pasa su mensaje."""
        for year, month in [(2026, None), (None, 3), (2026, 13), (0, 3), (10_000, 3), (2026, 4)]:
            with pytest.raises(DomainValidationError) as exc:
                resolver_mes(year, month, AHORA, UTC_TZ)
            assert isinstance(exc.value.detail, str)
            assert exc.value.detail != "Error de dominio."


class TestRangoMes:
    """Fase 31 (B6, QA-019): límite superior EXCLUSIVO; Fase 34 (B6): en la zona del usuario,
    límites aware UTC."""

    def test_mes_actual_se_acota_a_ahora(self):
        inicio, limite = rango_mes(2026, 3, AHORA, UTC_TZ)
        assert inicio == datetime(2026, 3, 1, tzinfo=UTC)
        assert limite == AHORA

    def test_limites_son_aware_utc(self):
        inicio, limite = rango_mes(2026, 3, AHORA, BOGOTA)
        assert inicio.utcoffset().total_seconds() == 0
        assert limite.utcoffset().total_seconds() == 0

    def test_mes_actual_con_ahora_naive_se_lee_como_utc(self):
        inicio, limite = rango_mes(2026, 3, datetime(2026, 3, 15, 10, 30), UTC_TZ)
        assert limite == AHORA

    def test_mes_pasado_no_se_acota_a_ahora(self):
        inicio, limite = rango_mes(2026, 2, AHORA, UTC_TZ)
        assert inicio == datetime(2026, 2, 1, tzinfo=UTC)
        assert limite == datetime(2026, 3, 1, tzinfo=UTC)

    def test_febrero_bisiesto_y_no_bisiesto(self):
        ahora = datetime(2026, 3, 15, tzinfo=UTC)
        assert rango_mes(2024, 2, ahora, UTC_TZ)[1] == datetime(2024, 3, 1, tzinfo=UTC)
        assert rango_mes(2026, 2, ahora, UTC_TZ)[1] == datetime(2026, 3, 1, tzinfo=UTC)

    def test_mes_pasado_que_cruza_diciembre_enero(self):
        inicio, limite = rango_mes(2025, 12, datetime(2026, 1, 9, tzinfo=UTC), UTC_TZ)
        assert inicio == datetime(2025, 12, 1, tzinfo=UTC)
        assert limite == datetime(2026, 1, 1, tzinfo=UTC)

    def test_mes_futuro_devuelve_el_mes_completo_sin_excepcion(self):
        """Presupuestos anticipados: el motor de alertas evalúa meses futuros completos."""
        inicio, limite = rango_mes(2026, 4, AHORA, UTC_TZ)
        assert inicio == datetime(2026, 4, 1, tzinfo=UTC)
        assert limite == datetime(2026, 5, 1, tzinfo=UTC)

    def test_bogota_mes_pasado(self):
        inicio, limite = rango_mes(2026, 2, AHORA, BOGOTA)
        assert inicio == datetime(2026, 2, 1, 5, tzinfo=UTC)
        assert limite == datetime(2026, 3, 1, 5, tzinfo=UTC)

    def test_tokyo_mes_pasado_va_adelantado_al_utc(self):
        inicio, limite = rango_mes(2026, 2, AHORA, TOKYO)
        assert inicio == datetime(2026, 1, 31, 15, tzinfo=UTC)
        assert limite == datetime(2026, 2, 28, 15, tzinfo=UTC)

    def test_new_york_dst_en_los_dos_extremos_del_mes(self):
        # Marzo 2026: el 8 pasa de EST (-5) a EDT (-4).
        inicio, limite = rango_mes(2026, 3, datetime(2026, 5, 1, tzinfo=UTC), NEW_YORK)
        assert inicio == datetime(2026, 3, 1, 5, tzinfo=UTC)
        assert limite == datetime(2026, 4, 1, 4, tzinfo=UTC)
        # Noviembre 2026: el 1 pasa de EDT (-4) a EST (-5).
        inicio, limite = rango_mes(2026, 11, datetime(2027, 1, 1, tzinfo=UTC), NEW_YORK)
        assert inicio == datetime(2026, 11, 1, 4, tzinfo=UTC)
        assert limite == datetime(2026, 12, 1, 5, tzinfo=UTC)


class TestMesActualSegunZona:
    def test_ultimo_dia_del_mes_a_las_22_bogota_sigue_siendo_ese_mes(self):
        # 2026-03-31 22:00 Bogotá = 2026-04-01 03:00 UTC
        ahora = datetime(2026, 4, 1, 3, 0, tzinfo=UTC)
        assert resolver_mes(None, None, ahora, BOGOTA) == (2026, 3, True)
        assert resolver_mes(None, None, ahora, UTC_TZ) == (2026, 4, True)

    def test_tokyo_va_adelantado(self):
        # 2026-03-31 20:00 UTC = 2026-04-01 05:00 Tokyo
        ahora = datetime(2026, 3, 31, 20, 0, tzinfo=UTC)
        assert resolver_mes(None, None, ahora, TOKYO) == (2026, 4, True)

    def test_mes_futuro_se_evalua_contra_el_mes_de_la_zona(self):
        ahora = datetime(2026, 4, 1, 3, 0, tzinfo=UTC)  # abril UTC, marzo Bogotá
        with pytest.raises(DomainValidationError):
            resolver_mes(2026, 4, ahora, BOGOTA)

    def test_techo_del_mes_en_curso_es_ahora(self):
        ahora = datetime(2026, 4, 1, 3, 0, tzinfo=UTC)
        inicio, limite = rango_mes(2026, 3, ahora, BOGOTA)
        assert inicio == datetime(2026, 3, 1, 5, tzinfo=UTC)
        assert limite == ahora


class TestLimitesSemana:
    def test_bogota_domingo_noche_pertenece_a_su_semana(self):
        # Domingo 2026-03-15 22:00 Bogotá = lunes 16 03:00 UTC
        inst = datetime(2026, 3, 16, 3, 0, tzinfo=UTC)
        inicio, fin = limites_semana(inst, BOGOTA)
        assert inicio == datetime(2026, 3, 9, 5, tzinfo=UTC)
        assert fin == datetime(2026, 3, 16, 5, tzinfo=UTC)

    def test_tokyo_lunes_temprano_ya_es_la_semana_nueva(self):
        # Domingo 2026-03-15 16:00 UTC = lunes 16 01:00 Tokyo
        inst = datetime(2026, 3, 15, 16, 0, tzinfo=UTC)
        inicio, fin = limites_semana(inst, TOKYO)
        assert inicio == datetime(2026, 3, 15, 15, tzinfo=UTC)
        assert fin == datetime(2026, 3, 22, 15, tzinfo=UTC)

    def test_new_york_semana_con_cambio_de_horario_dura_167_horas(self):
        # Semana lunes 2026-03-02 .. lunes 03-09; el DST es domingo 03-08 -> semana de 167 h.
        inicio, fin = limites_semana(datetime(2026, 3, 8, 12, tzinfo=UTC), NEW_YORK)
        assert inicio == datetime(2026, 3, 2, 5, tzinfo=UTC)
        assert fin == datetime(2026, 3, 9, 4, tzinfo=UTC)
        assert (fin - inicio).total_seconds() == 167 * 3600

    def test_new_york_semana_de_noviembre_dura_169_horas(self):
        inicio, fin = limites_semana(datetime(2026, 11, 1, 12, tzinfo=UTC), NEW_YORK)
        assert inicio == datetime(2026, 10, 26, 4, tzinfo=UTC)
        assert fin == datetime(2026, 11, 2, 5, tzinfo=UTC)
        assert (fin - inicio).total_seconds() == 169 * 3600


class TestRangoDias:
    def test_bogota_fin_exclusivo_incluye_todo_el_ultimo_dia(self):
        inicio, fin = rango_dias(date(2026, 3, 10), date(2026, 3, 12), BOGOTA)
        assert inicio == datetime(2026, 3, 10, 5, tzinfo=UTC)
        assert fin == datetime(2026, 3, 13, 5, tzinfo=UTC)

    def test_tokyo(self):
        inicio, fin = rango_dias(date(2026, 3, 10), date(2026, 3, 10), TOKYO)
        assert inicio == datetime(2026, 3, 9, 15, tzinfo=UTC)
        assert fin == datetime(2026, 3, 10, 15, tzinfo=UTC)

    def test_new_york_dia_del_cambio_de_horario_dura_23_horas(self):
        inicio, fin = rango_dias(date(2026, 3, 8), date(2026, 3, 8), NEW_YORK)
        assert (fin - inicio).total_seconds() == 23 * 3600
        inicio, fin = rango_dias(date(2026, 11, 1), date(2026, 11, 1), NEW_YORK)
        assert (fin - inicio).total_seconds() == 25 * 3600


class TestDiaLocal:
    def test_mismo_instante_distinto_dia_segun_zona(self):
        inst = datetime(2026, 3, 15, 3, 0, tzinfo=UTC)
        assert dia_local(inst, BOGOTA) == date(2026, 3, 14)
        assert dia_local(inst, TOKYO) == date(2026, 3, 15)
        assert dia_local(inst, NEW_YORK) == date(2026, 3, 14)

    def test_naive_se_lee_como_utc(self):
        assert dia_local(datetime(2026, 3, 15, 3, 0), BOGOTA) == date(2026, 3, 14)


class TestInstanteDeDia:
    def test_hoy_conserva_la_hora_real(self):
        ahora = datetime(2026, 3, 15, 3, 0, tzinfo=UTC)  # 14 en Bogotá
        assert instante_de_dia(date(2026, 3, 14), ahora, BOGOTA) == ahora

    def test_otro_dia_es_mediodia_local(self):
        assert instante_de_dia(date(2026, 3, 10), AHORA, BOGOTA) == datetime(2026, 3, 10, 17, tzinfo=UTC)
        assert instante_de_dia(date(2026, 3, 10), AHORA, TOKYO) == datetime(2026, 3, 10, 3, tzinfo=UTC)
        assert instante_de_dia(date(2026, 3, 10), AHORA, NEW_YORK) == datetime(2026, 3, 10, 16, tzinfo=UTC)

    def test_el_dia_local_del_resultado_es_el_pedido(self):
        for tz in (BOGOTA, TOKYO, NEW_YORK):
            assert dia_local(instante_de_dia(date(2026, 3, 10), AHORA, tz), tz) == date(2026, 3, 10)
