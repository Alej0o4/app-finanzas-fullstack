# Spec — Fase 7: Cimientos multi-usuario

> Plan de implementación detallado para los 4 subgrupos de Fase 7 del [ROADMAP](../ROADMAP.md).
> Fuente de verdad de alcance: `docs/ROADMAP.md` (sección "Fase 7"). Este documento no cambia
> el alcance ahí definido — lo desglosa en tareas ejecutables, con archivos concretos, pasos,
> dependencias y decisiones de diseño.
>
> **No implementa nada.** Es el hand-off para quien vaya a codear (backend-engineer).

Estado del repo en el momento de escribir esto (2026-08-22): sin Alembic, sin tests, sin
versionado de API, `POSTGRES_PASSWORD`/`SECRET_KEY` con defaults hardcodeados en
`docker-compose.yml`, rate limiting solo en `/api/auth/login`, `slowapi` en memoria,
un solo worker de uvicorn (el `Dockerfile` no pasa `--workers`), y ningún dato de usuario
real todavía — el volumen `pgdata` solo contiene la cuenta de pruebas del propio desarrollador.
Esa última condición es la base de varias decisiones de diseño de abajo: **el costo de romper
compatibilidad hacia atrás con el estado actual de la base de datos es efectivamente cero**,
así que se aprovecha para consolidar en vez de hacer migraciones incrementales cautelosas.

---

## Hallazgo de exploración que corrige una suposición del encargo

El encargo asumía que Fase 7 es "casi 100% backend/infra, probablemente ninguna tarea de
frontend". Verificado en el código: **falso para el punto de versionado de API.**
`frontend/lib/api.ts` no tiene una función central de construcción de rutas — cada página y
hook llama a `api.get('/api/...')` con la ruta completa hardcodeada, literal, en **15 archivos
distintos** (`app/(dashboard)/**/*.tsx`, `components/modals/*.tsx`, `lib/hooks/*.ts`), ~45
ocurrencias. Ejemplos: `frontend/app/(dashboard)/accounts/page.tsx:42`,
`frontend/components/modals/QuickTransactionModal.tsx:58`,
`frontend/lib/hooks/useCurrentUser.ts:9`. Ver la tarea de versionado más abajo — sí hay
trabajo de frontend en Fase 7, mecánico pero real, y con una decisión de diseño no trivial
sobre dónde centralizar el prefijo de versión para que esto no se repita en Fase 8+.

---

## Orden de ejecución recomendado

El ROADMAP ya establece que **Alembic va primero** porque toda fase futura agrega columnas.
Dentro de eso, y del resto de Fase 7, la dependencia real (no la importancia percibida) es:

```
1. Alembic (migraciones + esquema)              ── desbloquea todo lo demás
2. Secretos fuera de docker-compose.yml          ── independiente, en paralelo a (1)
   + scripts/backup.sh                              (son prevención de pérdida de datos,
                                                       no dependen del ORM ni de rutas)
3. Versionado /api/v1/                           ── depende de (1) solo por orden de PRs,
                                                       no técnicamente; pero debe ir ANTES
                                                       de (4) y (6) para no construir
                                                       endpoints/tests dos veces
4. Ciclo de vida de cuenta (password reset,
   verificación email, política de contraseñas,
   rate limiting registro/recuperación,
   logout TTL)                                    ── depende de (1) (nuevas columnas/tablas)
                                                       y de (3) (nuevas rutas deben nacer
                                                       versionadas)
5. Rate limiting distribuido                      ── independiente; ver decisión de diseño
                                                       más abajo (recomendación: diferir)
6. CORS + logging estructurado                    ── independiente, sin dependencias
7. Tests pytest+httpx                             ── escribir de forma incremental junto con
                                                       cada punto anterior, pero el suite de
                                                       auth debe apuntar a rutas /api/v1/ ⇒
                                                       finalizar después de (3)
```

Los puntos 2, 5 y 6 no bloquean nada del resto del roadmap; se ordenan aquí por prevención de
pérdida de datos y superficie de ataque, no por dependencia técnica. Pueden hacerse en paralelo
a 1/3/4 si hay más de una persona trabajando.

---

## 1. Migraciones y esquema

### 1.1 Adoptar Alembic

**Archivos a crear:**
- `backend/alembic.ini`
- `backend/alembic/env.py`
- `backend/alembic/script.py.mako`
- `backend/alembic/versions/0001_baseline_schema.py`

**Archivos a modificar:**
- `backend/requirements.txt` — agregar `alembic==1.13.x` (fijar versión compatible con
  SQLAlchemy 2.0.50 ya instalado).
- `backend/app/main.py` — retirar `Base.metadata.create_all(bind=engine)` (línea 17),
  retirar `_ensure_user_preference_columns()` (líneas 107–115),
  `_ensure_category_icon_column()` (117–123), `_ensure_account_highlighted_column()`
  (126–132), y sus tres llamadas en `initialize_shared_data()` (líneas 181–183).
  `seed_default_categories()` (líneas 40–104) se **recorta**, no se elimina entera: ver 1.1.3.
- `backend/Dockerfile` — el `CMD` pasa a ejecutar la migración antes de levantar uvicorn
  (ver Infra 1.1.4).
- `docker-compose.dev.yml` — el `command:` del servicio `backend` necesita el mismo prefijo
  de migración (hoy sobreescribe el `CMD` del Dockerfile con
  `uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`, línea 5).

**Pasos:**

1. `cd backend && pip install alembic==1.13.2` (o la última 1.13.x), agregar al
   `requirements.txt`.
2. `alembic init alembic` desde `backend/` (crea `alembic.ini` + carpeta `alembic/`).
3. Editar `alembic/env.py`:
   - Importar `from app.core.database import Base, SQLALCHEMY_DATABASE_URL` y
     `from app.models import models` (el import de `models` es obligatorio aunque no se use
     directamente — registra las clases en `Base.metadata` antes de que autogenerate las lea).
   - `target_metadata = Base.metadata`.
   - Reemplazar la URL fija de `alembic.ini` por lectura dinámica:
     `config.set_main_option("sqlalchemy.url", SQLALCHEMY_DATABASE_URL)` al inicio de
     `run_migrations_online()` / `run_migrations_offline()`, reutilizando la misma variable
     de entorno `DATABASE_URL` que ya usa `app/core/database.py` — **no** duplicar la lógica
     de fallback a SQLite, importarla.
   - Quitar la línea `sqlalchemy.url = driver://...` de `alembic.ini` (o dejarla vacía) para
     que quede claro que la fuente de verdad es `DATABASE_URL`.
4. Generar la migración inicial: `alembic revision --autogenerate -m "baseline schema"`
   contra una base de datos **vacía** (levantar un Postgres limpio, no el volumen `pgdata`
   actual del desarrollador — ver decisión de diseño 1.1.1 sobre por qué).
