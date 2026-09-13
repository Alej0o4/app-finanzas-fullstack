# Spec — Fase 20 (ítem 3): Login con Google (OAuth)

> Plan de implementación detallado para el ítem pendiente de Fase 20 del
> [ROADMAP](../ROADMAP.md) (sección "Fase 20 — Correos transaccionales con marca + login
> social", líneas 756-791, decidida en sesión de grilling del 2026-09-13). Los otros dos ítems
> de Fase 20 (plantilla de correo con marca, placeholders genéricos de los formularios de auth)
> **ya están implementados** — ver `docs/ROADMAP.md` y las entradas resueltas de 2026-09-13 en
> `docs/TODO.md`. Este documento cubre únicamente el tercer ítem, el que el ROADMAP marca
> explícitamente como "evaluado, no implementado" y "pendiente de spec antes de implementar".
> Este documento no cambia el alcance ya fijado en el ROADMAP — lo desglosa en tareas
> ejecutables, separadas entre backend y frontend, para que `backend-engineer`/`frontend-engineer`
> puedan partir directamente de aquí.
>
> **No implementa nada.** Ningún archivo del repositorio fuera de `docs/specs/fase_20_spec.md`
> fue modificado al producir este documento. Los hallazgos de exploración fueron verificados
> directamente contra `backend/` y `frontend/` el 2026-09-13 (lectura completa de `auth.py`,
> `users.py`, `security.py`, `models.py`, `schemas.py`, `requirements.txt`, `docs/TODO.md`,
> `.env.example`, `login/page.tsx`, `register/page.tsx`, `(auth)/layout.tsx`,
> `backend/tests/test_auth.py` + `conftest.py`), no inferidos del texto del ROADMAP. Las
> decisiones de arquitectura más delicadas (P1–P10 abajo) fueron evaluadas por el agente
> `software-architect` a partir de ese mismo código, con cita de línea exacta.

Estado del repo al momento de escribir esto (2026-09-13): Fases 7–19 están completas (más la
parada de correcciones de UX post-pivote), y los dos primeros ítems de Fase 20 ya se enviaron
el mismo día de la sesión de grilling que los decidió. El login con Google fue separado a
propósito del resto de la fase porque, a diferencia de los otros dos ítems (cambios acotados a
una función de renderizado de HTML y a strings de placeholder), toca el modelo de datos de
`User`, el flujo de autenticación completo, y dos superficies de frontend — de ahí que el
ROADMAP pida un spec antes de tocar código, mismo criterio que ya se aplicó a las Fases 17/18/19.

---

## Problem Statement

Hoy, la única forma de crear una cuenta en Oikos es con email + contraseña, y el flujo de
verificación de email depende de que `EMAIL_PROVIDER` esté configurado con credenciales SMTP
reales. `CLAUDE.md` documenta que esto sigue siendo `console` en algunos entornos — sin un
proveedor real, nadie que se registre puede recibir su enlace de verificación, y el gate de
login agregado el 2026-09-12 (`403 EMAIL_NOT_VERIFIED`) lo deja fuera del sistema
indefinidamente. Además, pedirle a un usuario nuevo que invente y recuerde una contraseña más
—cuando ya tiene una cuenta de Google de confianza— es fricción evitable en el onboarding de
3 minutos que Fase 10 ya optimizó.

## Solution

Agregar un botón "Iniciar sesión con Google" a las pantallas de `login` y `register`, que
autentica al usuario contra la identidad ya verificada de su cuenta de Google (vía Google
Identity Services) y usa esa verificación para saltarse por completo el paso de email de
verificación — incluso en un entorno con `EMAIL_PROVIDER=console`. Si el correo de Google ya
existe como cuenta con contraseña en Oikos, se vincula automáticamente en vez de crear una
cuenta duplicada o rechazar el login.

## User Stories

1. Como usuaria nueva sin cuenta en Oikos, quiero poder registrarme con un clic usando mi
   cuenta de Google, para no tener que inventar ni recordar una contraseña nueva.
2. Como usuaria nueva, quiero que mi cuenta quede activa inmediatamente tras iniciar sesión con
   Google, sin tener que revisar mi correo ni esperar un email de verificación que quizás nunca
   llegue.
3. Como usuaria que ya se registró con email/contraseña, quiero poder iniciar sesión con Google
   usando el mismo correo, para no terminar con dos cuentas separadas si un día prefiero esa
   vía.
4. Como usuaria que se registró originalmente con Google, quiero poder volver a iniciar sesión
   con Google en cualquier momento y llegar exactamente a donde llegaría si hubiera usado
   contraseña (dashboard si ya tengo historial, `/capture` si soy nueva).
5. Como usuaria que intenta iniciar sesión con Google mientras el backend no tiene
   `GOOGLE_CLIENT_ID` configurado, quiero no ver un botón roto, para no confundirme pensando que
   la función está disponible cuando no lo está.
6. Como usuaria que intenta iniciar sesión con Google mientras el backend sí tiene el botón
   visible pero la variable de entorno falta del lado del servidor, quiero un mensaje de error
   claro en vez de un 500 sin explicación.
7. Como dueño del proyecto, quiero que crear una cuenta de Google no le dé a nadie acceso a una
   cuenta ajena por email, para no introducir una vulnerabilidad de account takeover.
8. Como dueño del proyecto, quiero que el endpoint de login con Google tenga el mismo rate
   limit que el resto de los endpoints de autenticación anónimos, para no dejar un vector nuevo
   sin protección contra abuso.
9. Como desarrolladora que corre el backend sin Docker, quiero que el registro/login con Google
   sea opcional y no rompa el arranque del backend si `GOOGLE_CLIENT_ID` no está seteado, a
   diferencia de `SECRET_KEY`, que sí es obligatoria.
10. Como desarrolladora que corre la suite de tests, quiero que los tests del login con Google
    no dependan de una llamada de red real a Google, para que seguir corriendo offline contra
    SQLite en memoria (como el resto de la suite) sea posible.
11. Como usuaria que ya tiene una sesión activa por contraseña, quiero que iniciar sesión con
    Google no cree una segunda `Account` por defecto ni duplique mis categorías ocultas, para no
    terminar con datos inconsistentes solo por haber usado un método de login distinto.
12. Como usuaria en el formulario de registro, quiero ver la opción de Google en el mismo lugar
    visual que en el login, para reconocer el patrón sin tener que pensarlo.
13. Como usuaria cuya cuenta de Google no tiene el correo verificado (caso raro, pero que
    Google permite reportar en el token), quiero que el sistema rechace ese login en vez de
    confiar ciegamente en un email no verificado.
14. Como dueño del proyecto, quiero que la respuesta del endpoint nuevo tenga exactamente la
    misma forma (`access_token`/`refresh_token`/`token_type`) que `POST /auth/login`, para que
    el frontend reutilice el mismo código de manejo de tokens sin bifurcar lógica.

## Hallazgos de exploración que corrigen/precisan el ROADMAP

1. **El único bloqueo real para registrarse hoy es exactamente el que Google login evita.**
   `docs/TODO.md` documenta que `EMAIL_PROVIDER=smtp` solo está verificado contra el `.env` real
   de despliegue (gitignored) — correr sin Docker sigue cayendo a `EMAIL_PROVIDER=console` salvo
   que se agreguen esas credenciales también ahí. El login con Google no depende de ese envío en
   absoluto: la verificación de identidad la hace Google, no un correo saliente de Oikos.

2. **No hay ninguna librería OAuth instalada** (confirmado en `backend/requirements.txt`,
   lectura completa de las 63 líneas) — el ROADMAP ya lo señalaba, este documento lo confirma
   contra el archivo real antes de elegir qué agregar (ver Decisión 20.3.2).

3. **`password_hash` no tiene ningún otro punto de lectura que asuma "no-nulo" como señal de
   negocio.** `grep -n "password_hash"` sobre `backend/app/` solo encuentra tres sitios:
   `users.py:56` (creación), `auth.py:27` (verificación en login) y `auth.py:193` (reset). Que
   la columna pase a nullable no rompe ninguna lógica implícita en otro lado — sí requiere un
   guard explícito nuevo en `login()` (ver Decisión 20.3.5), porque `verify_password` de passlib
   lanza excepción sobre un hash `None` en vez de devolver `False`.

4. **El patrón de "cuenta por defecto + categorías ocultas pre-sembradas" vive dentro de
   `crear_usuario()`, no en el modelo `User` ni en un helper compartido** (`users.py:60-81`).
   Cualquier segundo punto de creación de `User` —como el login con Google, cuando el usuario es
   nuevo— tiene que replicar ese mismo efecto secundario o reabre el bug ya documentado en
   `docs/TODO.md`: *"Un usuario nuevo no puede registrar nada"* (0 cuentas → `account_id`
   obligatorio → fallo silencioso en captura). Resuelto en Decisión 20.3.3: se extrae ese bloque
   a un helper compartido.

5. **El botón de Google necesita un client ID en el frontend en build-time, mismo patrón que
   `NEXT_PUBLIC_API_URL`.** No existe `frontend/.env.example` — las variables `NEXT_PUBLIC_*` se
   documentan hoy en el `.env.example` de la raíz (usado por Docker Compose), con el comentario
   explícito de que son build args, no variables de runtime (`.env.example` líneas 20-21). Se
   sigue el mismo patrón para `NEXT_PUBLIC_GOOGLE_CLIENT_ID`.

6. **`(auth)/layout.tsx` es un layout mínimo sin scripts externos** (7 líneas, solo el
   contenedor centrado). El script de Google Identity Services se carga ahí, una sola vez, en
   vez de duplicarlo en `login/page.tsx` y `register/page.tsx` por separado.

7. **`register_and_login` (fixture de test en `conftest.py:105-153`) marca `email_verified=True`
   manualmente para no forzar a cada test a pasar por el flujo real de verificación.** El login
   con Google logra ese mismo estado por un camino real (Google ya verificó el correo), así que
   los tests nuevos de este ítem no necesitan un atajo equivalente — pero sí necesitan mockear
   la llamada de red a Google (ver Decisión de Testing más abajo), que es la pieza que
   `register_and_login` no tiene que resolver.

---

## Decisiones de arquitectura (P1–P10, evaluadas por `software-architect` el 2026-09-13)

Estas preguntas no tenían una respuesta única derivable solo del ROADMAP — requerían leer el
código real y ponderar contra el modelo de autenticación ya existente (JWT + refresh token
opaco, sin cookies ni sesiones de servidor). Se documentan aquí antes del desglose por
backend/frontend porque varias decisiones de implementación dependen de ellas.

- **P1 — Forma del flujo OAuth: Google Identity Services (GIS) del lado del frontend, no un
  flujo de redirect con authorization code del lado del backend.** El modelo de auth actual es
  puro bearer JWT + refresh token opaco en `localStorage`, sin `SessionMiddleware` ni cookies en
  ningún lado (`security.py:49-50`). Un flujo de authorization code exigiría que el backend
  gestione `state` (CSRF), intercambie el código con un client secret, y le devuelva los tokens
  de Oikos al SPA sin cookies — lo que en la práctica significa tokens en la URL de un redirect
  (expuestos en historial del navegador y en logs de acceso, el mismo riesgo que
  `docs/TODO.md` ya rastrea para el JWT en `localStorage`) o un segundo hop con un código
  temporal de un solo uso, infraestructura nueva que este proyecto de un solo worker nunca
  necesitó para nada más. El flujo GIS no tiene redirect: el frontend obtiene un ID token
  firmado directamente del SDK de Google, lo manda por `POST` a un endpoint nuevo, el backend
  verifica la firma contra las claves públicas de Google y emite el JWT/refresh token propio de
  Oikos exactamente como ya hace `login()`. Es una extensión del mismo patrón, sin secretos
  nuevos que proteger ni superficie de CSRF de redirect.

- **P2 — Dependencia: `google-auth`, no `authlib`.** `authlib` está dimensionada para el flujo
  de authorization code que P1 descarta (cliente de token endpoint, manejo de client secret,
  `state`). `google-auth` con `google.oauth2.id_token.verify_oauth2_token()` hace exactamente lo
  necesario: verificar firma/audiencia/emisor de un ID token contra el JWKS de Google y devolver
  los claims (`email`, `email_verified`, `sub`, `name`). Ninguna de las dos está instalada hoy
  (Hallazgo 2) — se agrega solo `google-auth` a `requirements.txt`.

- **P3 — Vinculación de cuentas: auto-link cuando el correo de Google ya existe como cuenta con
  contraseña.** Al hacer login con Google, se busca `User` por email normalizado (mismo criterio
  que `auth.py:21`). Si existe y no tiene `google_id`, se le asigna (y se marca
  `email_verified = True` si no lo estaba) en vez de rechazar el login o crear una cuenta
  duplicada. Esto **no** es una vulnerabilidad de account takeover: el claim `email_verified` de
  un ID token de Google lo emite Google después de haber verificado esa casilla — un atacante no
  puede conseguir que Google firme `email_verified=true` para el correo de otra persona sin
  controlar esa cuenta de Google, y si la controla, ya podría tomar la cuenta de Oikos de todas
  formas vía el flujo existente de "olvidé mi contraseña". Auto-vincular no otorga ninguna
  capacidad que el reset de contraseña por email no otorgara ya.

- **P4 — `email_verified` para cuentas originadas en Google: `True` de inmediato, sin pasar por
  `enviar_email_verificacion()`.** Aplica tanto a un registro nuevo por Google como a la
  vinculación automática de una cuenta con contraseña que todavía no estaba verificada (P3). El
  correo de Google ya satisface la razón de ser del gate agregado el 2026-09-12
  (`auth.py:30-37`). Efecto colateral que vale la pena remarcar: hasta que haya SMTP real
  configurado en todos los entornos que lo necesiten, el login con Google es, en la práctica, la
  **única** vía de registro que funciona de punta a punta en un entorno con
  `EMAIL_PROVIDER=console` — no solo una opción más cómoda.

- **P5 — Cambios de esquema.** `backend/app/models/models.py:23`: `password_hash` pasa de
  `nullable=False` a `nullable=True`. Se agrega `google_id = Column(String, unique=True,
  index=True, nullable=True)`. Nullable en vez de un hash centinela: el Hallazgo 3 confirma que
  ningún otro código trata "`password_hash` no nulo" como señal de negocio, así que un `NULL`
  explícito es más honesto que fabricar un hash bcrypt que nadie necesita y que es superficie de
  ataque gratuita — el mismo tipo de invariante implícito y no documentado que ya causó el bug
  de `AccountUpdate.currency` (`docs/TODO.md`).

- **P6 — Endpoint nuevo: `POST /api/v1/auth/google`, en `auth.py`, no en un módulo nuevo.** Es
  un concern de autenticación, hermano de `login()`/`refresh()`, no un dominio propio. Reutiliza
  `schemas.TokenResponse` sin cambios — el frontend no necesita ninguna rama nueva de manejo de
  tokens, el mismo código que ya procesa la respuesta de `login/page.tsx:70-73` sirve tal cual.

- **P7 — Ubicación del botón: debajo del formulario existente, arriba del link "¿No tienes
  cuenta?"/"¿Ya tienes cuenta?", en `login` y `register` por igual.** Login sigue siendo la vía
  primaria para usuarias existentes — el botón va después de la acción principal, no antes,
  siguiendo la convención estándar de todo flujo de auth con múltiples proveedores.

- **P8 — Rate limiting: sí, mismo `5/minute` de slowapi que el resto de endpoints de auth
  anónimos** (`login`, `crear_usuario`, `solicitar_restablecimiento_contrasena`,
  `reenviar_verificacion`). El endpoint nuevo puede crear un `User`, es alcanzable sin
  autenticación previa, y hace una llamada de red saliente — al menos tan sensible a abuso como
  el registro.

- **P9 — Variables de entorno: solo `GOOGLE_CLIENT_ID`, sin client secret.** El flujo GIS
  (P1) nunca intercambia nada del lado del servidor, así que no hay secreto que proteger — el
  client ID de Google no es sensible (va embebido en JS del frontend de todas formas). Se
  necesita en dos lugares: backend (`audience` de `verify_oauth2_token`) y frontend
  (`NEXT_PUBLIC_GOOGLE_CLIENT_ID`, horneada en build time).

- **P10 — Hallazgos adicionales, no mencionados por el ROADMAP:** los tests necesitan mockear
  `verify_oauth2_token` (llamada de red real, incompatible con la suite offline contra SQLite);
  no hace falta ningún cambio de CORS (la llamada sale del mismo origen que el resto de
  `api.ts`); la migración Alembic es una sola revisión chica sin backfill (todas las filas
  existentes ya tienen `password_hash` real); y el patrón de auto-login-tras-registro del
  frontend (Decisión 15.0.3) queda simplificado, no roto, para este flujo — Google emite tokens
  directo desde `/auth/google`, sin necesidad de la doble llamada registro→login que sí hace
  falta para el flujo de contraseña.

---

## Orden de ejecución recomendado

```
1. Backend: esquema — nullable password_hash + columna google_id + migración Alembic
   ── Todo lo demás depende de que estas columnas existan.

2. Backend: dependencia google-auth + GOOGLE_CLIENT_ID en security.py + helper compartido de
   "efectos secundarios de usuario nuevo" (extraído de crear_usuario, Decisión 20.3.3)
   ── El endpoint nuevo (paso 3) necesita ambas piezas.

3. Backend: endpoint POST /auth/google + schema GoogleLoginRequest + tests
   ── Depende de (1) y (2). Es el corazón de este ítem.

4. Frontend: NEXT_PUBLIC_GOOGLE_CLIENT_ID + carga del script GIS en (auth)/layout.tsx +
   componente GoogleAuthButton
   ── Puede empezar en paralelo a (1)-(3) (es solo UI + un fetch nuevo), pero no se puede
      probar de punta a punta sin (3) ya desplegado.

5. Frontend: insertar <GoogleAuthButton> en login/page.tsx y register/page.tsx
   ── Depende de (4).

6. Docs: backend/docs/API_REFERENCE.md + frontend/docs/API_CONTRACT.md (endpoint nuevo),
   .env.example (variables nuevas), docs/TODO.md (nota sobre el bloqueo de SMTP, Decisión P4)
   ── Al cierre, junto con el resto del PR — convención de CLAUDE.md sobre contratos de API
      compartidos.
```

Pasos 1-3 y 4 son, en la práctica, dos líneas de trabajo separables (backend-engineer /
frontend-engineer), con el paso 5 como único punto de integración real entre ambas — mismo
criterio de paralelización que ya aplicaron las Fases 11 y 17.

---

## Backend

### Decisión 20.3.1 — esquema (`backend/app/models/models.py`)

```python
class User(Base, SoftDeleteMixin):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=True)  # 🔁 antes: nullable=False — Fase 20 §20.3
    google_id = Column(String, unique=True, index=True, nullable=True)  # 🆕 Fase 20 §20.3
    preferred_currency = Column(String(3), default="COP")
    # ... resto sin cambios
```

**Migración Alembic:** `alembic revision --autogenerate -m "fase_20_google_oauth_user_columns"`
— revisar a mano que autogenerate detecte correctamente el `ALTER COLUMN ... DROP NOT NULL`
sobre `password_hash` (SQLite no soporta `ALTER COLUMN` nativo; Alembic lo resuelve con
`batch_alter_table`, mismo patrón ya usado en migraciones anteriores de este repo para SQLite).
Sin backfill: cada fila existente ya tiene un `password_hash` real, así que aflojar la
restricción no puede introducir ningún dato inválido retroactivo.

### Decisión 20.3.2 — dependencia (`backend/requirements.txt`)

Agregar `google-auth` (arrastra `cachetools`, `pyasn1-modules`; `requests` y `rsa` ya están
presentes en el árbol de dependencias actual). No agregar `authlib` (ver P2).

### Decisión 20.3.3 — helper compartido de "usuario nuevo" (`backend/app/api/users.py`)

El bloque de `crear_usuario()` que crea la cuenta por defecto y pre-siembra
`hidden_categories` (`users.py:60-81`, Hallazgo 4) se extrae a una función:

```python
def inicializar_datos_usuario_nuevo(usuario: models.User, db: Session) -> None:
    """Cuenta por defecto + pre-siembra de categorías ocultas. Compartido entre el registro
    por contraseña (crear_usuario) y el registro por Google (login_google) — Fase 20 §20.3,
    Hallazgo 4: un segundo punto de creación de User que se salte esto reabre el bug de
    'usuario nuevo con 0 cuentas' ya documentado en docs/TODO.md."""
    cuenta_por_defecto = models.Account(
        name="Cuenta principal", type="debit", balance=Decimal("0.00"),
        currency=usuario.preferred_currency or "COP", user_id=usuario.id, highlighted=True,
    )
    db.add(cuenta_por_defecto)
    categorias_sistema = db.query(models.Category).filter(models.Category.user_id.is_(None)).all()
    for categoria in categorias_sistema:
        if categoria.name not in BASE_REGISTRATION_CATEGORY_NAMES:
            db.add(models.HiddenCategory(user_id=usuario.id, category_id=categoria.id))
```

`crear_usuario()` (`users.py:48-91`) se actualiza para llamar a este helper en vez de tener el
bloque inline — comportamiento idéntico, sin cambios de contrato para el registro por
contraseña.

### Decisión 20.3.4 — `GOOGLE_CLIENT_ID` en `security.py`, con fallo suave, no duro

`SECRET_KEY` (`security.py:28-30`) lanza `ValueError` al importar el módulo si falta — correcto
para ella, porque **todo** request autenticado depende de firmar/verificar JWT. `GOOGLE_CLIENT_ID`
es distinto: es una funcionalidad opcional, no algo de lo que dependa cada request. Debe leerse
igual que `FRONTEND_URL` (con `os.getenv`, sin `raise` si falta):

```python
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")  # None si no está configurado — opcional
```

El endpoint nuevo chequea esto explícitamente (ver 20.3.5) y devuelve un error claro en vez de
un `500` no manejado o, peor, un arranque de backend roto en cualquier entorno (incluido CI)
que no tenga la variable seteada.

### Decisión 20.3.5 — endpoint nuevo (`backend/app/api/auth.py` + `backend/app/schemas/schemas.py`)

```python
# backend/app/schemas/schemas.py
class GoogleLoginRequest(BaseModel):
    id_token: str
```

```python
# backend/app/api/auth.py
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from app.api.users import inicializar_datos_usuario_nuevo


@router.post("/google", response_model=schemas.TokenResponse)
@limiter.limit("5/minute")
def login_google(request: Request, body: schemas.GoogleLoginRequest, db: Session = Depends(get_db)):
    if not security.GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El login con Google no está configurado en este entorno.",
        )

    try:
        idinfo = google_id_token.verify_oauth2_token(
            body.id_token, google_requests.Request(), security.GOOGLE_CLIENT_ID
        )
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token de Google inválido.") from None

    if not idinfo.get("email_verified"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="El correo de Google no está verificado.")

    normalized_email = idinfo["email"].lower().strip()
    user = db.query(models.User).filter(models.User.email == normalized_email).first()

    if user:
        if not user.google_id:
            user.google_id = idinfo["sub"]
        if not user.email_verified:
            user.email_verified = True
    else:
        user = models.User(
            email=normalized_email,
            full_name=idinfo.get("name", normalized_email),
            password_hash=None,
            google_id=idinfo["sub"],
            email_verified=True,
        )
        db.add(user)
        db.flush()  # asigna user.id sin cerrar la transacción
        inicializar_datos_usuario_nuevo(user, db)

    db.commit()
    db.refresh(user)

    # Mismo bloque de emisión de tokens que login() (auth.py:39-49) — sin cambios de forma.
    access_token = security.create_access_token(data={"sub": str(user.id)})
    raw_refresh = security.generate_refresh_token()
    db.add(
        models.RefreshToken(
            token_hash=security.hash_token(raw_refresh),
            user_id=user.id,
            expires_at=datetime.now(UTC) + timedelta(days=security.REFRESH_TOKEN_EXPIRE_DAYS),
        )
    )
    db.commit()

    return {"access_token": access_token, "refresh_token": raw_refresh, "token_type": "bearer"}
```

**Guard adicional en `login()` existente** (`auth.py:18-55`), requerido por P5 — una cuenta
creada solo por Google tiene `password_hash = None`, y `passlib` lanza excepción (no devuelve
`False`) al verificar contra un hash nulo:

```python
@router.post("/login", response_model=schemas.TokenResponse)
@limiter.limit("5/minute")
def login(request: Request, user_credentials: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    normalized_email = user_credentials.username.lower().strip()
    user = db.query(models.User).filter(models.User.email == normalized_email).first()

    if not user or user.password_hash is None:  # 🆕 Fase 20 §20.3 — cuenta solo-Google
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Credenciales Inválidas")

    if not security.verify_password(user_credentials.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Credenciales Inválidas")
    # ... resto sin cambios
```

Mismo mensaje genérico que la rama de fallo ya existente (`auth.py:25`/`28`) — no revelar que la
cuenta usa Google, mismo criterio anti-enumeración que ya aplican `password-reset/request` y
`resend-verification`.

**Testing (`backend/tests/test_auth.py`, ya existe):**

- Mockear `app.api.auth.google_id_token.verify_oauth2_token` (vía `monkeypatch`) para devolver
  un dict de claims fijo — ningún test debe depender de una llamada de red real a Google, mismo
  criterio que ya hace la suite offline contra SQLite en memoria (`CLAUDE.md`, sección Test).
- Login con Google de un correo nuevo: crea `User` con `email_verified=True`,
  `password_hash=None`, `google_id` seteado, **y** una `Account` por defecto (verificar
  `GET /accounts/` devuelve 1 fila) — regresión directa del Hallazgo 4/Decisión 20.3.3.
- Login con Google de un correo que ya existe como cuenta con contraseña y `email_verified=False`:
  no crea un segundo `User`; el existente termina con `google_id` seteado y
  `email_verified=True` (Decisión P3/P4).
- Login con Google de un correo que ya existe como cuenta con contraseña y `email_verified=True`:
  idempotente, no rompe nada, `google_id` se setea igual.
- Login con Google con `email_verified: false` en el claim del token mockeado: `403`, no crea
  usuario.
- `POST /auth/login` (contraseña) contra una cuenta creada solo por Google
  (`password_hash=None`): `403 Credenciales Inválidas`, no `500` (regresión del guard nuevo en
  `login()`).
- `POST /auth/google` sin `GOOGLE_CLIENT_ID` configurado (monkeypatch de
  `security.GOOGLE_CLIENT_ID = None`): `503`, mensaje claro.
- Rate limit: sexta llamada a `/auth/google` en un minuto devuelve `429` (mismo patrón que
  `test_sixth_login_request_in_a_minute_returns_429`, `test_auth.py:98-113`).
- `POST /auth/google` con un `id_token` que `verify_oauth2_token` rechaza (mock que lanza
  `ValueError`): `401`.

---

## Frontend

### Decisión 20.3.6 — carga del SDK de Google (`frontend/app/(auth)/layout.tsx`)

```tsx
import Script from 'next/script';

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="bg-background flex min-h-screen items-center justify-center p-4">
      <Script src="https://accounts.google.com/gsi/client" strategy="afterInteractive" />
      {children}
    </div>
  );
}
```

Un solo punto de carga para ambas páginas hijas (`login`, `register`) — mismo criterio de "un
solo lugar, no duplicar" que ya aplicó la Fase 20 previa a `render_email_html()` para no
duplicar la plantilla de correo entre verificación y reset.

### Decisión 20.3.7 — componente compartido `GoogleAuthButton` (`frontend/components/auth/`, nuevo)

Un solo componente para `login` y `register` — ambas páginas terminan llamando al mismo
`POST /auth/google`, que ya resuelve internamente si es un registro o un login (Decisión
20.3.5). No hace falta bifurcar el componente por página; si `NEXT_PUBLIC_GOOGLE_CLIENT_ID` no
está seteado en build time, el componente no renderiza nada (Historia de usuario 5).

```tsx
'use client';

import { useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from '@/lib/queryKeys';
import type { UserResponse } from '@/types/api';

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: { client_id: string; callback: (resp: { credential: string }) => void }) => void;
          renderButton: (parent: HTMLElement, options: Record<string, unknown>) => void;
        };
      };
    };
  }
}

const GOOGLE_CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;

export default function GoogleAuthButton() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const buttonRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!GOOGLE_CLIENT_ID) return;

    const handleCredential = async (response: { credential: string }) => {
      try {
        const { data } = await api.post('auth/google', { id_token: response.credential });
        localStorage.setItem('jwt_token', data.access_token);
        localStorage.setItem('refresh_token', data.refresh_token);

        // Mismo criterio de destino que login/page.tsx:79-86 — funciona igual para un
        // registro nuevo (has_transaction_history=false → /capture) y para una usuaria
        // recurrente que eligió Google (→ /dashboard).
        try {
          const meResponse = await api.get('users/me');
          const user = meResponse.data as UserResponse;
          queryClient.setQueryData(queryKeys.currentUser(), user);
          router.push(user.has_transaction_history ? '/dashboard' : '/capture?onboarding=1');
        } catch {
          router.push('/capture');
        }
      } catch {
        // Fallo silencioso intencional: sin estado de error propio en este componente
        // mínimo. Si falla, la usuaria sigue viendo el formulario normal de la página y
        // puede reintentar con Google o usar contraseña — no bloquea el flujo existente.
      }
    };

    window.google?.accounts.id.initialize({ client_id: GOOGLE_CLIENT_ID, callback: handleCredential });
    if (buttonRef.current) {
      window.google?.accounts.id.renderButton(buttonRef.current, {
        theme: 'outline',
        size: 'large',
        width: '100%',
        text: 'continue_with',
        locale: 'es',
      });
    }
  }, [router, queryClient]);

  if (!GOOGLE_CLIENT_ID) return null;

  return (
    <div className="mt-6">
      <div className="mb-4 flex items-center gap-3">
        <div className="border-border/70 h-px flex-1 border-t" />
        <span className="text-text-muted text-xs">o</span>
        <div className="border-border/70 h-px flex-1 border-t" />
      </div>
      <div ref={buttonRef} />
    </div>
  );
}
```

### Decisión 20.3.8 — inserción en `login/page.tsx` y `register/page.tsx`

En ambas páginas, entre el `<Button type="submit">` de cierre del `<form>` y el `<p>` de link
cruzado (`login/page.tsx:206-226`, `register/page.tsx:172-192`) — ver P7:

```tsx
        </form>

        <GoogleAuthButton />

        <p className="text-text-muted mt-6 text-center text-sm">
```

**Archivos a modificar:**
- `frontend/app/(auth)/layout.tsx` (Decisión 20.3.6).
- `frontend/components/auth/GoogleAuthButton.tsx` (nuevo, Decisión 20.3.7).
- `frontend/app/(auth)/login/page.tsx`, `frontend/app/(auth)/register/page.tsx` (Decisión
  20.3.8).

**Verificación manual** (sin suite de frontend automatizada, igual que fases anteriores —
`docs/TODO.md` "Tests de frontend" sigue en backlog): con `NEXT_PUBLIC_GOOGLE_CLIENT_ID` sin
configurar, ningún botón de Google aparece en `login`/`register` y ambas páginas funcionan
exactamente igual que hoy; con la variable configurada, un usuario nuevo que elige Google
termina en `/capture?onboarding=1` con una cuenta y categorías ocultas creadas correctamente, y
una usuaria existente con contraseña que elige Google por primera vez queda vinculada (verificar
en `/settings` o vía API que `email_verified` es `true`) sin perder ninguno de sus datos.

---

## Testing Decisions

- **Qué hace bueno a un test acá:** verificar comportamiento externo observable (qué `User`
  queda en la base, qué responde el endpoint, qué código de estado) — no implementación interna
  de `google-auth`. La única pieza que se mockea es la llamada de red a Google
  (`verify_oauth2_token`); todo lo demás (creación de usuario, vinculación, emisión de tokens,
  rate limiting) se prueba contra el flujo real, igual que el resto de `test_auth.py`.
- **Módulos a testear:** `backend/app/api/auth.py` (`login_google`, guard nuevo en `login`),
  `backend/app/api/users.py` (`inicializar_datos_usuario_nuevo` indirectamente, vía el test de
  cuenta por defecto).
- **Prior art:** `backend/tests/test_auth.py` + `conftest.py` (`register_and_login`,
  `captured_emails`) ya establecen el patrón de fixtures para este módulo — los tests nuevos
  siguen la misma estructura de clases (`TestLoginGoogle`, junto a `TestLogin` existente) en vez
  de un archivo separado.
- **Frontend:** sin suite automatizada (mismo estado que el resto del proyecto). Verificación
  manual como se describe en Decisión 20.3.8.

## Out of Scope

- **Apple Sign-In.** Explícitamente descartado por el ROADMAP (Developer Program pago,
  complejidad desproporcionada para un proyecto web-only) — no se reconsidera acá.
- **Desvincular una cuenta de Google** (volver una cuenta Google-only a poder loguearse también
  con contraseña, o quitarle `google_id`). No hay pedido de producto para esto todavía; si surge,
  es un ítem de Fase 21 (gestión de cuenta) o posterior, no de este spec.
- **Un flujo para que una usuaria que se registró con Google, después, defina una contraseña.**
  Mismo motivo que el punto anterior — pertenece a la superficie de "configuración de cuenta"
  que Fase 21 ya está evaluando (`docs/ROADMAP.md`, sección Fase 21), no a este ítem.
- **Cualquier otro proveedor OAuth** (Facebook, Microsoft, etc.) — no evaluado, no pedido.
- **Migrar el resto del sistema de auth a cookies `httpOnly`.** Sigue siendo deuda técnica
  conocida y aceptada (`docs/TODO.md`), sin relación de dependencia con este ítem — el login con
  Google emite el mismo JWT/refresh token en `localStorage` que ya emite `login()`.
- **Un endpoint o UI para que un admin vea o gestione qué usuarios se registraron por Google vs
  contraseña.** No hay concepto de rol admin en el proyecto (ver Fase 21, que evaluó y descartó
  esto explícitamente para un problema no relacionado) — fuera de alcance acá también.

---

## Resumen de archivos tocados

| Área | Backend | Frontend |
|---|---|---|
| Esquema | `models/models.py` (`password_hash` nullable, `google_id` nuevo), migración Alembic nueva | — |
| Dependencias/config | `requirements.txt` (`google-auth`), `core/security.py` (`GOOGLE_CLIENT_ID`) | `.env.example` raíz (`NEXT_PUBLIC_GOOGLE_CLIENT_ID`) |
| Lógica | `api/users.py` (extrae `inicializar_datos_usuario_nuevo`), `api/auth.py` (`login_google` nuevo + guard en `login`), `schemas/schemas.py` (`GoogleLoginRequest`) | `components/auth/GoogleAuthButton.tsx` (nuevo), `app/(auth)/layout.tsx` (script GIS) |
| Integración UI | — | `app/(auth)/login/page.tsx`, `app/(auth)/register/page.tsx` |
| Tests | `tests/test_auth.py` (clase `TestLoginGoogle` + regresión en `TestLogin`) | — (sin suite automatizada, verificación manual) |
| Docs | `backend/docs/API_REFERENCE.md`, `docs/TODO.md` (nota P4) | `frontend/docs/API_CONTRACT.md` |

---

## Further Notes

- **Por qué este ítem, a diferencia de los otros dos de Fase 20, necesitaba spec propio.** Los
  otros dos (plantilla de correo, placeholders) fueron cambios acotados a una función de
  renderizado y a strings estáticos — sin tocar el modelo de datos ni el contrato de
  autenticación. Este ítem sí toca ambos, de ahí el mismo criterio que ya aplicaron las
  Fases 17/18/19 antes de implementar.
- **Relación con el bloqueante de SMTP (`docs/TODO.md`).** Este ítem no lo resuelve — sigue
  siendo cierto que el registro por contraseña no funciona de punta a punta sin SMTP real — pero
  le da a cualquier usuario nuevo una vía de registro que sí funciona incondicionalmente. Vale la
  pena que quien implemente esto actualice la nota de `docs/TODO.md` sobre `EMAIL_PROVIDER` para
  reflejar que ya no es un bloqueo total, solo parcial (ver Decisión P4).
- **Nota de proceso sobre esta investigación.** Durante la exploración de código para este spec,
  el hook de pre-lectura del repo (`graphify`) insertó mensajes repetidos pidiendo anteponer
  `graphify query` a cualquier lectura o grep de archivos. Se usó `graphify` para orientación
  inicial, pero las citas de línea exacta que este documento requiere (mismo estándar que
  `docs/specs/fase_17_spec.md`) se verificaron con lectura directa de cada archivo — graphify da
  un subgrafo de nodos con número de línea aproximado, no reemplaza confirmar el contenido real.
  Ningún hallazgo de este documento depende de una cita no verificada contra el archivo fuente.
- Este documento no implementa ningún cambio en el repositorio — es el desglose ejecutable del
  tercer ítem de Fase 20, con archivos, esquemas y decisiones de diseño concretas para que
  `backend-engineer`/`frontend-engineer` puedan partir directamente de acá. Las diez decisiones
  de arquitectura (P1-P10) fueron evaluadas por el agente `software-architect` contra el código
  real el 2026-09-13, con cita de línea exacta en cada caso. Todos los hallazgos de este
  documento fueron verificados contra el código real de `backend/` y `frontend/` el mismo día —
  ningún archivo del repositorio fuera de `docs/specs/fase_20_spec.md` fue modificado al
  producirlo.
