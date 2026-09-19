"""Delta contable compartido entre crear/actualizar/eliminar transacción (Fase 25 §25.1).

Antes de esta extracción, el signo del delta (income → +monto, expense → -monto) y el
UPDATE atómico de Account.balance estaban copy-pasteados tres veces en
app/api/transactions.py (líneas 186, 312, 393-395). Mismo criterio de "función pura +
db: Session + primitivos, sin estado propio" que ya usa app/core/budget_alerts.py — el
patrón de servicio ad-hoc de este repo, no una capa nueva inventada desde cero.

Los routers siguen siendo dueños de la transacción SQL (dónde arranca el try/except,
cuándo se hace db.commit()) — estas funciones solo ejecutan los UPDATEs, nunca comitean
ni hacen rollback por su cuenta (Decisión L2).
"""

from decimal import Decimal

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models import models


def delta_para(tipo: str, monto: Decimal) -> Decimal:
    """Signo del impacto contable: `income` suma, `expense` resta."""
    return monto if tipo == "income" else -monto


def aplicar_delta(db: Session, account_id: int, delta: Decimal) -> None:
    """UPDATE atómico de Account.balance, SQL puro (no read-modify-write ORM) — mismo
    filtro deleted_at IS NULL que las tres funciones originales ya usaban para no mutar
    el saldo de una cuenta soft-deleted (Decisión 6.1)."""
    db.execute(
        update(models.Account)
        .where(models.Account.id == account_id, models.Account.deleted_at.is_(None))
        .values(balance=models.Account.balance + delta)
    )


def registrar_impacto(db: Session, account_id: int, tipo: str, monto: Decimal) -> None:
    """Aplica el impacto de una transacción NUEVA (crear_transaccion)."""
    aplicar_delta(db, account_id, delta_para(tipo, monto))


def revertir_impacto(db: Session, account_id: int, tipo: str, monto: Decimal) -> None:
    """Revierte el impacto de una transacción borrada (eliminar_transaccion) — inverso
    exacto de registrar_impacto sobre el mismo (tipo, monto)."""
    aplicar_delta(db, account_id, -delta_para(tipo, monto))


def aplicar_edicion(
    db: Session,
    *,
    cuenta_vieja_id: int,
    cuenta_nueva_id: int,
    tipo_viejo: str,
    monto_viejo: Decimal,
    tipo_nuevo: str,
    monto_nuevo: Decimal,
) -> None:
    """Recalcula el impacto de una transacción editada (actualizar_transaccion).

    Misma cuenta: un solo UPDATE con el delta neto (evita dos escrituras que se pisan).
    Cuenta distinta (el usuario movió el gasto/ingreso a otra cuenta): revierte el
    impacto viejo en la cuenta origen y aplica el nuevo en la cuenta destino — mismo
    comportamiento ya verificado por
    test_update_moving_to_different_currency_account_updates_currency
    (backend/tests/test_transactions.py:401-433, Fase 11 §11.2)."""
    old_delta = delta_para(tipo_viejo, monto_viejo)
    new_delta = delta_para(tipo_nuevo, monto_nuevo)
    if cuenta_vieja_id == cuenta_nueva_id:
        aplicar_delta(db, cuenta_vieja_id, new_delta - old_delta)
    else:
        aplicar_delta(db, cuenta_vieja_id, -old_delta)
        aplicar_delta(db, cuenta_nueva_id, new_delta)
