"""Funciones puras de sobres (Fase 35 T1 + T5): sin HTTP, con `hoy`/`ahora` fijos."""

from datetime import UTC, date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from app.models import models
from app.services import funds as svc

BOGOTA = ZoneInfo("America/Bogota")
D = Decimal


class TestMesesRestantes:
    def test_sin_fecha(self):
        assert svc.meses_restantes(None, date(2026, 10, 17)) is None

    def test_mismo_mes_cuenta_como_uno(self):
        assert svc.meses_restantes(date(2026, 10, 30), date(2026, 10, 17)) == 1

    def test_mes_siguiente(self):
        assert svc.meses_restantes(date(2026, 11, 5), date(2026, 10, 17)) == 1

    def test_diciembre_desde_octubre(self):
        assert svc.meses_restantes(date(2026, 12, 15), date(2026, 10, 17)) == 2

    def test_cruce_de_anio(self):
        assert svc.meses_restantes(date(2027, 2, 1), date(2026, 11, 30)) == 3

    def test_fecha_pasada_es_cero(self):
        assert svc.meses_restantes(date(2026, 10, 16), date(2026, 10, 17)) == 0

    def test_hoy_es_el_objetivo(self):
        assert svc.meses_restantes(date(2026, 10, 17), date(2026, 10, 17)) == 1


class TestAporteRequerido:
    def test_redondea_hacia_arriba_al_centavo(self):
        # 1000 / 3 = 333.333... → 333.34 (cubre la meta, nunca se queda corto)
        assert svc.aporte_requerido(D("1000.00"), 3) == D("333.34")

    def test_division_exacta(self):
        assert svc.aporte_requerido(D("1200.00"), 12) == D("100.00")

    def test_sin_fecha(self):
        assert svc.aporte_requerido(D("500.00"), None) is None

    def test_meta_cumplida(self):
        assert svc.aporte_requerido(D("0.00"), 4) is None

    def test_fecha_vencida_pide_todo(self):
        assert svc.aporte_requerido(D("800.00"), 0) == D("800.00")

    def test_sin_meta(self):
        assert svc.aporte_requerido(None, 4) is None


class TestProximaCuota:
    """A2: cuota del mes siguiente = restante / (meses - 1), hacia arriba al centavo."""

    def test_cuota_cumplida_reparte_lo_que_falta_en_los_meses_que_quedan(self):
        # Meta 2.000.000, aportado 1.000.000, quedan 3 meses (este incluido): 1.000.000 / 2
        assert svc.proxima_cuota(D("1000000.00"), 3) == D("500000.00")

    def test_redondea_hacia_arriba_al_centavo(self):
        assert svc.proxima_cuota(D("1000.00"), 4) == D("333.34")

    def test_ultimo_mes_no_hay_proxima(self):
        assert svc.proxima_cuota(D("500.00"), 1) is None

    def test_fecha_vencida_no_hay_proxima(self):
        assert svc.proxima_cuota(D("500.00"), 0) is None

    def test_sin_fecha(self):
        assert svc.proxima_cuota(D("500.00"), None) is None

    def test_sin_nada_por_aportar(self):
        assert svc.proxima_cuota(D("0.00"), 5) is None
        assert svc.proxima_cuota(None, 5) is None

    def test_cruce_de_anio(self):
        # nov 30 -> 2027-02-01 son 3 meses; la próxima reparte entre 2
        meses = svc.meses_restantes(date(2027, 2, 1), date(2026, 11, 30))
        assert svc.proxima_cuota(D("100.00"), meses) == D("50.00")


class TestRitmo:
    creado = date(2026, 1, 1)
    objetivo = date(2026, 12, 31)  # 364 días

    def test_cumplido(self):
        assert svc.ritmo(D("1000.00"), D("1000.00"), self.creado, self.objetivo, date(2026, 3, 1)) == "completed"

    def test_cumplido_sin_fecha(self):
        assert svc.ritmo(D("1000.00"), D("900.00"), self.creado, None, date(2026, 3, 1)) == "completed"

    def test_sin_fecha_no_hay_ritmo(self):
        assert svc.ritmo(D("10.00"), D("1000.00"), self.creado, None, date(2026, 3, 1)) is None

    def test_sin_meta_no_hay_ritmo(self):
        assert svc.ritmo(D("10.00"), None, self.creado, self.objetivo, date(2026, 3, 1)) is None

    def test_al_dia_el_primer_dia(self):
        assert svc.ritmo(D("0.00"), D("1000.00"), self.creado, self.objetivo, self.creado) == "on_track"

    def test_atrasado_a_mitad_de_camino_sin_aportes(self):
        # 182/364 = 50% → esperado 500
        assert svc.ritmo(D("0.00"), D("1000.00"), self.creado, self.objetivo, date(2026, 7, 2)) == "behind"

    def test_al_dia_con_exactamente_lo_esperado(self):
        assert svc.ritmo(D("500.00"), D("1000.00"), self.creado, self.objetivo, date(2026, 7, 2)) == "on_track"

    def test_un_centavo_menos_es_atrasado(self):
        assert svc.ritmo(D("499.99"), D("1000.00"), self.creado, self.objetivo, date(2026, 7, 2)) == "behind"

    def test_fecha_vencida_sin_cumplir(self):
        assert svc.ritmo(D("999.00"), D("1000.00"), self.creado, self.objetivo, date(2027, 1, 5)) == "behind"

    def test_objetivo_igual_a_creacion(self):
        assert svc.ritmo(D("1.00"), D("1000.00"), self.creado, self.creado, self.creado) == "behind"


