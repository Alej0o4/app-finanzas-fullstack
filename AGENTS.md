# AGENTS.md — Oikos

App web de finanzas personales. Backend FastAPI + SQLAlchemy, frontend Next.js App Router + React 19 + TanStack Query + Zustand + Recharts + Tailwind CSS 4. SQLite en desarrollo, sin tests automatizados aún.

## Startup

Backend primero, frontend después:

```sh
# backend — requiere .env con SECRET_KEY (ya existe)
cd backend && uvicorn app.main:app --reload     # http://localhost:8000

# frontend
cd frontend && pnpm dev                          # http://localhost:3000
```

- Backend crea tablas al arrancar (`Base.metadata.create_all()`) — sin Alembic.
- Columnas de preferencias se agregan en runtime si no existen (`ALTER TABLE` incremental).
- Categorías base del sistema se siembran en startup (`user_id IS NULL`).
- Token JWT expira a los 60 min; guardado en `localStorage` como `jwt_token`.
- Refresh token (30 días) para renovar sesión sin re-login; guardado en `localStorage` como `refresh_token`.

## Comandos

| Acción | Comando |
|--------|---------|
| Dev frontend | `pnpm dev` |
| Build frontend | `pnpm build` |
| Lint frontend | `pnpm lint` |
| Backend (uvicorn) | `uvicorn app.main:app --reload` |
| Backend (Python) | `pip install -r requirements.txt` (venv activo) |
| Seed test data | `python -c "from app.core.seed import run_seed; run_seed()"` (venv activo, desde `backend/`) |

No hay formateador, typecheck ni test configurados en ninguna capa.

> Para cargar datos de prueba multi-moneda con 3 cuentas y 45 transacciones, ejecuta el comando Seed. Credenciales: `test@test.com` / `testpass123`. Ver skill `seed-data`.

## Arquitectura

- Backend es fuente de verdad para saldos, presupuestos, agregados. **Frontend no recalcula métricas financieras.**
- State: React Query (servidor, staleTime 1 min, refetchOnWindowFocus=false) + Zustand (solo UI: sidebar) + useState (formularios/modales).
- Auth: `OAuth2PasswordBearer` → JWT con `sub=user_id`. Login espera `username` (email) + `password`. Refresh token rotation.
- Preferencias de usuario: `preferred_currency` (COP), `preferred_locale` (es-CO), `preferred_theme` (dark) vía `GET/PATCH /api/users/me/preferences`.
- CORS configurado vía variable de entorno `ALLOWED_ORIGINS`.
- Rate limiting en login via `slowapi` (5 req/min).
- Rutas FastAPI monolíticas (sin capa service); `backend/app/services/` vacío (deuda técnica).
- DB: SQLite (`backend/finanzas.db`), configurada para cambiar a PostgreSQL vía `psycopg2-binary`.
- Frontend import alias `@/*` → raíz del proyecto.
- `pnpm` (no npm).

## Documentación relevante

- [Reglas de negocio](backend/docs/BUSINESS_RULES.md) — invariantes de dominio.
- [API](backend/docs/API_REFERENCE.md) + [Contrato frontend](frontend/docs/API_CONTRACT.md) — endpoints y payloads.
- [Frontend: fetching y estado](frontend/docs/STATE_AND_FETCHING.md) — query keys y patrones de invalidación.
- [Frontend: componentes](frontend/docs/COMPONENTS_GUIDE.md) — piezas reutilizables.
- [Deuda técnica](TODO_TECH_DEBT.md) — atajos del MVP.
- [Roadmap](REFACTOR_ROADMAP.md) — plan de desarrollo priorizado.

## Convenciones

- Mutaciones deben invalidar queries relacionadas (ver STATE_AND_FETCHING.md).
- Categorías con `user_id IS NULL` no se editan ni eliminan.
- Si cambias un contrato compartido, actualiza doc backend + frontend.
- Los routers deben mantenerse delgados; extraer lógica si crece.
- Montos como `Decimal`/`Numeric(14,2)` tanto en modelos como en schemas.
