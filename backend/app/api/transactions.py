import hashlib
import json
import logging
import unicodedata
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import desc, func, or_, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.budget_alerts import evaluate_budget_thresholds_safely
from app.core.database import get_db
from app.core.rate_limit import key_func_por_usuario_o_ip, limiter

# 🔒 Importamos a nuestro Guardia de Seguridad
from app.core.security import get_current_user
from app.models import models
from app.schemas import schemas

router = APIRouter()
logger = logging.getLogger(__name__)


# --- Helpers de resolución por nombre (Fase 16 §16.2) ---
def _normalizar_nombre_categoria(nombre: str) -> str:
    """Normaliza un nombre de categoría para comparar sin acentos ni mayúsculas
    (Decisión 16.2.2) — "Alimentación" == "alimentacion" == "ALIMENTACIÓN"."""
    sin_acentos = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode()
    return sin_acentos.strip().lower()


def _resolver_categoria_por_nombre(db: Session, user_id: int, nombre: str, tipo: str) -> models.Category:
    """Resuelve una categoría por nombre (Fase 16 §16.2, Decisión 16.2.2).

    Reglas: filtrado por `type` (elimina ambigüedad cruzada gasto/ingreso), precedencia de
    categoría propia sobre categoría de sistema si ambas matchean, y `409` si hay más de un
    match dentro del mismo alcance (propio o sistema). Sin match → `404` con la lista de
    nombres válidos para ese tipo (sin fuzzy match, a propósito).
    """
    objetivo = _normalizar_nombre_categoria(nombre)
    candidatas = (
        db.query(models.Category)
        .filter(
            or_(models.Category.user_id.is_(None), models.Category.user_id == user_id),
            models.Category.type == tipo,
        )
        .all()
    )
    matches = [c for c in candidatas if _normalizar_nombre_categoria(c.name) == objetivo]
    propias = [c for c in matches if c.user_id == user_id]
    sistema = [c for c in matches if c.user_id is None]

    if propias:
        if len(propias) > 1:
            raise HTTPException(
                status_code=409,
                detail=f"Tenés más de una categoría propia llamada '{nombre}'. Usá category_id.",
            )
        return propias[0]
    if sistema:
        if len(sistema) > 1:  # no debería pasar hoy (DEFAULT_CATEGORIES no tiene duplicados), defensivo
            raise HTTPException(status_code=409, detail=f"Categoría '{nombre}' ambigua.")
        return sistema[0]

    nombres_validos = sorted({c.name for c in candidatas})
    raise HTTPException(
        status_code=404,
        detail=f"Categoría '{nombre}' no encontrada. Válidas para {tipo}: {', '.join(nombres_validos)}.",
    )


def _resolver_cuenta(db: Session, user_id: int, account_id: int | None) -> models.Account:
    """Resuelve la cuenta destino (Fase 16 §16.2, Decisión 16.2.4): si el cliente omite
    `account_id`, se usa la única cuenta del usuario; con más de una se responde `400`
    (no se adivina cuál — mismo criterio de "no adivinar con dinero" que la decisión de
    categorías ambiguas). Con `account_id` explícito, valida que exista y pertenezca."""
    if account_id is not None:
        cuenta = (
            db.query(models.Account).filter(models.Account.id == account_id, models.Account.user_id == user_id).first()
        )
        if not cuenta:
            raise HTTPException(status_code=404, detail="La cuenta especificada no existe o no te pertenece.")
        return cuenta

    cuentas_usuario = db.query(models.Account).filter(models.Account.user_id == user_id).all()
    if len(cuentas_usuario) != 1:
        raise HTTPException(
            status_code=400,
            detail=(
                "Especificá account_id: tenés más de una cuenta."
                if cuentas_usuario
                else "No tenés ninguna cuenta activa."
            ),
        )
    return cuentas_usuario[0]


