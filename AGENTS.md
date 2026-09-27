# AGENTS.md — Oikos

Instrucciones para agentes de código (Claude Code, Codex, OpenCode) que trabajan en este repo.
**Este archivo es la fuente única**: `CLAUDE.md` solo lo importa. Cómo está armado el harness
(skills, hooks, subagentes, MCP) está en [docs/agents/harness.md](docs/agents/harness.md).

## Proyecto

Oikos — app web de finanzas personales multi-moneda. Backend FastAPI, frontend Next.js App
Router, base de datos PostgreSQL.

**El 2026-08-22 el proyecto pasó de "app personal de un solo usuario" a producto para
cualquier persona, y el 2026-09-19 volvió atrás.** Oikos no se va a lanzar, promocionar ni
abrir a usuarios externos en el futuro previsible: es una herramienta de finanzas personales
de su único dueño/desarrollador. La vuelta **no** deshace la primera arquitectónicamente: las
migraciones con Alembic, el testing automatizado y el versionado de API siguen en scope porque
hacen el código más fácil de extender, no por un modelo de amenazas multi-usuario. Lo que sí
cambia es la prioridad: **el hardening de seguridad, las features de auth y la resistencia a
abuso dejan de perseguirse activamente.** El baseline entregado hasta la Fase 26 (ver abajo) se
considera suficiente para un solo usuario de confianza en un despliegue personal — no proponer
trabajo nuevo de seguridad/auth salvo que algo esté roto de verdad o el dueño lo pida. Por
defecto, invertir el esfuerzo en features que mejoren el registro y el análisis de gastos. Leer
`docs/ROADMAP.md` (backlog actual) y `docs/CHANGELOG.md` (historia fase a fase) antes de
proponer arquitectura.