class TestMetaYProgreso:
    def test_meta_fija(self):
        assert svc.meta_efectiva(D("500.00"), None, D("100.00")) == D("500.00")

    def test_meta_en_meses(self):
        assert svc.meta_efectiva(None, 3, D("1234.56")) == D("3703.68")

    def test_meta_en_meses_sin_historial(self):
        assert svc.meta_efectiva(None, 3, None) is None

    def test_progreso_capado(self):
        assert svc.progreso(D("1500.00"), D("1000.00")) == 100.0
        assert svc.progreso(D("250.00"), D("1000.00")) == 25.0
        assert svc.progreso(D("1.00"), None) is None

    def test_runway(self):
        assert svc.runway(D("5000.00"), D("1000.00")) == D("5.0")
        assert svc.runway(D("5000.00"), None) is None


class TestPromedioGastoMensual:
    """T5: promedio de hasta 3 meses completos, en la zona del usuario."""

    @pytest.fixture
    def contexto(self, db_session, register_and_login, make_account, make_category, client):
        usuario = register_and_login(email="promedio@example.com")
        cuenta = make_account(usuario["headers"], balance="0.00")
        categoria = make_category(usuario["headers"])

        def _gasto(cuando: datetime, monto: str, moneda: str = "COP", tipo: str = "expense"):
            db_session.add(
                models.Transaction(
                    user_id=usuario["id"],
                    account_id=cuenta["id"],
                    category_id=categoria["id"],
                    amount=D(monto),
                    currency=moneda,
                    type=tipo,
                    date=cuando,
                )
            )
            db_session.commit()

        return usuario["id"], _gasto

    ahora = datetime(2026, 10, 17, 15, 0, tzinfo=UTC)

    def test_sin_transacciones(self, db_session, contexto):
        uid, _ = contexto
        assert svc.promedio_gasto_mensual(db_session, uid, "COP", self.ahora, BOGOTA) is None

    def test_tres_meses_completos(self, db_session, contexto):
        uid, gasto = contexto
        gasto(datetime(2026, 7, 10, 17, tzinfo=UTC), "300.00")
        gasto(datetime(2026, 8, 10, 17, tzinfo=UTC), "600.00")
        gasto(datetime(2026, 9, 10, 17, tzinfo=UTC), "900.00")
        gasto(datetime(2026, 10, 2, 17, tzinfo=UTC), "99999.00")  # mes en curso: no cuenta
        gasto(datetime(2026, 9, 10, 17, tzinfo=UTC), "50.00", moneda="USD")  # otra moneda
        gasto(datetime(2026, 9, 11, 17, tzinfo=UTC), "777.00", tipo="income")  # no es gasto
        assert svc.promedio_gasto_mensual(db_session, uid, "COP", self.ahora, BOGOTA) == D("600.00")

    def test_historial_menor_a_tres_meses(self, db_session, contexto):
        """Solo agosto y septiembre son completos desde la primera transacción: N = 2."""
        uid, gasto = contexto
        gasto(datetime(2026, 8, 20, 17, tzinfo=UTC), "400.00")
        gasto(datetime(2026, 9, 20, 17, tzinfo=UTC), "200.00")
        assert svc.promedio_gasto_mensual(db_session, uid, "COP", self.ahora, BOGOTA) == D("300.00")

    def test_primera_transaccion_en_el_mes_en_curso(self, db_session, contexto):
        uid, gasto = contexto
        gasto(datetime(2026, 10, 3, 17, tzinfo=UTC), "400.00")
        assert svc.promedio_gasto_mensual(db_session, uid, "COP", self.ahora, BOGOTA) is None

    def test_frontera_de_mes_en_la_zona_del_usuario(self, db_session, contexto):
        """01-oct 03:00Z es 30-sep 22:00 en Bogotá: cuenta como septiembre, no octubre."""
        uid, gasto = contexto
        gasto(datetime(2026, 9, 1, 12, tzinfo=UTC), "100.00")
        gasto(datetime(2026, 10, 1, 3, tzinfo=UTC), "200.00")
        assert svc.promedio_gasto_mensual(db_session, uid, "COP", self.ahora, BOGOTA) == D("300.00")
