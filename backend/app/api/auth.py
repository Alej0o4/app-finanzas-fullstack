from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security.oauth2 import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import models
from app.core import security

router = APIRouter()

# El endpoint es /login, y no devuelve un Schema nuestro, sino un diccionario estándar
@router.post("/login")
def login(
    # OAuth2PasswordRequestForm espera 'username' (que usaremos como email) y 'password'
    user_credentials: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    # 1. Buscamos al usuario por su "username" (que en nuestro caso es el email)
    user = db.query(models.User).filter(models.User.email == user_credentials.username).first()
    
    # 2. Si no existe el correo, lanzamos error
    if not user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Credenciales Inválidas" # Mensaje vago por seguridad (no decimos si falló el correo o la clave)
        )

    # 3. Verificamos que la contraseña sea correcta comparándola con el hash
    if not security.verify_password(user_credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Credenciales Inválidas"
        )

    # 4. Si todo es correcto, creamos el "gafete" JWT
    # Guardamos el 'id' del usuario dentro del token bajo la llave estándar 'sub' (subject)
    access_token = security.create_access_token(data={"sub": str(user.id)})

    # 5. Devolvemos el token en el formato exacto que exige el estándar OAuth2
    return {"access_token": access_token, "token_type": "bearer"}