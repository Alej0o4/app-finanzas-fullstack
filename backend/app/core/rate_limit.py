from slowapi import Limiter
from slowapi.util import get_remote_address


def key_func_por_usuario_o_ip(request) -> str:
    """Si la petición trae una API key (Fase 16 §16.1), el límite es por usuario — una
    automatización corre desde una IP estable y el límite por IP no la protege de sí misma
    ni de un abuso si la key se filtra. Si es JWT o anónima, se mantiene el límite por IP
    existente (sin cambio de comportamiento para el frontend web).

    slowapi evalúa `key_func` ANTES de que las dependencias de FastAPI corran (no hay
    `current_user` disponible aquí — Decisión 16.1.7). Se keyea por el SHA-256 del token:
    cada API key pertenece a un solo usuario, así que funcionalmente es por usuario, y no
    hace falta consultar la DB en el key_func.
    """
    from app.core import security  # import diferido: rate_limit no depende de security en import-time

    auth = request.headers.get("authorization", "")
    token = auth.removeprefix("Bearer ").strip()
    if token.startswith(security.API_KEY_PREFIX):
        return security.hash_token(token)
    return get_remote_address(request)


limiter = Limiter(key_func=get_remote_address)