El cambio conceptual central de la primera vuelta se mantiene: la app original se basa en
**stock** (las cuentas tienen saldos; el dashboard responde *"¿cuánto tengo?"*). El MVP
construido en las Fases 8-15 se basa en **flujo** (el dashboard responde *"¿cuánto gasté este
mes y cuánto me queda?"*). Ambos conviven — los saldos de cuentas siguen visibles en una vista
secundaria — pero la cifra principal del dashboard es el flujo mensual
(`monthly_income − gastos del mes`).

**Las Fases 0–31 están completas** (2026-07-06 a 2026-09-27) — ver `docs/CHANGELOG.md` para la
historia completa y `docs/specs/fase_NN_spec.md` para el detalle de implementación de cada
fase. En producción, no solo planeado: el dashboard de flujo, alertas de presupuesto + push
notifications, el resumen semanal, el onboarding de 3 minutos, atajos móviles con API keys,
analytics por cuenta, un sistema de categorías personalizable, email transaccional con marca,
login con Google OAuth, ajustes de cuenta self-service (moneda + baja), una capa de
servicios/schemas/excepciones de dominio (`app/services/ledger.py`, `app/schemas/*`,
`app/core/exceptions.py` — la capa de excepciones cubre todos los routers desde la Fase 28, no
solo un piloto) y sesión en cookies `httpOnly` con protección CSRF (Fase 26). Las Fases 27–28
(2026-09-19) cerraron la última deuda de modularidad abierta — `transactions/page.tsx`
descompuesto en subcomponentes, `DomainError` en todo el repo — a propósito, antes de retomar el
backlog de features (ver `docs/ROADMAP.md`). La Fase 29 (2026-09-26) lo retomó: el dashboard se
navega por mes (`?month=YYYY-MM`, respaldado por `?year=&month=` opcionales en
`GET /dashboard/summary` y `/budgets-progress`), Analytics por semana/mes/año (`?ref=`), y ambos
tienen selector de moneda. La Fase 30 (2026-09-26) alineó `/transactions` a la misma semana
calendario (chip "Esta semana", UTC) y movió los totales KPI de Analytics al servidor:
`GET /dashboard/cashflow-series` ahora devuelve un objeto
`{ buckets, total_income, total_expense, net }`, no una lista. La Fase 31 (2026-09-27) corrigió
los hallazgos del primer QA: `PUT`/`DELETE /transactions` con row-lock, `422` por rango de
montos, rangos de mes semiabiertos, el balance de flujo del dashboard es siempre ingreso real −
gasto real (`monthly_income` es solo una referencia visual), y el override de Docker para dev
queda aislado de producción.

Algunos hechos operativos de esa historia siguen vigentes hoy, no son solo registro:

- **El login con Google está caído en producción** — Google Cloud deshabilitó el cliente OAuth
  (`disabled_client`, 2026-09-19), probablemente un falso positivo antifraude automático sobre un
  proyecto personal nuevo; hay una apelación pendiente. Es un bug real que afecta el uso
  personal (el login diario del dueño), no un ítem de hardening — ver `docs/TODO.md` 🟠 para el
  workaround en uso y el arreglo si la apelación falla. Aparte, `GOOGLE_CLIENT_ID` /
  `NEXT_PUBLIC_GOOGLE_CLIENT_ID` tienen que estar configurados por entorno o `GoogleAuthButton`
  no renderiza nada en silencio y `/auth/google` devuelve `503`.
- **El rate limiting distribuido no se va a implementar** — `slowapi` es en memoria y de un solo
  worker, lo cual ya estaba bien con el plan multi-usuario y ahora lo está para siempre: el
  despliegue no va a escalar más allá de un worker/réplica para una app de un solo usuario.
  Antes "diferido", ahora fuera de scope — ver `docs/ROADMAP.md`.
- **La sesión funciona con cookies `httpOnly` (Fase 26)** — `access_token` (HttpOnly, 15 min),
  `refresh_token` (HttpOnly, Path `/api/v1/auth`, 30 días) y un `csrf_token` no-HttpOnly para el
  patrón double-submit en mutaciones (`X-CSRF-Token`). No hay JWT en `localStorage`. Los
  clientes no-browser (curl, API keys `oikos_pat_...`) siguen usando el header `Authorization`
  como camino principal. Spec: `docs/specs/fase_26_spec.md`. Es el baseline de seguridad sobre
  el que está parado el proyecto — no la base para más hardening, solo donde se detuvo.
- Una vulnerabilidad crítica de toma de cuenta vía Google OAuth (auto-link silencioso de una
  contraseña plantada por un atacante) se encontró en la auditoría del 2026-09-15 y se corrigió
  en la Fase 23 — ver `docs/CHANGELOG.md`. Hallazgos de esa clase son la razón por la que el
  baseline se subió a un nivel razonable antes de despriorizar la seguridad, no evidencia de que
  falte más hardening.

**Tailscale Funnel se activó el 2026-09-06** — Oikos es accesible desde internet público
(`https://<host>.<tailnet>.ts.net`), no solo desde IPs del tailnet, aunque en la práctica lo usa
una sola persona. Esa exposición fue la razón por la que el tradeoff de JWT en `localStorage` no
se podía diferir indefinidamente — ya está cerrado: el login de producción se consolidó en el
dominio HTTPS del Funnel (`COOKIE_SECURE=true` por defecto), y el acceso por navegador directo a
la IP del tailnet queda deprecado para cookies de sesión, no para API keys (Decisión B10/F6 de
`docs/specs/fase_26_spec.md`).

## Comandos

### Correr (Docker, recomendado)

Necesita un `.env` en la raíz (copiar de `.env.example`) con `POSTGRES_PASSWORD` y `SECRET_KEY` —
`docker compose up` falla de inmediato si falta alguno, sin fallback silencioso a un valor
conocido. Las variables de email (`EMAIL_PROVIDER`, `SMTP_*`) son opcionales y por defecto
`EMAIL_PROVIDER=console` (loguea el email en vez de enviarlo — ver `docs/TODO.md`).

```sh
docker compose up -d --build                                          # producción
docker compose -f docker-compose.yml -f docker-compose.dev.yml up      # dev, hot-reload — proyecto separado `oikos-dev`
docker compose logs -f backend                                        # logs (producción)
docker compose -p oikos-dev exec backend python -c "from app.core.seed import run_seed; run_seed()"  # seed — SOLO DEV
docker compose exec backend python -c "from app.core.database import SessionLocal; from app.core.user_deletion import delete_user_by_email; db = SessionLocal(); print(delete_user_by_email(db, 'email@ejemplo.com')); db.close()"  # borrar usuario por email (Fase 21, Decisión 21.2.5)
```

**El proyecto compose por defecto en la máquina de despliegue ES producción** (Tailscale Funnel
hace proxy a su `:3000`/`:8000`). El override de dev (Fase 31, I1) está aislado: nombre de
proyecto `oikos-dev`, su propio volumen de DB (`oikos-dev_pgdata`), puertos **`:3001`
(frontend) / `:8001` (backend)**, `EMAIL_PROVIDER=console`, `FRONTEND_URL`/`ALLOWED_ORIGINS` en
`localhost:3001`, `restart: "no"` y sin servicio `backup` (queda detrás de
`profiles: ["backup"]`). Cualquier `exec`/`logs`/`down` contra dev necesita `-p oikos-dev` (o
ambos `-f`) — **sin eso el comando le pega a producción**, que es como el usuario del seed
terminó una vez en la DB real (QA-002). Las cookies no distinguen puertos, así que dev y
producción abiertos en el mismo navegador sobre `localhost` se pisan la sesión; producción se
usa por el dominio del Funnel, así que en la práctica no chocan. `pnpm gen:types` lee del backend
de dev (`:8001`, sobrescribible con `GEN_TYPES_API_URL`), nunca de producción.

### Correr (sin Docker)

```sh
cd backend && uvicorn app.main:app --reload --host 0.0.0.0   # necesita backend/.env con SECRET_KEY
cd frontend && pnpm dev                                       # pnpm, no npm
```

### Lint / formato

```sh
cd backend && ruff check .    && ruff format .    # backend
cd frontend && pnpm lint      && pnpm format       # frontend (eslint + prettier)
```

No hay comando de typecheck configurado — todavía no existe en este repo. El `pre-commit`
versionado (`scripts/git-hooks/pre-commit`, se activa con `scripts/setup-agent-harness.sh`)
corre ruff/eslint/prettier sobre lo que está en stage.

### Tests

```sh
cd backend && pytest          # suite completa (SQLite en memoria, sin Docker/Postgres)
cd backend && pytest -v       # verbose
cd backend && pytest --cov    # con cobertura (pytest-cov)
```

Postgres (Fase 31, T1): con `TEST_DATABASE_URL` definido, la suite corre contra Postgres
(`drop_all`/`create_all` por sesión) y además corre los tests `@pytest.mark.postgres`
(concurrencia real, overflow de `Numeric`, timezone de sesión — se saltan solos en SQLite). La
suite **aborta** si el nombre de la DB no contiene `test`. Usar un contenedor descartable, nunca
el Postgres de compose:

```sh
docker run -d --rm --name oikos-test-pg -e POSTGRES_PASSWORD=test -e POSTGRES_DB=oikos_test \
  -p 127.0.0.1:5433:5432 --tmpfs /var/lib/postgresql/data postgres:16-alpine
cd backend && TEST_DATABASE_URL=postgresql://postgres:test@127.0.0.1:5433/oikos_test pytest
docker stop oikos-test-pg
```

### Datos de prueba (seed)

Solo contra dev o una DB descartable — nunca producción.
`python -c "from app.core.seed import run_seed; run_seed()"` desde `backend/` (venv activo,
`DATABASE_URL` apuntando a una DB que no sea producción), o el comando `-p oikos-dev` de arriba —
crea 3 cuentas, 45 transacciones y 6 presupuestos bajo `test@test.com` / `testpass123`.

## Arquitectura

### Backend (`backend/app/`)

Estructura en capas delgada con una capa de servicios naciente (`app/services/ledger.py`,
agregada en la Fase 25 — el único módulo por ahora; la mayoría de la lógica de negocio sigue
directamente en los routers, a propósito a esta escala):

- `main.py` — arma la app FastAPI, CORS (ver abajo), logging estructurado + middleware de
  request-ID, headers de seguridad, y monta cada router bajo `/api/v1/...`.
- `core/` — `database.py` (engine/sesión SQLAlchemy, PostgreSQL vía la variable `DATABASE_URL`,
  con fallback a SQLite), `security.py` (JWT + bcrypt), `rate_limit.py` (instancia `Limiter` de
  slowapi), `email.py` (envío de email enchufable, ver flujo de auth abajo), `logging_config.py`
  (logging JSON estructurado a stdout), `exceptions.py` (`DomainError` + una taxonomía genérica
  de subclases por status code — `BadRequestError`/`UnauthorizedError`/`ForbiddenError`/
  `NotFoundError`/`ConflictError`/`ValidationError`/`InternalServerError`/
  `ServiceUnavailableError`, más `AccountNotFoundError`/`CategoryNotFoundError`; empezó como
  piloto en la Fase 25 y se extendió a todos los routers en la Fase 28 — todo router lanza
  subclases de `DomainError`, no `HTTPException` directo), `seed.py`.
- `models/models.py` — 13 modelos SQLAlchemy en un archivo (User, Account, Category,
  HiddenCategory, Transaction, Budget, RefreshToken, PasswordResetToken,
  EmailVerificationToken, IdempotencyKey, Notification, PushSubscription, ApiKey).
- `schemas/` — schemas Pydantic divididos por dominio desde la Fase 25 (`accounts.py`,
  `api_keys.py`, `auth.py`, `budgets.py`, `categories.py`, `common.py`, `dashboard.py`,
  `notifications.py`, `push.py`, `transactions.py`, `users.py`); `schemas.py` se mantiene como
  shim de re-export para que el `from app.schemas import schemas` de cada router siga
  funcionando sin cambios.
- `services/ledger.py` — la lógica compartida de delta de saldo de cuenta que usan
  `crear_transaccion`/`eliminar_transaccion`/`actualizar_transaccion` (Fase 25 §25.1), extraída
  de tres copias pegadas.
- `api/` — un módulo router por dominio (auth, users, accounts, categories, transactions,
  budgets, dashboard, preferences).

**Alembic gestiona el esquema** (`backend/alembic/`, migraciones en `backend/alembic/versions/`).
El `CMD` de Docker corre `alembic upgrade head` antes de arrancar uvicorn (ver `Dockerfile` /
`docker-compose.dev.yml`). Sin Docker: con el venv activo, correr `alembic upgrade head` desde
`backend/` antes del primer arranque o después de traer un cambio que agregue una migración. Las
viejas funciones ad-hoc `_ensure_*_column()` y la migración legacy de categorías en cada arranque
ya no existen — los cambios de esquema pasan por `alembic revision --autogenerate`, revisado a
mano antes de commitear (skill `alembic-migration`).

Flujo de auth: `OAuth2PasswordBearer`, el login recibe el email en el campo `username`, el JWT
(`sub=user_id`) expira en **15 min** (bajado de 60 en la Fase 7 para que un token robado o
post-logout tenga una ventana corta — sin blacklist en servidor, ver
`docs/specs/fase_07_spec.md` §2.5.1), y un refresh token opaco (hasheado en DB, 30 días) rota vía
`/api/v1/auth/refresh`. Registro, login y pedidos de reset de contraseña tienen rate limit de
5 req/min vía slowapi (en memoria — suficiente para el despliegue de un solo worker).

Ciclo de vida de la cuenta (Fase 7): `POST /api/v1/auth/password-reset/request` + `.../confirm`
(token de un solo uso, 45 min, revoca todos los refresh tokens activos al confirmar, nunca revela
si un email está registrado) y `GET /api/v1/auth/verify-email` (token de un solo uso, 48 h).
**El login exige email verificado** (agregado el 2026-09-12, revirtiendo la decisión original de
la Fase 7) — `POST /api/v1/auth/login` devuelve `403` con `detail.code == "EMAIL_NOT_VERIFIED"`
para un usuario sin verificar, y `POST /api/v1/auth/resend-verification` (seguro contra
enumeración, 5 req/min) emite un token nuevo. El registro nunca falla ni se bloquea por el envío.
Ambos envían email vía `app/core/email.py`, enchufable con `EMAIL_PROVIDER`: `console` (por
defecto — loguea el email/link en vez de enviarlo, sin credenciales) o `smtp` (envío real con
`smtplib`, necesita `SMTP_HOST`/`PORT`/`USER`/`PASSWORD`/`FROM_EMAIL`).
**`EMAIL_PROVIDER=smtp` se configuró y verificó de punta a punta contra el `.env` real del
despliegue el 2026-09-12** (Gmail + app password) — registro/verificación/reset con contraseña
funcionan en ese despliegue. Las credenciales viven solo en el `.env` gitignoreado del despliegue;
`backend/.env` (corridas locales sin Docker) no tiene variables SMTP, así que sin Docker se cae a
`EMAIL_PROVIDER=console` salvo que se agreguen ahí también. Las páginas de frontend que consumen
esos links están en `app/(auth)/forgot-password`, `reset-password`, `verify-email`.

El dinero es siempre `Decimal` en schemas y `Numeric(14,2)` en modelos — nunca float.

**El backend es la fuente de verdad de todos los cálculos financieros** (saldos de cuentas,
progreso de presupuestos, agregados del dashboard). El frontend nunca debe recalcularlos.

### Frontend (`frontend/`)

Next.js App Router con dos route groups: `app/(auth)/` (login, register, forgot-password,
reset-password, verify-email — layout mínimo, sin sidebar) y `app/(dashboard)/` (el shell
autenticado — sidebar + todas las páginas de dominio: raíz del dashboard, `analytics/`,
`transactions/`, `accounts/[id]`, `categories/[id]`, `budgets/`). Hay además una ruta autenticada
fuera de ambos grupos, `app/capture/` (`/capture`, la pantalla de captura post-login de la
Fase 10) — layout centrado minimalista como `(auth)`, sin sidebar/FAB, protegida por el hook
compartido `useRequireAuth` con un link explícito "Ver dashboard" para salir.

La separación del estado es intencional, en tres partes — no mezclarlas:

- **TanStack Query** — todo el estado de servidor. `QueryProvider` crea un `QueryClient` por
  sesión (`staleTime` 1 min, `refetchOnWindowFocus` apagado). Las mutaciones deben invalidar
  las queries relacionadas (ver `frontend/docs/STATE_AND_FETCHING.md` para el mapa de keys e
  invalidación). `frontend/lib/hooks/{useAccounts,useCategories,useTransactions}.ts` (Fase 25)
  envuelven el patrón repetido `useQuery`+`queryFn` de solo lectura — preferirlos sobre un
  `useQuery` inline para leer cuentas/categorías/transacciones; las mutaciones siguen inline en
  cada página.
- **Zustand** (`store/useUiStore.ts`) — estado solo de UI (hoy solo sidebar abierto/colapsado).
  No para datos de servidor.
- **`useState`** — estado local de formularios/modales.

`lib/api.ts` es la única instancia de Axios: `baseURL` es
`` `${NEXT_PUBLIC_API_URL}/api/v1` `` (por defecto `http://localhost:8000/api/v1`) — cada llamada
usa una ruta **relativa a eso** (p. ej. `api.get('accounts/')`, nunca `/api/...`; la Fase 7
centralizó el prefijo de versión aquí para que un futuro `/api/v2/` solo toque este archivo).
Usa `withCredentials: true` para que las cookies de sesión (`access_token` HttpOnly;
`csrf_token` legible por JS) viajen en cada request; el interceptor de request agrega
`X-CSRF-Token` en todo método que no sea `GET`/`HEAD`, y el de response redirige a `/login` ante
un 401 con un mutex/cola para que 401 concurrentes compartan una sola llamada de refresh
(`api.post('auth/refresh')`, sin body) en vez de disparar duplicados. Desde la Fase 26 ya no
lee/escribe JWT en `localStorage` ni pone `Authorization: Bearer` (ver
`docs/specs/fase_26_spec.md`).

El alias de import `@/*` resuelve a la raíz del frontend.

### Convenciones transversales

- Si cambias un contrato de API compartido, actualiza **ambos** `backend/docs/API_REFERENCE.md` y
  `frontend/docs/API_CONTRACT.md` en el mismo cambio.
- Las categorías con `user_id = NULL` son categorías base del sistema — nunca editables ni
  borrables vía la API, se siembran en el arranque.
- CORS se controla con la variable `ALLOWED_ORIGINS`. El regex de IPs de Tailscale (100.x.x.x)
  solo aplica con `ENABLE_TAILSCALE_CORS=true` (definido en `docker-compose.yml` para el
  despliegue actual) — dejarlo sin definir cuando la app salga de Tailscale, sin cambio de código
  (Fase 7 §3.3).
- `POSTGRES_PASSWORD` y `SECRET_KEY` son obligatorios para `docker compose up` (`.env` en la
  raíz, ver `.env.example`) — ya no hay fallback silencioso a un valor conocido; si falta uno, el
  arranque falla (Fase 7 §3.2).
- Los routers se mantienen delgados; extraer lógica a `app/services/` si crece.
- Los agentes **no editan archivos `.env`** (los hooks lo bloquean); las plantillas van en
  `.env.example`.

## Dónde buscar más detalle

Este repo mantiene su propia documentación detallada — revisarla antes de inferir comportamiento
solo desde el código:

- `docs/WORKFLOW.md` — **leer antes de empezar cualquier feature, fase o bugfix.** La secuencia de
  desarrollo: cuándo un cambio lleva spec, el flujo completo (`grilling` → `to-spec` →
  `analyze-spec` → implementar → `run-tests` → revisión de código → `analyze-spec cierre` → docs
  de cierre → PR) y el flujo corto para bugs.
- `docs/ROADMAP.md` — **leer primero para cualquier cosa arquitectónica.** Registra los cambios de
  enfoque, los cinco componentes del MVP, qué sigue abierto, el backlog priorizado y qué queda
  fuera de scope (integraciones con brokers, motores de recompensas de tarjetas, temas
  dinámicos, i18n). La historia fase a fase está en `docs/CHANGELOG.md`.
- `docs/TODO.md` — deuda técnica y bugs confirmados, etiquetados por urgencia, con fechas de
  resolución.
- `docs/specs/` — specs detalladas por fase (tareas a nivel de archivo, decisiones de diseño),
  escritas antes de implementar cada fase.
- `backend/docs/ARCHITECTURE.md`, `frontend/docs/ARCHITECTURE.md` — arquitectura completa.
- `backend/docs/BUSINESS_RULES.md` — invariantes de dominio (chequeos de ownership, guardas de
  borrado, unicidad de presupuestos, etc.).
- `backend/docs/API_REFERENCE.md`, `frontend/docs/API_CONTRACT.md` — contratos de endpoints y
  payloads.
- `frontend/docs/STATE_AND_FETCHING.md` — patrones de query keys e invalidación de React Query.
- `frontend/docs/COMPONENTS_GUIDE.md`, `frontend/docs/UI_SYSTEM.md` — componentes reutilizables y
  tokens visuales.

## Skills de agentes

Las skills viven en `.agents/skills/<nombre>/SKILL.md` (formato abierto Agent Skills, lo leen las
tres herramientas). Se invocan por nombre: `/nombre` en Claude Code y OpenCode, `$nombre` en
Codex, o implícitamente cuando la tarea coincide con la `description`. Donde una skill diga "call
the Skill tool with X", en cualquier herramienta significa "carga y sigue la skill X".

| Skill | Para qué |
|---|---|
| `grilling` | Interrogar una idea hasta que no quede ninguna decisión asumida (paso 2 del flujo). |
| `to-spec` | Sintetizar la conversación en `docs/specs/fase_NN_spec.md`. |
| `analyze-spec` | Chequeo de consistencia de una spec, antes de implementar y al cerrar la fase. |
| `run-tests` | Suite completa (pytest, ruff, eslint, prettier) — el sustituto manual de CI. |
| `alembic-migration` | Migración de Alembic para un cambio en `models.py`. |
| `tdd` | Desarrollo guiado por tests (red-green-refactor). |
| `codebase-design`, `improve-codebase-architecture` | Vocabulario y análisis de módulos profundos. |
| `graphify` | Construir/consultar el grafo de conocimiento del repo. |

### Issue tracker

Markdown local, no GitHub Issues pese al remoto de GitHub: specs en `docs/specs/fase_NN_spec.md`
(convención por fase), tickets/seguimiento en `.scratch/<feature>/`. Ver
`docs/agents/issue-tracker.md` — define además dos agregados de Oikos a la plantilla de
`to-spec` (marcadores `[NEEDS CLARIFICATION: …]` y un `## Orden de ejecución` etiquetado con
`[backend]`/`[frontend]`/`[P]`/`Depende de:`). Correr `analyze-spec` antes de implementar una
spec y otra vez al cerrar la fase.

### Docs de dominio

Contexto único: `CONTEXT.md` en la raíz + `docs/adr/` (ninguno existe todavía — se crean cuando
hagan falta, no por adelantado). Ver `docs/agents/domain.md`.

## graphify

Este proyecto tiene un grafo de conocimiento en `graphify-out/` con nodos centrales, estructura
de comunidades y relaciones entre archivos.

Cuando el usuario escriba `/graphify`, usar la skill `graphify` antes de hacer cualquier otra
cosa.

Reglas:

- Para preguntas sobre el código, primero correr `graphify query "<pregunta>"` cuando exista
  `graphify-out/graph.json`. Usar `graphify path "<A>" "<B>"` para relaciones y
  `graphify explain "<concepto>"` para conceptos puntuales. Devuelven un subgrafo acotado,
  normalmente mucho más chico que `GRAPH_REPORT.md` o la salida cruda de grep.
- Que `graphify-out/` tenga archivos modificados es esperable tras hooks o actualizaciones
  incrementales; no es razón para saltarse graphify. Solo saltarlo si la tarea trata de un grafo
  desactualizado/incorrecto o el usuario lo pide explícitamente.
- Si existe `graphify-out/wiki/index.md`, usarlo para navegación amplia en vez de recorrer el
  código crudo.
- Leer `graphify-out/GRAPH_REPORT.md` solo para revisiones amplias de arquitectura o cuando
  query/path/explain no alcancen.
- Después de modificar código, correr `graphify update .` para mantener el grafo al día (solo
  AST, sin costo de API).
