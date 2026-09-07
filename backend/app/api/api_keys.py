"""Router de API keys personales revocables (Fase 16 §16.1).

La key en texto plano se devuelve UNA sola vez, en la respuesta del POST (Decisión
16.1.5, mismo patrón que un PAT de GitHub); nunca se puede volver a consultar. El DELETE
revoca (marca `revoked_at`), no borra la fila — conserva `last_used_at`/`created_at` para
auditar incidentes.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core import security
from app.core.database import get_db
from app.core.rate_limit import limiter
from app.core.security import get_current_user
from app.models import models
from app.schemas import schemas

router = APIRouter()

# Revisión de seguridad post-Fase 16 §16.1 (Decisión 16.1.8, ver docs/TODO.md): sin este
# tope, un JWT robado (válido 15 min) alcanza para mintear un número arbitrario de API
# keys de larga vida antes de que la víctima note algo — cada key sobrevive un reset de
# contraseña salvo que se revoque a mano. El límite es generoso (ninguna automatización
# personal legítima necesita más de unas pocas keys activas a la vez) y no bloquea crear
# una key nueva si antes se revocan viejas.
MAX_ACTIVE_API_KEYS_POR_USUARIO = 20


@router.post("/", response_model=schemas.ApiKeyCreateResponse)
@limiter.limit("5/minute")
def crear_api_key(
    request: Request,
    body: schemas.ApiKeyCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    activas = (
        db.query(models.ApiKey)
        .filter(models.ApiKey.user_id == current_user.id, models.ApiKey.revoked_at.is_(None))
        .count()
    )
    if activas >= MAX_ACTIVE_API_KEYS_POR_USUARIO:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Ya tenés {MAX_ACTIVE_API_KEYS_POR_USUARIO} API keys activas, el máximo "
                "permitido. Revocá alguna que ya no uses antes de crear una nueva."
            ),
        )

    raw_key = security.generate_api_key()
    nueva = models.ApiKey(
        user_id=current_user.id,
        name=body.name,
        key_hash=security.hash_token(raw_key),
        key_prefix=raw_key[:12],
    )
    db.add(nueva)
    db.commit()
    db.refresh(nueva)
    return {
        "id": nueva.id,
        "name": nueva.name,
        "key": raw_key,
        "key_prefix": nueva.key_prefix,
        "created_at": nueva.created_at,
    }


@router.get("/", response_model=list[schemas.ApiKeyResponse])
def listar_api_keys(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return db.query(models.ApiKey).filter(models.ApiKey.user_id == current_user.id).all()


@router.delete("/{api_key_id}")
def revocar_api_key(
    api_key_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    api_key = (
        db.query(models.ApiKey).filter(models.ApiKey.id == api_key_id, models.ApiKey.user_id == current_user.id).first()
    )
    if not api_key or api_key.revoked_at is not None:
        raise HTTPException(status_code=404, detail="La API key no existe o ya fue revocada.")
    api_key.revoked_at = datetime.now(UTC)
    db.commit()
    return {"estado": "OK", "mensaje": "API key revocada exitosamente."}
