"""Funciones puras de recurrentes (Fase 37 T1): sin HTTP ni DB, con fechas fijas."""

from datetime import date
from decimal import Decimal

import pytest

from app.services import recurring as svc

D = Decimal


class TestSiguienteOcurrencia:
    def test_mensual_dia_31_se_recorta_y_vuelve_a_31(self):
        inicio = date(2026, 1, 31)
        feb = svc.siguiente_ocurrencia(inicio, "monthly", date(2026, 1, 31))
        assert feb == date(2026, 2, 28)
        mar = svc.siguiente_ocurrencia(inicio, "monthly", feb)
        assert mar == date(2026, 3, 31)  # desde el ancla, no desde la anterior
        assert svc.siguiente_ocurrencia(inicio, "monthly", mar) == date(2026, 4, 30)

    def test_mensual_febrero_bisiesto(self):
        assert svc.siguiente_ocurrencia(date(2028, 1, 31), "monthly", date(2028, 1, 31)) == date(2028, 2, 29)

    def test_mensual_cruce_de_anio(self):
        assert svc.siguiente_ocurrencia(date(2026, 12, 15), "monthly", date(2026, 12, 15)) == date(2027, 1, 15)

    def test_anual_29_de_febrero(self):
        inicio = date(2028, 2, 29)
        assert svc.siguiente_ocurrencia(inicio, "yearly", inicio) == date(2029, 2, 28)
        assert svc.siguiente_ocurrencia(inicio, "yearly", date(2031, 2, 28)) == date(2032, 2, 29)

    def test_semanal_cruzando_anio(self):
        assert svc.siguiente_ocurrencia(date(2026, 12, 28), "weekly", date(2026, 12, 28)) == date(2027, 1, 4)

    def test_actual_entre_ocurrencias_devuelve_la_siguiente_estricta(self):
        assert svc.siguiente_ocurrencia(date(2026, 1, 10), "monthly", date(2026, 3, 20)) == date(2026, 4, 10)

    def test_actual_anterior_al_ancla_devuelve_el_ancla(self):
        assert svc.siguiente_ocurrencia(date(2026, 5, 1), "monthly", date(2026, 1, 1)) == date(2026, 5, 1)


class TestPrimeraDesde:
    def test_desde_igual_a_una_ocurrencia_la_incluye(self):
        assert svc.primera_desde(date(2026, 1, 15), "monthly", date(2026, 4, 15)) == date(2026, 4, 15)

    def test_desde_posterior_salta_a_la_siguiente(self):
        assert svc.primera_desde(date(2026, 1, 15), "monthly", date(2026, 4, 16)) == date(2026, 5, 15)

    def test_desde_anterior_al_ancla_devuelve_el_ancla(self):
        assert svc.primera_desde(date(2026, 1, 15), "yearly", date(2025, 1, 1)) == date(2026, 1, 15)

    def test_semanal(self):
        assert svc.primera_desde(date(2026, 10, 1), "weekly", date(2026, 10, 9)) == date(2026, 10, 15)

    def test_anual_dia_31_mes_corto_conserva_ancla(self):
        assert svc.primera_desde(date(2026, 8, 31), "yearly", date(2027, 8, 1)) == date(2027, 8, 31)


class TestEquivalenteMensual:
    def test_mensual_es_el_monto(self):
        assert svc.equivalente_mensual(D("1500000.00"), "monthly") == D("1500000.00")

    def test_anual_se_divide_en_12(self):
        assert svc.equivalente_mensual(D("1200000.00"), "yearly") == D("100000.00")

    def test_anual_redondea_half_up(self):
        assert svc.equivalente_mensual(D("100.10"), "yearly") == D("8.34")  # 8.3416...
        assert svc.equivalente_mensual(D("0.30"), "yearly") == D("0.03")  # 0.025 -> 0.03

    def test_semanal_52_sobre_12(self):
        assert svc.equivalente_mensual(D("100.00"), "weekly") == D("433.33")


class TestOcurrenciasEn:
    def test_ventana_inclusiva(self):
        out = svc.ocurrencias_en(date(2026, 1, 31), "monthly", date(2026, 1, 31), date(2026, 4, 30), 400)
        assert out == [date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31), date(2026, 4, 30)]

    def test_respeta_el_tope(self):
        out = svc.ocurrencias_en(date(2026, 1, 1), "weekly", date(2026, 1, 1), date(2030, 1, 1), 5)
        assert len(out) == 5

    def test_desde_posterior_al_hasta_es_vacio(self):
        assert svc.ocurrencias_en(date(2026, 1, 1), "monthly", date(2026, 6, 1), date(2026, 5, 1), 10) == []


class TestNormalizarNombre:
    def test_strip_minusculas_y_espacios_colapsados(self):
        assert svc.normalizar_nombre("  Seguro   del  CARRO ") == "seguro del carro"


def _es_candidato_anual(fechas, montos) -> bool:
    return svc.indice_ultima_pareja_anual(fechas, montos) is not None


class TestEsCandidatoAnual:
    def test_par_a_365_dias_con_monto_similar(self):
        assert _es_candidato_anual([date(2025, 10, 1), date(2026, 10, 1)], [D("1000"), D("1100")])

    @pytest.mark.parametrize("dias,esperado", [(349, False), (350, True), (380, True), (381, False)])
    def test_bordes_de_dias(self, dias, esperado):
        a = date(2025, 1, 1)
        b = date.fromordinal(a.toordinal() + dias)
        assert _es_candidato_anual([a, b], [D("100"), D("100")]) is esperado

    @pytest.mark.parametrize(
        "ultimo,esperado", [("120.00", True), ("120.01", False), ("80.00", True), ("79.99", False)]
    )
    def test_borde_de_monto_20_por_ciento(self, ultimo, esperado):
        fechas = [date(2025, 1, 1), date(2026, 1, 1)]
        assert _es_candidato_anual(fechas, [D("100.00"), D(ultimo)]) is esperado

    def test_una_sola_transaccion_no_alcanza(self):
        assert not _es_candidato_anual([date(2026, 1, 1)], [D("100")])

    def test_dos_pagos_muy_cercanos_no_son_anuales(self):
        assert not _es_candidato_anual([date(2026, 1, 1), date(2026, 2, 1)], [D("100"), D("100")])

    def test_el_monto_se_mide_en_la_pareja_anual_no_en_las_dos_ultimas(self):
        fechas = [date(2025, 3, 10), date(2026, 3, 8), date(2026, 3, 12)]
        montos = [D("1000"), D("1000"), D("50")]
        assert _es_candidato_anual(fechas, montos)
        assert svc.indice_ultima_pareja_anual(fechas, montos) == 1

    def test_pareja_anual_con_monto_distinto_no_califica(self):
        fechas = [date(2025, 3, 10), date(2026, 3, 8), date(2026, 3, 12)]
        assert not _es_candidato_anual(fechas, [D("1000"), D("1500"), D("1500")])

    def test_acepta_fechas_desordenadas(self):
        assert _es_candidato_anual([date(2026, 10, 1), date(2025, 10, 1)], [D("1100"), D("1000")])