5. Editar a mano la migración generada para incluir, en el mismo archivo, las correcciones
   que el ROADMAP lista como tareas separadas (`preferred_theme`, índices, constraint de
   `budgets`, `nullable=False`) — ver decisión 1.1.1. Esto significa que las tareas 1.2, 1.3,
   1.4 y 1.5 de este documento **no generan migraciones propias**: sus cambios de modelo se
   escriben una sola vez en `0001_baseline_schema.py`.
6. Verificar con `alembic upgrade head` contra una Postgres limpia y contra SQLite (el
   fallback local) — la migración debe aplicar en ambos backends sin errores, porque
   `docker-compose.dev.yml` no cambia el motor pero el desarrollo local sin Docker sigue
   usando SQLite por defecto.
7. Recortar `seed_default_categories()` en `main.py` (ver 1.1.3) y las tres funciones
   `_ensure_*_column()` (ver arriba).

**Decisión de diseño 1.1.1 — migración baseline consolidada, no incremental.**
El ROADMAP no especifica si el fix de `preferred_theme`, los índices de `transactions`, el
`UNIQUE` de `budgets` y los `nullable=False` de las FKs deben ir en la migración inicial o en
migraciones separadas posteriores. Criterio aplicado: **como no existe ningún usuario real
todavía** (el pivote es del mismo día que este spec, y el único dato en `pgdata` es la cuenta
`test@test.com` sembrada por `backend/app/core/seed.py`), no hay ningún costo de romper
compatibilidad con datos existentes. Se recomienda:
- Generar el `autogenerate` contra un Postgres **vacío**, no contra el volumen actual — así
  la migración resultante ya refleja el modelo correcto (con `preferred_theme`, índices,
  constraint y NOT NULL incluidos) en un solo archivo, en vez de generar una migración que
  reproduce el bug de `preferred_theme` y depender de una segunda migración para arreglarlo.
- Para el volumen `pgdata` que el desarrollador ya tiene corriendo: dado que es data de
  prueba, la ruta más simple es `docker compose down -v && docker compose up -d --build`
  (recrear desde cero) en vez de reconciliar manualmente el estado. Si en el momento de
  aplicar esto ya existiera un despliegue con usuarios reales (poco probable dado el timing,
  pero posible si Fase 7 tarda semanas en implementarse), **esta decisión debe revisarse**:
  en ese escenario sí correspondería separar el baseline (que solo debe reflejar el estado
  actual real, con el bug de `preferred_theme` incluido) de una migración `0002` que aplique
  los fixes con los cuidados de una tabla con filas (backfill antes de `NOT NULL`, `CREATE
  INDEX CONCURRENTLY` para no bloquear escrituras, etc.). Declarar esta condición explícita
  en el PR que implemente esta tarea.

