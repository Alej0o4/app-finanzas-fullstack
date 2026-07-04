from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security.oauth2 import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.core.database import get_db
from app.core.rate_limit import limiter
from app.models import models
from app.schemas import schemas
from app.core import security

router = APIRouter()


@router.post("/login", response_model=schemas.TokenResponse)
@limiter.limit("5/minute")
def login(
    request: Request,
    user_credentials: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    user = db.query(models.User).filter(models.User.email == user_credentials.username).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Credenciales Inválidas"
        )

    if not security.verify_password(user_credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Credenciales Inválidas"
        )

    access_token = security.create_access_token(data={"sub": str(user.id)})

    raw_refresh = security.generate_refresh_token()
    db.add(models.RefreshToken(
        token_hash=security.hash_token(raw_refresh),
        user_id=user.id,
        expires_at=datetime.utcnow() + timedelta(days=security.REFRESH_TOKEN_EXPIRE_DAYS),
    ))
    db.commit()

    return {
        "access_token": access_token,
        "refresh_token": raw_refresh,
        "token_type": "bearer",
    }


@router.post("/refresh", response_model=schemas.TokenResponse)
def refresh(
    body: schemas.RefreshRequest,
    db: Session = Depends(get_db),
):
    token_hash = security.hash_token(body.refresh_token)
    stored = db.query(models.RefreshToken).filter(
        models.RefreshToken.token_hash == token_hash,
        models.RefreshToken.revoked_at.is_(None),
        models.RefreshToken.expires_at > datetime.utcnow(),
    ).first()

    if not stored:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token inválido o expirado",
        )

    stored.revoked_at = datetime.utcnow()

    access_token = security.create_access_token(data={"sub": str(stored.user_id)})
    raw_refresh = security.generate_refresh_token()
    db.add(models.RefreshToken(
        token_hash=security.hash_token(raw_refresh),
        user_id=stored.user_id,
        expires_at=datetime.utcnow() + timedelta(days=security.REFRESH_TOKEN_EXPIRE_DAYS),
    ))
    db.commit()

    return {
        "access_token": access_token,
        "refresh_token": raw_refresh,
        "token_type": "bearer",
    }


@router.post("/logout")
def logout(
    body: schemas.LogoutRequest,
    db: Session = Depends(get_db),
):
    token_hash = security.hash_token(body.refresh_token)
    stored = db.query(models.RefreshToken).filter(
        models.RefreshToken.token_hash == token_hash,
        models.RefreshToken.revoked_at.is_(None),
    ).first()

    if stored:
        stored.revoked_at = datetime.utcnow()
        db.commit()

    return {"estado": "OK", "mensaje": "Sesión cerrada exitosamente."}
