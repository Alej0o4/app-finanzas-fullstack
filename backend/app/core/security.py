import hashlib
import os
import secrets
from datetime import UTC, datetime, timedelta

from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import models

# 1. VARIABLES DE ENTORNO (Actualizado)
load_dotenv()  # Esto lee el archivo .env automáticamente

# Extraemos la llave. Si por algún error el archivo .env no existe, lanzará un error para protegerte.
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("¡Error Crítico! No se encontró la SECRET_KEY en el archivo .env")

ALGORITHM = "HS256"
# Bajado de 60 a 15 min (Fase 7, §2.5): reduce la ventana en la que un JWT robado sigue
# siendo válido tras el logout, apoyándose en el refresh token para sesiones largas.
# Ver "Decisión de diseño 2.5.1" en docs/specs/fase_07_spec.md sobre por qué no se agrega
# una blacklist de tokens en su lugar.
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 30
PASSWORD_RESET_TOKEN_EXPIRE_MINUTES = 45
EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS = 48

# URL base del frontend, usada para construir links en los emails de recuperación de
# contraseña y verificación de email (§2.1/§2.2). No hay todavía páginas en el frontend
# que consuman estos links (fuera del alcance de Fase 7 backend) — se documenta como
# variable opcional en .env.example.
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# 2. CONFIGURACIONES DE SEGURIDAD
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


# 3. FUNCIONES DE CONTRASEÑAS (Bcrypt)
def get_password_hash(password: str):
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str):
    return pwd_context.verify(plain_password, hashed_password)


# 4. FUNCIÓN PARA CREAR EL TOKEN (JWT)
def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update(
        {
            "exp": expire,
            "iat": datetime.now(UTC),
            "jti": secrets.token_urlsafe(16),
        }
    )
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


# 5. FUNCIONES PARA REFRESH TOKENS
def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# 5.1 FUNCIONES PARA API KEYS (Fase 16 §16.1)
# Prefijo reconocible para distinguir "esto es una API key" de "esto es un JWT" con una
# comparación de string barata, ANTES de intentar jwt.decode(...) — el branching no se apoya
# en capturar JWTError como mecanismo de control de flujo (Decisión 16.1.2).
API_KEY_PREFIX = "oikos_pat_"


def generate_api_key() -> str:
    return API_KEY_PREFIX + secrets.token_urlsafe(32)


# 6. EL GUARDIA DE SEGURIDAD (Dependencia para las rutas protegidas)
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if token.startswith(API_KEY_PREFIX):
        return _get_user_from_api_key(token, db, credentials_exception)

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception from None

    user = db.query(models.User).filter(models.User.id == int(user_id)).first()
    if user is None:
        raise credentials_exception

    return user


def _get_user_from_api_key(token: str, db: Session, credentials_exception: HTTPException) -> models.User:
    api_key = (
        db.query(models.ApiKey)
        .filter(models.ApiKey.key_hash == hash_token(token), models.ApiKey.revoked_at.is_(None))
        .first()
    )
    if api_key is None:
        raise credentials_exception
    # Decisión 16.1.4: última fecha de uso, sin throttling de escritura — el volumen de
    # llamadas esperado (automatizaciones personales, no tráfico masivo) no lo justifica.
    # Revolcar es efectivo en el siguiente request: cada llamada consulta `revoked_at
    # IS NULL` — ventana de gracia cero, a diferencia del JWT (sin blacklist).
    api_key.last_used_at = datetime.now(UTC)
    db.commit()
    user = db.query(models.User).filter(models.User.id == api_key.user_id).first()
    if user is None:
        raise credentials_exception
    return user