# --- RUTA PROTEGIDA ---
@router.post("/", response_model=schemas.TransactionResponse)
@limiter.limit("60/minute", key_func=key_func_por_usuario_o_ip)
def crear_transaccion(
    request: Request,
    transaccion: schemas.TransactionCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key", max_length=255),
):
    # 🔁 Idempotencia (Fase 10, ítem 10.4): si el cliente reenvía la misma
    # Idempotency-Key, se devuelve la transacción original en vez de crear otra y
    # volver a mover el saldo. Un payload distinto con una clave ya usada es casi con
    # certeza un bug del cliente (Decisión 10.4.3): se hace visible con un 409.
    request_hash = None
    if idempotency_key:
        request_hash = hashlib.sha256(
            json.dumps(transaccion.model_dump(mode="json"), sort_keys=True).encode()
        ).hexdigest()
        existente = (
            db.query(models.IdempotencyKey)
            .filter(
                models.IdempotencyKey.user_id == current_user.id,
                models.IdempotencyKey.key == idempotency_key,
            )
            .first()
        )
        if existente:
            if existente.request_hash != request_hash:
                raise HTTPException(
                    status_code=409,
                    detail="Esta Idempotency-Key ya se usó con datos distintos.",
                )
            transaccion_previa = (
                db.query(models.Transaction).filter(models.Transaction.id == existente.transaction_id).first()
            )
            if not transaccion_previa:
                # La transacción original fue borrada (soft-delete) desde el envío
                # original — ver caso borde en el spec de Fase 10, ítem 10.4.
                raise HTTPException(
                    status_code=409,
                    detail="La transacción original de esta Idempotency-Key ya no existe.",
                )
            return transaccion_previa

    # 🔒 1. Resolución de la cuenta (Fase 16 §16.2, Decisión 16.2.4 — ver
    # _resolver_cuenta). Aplica ANTES de la verificación de pertenencia de abajo: una vez
    # resuelto, el resto del endpoint no cambia una sola línea.
    cuenta = _resolver_cuenta(db, current_user.id, transaccion.account_id)
    transaccion.account_id = cuenta.id

    # 🔒 2. Resolución de la categoría por nombre (Fase 16 §16.2, Decisión 16.2.2). El XOR
    # del schema garantiza que si `category_id` es None, `category` trae un nombre.
    if transaccion.category_id is None:
        categoria = _resolver_categoria_por_nombre(db, current_user.id, transaccion.category, transaccion.type.value)
        transaccion.category_id = categoria.id
        transaccion.category = None  # nunca llega al model_dump (exclude_none)

    # 🔒 3. Verificar que la cuenta de destino exista y PERTENEZCA al usuario
    cuenta = (
        db.query(models.Account)
        .filter(models.Account.id == transaccion.account_id, models.Account.user_id == current_user.id)
        .first()
    )

    if not cuenta:
        raise HTTPException(status_code=404, detail="La cuenta especificada no existe o no te pertenece.")

    categoria = (
        db.query(models.Category)
        .filter(
            models.Category.id == transaccion.category_id,
            or_(models.Category.user_id.is_(None), models.Category.user_id == current_user.id),
        )
        .first()
    )

    if not categoria:
        raise HTTPException(
            status_code=404, detail="La categoría especificada no existe o no tienes permisos para usarla."
        )

    # 2. Ensamblar la transacción
    nueva_transaccion = models.Transaction(**transaccion.model_dump(exclude_none=True), user_id=current_user.id)
    nueva_transaccion.currency = cuenta.currency  # hereda la moneda de la cuenta

    # 🧮 3. Lógica Contable: Actualizar saldo de forma atómica en SQL
    delta = transaccion.amount if transaccion.type == "income" else -transaccion.amount

    try:
        db.add(nueva_transaccion)
        # El filtro explícito de borrado lógico complementa al handler select-only de
        # database.py (Opción A, Decisión 6.1): un update() ORM-enabled NO queda
        # cubierto por el filtro global — mutar el saldo de una cuenta soft-deleted
        # sería un bug de integridad.
        db.execute(
            update(models.Account)
            .where(
                models.Account.id == transaccion.account_id,
                models.Account.deleted_at.is_(None),
            )
            .values(balance=models.Account.balance + delta)
        )
        if idempotency_key:
            # Decisión 10.4.4: Transaction + saldo + bitácora comparten UN solo commit —
            # si el INSERT de la clave pierde una carrera contra el UNIQUE(user_id, key),
            # el rollback revierte también la transacción contable completa.
            db.flush()  # asigna nueva_transaccion.id antes del commit final
            db.add(
                models.IdempotencyKey(
                    user_id=current_user.id,
                    key=idempotency_key,
                    request_hash=request_hash,
                    transaction_id=nueva_transaccion.id,
                )
            )
        db.commit()
        db.refresh(nueva_transaccion)
    except IntegrityError:
        db.rollback()
        # Se perdió la carrera: otra petición con la misma clave ya insertó primero.
        existente = (
            db.query(models.IdempotencyKey)
            .filter(models.IdempotencyKey.user_id == current_user.id, models.IdempotencyKey.key == idempotency_key)
            .first()
        )
        if existente:
            return db.query(models.Transaction).filter(models.Transaction.id == existente.transaction_id).first()
        raise HTTPException(status_code=500, detail="Error interno al procesar la transacción contable.") from None
    except Exception:
        db.rollback()
        logger.exception("Error al crear transacción para el usuario %s", current_user.id)
        raise HTTPException(status_code=500, detail="Error interno al procesar la transacción contable.") from None

    # 🚨 Hook Fase 13 §13.3 (motor de presupuestos): se evalúa tras confirmar el
    # movimiento contable y solo para gastos. Decisión 13.3.4: un fallo del motor NUNCA
    # revierte la transacción ya confirmada ni tumba el request — se loguea y se sigue.
    # Decisión 13.3.1: evalúa el mes/año de la transacción recién guardada (su `date`),
    # no el mes en curso — un gasto atrasado se registra contra el período que corresponde.
    if nueva_transaccion.type == "expense":
        fecha = nueva_transaccion.date or datetime.now(UTC)
        evaluate_budget_thresholds_safely(
            db,
            current_user.id,
            nueva_transaccion.category_id,
            fecha,
            f"crear transacción {nueva_transaccion.id} del usuario {current_user.id}",
        )

    return nueva_transaccion


