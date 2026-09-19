"""Seteo/limpieza de los cookies de sesión (Fase 26).

`login`, `login_google` y `refresh` (app/api/auth.py) necesitan setear exactamente los
mismos tres cookies con los mismos flags cada vez que emiten un par de tokens nuevo;
`logout` y `eliminar_cuenta_propia` (app/api/users.py) necesitan limpiarlos exactamente
igual. Extraído a un solo lugar desde el primer commit de esta fase para no repetir el
copy-paste que Fase 25 §25.1 ya tuvo que corregir para el delta contable de
transactions.py — ver Hallazgo 5 de docs/specs/fase_26_spec.md.

Nombres y paths de los tres cookies (contrato compartido con frontend/lib/api.ts y
frontend/lib/authSession.ts — Decisiones F1/F2 de la misma spec):
- access_token:  HttpOnly, Path=/,                         Max-Age = TTL del JWT (15 min).
- refresh_token: HttpOnly, Path=/api/v1/auth,               Max-Age = 30 días.
- csrf_token:    NO HttpOnly (el frontend lo lee por JS),  Path=/,  mismo Max-Age que refresh_token.

Path de refresh_token corregido a `/api/v1/auth` (no solo `/api/v1/auth/refresh`, como decía
la primera versión de esta fase): con el Path angosto, el cookie nunca llegaba a
`POST /auth/logout` (ruta hermana, no subruta de `/refresh`) y el logout desde el navegador
nunca revocaba el refresh token en la DB — quedaba activo hasta su expiración natural (30
días) pese a que el usuario creía haber cerrado sesión. `/api/v1/auth` sigue excluyendo el
cookie de mayor privilegio de todas las rutas de datos de la app (transacciones, cuentas,
etc.) — el objetivo original de la Decisión B2 —, solo deja de ser tan angosto como para
romper el propio logout.

`Secure` y `SameSite` son iguales para los tres — ver COOKIE_SECURE en security.py
(Decisión B3).
"""

import secrets

from starlette.responses import Response

from app.core import security

CSRF_COOKIE_NAME = "csrf_token"
ACCESS_COOKIE_NAME = "access_token"
REFRESH_COOKIE_NAME = "refresh_token"
REFRESH_COOKIE_PATH = "/api/v1/auth"


def generar_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def establecer_cookies_de_sesion(
    response: Response,
    *,
    access_token: str,
    refresh_token: str,
    csrf_token: str,
) -> None:
    """Setea los tres cookies de sesión en una respuesta de login/google/refresh."""
    cookie_kwargs = {
        "secure": security.COOKIE_SECURE,
        "samesite": "lax",
    }
    response.set_cookie(
        ACCESS_COOKIE_NAME,
        access_token,
        max_age=security.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
        httponly=True,
        **cookie_kwargs,
    )
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        refresh_token,
        max_age=security.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        **cookie_kwargs,
    )
    # NO httponly: frontend/lib/api.ts lo lee de document.cookie para mandarlo de vuelta
    # como header X-CSRF-Token (patrón double-submit, Decisión B5). No es un secreto de
    # autenticación por sí solo — solo prueba que quien arma la request puede leer cookies
    # de este origen, que un atacante cross-site no puede.
    response.set_cookie(
        CSRF_COOKIE_NAME,
        csrf_token,
        max_age=security.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path="/",
        httponly=False,
        **cookie_kwargs,
    )


def limpiar_cookies_de_sesion(response: Response) -> None:
    """Usado por logout y por la baja de cuenta (Hallazgo 6) — mismos paths que al setear,
    o `delete_cookie` no los encuentra (un cookie se identifica por name+path+domain)."""
    response.delete_cookie(ACCESS_COOKIE_NAME, path="/")
    response.delete_cookie(REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH)
    response.delete_cookie(CSRF_COOKIE_NAME, path="/")
