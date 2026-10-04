import hashlib
import json
import logging
from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy import desc, func, or_, update
from sqlalchemy.exc import DataError, IntegrityError
from sqlalchemy.orm import Session

from app.core.budget_alerts import evaluate_budget_thresholds_safely
from app.core.database import get_db
from app.core.exceptions import (
    AccountNotFoundError,
    BadRequestError,
    CategoryNotFoundError,
    ConflictError,
    InternalServerError,
    NotFoundError,
    ValidationError,
)
from app.core.periods import RANGO_DESC, instante_de_dia, resolver_rango
from app.core.rate_limit import key_func_por_usuario_o_ip, limiter

# 🔒 Importamos a nuestro Guardia de Seguridad
from app.core.security import get_current_user
from app.core.text import normalizar_nombre
from app.core.timezones import get_zoneinfo
from app.models import models
from app.schemas import schemas
from app.services import ledger

router = APIRouter()
logger = logging.getLogger(__name__)


# --- Helpers de resolución por nombre (Fase 16 §16.2) ---
def _resolver_categoria_por_nombre(db: Session, user_id: int, nombre: str, tipo: str) -> models.Category:
    """Resuelve una categoría por nombre (Fase 16 §16.2, Decisión 16.2.2).

    Reglas: filtrado por `type` (elimina ambigüedad cruzada gasto/ingreso), precedencia de
    categoría propia sobre categoría de sistema si ambas matchean, y `409` si hay más de un
    match dentro del mismo alcance (propio o sistema). Sin match → `404` con la lista de
    nombres válidos para ese tipo (sin fuzzy match, a propósito).

    La normalización del nombre vive en `app/core/text.py` (compartida con el chequeo de
    duplicados de `api/categories.py`, QA-028): la regla por la que este resolver llama
    "duplicado" es exactamente por (nombre normalizado, `type`), dentro de las categorías
    PROPIAS del usuario — el mismo ámbito en el que el 409 se manifiesta.
    """
    objetivo = normalizar_nombre(nombre)
    candidatas = (
        db.query(models.Category)
        .filter(
            or_(models.Category.user_id.is_(None), models.Category.user_id == user_id),
            models.Category.type == tipo,
        )
        .all()
    )
    matches = [c for c in candidatas if normalizar_nombre(c.name) == objetivo]
    propias = [c for c in matches if c.user_id == user_id]
    sistema = [c for c in matches if c.user_id is None]

    if propias:
        if len(propias) > 1:
            raise ConflictError(f"Tenés más de una categoría propia llamada '{nombre}'. Usá category_id.")
        return propias[0]
    if sistema:
        if len(sistema) > 1:  # no debería pasar hoy (DEFAULT_CATEGORIES no tiene duplicados), defensivo
            raise ConflictError(f"Categoría '{nombre}' ambigua.")
        return sistema[0]

    nombres_validos = sorted({c.name for c in candidatas})
    raise NotFoundError(f"Categoría '{nombre}' no encontrada. Válidas para {tipo}: {', '.join(nombres_validos)}.")


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
            raise AccountNotFoundError()  # 🔁 antes: raise HTTPException(404, "...")
        return cuenta

    cuentas_usuario = db.query(models.Account).filter(models.Account.user_id == user_id).all()
    if len(cuentas_usuario) != 1:
        raise BadRequestError(
            "Especificá account_id: tenés más de una cuenta." if cuentas_usuario else "No tenés ninguna cuenta activa."
        )
    return cuentas_usuario[0]


