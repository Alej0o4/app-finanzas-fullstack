# Spec — Fase 26: JWT de `localStorage` a cookies `httpOnly`

> Plan de implementación detallado para el único ítem pendiente de esta fase — la migración de
> auth de `localStorage` a cookies `httpOnly` que [ROADMAP.md](../ROADMAP.md) (sección "Próxima
> fase planeada — Fase 26: JWT en cookies httpOnly", líneas 56–68 al momento de escribir esto)
> señala como la siguiente fase, y que `docs/specs/fase_25_spec.md` §25.5 (decisiones J1–J8)
> diseñó pero deliberadamente NO ejecutó — ver Decisión J1 de esa spec para el razonamiento
> completo de por qué se diferó a un spec propio. Este documento retoma ese diseño, lo
> reverifica contra el código actual (algunos hallazgos de J1–J8 quedaron desactualizados o
> incompletos porque Fase 25 se implementó después de escribirse esa sección, y porque J1–J8
> nunca revisó el blast radius real del lado frontend), lo corrige donde corresponde, y lo
> desglosa en tareas ejecutables — código concreto, archivos, decisiones numeradas, separadas
> explícitamente en Backend/Frontend para que agentes `backend-engineer`/`frontend-engineer`
> distintos puedan tomar cada mitad en paralelo.
>
> **No implementa nada.** Ningún archivo del repositorio fuera de `docs/specs/fase_26_spec.md`
> (y el pointer agregado a `docs/ROADMAP.md`) fue modificado al producir este documento. Los
> hallazgos fueron verificados el 2026-09-19 contra el código real: lectura completa de
> `backend/app/core/security.py`, `backend/app/main.py`, `backend/app/api/auth.py`,
> `backend/app/api/users.py` (bloque de borrado de cuenta), `backend/app/core/exceptions.py`,
> `backend/app/schemas/auth.py`, `frontend/lib/api.ts`, `frontend/lib/hooks/useRequireAuth.ts`,
> `frontend/lib/hooks/useUserPreferences.ts`, `frontend/components/auth/GoogleAuthButton.tsx`,
> `frontend/components/Sidebar.tsx`, `frontend/components/ThemeToggle.tsx`,
> `frontend/app/(auth)/login/page.tsx`, `frontend/app/(auth)/register/page.tsx`,
> `frontend/app/(dashboard)/settings/page.tsx`, `docker-compose.yml`, `docker-compose.dev.yml`,
> `backend/tests/conftest.py`, `backend/tests/test_auth.py`, `backend/tests/test_api_keys.py`,
> `docs/TODO.md`, `CODE_REVIEW.md`, y el código instalado de `starlette` (`Response.set_cookie`,
> `Starlette.add_middleware`/`build_middleware_stack`) para verificar el comportamiento real de
> dos mecanismos de los que J1–J8 no podía dar por sentado el comportamiento exacto — no
> inferido de la spec de Fase 25 en aislado, aunque esa spec es el punto de partida correcto.

Estado del repo al momento de escribir esto (2026-09-19): Fases 7–25 completas. Este es el
único ítem que queda del diseño J1–J8 de Fase 25 sin ejecutar. No hay ningún otro trabajo de
arquitectura pendiente que compita con este en el mismo lote — es una fase de un solo ítem, a
propósito (ver Decisión J1 de `fase_25_spec.md`).

---

## Hallazgos de exploración que corrigen/precisan el diseño J1–J8

1. **`get_current_user` (`backend/app/core/security.py:108-130`) no puede recibir un fallback
   de cookie con un simple `if`, como sugiere J3 al pie de la letra — `oauth2_scheme`
   (`security.py:56`, `OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")`) no pasa
   `auto_error=False`, así que su valor por defecto es `auto_error=True`: si no hay header
   `Authorization`, la propia dependencia de FastAPI lanza `401` **antes** de que el cuerpo de
   `get_current_user` llegue a ejecutarse. Un fallback a cookie dentro del cuerpo de la función
   nunca se alcanzaría para una request sin header. Hace falta cambiar `oauth2_scheme` a
   `auto_error=False` y agregar `request: Request` como parámetro de `get_current_user` para
   poder leer `request.cookies` cuando el header viene vacío (Decisión B4).

2. **El "único cambio en `lib/api.ts`" que asume J1/J5 subestima el blast radius real: hay 8
   archivos de frontend, no 1, que leen/escriben `localStorage.getItem('jwt_token')` /
   `'refresh_token'` fuera de `lib/api.ts` mismo** — verificado con
   `grep -rln "jwt_token\|refresh_token" frontend --include="*.ts" --include="*.tsx"`:
   - **Escritura** (guardan tokens tras autenticar): `frontend/app/(auth)/login/page.tsx:73-74`,
     `frontend/app/(auth)/register/page.tsx:69-70`,
     `frontend/components/auth/GoogleAuthButton.tsx:45-46`.
   - **Lectura como "¿hay sesión activa?"** (no para autenticar una request — solo para decidir
     si renderizar/consultar algo): `frontend/lib/hooks/useRequireAuth.ts:13` (guard de
     `(dashboard)/layout.tsx` y `app/capture/layout.tsx`),
     `frontend/lib/hooks/useUserPreferences.ts:14` (`enabled: hasToken` de un `useQuery`),
     `frontend/components/ThemeToggle.tsx:79` (decide si persistir el tema al backend).
   - **Borrado** (logout / baja de cuenta): `frontend/components/Sidebar.tsx:51,59-60` (además
     lee `refresh_token` para mandarlo en el body de `POST /auth/logout`),
     `frontend/app/(dashboard)/settings/page.tsx:117-118` (`onSuccess` de
     `DELETE /api/v1/users/me`).

   Ninguno de estos 8 sitios existe todavía como tarea en J1–J8 — todos necesitan una decisión
   explícita (Decisiones F3–F5), no solo "borrar lo que haya en `lib/api.ts`".

3. **El interceptor de refresh de `lib/api.ts` tiene un bug latente para este mismo propósito,
   ya presente hoy, que se activaría recién con cookies: la llamada de refresh usa `axios.post`
   crudo, no la instancia `api` configurada.** `frontend/lib/api.ts:58`
   (`axios.post(`${api.defaults.baseURL}/auth/refresh`, ...)`) llama al módulo `axios` importado
   directo, no a `export const api = axios.create(...)` (línea 3-5) — cualquier opción que se
   agregue a `api` (como `withCredentials: true`, Decisión F1) **no aplica a esta llamada en
   particular** salvo que se le pase explícitamente. Hoy no importa (el refresh viaja en el
   body JSON, no en una cookie), pero si `withCredentials` no se agrega también acá, la cookie
   `refresh_token` nunca viajaría en la única llamada que la necesita — el propio mecanismo de
   renovación quedaría roto en silencio. Cambiar esta línea a `api.post('auth/refresh', ...)` es
   parte de la Decisión F1, no un detalle menor.

4. **`Response.set_cookie` de Starlette (versión instalada, `starlette==1.2.1`) ya defaultea
   `path="/"` si no se pasa `path` explícito** (`starlette/responses.py:89-99`, firma completa
   verificada) — a diferencia del default-path de la RFC 6265 cruda (que derivaría el path del
   propio endpoint que responde, ej. `/api/v1/auth` para una respuesta de `/api/v1/auth/login`,
   lo cual habría roto el envío de `access_token` a cualquier otra ruta). No hace falta ningún
   workaround por esto — alcanza con pasar `path="/"` explícito por claridad para
   `access_token`/`csrf_token`, y `path="/api/v1/auth/refresh"` explícito para `refresh_token`
   (Decisión B2).

5. **Los routers `login`, `login_google` y `refresh` (`backend/app/api/auth.py:20-57,60-139,
   142-181`) ya arman el mismo bloque de emisión de tokens tres veces** — el mismo patrón de
   copy-paste que Fase 25 §25.1 (Hallazgo 1 de `fase_25_spec.md`) ya encontró y corrigió para
   el delta contable de `transactions.py`. Agregar el seteo de cookies sin extraerlo a un
   helper compartido repetiría exactamente el mismo error que esa fase acaba de pagar — se
   extrae a `app/core/auth_cookies.py` desde el primer commit (Decisión B1), no como mejora
   futura.

6. **`DELETE /api/v1/users/me` (`backend/app/api/users.py:139-160`, `eliminar_cuenta_propia`)
   no está en el alcance de J1–J8 pero necesita el mismo tratamiento que logout: borra al
   usuario de la base de datos pero hoy nunca revoca ni limpia nada del lado del cliente más
   allá de lo que hacía `settings/page.tsx` manualmente en `localStorage`.** Con cookies
   `httpOnly`, el frontend ya no puede limpiarlas — si este endpoint no las limpia en su propia
   respuesta, el navegador conserva un `access_token`/`refresh_token` con apariencia válida
   hasta que expiren solos (15 min / 30 días) apuntando a un `user_id` que ya no existe. No es
   una vulnerabilidad grave (`get_current_user` haría `404`-equivalente vía `user is None` →
   401 en el siguiente request, `security.py:126-128`), pero es una inconsistencia de UX e
   higiene que el diseño original no contempló — se resuelve reusando el mismo helper de
   limpieza que logout (Decisión B8).

7. **La topología de orígenes de `docker-compose.yml` que documentó Fase 25 (Hallazgo 11)
   sigue exacta, pero con una precisión que J2 pasó por alto: los cookies no distinguen por
   puerto en absoluto (RFC 6265, atributo `Domain` es solo host, nunca incluye puerto), así que
   la pregunta "¿alcanza `SameSite=Lax` entre :3000 y :8000?" tiene una respuesta más fuerte de
   lo que sugiere J2's frase ("mismo registrable domain, distinto puerto — Lax alcanza"): no
   hace falta ni razonar sobre "site" vs "origin" — un cookie seteado sin `Domain` explícito
   por una respuesta de `http://100.76.235.30:8000` ya es visible y se envía automáticamente en
   requests a `http://100.76.235.30:3000`, porque para el navegador es **el mismo host**, punto.
   `SameSite=Lax` es, aun así, la elección correcta (protege contra el vector real de CSRF:
   requests de un origen *distinto*), no hace falta `SameSite=None`.

8. **Hallazgo nuevo, no cubierto por J2: la mayoría del tráfico de este despliegue corre sobre
   `http://`, no `https://`, así que `Secure=True` en los cookies rompería el acceso hoy, no
   solo "en teoría".** Verificado contra `docker-compose.yml` (`ALLOWED_ORIGINS` default
   `http://localhost:3000,http://100.76.235.30:3000`, sin ningún origen `https://`) y
   `docker-compose.dev.yml` (`NEXT_PUBLIC_API_URL=http://localhost:8000`) — no hay ningún
   `nginx`/`caddy`/`traefik` en el repo (`grep` sin resultados) que termine TLS delante de
   `backend`/`frontend`; ambos contenedores sirven HTTP plano. Un cookie con `Secure=True` **no
   se envía nunca** a un origen `http://`, sin importar que Tailscale cifre el transporte por
   debajo (WireGuard cifra la red; el navegador solo mira el esquema de la URL, `http:` vs
   `https:`, para decidir si manda un cookie `Secure`). Fijar `Secure=True` incondicional
   rompería el login para el 100% del acceso actual por IP de Tailscale (`http://100.76.235.30:
   3000`) — el único acceso hoy que sí es HTTPS real es el Tailscale Funnel
   (`https://<host>.<tailnet>.ts.net`, activo desde 2026-09-06, CLAUDE.md). El default de
   `COOKIE_SECURE` cambia a `true` en la resolución final de esta fase — ver Hallazgo 9 y
   Decisión B10, que consolidan el acceso de producción sobre ese dominio HTTPS.

9. **Resuelto el 2026-09-19, con el usuario, corriendo `tailscale funnel status` directo en el
   host de despliegue (esta sesión corre en esa misma máquina) — no es una pregunta abierta.**
   Salida real:

   ```
   https://alejo-yoga-6-13alc6.tail44159c.ts.net (Funnel on)
   |-- /     proxy http://127.0.0.1:3000
   |-- /api  proxy http://127.0.0.1:8000/api
   ```

   Funnel ya enruta frontend y backend **bajo el mismo hostname público**, con `/` al frontend
   y `/api` al backend (que a su vez sirve todo bajo `/api/v1/...`, así que
   `https://<host>/api/v1/auth/login` llega correctamente a `http://127.0.0.1:8000/api/v1/
   auth/login`). Sin embargo, se confirmó el problema que este hallazgo anticipaba: el build de
   frontend sigue usando `NEXT_PUBLIC_API_URL=http://100.76.235.30:8000` (default de
   `docker-compose.yml`) — una página servida por HTTPS desde el dominio `.ts.net` haciendo
   `fetch`/XHR a ese endpoint `http://` es contenido mixto activo, que los navegadores bloquean
   por default. El acceso autenticado vía Funnel está roto hoy por este motivo, independiente de
   cookies. **Decisión del usuario (2026-09-19): consolidar el acceso de producción en un solo
   origen HTTPS vía este dominio de Funnel en vez de dejarlo como limitación conocida — ver
   Decisión B10 (backend/infra) y F6 (frontend).**

10. **No existe ningún mecanismo CSRF en el repo — confirmado de nuevo, sin cambios desde Fase
    25** (`grep -rni csrf backend frontend` solo devuelve comentarios/docs que *hablan de* CSRF,
    ningún código). La premisa J1/J4 sigue vigente sin corrección.

11. **`backend/app/main.py` construye la pila de middleware en un orden que importa menos de lo
    que parece — verificado contra el código instalado de Starlette, no asumido.**
    `Starlette.add_middleware` (`starlette/applications.py:98-101`) hace
    `self.user_middleware.insert(0, ...)`, y `build_middleware_stack`
    (`starlette/applications.py:57-77`) envuelve la pila en `reversed(middleware)` — el efecto
    neto es que la **última** llamada a `app.add_middleware(...)` en el código termina siendo
    la más **externa** en tiempo de ejecución. Con el orden actual de `main.py` (CORS línea
    140-147, `security_headers_middleware` línea 149-152, `request_id_middleware` línea 154-157),
    la cadena real es `request_id → security_headers → CORS → ExceptionMiddleware/rutas`. El
    middleware CSRF nuevo (Decisión B5) exime explícitamente `OPTIONS`/`GET`/`HEAD` en su propio
    cuerpo, así que su posición relativa a `CORSMiddleware` no es crítica — se agrega como una
    cuarta llamada, después de las tres existentes, sin que eso implique una dependencia de
    orden real distinta a esa exención explícita.

12. **`app/core/exceptions.py` (`DomainError` + handler en `main.py:160-166`) es el patrón
    correcto para errores de *ruta* (algo que un endpoint decide dentro de su propio cuerpo),
    no para el rechazo CSRF, que tiene que ocurrir en middleware, antes de que cualquier
    dependencia de ruta corra.** No se reusa `DomainError` para el rechazo CSRF — el middleware
    devuelve un `JSONResponse(status_code=403, ...)` directo, mismo estilo que ya usan
    `security_headers_middleware`/`request_id_middleware` (funciones `async def (request,
    call_next)` registradas vía `app.add_middleware(BaseHTTPMiddleware, dispatch=...)`) — no una
    excepción nueva de dominio para un problema que no es de dominio.

13. **`backend/tests/conftest.py` usa `TestClient` sobre `httpx` (`fastapi==0.136.3`,
    `httpx==0.28.1`, confirmado en `backend/requirements.txt`), que mantiene un cookie-jar real
    por instancia de cliente** — un test que hace `client.post("/api/v1/auth/login", ...)` y
    luego una segunda request con el mismo `client` ya arrastra automáticamente cualquier
    `Set-Cookie` de la primera respuesta, sin código adicional. Esto simplifica mucho los tests
    nuevos de cookies (Decisión T1-T4) — no hace falta simular un navegador a mano.

14. **`backend/tests/test_api_keys.py::TestAutenticacionConApiKey`
    (líneas 69-87) ya tiene la forma exacta que pide J7/la Decisión B4: una clase con tests de
    "la API key autentica", "una key inválida da 401", "el JWT por header sigue funcionando como
    regresión".** El test nuevo de esta fase (ninguna cookie presente, solo header
    `Authorization: Bearer oikos_pat_...`, debe seguir autenticando) se agrega ahí mismo como un
    cuarto test de esa clase, no como un archivo nuevo (Decisión T3).

