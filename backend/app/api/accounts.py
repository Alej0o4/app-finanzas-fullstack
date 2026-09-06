from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models import models
from app.schemas import schemas

router = APIRouter()


@router.post("/", response_model=schemas.AccountResponse)
def crear_cuenta(
    cuenta: schemas.AccountCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)
):
    # Fase 16 §16.4 (Decisión 16.4.1): `AccountCreate.balance` es el saldo de apertura —
    # alimenta AMBAS columnas al crear; `opening_balance` queda inmutable tras la creación.
    nueva_cuenta = models.Account(
        **cuenta.model_dump(),
        user_id=current_user.id,
        opening_balance=cuenta.balance,
    )
    db.add(nueva_cuenta)
    db.commit()
    db.refresh(nueva_cuenta)
    return nueva_cuenta


@router.get("/", response_model=list[schemas.AccountResponse])
def obtener_cuentas(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    cuentas = db.query(models.Account).filter(models.Account.user_id == current_user.id).offset(skip).limit(limit).all()
    return cuentas


# ⚠️ Declarada ANTES de GET /{account_id}: FastAPI resuelve rutas en orden de declaración
# y si esta ruta quedara después, "/accounts/summary" coincidiría con /{account_id} y
# daría 422 al intentar parsear "summary" como int.
@router.get("/summary", response_model=list[schemas.BalanceByCurrency])
def obtener_resumen_saldos(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """Saldo total por moneda de TODAS las cuentas del usuario (sin filtro de destacadas).

    Distinto de GET /dashboard/summary, que sí filtra por cuentas destacadas cuando existen
    (Fase 11 §11.5, Decisión 11.5.1) — este endpoint alimenta accounts/page.tsx, cuya lista
    de tarjetas tampoco filtra por destacadas, así que el total debe coincidir con esa lista.
    """
    rows = (
        db.query(models.Account.currency, func.sum(models.Account.balance).label("total"))
        .filter(models.Account.user_id == current_user.id)
        .group_by(models.Account.currency)
        .all()
    )
    return [{"currency": r.currency, "total": r.total} for r in rows]


# ⚠️ Declarado ANTES de GET /{account_id} (mismo criterio de orden que /summary arriba):
# FastAPI resuelve rutas en orden de declaración y el patrón /{account_id}/reconcile es
# más específico que /{account_id}.
@router.post("/{account_id}/reconcile", response_model=schemas.AccountReconcileResponse)
def reconciliar_cuenta(
    account_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Reconcilia el saldo de una cuenta (Fase 16 §16.4, Decisión 16.4.2): recalcula
    `balance` desde `opening_balance` + historial de transacciones no eliminadas y aplica
    la corrección de inmediato (sin preview — la operación es explícita y no destructiva).
    """
    cuenta = (
        db.query(models.Account)
        .filter(models.Account.id == account_id, models.Account.user_id == current_user.id)
        .first()
    )
    if not cuenta:
        raise HTTPException(status_code=404, detail="La cuenta no existe o no tienes permisos.")

    neto = (
        db.query(
            func.sum(
                case(
                    (models.Transaction.type == "income", models.Transaction.amount),
                    else_=-models.Transaction.amount,
                )
            )
        )
        .filter(models.Transaction.account_id == account_id, models.Transaction.deleted_at.is_(None))
        .scalar()
    ) or Decimal("0.00")

    saldo_recalculado = cuenta.opening_balance + neto
    saldo_anterior = cuenta.balance
    discrepancia = saldo_recalculado - saldo_anterior

    cuenta.balance = saldo_recalculado
    db.commit()

    return {
        "account_id": cuenta.id,
        "previous_balance": saldo_anterior,
        "recalculated_balance": saldo_recalculado,
        "discrepancy": discrepancia,
        "opening_balance": cuenta.opening_balance,
    }


@router.get("/{account_id}", response_model=schemas.AccountResponse)
def obtener_cuenta(
    account_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)
):
    cuenta = db.query(models.Account).filter(models.Account.id == account_id).first()

    # Usamos tu misma lógica de validación para mantener coherencia
    if not cuenta or cuenta.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="La cuenta no existe o no tienes permisos.")

    return cuenta


@router.put("/{account_id}", response_model=schemas.AccountResponse)
def actualizar_cuenta(
    account_id: int,
    cuenta_actualizada: schemas.AccountUpdate,  # 🔒 Usamos el nuevo molde restrictivo
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> models.Account:
    cuenta = db.query(models.Account).filter(models.Account.id == account_id).first()
    if not cuenta or cuenta.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="La cuenta a actualizar no existe o no tienes permisos.")

    cuenta.name = cuenta_actualizada.name
    cuenta.type = cuenta_actualizada.type
    cuenta.highlighted = cuenta_actualizada.highlighted

    db.commit()
    db.refresh(cuenta)
    return cuenta


@router.patch("/{account_id}/highlighted", response_model=schemas.AccountResponse)
def toggle_destacada(
    account_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    cuenta = db.query(models.Account).filter(models.Account.id == account_id).first()
    if not cuenta or cuenta.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="La cuenta no existe o no tienes permisos.")

    cuenta.highlighted = not cuenta.highlighted
    db.commit()
    db.refresh(cuenta)
    return cuenta


@router.delete("/{account_id}")
def eliminar_cuenta(
    account_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)
):
    cuenta = db.query(models.Account).filter(models.Account.id == account_id).first()
    if not cuenta or cuenta.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="La cuenta a eliminar no existe o no tienes permisos.")

    tiene_transacciones = db.query(models.Transaction).filter(models.Transaction.account_id == account_id).first()
    if tiene_transacciones:
        raise HTTPException(
            status_code=400, detail="No se puede eliminar la cuenta porque tiene transacciones asociadas."
        )

    cuenta.deleted_at = datetime.now(UTC)
    db.commit()
    return {"estado": "OK", "mensaje": "Cuenta eliminada exitosamente."}
