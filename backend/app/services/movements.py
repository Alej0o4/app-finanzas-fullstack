"""Feed unificado de movimientos: transacciones + transferencias (Fase 39 §B4).

Una sola consulta `UNION ALL` ordenada y paginada en la base de datos; luego se cargan las filas
completas de la página. Los totales/KPI NO salen de acá: ningún agregado existente lee `transfers`
(las transferencias no son flujo). Los filtros que no tienen sentido para una transferencia
(`category_id`, `type`, búsqueda de texto) las excluyen.
"""

from sqlalchemy import String, cast, func, literal_column, or_, select, union_all
from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestError
from app.core.periods import resolver_rango
from app.core.timezones import get_zoneinfo
from app.models import models
from app.schemas import schemas
from app.services import funds as funds_service
from app.services import transfers as transfers_service


def _adjuntar_enlaces(db: Session, transacciones: list[models.Transaction]) -> None:
    """Mismos campos transitorios de sobre que `GET /transactions` (Fase 36 D15)."""
    mapa = funds_service.vinculos(db, [t.id for t in transacciones])
    for t in transacciones:
        t.fund_id, t.fund_applied_amount = mapa.get(t.id, (None, None))


def listar(
    db: Session,
    user: models.User,
    *,
    account_id: int | None,
    category_id: int | None,
    tipo: str | None,
    busqueda: str | None,
    start_date: str | None,
    end_date: str | None,
    include_transfers: bool,
    skip: int,
    limit: int,
) -> dict:
    inicio, fin = resolver_rango(start_date, end_date, get_zoneinfo(user.timezone))
    if inicio is not None and fin is not None and inicio >= fin:
        raise BadRequestError("La fecha inicial no puede ser mayor que la fecha final.")

    T, F = models.Transaction, models.Transfer
    tx = select(
        cast(literal_column("'transaction'"), String).label("kind"), T.id.label("id"), T.date.label("date")
    ).where(T.user_id == user.id, T.deleted_at.is_(None))
    if account_id is not None:
        tx = tx.where(T.account_id == account_id)
    if category_id is not None:
        tx = tx.where(T.category_id == category_id)
    if tipo is not None:
        tx = tx.where(T.type == tipo)
    if busqueda:
        tx = tx.where(func.lower(T.description).contains(busqueda.lower(), autoescape=True))
    if inicio is not None:
        tx = tx.where(T.date >= inicio)
    if fin is not None:
        tx = tx.where(T.date < fin)

    partes = [tx]
    # category_id / tipo / texto no aplican a una transferencia: la excluyen (B4).
    if include_transfers and category_id is None and tipo is None and not busqueda:
        tr = select(
            cast(literal_column("'transfer'"), String).label("kind"), F.id.label("id"), F.date.label("date")
        ).where(F.user_id == user.id)
        if account_id is not None:
            tr = tr.where(or_(F.from_account_id == account_id, F.to_account_id == account_id))
        if inicio is not None:
            tr = tr.where(F.date >= inicio)
        if fin is not None:
            tr = tr.where(F.date < fin)
        partes.append(tr)

    union = (union_all(*partes) if len(partes) > 1 else partes[0]).subquery()
    total = db.execute(select(func.count()).select_from(union)).scalar() or 0
    pagina = db.execute(
        select(union.c.kind, union.c.id)
        .order_by(union.c.date.desc(), union.c.id.desc(), union.c.kind.desc())
        .offset(skip)
        .limit(limit)
    ).all()

    ids_tx = [r.id for r in pagina if r.kind == "transaction"]
    ids_tr = [r.id for r in pagina if r.kind == "transfer"]
    transacciones = {t.id: t for t in db.query(T).filter(T.id.in_(ids_tx)).all()} if ids_tx else {}
    transferencias = {t.id: t for t in db.query(F).filter(F.id.in_(ids_tr)).all()} if ids_tr else {}
    _adjuntar_enlaces(db, list(transacciones.values()))
    resp_tr = {fila["id"]: fila for fila in transfers_service.respuestas(db, list(transferencias.values()))}

    items = []
    for r in pagina:
        if r.kind == "transaction":
            items.append(schemas.TransactionMovement.model_validate(transacciones[r.id], from_attributes=True))
        else:
            items.append(schemas.TransferMovement(**resp_tr[r.id]))
    return {"items": items, "total": total, "page": (skip // limit) + 1, "page_size": limit}
