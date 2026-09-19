from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security.oauth2 import OAuth2PasswordRequestForm
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from sqlalchemy.orm import Session
from starlette.responses import Response  # 🆕 Fase 26

from app.api.users import enviar_email_verificacion, inicializar_datos_usuario_nuevo
from app.core import auth_cookies, security  # 🆕 Fase 26: auth_cookies
from app.core.database import get_db
from app.core.email import render_email_html, send_email
from app.core.rate_limit import limiter
from app.models import models
from app.schemas import schemas

router = APIRouter()


@router.post("/login", response_model=schemas.TokenResponse)
@limiter.limit("5/minute")
def login(
    request: Request,
    response: Response,  # 🆕 Fase 26
    user_credentials: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    normalized_email = user_credentials.username.lower().strip()
    user = db.query(models.User).filter(models.User.email == normalized_email).first()

    if not user or user.password_hash is None:  # 🆕 Fase 20 §20.3 — cuenta solo-Google
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Credenciales Inválidas")

    if not security.verify_password(user_credentials.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Credenciales Inválidas")

    if not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "EMAIL_NOT_VERIFIED",
                "mensaje": "Verificá tu correo antes de iniciar sesión. Revisá tu bandeja de entrada.",
            },
        )

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

    # 🆕 Fase 26 (Decisión B6): cookies de sesión en la misma respuesta que el body —
    # el frontend deja de leer/escribir localStorage y autentica vía cookie.
    csrf_token = auth_cookies.generar_csrf_token()
    auth_cookies.establecer_cookies_de_sesion(
        response, access_token=access_token, refresh_token=raw_refresh, csrf_token=csrf_token
    )

    return {
        "access_token": access_token,
        "refresh_token": raw_refresh,
        "token_type": "bearer",
    }


@router.post("/google", response_model=schemas.TokenResponse)
@limiter.limit("5/minute")
def login_google(
    request: Request,
    response: Response,  # 🆕 Fase 26
    body: schemas.GoogleLoginRequest,
    db: Session = Depends(get_db),
):
    """Login/registro con ID token de Google Identity Services (Fase 20 §20.3).

    Google ya verificó la identidad del usuario (firma + `email_verified`), así que esta
    cuenta nace directamente verificada — sin pasar por `enviar_email_verificacion()`
    (Decisión P4). Respuesta con la MISMA forma que `login()`: el frontend reutiliza el
    mismo manejo de tokens sin bifurcar lógica (Historia de usuario 14).
    """
    if not security.GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El login con Google no está configurado en este entorno.",
        )

    try:
        idinfo = google_id_token.verify_oauth2_token(
            body.id_token, google_requests.Request(), security.GOOGLE_CLIENT_ID
        )
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token de Google inválido.") from None

    if not idinfo.get("email_verified"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="El correo de Google no está verificado.")

    normalized_email = idinfo["email"].lower().strip()
    user = db.query(models.User).filter(models.User.email == normalized_email).first()

    if user:
        # Fase 23 (Decisión G1): capturar el estado ANTES de tocar `email_verified` — si se
        # leyera después de la línea que lo pone en True, la condición sería siempre falsa y
        # nunca anularía nada (mismo tipo de bug de orden lectura/escritura que la Decisión D4
        # de docs/specs/fase_22_spec.md encontró para has_password).
        cuenta_no_verificada_antes_de_este_login = not user.email_verified

        if not user.google_id:
            user.google_id = idinfo["sub"]

        if cuenta_no_verificada_antes_de_este_login:
            user.email_verified = True
            # Este login de Google es la primera prueba real de que esta cuenta controla el
            # email — cualquier password_hash preexistente nunca fue probado contra su dueño
            # real (pudo ser plantado por un atacante, ver docs/ROADMAP.md Fase 23 y
            # CODE_REVIEW.md). Se anula: la cuenta queda Google-only hasta que su dueño fije
            # una contraseña nueva (Settings/forgot-password, mismo flujo que Fase 22 ya
            # construyó para cuentas Google-only puras — Decisión D1-D3 de fase_22_spec.md).
            user.password_hash = None
    else:
        user = models.User(
            email=normalized_email,
            full_name=idinfo.get("name", normalized_email),
            password_hash=None,
            google_id=idinfo["sub"],
            email_verified=True,
        )
        db.add(user)
        db.flush()  # asigna user.id sin cerrar la transacción
        inicializar_datos_usuario_nuevo(user, db)

    db.commit()
    db.refresh(user)

    # Mismo bloque de emisión de tokens que login() — sin cambios de forma.
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

    # 🆕 Fase 26 (Decisión B6): mismos cookies que login() — el frontend no bifurca lógica.
    csrf_token = auth_cookies.generar_csrf_token()
    auth_cookies.establecer_cookies_de_sesion(
        response, access_token=access_token, refresh_token=raw_refresh, csrf_token=csrf_token
    )

    return {
        "access_token": access_token,
        "refresh_token": raw_refresh,
        "token_type": "bearer",
    }


