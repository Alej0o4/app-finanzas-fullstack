from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core import security
from app.core.database import get_db
from app.core.default_categories import BASE_REGISTRATION_CATEGORY_NAMES
from app.core.email import render_email_html, send_email
from app.core.rate_limit import limiter
from app.core.security import get_current_user, get_password_hash
from app.models import models
from app.schemas import schemas

router = APIRouter()


def enviar_email_verificacion(user: models.User, db: Session) -> None:
    raw_token = security.generate_refresh_token()
    db.add(
        models.EmailVerificationToken(
            token_hash=security.hash_token(raw_token),
            user_id=user.id,
            expires_at=datetime.now(UTC) + timedelta(hours=security.EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS),
        )
    )
    db.commit()

    verify_link = f"{security.FRONTEND_URL}/verify-email?token={raw_token}"
    send_email(
        to=user.email,
        subject="Verificá tu correo — Oikos",
        html_body=render_email_html(
            heading="Confirmá tu cuenta",
            intro_html=(
                f"Gracias por registrarte en Oikos. Hacé clic en el botón para verificar tu "
                f"correo (el enlace expira en {security.EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS} horas)."
            ),
            cta_text="Verificar mi correo",
            cta_link=verify_link,
        ),
    )


def inicializar_datos_usuario_nuevo(usuario: models.User, db: Session) -> None:
    """Cuenta por defecto + pre-siembra de categorías ocultas. Compartido entre el registro
    por contraseña (crear_usuario) y el registro por Google (login_google) — Fase 20 §20.3,
    Hallazgo 4: un segundo punto de creación de User que se salte esto reabre el bug de
    'usuario nuevo con 0 cuentas' ya documentado en docs/TODO.md."""
    # Cuenta por defecto (Fase 8 §5): un usuario nuevo nunca debe quedarse con 0 cuentas
    # — `account_id` es obligatorio al transaccionar y QuickTransactionModal falla en silencio.
    # Mismo commit que el usuario: o existen ambos, o ninguno.
    cuenta_por_defecto = models.Account(
        name="Cuenta principal",
        type="debit",
        balance=Decimal("0.00"),
        currency=usuario.preferred_currency or "COP",
        user_id=usuario.id,
        highlighted=True,
    )
    db.add(cuenta_por_defecto)

    # Fase 18 §18.2 (Decisión 18.2.1/Q2/Q3): pre-siembra silenciosa de `hidden_categories`.
    # Las categorías de sistema fuera del set base quedan ocultas por defecto en el selector
    # de captura, sin pantalla nueva de registro. Mismo commit que el usuario y la cuenta:
    # o existen los tres, o ninguno. El query pasa por el listener global de soft-delete,
    # así que categorías de sistema borradas lógicamente no entran al loop.
    categorias_sistema = db.query(models.Category).filter(models.Category.user_id.is_(None)).all()
    for categoria in categorias_sistema:
        if categoria.name not in BASE_REGISTRATION_CATEGORY_NAMES:
            db.add(models.HiddenCategory(user_id=usuario.id, category_id=categoria.id))


@router.post("/", response_model=schemas.UserResponse)
@limiter.limit("5/minute")
def crear_usuario(request: Request, usuario: schemas.UserCreate, db: Session = Depends(get_db)):
    normalized_email = usuario.email.lower().strip()
    usuario_existente = db.query(models.User).filter(models.User.email == normalized_email).first()
    if usuario_existente:
        raise HTTPException(status_code=400, detail="Error: Este correo electrónico ya está registrado.")

    hashed_password = get_password_hash(usuario.password)

    nuevo_usuario = models.User(email=normalized_email, full_name=usuario.full_name, password_hash=hashed_password)
    db.add(nuevo_usuario)
    db.flush()  # asigna nuevo_usuario.id sin cerrar la transacción todavía
    inicializar_datos_usuario_nuevo(nuevo_usuario, db)

    db.commit()
    db.refresh(nuevo_usuario)

    # El registro no debe fallar ni demorarse si el envío de email tiene un problema
    # (decisión original de Fase 7 §2.2). El login sí exige email verificado desde el gate
    # agregado en auth.py `login()` — ver docs/TODO.md.
    enviar_email_verificacion(nuevo_usuario, db)

    return nuevo_usuario


@router.get("/me", response_model=schemas.UserResponse)  # 🆕 nuevo endpoint
def obtener_usuario_actual(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),  # Fase 19 §19.1
):
    # Fase 19 §19.1.2: LIMIT 2, no COUNT(*) — solo hace falta saber si hay 2 o más,
    # no cuántas. El filtro de deleted_at IS NULL lo aplica el with_loader_criteria global.
    primeras_dos = db.query(models.Transaction.id).filter(models.Transaction.user_id == current_user.id).limit(2).all()
    current_user.has_transaction_history = len(primeras_dos) >= 2
    return current_user


@router.patch("/me", response_model=schemas.UserResponse)
def actualizar_perfil(
    body: schemas.UserProfileUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    update_data = body.model_dump(exclude_none=True)
    for field, value in update_data.items():
        setattr(current_user, field, value)
    db.commit()
    db.refresh(current_user)
    return current_user
