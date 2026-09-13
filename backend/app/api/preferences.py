from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models import models
from app.schemas import schemas

router = APIRouter()


@router.get("/me/preferences")
def get_preferences(current_user: models.User = Depends(get_current_user)):
    return {
        "preferred_currency": current_user.preferred_currency,
        "preferred_locale": current_user.preferred_locale,
        "preferred_theme": current_user.preferred_theme,
        "weekly_summary_enabled": current_user.weekly_summary_enabled,
    }


@router.patch("/me/preferences")
def update_preferences(
    prefs: schemas.PreferencesUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # `apply_to_default_account` se excluye del dump: es una instrucción de cascada
    # (Decisión A5), no un campo de User — `setattr` le crearía un atributo fantasma al
    # ORM sin ningún efecto.
    update_data = prefs.model_dump(exclude={"apply_to_default_account"}, exclude_none=True)
    for field, value in update_data.items():
        setattr(current_user, field, value)

    # Fase 22 §22.1 (Decisiones A2/A5): cascada opcional a la cuenta por defecto, en la
    # misma transacción — sin ventana entre "leer si la cuenta sigue virgen" y "escribirle
    # la moneda" (evita el TOCTOU que tendría una segunda request HTTP separada).
    if prefs.apply_to_default_account and prefs.preferred_currency:
        cuenta_virgen = (
            db.query(models.Account)
            .filter(
                models.Account.user_id == current_user.id,
                models.Account.name == "Cuenta principal",
                models.Account.balance == 0,
            )
            .first()
        )
        if cuenta_virgen is not None:
            tiene_transacciones = (
                db.query(models.Transaction.id).filter(models.Transaction.account_id == cuenta_virgen.id).first()
            )
            if tiene_transacciones is None:
                cuenta_virgen.currency = prefs.preferred_currency
        # Si el guard no pasa (nombre distinto, saldo != 0, o ya tiene transacciones):
        # no se toca la cuenta y no se informa error — `preferred_currency` del usuario
        # igual queda actualizado (Decisión A2: "dejar que el usuario la corrija
        # manualmente en Cuentas, igual que hoy").

    db.commit()
    db.refresh(current_user)
    return {
        "preferred_currency": current_user.preferred_currency,
        "preferred_locale": current_user.preferred_locale,
        "preferred_theme": current_user.preferred_theme,
        "weekly_summary_enabled": current_user.weekly_summary_enabled,
    }
