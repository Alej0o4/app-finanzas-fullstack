import hashlib
import os
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import models

# 1. VARIABLES DE ENTORNO
# `load_dotenv()` sin argumentos busca un `.env` hacia arriba desde este archivo hasta la raíz
# del filesystem — si `backend/.env` no existe (ej. un git worktree recién creado, donde los
# archivos gitignored no se copian), sigue subiendo y puede terminar leyendo el `.env` de la
# raíz del repo real (el que usa Docker Compose, con credenciales SMTP reales) en vez de no
# cargar nada. Se fija la ruta explícita a `backend/.env` para que nunca "escape" del proyecto;
# si ese archivo no existe (como en Docker, donde las env vars ya vienen inyectadas), no hace
# nada — no lanza error.
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

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

# Client ID de Google para el login social (Fase 20 §20.3). Es una funcionalidad OPCIONAL:
# a diferencia de SECRET_KEY (que firma cada JWT), nadie depende de esta variable hasta que
# alguien use POST /auth/google. Se lee igual que FRONTEND_URL (fallo suave, sin raise) —
# el endpoint chequea explícitamente `None` y responde 503 con mensaje claro.
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")  # None si no está configurado — opcional

# Flag de cookies (Fase 26). Default True: el acceso de producción se consolida en el dominio
# HTTPS de Tailscale Funnel (Decisión B10, docs/specs/fase_26_spec.md) — un cookie Secure=True
# nunca se envía a un origen http://, así que este flag solo necesita bajar a False en entornos
# que sirven HTTP plano a propósito (docker-compose.dev.yml, desarrollo local sin Funnel).
# Mismo patrón que ENABLE_TAILSCALE_CORS (Fase 7 §3.3): un flag de entorno, no una rama de
# código nueva, para no hardcodear una topología de red específica de este despliegue.
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true").lower() == "true"

# 2. CONFIGURACIONES DE SEGURIDAD
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
# 🆕 Fase 26 (Decisión B4): auto_error=False — sin header `Authorization`, la dependencia NO
# lanza 401 por su cuenta; `get_current_user` decide: primero header, y si viene vacío, cae
# al cookie `access_token` como fallback (Hallazgo 1 de docs/specs/fase_26_spec.md). Con el
# default auto_error=True, un fallback de cookie dentro del cuerpo de get_current_user nunca
# se alcanzaría para una request sin header.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


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
def get_current_user(
    request: Request,  # 🆕 Fase 26 — necesario para leer el cookie de fallback
    token: str | None = Depends(oauth2_scheme),  # 🆕 ahora puede ser None
    db: Session = Depends(get_db),
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # 🆕 Fase 26 (Decisión B4): el header Authorization sigue siendo el camino primario —
    # clientes no-browser (curl, Shortcuts de iOS con oikos_pat_, un futuro cliente API) no
    # cambian nada. El cookie es un fallback que solo se consulta si no vino header, nunca al
    # revés — no hay ninguna rama nueva que toque el camino de API key.
    # Nota: "access_token" es un string literal a propósito — app/core/auth_cookies.py
    # (que define ACCESS_COOKIE_NAME) importa de este módulo, así que importarlo acá a nivel
    # de módulo crearía un ciclo. Ambos valores deben coincidir por convención (ver el
    # comentario cruzado en auth_cookies.py; Decisión B4 de docs/specs/fase_26_spec.md).
    if token is None:
        token = request.cookies.get("access_token")
    if token is None:
        raise credentials_exception

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