---

## Decisiones de arquitectura

Nomenclatura: se conserva la numeración J1/J2/... de `fase_25_spec.md` §25.5 donde la decisión
original sigue vigente sin cambios de fondo (se cita, no se repite en detalle); las decisiones
nuevas o corregidas por esta spec usan **B** (Backend) y **F** (Frontend), numeradas por área
para que cada ítem sea evidentemente asignable a un agente `backend-engineer` o
`frontend-engineer` distinto. **Donde una decisión de un lado depende de un nombre/valor exacto
del otro lado, se marca explícitamente "⚠️ contrato compartido con [B/F]N" — ningún ingeniero
debería asumir un nombre de cookie/header sin mirar esa marca.**

### Backend

**B1 — Nuevo módulo `app/core/auth_cookies.py`: dos funciones puras, sin estado propio, mismo
estilo que `app/services/ledger.py` (Fase 25 §25.1) y `app/core/exceptions.py` (Fase 25 §25.3)
— evita repetir el copy-paste de tres bloques que Hallazgo 5 señala.**

```python
# backend/app/core/auth_cookies.py
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
- refresh_token: HttpOnly, Path=/api/v1/auth/refresh,      Max-Age = 30 días.
- csrf_token:    NO HttpOnly (el frontend lo lee por JS),  Path=/,  mismo Max-Age que refresh_token.

`Secure` y `SameSite` son iguales para los tres — ver COOKIE_SECURE en security.py
(Decisión B3).
"""

import secrets

from starlette.responses import Response

from app.core import security

CSRF_COOKIE_NAME = "csrf_token"
ACCESS_COOKIE_NAME = "access_token"
REFRESH_COOKIE_NAME = "refresh_token"
REFRESH_COOKIE_PATH = "/api/v1/auth/refresh"


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
```

