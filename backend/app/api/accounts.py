
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models import models
from app.schemas import schemas

router = APIRouter()

@router.post("/", response_model=schemas.AccountResponse)
def crear_cuenta(
    cuenta: schemas.AccountCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    nueva_cuenta = models.Account(**cuenta.model_dump(), user_id=current_user.id)
    db.add(nueva_cuenta)
    db.commit()
    db.refresh(nueva_cuenta)
    return nueva_cuenta

@router.get("/", response_model=list[schemas.AccountResponse])
def obtener_cuentas(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    cuentas = db.query(models.Account).filter(models.Account.user_id == current_user.id).offset(skip).limit(limit).all()
    return cuentas

@router.get("/{account_id}", response_model=schemas.AccountResponse)
def obtener_cuenta(
    account_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    cuenta = db.query(models.Account).filter(models.Account.id == account_id).first()

    # Usamos tu misma lógica de validación para mantener coherencia
    if not cuenta or cuenta.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="La cuenta no existe o no tienes permisos.")

    return cuenta

@router.put("/{account_id}", response_model=schemas.AccountResponse)
def actualizar_cuenta(
    account_id: int,
    cuenta_actualizada: schemas.AccountUpdate, # 🔒 Usamos el nuevo molde restrictivo
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
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
    account_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    cuenta = db.query(models.Account).filter(models.Account.id == account_id).first()
    if not cuenta or cuenta.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="La cuenta a eliminar no existe o no tienes permisos.")

    tiene_transacciones = db.query(models.Transaction).filter(models.Transaction.account_id == account_id).first()
    if tiene_transacciones:
        raise HTTPException(
            status_code=400,
            detail="No se puede eliminar la cuenta porque tiene transacciones asociadas."
        )

    db.delete(cuenta)
    db.commit()
    return {"estado": "OK", "mensaje": "Cuenta eliminada exitosamente."}
