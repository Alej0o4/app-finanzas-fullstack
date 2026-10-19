"""Funciones puras del CDT (Fase 38 T1): sin HTTP ni DB, con fechas fijas."""

from datetime import date
from decimal import Decimal

from app.services import cdt as svc

D = Decimal


class TestDiasTranscurridos:
    def test_antes_de_abrir_vale_cero(self):
        assert svc.dias_transcurridos(date(2026, 6, 1), date(2026, 12, 1), date(2026, 5, 1)) == 0

    def test_el_dia_de_apertura_vale_cero(self):
        assert svc.dias_transcurridos(date(2026, 6, 1), date(2026, 12, 1), date(2026, 6, 1)) == 0

    def test_a_mitad_de_plazo(self):
        assert svc.dias_transcurridos(date(2026, 6, 1), date(2026, 12, 1), date(2026, 6, 11)) == 10

    def test_se_acota_al_plazo(self):
        assert svc.dias_transcurridos(date(2026, 6, 1), date(2026, 12, 1), date(2027, 6, 1)) == 183


class TestInteresCausado:
    def test_cero_dias_es_cero(self):
        assert svc.interes_causado(D("10000000.00"), D("11.5"), 0) == D("0.00")

    def test_365_dias_es_la_tasa_efectiva_anual_exacta(self):
        assert svc.interes_causado(D("10000000.00"), D("11.5"), 365) == D("1150000.00")

    def test_182_dias(self):
        # 10.000.000 * (1.115^(182/365) - 1), verificado a mano con 28 dígitos.
        assert svc.interes_causado(D("10000000.00"), D("11.5"), 182) == D("557781.59")

    def test_redondea_half_up_a_centavo(self):
        # 100 * (1.1^(1/365) - 1) = 0.02611... -> 0.03
        assert svc.interes_causado(D("100.00"), D("10"), 1) == D("0.03")

    def test_es_decimal_con_dos_decimales(self):
        resultado = svc.interes_causado(D("123.45"), D("7.3"), 100)
        assert isinstance(resultado, Decimal)
        assert resultado == resultado.quantize(D("0.01"))

    def test_dos_anios_compuesto(self):
        assert svc.interes_causado(D("1000.00"), D("10"), 730) == D("210.00")


class TestDiasParaVencer:
    def test_positivo_antes_del_vencimiento(self):
        assert svc.dias_para_vencer(date(2026, 12, 1), date(2026, 11, 20)) == 11

    def test_cero_el_dia_del_vencimiento(self):
        assert svc.dias_para_vencer(date(2026, 12, 1), date(2026, 12, 1)) == 0

    def test_negativo_si_ya_vencio(self):
        assert svc.dias_para_vencer(date(2026, 12, 1), date(2026, 12, 4)) == -3


class TestAlerta:
    def test_borde_16_dias_es_ok(self):
        assert svc.alerta(date(2026, 12, 17), date(2026, 12, 1), "active") == "ok"

    def test_borde_15_dias_es_due_soon(self):
        assert svc.alerta(date(2026, 12, 16), date(2026, 12, 1), "active") == "due_soon"

    def test_el_dia_del_vencimiento_es_matured(self):
        assert svc.alerta(date(2026, 12, 1), date(2026, 12, 1), "active") == "matured"

    def test_vencido_sin_redimir_es_matured(self):
        assert svc.alerta(date(2026, 12, 1), date(2027, 1, 1), "active") == "matured"

    def test_redimido_siempre_es_ok(self):
        assert svc.alerta(date(2026, 12, 1), date(2027, 1, 1), "redeemed") == "ok"
