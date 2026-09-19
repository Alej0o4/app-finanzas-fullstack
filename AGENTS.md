# AGENTS.md — Oikos

App web de finanzas personales multi-moneda. Backend FastAPI + SQLAlchemy, frontend Next.js App Router + React 19 + TanStack Query + Zustand + Recharts + Tailwind CSS 4. PostgreSQL en Docker. 251 tests de backend (pytest), lint limpio (`ruff`).

> ⚠️ **Cambio de enfoque (2026-08-22 → revertido 2026-09-19).** El proyecto pasó de "app
> personal de un solo usuario" a producto para cualquier persona (2026-08-22), y **volvió a ser
> herramienta personal el 2026-09-19** — sin plan de publicarlo ni abrirlo a usuarios externos.
>
> Lo que **no** cambia con la vuelta: Alembic, testing y versionado de API siguen en scope (por
> mantenibilidad, no por multi-usuario), igual que la capa `app/services/`/`app/schemas/`/
> `app/core/exceptions.py`. Lo que **sí** cambia: seguridad/auth/hardening deja de ser foco
> activo — el baseline de la Fase 26 (cookies httpOnly + CSRF) se considera suficiente para un
> solo usuario de confianza. No proponer trabajo nuevo de seguridad salvo bug real o pedido
> explícito.
>
> El dashboard mide **flujo** (`ingreso mensual − gastos del mes`), no solo **stock** (saldo de
> cuentas); los saldos siguen visibles en vista secundaria.
>
> **Lee [docs/ROADMAP.md](docs/ROADMAP.md) antes de proponer arquitectura o features.**

## Startup

### Docker (recomendado)

```sh
# Producción — levantar todo (postgres + backend + frontend)
docker compose up -d --build

# Desarrollo — hot-reload, sin rebuilds
docker compose -f docker-compose.yml -f docker-compose.dev.yml up

# Ver estado
docker compose ps

# Logs
docker compose logs -f backend
```

### Sin Docker (alternativa)

```sh
# backend — requiere .env con SECRET_KEY (ya existe)
cd backend && uvicorn app.main:app --reload --host 0.0.0.0  # http://localhost:8000

# frontend
cd frontend && pnpm dev                          # http://localhost:3000
```

- El esquema se gestiona con Alembic (`alembic upgrade head` desde `backend/`) — ya no se crean tablas con `Base.metadata.create_all()` en el arranque (solo los tests lo usan sobre SQLite en memoria).
- Columnas de preferencias se agregan en runtime si no existen (`ALTER TABLE` incremental).
- Categorías base del sistema se siembran en startup (`user_id IS NULL`).
- Sesión de navegador vía cookies httpOnly (Fase 26): `access_token` (HttpOnly, Path=/, 15 min), `refresh_token` (HttpOnly, Path=`/api/v1/auth`, 30 días) y `csrf_token` (NO HttpOnly, para el patrón double-submit via header `X-CSRF-Token` en mutaciones). Ya no hay JWT en `localStorage`.
- El login/refresh rotan los cookies en su respuesta; logout y baja de cuenta los limpian (<code>Max-Age=0</code>). Los clientes no-browser (curl, API keys `oikos_pat_...`) siguen autenticando por header `Authorization`.

## Comandos

| Acción | Comando |
|--------|---------|
| Dev frontend | `pnpm dev` |
| Build frontend | `pnpm build` |
| Lint frontend | `pnpm lint` |
| Format frontend | `pnpm format` |
| Lint backend | `ruff check .` (desde `backend/`) |
| Format backend | `ruff format .` (desde `backend/`) |
| Backend (uvicorn) | `uvicorn app.main:app --reload --host 0.0.0.0` |
| Backend (Python) | `pip install -r requirements.txt` (venv activo) |
| Seed test data | `python -c "from app.core.seed import run_seed; run_seed()"` (venv activo, desde `backend/`) |
| Docker up | `docker compose up -d --build` |
| Docker dev (hot-reload) | `docker compose -f docker-compose.yml -f docker-compose.dev.yml up` |
| Docker logs | `docker compose logs -f backend` |
| Docker seed | `docker compose exec backend python -c "from app.core.seed import run_seed; run_seed()"` |
| Docker delete user | `docker compose exec backend python -c "from app.core.database import SessionLocal; from app.core.user_deletion import delete_user_by_email; db = SessionLocal(); print(delete_user_by_email(db, 'email@ejemplo.com')); db.close()"` — Fase 21, en el CLAUDE.md raíz |

