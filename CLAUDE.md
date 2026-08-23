# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Oikos — a multi-currency personal-finance web app. FastAPI backend, Next.js App Router frontend, PostgreSQL database.

**As of 2026-08-22 the project pivoted from "single-user personal app" to a product anyone can use.** This invalidated three previously-out-of-scope decisions, which are now in scope: **Alembic migrations, automated testing, and API versioning**. Read `docs/ROADMAP.md` before proposing architecture — it records the pivot, the decisions taken, and the phased plan.

The central conceptual shift: the current app is **stock**-based (accounts hold balances; the dashboard answers *"how much do I have?"*). The new MVP is **flow**-based (the dashboard answers *"how much did I spend this month and what's left?"*). Both coexist — account balances stay visible in a secondary view — but the dashboard's headline figure becomes monthly flow (`monthly_income − monthly expenses`).

**Phase 7 (multi-user foundations) is complete as of 2026-08-22** — see `docs/ROADMAP.md` and `docs/specs/fase_07_spec.md`. Alembic, API versioning (`/api/v1/`), account lifecycle (password reset, email verification, 15-min JWT TTL), and the pytest suite are all in place. The one item deliberately deferred is distributed rate limiting (no multi-worker deployment yet, so it isn't needed). Phase 8 (data model for the new MVP) is next.

One loose end from Phase 7: `EMAIL_PROVIDER` is still `console` everywhere — no real SMTP credentials have been configured, so password-reset and verification emails are only logged, never actually delivered. See `docs/TODO.md`.

## Commands

### Run (Docker, recommended)

Needs a root `.env` (copy from `.env.example`) with `POSTGRES_PASSWORD` and `SECRET_KEY` — `docker compose up` fails fast if either is missing, no silent fallback to a known default. Email vars (`EMAIL_PROVIDER`, `SMTP_*`) are optional and default to `EMAIL_PROVIDER=console` (logs the email instead of sending it — see `docs/TODO.md`).

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

- `main.py` — assembles FastAPI app, CORS (see below), structured logging + request-ID middleware, security headers, and mounts every router under `/api/v1/...`.
- `core/` — `database.py` (SQLAlchemy engine/session, PostgreSQL via `DATABASE_URL` env var, falls back to SQLite), `security.py` (JWT + bcrypt), `rate_limit.py` (slowapi `Limiter` instance), `email.py` (pluggable email sender, see Auth flow below), `logging_config.py` (structured JSON logging to stdout), `seed.py`.
- `models/models.py` — 8 SQLAlchemy models in one file (User, Account, Category, Transaction, Budget, RefreshToken, PasswordResetToken, EmailVerificationToken).
- `schemas/schemas.py` — all Pydantic schemas in one file.
- `api/` — one router module per domain (auth, users, accounts, categories, transactions, budgets, dashboard, preferences).

**Alembic manages the schema** (`backend/alembic/`, migrations in `backend/alembic/versions/`). The Docker `CMD` runs `alembic upgrade head` before starting uvicorn (see `Dockerfile` / `docker-compose.dev.yml`). Running without Docker: activate the venv and run `alembic upgrade head` from `backend/` before first start, or after pulling a change that adds a migration. The old ad-hoc `_ensure_*_column()` functions and the on-every-boot legacy category migration are gone — schema changes now go through `alembic revision --autogenerate`, reviewed by hand before committing.

Auth flow: `OAuth2PasswordBearer`, login takes email in the `username` field, JWT (`sub=user_id`) expires in **15 min** (shortened from 60 in Phase 7 so a stolen/post-logout token has a short window — no server-side blacklist, see `docs/specs/fase_07_spec.md` §2.5.1), opaque refresh token (hashed in DB, 30-day expiry) rotates via `/api/v1/auth/refresh`. Registration, login, and password-reset requests are all rate-limited to 5 req/min via slowapi (in-memory — fine for the current single-worker deployment; distributed rate limiting is deferred, see `docs/ROADMAP.md`).

Account lifecycle (Phase 7): `POST /api/v1/auth/password-reset/request` + `.../confirm` (one-time token, 45-min expiry, revokes all active refresh tokens on success, never reveals whether an email is registered) and `GET /api/v1/auth/verify-email` (one-time token, 48h expiry; login is **not** gated on verification, by design). Both send email via `app/core/email.py`, pluggable through `EMAIL_PROVIDER`: `console` (default — logs the email/link instead of sending, no credentials needed) or `smtp` (real send via `smtplib`, needs `SMTP_HOST`/`PORT`/`USER`/`PASSWORD`/`FROM_EMAIL`). **`EMAIL_PROVIDER` is still `console` in every environment** — real SMTP credentials have never been configured, so no password-reset or verification email has actually been delivered end-to-end yet (see `docs/TODO.md`). Frontend pages that consume these links live at `app/(auth)/forgot-password`, `reset-password`, `verify-email`.

Money is always `Decimal` in schemas and `Numeric(14,2)` in models — never float.

**Backend is the source of truth for all financial calculations** (account balances, budget progress, dashboard aggregates). The frontend must never recompute these.

### Frontend (`frontend/`)

Next.js App Router with two route groups: `app/(auth)/` (login, register, forgot-password, reset-password, verify-email — minimal layout, no sidebar) and `app/(dashboard)/` (the authenticated shell — sidebar + all domain pages: dashboard root, `analytics/`, `transactions/`, `accounts/[id]`, `categories/[id]`, `budgets/`).

State layering is intentional and split three ways — don't blur these:
- **TanStack Query** — all server state. `QueryProvider` creates one `QueryClient` for the session (`staleTime` 1 min, `refetchOnWindowFocus` off). Mutations must invalidate related queries (see `frontend/docs/STATE_AND_FETCHING.md` for the key/invalidation map).
- **Zustand** (`store/useUiStore.ts`) — UI-only state (currently just sidebar open/collapsed). Not for server data.
- **`useState`** — local form/modal state.

`lib/api.ts` is the single Axios instance: `baseURL` is `` `${NEXT_PUBLIC_API_URL}/api/v1` `` (defaults to `http://localhost:8000/api/v1`) — every call site uses a path **relative to that** (e.g. `api.get('accounts/')`, never `/api/...`; Phase 7 centralized the version prefix here so a future `/api/v2/` only touches this one file). Injects `Authorization: Bearer <jwt>` from `localStorage` on every request, clears the token and redirects to `/login` on 401, with a mutex/queue so concurrent 401s share a single refresh call instead of firing duplicates.

Import alias `@/*` resolves to the frontend root.

### Cross-cutting conventions

- If you change a shared API contract, update **both** `backend/docs/API_REFERENCE.md` and `frontend/docs/API_CONTRACT.md` in the same change.
- Categories with `user_id = NULL` are system-base categories — never editable or deletable via the API, seeded at startup.
- CORS is driven by the `ALLOWED_ORIGINS` env var. The Tailscale IP regex (100.x.x.x) only applies when `ENABLE_TAILSCALE_CORS=true` (set in `docker-compose.yml` for the current deploy) — leave it unset once the app moves off Tailscale, no code change needed (Phase 7 §3.3). Some security tradeoffs (JWT in `localStorage`) are still accepted for now (see `docs/TODO.md`).
- `POSTGRES_PASSWORD` and `SECRET_KEY` are required env vars for `docker compose up` (root `.env`, see `.env.example`) — there's no silent fallback to a known default anymore; a missing value fails the boot (Phase 7 §3.2).

## Where to look for more detail

This repo maintains its own detailed docs — check them before inferring behavior from code alone:

- `backend/docs/ARCHITECTURE.md`, `frontend/docs/ARCHITECTURE.md` — full architecture writeups.
- `backend/docs/BUSINESS_RULES.md` — domain invariants (ownership checks, deletion guards, budget uniqueness, etc.).
- `backend/docs/API_REFERENCE.md`, `frontend/docs/API_CONTRACT.md` — endpoint/payload contracts.
- `frontend/docs/STATE_AND_FETCHING.md` — React Query key/invalidation patterns.
- `frontend/docs/COMPONENTS_GUIDE.md`, `frontend/docs/UI_SYSTEM.md` — reusable components and visual tokens.
- `docs/TODO.md` — technical debt and confirmed bugs, tagged by urgency, with resolution dates. Reprioritized 2026-08-22 for the multi-user pivot.
- `docs/ROADMAP.md` — **read this first for anything architectural.** Records the 2026-08-22 pivot, the five MVP components, the phased plan (Phases 7–14), the prioritized backlog, and what remains genuinely out of scope (broker integrations, credit-card rewards engines, dynamic themes, i18n).
- `docs/specs/` — detailed per-phase implementation specs (file-level tasks, design decisions) written before implementing a phase. `fase_07_spec.md` covers everything implemented in Phase 7.