**B2 — Paths explícitos, no default implícito, aunque Hallazgo 4 confirma que el default de
Starlette (`path="/"`) ya es seguro para `access_token`/`csrf_token`.** Se pasan igual por
legibilidad y para que quede claro en el código, sin depender de memorizar el default de una
librería externa. `refresh_token` sí necesita su `Path` angosto a propósito (Decisión J2
original, sigue vigente): minimiza cuántas requests llevan el cookie de mayor privilegio
(30 días vs 15 min).

**B3 — `COOKIE_SECURE`, variable de entorno nueva en `backend/app/core/security.py`, no un
valor fijo — corrige J2 (Hallazgo 8), y su default cambia a `true` tras la Decisión B10
(resolución del 2026-09-19, ver Hallazgo 9).**

```python
# backend/app/core/security.py — agregar junto a las demás env vars (después de GOOGLE_CLIENT_ID)

# Flag de cookies (Fase 26). Default True: el acceso de producción se consolida en el dominio
# HTTPS de Tailscale Funnel (Decisión B10, docs/specs/fase_26_spec.md) — un cookie Secure=True
# nunca se envía a un origen http://, así que este flag solo necesita bajar a False en entornos
# que sirven HTTP plano a propósito (docker-compose.dev.yml, desarrollo local sin Funnel).
# Mismo patrón que ENABLE_TAILSCALE_CORS (Fase 7 §3.3): un flag de entorno, no una rama de
# código nueva, para no hardcodear una topología de red específica de este despliegue.
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true").lower() == "true"
```

