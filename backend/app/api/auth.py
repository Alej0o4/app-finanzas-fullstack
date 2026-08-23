from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security.oauth2 import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core import security
from app.core.database import get_db
from app.core.email import send_email
from app.core.rate_limit import limiter
from app.models import models
from app.schemas import schemas

router = APIRouter()


@router.post("/login", response_model=schemas.TokenResponse)
@limiter.limit("5/minute")
def login(request: Request, user_credentials: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    normalized_email = user_credentials.username.lower().strip()
    user = db.query(models.User).filter(models.User.email == normalized_email).first()

    if not user:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Credenciales Inválidas")

    if not security.verify_password(user_credentials.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Credenciales Inválidas")

    access_token = security.create_access_token(data={"sub": str(user.id)})

    raw_refresh = security.generate_refresh_token()
    db.add(
        models.RefreshToken(
            token_hash=security.hash_token(raw_refresh),
            user_id=user.id,
            expires_at=datetime.now(UTC) + timedelta(days=security.REFRESH_TOKEN_EXPIRE_DAYS),
        )
    )
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
    stored = (
        db.query(models.RefreshToken)
        .filter(
            models.RefreshToken.token_hash == token_hash,
            models.RefreshToken.revoked_at.is_(None),
            models.RefreshToken.expires_at > datetime.now(UTC),
        )
        .first()
    )

    if not stored:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token inválido o expirado",
        )

    stored.revoked_at = datetime.now(UTC)

    access_token = security.create_access_token(data={"sub": str(stored.user_id)})
    raw_refresh = security.generate_refresh_token()
    db.add(
        models.RefreshToken(
            token_hash=security.hash_token(raw_refresh),
            user_id=stored.user_id,
            expires_at=datetime.now(UTC) + timedelta(days=security.REFRESH_TOKEN_EXPIRE_DAYS),
        )
    )
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
    stored = (
        db.query(models.RefreshToken)
        .filter(
            models.RefreshToken.token_hash == token_hash,
            models.RefreshToken.revoked_at.is_(None),
        )
        .first()
    )

    if stored:
        stored.revoked_at = datetime.now(UTC)
        db.commit()

    return {"estado": "OK", "mensaje": "Sesión cerrada exitosamente."}


@router.post("/password-reset/request")
@limiter.limit("5/minute")
def solicitar_restablecimiento_contrasena(
    request: Request,
    body: schemas.PasswordResetRequest,
    db: Session = Depends(get_db),
):
    """Genera y envía un token de restablecimiento si el email existe.

    Responde 200 exista o no el email registrado — no revelar qué correos están
    registrados (enumeration attack), ver docs/specs/fase_07_spec.md §2.1.
    """
    normalized_email = body.email.lower().strip()
    user = db.query(models.User).filter(models.User.email == normalized_email).first()

    if user:
        raw_token = security.generate_refresh_token()
        db.add(
            models.PasswordResetToken(
                token_hash=security.hash_token(raw_token),
                user_id=user.id,
                expires_at=datetime.now(UTC) + timedelta(minutes=security.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES),
            )
        )
        db.commit()

        reset_link = f"{security.FRONTEND_URL}/reset-password?token={raw_token}"
        send_email(
            to=user.email,
            subject="Recuperación de contraseña — Oikos",
            html_body=(
                f"<p>Solicitaste restablecer tu contraseña de Oikos. Este enlace expira en "
                f"{security.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES} minutos:</p>"
                f'<p><a href="{reset_link}">{reset_link}</a></p>'
                f"<p>Si no fuiste vos, podés ignorar este correo — tu contraseña actual sigue funcionando.</p>"
            ),
        )

    return {
        "estado": "OK",
        "mensaje": "Si el correo está registrado, recibirás instrucciones para restablecer tu contraseña.",
    }


@router.post("/password-reset/confirm")
def confirmar_restablecimiento_contrasena(
    body: schemas.PasswordResetConfirm,
    db: Session = Depends(get_db),
):
    token_hash = security.hash_token(body.token)
    stored = (
        db.query(models.PasswordResetToken)
        .filter(
            models.PasswordResetToken.token_hash == token_hash,
            models.PasswordResetToken.used_at.is_(None),
            models.PasswordResetToken.expires_at > datetime.now(UTC),
        )
        .first()
    )

    if not stored:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token inválido o expirado.")

    user = db.query(models.User).filter(models.User.id == stored.user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token inválido o expirado.")

    user.password_hash = security.get_password_hash(body.new_password)
    stored.used_at = datetime.now(UTC)

    # Si alguien reseteó la contraseña porque sospecha que la cuenta fue comprometida,
    # dejar sesiones viejas vivas sería contradictorio — se revocan todos los refresh
    # tokens activos del usuario.
    db.query(models.RefreshToken).filter(
        models.RefreshToken.user_id == user.id,
        models.RefreshToken.revoked_at.is_(None),
    ).update({"revoked_at": datetime.now(UTC)})

    db.commit()

    return {"estado": "OK", "mensaje": "Contraseña actualizada exitosamente. Iniciá sesión nuevamente."}


@router.get("/verify-email")
def verificar_email(token: str, db: Session = Depends(get_db)):
    token_hash = security.hash_token(token)
    stored = (
        db.query(models.EmailVerificationToken)
        .filter(
            models.EmailVerificationToken.token_hash == token_hash,
            models.EmailVerificationToken.used_at.is_(None),
            models.EmailVerificationToken.expires_at > datetime.now(UTC),
        )
        .first()
    )

    if not stored:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Token de verificación inválido o expirado."
        )

    user = db.query(models.User).filter(models.User.id == stored.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Token de verificación inválido o expirado."
        )

    user.email_verified = True
    stored.used_at = datetime.now(UTC)
    db.commit()

    return {"estado": "OK", "mensaje": "Correo verificado exitosamente."}
