"""CSRF vía double-submit cookie (Fase 26, Decisión B5).

Solo protege el camino de auth por cookie — una request autenticada por header
(Authorization: Bearer <jwt-o-api-key>, nunca adjuntado automáticamente por el navegador a
requests cross-site) no necesita este chequeo: el vector CSRF depende de que el navegador
adjunte credenciales SIN que el sitio que dispara la request pueda leerlas ni elegirlas, que
es exactamente lo que pasa con un cookie y nunca pasa con un header armado a mano por JS.

Se exime explícitamente:
- Métodos "seguros" (GET/HEAD/OPTIONS) — nunca deberían mutar estado; OPTIONS además es el
  preflight de CORS, que no debe rebotar antes de que CORSMiddleware lo conteste.
- Requests sin cookie `access_token` presente — nada que proteger si no hay sesión de
  cookie; cubre también el 100% del tráfico de API keys/Shortcuts de iOS.
- POST /api/v1/auth/login, /auth/google, /auth/refresh — antes de loguear no existe
  `csrf_token` todavía (login/google) o el cookie de refresh ya está protegido por su propio
  Path angosto + SameSite=Lax (que ya bloquea el vector real: un POST cross-site disparado
  por otro sitio no lleva cookies SameSite=Lax, salvo navegación top-level, que nunca es un
  POST). Exigir también el header ahí no suma protección real y complica el primer login
  (todavía no hay csrf_token que leer).
"""

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.auth_cookies import ACCESS_COOKIE_NAME, CSRF_COOKIE_NAME

_METODOS_SEGUROS = {"GET", "HEAD", "OPTIONS"}
_RUTAS_EXENTAS = {"/api/v1/auth/login", "/api/v1/auth/google", "/api/v1/auth/refresh"}
CSRF_HEADER_NAME = "X-CSRF-Token"


async def csrf_protection_middleware(request: Request, call_next) -> Response:
    if request.method in _METODOS_SEGUROS or request.url.path in _RUTAS_EXENTAS:
        return await call_next(request)

    cookie_sesion = request.cookies.get(ACCESS_COOKIE_NAME)
    if cookie_sesion is None:
        # Sin cookie de sesión: header-only (JWT o API key) o sin autenticar — no aplica.
        return await call_next(request)

    csrf_cookie = request.cookies.get(CSRF_COOKIE_NAME)
    csrf_header = request.headers.get(CSRF_HEADER_NAME)
    if not csrf_cookie or not csrf_header or csrf_cookie != csrf_header:
        return JSONResponse(
            status_code=403,
            content={"detail": "Token CSRF inválido o ausente."},
        )

    return await call_next(request)