`docker-compose.yml` (producción) gana una línea nueva en `backend.environment`:
`COOKIE_SECURE: ${COOKIE_SECURE:-true}`. `docker-compose.dev.yml` la fija explícita en `false`
(desarrollo local sirve HTTP plano por diseño) — mismo estilo que `ENABLE_TAILSCALE_CORS` ya
fijo en el compose de este despliegue. Ver Decisión B10 para el resto del cambio de
configuración que esto presupone (sin B10, este default rompería el login del 100% del acceso
actual por IP de Tailscale).

**B4 — `get_current_user` gana el fallback de cookie, pero requiere dos cambios de firma, no
uno (corrige la lectura literal de J3 — Hallazgo 1).**

```python
# backend/app/core/security.py

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)  # 🆕 Fase 26


def get_current_user(
    request: Request,  # 🆕 Fase 26 — necesario para leer el cookie de fallback
    token: str | None = Depends(oauth2_scheme),  # 🆕 ahora puede ser None
    db: Session = Depends(get_db),
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # 🆕 Fase 26 (Decisión B4): el header Authorization sigue siendo el camino primario —
    # clientes no-browser (curl, Shortcuts de iOS con oikos_pat_, un futuro cliente API) no
    # cambian nada. El cookie es un fallback que solo se consulta si no vino header, nunca al
    # revés — no hay ninguna rama nueva que toque el camino de API key.
    if token is None:
        token = request.cookies.get(auth_cookies.ACCESS_COOKIE_NAME)
    if token is None:
        raise credentials_exception

    if token.startswith(API_KEY_PREFIX):
        return _get_user_from_api_key(token, db, credentials_exception)

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception from None

    user = db.query(models.User).filter(models.User.id == int(user_id)).first()
    if user is None:
        raise credentials_exception

    return user
```

Import nuevo: `from fastapi import Request` (falta hoy en `security.py`) y
`from app.core import auth_cookies` — riesgo de import circular verificado como inexistente:
`auth_cookies.py` importa de `app.core.security` (para `COOKIE_SECURE`/TTLs), así que
`security.py` no puede importar `auth_cookies` a nivel de módulo sin crear un ciclo. Se
resuelve con las constantes de nombre de cookie duplicadas como strings literales en
`security.py` (`"access_token"`) en vez de importar `auth_cookies.ACCESS_COOKIE_NAME` — dos
constantes de módulos distintos que deben coincidir por convención, documentado con un
comentario cruzado en ambos archivos (alternativa: mover las constantes de nombre a
`security.py` y que `auth_cookies.py` las importe de ahí — igual de válido; se deja como
detalle de implementación menor, no una decisión de arquitectura).

**B5 — CSRF: middleware nuevo `app/core/csrf.py`, patrón *double-submit cookie* (J4 sigue
vigente sin cambios de fondo), pero con el alcance de exención hecho explícito — J4 no lo
precisaba.**

```python
# backend/app/core/csrf.py
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
```

Wiring en `main.py` (después de las tres llamadas existentes a `app.add_middleware`, línea
~157 — ver Hallazgo 11 sobre por qué el orden relativo a `CORSMiddleware` no es crítico acá):

```python
from app.core.csrf import csrf_protection_middleware  # 🆕 Fase 26

# ... (CORS, security_headers, request_id sin cambios) ...

app.add_middleware(
    BaseHTTPMiddleware,
    dispatch=csrf_protection_middleware,
)  # 🆕 Fase 26 (Decisión B5)
```

⚠️ **Contrato compartido con F1**: el nombre del header es `X-CSRF-Token`
(`csrf.CSRF_HEADER_NAME`) y el nombre del cookie legible por JS es `csrf_token`
(`auth_cookies.CSRF_COOKIE_NAME`) — si `lib/api.ts` lee un nombre de cookie distinto o manda un
header con otro nombre, todo mutation request autenticada por cookie empieza a devolver `403`.

**B6 — `login`, `login_google`, `refresh` (`app/api/auth.py`) ganan un parámetro
`response: Response` y llaman a `auth_cookies.establecer_cookies_de_sesion(...)` antes del
`return`, sin tocar el `response_model=schemas.TokenResponse` ni el body devuelto — J2's
decisión de mantener el body por compatibilidad con clientes no-browser sigue vigente.**

```python
# backend/app/api/auth.py — login(), fragmento final (mismo patrón en login_google y refresh)

from starlette.responses import Response  # 🆕 Fase 26
from app.core import auth_cookies  # 🆕 Fase 26

@router.post("/login", response_model=schemas.TokenResponse)
@limiter.limit("5/minute")
def login(
    request: Request,
    response: Response,  # 🆕 Fase 26
    user_credentials: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    ...  # sin cambios hasta la emisión de tokens

    csrf_token = auth_cookies.generar_csrf_token()
    auth_cookies.establecer_cookies_de_sesion(
        response, access_token=access_token, refresh_token=raw_refresh, csrf_token=csrf_token
    )

    return {
        "access_token": access_token,
        "refresh_token": raw_refresh,
        "token_type": "bearer",
    }
```

**B7 — `logout` (`app/api/auth.py:184-203`) lee el refresh token del cookie primero, cae al
body si no hay cookie (compatibilidad no-browser), y siempre limpia los tres cookies.**

```python
@router.post("/logout")
def logout(
    response: Response,  # 🆕 Fase 26
    request: Request,  # 🆕 Fase 26
    body: schemas.LogoutRequest | None = None,  # 🆕 Fase 26 — ahora opcional
    db: Session = Depends(get_db),
):
    raw_refresh = request.cookies.get(auth_cookies.REFRESH_COOKIE_NAME) or (
        body.refresh_token if body else None
    )
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
```

`schemas.LogoutRequest` (`backend/app/schemas/auth.py:19-20`) no cambia de forma — solo pasa a
ser un body opcional en la firma del endpoint, no un schema opcional.

**B8 — `eliminar_cuenta_propia` (`backend/app/api/users.py:139-160`) gana `response: Response`
y llama a `auth_cookies.limpiar_cookies_de_sesion(response)` justo antes del `return` implícito
de `204`** (Hallazgo 6 — ítem que J1–J8 no cubría). Sin cambios en la lógica de borrado ni en
`delete_user_cascade`.