@router.post("/refresh", response_model=schemas.TokenResponse)
def refresh(
    request: Request,  # 🆕 Fase 26 — leer el cookie refresh_token cuando no viene body
    response: Response,  # 🆕 Fase 26
    body: schemas.RefreshRequest | None = None,  # 🆕 Fase 26 — ahora opcional
    db: Session = Depends(get_db),
):
    # 🆕 Fase 26: el frontend manda el refresh en el cookie (Path angosto
    # /api/v1/auth/refresh) sin body; el body queda para clientes no-browser. Si vienen
    # ambos, se usa el body (misma semántica de rotación/reuso que el flujo viejo).
    raw_refresh = body.refresh_token if body else request.cookies.get(auth_cookies.REFRESH_COOKIE_NAME)
    if raw_refresh is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token inválido o expirado",
        )

    token_hash = security.hash_token(raw_refresh)
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

    # 🆕 Fase 26 (Decisión B6): rota también los cookies — el access token nuevo reemplaza
    # al viejo y el refresh token nuevo reemplaza al que acaba de revocarse.
    csrf_token = auth_cookies.generar_csrf_token()
    auth_cookies.establecer_cookies_de_sesion(
        response, access_token=access_token, refresh_token=raw_refresh, csrf_token=csrf_token
    )

    return {
        "access_token": access_token,
        "refresh_token": raw_refresh,
        "token_type": "bearer",
    }


@router.post("/logout")
def logout(
    response: Response,  # 🆕 Fase 26
    request: Request,  # 🆕 Fase 26
    body: schemas.LogoutRequest | None = None,  # 🆕 Fase 26 — ahora opcional
    db: Session = Depends(get_db),
):
    raw_refresh = request.cookies.get(auth_cookies.REFRESH_COOKIE_NAME) or (body.refresh_token if body else None)
    if raw_refresh:
        token_hash = security.hash_token(raw_refresh)
        stored = (
            db.query(models.RefreshToken)
            .filter(models.RefreshToken.token_hash == token_hash, models.RefreshToken.revoked_at.is_(None))
            .first()
        )
        if stored:
            stored.revoked_at = datetime.now(UTC)
            db.commit()

    auth_cookies.limpiar_cookies_de_sesion(response)  # 🆕 Fase 26
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
            html_body=render_email_html(
                heading="Restablecé tu contraseña",
                intro_html=(
                    f"Solicitaste restablecer tu contraseña de Oikos. Este enlace expira en "
                    f"{security.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES} minutos."
                ),
                cta_text="Restablecer contraseña",
                cta_link=reset_link,
                footer_note="Si no fuiste vos, podés ignorar este correo — tu contraseña actual sigue funcionando.",
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

    # Revisión de seguridad post-Fase 16 §16.1 (Decisión 16.1.8, ver docs/TODO.md): las API
    # keys no expiran solas (a diferencia del JWT/refresh token) y hasta este fix sobrevivían
    # sin cambios a un reset de contraseña — si alguien mintió una API key durante una
    # ventana de compromiso (p. ej. un JWT robado por XSS, válido 15 min), el reset de
    # contraseña la dejaba activa para siempre, contradiciendo la razón de ser de este mismo
    # bloque ("dejar sesiones viejas vivas sería contradictorio"). Se revocan también todas
    # las API keys activas del usuario.
    db.query(models.ApiKey).filter(
        models.ApiKey.user_id == user.id,
        models.ApiKey.revoked_at.is_(None),
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


@router.post("/resend-verification")
@limiter.limit("5/minute")
def reenviar_verificacion(
    request: Request,
    body: schemas.ResendVerificationRequest,
    db: Session = Depends(get_db),
):
    """Reenvía el email de verificación (mismo patrón anti-enumeración que password-reset:
    siempre responde 200, exista o no el correo, y no revela si ya estaba verificado)."""
    normalized_email = body.email.lower().strip()
    user = db.query(models.User).filter(models.User.email == normalized_email).first()

    if user and not user.email_verified:
        enviar_email_verificacion(user, db)

    return {
        "estado": "OK",
        "mensaje": "Si el correo está registrado y aún no fue verificado, te enviamos un nuevo enlace.",
    }
