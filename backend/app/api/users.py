from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, get_password_hash
from app.models import models
from app.schemas import schemas

router = APIRouter()

@router.post("/", response_model=schemas.UserResponse)
def crear_usuario(
    usuario: schemas.UserCreate,
    db: Session = Depends(get_db)
):
    normalized_email = usuario.email.lower().strip()
    usuario_existente = db.query(models.User).filter(models.User.email == normalized_email).first()
    if usuario_existente:
        raise HTTPException(status_code=400, detail="Error: Este correo electrónico ya está registrado.")

    hashed_password = get_password_hash(usuario.password)

    nuevo_usuario = models.User(
        email=normalized_email,
        full_name=usuario.full_name,
        password_hash=hashed_password
    )

    db.add(nuevo_usuario)
    db.commit()
    db.refresh(nuevo_usuario)

    return nuevo_usuario

@router.get("/me", response_model=schemas.UserResponse)  # 🆕 nuevo endpoint
def obtener_usuario_actual(
    current_user: models.User = Depends(get_current_user)
):
    return current_user