**B9 — Corte limpio, no ventana de transición dual localStorage+cookie — responde la pregunta
que el enunciado de esta spec deja explícitamente abierta.** El backend YA soporta ambos
caminos de forma permanente (header primero, cookie de fallback — Decisión B4), pero eso es
para clientes no-browser, no una ventana de migración. El frontend (Decisión F1) corta
limpio: en el mismo commit que agrega `withCredentials`, deja de leer/escribir
`localStorage` para JWT — no hay una fase intermedia donde el frontend mande *ambos*.
Justificación, con evidencia del propio repo:
- Solo hay 2 usuarios reales (`alejomaringomez2004@gmail.com` vía Google + la cuenta de
  pruebas) — el costo de "todos tienen que volver a loguearse una vez tras el deploy" es
  literalmente 2 personas, no una campaña de usuarios.
- El despliegue es `docker compose up -d --build` de frontend+backend juntos (mismo comando,
  mismo momento) — no hay releases independientes de frontend/backend que puedan quedar
  desincronizados a mitad de camino, a diferencia de un mobile app con rollout gradual.
- Mantener un modo dual (frontend leyendo `localStorage` Y confiando en cookies a la vez)
  multiplica la superficie de la migración de auth más riesgosa del proyecto (ver Decisión J1
  original) sin ningún beneficio real dado el punto anterior — es el mismo criterio que ya usó
  Fase 21 (borrar usuarios de prueba en vez de migrarlos) y Fase 23 (anular el password
  plantado en vez de tratar de "reconciliarlo").
- Consecuencia operativa a anunciar en el commit/PR: el primer deploy de esta fase desloguea a
  las 2 cuentas reales una vez. No hace falta backfill de datos ni migración de sesiones.

**B10 — Consolidar el acceso de producción en un único origen HTTPS vía Tailscale Funnel —
resuelve Hallazgo 9, decisión tomada con el usuario el 2026-09-19 en vez de dejarse como
limitación conocida.** Cambia tres defaults en `docker-compose.yml` (producción; NO
`docker-compose.dev.yml`, que sigue sirviendo HTTP local a propósito):

```yaml
# docker-compose.yml — backend.environment
ALLOWED_ORIGINS: ${ALLOWED_ORIGINS:-http://localhost:3000,https://alejo-yoga-6-13alc6.tail44159c.ts.net}
COOKIE_SECURE: ${COOKIE_SECURE:-true}   # ya cubierto por Decisión B3

# docker-compose.yml — frontend.build.args
NEXT_PUBLIC_API_URL: ${NEXT_PUBLIC_API_URL:-https://alejo-yoga-6-13alc6.tail44159c.ts.net}
```

Con esto, la request del navegador a la API pasa de `http://100.76.235.30:8000` (IP directa,
otro origen, HTTP plano) a `https://alejo-yoga-6-13alc6.tail44159c.ts.net/api/v1/...` — que
Funnel reenvía a `http://127.0.0.1:8000/api/v1/...` (Hallazgo 9). El frontend queda servido
por el **mismo origen** (mismo esquema+host+puerto: HTTPS, sin puerto explícito) que la API, lo
que de hecho **simplifica** el resto del diseño: esa request ya no es cross-origin en absoluto,
así que ni `CORSMiddleware` ni el `SameSite` del cookie tienen que resolver nada para el camino
principal — `SameSite=Lax` (Decisión J2/B1) sigue siendo la elección correcta igual, ahora por
redundancia con la política del navegador, no como único mecanismo.

*Local IP directa (`http://100.76.235.30:3000`, sin pasar por Funnel) queda oficialmente
deprecada para login por cookie* — con `COOKIE_SECURE=true`, un cookie `Secure` no se envía
nunca a ese origen `http://`, así que un usuario que entre por la IP directa no podría loguear
por cookie (sí puede seguir entrando por Funnel desde cualquier dispositivo del tailnet, no
solo desde internet público — Funnel no le saca acceso a los miembros del tailnet, solo lo
agrega desde afuera). El camino de API key (`Authorization: Bearer oikos_pat_...`, Atajos de
iOS) no usa cookies en absoluto y sigue funcionando contra cualquier origen, IP incluida — sin
cambios (Decisión B4/J7).

*Alternativa descartada: mantener `COOKIE_SECURE=false` y aceptar el acceso HTTP-IP
indefinidamente junto al HTTPS-Funnel.* Es la opción de menor esfuerzo inmediato, pero deja el
cookie de sesión viajando sin cifrado en un camino que el proyecto sigue anunciando como
soportado — exactamente el tipo de compromiso de seguridad que esta fase migra *lejos de*
(salir de `localStorage`) sin terminar de resolverlo. El usuario pidió explícitamente resolver
esto "de una vez, que quede bien a largo plazo" en vez de dejarlo como deuda técnica nueva.

### Frontend

**F1 — `frontend/lib/api.ts`: reescritura del archivo completo, no un parche — corrige J5 con
el detalle que Hallazgo 2/3 encontraron.**

```typescript
// frontend/lib/api.ts
import axios from 'axios';

export const api = axios.create({
  baseURL: `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1`,
  withCredentials: true, // 🆕 Fase 26 — manda/recibe los cookies httpOnly de sesión
});

// 🆕 Fase 26: lee el cookie NO-httpOnly csrf_token (Decisión B1/B5 del backend — mismo
// nombre, contrato compartido) para el patrón double-submit. No hay librería de cookies en
// el proyecto todavía; un regex sobre document.cookie alcanza para un solo valor.
function leerCsrfTokenDeCookie(): string | null {
  if (typeof document === 'undefined') return null;
  const match = document.cookie.match(/(?:^|; )csrf_token=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}

let isRefreshing = false;
let failedQueue: Array<{ resolve: () => void; reject: (error: unknown) => void }> = [];

function processQueue(error: unknown) {
  failedQueue.forEach(({ resolve, reject }) => (error ? reject(error) : resolve()));
  failedQueue = [];
}

// 🆕 Fase 26: reemplaza al interceptor de Authorization — ya no arma el header del JWT
// (el cookie viaja solo), solo agrega X-CSRF-Token en mutaciones.
api.interceptors.request.use((config) => {
  const metodo = (config.method || 'get').toUpperCase();
  if (metodo !== 'GET' && metodo !== 'HEAD') {
    const csrfToken = leerCsrfTokenDeCookie();
    if (csrfToken) config.headers['X-CSRF-Token'] = csrfToken;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        return new Promise<void>((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        }).then(() => api(originalRequest));
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        // 🆕 Fase 26 (Hallazgo 3): usa `api`, no `axios` crudo — si no, withCredentials
        // no aplica y el cookie refresh_token nunca viaja acá.
        await api.post('auth/refresh');
        processQueue(null);
        return api(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError);
        window.location.href = '/login';
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  }
);
```