def _resolver_transaccion_idempotente(
    db: Session, existente: models.IdempotencyKey, request_hash: str
) -> models.Transaction:
    """Resuelve una `Idempotency-Key` ya usada (Fase 31, Decisión B7, QA-020): compara el
    hash del payload y devuelve la transacción original, o levanta `409` si el payload
    cambió o si la original ya no existe (soft-deleted).

    Compartido por las DOS ramas que pueden encontrar la clave ya usada — la consulta
    previa (camino feliz) y el `except IntegrityError` de abajo (la petición perdió una
    carrera contra otra con la misma clave). Antes de este fix esa segunda rama
    devolvía la transacción sin comparar el hash (un payload distinto se "colaba"
    silenciosamente) y, si la original estaba borrada, devolvía `None` — un `500` de
    validación de respuesta en vez de un error de dominio legible (Decisión 10.4.3).
    """
    if existente.request_hash != request_hash:
        raise ConflictError("Esta Idempotency-Key ya se usó con datos distintos.")
    transaccion_previa = db.query(models.Transaction).filter(models.Transaction.id == existente.transaction_id).first()
    if not transaccion_previa:
        # La transacción original fue borrada (soft-delete) desde el envío original —
        # ver caso borde en el spec de Fase 10, ítem 10.4.
        raise ConflictError("La transacción original de esta Idempotency-Key ya no existe.")
    return transaccion_previa


def _resolver_fecha(valor: date | datetime | None, tz) -> datetime | None:
    """Fase 34 B9: convierte la `date` del payload en el instante a guardar.

    Solo-día (`date`) → hoy en la zona del usuario: hora real (`now()`); otro día: las 12:00
    locales de ese día. Datetime completo → tal cual (un naive conserva el comportamiento de
    siempre: UTC). Sin `date` → `None` (el caller conserva `now()` o la fecha previa)."""
    if valor is None:
        return None
    if isinstance(valor, datetime):
        return valor
    return instante_de_dia(valor, datetime.now(UTC), tz)


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
            return _resolver_transaccion_idempotente(db, existente, request_hash)

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
        raise AccountNotFoundError()  # 🔁 antes: raise HTTPException(404, "...")

    categoria = (
        db.query(models.Category)
        .filter(
            models.Category.id == transaccion.category_id,
            or_(models.Category.user_id.is_(None), models.Category.user_id == current_user.id),
        )
        .first()
    )

    if not categoria:
        raise CategoryNotFoundError()  # 🔁 antes: raise HTTPException(404, "...")

    # Fase 34 B9: solo-día → instante según la zona del usuario (el hash de idempotencia ya
    # se calculó sobre el payload tal cual llegó).
    transaccion.date = _resolver_fecha(transaccion.date, get_zoneinfo(current_user.timezone))

    # 2. Ensamblar la transacción
    nueva_transaccion = models.Transaction(**transaccion.model_dump(exclude_none=True), user_id=current_user.id)
    nueva_transaccion.currency = cuenta.currency  # hereda la moneda de la cuenta

    try:
        db.add(nueva_transaccion)
        # 🧮 3. Lógica Contable (Fase 25 §25.1 — extraída a app/services/ledger.py: el
        # signo del delta y el UPDATE atómico viven en ledger.registrar_impacto /
        # aplicar_delta, que documenta el filtro deleted_at IS NULL — Decisión 6.1: un
        # update() ORM-enabled no queda cubierto por el filtro global select-only de
        # database.py, hay que llevarlo explícito en el WHERE).
        ledger.registrar_impacto(db, cuenta.id, transaccion.type, transaccion.amount)
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
        # Se perdió la carrera: otra petición con la misma clave ya insertó primero. Se
        # resuelve con el MISMO helper que la consulta previa (B7): compara el hash del
        # payload (409 si difiere) y valida que la original siga viva (409 si la
        # borraron) — antes esta rama devolvía la transacción sin comparar nada.
        existente = (
            db.query(models.IdempotencyKey)
            .filter(models.IdempotencyKey.user_id == current_user.id, models.IdempotencyKey.key == idempotency_key)
            .first()
        )
        if existente:
            return _resolver_transaccion_idempotente(db, existente, request_hash)
        raise InternalServerError("Error interno al procesar la transacción contable.") from None
    except DataError:
        # Fase 31 (Decisión B4, QA-015): con B3 el monto en sí ya es válido — el único
        # DataError posible acá es el desborde del UPDATE de Account.balance
        # (NumericValueOutOfRange en Postgres; no ocurre en SQLite, que no aplica
        # Numeric). Es un 422 de dominio, no un 500 en texto plano.
        db.rollback()
        raise ValidationError("La operación dejaría el saldo de la cuenta fuera del rango permitido.") from None
    except Exception:
        db.rollback()
        logger.exception("Error al crear transacción para el usuario %s", current_user.id)
        raise InternalServerError("Error interno al procesar la transacción contable.") from None

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
            get_zoneinfo(current_user.timezone),
        )

    return nueva_transaccion


