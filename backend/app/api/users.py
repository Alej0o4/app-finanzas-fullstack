from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import models
from app.schemas import schemas

router = APIRouter()

@router.post("/", response_model=schemas.UserResponse)
def crear_usuario(
    usuario: schemas.UserCreate, 
    db: Session = Depends(get_db)
):
    # Paso A: Programación Defensiva (Evitar duplicados)
    # Buscamos si ya existe alguien con ese email en la base de datos
    usuario_existente = db.query(models.User).filter(models.User.email == usuario.email).first()
    if usuario_existente:
        # El Error 400 (Bad Request) significa que el cliente nos envió datos inválidos
        raise HTTPException(status_code=400, detail="Error: Este correo electrónico ya está registrado.")
    
    # Paso B: Gestión de Contraseñas (Temporal)
    # ⚠️ ADVERTENCIA: En la Fase C reemplazaremos esta línea con una encriptación real (Bcrypt).
    # Por ahora, creamos un "hash falso" para que la base de datos acepte el registro.
    hash_falso = usuario.password + "-encriptado"
    
    # Paso C: Ensamblaje de la pieza
    nuevo_usuario = models.User(
        email=usuario.email,
        password_hash=hash_falso
    )
    
    # Paso D: Guardado físico en el disco
    db.add(nuevo_usuario)
    db.commit()
    db.refresh(nuevo_usuario)
    
    return nuevo_usuario