`POST /api/v1/auth/refresh` deja de necesitar body (`schemas.RefreshRequest` en el backend
puede quedar como está — el cookie es la fuente primaria; ver Decisión B9 sobre por qué no hay
modo dual — el body queda para clientes no-browser exactamente como `LogoutRequest`, pero el
frontend ya no lo manda).

⚠️ **Contrato compartido con B1/B5**: nombre de cookie `csrf_token`, nombre de header
`X-CSRF-Token` — deben coincidir carácter por carácter con `auth_cookies.CSRF_COOKIE_NAME` /
`csrf.CSRF_HEADER_NAME`.

**F2 — Módulo nuevo `frontend/lib/authSession.ts`: reemplaza los 3 sitios de "lectura de
presencia" (Hallazgo 2) por una sola función, reusando el cookie CSRF con un segundo propósito
explícito — no una decisión implícita.**

```typescript
// frontend/lib/authSession.ts
/**
 * Fase 26: con cookies httpOnly, JS ya no puede leer el JWT — pero sí puede leer el cookie
 * csrf_token (no-httpOnly a propósito, ver backend/app/core/auth_cookies.py), que el backend
 * setea/limpia exactamente cuando hay/no-hay sesión. Se reusa como señal de "¿hay sesión
 * activa?" para UX (mostrar/ocultar, activar una query) — NO es un chequeo de seguridad: la
 * fuente de verdad sigue siendo el 401 real del backend en cada request (igual que hoy).
 */
export function haySesionActiva(): boolean {
  if (typeof document === 'undefined') return false;
  return /(?:^|; )csrf_token=/.test(document.cookie);
}
```

Reemplaza:
- `frontend/lib/hooks/useRequireAuth.ts:13` — `const token = localStorage.getItem('jwt_token')`
  → `if (!haySesionActiva()) router.replace('/login')`. Sigue siendo un guard de UX (evita el
  flash de contenido protegido antes de redirigir), no de seguridad — igual que hoy: un
  `localStorage` falseado tampoco daba acceso real, la aplicación real la sigue haciendo el
  401 de cada request.
- `frontend/lib/hooks/useUserPreferences.ts:14` — `hasToken` pasa a ser
  `haySesionActiva()`.
- `frontend/components/ThemeToggle.tsx:79` — mismo reemplazo directo.

**F3 — `login/page.tsx:73-74`, `register/page.tsx:69-70`, `GoogleAuthButton.tsx:45-46`: se
borran las 3 líneas de `localStorage.setItem`, sin reemplazo — el `Set-Cookie` de la respuesta
ya dejó la sesión lista.** El resto de cada función (redirigir según
`has_transaction_history`, etc.) no cambia. `response.data.access_token`/`refresh_token`
siguen llegando en el body (Decisión B6) pero el frontend ya no los toca — quedan sin usar en
esos 3 call sites (no hace falta destructurarlos si no se usan).

**F4 — Logout y baja de cuenta: se borra la lectura/limpieza manual de `localStorage`.**
- `frontend/components/Sidebar.tsx:50-61` (`handleLogout`): ya no necesita leer
  `refresh_token` para armar el body — `api.post('auth/logout')` sin body alcanza (el cookie
  lo manda solo). Se borran las líneas 51 (lectura) y 59-60 (`removeItem`); el resto
  (`queryClient.clear()`, `router.push('/login')`) no cambia.
- `frontend/app/(dashboard)/settings/page.tsx:117-118` (`onSuccess` de `deleteAccount`): se
  borran las dos líneas de `removeItem` — el backend ya limpia los cookies en la misma
  respuesta de `DELETE /users/me` (Decisión B8). `queryClient.clear()` y el resto del bloque
  no cambian.

**F5 — Nada de esto requiere tocar `QueryProvider`, `useCurrentUser`, ni ningún componente que
ya use `useQuery`/`api.get(...)` — todos siguen funcionando igual porque el cambio real
(cookies en vez de header) vive enteramente dentro de `lib/api.ts` para el 100% de las
requests de datos.** Confirmado leyendo `frontend/lib/hooks/useCurrentUser.ts` (usa `api.get`
sin ningún manejo de token propio) — no hay ningún otro call site que arme
`Authorization: Bearer` a mano fuera de `lib/api.ts` (`grep -rn "Authorization" frontend` no
devuelve nada más).