# --- RUTA PROTEGIDA ---
@router.get("/", response_model=schemas.PaginatedResponse[schemas.TransactionResponse])
def obtener_transacciones(
    skip: int = Query(0, ge=0),
    # Tope de 1000 (QA-025): sin `le`, un cliente puede pedir `limit=999999999` y el backend
    # ejecuta un SELECT de toda la tabla — el filtro `user_id` acota, pero el trabajo no.
    # 1000 deja de sobra margen para el "Cargar más" del frontend, que suma 20 por página.
    limit: int = Query(100, ge=1, le=1000),
    account_id: int | None = None,
    category_id: int | None = None,
    start_date: str | None = Query(None, description=RANGO_DESC),
    end_date: str | None = Query(None, description=RANGO_DESC),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Fase 34 B7: cada extremo es un día `YYYY-MM-DD` (zona del usuario, fin exclusivo al
    # día siguiente) o un datetime completo (instante; `end_date` inclusivo).
    inicio, fin = resolver_rango(start_date, end_date, get_zoneinfo(current_user.timezone))
    if inicio is not None and fin is not None and inicio >= fin:
        raise BadRequestError("La fecha inicial no puede ser mayor que la fecha final.")

    # Fase 31 (Decisión B5, QA-006): `deleted_at IS NULL` explícito, aunque el filtro
    # global de `core/database.py` ya lo aplique a este SELECT — `total`, más abajo,
    # sale de `with_entities(func.count())`, que NO tiene entidad mapeada y por eso es
    # el único agregado del backend que el filtro global NO alcanza (H9). Dejarlo
    # implícito solo en el SELECT normal habría dejado el `total` contando las
    # borradas mientras `items` sí las excluía — "N de M" nunca cuadraba con la lista y
    # "Cargar más" quedaba disponible para siempre.
    query = db.query(models.Transaction).filter(
        models.Transaction.user_id == current_user.id,
        models.Transaction.deleted_at.is_(None),
    )

    if account_id is not None:
        query = query.filter(models.Transaction.account_id == account_id)

    if category_id is not None:
        query = query.filter(models.Transaction.category_id == category_id)

    if inicio is not None:
        query = query.filter(models.Transaction.date >= inicio)

    if fin is not None:
        query = query.filter(models.Transaction.date < fin)

    total = query.with_entities(func.count()).scalar()

    transacciones = (
        query.order_by(desc(models.Transaction.date), desc(models.Transaction.id)).offset(skip).limit(limit).all()
    )

    # Con `ge=1` (QA-025) la división ya nunca es por cero: el `if limit > 0 else 1` de
    # antes solo estaba para defenderse de un `limit=0` que el schema ahora rechaza con 422.
    page = (skip // limit) + 1

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
    # Fase 31 (Decisión B1, QA-003): `SELECT ... FOR UPDATE` es la PRIMERA consulta, con
    # el filtro `deleted_at IS NULL` explícito (el filtro global ya lo agrega a nivel
    # ORM, pero es lo que hace que, en Postgres, una segunda petición que estaba
    # esperando este lock reevalúe el WHERE al liberarse y no devuelva fila si la
    # primera ya la borró — así se serializan dos DELETE o un DELETE y un PUT
    # concurrentes sobre la misma transacción). En SQLite `with_for_update()` no genera
    # nada (no soportado) y la suite sigue corriendo sin el lock real.
    transaccion = (
        db.query(models.Transaction)
        .filter(
            models.Transaction.id == transaction_id,
            models.Transaction.user_id == current_user.id,
            models.Transaction.deleted_at.is_(None),
        )
        .with_for_update()
        .first()
    )

    if not transaccion:
        raise NotFoundError("La transacción no existe o no tienes permisos.")

    try:
        # 1. Borrado condicional (segunda defensa, Q2): un UPDATE Core con el mismo
        # WHERE que la SELECT de arriba. Si otra petición ganó la carrera entre esa
        # SELECT y este UPDATE (imposible en Postgres gracias al lock, pero es la
        # defensa que SQLite sí necesita, sin FOR UPDATE real), `rowcount == 0` y no se
        # toca el saldo.
        resultado = db.execute(
            update(models.Transaction)
            .where(
                models.Transaction.id == transaction_id,
                models.Transaction.user_id == current_user.id,
                models.Transaction.deleted_at.is_(None),
            )
            .values(deleted_at=datetime.now(UTC))
        )
        if resultado.rowcount == 0:
            db.rollback()
            raise NotFoundError("La transacción no existe o no tienes permisos.")

        # 🧮 2. Lógica Contable Inversa: revertir el impacto de forma atómica (Fase 25
        # §25.1 — el filtro deleted_at IS NULL vive en ledger.aplicar_delta), SOLO
        # después de confirmar el borrado — antes el orden era el inverso (revertía el
        # saldo y recién después marcaba deleted_at sin condición), que es justamente lo
        # que permitía revertir el saldo dos veces con dos DELETE simultáneos.
        cuenta = db.query(models.Account).filter(models.Account.id == transaccion.account_id).first()
        if cuenta:
            ledger.revertir_impacto(db, transaccion.account_id, transaccion.type, transaccion.amount)

        db.commit()
        return {"estado": "OK", "mensaje": "Transacción eliminada y saldo de cuenta revertido exitosamente."}
    except NotFoundError:
        raise
    except DataError:
        # Fase 31 (Decisión B4, QA-015): desborde del saldo al revertir el impacto
        # (p. ej. revertir un gasto sobre una cuenta ya en el tope de Numeric(14,2)).
        db.rollback()
        raise ValidationError("La operación dejaría el saldo de la cuenta fuera del rango permitido.") from None
    except Exception:
        db.rollback()
        logger.exception("Error al eliminar la transacción %s del usuario %s", transaction_id, current_user.id)
        raise InternalServerError("Error al intentar eliminar y revertir saldos.") from None


@router.put("/{transaction_id}", response_model=schemas.TransactionResponse)
def actualizar_transaccion(
    transaction_id: int,
    transaccion_actualizada: schemas.TransactionBase,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> models.Transaction:
    # 1. Buscamos la transacción original — `SELECT ... FOR UPDATE` (Fase 31, Decisión
    # B1, QA-003): el mismo lock de fila que `eliminar_transaccion`, para que el delta
    # se calcule sobre el `amount`/`type`/`account_id` que dejó la última escritura
    # confirmada, no sobre una versión ya obsoleta leída antes de que otra petición
    # concurrente terminara. Sin segunda defensa condicional acá (a diferencia de
    # DELETE): el UPDATE del ORM de abajo va por clave primaria y su seguridad
    # descansa en este lock. En SQLite `with_for_update()` no genera nada.
    transaccion_db = (
        db.query(models.Transaction)
        .filter(
            models.Transaction.id == transaction_id,
            models.Transaction.user_id == current_user.id,
            models.Transaction.deleted_at.is_(None),
        )
        .with_for_update()
        .first()
    )

    if not transaccion_db:
        raise NotFoundError("Transacción no encontrada.")

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

    # 2. La cuenta DESTINO (la vieja no se consulta: su id YA es `transaccion_db.account_id`
    # por construcción, y con la query de más el `cuenta_vieja.id` de abajo era un
    # `AttributeError` si la fila estaba borrada — QA-031).
    cuenta_nueva = (
        db.query(models.Account)
        .filter(models.Account.id == transaccion_actualizada.account_id, models.Account.user_id == current_user.id)
        .first()
    )

    if not cuenta_nueva:
        raise NotFoundError("La nueva cuenta asignada no existe o no te pertenece.")

    categoria = (
        db.query(models.Category)
        .filter(
            models.Category.id == transaccion_actualizada.category_id,
            or_(models.Category.user_id.is_(None), models.Category.user_id == current_user.id),
        )
        .first()
    )

    if not categoria:
        raise CategoryNotFoundError()  # 🔁 antes: raise HTTPException(404, "...")

    try:
        ledger.aplicar_edicion(
            db,
            # QA-031: se pasa el id directo. La query que lo traía era redundante por
            # construcción —`cuenta_vieja.id` ES `transaccion_db.account_id`— y solo servía
            # para tapar el caso "la cuenta vieja ya está borrada", donde devolvía `None` y
            # el `.id` de abajo reventaba con `AttributeError`. La semántica NO cambia:
            # `ledger.aplicar_delta` filtra `deleted_at IS NULL` (Decisión 6.1 de la Fase 31),
            # así que una cuenta desaparecida conserva su saldo obsoleto — que además no
            # aparece en ninguna lista.
            cuenta_vieja_id=transaccion_db.account_id,
            cuenta_nueva_id=cuenta_nueva.id,
            tipo_viejo=transaccion_db.type,
            monto_viejo=transaccion_db.amount,
            tipo_nuevo=transaccion_actualizada.type,
            monto_nuevo=transaccion_actualizada.amount,
        )

        transaccion_db.amount = transaccion_actualizada.amount
        transaccion_db.type = transaccion_actualizada.type
        transaccion_db.account_id = transaccion_actualizada.account_id
        transaccion_db.category_id = transaccion_actualizada.category_id
        # Sin condición: la moneda es un dato derivado de la cuenta, no un campo que el
        # usuario edite — siempre hereda la de la cuenta destino, igual que crear_transaccion.
        transaccion_db.currency = cuenta_nueva.currency

        # 🐛 QA-026 — actualización parcial real para los campos opcionales, con el mismo
        # idioma que `actualizar_cuenta` (`model_fields_set`, Fase 24 §24.3 Decisión C1):
        # AUSENTE conserva, `null` explícito limpia. Antes `description` se asignaba siempre
        # (`transaccion_db.description = transaccion_actualizada.description`), así que un
        # cliente API que actualizara solo el monto —sin reenviar el texto— borraba la
        # descripción sin querer (los atajos móviles y la captura por nombre son justamente
        # clientes que mandan payloads parciales).
        #
        # La WEB no cambia de comportamiento: `EditTransactionModal` siempre manda la clave
        # `description`, y vacía → `null`, así que borrar el texto sigue borrándolo.
        campos_enviados = transaccion_actualizada.model_fields_set
        if "description" in campos_enviados:
            transaccion_db.description = transaccion_actualizada.description
        if "payment_method" in campos_enviados:
            transaccion_db.payment_method = transaccion_actualizada.payment_method
        # `date` NO lleva la misma regla a propósito: `Transaction.date` es nullable en el
        # modelo, pero `TransactionResponse.date` es `datetime` (no opcional). Aceptar un
        # `null` explícito dejaría la fila sin fecha y el response en 500
        # (`ResponseValidationError`), así que acá sigue la regla anterior: ausente o null
        # → conserva la fecha actual.
        if transaccion_actualizada.date is not None:
            transaccion_db.date = _resolver_fecha(transaccion_actualizada.date, get_zoneinfo(current_user.timezone))

        db.commit()
        db.refresh(transaccion_db)
    except DataError:
        # Fase 31 (Decisión B4, QA-015): desborde del saldo de alguna de las cuentas
        # involucradas (misma cuenta con delta neto, o la vieja/nueva si se movió).
        db.rollback()
        raise ValidationError("La operación dejaría el saldo de la cuenta fuera del rango permitido.") from None
    except Exception:
        db.rollback()
        logger.exception("Error al actualizar la transacción %s del usuario %s", transaction_id, current_user.id)
        raise InternalServerError("Error al recalcular saldos en la actualización.") from None

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
            get_zoneinfo(current_user.timezone),
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
                get_zoneinfo(current_user.timezone),
            )

    return transaccion_db
