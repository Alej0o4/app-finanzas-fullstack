"""Funciones puras de transferencias (Fase 39 T1): monto desde tasa, redondeo, misma moneda y
pares sin COP. Sin DB."""

from decimal import Decimal

import pytest

from app.core.exceptions import ValidationError
from app.services.ledger import deltas_transferencia, invertir_deltas, sumar_deltas
from app.services.transfers import calcular_monto_entrada, tasa_implicita

D = Decimal


class TestCalcularMontoEntrada:
    def test_cop_a_usd_con_tasa_divide(self):
        assert calcular_monto_entrada("COP", "USD", D("642000.00"), None, D("3210")) == D("200.00")

    def test_usd_a_cop_con_tasa_multiplica(self):
        assert calcular_monto_entrada("USD", "COP", D("200.00"), None, D("3210")) == D("642000.00")

    def test_redondea_half_up_a_centavo(self):
        # 100 / 3 = 33.3333...
        assert calcular_monto_entrada("COP", "USD", D("100.00"), None, D("3")) == D("33.33")
        # 1.005 * 1 = 1.005 -> half up -> 1.01 (no banker's rounding)
        assert calcular_monto_entrada("USD", "COP", D("1.00"), None, D("1.005")) == D("1.01")

    def test_con_amount_in_se_respeta_tal_cual(self):
        assert calcular_monto_entrada("COP", "USD", D("642000.00"), D("199.50"), None) == D("199.50")

    def test_misma_moneda_sin_amount_in_iguala(self):
        assert calcular_monto_entrada("COP", "COP", D("50.00"), None, None) == D("50.00")

    def test_misma_moneda_con_amount_in_igual_es_valido(self):
        assert calcular_monto_entrada("COP", "COP", D("50.00"), D("50.00"), None) == D("50.00")

    def test_misma_moneda_con_amount_in_distinto_es_422(self):
        with pytest.raises(ValidationError):
            calcular_monto_entrada("COP", "COP", D("50.00"), D("49.00"), None)

    def test_misma_moneda_rechaza_tasa(self):
        with pytest.raises(ValidationError):
            calcular_monto_entrada("COP", "COP", D("50.00"), None, D("1"))

    def test_monedas_distintas_exigen_exactamente_uno(self):
        with pytest.raises(ValidationError):
            calcular_monto_entrada("COP", "USD", D("100.00"), D("1.00"), D("3210"))
        with pytest.raises(ValidationError):
            calcular_monto_entrada("COP", "USD", D("100.00"), None, None)

    def test_par_sin_cop_exige_amount_in_y_rechaza_tasa(self):
        with pytest.raises(ValidationError):
            calcular_monto_entrada("USD", "EUR", D("100.00"), None, D("0.9"))
        assert calcular_monto_entrada("USD", "EUR", D("100.00"), D("92.00"), None) == D("92.00")

    def test_tasa_que_redondea_a_cero_es_422(self):
        with pytest.raises(ValidationError):
            calcular_monto_entrada("COP", "USD", D("0.01"), None, D("100000"))

    def test_resultado_que_desborda_numeric_es_422(self):
        with pytest.raises(ValidationError):
            calcular_monto_entrada("USD", "COP", D("999999999999.00"), None, D("4000"))


class TestTasaImplicita:
    def test_cop_a_usd(self):
        assert tasa_implicita("COP", D("642000.00"), "USD", D("200.00")) == D("3210.0000")

    def test_usd_a_cop(self):
        assert tasa_implicita("USD", D("200.00"), "COP", D("642000.00")) == D("3210.0000")

    def test_misma_moneda_y_par_sin_cop_no_tienen_tasa(self):
        assert tasa_implicita("COP", D("1.00"), "COP", D("1.00")) is None
        assert tasa_implicita("USD", D("1.00"), "EUR", D("0.90")) is None


class TestDeltas:
    def test_origen_resta_destino_suma_y_pueden_diferir(self):
        assert deltas_transferencia(1, 2, D("642000"), D("200")) == {1: D("-642000"), 2: D("200")}

    def test_con_cdt_solo_se_mueve_la_cuenta(self):
        assert deltas_transferencia(1, None, D("10"), D("10")) == {1: D("-10")}
        assert deltas_transferencia(None, 2, D("10"), D("10")) == {2: D("10")}

    def test_sumar_e_invertir(self):
        viejo = deltas_transferencia(1, 2, D("10"), D("10"))
        nuevo = deltas_transferencia(1, 3, D("15"), D("15"))
        assert sumar_deltas(invertir_deltas(viejo), nuevo) == {1: D("-5"), 2: D("-10"), 3: D("15")}