# --- RUTA PROTEGIDA ---
@router.get("/", response_model=schemas.PaginatedResponse[schemas.TransactionResponse])
def obtener_transacciones(
    skip: int = 0,
    limit: int = 100,
    account_id: int | None = None,
    category_id: int | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=400, detail="La fecha inicial no puede ser mayor que la fecha final.")

    query = db.query(models.Transaction).filter(models.Transaction.user_id == current_user.id)

    if account_id is not None:
        query = query.filter(models.Transaction.account_id == account_id)

    if category_id is not None:
        query = query.filter(models.Transaction.category_id == category_id)

    if start_date is not None:
        query = query.filter(models.Transaction.date >= start_date)

    if end_date is not None:
        query = query.filter(models.Transaction.date <= end_date)

    total = query.with_entities(func.count()).scalar()

    transacciones = (
        query.order_by(desc(models.Transaction.date), desc(models.Transaction.id)).offset(skip).limit(limit).all()
    )

    page = (skip // limit) + 1 if limit > 0 else 1

    return schemas.PaginatedResponse(
        items=transacciones,
        total=total,
        page=page,
        page_size=limit,
    )


# --- RUTA PROTEGIDA ---
@router.delete("/{transaction_id}")
def eliminar_transaccion(
    transaction_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)
):
    transaccion = db.query(models.Transaction).filter(models.Transaction.id == transaction_id).first()

    if not transaccion or transaccion.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="La transacción no existe o no tienes permisos.")

    # 1. Obtener la cuenta asociada a esta transacción
    cuenta = db.query(models.Account).filter(models.Account.id == transaccion.account_id).first()

    # 🧮 2. Lógica Contable Inversa: Revertir el impacto de forma atómica
    # (mismo filtro explícito de borrado lógico que en crear_transaccion)
    if cuenta:
        delta = -transaccion.amount if transaccion.type == "income" else transaccion.amount
        db.execute(
            update(models.Account)
            .where(
                models.Account.id == transaccion.account_id,
                models.Account.deleted_at.is_(None),
            )
            .values(balance=models.Account.balance + delta)
        )

    try:
        transaccion.deleted_at = datetime.now(UTC)  # borrado lógico: el impacto contable ya fue revertido arriba
        db.commit()
        return {"estado": "OK", "mensaje": "Transacción eliminada y saldo de cuenta revertido exitosamente."}
    except Exception:
        db.rollback()
        logger.exception("Error al eliminar la transacción %s del usuario %s", transaction_id, current_user.id)
        raise HTTPException(status_code=500, detail="Error al intentar eliminar y revertir saldos.") from None


