"""Tests unit-level del delta contable compartido (Fase 25 §25.1, Decisión L6).

Contra `db_session` directo (sin pasar por HTTP): inserta `models.Account` a mano para
aislar el cálculo puro de las funciones de `app/services/ledger.py`, sin depender del
resto del stack. Los tests HTTP que ya cubren el mismo comportamiento como regresión de
caja negra (test_transactions.py::TestCreateTransactionAdjustsBalance,
TestDeleteTransactionRevertsBalance, TestUpdateTransactionAdjustsBalance y
test_accounts.py) no cambian en este ítem.
"""

from decimal import Decimal

import sqlalchemy as sa

from app.models import models
from app.services import ledger


def _crear_usuario(db_session, email: str) -> models.User:
    """Usuario mínimo para satisfacer la FK de `Account`. Cada test corre en una
    transacción externa que se revierte al final (conftest), así que el email puede
    repetirse entre tests sin chocar con el índice único."""
    usuario = models.User(full_name="Ledger de Prueba", email=email, password_hash="x")
    db_session.add(usuario)
    db_session.flush()  # asigna usuario.id para usarlo en la FK de Account
    return usuario


def _crear_cuenta(db_session, user_id: int, *, balance: str = "1000.00") -> models.Account:
    """Cuenta aislada por test, con saldo de partida explícito."""
    cuenta = models.Account(
        name="Cuenta ledger",
        type="cash",
        currency="COP",
        balance=Decimal(balance),
        user_id=user_id,
    )
    db_session.add(cuenta)
    db_session.commit()
    return cuenta


def _raw_balance(db_session, account_id: int) -> Decimal:
    """Saldo por SQL crudo: un SELECT ORM estaría filtrado por el soft-delete global
    (devuelve None para cuentas borradas) y el atributo del objeto ORM guarda el valor
    anterior al UPDATE — el ledger muta por Core SQL, fuera del identity map. Mismo
    patrón que test_soft_delete.py::_raw_balance."""
    balance = db_session.execute(sa.text("SELECT balance FROM accounts WHERE id = :id"), {"id": account_id}).scalar()
    return Decimal(str(balance))


class TestRegistrarImpacto:
    def test_income_incrementa_balance_en_exacto_monto(self, db_session):
        usuario = _crear_usuario(db_session, "ledger-income@example.com")
        cuenta = _crear_cuenta(db_session, usuario.id, balance="1000.00")

        ledger.registrar_impacto(db_session, cuenta.id, "income", Decimal("250.50"))

        assert _raw_balance(db_session, cuenta.id) == Decimal("1250.50")

    def test_expense_decrementa_balance_en_exacto_monto(self, db_session):
        usuario = _crear_usuario(db_session, "ledger-expense@example.com")
        cuenta = _crear_cuenta(db_session, usuario.id, balance="1000.00")

        ledger.registrar_impacto(db_session, cuenta.id, "expense", Decimal("150.25"))

        assert _raw_balance(db_session, cuenta.id) == Decimal("849.75")


class TestRevertirImpacto:
    def test_es_inverso_exacto_de_registrar_impacto(self, db_session):
        usuario = _crear_usuario(db_session, "ledger-revertir@example.com")
        cuenta = _crear_cuenta(db_session, usuario.id, balance="1000.00")

        ledger.registrar_impacto(db_session, cuenta.id, "expense", Decimal("200.00"))
        assert _raw_balance(db_session, cuenta.id) == Decimal("800.00")

        ledger.revertir_impacto(db_session, cuenta.id, "expense", Decimal("200.00"))

        assert _raw_balance(db_session, cuenta.id) == Decimal("1000.00")


class TestAplicarEdicion:
    def test_misma_cuenta_aplica_solo_el_delta_neto(self, db_session):
        """Un solo UPDATE con el delta neto, no dos escrituras que se pisan: la cuenta
        pasa de reflejar un gasto de 300 a uno de 120 (neto = +180 sobre el saldo)."""
        usuario = _crear_usuario(db_session, "ledger-edicion@example.com")
        cuenta = _crear_cuenta(db_session, usuario.id, balance="1000.00")

        ledger.aplicar_edicion(
            db_session,
            cuenta_vieja_id=cuenta.id,
            cuenta_nueva_id=cuenta.id,
            tipo_viejo="expense",
            monto_viejo=Decimal("300.00"),
            tipo_nuevo="expense",
            monto_nuevo=Decimal("120.00"),
        )

        assert _raw_balance(db_session, cuenta.id) == Decimal("1180.00")

    def test_cuentas_distintas_resta_old_delta_y_suma_new_delta(self, db_session):
        """El usuario movió la transacción a otra cuenta: la vieja revierte su impacto
        original (gasto de 300 → recupera 300) y la nueva aplica el impacto nuevo
        (ingreso de 50 → suma 50)."""
        usuario = _crear_usuario(db_session, "ledger-edicion-mover@example.com")
        cuenta_vieja = _crear_cuenta(db_session, usuario.id, balance="1000.00")
        cuenta_nueva = _crear_cuenta(db_session, usuario.id, balance="500.00")

        ledger.aplicar_edicion(
            db_session,
            cuenta_vieja_id=cuenta_vieja.id,
            cuenta_nueva_id=cuenta_nueva.id,
            tipo_viejo="expense",
            monto_viejo=Decimal("300.00"),
            tipo_nuevo="income",
            monto_nuevo=Decimal("50.00"),
        )

        assert _raw_balance(db_session, cuenta_vieja.id) == Decimal("1300.00")
        assert _raw_balance(db_session, cuenta_nueva.id) == Decimal("550.00")


class TestAplicarDelta:
    def test_cuenta_soft_deleted_no_cambia_su_balance(self, db_session):
        """El filtro `deleted_at IS NULL` del WHERE protege el saldo de una cuenta
        soft-deleted — mismo comportamiento que el código original de transactions.py
        (Decisión 6.1, Opción A). Borrado por SQL crudo, igual que test_soft_delete.py:
        es el estado intermedio que el UPDATE de saldo debe resistir."""
        usuario = _crear_usuario(db_session, "ledger-soft-deleted@example.com")
        cuenta = _crear_cuenta(db_session, usuario.id, balance="1000.00")

        db_session.execute(
            sa.text("UPDATE accounts SET deleted_at = CURRENT_TIMESTAMP WHERE id = :id"), {"id": cuenta.id}
        )
        db_session.commit()

        ledger.aplicar_delta(db_session, cuenta.id, Decimal("-100.00"))

        assert _raw_balance(db_session, cuenta.id) == Decimal("1000.00")
