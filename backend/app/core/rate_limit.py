from slowapi import Limiter
from slowapi.util import get_remote_address


def key_func_por_usuario_o_ip(request) -> str:
    """Si la petición trae una API key válida y no revocada (Fase 16 §16.1), el límite es
    por usuario — una automatización corre desde una IP estable y el límite por IP no la
    protege de sí misma ni de un abuso si la key se filtra. Si es JWT o anónima, se
    mantiene el límite por IP existente (sin cambio de comportamiento para el frontend web).

    Revisión de seguridad post-16.1 (Decisión 16.1.8, ver docs/TODO.md): la primera versión
    de esta función keyeaba directamente por el hash del token presentado, y **no era "por
    usuario" pese al nombre/comentario original** — corregido acá. Dos API keys distintas
    del mismo usuario producían dos hashes distintos, es decir dos contadores
    independientes: un usuario con N keys activas (sin límite propio hasta esta misma
    revisión — ver `MAX_ACTIVE_API_KEYS_POR_USUARIO` en `api_keys.py`) podía repartir
    tráfico entre ellas y multiplicar por N su cuota real de `60/minute`, exactamente el
    tipo de automatización sin freno que la Decisión 16.1.7 buscaba evitar. Confirmado con
    el test que existía antes de este fix (`test_rate_limit_counter_is_per_api_key`), que
    afirmaba ese comportamiento como si fuera el diseño correcto. Ahora se resuelve el
    `user_id` real de la key contra la DB y se clavea por usuario — todas las keys activas
    de un mismo usuario comparten un único balde.

    Nota descartada tras verificar contra el código de `slowapi` instalado (0.1.9): un
    token inválido/revocado con el prefijo correcto **no** logra un balde propio infinito
    en esta ruta como se sospechó en un primer análisis — `get_current_user` ya devolvió
    401 antes de que FastAPI invoque la función decorada (el decorador de `slowapi` envuelve
    la función de la ruta, que sólo se llama después de resolver todas las dependencias), así
    que `key_func` nunca llega a ejecutarse para esas requests en este endpoint. El fallback
    a IP para keys inválidas que queda más abajo es entonces defensivo (correcto si esta
    función se reutiliza en una ruta con auth opcional o si cambia el orden de ejecución),
    no una corrección de un bypass activo hoy — verificado enviando 80 requests con tokens
    `oikos_pat_` inventados distintos: los 80 devuelven 401, ninguno cuenta contra el límite
    ni lo elude (no hay nada que eludir, el 401 ya cortó antes).

    slowapi evalúa `key_func` dentro del wrapper de la ruta decorada, con las dependencias de
    FastAPI (`current_user`, `db`) ya resueltas pero no expuestas a esta función — por eso se
    abre acá una sesión de DB propia, respetando `app.dependency_overrides[get_db]` si existe
    (necesario para que los tests, que corren sobre una sesión de SQLite en memoria distinta
    al `SessionLocal` de producción, vean las keys creadas dentro del propio test).
    """
    from app.core import security  # import diferido: rate_limit no depende de security en import-time
    from app.core.database import get_db
    from app.models import models

    auth = request.headers.get("authorization", "")
    token = auth.removeprefix("Bearer ").strip()
    if not token.startswith(security.API_KEY_PREFIX):
        return get_remote_address(request)

    try:
        db_dependency = request.app.dependency_overrides.get(get_db, get_db)
        db_gen = db_dependency()
        try:
            db = next(db_gen)
            api_key = (
                db.query(models.ApiKey)
                .filter(
                    models.ApiKey.key_hash == security.hash_token(token),
                    models.ApiKey.revoked_at.is_(None),
                )
                .first()
            )
        finally:
            db_gen.close()
    except Exception:
        # Nunca dejar que una falla en la resolución del rate limit tumbe el request en sí
        # (p. ej. un error de DB transitorio) — degradar a límite por IP en vez de propagar.
        return get_remote_address(request)

    if api_key is None:
        return get_remote_address(request)

    return f"api_key_user:{api_key.user_id}"


limiter = Limiter(key_func=get_remote_address)