**F6 — `NEXT_PUBLIC_API_URL` (build arg del frontend, `docker-compose.yml`) cambia de default
— ⚠️ contrato compartido con B10, mismo valor exacto, coordinar en el mismo PR.** Solo cambia
el *valor por defecto* de la variable de entorno de build; `frontend/lib/api.ts` ya construye
`baseURL` como `` `${NEXT_PUBLIC_API_URL}/api/v1` `` (CLAUDE.md, sin cambios en esa línea por
este ítem — F1 la reescribe por otros motivos, no por esto). El plumbing de Docker que propaga
este build arg al frontend ya existe desde Fase 20 (CLAUDE.md: "el plumbing de Docker ya las
propaga") — no hace falta tocar `frontend/Dockerfile`. Sin este cambio, F1 (`withCredentials:
true`) no alcanza: el navegador seguiría pidiendo la API a un origen `http://` distinto,
contenido mixto bloqueado antes de que cualquier cookie viaje (Hallazgo 9).

---

## Decisiones de testing

**T1 — Backend, nuevos tests en `backend/tests/test_auth.py`, clase `TestCookiesDeSesion`
(nueva), aprovechando el cookie-jar real de `TestClient` (Hallazgo 13) — no hace falta simular
un navegador.**
- `test_login_sets_httponly_access_and_refresh_cookies` — login vía `client.post(...)`,
  inspecciona `response.cookies` (o `client.cookies` tras la request) por los 3 nombres, y
  verifica que el cookie jar del propio `TestClient` los adoptó.
- `test_refresh_rotates_cookie_without_body` — login, luego `client.post("/api/v1/auth/
  refresh")` **sin** body, confía en que el cookie-jar del cliente ya trae `refresh_token`
  (httpx lo hace solo) — 200, nuevo `access_token` distinto en cookie.
- `test_protected_route_authenticates_via_cookie_without_header` — login, luego
  `client.get("/api/v1/users/me")` sin pasar `headers=` a mano (el cookie viaja solo) → 200.
- `test_logout_clears_all_three_cookies` — verifica `Set-Cookie` con `Max-Age=0` (o
  equivalente) para los 3 nombres tras logout.
- `test_delete_account_clears_cookies` — cubre Hallazgo 6/Decisión B8: login, `DELETE /users/
  me`, verifica limpieza de cookies en esa misma respuesta.

**T2 — Backend, nuevos tests en un archivo nuevo `backend/tests/test_csrf.py` — cubre B5.**
- `test_mutation_via_cookie_without_csrf_header_returns_403`.
- `test_mutation_via_cookie_with_mismatched_csrf_header_returns_403`.
- `test_mutation_via_cookie_with_matching_csrf_header_succeeds`.
- `test_mutation_via_jwt_header_without_any_cookie_is_exempt` — regresión directa del
  Hallazgo 10/Decisión B5 (clientes header-only, ej. un test de integración externo, no
  deberían necesitar simular CSRF).
- `test_get_request_never_requires_csrf_header` — método seguro, exento sin importar cookies.

**T3 — Backend, un test agregado a la clase ya existente
`backend/tests/test_api_keys.py::TestAutenticacionConApiKey` (Hallazgo 14), no un archivo
nuevo — cierra J7 explícitamente:**

```python
def test_api_key_still_authenticates_with_no_cookie_present(self, client, test_user):
    """Regresión directa contra el Hallazgo 10 de docs/specs/fase_26_spec.md — el camino
    de API key (Shortcuts de iOS reales) no debe depender de ningún cookie."""
    creada = _crear_api_key(client, test_user["headers"])
    headers = {"Authorization": f"Bearer {creada['key']}"}
    response = client.get("/api/v1/users/me", headers=headers)
    assert response.status_code == 200, response.text
    # Ningún cookie de sesión debería haberse seteado por esta request.
    assert "access_token" not in response.cookies
```

**T4 — Frontend: sin suite de tests automatizada — `docs/TODO.md` confirma que no existe
ninguna (Vitest/RTL fuera de alcance, marcado "solo si el proyecto crece").** Esta spec NO
amplía el alcance para agregar una — sería una expansión de alcance no pedida y
desproporcionada para un cambio que ya de por sí es el de mayor riesgo del proyecto (Decisión
J1 original). Verificación **manual** obligatoria antes de dar por cerrada la fase, checklist
mínimo:
- Login con contraseña → cookies visibles en DevTools (`access_token`/`refresh_token`
  `HttpOnly` tildado, `csrf_token` no) → refrescar la página → sigue logueado.
- Esperar >15 min (o adelantar el reloj del sistema/backend en un entorno de prueba) →
  cualquier request dispara el refresh automático sin loguear de nuevo.
- Logout → cookies desaparecen de DevTools → refrescar `/dashboard` → redirige a `/login`.
- Borrar cuenta (`settings`) → cookies desaparecen → redirige a `/login`.
- Login con Google → mismo comportamiento que login con contraseña.
- Crear una transacción (mutación real, no solo login) → confirma que `X-CSRF-Token` viaja y
  no rebota con 403.
- Un Atajo de iOS real (o un `curl -H "Authorization: Bearer oikos_pat_..."`) sigue
  funcionando sin ningún cookie — regresión manual de B4/J7 fuera del navegador.

---

## Orden de ejecución recomendado

```
1. Backend: app/core/auth_cookies.py + app/core/security.py (COOKIE_SECURE, oauth2_scheme
   auto_error=False, get_current_user con fallback de cookie) — Decisiones B1, B3, B4.
   ── Primero porque B5/B6/B7/B8 importan de auth_cookies.py; sin este paso no hay nada
      que "wirear" en los endpoints.

2. Backend: app/core/csrf.py + wiring en main.py — Decisión B5.
   ── Depende de (1) solo por el import de los nombres de cookie (auth_cookies.py). Puede
      ir en un commit separado inmediatamente después de (1).

3. Backend: auth.py (login/login_google/refresh/logout) + users.py (eliminar_cuenta_propia)
   — Decisiones B6, B7, B8.
   ── Depende de (1) (auth_cookies) y, para que los tests de CSRF de T2 tengan sentido,
      idealmente de (2) ya wireado — pero el código de estos endpoints no importa nada de
      csrf.py directamente, así que (3) podría empezar en paralelo con (2) si hace falta.

4. Backend: tests T1-T3.
   ── Depende de (1)-(3) completos — son tests de integración HTTP contra el comportamiento
      real, no se pueden escribir en paralelo sin el código que ejercitan.

5. Frontend: lib/api.ts (F1) + lib/authSession.ts (F2).
   ── Independiente del backend en el sentido de "no comparte archivos", pero
      FUNCIONALMENTE no se puede verificar manualmente (T4) sin que el backend de (1)-(3)
      ya esté corriendo — recomendado empezar el código en paralelo con el backend, pero
      NO mergear/deployar antes de que (1)-(3) estén en la misma rama.

6. Frontend: los 5 call sites de F3/F4 (login, register, GoogleAuthButton, Sidebar,
   settings) — depende de (5) solo por convención de "no tocar el mismo archivo de auth dos
   veces por separado", no por una dependencia de código real.

7. Verificación manual end-to-end (T4) — depende de TODO lo anterior desplegado junto
   (backend + frontend en el mismo `docker compose up --build`, consistente con la Decisión
   B9 de corte limpio sin ventana de transición).

8. Docs: backend/docs/API_REFERENCE.md, frontend/docs/API_CONTRACT.md, backend/docs/
   BUSINESS_RULES.md (si corresponde) — actualizar la sección de autenticación para
   documentar los 3 cookies + el header X-CSRF-Token, por la convención de CLAUDE.md
   ("si cambiás un contrato de API compartido, actualizá ambos docs en el mismo cambio").
   No es opcional — el contrato de auth cambia de fondo aunque el JSON body de
   TokenResponse no cambie de forma.

9. Infra: `docker-compose.yml`/`.env` — `ALLOWED_ORIGINS`, `COOKIE_SECURE`,
   `NEXT_PUBLIC_API_URL` (Decisiones B10, F6). No depende de código — puede aplicarse en
   cualquier momento — pero tiene que estar aplicado ANTES de (7), porque la verificación
   manual end-to-end solo tiene sentido accediendo vía el dominio de Funnel una vez que
   `COOKIE_SECURE=true` es el default real.
```

A diferencia del "no ejecutar en paralelo con nada" que recomendaba Fase 25 para este mismo
ítem (Decisión J1 original), esta fase SÍ tiene paralelismo interno real entre (1)-(4)
backend y (5)-(6) frontend — la recomendación de Fase 25 era sobre no mezclar esto con los
otros 6 ítems de esa fase, no sobre que este ítem en sí mismo sea estrictamente secuencial.

---

## Resumen de archivos tocados

| Decisión | Backend | Frontend |
|---|---|---|
| B1/B2/B3 cookies + flags | `app/core/auth_cookies.py` (nuevo), `app/core/security.py` (COOKIE_SECURE) | — |
| B4 fallback de cookie en auth | `app/core/security.py` (`get_current_user`, `oauth2_scheme`) | — |
| B5 CSRF | `app/core/csrf.py` (nuevo), `main.py` (wiring) | — |
| B6 emisión de cookies | `app/api/auth.py` (`login`, `login_google`, `refresh`) | — |
| B7 logout | `app/api/auth.py` (`logout`), `app/schemas/auth.py` (`LogoutRequest` pasa a opcional en la firma, no en el schema) | — |
| B8 baja de cuenta | `app/api/users.py` (`eliminar_cuenta_propia`) | — |
| F1 cliente HTTP | — | `lib/api.ts` (reescritura completa) |
| F2 señal de sesión | — | `lib/authSession.ts` (nuevo) |
| F3 login/registro/Google | — | `app/(auth)/login/page.tsx`, `app/(auth)/register/page.tsx`, `components/auth/GoogleAuthButton.tsx` |
| F4 logout/baja de cuenta | — | `components/Sidebar.tsx`, `app/(dashboard)/settings/page.tsx` |
| F5 sin cambios (confirmación) | — | `lib/hooks/useCurrentUser.ts` y todo el resto de `useQuery`/`api.get` — sin tocar |
| Testing | `tests/test_auth.py` (clase nueva), `tests/test_csrf.py` (nuevo), `tests/test_api_keys.py` (1 test agregado) | Ninguno automatizado — checklist manual (T4) |
| B10/F6 infra (origen único HTTPS) | `docker-compose.yml` (`ALLOWED_ORIGINS`, `COOKIE_SECURE` defaults) | `docker-compose.yml` (`NEXT_PUBLIC_API_URL` build arg default) |
| Docs | `backend/docs/API_REFERENCE.md`, `backend/docs/BUSINESS_RULES.md` (si aplica) | `frontend/docs/API_CONTRACT.md` |

---

## Out of scope

- **El flujo de Google Identity Services en sí (`GoogleAuthButton.tsx`, el ID token, la
  verificación `verify_oauth2_token`)** — J8 sigue vigente sin cambios: lo único que cambia en
  ese componente es qué hace con la respuesta de `POST /auth/google` (dejar de escribir
  `localStorage`, Decisión F3), no el flujo de GIS en sí.
- **Suite de tests de frontend (Vitest/React Testing Library)** — confirmado fuera de alcance
  por `docs/TODO.md` (Decisión T4); no se agrega como parte de esta fase aunque sería la
  primera vez que un cambio de esta superficie no tiene ningún test automatizado del lado
  frontend que lo respalde. Riesgo aceptado explícitamente, no ignorado.
- **Rate limiting distribuido** — sigue fuera de alcance por las mismas razones que
  `docs/ROADMAP.md` ya documenta (single-worker); sin relación con esta fase.
- **Scopes/TTL obligatorio de API keys** — mencionados en `docs/TODO.md` como mejoras futuras
  de un mecanismo que esta fase deliberadamente no toca (B4 lo deja intacto).
- **Migrar `RefreshRequest`/`LogoutRequest` a schemas completamente opcionales o eliminarlos**
  — quedan como están (el body sigue siendo válido para clientes no-browser); solo cambia que
  la firma del endpoint ya no los exige.

---

## Decisiones resueltas con el usuario (2026-09-19)

Las dos preguntas que la primera versión de esta spec dejaba abiertas se resolvieron con el
usuario el mismo día, verificando el estado real del host de despliegue en vez de asumirlo:

1. **¿Funnel enruta frontend y backend bajo el mismo dominio?** Sí — confirmado corriendo
   `tailscale funnel status` directo en el host (Hallazgo 9): `/` → frontend, `/api` → backend.
   Encontró además un problema real no cubierto por J1–J8: el frontend sigue apuntando su
   `NEXT_PUBLIC_API_URL` a la IP de Tailscale en HTTP plano, no al dominio de Funnel — contenido
   mixto, bloqueado por el navegador.
2. **¿El despliegue sigue siendo HTTP plano?** Sí para el acceso por IP directa; el dominio de
   Funnel ya es HTTPS real. El usuario pidió resolver esto "de una vez, que quede bien a largo
   plazo" en vez de dejarlo como deuda — se decidió consolidar el acceso de producción en el
   dominio HTTPS de Funnel como único origen soportado para login por cookie (Decisión B10/F6),
   con `COOKIE_SECURE=true` por default (Decisión B3 actualizada). El acceso por IP directa vía
   navegador queda deprecado para sesión (no para API keys, que no usan cookies — Decisión B4).

---

## Further notes

- Esta spec no repite en detalle las partes de J2/J4/J8 que siguieron vigentes sin corrección
  (flags de cookie de alto nivel, patrón double-submit, alcance de la migración) — se citan
  como decisión heredada y se listan solo las correcciones/precisiones nuevas (Hallazgos 1-14).
- El hallazgo con más impacto práctico no es ninguno de los ocho puntos J1-J8 originales, sino
  uno que J1-J8 no cubría en absoluto: los 8 archivos de frontend que leen/escriben
  `jwt_token`/`refresh_token` de `localStorage` fuera de `lib/api.ts` (Hallazgo 2) — sin este
  hallazgo, la implementación de esta fase habría dejado 5 rutas de UI rotas (dos formularios
  de login que siguen "guardando" un token que nunca se usa, dos guards de sesión que nunca
  detectan una sesión de cookie, y un logout que manda un `refresh_token` vacío en el body).
- Ningún archivo del repositorio fuera de `docs/specs/fase_26_spec.md` (y el pointer en
  `docs/ROADMAP.md`) fue modificado al producir este documento — sigue siendo, en su
  totalidad, un documento de planificación.
- **Actualización 2026-09-19, mismo día, con el usuario:** la primera versión de esta spec
  dejaba dos preguntas abiertas (topología de Funnel, default de `COOKIE_SECURE`). Se
  resolvieron verificando el host de despliegue real en vivo (`tailscale funnel status`, no
  documentación desactualizada) y se agregaron las Decisiones B10/F6 (consolidar el acceso de
  producción en el dominio HTTPS de Funnel) — ver "Decisiones resueltas con el usuario" arriba.
  El resto del documento (Hallazgos 1-8, 10-14, Decisiones B1-B9, F1-F5, T1-T4) no cambió de
  fondo, solo se ajustaron las referencias cruzadas al Hallazgo 9 y a B3.