@router.put("/{transaction_id}", response_model=schemas.TransactionResponse)
def actualizar_transaccion(
    transaction_id: int,
    transaccion_actualizada: schemas.TransactionBase,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> models.Transaction:
    # 1. Buscamos la transacción original
    transaccion_db = (
        db.query(models.Transaction)
        .filter(models.Transaction.id == transaction_id, models.Transaction.user_id == current_user.id)
        .first()
    )

    if not transaccion_db:
        raise HTTPException(status_code=404, detail="Transacción no encontrada.")

    # Categoría y fecha originales, capturadas ANTES de cualquier mutación: si el gasto se
    # reclasifica, hay que re-evaluar también la categoría de origen contra el período al
    # que pertenecía ANTES del cambio (no el período de la fecha nueva, que puede ser un
    # mes distinto) — el ROADMAP no pide retirar avisos ya emitidos, solo evaluar.
    categoria_vieja_id = transaccion_db.category_id
    fecha_vieja_original = transaccion_db.date

    # 1.1 Resolución Fase 16 §16.2 — misma lógica que en crear_transaccion: `account_id`
    # opcional (fallback a la única cuenta) y `category` por nombre → `category_id`.
    cuenta_resuelta = _resolver_cuenta(db, current_user.id, transaccion_actualizada.account_id)
    transaccion_actualizada.account_id = cuenta_resuelta.id

    if transaccion_actualizada.category_id is None:
        categoria_resuelta = _resolver_categoria_por_nombre(
            db, current_user.id, transaccion_actualizada.category, transaccion_actualizada.type.value
        )
        transaccion_actualizada.category_id = categoria_resuelta.id
        transaccion_actualizada.category = None  # nunca llega al model_dump (exclude_none)

    # 2. Buscamos las cuentas (la vieja y la nueva, por si el usuario movió el gasto a otra cuenta)
    cuenta_vieja = db.query(models.Account).filter(models.Account.id == transaccion_db.account_id).first()
    cuenta_nueva = (
        db.query(models.Account)
        .filter(models.Account.id == transaccion_actualizada.account_id, models.Account.user_id == current_user.id)
        .first()
    )

    if not cuenta_nueva:
        raise HTTPException(status_code=404, detail="La nueva cuenta asignada no existe o no te pertenece.")

    categoria = (
        db.query(models.Category)
        .filter(
            models.Category.id == transaccion_actualizada.category_id,
            or_(models.Category.user_id.is_(None), models.Category.user_id == current_user.id),
        )
        .first()
    )

    if not categoria:
        raise HTTPException(
            status_code=404, detail="La categoría especificada no existe o no tienes permisos para usarla."
        )

    old_delta = transaccion_db.amount if transaccion_db.type == "income" else -transaccion_db.amount
    new_delta = (
        transaccion_actualizada.amount if transaccion_actualizada.type == "income" else -transaccion_actualizada.amount
    )

    try:
        if cuenta_vieja.id == cuenta_nueva.id:
            net_delta = new_delta - old_delta
            db.execute(
                update(models.Account)
                .where(
                    models.Account.id == cuenta_vieja.id,
                    models.Account.deleted_at.is_(None),
                )
                .values(balance=models.Account.balance + net_delta)
            )
        else:
            db.execute(
                update(models.Account)
                .where(
                    models.Account.id == cuenta_vieja.id,
                    models.Account.deleted_at.is_(None),
                )
                .values(balance=models.Account.balance - old_delta)
            )
            db.execute(
                update(models.Account)
                .where(
                    models.Account.id == cuenta_nueva.id,
                    models.Account.deleted_at.is_(None),
                )
                .values(balance=models.Account.balance + new_delta)
            )

        transaccion_db.amount = transaccion_actualizada.amount
        transaccion_db.type = transaccion_actualizada.type
        transaccion_db.description = transaccion_actualizada.description
        transaccion_db.account_id = transaccion_actualizada.account_id
        transaccion_db.category_id = transaccion_actualizada.category_id
        # Sin condición: la moneda es un dato derivado de la cuenta, no un campo que el
        # usuario edite — siempre hereda la de la cuenta destino, igual que crear_transaccion.
        transaccion_db.currency = cuenta_nueva.currency
        # Opcional: si el cliente no reenvía payment_method conservamos el valor actual
        if transaccion_actualizada.payment_method is not None:
            transaccion_db.payment_method = transaccion_actualizada.payment_method
        if transaccion_actualizada.date is not None:
            transaccion_db.date = transaccion_actualizada.date

        db.commit()
        db.refresh(transaccion_db)
    except Exception:
        db.rollback()
        logger.exception("Error al actualizar la transacción %s del usuario %s", transaction_id, current_user.id)
        raise HTTPException(status_code=500, detail="Error al recalcular saldos en la actualización.") from None

    # 🚨 Hook Fase 13 §13.3 (motor de presupuestos): mismo criterio que en la creación —
    # después del commit contable, solo para gastos. Cada categoría se evalúa con su
    # propia llamada independiente (evaluate_budget_thresholds_safely ya encapsula su
    # propio try/except + rollback) para que un fallo evaluando la categoría nueva no
    # impida evaluar la vieja, ni viceversa.
    if transaccion_db.type == "expense":
        fecha_nueva = transaccion_db.date or datetime.now(UTC)
        evaluate_budget_thresholds_safely(
            db,
            current_user.id,
            transaccion_db.category_id,
            fecha_nueva,
            f"actualizar transacción {transaction_id} del usuario {current_user.id} (categoría nueva)",
        )
        # Si cambió de categoría, también se evalúa la de origen — contra el período al
        # que pertenecía la transacción ANTES del cambio (fecha_vieja_original), no el de
        # la fecha nueva. Un gasto que se reclasifica puede hacer que la categoría
        # anterior baje de umbral; el ROADMAP no pide retirar avisos ya emitidos.
        if categoria_vieja_id != transaccion_db.category_id:
            fecha_vieja = fecha_vieja_original or datetime.now(UTC)
            evaluate_budget_thresholds_safely(
                db,
                current_user.id,
                categoria_vieja_id,
                fecha_vieja,
                f"actualizar transacción {transaction_id} del usuario {current_user.id} (categoría anterior)",
            )

    return transaccion_db