No hay typecheck configurado. Tests: `pytest` desde `backend/` (SQLite en memoria, sin Docker). Formateadores: `ruff` (backend) + `prettier` (frontend).

> Para cargar datos de prueba multi-moneda con 3 cuentas y 45 transacciones, ejecuta el comando Seed. Credenciales: `test@test.com` / `testpass123`. Ver skill `seed-data`.

## Arquitectura

- Backend es fuente de verdad para saldos, presupuestos, agregados. **Frontend no recalcula métricas financieras.**
- State: React Query (servidor, staleTime 1 min, refetchOnWindowFocus=false) + Zustand (solo UI: sidebar) + useState (formularios/modales).
- Auth: JWT con `sub=user_id`, `access_token`/`refresh_token`/`csrf_token` en cookies httpOnly (Fase 26, ver Startup arriba); `Authorization: Bearer` sigue siendo el camino primario para clientes no-browser (curl, API keys). Login espera `username` (email) + `password`. Refresh token rotation.
- Preferencias de usuario: `preferred_currency` (COP), `preferred_locale` (es-CO), `preferred_theme` (dark) vía `GET/PATCH /api/users/me/preferences`.
- CORS configurado vía variable de entorno `ALLOWED_ORIGINS`.
- Rate limiting en login via `slowapi` (5 req/min, en memoria — distribuido queda fuera de scope, ver ROADMAP).
- Capa de servicios naciente: `app/services/ledger.py` (Fase 25) extrae la lógica contable compartida por `transactions.py`; la mayoría de la lógica de negocio de los otros 10 routers sigue inline (deuda técnica incremental, documentada en TODO.md). Capa de excepciones de dominio (`app/core/exceptions.py`) ya cubre los 10 routers (Fase 28, 2026-09-19) — todo `raise` de error de negocio usa `DomainError`/subclases, no `HTTPException` directo.
- DB: PostgreSQL en Docker (`postgres:16-alpine`), datos en volumen `pgdata`. Backend lee `DATABASE_URL` de variable de entorno.
- Frontend import alias `@/*` → raíz del proyecto.
- `pnpm` (no npm).

## Documentación relevante

- [Roadmap](docs/ROADMAP.md) — **empieza aquí.** Cambio de enfoque (2026-08-22 y 2026-09-19), los 5 componentes del MVP, historial de fases y backlog priorizado.
- [Deuda técnica y bugs](docs/TODO.md) — repriorizada el 2026-08-22 y de nuevo el 2026-09-19; incluye bugs confirmados en auditoría.
- [Reglas de negocio](backend/docs/BUSINESS_RULES.md) — invariantes de dominio.
- [API](backend/docs/API_REFERENCE.md) + [Contrato frontend](frontend/docs/API_CONTRACT.md) — endpoints y payloads.
- [Frontend: fetching y estado](frontend/docs/STATE_AND_FETCHING.md) — query keys y patrones de invalidación.
- [Frontend: componentes](frontend/docs/COMPONENTS_GUIDE.md) — piezas reutilizables.

## Convenciones

- Mutaciones deben invalidar queries relacionadas (ver STATE_AND_FETCHING.md).
- Categorías con `user_id IS NULL` no se editan ni eliminan.
- Si cambias un contrato compartido, actualiza doc backend + frontend.
- Los routers deben mantenerse delgados; extraer lógica si crece.
- Montos como `Decimal`/`Numeric(14,2)` tanto en modelos como en schemas.
