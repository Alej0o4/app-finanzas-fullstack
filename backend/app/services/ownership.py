"""Lectura de una fila propia del usuario, con `FOR UPDATE` opcional, compartida por los servicios.

Cuatro servicios (sobres, CDT, transferencias, recurrentes) tenían la misma consulta pegada:
filtrar por `id` + `user_id`, bloquear la fila si la operación escribe y responder 404 si no
existe o es de otro usuario. En SQLite `with_for_update()` no genera nada.
"""

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError


def obtener_propio[M](
    db: Session,
    modelo: type[M],
    user_id: int,
    id_: int,
    mensaje_no_existe: str,
    *,
    bloquear: bool = False,
    releer: bool = False,
) -> M:
    """Devuelve la fila `id_` de `modelo` si pertenece a `user_id`; si no, `NotFoundError`.

    `bloquear=True` toma `FOR UPDATE` y debe ser la PRIMERA consulta de la operación (serializa
    escrituras concurrentes sobre la misma fila). `releer=True` agrega `populate_existing()`
    para refrescar una fila ya cargada en la sesión con lo que dejó quien tenía el lock.
    """
    consulta = db.query(modelo).filter(modelo.id == id_, modelo.user_id == user_id)  # type: ignore[attr-defined]
    if bloquear:
        consulta = consulta.with_for_update()
        if releer:
            consulta = consulta.populate_existing()
    fila = consulta.first()
    if fila is None:
        raise NotFoundError(mensaje_no_existe)
    return fila
