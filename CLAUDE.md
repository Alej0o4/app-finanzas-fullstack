# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Oikos — a multi-currency personal-finance web app. FastAPI backend, Next.js App Router frontend, PostgreSQL database.

**As of 2026-08-22 the project pivoted from "single-user personal app" to a product anyone can use.** This invalidated three previously-out-of-scope decisions, which are now in scope: **Alembic migrations, automated testing, and API versioning**. Read `docs/ROADMAP.md` before proposing architecture — it records the pivot, the decisions taken, and the phased plan.

The central conceptual shift: the current app is **stock**-based (accounts hold balances; the dashboard answers *"how much do I have?"*). The new MVP is **flow**-based (the dashboard answers *"how much did I spend this month and what's left?"*). Both coexist — account balances stay visible in a secondary view — but the dashboard's headline figure becomes monthly flow (`monthly_income − monthly expenses`).

There are still no automated tests in the repo. That is now tracked as a blocker, not an accepted tradeoff.

## Commands

### Run (Docker, recommended)

```sh
docker compose up -d --build                                          # production
docker compose -f docker-compose.yml -f docker-compose.dev.yml up      # dev, hot-reload
docker compose logs -f backend                                        # logs
docker compose exec backend python -c "from app.core.seed import run_seed; run_seed()"  # seed data
```

### Run (without Docker)

```sh
cd backend && uvicorn app.main:app --reload --host 0.0.0.0   # needs backend/.env with SECRET_KEY
cd frontend && pnpm dev                                       # pnpm, not npm
```

### Lint / format

```sh
cd backend && ruff check .    && ruff format .    # backend
cd frontend && pnpm lint      && pnpm format       # frontend (eslint + prettier)
```

There is no typecheck command configured — none exists in this repo yet.

### Test

```sh
cd backend && pytest          # full suite (SQLite in-memory, no Docker/Postgres needed)
cd backend && pytest -v       # verbose
cd backend && pytest --cov    # with coverage (pytest-cov)
```

### Seed data

`python -c "from app.core.seed import run_seed; run_seed()"` from `backend/` (venv active) — creates 3 accounts, 45 transactions, 6 budgets under `test@test.com` / `testpass123`.

## Architecture

### Backend (`backend/app/`)

Thin layered structure, **no service layer** (`app/services/` doesn't exist yet — business logic lives directly in routers, by design at current scale):

- `main.py` — assembles FastAPI app, CORS, routers, and runs startup-time DB migrations (see below).
- `core/` — `database.py` (SQLAlchemy engine/session, PostgreSQL via `DATABASE_URL` env var, falls back to SQLite), `security.py` (JWT + bcrypt), `rate_limit.py` (slowapi `Limiter` instance), `seed.py`.
- `models/models.py` — all 6 SQLAlchemy models in one file (User, Account, Category, Transaction, Budget, RefreshToken).
- `schemas/schemas.py` — all Pydantic schemas in one file.
- `api/` — one router module per domain (auth, users, accounts, categories, transactions, budgets, dashboard, preferences).

**No Alembic yet.** Schema evolves via `Base.metadata.create_all()` at startup plus ad-hoc runtime migrations in `main.py`: `_ensure_user_preference_columns()` / `_ensure_category_icon_column()` / `_ensure_account_highlighted_column()` do incremental `ALTER TABLE ADD COLUMN`, and a legacy-category-rename step runs on every boot. **Adopting Alembic is now Phase 7 and blocks the rest of the roadmap** (every later phase adds columns). Note the known gap: `_ensure_user_preference_columns()` never adds `preferred_theme` even though the model declares it.

Auth flow: `OAuth2PasswordBearer`, login takes email in the `username` field, JWT (`sub=user_id`) expires in 60 min, opaque refresh token (hashed in DB, 30-day expiry) rotates via `/api/auth/refresh`, login is rate-limited to 5 req/min via slowapi.

Money is always `Decimal` in schemas and `Numeric(14,2)` in models — never float.

**Backend is the source of truth for all financial calculations** (account balances, budget progress, dashboard aggregates). The frontend must never recompute these.

### Frontend (`frontend/`)

Next.js App Router with two route groups: `app/(auth)/` (login/register, minimal layout, no sidebar) and `app/(dashboard)/` (the authenticated shell — sidebar + all domain pages: dashboard root, `analytics/`, `transactions/`, `accounts/[id]`, `categories/[id]`, `budgets/`).

State layering is intentional and split three ways — don't blur these:
- **TanStack Query** — all server state. `QueryProvider` creates one `QueryClient` for the session (`staleTime` 1 min, `refetchOnWindowFocus` off). Mutations must invalidate related queries (see `frontend/docs/STATE_AND_FETCHING.md` for the key/invalidation map).
- **Zustand** (`store/useUiStore.ts`) — UI-only state (currently just sidebar open/collapsed). Not for server data.
- **`useState`** — local form/modal state.

`lib/api.ts` is the single Axios instance: injects `Authorization: Bearer <jwt>` from `localStorage` on every request, clears the token and redirects to `/login` on 401. `NEXT_PUBLIC_API_URL` selects the backend target (defaults to `http://localhost:8000`).

Import alias `@/*` resolves to the frontend root.

### Cross-cutting conventions

- If you change a shared API contract, update **both** `backend/docs/API_REFERENCE.md` and `frontend/docs/API_CONTRACT.md` in the same change.
- Categories with `user_id = NULL` are system-base categories — never editable or deletable via the API, seeded at startup.
- CORS is driven by the `ALLOWED_ORIGINS` env var plus a regex allowing Tailscale IPs (100.x.x.x) — the app is deployed for private/personal access via Tailscale, not the public internet, which is why some security tradeoffs (JWT in `localStorage`) are accepted for now (see `docs/TODO.md`).

## Where to look for more detail

This repo maintains its own detailed docs — check them before inferring behavior from code alone:

- `backend/docs/ARCHITECTURE.md`, `frontend/docs/ARCHITECTURE.md` — full architecture writeups.
- `backend/docs/BUSINESS_RULES.md` — domain invariants (ownership checks, deletion guards, budget uniqueness, etc.).
- `backend/docs/API_REFERENCE.md`, `frontend/docs/API_CONTRACT.md` — endpoint/payload contracts.
- `frontend/docs/STATE_AND_FETCHING.md` — React Query key/invalidation patterns.
- `frontend/docs/COMPONENTS_GUIDE.md`, `frontend/docs/UI_SYSTEM.md` — reusable components and visual tokens.
- `docs/TODO.md` — technical debt and confirmed bugs, tagged by urgency, with resolution dates. Reprioritized 2026-08-22 for the multi-user pivot.
- `docs/ROADMAP.md` — **read this first for anything architectural.** Records the 2026-08-22 pivot, the five MVP components, the phased plan (Phases 7–14), the prioritized backlog, and what remains genuinely out of scope (broker integrations, credit-card rewards engines, dynamic themes, i18n).