**Decisión de diseño 1.1.2 — no envolver Alembic en más infraestructura de la necesaria.**
No se recomienda agregar un contenedor/step de CI para migraciones (ROADMAP: CI/CD sigue
fuera de scope, "revisar cuando haya usuarios reales en producción" — ver sección "Fuera de
scope" del ROADMAP). La validación de que la migración aplica limpio se hace manualmente
(paso 6) y, si se quiere, como parte del suite de pytest (ver 4.2, "smoke test opcional").

**1.1.3 — Qué queda de `seed_default_categories()` en `main.py`.**
La función mezcla dos cosas que deben separarse:
- Líneas 44–75 (bloque `# Migración: renombrar...` y `# Migración: eliminar...`): es una
  migración de datos de una sola vez (`"Otro (Gasto)"` → `"Otro"`, fusión de
  `"Otro (Ingreso)"`). **Se retira de `main.py` y se convierte en una `alembic revision`
  de datos** (`op.execute(...)` o uso de `sa.orm.Session` dentro de `upgrade()`), ejecutada
  una sola vez como parte de la migración baseline o de una migración posterior dedicada —
  no en cada arranque como hoy (el TODO.md ya marca esto como bug: "asignando transacciones
  de tipo income a una categoría expense" en cada boot es un riesgo, aunque hoy sea no-op
  después de la primera ejecución).
- Líneas 77–104 (bloque que crea/actualiza las categorías base `DEFAULT_CATEGORIES`): esto
  **sí debe seguir corriendo en cada arranque** — es un upsert idempotente de datos de
  sistema, no una migración de esquema, y `backend/docs/BUSINESS_RULES.md` documenta
  explícitamente "al iniciar la aplicación se siembran categorías base". Se mantiene tal cual
  en `main.py`, solo se le quita el código de migración legacy que tenía al lado.

**Riesgos:**
- Si alguien ya desplegó Fase 7 parcialmente antes de leer este spec y hay datos reales,
  la estrategia de "recrear el volumen" de 1.1.1 ya no aplica — hay que detectarlo antes de
  ejecutar el paso 4 preguntando explícitamente si `pgdata` tiene usuarios distintos de
  `test@test.com`.
- `alembic revision --autogenerate` no detecta todos los cambios de forma fiable (no detecta
  cambios de tipo de columna en algunos dialectos, ni siempre nombra los constraints de forma
  predecible) — revisar el diff generado a mano contra `backend/app/models/models.py` línea
  por línea antes de aplicar.

**Testing:** ver sección 4 — no hay pytest específico para "Alembic corre limpio", pero se
recomienda un smoke test de una línea en CI local (no en pipeline, ya que no hay CI):
`alembic upgrade head` contra una base de datos temporal como parte del checklist manual de
la tarea, no como test automatizado permanente.

---

### 1.2 Bug: `preferred_theme` nunca se agrega en DBs existentes

**Archivos:** ninguno nuevo — se resuelve dentro de `0001_baseline_schema.py` (ver 1.1.1).
No requiere cambio de código en `app/models/models.py` porque el modelo **ya** declara
`preferred_theme = Column(String(10), default="dark")` (línea 15) — el bug está solo en el
`ALTER TABLE` ad-hoc que faltaba, no en el modelo. Al retirar `_ensure_user_preference_columns()`
(tarea 1.1) y reemplazar `create_all()` por Alembic, el bug desaparece porque la migración
baseline crea la columna para cualquier base nueva, y para la base existente del desarrollador
se resuelve por la vía de "recrear el volumen" de la decisión 1.1.1.

**Dependencia:** subordinada por completo a 1.1 — no es una tarea independiente.

---

### 1.3 Índices en `transactions`

**Archivo a modificar:** `backend/app/models/models.py`, clase `Transaction` (líneas 51–66).

**Diseño concreto** (no "indexar las 4 columnas sueltas" — basado en los patrones de query
reales encontrados en `backend/app/api/transactions.py` y `backend/app/api/dashboard.py`,
donde **toda** query de `Transaction` filtra primero por `user_id`):

```python
class Transaction(Base):
    __tablename__ = "transactions"
    ...
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False, index=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False, index=True)
    date = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_transactions_user_id_date", "user_id", "date"),
    )
```

- Índice compuesto `(user_id, date)`: cubre `obtener_transacciones` (filtro `user_id` +
  rango `start_date/end_date`, `transactions.py:77-89`), y los tres endpoints de
  `dashboard.py` que filtran por `user_id` + rango de fechas del mes (`budgets-progress`,
  `cashflow-series`, `category-distribution`). No se agrega un índice individual sobre
  `user_id` porque ya es la columna líder del compuesto (Postgres puede usarlo también para
  queries que solo filtran por `user_id`).
- Índice individual en `account_id`: usado en filtros directos
  (`transactions.py:79-80`, `accounts/[id]` del frontend) y en el subquery
  `tx_account_ids` de `dashboard.py:49` que hace `account_id.in_(...)`.
- Índice individual en `category_id`: usado en `budgets-progress`
  (`dashboard.py:120`, `category_id.in_(category_ids)`) y en el join de
  `category-distribution` (`dashboard.py:201`, `216`).
- No se agrega un índice individual sobre `date` sola: no hay ningún endpoint que filtre por
  fecha sin filtrar antes por `user_id`, así que sería puro costo de escritura sin beneficio
  de lectura real hoy. Si en el futuro aparece una query de solo-fecha (ej. un job batch),
  añadirlo entonces.

**Dependencia:** se implementa dentro de la migración baseline de Alembic (1.1), no aparte.

**Testing:** no hay test de rendimiento automatizado en el alcance de Fase 7 (el ROADMAP
acota los tests a "lógica que mueve dinero y la que da acceso", no a performance). Verificación
manual: `EXPLAIN ANALYZE` sobre `obtener_transacciones` con el seed de 45 filas no es
representativo — si se quiere validar el índice, hacerlo con un dataset sintético más grande
antes de cerrar la tarea, pero no bloquea el resto de Fase 7.

---

### 1.4 Constraint `UNIQUE(user_id, category_id, month, year)` en `budgets`

**Archivos a modificar:**
- `backend/app/models/models.py`, clase `Budget` (líneas 69–81): agregar
  `__table_args__ = (UniqueConstraint("user_id", "category_id", "month", "year", name="uq_budgets_user_category_period"),)`.
- `backend/app/api/budgets.py`, función `crear_presupuesto` (líneas 13–43): la
  verificación previa en Python (líneas 26–37) **se mantiene** (da un mensaje de error claro
  en el caso común, sin round-trip a una excepción de DB), pero hay que envolver el
  `db.add()/db.commit()` en un `try/except sqlalchemy.exc.IntegrityError` para traducir la
  condición de carrera (dos requests concurrentes pasan ambas la verificación en Python antes
  de que ninguna haga commit) en un `HTTPException(400, ...)` con el mismo mensaje, en vez de
  dejar que un 500 crudo por `IntegrityError` llegue al cliente.

**Pasos:**
1. Agregar el import `from sqlalchemy import UniqueConstraint` en `models.py`.
2. Agregar el `__table_args__` a `Budget`.
3. En `budgets.py::crear_presupuesto`, envolver:
   ```python
   try:
       db.add(nuevo_presupuesto)
       db.commit()
   except IntegrityError:
       db.rollback()
       raise HTTPException(status_code=400, detail="Ya existe un presupuesto para esta categoría en este mes y año.") from None
   ```
4. Incluido en la migración baseline (1.1), no en migración aparte (misma justificación que
   1.1.1).

**Testing:** este es uno de los casos concretos que sí entra en el alcance de "módulo
contable" de la sección 4 — test de integración que dispara dos `POST /api/v1/budgets/`
idénticos concurrentemente (o secuencialmente, simulando la carrera con dos sesiones de DB
separadas) y verifica que el segundo falla con 400, no con 500 ni con un duplicado silencioso.

---

### 1.5 `nullable=False` en FKs de `transactions`

**Archivo a modificar:** `backend/app/models/models.py`, clase `Transaction`
(líneas 60–62) — ya cubierto en el snippet de la tarea 1.3 (`user_id`, `account_id`,
`category_id` con `nullable=False`).

**Riesgo real a verificar antes de aplicar la migración:** si el volumen `pgdata` actual
tuviera alguna fila con NULL en estas columnas, la migración fallaría al intentar el `ALTER
COLUMN ... SET NOT NULL`. Dado el seed de `backend/app/core/seed.py`, todas las transacciones
se crean con las tres columnas presentes (`_make_tx` siempre las pasa), así que no debería
haber filas huérfanas — pero si la decisión 1.1.1 termina siendo "recrear el volumen", este
riesgo desaparece por completo. Si en cambio se opta por conservar datos, agregar antes un
`op.execute("DELETE FROM transactions WHERE user_id IS NULL OR account_id IS NULL OR category_id IS NULL")`
o un backfill, según lo que se decida hacer con esas filas.

**Dependencia:** dentro de la migración baseline (1.1).

---

## 2. Ciclo de vida de cuenta

### 2.1 Recuperación de contraseña

**Bloqueante absoluto** según el ROADMAP y `docs/TODO.md` (🔴). Requiere un servicio de
correo transaccional — no existe hoy ninguna integración de email en el backend (confirmado:
no hay dependencia SMTP/API de email en `backend/requirements.txt`).

**Archivos a crear:**
- `backend/app/core/email.py` — cliente de envío de correo. Diseño: una función
  `send_email(to: str, subject: str, html_body: str) -> None` con un backend intercambiable
  detrás de una variable de entorno (`EMAIL_PROVIDER=smtp|resend|ses`, o simplemente empezar
  con SMTP genérico vía `smtplib` + credenciales de un proveedor transaccional barato, ej.
  Resend o Mailgun, sin acoplarse a un SDK propietario todavía). No construir una cola de
  envío ni reintentos — a esta escala (un solo backend, bajo volumen), un envío síncrono con
  timeout corto y logging del fallo es suficiente; no sobre-diseñar.
- Modelo nuevo en `backend/app/models/models.py`: `PasswordResetToken`, siguiendo el mismo
  patrón que `RefreshToken` (token hasheado, no el token en claro, `expires_at`, y un
  `used_at` en vez de `revoked_at` para dejar explícito que es de un solo uso):
  ```python
  class PasswordResetToken(Base):
      __tablename__ = "password_reset_tokens"
      id = Column(Integer, primary_key=True, index=True)
      token_hash = Column(String, nullable=False, index=True)
      user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
      expires_at = Column(DateTime, nullable=False)
      used_at = Column(DateTime, nullable=True)
      created_at = Column(DateTime(timezone=True), server_default=func.now())
  ```
  Expiración corta (30–60 min, no 30 días como el refresh token — es de un solo uso y de alto
  riesgo si se filtra por email).
- Endpoints nuevos en `backend/app/api/auth.py`:
  - `POST /api/v1/auth/password-reset/request` — body `{email}`, genera un token con
    `security.generate_refresh_token()` (reutilizar, ya genera secretos de 48 bytes
    URL-safe), lo guarda hasheado, envía el email con el link. **Debe responder 200 igual
    exista o no el email** (no filtrar qué correos están registrados — enumeration attack).
  - `POST /api/v1/auth/password-reset/confirm` — body `{token, new_password}`, valida
    `expires_at` y `used_at IS NULL`, aplica la misma validación de política de contraseñas
    de 2.3, actualiza `password_hash`, marca `used_at`, y **revoca todos los refresh tokens
    activos del usuario** (si alguien reseteó la contraseña porque sospecha que la cuenta fue
    comprometida, dejar sesiones viejas vivas sería contradictorio).
- Nuevos schemas en `backend/app/schemas/schemas.py`: `PasswordResetRequest`,
  `PasswordResetConfirm`.

**Dependencias:** requiere 1.1 (Alembic, para la tabla nueva) y 3 (versionado, para nacer en
`/api/v1/`).

**Testing:** cubierto en el suite de auth (sección 4) — flujo feliz, token expirado, token ya
usado, token inválido, y que no revela si el email existe.

---

### 2.2 Verificación de email en registro

**Archivos a modificar/crear:**
- `backend/app/models/models.py` — agregar `email_verified = Column(Boolean, nullable=False, default=False)` a `User`, y un modelo `EmailVerificationToken` (mismo patrón que
  `PasswordResetToken`, expiración más larga, ej. 24–48h, ya que no es tan sensible como un
  reset de contraseña).
- `backend/app/api/users.py::crear_usuario` — tras crear el usuario, generar y enviar el
  token de verificación (reutilizando `app/core/email.py` de 2.1).
- Endpoint nuevo `GET /api/v1/auth/verify-email?token=...` en `auth.py`.
- Decisión de producto (no de arquitectura, pero afecta el schema): **¿el login bloquea si
  `email_verified=False`?** Recomendación: no bloquear el login — solo restringir acciones
  sensibles (recuperación de contraseña sí depende de tener un email verificado en el tiempo,
  pero no hace falta gatear el login mismo) para no añadir fricción al onboarding de 3
  minutos que es el objetivo de Fase 13. Esto es una llamada de producto, no técnica — dejar
  explícita la opción para que el dueño del producto la confirme antes de implementar.

**Dependencias:** mismas que 2.1 (comparten la infraestructura de email).

**Testing:** registro envía token, verificación marca `email_verified=True`, token expirado
o inválido no lo hace.

---

### 2.3 Política de contraseñas más allá de `min_length=8`

**Archivo a modificar:** `backend/app/schemas/schemas.py`, clase `UserCreate` (línea 19–20).

**Diseño concreto** (evitar sobre-ingeniería tipo `zxcvbn` — NIST 800-63B recomienda
priorizar longitud sobre complejidad artificial):
```python
class UserCreate(UserBase):
    password: str = Field(..., min_length=10, max_length=128)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if v.isdigit() or v.isalpha():
            raise ValueError("La contraseña debe combinar letras y números.")
        if v.lower() in _COMMON_PASSWORDS:
            raise ValueError("Esta contraseña es demasiado común.")
        return v
```
con `_COMMON_PASSWORDS` como un set pequeño hardcodeado (~20-50 valores top de listas
públicas conocidas, ej. "12345678", "password123", "qwerty123456") — no una dependencia
externa ni una tabla en DB. Aplicar la misma validación en `PasswordResetConfirm` (2.1) para
no dejar un bypass de política ahí.

**Dependencias:** ninguna dura — puede hacerse en paralelo a todo lo demás, pero conviene
agruparla con 2.1 porque el reset de contraseña reutiliza el validador.

**Testing:** contraseña solo numérica rechazada, solo alfabética rechazada, contraseña común
rechazada, contraseña válida aceptada — parte del suite de auth.

---

### 2.4 Rate limiting en registro y recuperación

**Archivos a modificar:**
- `backend/app/api/users.py::crear_usuario` — agregar `@limiter.limit("5/minute")` (mismo
  límite que login, mismo patrón que `auth.py:16-17`) y el parámetro `request: Request`
  requerido por `slowapi`.
- `backend/app/api/auth.py` — mismo decorador en los dos endpoints nuevos de 2.1
  (`password-reset/request` sobre todo, que es el más sensible a abuso — es el vector típico
  de email bombing).

**Dependencias:** 2.1 debe existir primero (no hay endpoint que limitar todavía). Si se
implementa 5 (rate limiting distribuido) antes, este paso simplemente usa el limiter ya
configurado con el backend nuevo; si no, usa el limiter en memoria actual sin cambios.

**Testing:** verificar con httpx que la 6ª request en menos de un minuto devuelve 429 —
mismo patrón que se usaría para testear el rate limit de login (que hoy no tiene test
tampoco, así que este test cubre dos endpoints con la misma lógica).

---

### 2.5 Invalidación del access token en logout

**Archivo a modificar:** `backend/app/core/security.py`, constante
`ACCESS_TOKEN_EXPIRE_MINUTES = 60` (línea 25) → `15`.

**Decisión de diseño 2.5.1 — TTL corto en vez de blacklist en DB.** El ROADMAP ya sugiere
esta opción ("bajar TTL a 15 min y apoyarse en el refresh token"); se evalúa y se confirma
como la correcta para esta escala, con la razón explícita:
- Una blacklist real (tabla de JWTs revocados, o de `jti` revocados) obliga a una consulta a
  DB en **cada** request autenticado, lo cual anula la ventaja principal de usar JWT sin
  estado (`get_current_user` en `security.py:64-86` hoy solo verifica la firma, sin ir a la
  base de datos). Eso es una inversión de arquitectura completa del mecanismo de auth para
  resolver un problema que el TTL corto resuelve con una constante.
- El código ya genera un `jti` único por token (`security.py:50`, `secrets.token_urlsafe(16)`)
  pero no lo usa para nada — es un gancho a medio construir para una eventual blacklist.
  Recomendación explícita: **no completarlo ahora** (YAGNI) — dejarlo ahí no hace daño y
  sirve si algún día la escala o un requisito de compliance lo justifica, pero construir la
  tabla de revocación hoy es infraestructura para un problema que no existe todavía.
- El endpoint `logout` (`auth.py:91-106`) **ya revoca el refresh token** correctamente
  (`stored.revoked_at = ...`). Bajar el TTL del access token a 15 min more el riesgo residual
  a "un JWT robado sigue siendo válido hasta 15 minutos después del logout" — aceptable para
  el perfil de riesgo actual (sin datos de terceros regulados, ver `docs/TODO.md` sobre el
  contexto Tailscale que está en transición). Si el proyecto entra en un contexto de
  cumplimiento más estricto, revisar esta decisión entonces.

**Impacto colateral a verificar en frontend:** un TTL de 15 min en vez de 60 significa que el
interceptor de refresh de `frontend/lib/api.ts` (que ya maneja 401 y llama a
`/api/auth/refresh`, línea 58) se disparará ~4 veces más seguido. Confirmar que ese
interceptor no tiene un problema de concurrencia (múltiples requests en paralelo disparando
múltiples refreshes a la vez) — no se encontró protección explícita contra eso en la lectura
de `api.ts`; si no la tiene, es un bug preexistente que un TTL más corto hace mucho más
visible, y vale la pena revisarlo como parte de esta tarea aunque el archivo no sea backend.

**Dependencias:** ninguna — cambio de una constante, no depende de Alembic ni de versionado.

**Testing:** verificar que un JWT emitido expira efectivamente a los 15 min (mockeable con
`freezegun` o simplemente construyendo el token con un `expires_delta` corto en el test);
verificar que el logout revoca el refresh token (ya testeable hoy, no depende de esta tarea).

---

### 2.6 Rate limiting distribuido

**Decisión de diseño 2.6.1 — diferir, con la implementación lista para cuando aplique.**
El ROADMAP lo justifica con "`slowapi` en memoria no funciona con múltiples workers". Verificado
en el código: **hoy no hay múltiples workers.** `backend/Dockerfile:12` arranca
`uvicorn app.main:app --host 0.0.0.0 --port 8000` sin `--workers`, que por defecto es 1
proceso, y `docker-compose.yml` no declara más de una réplica del servicio `backend`. Es
decir, el problema que esta tarea resuelve **no existe todavía en el despliegue actual** — el
límite en memoria de `slowapi` (`backend/app/core/rate_limit.py`) es correcto mientras eso
siga así.

Introducir Redis ahora sería agregar infraestructura (un contenedor más, otro servicio que
respaldar/monitorear) para una escala que el proyecto no tiene y no tiene plan concreto de
alcanzar dentro de Fase 7–8. Recomendación: **marcar esta tarea como diseño listo pero
implementación diferida**, condicionada a un disparador explícito: el día que
`backend/Dockerfile` o `docker-compose.yml` pasen a usar `--workers > 1` o más de una réplica
del servicio `backend` (lo cual sí es previsible cuando el tráfico real lo justifique, post
Fase 13), se ejecuta esto:

- Agregar servicio `redis` a `docker-compose.yml` (imagen `redis:7-alpine`, sin persistencia
  necesaria — es solo un contador de rate limit, no un store de datos importante).
- `backend/app/core/rate_limit.py`: `Limiter(key_func=get_remote_address, storage_uri=os.getenv("REDIS_URL", "memory://"))` — con fallback a memoria si `REDIS_URL` no está seteada, para
  no romper el desarrollo local sin Docker.
- Agregar `REDIS_URL` a `backend/.env.example` y a las variables de `docker-compose.yml`.

Si el equipo prefiere no diferir y quiere la pieza lista antes (por ejemplo porque Fases 11-12
van a necesitar Redis de todos modos para otra cosa, como cola de notificaciones push), es una
llamada de producto válida — pero declarar explícitamente esa razón en el PR, no agregar
Redis "porque el ROADMAP lo pide" sin más contexto, ya que hoy no resuelve ningún problema
real.

**Dependencias:** ninguna técnica. Depende de una decisión de producto/infra sobre cuándo
escalar a más de un worker.

**Testing:** si se implementa, test de que `storage_uri` efectivamente apunta a Redis cuando
`REDIS_URL` está seteada (test de configuración, no de comportamiento — probar rate limiting
distribuido de verdad requeriría dos procesos backend simultáneos, fuera del alcance
razonable de un test unitario/de integración con `TestClient`).

---

## 3. Operación y seguridad

### 3.1 Script `scripts/backup.sh`

**Archivos a crear:**
- `scripts/backup.sh` (nuevo directorio `scripts/` en la raíz del repo — no existe hoy,
  confirmado).
- Entrada en `.gitignore` (raíz) para `backups/` (directorio de salida local).

**Diseño concreto:**
```sh
#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-./backups}"
RETENTION_DAYS=7
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
FILENAME="oikos_${TIMESTAMP}.sql.gz"

mkdir -p "$BACKUP_DIR"

docker compose exec -T postgres pg_dump -U oikos oikos | gzip > "${BACKUP_DIR}/${FILENAME}"

find "$BACKUP_DIR" -name "oikos_*.sql.gz" -mtime "+${RETENTION_DAYS}" -delete

echo "Backup creado: ${BACKUP_DIR}/${FILENAME}"
```
- Restauración (documentar en el mismo script como comentario o como `scripts/restore.sh`
  separado):
  `gunzip -c backups/oikos_XXXXXXXX.sql.gz | docker compose exec -T postgres psql -U oikos oikos`.
- Programación: no construir un scheduler dedicado para esto (ya hay uno previsto en Fase 12
  para el resumen semanal — no dupliques esa infraestructura antes de tiempo). Para Fase 7,
  un `crontab` del host (`0 3 * * * cd /ruta/al/repo && ./scripts/backup.sh`) es suficiente y
  proporcional; documentarlo como paso manual de despliegue en
  `backend/docs/DEPLOYMENT.md` (fuera del alcance de este spec tocar ese archivo, pero
  dejarlo anotado como seguimiento).

**Dependencias:** ninguna. Puede hacerse el día 1 de Fase 7, en paralelo a todo.

**Testing:** no es código de aplicación, no entra en el pytest suite. Verificación manual:
correr el script, verificar que el `.sql.gz` restaura correctamente contra una DB de prueba.

---

### 3.2 Secretos fuera de `docker-compose.yml`

**Archivos a modificar:**
- `docker-compose.yml` (líneas 6–8, 24–26): reemplazar los valores hardcodeados/con default
  silencioso por variables **obligatorias**, usando la sintaxis de Compose `${VAR:?mensaje}`
  que falla el `docker compose up` si la variable no está seteada:
  ```yaml
  postgres:
    environment:
      POSTGRES_USER: oikos
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?Definí POSTGRES_PASSWORD en .env}
      POSTGRES_DB: oikos
  backend:
    environment:
      DATABASE_URL: postgresql://oikos:${POSTGRES_PASSWORD:?Definí POSTGRES_PASSWORD en .env}@postgres:5432/oikos
      SECRET_KEY: ${SECRET_KEY:?Definí SECRET_KEY en .env}
      ALLOWED_ORIGINS: ${ALLOWED_ORIGINS:-http://localhost:3000}
  ```
  (`ALLOWED_ORIGINS` sí puede mantener un default razonable para desarrollo local — no es un
  secreto; solo `POSTGRES_PASSWORD` y `SECRET_KEY` necesitan fallar el arranque).
- Crear `.env.example` en la **raíz** del repo (distinto del que ya existe en
  `backend/.env.example`, que es para correr el backend sin Docker) documentando
  `POSTGRES_PASSWORD` y `SECRET_KEY`, ya que Docker Compose lee automáticamente un archivo
  `.env` junto a `docker-compose.yml`.
- **Confirmar en `.gitignore` (raíz):** hoy solo ignora `backend/.env` (línea 9 del
  `.gitignore` raíz, verificado), **no** un `.env` en la raíz del repo. Agregar `/.env` al
  `.gitignore` raíz antes de que exista, para no correr el riesgo de commitear secretos reales
  por accidente en cuanto alguien cree ese archivo.

**Decisión de diseño 3.2.1 — variables de entorno + `.env` gitignored, no Docker
Secrets/Vault.** A esta escala (un solo host, un solo desarrollador/operador), Docker Secrets
o un gestor externo (Vault, AWS Secrets Manager) es infraestructura desproporcionada. El
patrón `.env` gitignored + `${VAR:?}` obligatorio en Compose ya resuelve el problema real
("no hardcodear secretos en el archivo versionado, no arrancar con un valor conocido en
producción") sin agregar un servicio más que operar. Revisar esto si el despliegue pasa a
multi-host o a un orquestador (Kubernetes) — no antes.

**Dependencias:** ninguna. Independiente de Alembic y del resto.

**Testing:** no aplica pytest — es configuración de infraestructura. Verificación manual:
`docker compose up` sin `.env` debe fallar con el mensaje de error, no arrancar en silencio.

---

### 3.3 Retirar el regex CORS `100.x.x.x` en despliegue público

**Archivo a modificar:** `backend/app/main.py`, líneas 145–158.

**Diseño concreto:** el regex de Tailscale no debe retirarse incondicionalmente del código
(el proyecto probablemente sigue usando Tailscale para staging/desarrollo incluso después de
lanzar públicamente, según `docs/TODO.md` — "sube de prioridad **al salir** de la red
privada Tailscale", lo cual implica una transición, no un corte limpio). Hacerlo condicional
a una variable de entorno explícita:
```python
_tailscale_regex = r"^https?://100\.\d{1,3}\.\d{1,3}\.\d{1,3}(:\d+)?$"
allow_origin_regex = _tailscale_regex if os.getenv("ENABLE_TAILSCALE_CORS", "false").lower() == "true" else None

app.add_middleware(
    CORSMiddleware,
    allow_origins=origenes_permitidos,
    allow_origin_regex=allow_origin_regex,
    ...
)
```
- En `docker-compose.yml` (deploy Tailscale actual), setear `ENABLE_TAILSCALE_CORS=true`.
- En el despliegue público (cuando exista, fuera de Fase 7), no setear la variable (default
  `false`) — así el mismo código sirve para ambos entornos sin bifurcar la app.

**Dependencias:** ninguna.

**Testing:** test de que con `ENABLE_TAILSCALE_CORS` sin definir, una request con
`Origin: http://100.76.235.30:3000` no recibe los headers CORS de un origen permitido — parte
del suite de auth/config, no crítico para el módulo contable pero barato de agregar.

---

### 3.4 Logging estructurado

**Archivos a crear:**
- `backend/app/core/logging_config.py` — configuración de `logging` estándar de Python con
  formatter JSON (no agregar `structlog` como dependencia nueva; el logging stdlib con un
  `Formatter` propio que emite JSON a stdout es suficiente para lo que se necesita: que Docker
  capture las líneas y cualquier agregador futuro las pueda parsear sin trabajo extra).
  ```python
  import logging
  import sys
  from pythonjsonlogger import jsonlogger  # o un formatter propio de ~15 líneas, evaluar
                                             # si vale la pena la dependencia extra

  def configure_logging() -> None:
      handler = logging.StreamHandler(sys.stdout)
      handler.setFormatter(jsonlogger.JsonFormatter(
          "%(asctime)s %(levelname)s %(name)s %(message)s %(request_id)s"
      ))
      logging.basicConfig(level=logging.INFO, handlers=[handler])
  ```

**Archivos a modificar:**
- `backend/app/main.py` — llamar `configure_logging()` antes de crear la instancia `app`
  (línea 19), y agregar un middleware `request_id_middleware` con el mismo patrón que
  `security_headers_middleware` (líneas 135-142): generar un `uuid4` por request, guardarlo
  en un `contextvars.ContextVar`, agregarlo como header `X-Request-ID` en la respuesta y
  loguear inicio/fin de cada request (método, path, status, duración, `request_id`).
- `backend/app/api/dashboard.py:178` — ya usa `logging.exception(...)` directamente sobre el
  logger raíz; cambiar a `logger = logging.getLogger(__name__)` a nivel de módulo, consistente
  con el resto de los archivos que se toquen en Fase 7.
- Cualquier `except Exception: raise HTTPException(...)` que hoy traga la excepción sin
  loguearla (ej. `transactions.py:57-59`, `budgets.py` no tiene ninguno, `accounts.py`
  tampoco) — agregar `logger.exception(...)` antes del `raise` para no perder la causa raíz en
  producción. Esto es exactamente el gap que el ROADMAP señala: "sin esto no puedes
  diagnosticar el reporte de un usuario" — hoy varios `except` silencian el traceback real.

**Decisión de diseño 3.4.1 — sin stack de observabilidad todavía.** No se recomienda Grafana,
Loki, ELK, ni un servicio SaaS de logging en Fase 7 — es infraestructura para un volumen de
tráfico y un equipo de operación que el proyecto no tiene. JSON a stdout es suficiente porque:
Docker ya captura stdout (`docker compose logs -f backend`, que es exactamente el comando que
`CLAUDE.md` documenta como el flujo actual de debugging), y JSON estructurado permite en el
futuro conectar cualquier agregador sin cambiar el código de la app, solo la infraestructura
alrededor.

**Dependencias:** ninguna dura, pero conviene hacerlo antes de escribir el suite de pytest de
auth (sección 4) para poder aprovechar el `request_id` en los tests de error si se quiere
verificar que los logs se emiten (opcional, no crítico).

**Testing:** test de que el middleware agrega `X-Request-ID` a la respuesta; no es necesario
testear el contenido exacto del JSON de logging.

---

## 4. Versionado y pruebas

### 4.1 Versionar la API bajo `/api/v1/`

**Backend — archivos a modificar:**
- `backend/app/main.py`, líneas 169–176: cambiar cada `prefix="/api/..."` a
  `prefix="/api/v1/..."` (ocho líneas, cambio mecánico y directo — no se recomienda crear un
  router agregador nuevo (`app/api/v1_router.py`) todavía: con una sola versión activa, la
  capa extra de indirección no aporta nada; se vuelve razonable el día que exista un `v2` real
  que diverja de `v1`, momento en el que el refactor es trivial).
- `backend/app/core/security.py`, línea 30: `OAuth2PasswordBearer(tokenUrl="/api/auth/login")`
  → `tokenUrl="/api/v1/auth/login"` — cambio funcional, no cosmético: esto determina la URL
  que Swagger UI usa para el flujo de login interactivo en `/docs`.

**Frontend — decisión de diseño 4.1.1 (ver también el hallazgo de exploración al inicio del
documento).** Dos formas de introducir el prefijo de versión en el frontend:

  - **(A)** Dejar `lib/api.ts` como está (baseURL = raíz del backend) y hacer un
    find-and-replace de `/api/` → `/api/v1/` en las ~45 ocurrencias literales de los 15
    archivos identificados.
  - **(B)** Centralizar el prefijo de versión en `frontend/lib/api.ts`
    (`baseURL: `${process.env.NEXT_PUBLIC_API_URL}/api/v1`}`) y despojar los ~45 call sites
    del prefijo `/api/`, dejándolos relativos (`/accounts/`, `/transactions/`, etc.).

  **Se recomienda (B).** Razón: (A) dejaría el número de versión disperso en 15 archivos, así
  que la próxima vez que exista un `/api/v2/` (o incluso un cambio menor de convención de
  rutas) hay que volver a tocar los mismos 15 archivos. (B) reduce ese costo futuro a un solo
  archivo (`lib/api.ts`), que es exactamente donde `CLAUDE.md` ya documenta que vive "la única
  instancia de Axios". El costo de (B) es el mismo esfuerzo mecánico una vez (hay que tocar
  los mismos 15 archivos igual, para quitar el prefijo `/api/` en vez de agregar `/v1`), así
  que no hay ninguna razón real para preferir (A).

  **Archivos concretos a tocar (frontend), todos con el patrón `/api/` → ``  al inicio de la
  ruta):**
  `frontend/lib/api.ts` (línea 4 `baseURL`, línea 58 refresh call),
  `frontend/lib/hooks/useCurrentUser.ts`, `frontend/lib/hooks/useUserPreferences.ts`,
  `frontend/app/(auth)/login/page.tsx`, `frontend/app/(auth)/register/page.tsx`,
  `frontend/app/(dashboard)/page.tsx`, `frontend/app/(dashboard)/accounts/page.tsx`,
  `frontend/app/(dashboard)/accounts/[id]/page.tsx`,
  `frontend/app/(dashboard)/categories/page.tsx`,
  `frontend/app/(dashboard)/categories/[id]/page.tsx`,
  `frontend/app/(dashboard)/budgets/page.tsx`,
  `frontend/app/(dashboard)/transactions/page.tsx`,
  `frontend/app/(dashboard)/analytics/page.tsx`,
  `frontend/components/Sidebar.tsx`, `frontend/components/ThemeToggle.tsx`,
  `frontend/components/modals/TransactionModal.tsx`,
  `frontend/components/modals/QuickTransactionModal.tsx`.

  Ejecutar como un sed acotado al patrón exacto (`s#/api/#/#g` dentro de los literales de
  `api.get/post/put/patch/delete(...)`) y revisar el diff completo a mano — el patrón es
  consistente pero un sed ciego sobre todo el árbol podría tocar strings no relacionados
  (ninguno detectado en la búsqueda hecha, pero revisar igual).

**Documentación:** por convención cruzada de `CLAUDE.md` ("si cambias un contrato de API
compartido, actualiza `backend/docs/API_REFERENCE.md` y `frontend/docs/API_CONTRACT.md` en el
mismo cambio"), este es exactamente ese caso — actualizar ambos documentos con el nuevo
prefijo en la misma PR que haga el cambio de código.

**Dependencias:** técnicamente ninguna respecto a Alembic, pero debe ir **antes** de 2.1/2.2
(los endpoints nuevos de password reset / email verification deben nacer ya en `/api/v1/`,
no crearse en `/api/` para moverlos después) y antes de finalizar el suite de pytest de la
tarea 4.2 (para no escribir los tests contra rutas que van a cambiar).

**Testing:** el suite de pytest de 4.2 se escribe directamente contra `/api/v1/...` — no hace
falta un test dedicado a "la versión existe", basta con que todos los tests de auth y
transacciones usen las rutas versionadas.

---

### 4.2 Tests del módulo contable y de autenticación (pytest + httpx)

**Alcance explícito** (el ROADMAP lo acota a propósito: "no cobertura completa: solo la
lógica que mueve dinero y la que da acceso"). No se recomienda expandir el alcance a
`accounts.py`/`categories.py` completos en esta tarea — sí vale la pena, sin embargo, incluir
el caso de la unique constraint de `budgets` (tarea 1.4) porque es lógica de integridad
contigua a "lo que mueve dinero" y ya quedó identificada como necesaria de testear ahí.

**Archivos a crear:**
- `backend/requirements.txt` — agregar `pytest`, `httpx` (no está como dependencia directa
  hoy — FastAPI la necesita para `TestClient` pero no está listada explícitamente en
  `requirements.txt`, verificar y fijar versión), opcionalmente `pytest-cov`.
- `backend/pyproject.toml` — agregar sección:
  ```toml
  [tool.pytest.ini_options]
  testpaths = ["tests"]
  ```
- `backend/tests/__init__.py` (vacío).
- `backend/tests/conftest.py` — fixtures:
  - `engine` (session-scoped): SQLite en memoria, `create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)` + `Base.metadata.create_all()`.
    Ver decisión 4.2.1 sobre por qué SQLite y no Postgres para estos tests.
  - `db_session` (function-scoped): abre una sesión nueva por test, hace rollback/drop al
    final para aislar tests entre sí.
  - `client` (function-scoped): `TestClient(app)` con `app.dependency_overrides[get_db]`
    apuntando a la sesión de test, no a `SessionLocal` real.
  - `test_user` / `auth_headers`: helper que registra un usuario vía
    `POST /api/v1/users/`, hace login vía `POST /api/v1/auth/login`, y devuelve
    `{"Authorization": f"Bearer {access_token}"}` listo para inyectar en los tests que lo
    necesiten.
  - Factories mínimas para crear cuenta y categoría de prueba (reutilizando los endpoints
    reales vía `client`, no insertando directo en la sesión — así los tests también validan
    el flujo HTTP completo, no solo el ORM).
- `backend/tests/test_transactions.py` — casos mínimos:
  - Crear transacción `income` incrementa `Account.balance` en el monto exacto.
  - Crear transacción `expense` decrementa `Account.balance` en el monto exacto.
  - Eliminar una transacción revierte el impacto exacto sobre `Account.balance`
    (`transactions.py:120-138`).
  - Editar una transacción cambiando el monto ajusta el balance por el delta neto, no por el
    monto completo dos veces (`transactions.py:175-196` — la lógica de `net_delta` cuando
    `cuenta_vieja.id == cuenta_nueva.id`).
  - Editar una transacción moviéndola de cuenta revierte el impacto en la cuenta vieja y
    aplica el impacto completo en la cuenta nueva (`transactions.py:186-196`).
  - Crear/editar/eliminar una transacción de una cuenta ajena devuelve 404, no 500 ni éxito
    silencioso (ownership checks ya existentes, pero sin test).
  - Crear una transacción con `category_id` de otro usuario (no del sistema, no propia)
    devuelve 404.
  - **Bug conocido documentado en `docs/TODO.md`:** `actualizar_transaccion` no actualiza
    `currency` al mover una transacción entre cuentas de distinta moneda — este test debe
    **fallar hoy** (test que documenta el bug, marcado `xfail` o simplemente escrito para que
    falle y quede visible en el suite) hasta que Fase 10 lo corrija; no es responsabilidad de
    Fase 7 arreglarlo, pero si el test ya existe cuando alguien lo arregle en Fase 10, el
    fix queda validado gratis.
- `backend/tests/test_budgets.py`:
  - Unique constraint: crear dos presupuestos idénticos (misma categoría/mes/año) devuelve
    400 en el segundo, no 500, y no crea una fila duplicada (test directo del constraint de
    1.4, insertando por debajo del check de Python si es necesario para probar la constraint
    de DB en sí, no solo el chequeo de aplicación).
  - Progreso de presupuesto calcula `spent`/`percentage` correctamente contra transacciones
    reales del mes.
- `backend/tests/test_auth.py`:
  - Registro: email duplicado devuelve 400; contraseña débil devuelve 422 (política de 2.3).
  - Login: credenciales correctas devuelven access + refresh token; credenciales incorrectas
    devuelven 403 (no 401 — así está hoy en `auth.py:27-36`, documentar el código real, no
    "corregirlo" silenciosamente en el test).
  - Refresh: rota el refresh token (el usado queda `revoked_at` no nulo, se emite uno nuevo);
    un refresh token ya usado no puede reutilizarse (`auth.py:60-71`).
  - Logout: revoca el refresh token; un logout con un refresh token ya inválido no rompe
    (`auth.py:91-106`, hoy es un no-op silencioso si `stored` es `None` — confirmar que ese
    es el comportamiento deseado, documentarlo con el test).
  - Rate limit de login: 6ª request en un minuto devuelve 429.
  - `get_current_user` rechaza un token con firma inválida, un token expirado, y un token con
    `sub` de un usuario que ya no existe.
  - (Si 2.1/2.2/2.5 ya están implementadas para cuando se escriba este archivo) password
    reset end-to-end, email verification end-to-end, TTL de 15 min del access token.

**Decisión de diseño 4.2.1 — SQLite en memoria para tests, no Postgres real.** El alcance de
Fase 7 son transacciones y auth, ninguno de los cuales depende de comportamiento
Postgres-específico (a diferencia de `dashboard.py`, que si bifurca por dialecto —
`to_char` vs `strftime`, líneas 155-161 — pero ese archivo está fuera del alcance de esta
tarea). SQLite en memoria da tests rápidos, sin necesidad de levantar un contenedor Postgres
extra para correr `pytest`, y sin depender de que Docker esté corriendo para poder testear.
Si en una fase futura se decide testear `dashboard.py` (fuera de Fase 7), ese suite sí
necesitará un fixture de Postgres real (ej. vía `testcontainers`) para cubrir la rama
`to_char`, momento en el que vale la pena introducir esa dependencia — no antes.

**Dependencias:** debe ir después de 4.1 (rutas ya versionadas) y, para los casos de password
reset/verificación/TTL, después de 2.1/2.2/2.5 respectivamente — pero el núcleo de
`test_transactions.py`/`test_budgets.py`/las partes de `test_auth.py` que no tocan esas
features nuevas pueden escribirse en paralelo, tan pronto como 4.1 esté mergeado.

**Nota de seguimiento (no ejecutar en este spec):** una vez que este suite exista,
`CLAUDE.md` debe actualizarse — hoy dice explícitamente "No hay comando de typecheck o test
configurado — ninguno existe en este repo todavía", lo cual dejaría de ser cierto. Ese cambio
de documentación queda fuera del alcance de este spec (que no debe tocar `CLAUDE.md`) pero
debe hacerse en la misma PR que introduzca el suite.

---

## Resumen de archivos tocados por sección

| Sección | Backend | Infra/DevOps | Frontend |
|---|---|---|---|
| 1.1 Alembic | `main.py`, `requirements.txt`, `alembic/*` (nuevo) | `Dockerfile`, `docker-compose.dev.yml` | — |
| 1.2 `preferred_theme` | (incluido en 1.1) | — | — |
| 1.3 Índices | `models/models.py` | — | — |
| 1.4 Unique budgets | `models/models.py`, `api/budgets.py` | — | — |
| 1.5 NOT NULL FKs | `models/models.py` | — | — |
| 2.1 Password reset | `core/email.py` (nuevo), `models/models.py`, `api/auth.py`, `schemas/schemas.py` | variables de entorno de email | — |
| 2.2 Verificación email | `models/models.py`, `api/users.py`, `api/auth.py` | — | — |
| 2.3 Política contraseñas | `schemas/schemas.py` | — | — |
| 2.4 Rate limit registro/recuperación | `api/users.py`, `api/auth.py` | — | — |
| 2.5 Logout TTL | `core/security.py` | — | revisar `lib/api.ts` (concurrencia de refresh) |
| 2.6 Rate limit distribuido | `core/rate_limit.py` (diferido) | `docker-compose.yml` (Redis, diferido) | — |
| 3.1 Backup | — | `scripts/backup.sh` (nuevo) | — |
| 3.2 Secretos | — | `docker-compose.yml`, `.env.example` (raíz, nuevo), `.gitignore` | — |
| 3.3 CORS | `main.py` | `docker-compose.yml` (env var) | — |
| 3.4 Logging | `core/logging_config.py` (nuevo), `main.py`, `api/dashboard.py` | — | — |
| 4.1 Versionado | `main.py`, `core/security.py` | — | `lib/api.ts` + 15 archivos con rutas literales |
| 4.2 Tests | `tests/*` (nuevo), `requirements.txt`, `pyproject.toml` | — | — |
