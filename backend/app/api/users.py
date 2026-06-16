from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import models
from app.schemas import schemas
from app.core.security import get_password_hash

router = APIRouter()

@router.post("/", response_model=schemas.UserResponse)
def crear_usuario(
    usuario: schemas.UserCreate, 
    db: Session = Depends(get_db)
):
    # Programación Defensiva (Evitar duplicados)
    usuario_existente = db.query(models.User).filter(models.User.email == usuario.email).first()
    if usuario_existente:
        raise HTTPException(status_code=400, detail="Error: Este correo electrónico ya está registrado.")
    
    # 🔒 Criptografía Aplicada: Trituramos la contraseña real
    hashed_password = get_password_hash(usuario.password)
    
    # Ensamblaje de la pieza con la contraseña segura
    nuevo_usuario = models.User(
        email=usuario.email,
        password_hash=hashed_password # Guardamos el texto ininteligible, NUNCA la original
    )
    
    # Guardado físico en el disco
    db.add(nuevo_usuario)
    db.commit()
    db.refresh(nuevo_usuario)
    
    return nuevo_usuario