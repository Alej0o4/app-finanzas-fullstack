# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Oikos — a multi-currency personal-finance web app. FastAPI backend, Next.js App Router frontend, PostgreSQL database.

**As of 2026-08-22 the project pivoted from "single-user personal app" to a product anyone can use.** This invalidated three previously-out-of-scope decisions, which are now in scope: **Alembic migrations, automated testing, and API versioning**. Read `docs/ROADMAP.md` before proposing architecture — it records the pivot, the decisions taken, and the phased plan.

The central conceptual shift: the current app is **stock**-based (accounts hold balances; the dashboard answers *"how much do I have?"*). The new MVP is **flow**-based (the dashboard answers *"how much did I spend this month and what's left?"*). Both coexist — account balances stay visible in a secondary view — but the dashboard's headline figure becomes monthly flow (`monthly_income − monthly expenses`).

**Phases 7–16 are complete** (2026-08-22 through 2026-09-06), plus an unnumbered maintenance stop ("Parada — Correcciones de UX post-pivote") between Phases 15 and 16 — see `docs/ROADMAP.md` for the full phase-by-phase history and `docs/specs/fase_NN_spec.md` for per-phase implementation detail. The flow-based dashboard, budget alerts + push notifications, the weekly summary, the 3-minute onboarding, and API-key-based mobile shortcuts are all live, not just planned. **Phases 17–19 are complete** (2026-09-12): per-account analytics plus a currency selector on budgets (Phase 17); an expanded, per-user-customizable category system (Phase 18); and a set of post-onboarding UX fixes — conditional login redirect, a dashboard card redesign, an income-based expense metric (Phase 19). **Phase 20** (added 2026-09-13) is complete: the transactional-email HTML template carries Oikos branding (`render_email_html()` in `app/core/email.py`, shared by both verification and password-reset emails), the auth-form placeholders were genericized, and Google OAuth login shipped the same day per `docs/specs/fase_20_spec.md` — `POST /api/v1/auth/google` verifies a Google Identity Services ID token (`google-auth` lib, no redirect/client-secret flow) and issues the same JWT/refresh token as `login()`; `User.password_hash` is now `nullable=True` with a new `google_id` column (migration `5b79ad1d27e4`); a Google login auto-links an existing password account with the same email instead of duplicating it — **as of Phase 23 (2026-09-18)**, that auto-link nulls the existing `password_hash` when the account wasn't already verified, closing a critical account-takeover vulnerability found in the 2026-09-15 audit (`CODE_REVIEW.md`) where an attacker could pre-register a victim's email with their own password and have it silently legitimized by the victim's real Google login; an already-verified account keeps its password unchanged when it later links Google. `POST /push/subscribe` also now logs (without blocking) any cross-user reassignment of a push subscription — see `docs/specs/fase_23_spec.md`. `GoogleAuthButton.tsx` is wired into both `login/page.tsx` and `register/page.tsx`. Apple sign-in was explicitly ruled out (paid Developer Program, disproportionate complexity for a web-only app). **Phase 24** (2026-09-18) closed the "silent failure" UX pattern the 2026-09-15 audit found repeated across the dashboard: the 4 dashboard queries now expose `isError`/`refetch` with a per-section "Reintentar" button instead of looking identical to "no data yet"; the inline monthly-income form gained `noValidate` + a visible field error + focus-on-fail, matching the Phase 12 §12.8 pattern used everywhere else; `PUT /api/v1/accounts/{account_id}` now actually applies `currency` changes (previously silently ignored) but blocks with `400` when the account has active transactions, to avoid an account ending up with mixed-currency transactions under one label — same guard pattern as account deletion; and `category-distribution` now returns `category_icon` like `BudgetProgress` already did, so the dashboard's category breakdown shows real icons instead of a generic fallback. See `docs/specs/fase_24_spec.md`. **Phase 25** (2026-09-18) paid down architecture debt flagged by the 2026-09-15 audit: transaction balance math — previously copy-pasted across `crear_transaccion`/`eliminar_transaccion`/`actualizar_transaccion` — is now `app/services/ledger.py`, the first real module in `app/services/`, following the same "pure functions + `db: Session`" style as `app/core/budget_alerts.py`; `app/schemas/schemas.py` (previously 462 lines / 48 classes in one file) is split into 12 per-domain modules under `app/schemas/`, with `schemas.py` kept as a transparent re-export shim so none of the 11 routers' imports needed to change; a domain-exceptions layer (`app/core/exceptions.py` + one handler in `main.py`) landed as a scoped pilot inside `transactions.py` only (4 call sites), not a rewrite of the other ~59 `raise HTTPException` sites across the rest of the API; and the frontend gained shared read hooks — `useAccounts`/`useCategories`/`useTransactions` in `frontend/lib/hooks/` — replacing 19 inline `useQuery`+`queryFn` call sites (mutations stayed inline). **JWT-in-`localStorage` → httpOnly cookies was deliberately NOT done in this phase** — designed in full (`docs/specs/fase_25_spec.md` §25.5) but deferred to its own future spec given its blast radius across every authenticated request, the total absence of CSRF protection anywhere in the codebase today, and the need to not break the `oikos_pat_` API-key header path used by real iOS Shortcuts (Phase 16). See `docs/specs/fase_25_spec.md`. **Google OAuth needs per-environment credentials to actually show the button** — `GOOGLE_CLIENT_ID` (backend) and `NEXT_PUBLIC_GOOGLE_CLIENT_ID` (frontend build arg) must be set in that environment's `.env`, or `GoogleAuthButton` silently renders nothing and `/auth/google` returns `503`. Neither was set in this deployment's `.env` as of 2026-09-13, and `docker-compose.yml`/`frontend/Dockerfile` didn't even propagate `NEXT_PUBLIC_GOOGLE_CLIENT_ID` as a frontend build arg — that plumbing gap was fixed 2026-09-13, but a real Google Cloud Console Client ID still needs to be generated and set before the button appears. The one deliberately deferred item from Phase 7 is distributed rate limiting — still a single-worker deployment, so it isn't needed yet.

One loose end still open, tracked in `docs/TODO.md`: **Tailscale Funnel was activated 2026-09-06** — Oikos is now reachable from the public internet (`https://<host>.<tailnet>.ts.net`), not just from tailnet IPs, though usage is still single-user in practice; this narrows how much longer the CORS/JWT-in-`localStorage` tradeoffs can be deferred.

## Commands

### Run (Docker, recommended)

Needs a root `.env` (copy from `.env.example`) with `POSTGRES_PASSWORD` and `SECRET_KEY` — `docker compose up` fails fast if either is missing, no silent fallback to a known default. Email vars (`EMAIL_PROVIDER`, `SMTP_*`) are optional and default to `EMAIL_PROVIDER=console` (logs the email instead of sending it — see `docs/TODO.md`).

```sh
docker compose up -d --build                                          # production
docker compose -f docker-compose.yml -f docker-compose.dev.yml up      # dev, hot-reload
docker compose logs -f backend                                        # logs
docker compose exec backend python -c "from app.core.seed import run_seed; run_seed()"  # seed data
docker compose exec backend python -c "from app.core.database import SessionLocal; from app.core.user_deletion import delete_user_by_email; db = SessionLocal(); print(delete_user_by_email(db, 'email@ejemplo.com')); db.close()"  # delete user by email (Fase 21, Decisión 21.2.5)
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

Thin layered structure with a nascent service layer (`app/services/ledger.py`, added Phase 25 — the only module so far; most business logic still lives directly in routers, by design at current scale):

- `main.py` — assembles FastAPI app, CORS (see below), structured logging + request-ID middleware, security headers, and mounts every router under `/api/v1/...`.
- `core/` — `database.py` (SQLAlchemy engine/session, PostgreSQL via `DATABASE_URL` env var, falls back to SQLite), `security.py` (JWT + bcrypt), `rate_limit.py` (slowapi `Limiter` instance), `email.py` (pluggable email sender, see Auth flow below), `logging_config.py` (structured JSON logging to stdout), `exceptions.py` (`DomainError` + subclasses, added Phase 25 as a scoped pilot — only `transactions.py` raises them so far, see below), `seed.py`.
- `models/models.py` — 13 SQLAlchemy models in one file (User, Account, Category, HiddenCategory, Transaction, Budget, RefreshToken, PasswordResetToken, EmailVerificationToken, IdempotencyKey, Notification, PushSubscription, ApiKey).
- `schemas/` — Pydantic schemas split by domain since Phase 25 (`accounts.py`, `api_keys.py`, `auth.py`, `budgets.py`, `categories.py`, `common.py`, `dashboard.py`, `notifications.py`, `push.py`, `transactions.py`, `users.py`); `schemas.py` is kept as a re-export shim so every router's existing `from app.schemas import schemas` import still works unchanged.
- `services/ledger.py` — the shared account-balance delta logic used by `crear_transaccion`/`eliminar_transaccion`/`actualizar_transaccion` (Phase 25 §25.1), extracted from three copy-pasted call sites.
- `api/` — one router module per domain (auth, users, accounts, categories, transactions, budgets, dashboard, preferences).

**Alembic manages the schema** (`backend/alembic/`, migrations in `backend/alembic/versions/`). The Docker `CMD` runs `alembic upgrade head` before starting uvicorn (see `Dockerfile` / `docker-compose.dev.yml`). Running without Docker: activate the venv and run `alembic upgrade head` from `backend/` before first start, or after pulling a change that adds a migration. The old ad-hoc `_ensure_*_column()` functions and the on-every-boot legacy category migration are gone — schema changes now go through `alembic revision --autogenerate`, reviewed by hand before committing.

Auth flow: `OAuth2PasswordBearer`, login takes email in the `username` field, JWT (`sub=user_id`) expires in **15 min** (shortened from 60 in Phase 7 so a stolen/post-logout token has a short window — no server-side blacklist, see `docs/specs/fase_07_spec.md` §2.5.1), opaque refresh token (hashed in DB, 30-day expiry) rotates via `/api/v1/auth/refresh`. Registration, login, and password-reset requests are all rate-limited to 5 req/min via slowapi (in-memory — fine for the current single-worker deployment; distributed rate limiting is deferred, see `docs/ROADMAP.md`).

Account lifecycle (Phase 7): `POST /api/v1/auth/password-reset/request` + `.../confirm` (one-time token, 45-min expiry, revokes all active refresh tokens on success, never reveals whether an email is registered) and `GET /api/v1/auth/verify-email` (one-time token, 48h expiry). **Login now requires a verified email** (added 2026-09-12, reversing the original Phase 7 decision) — `POST /api/v1/auth/login` returns `403` with `detail.code == "EMAIL_NOT_VERIFIED"` for an unverified user, and `POST /api/v1/auth/resend-verification` (enumeration-safe, 5 req/min) issues a new token. Registration still never fails or blocks on the send itself. Both send email via `app/core/email.py`, pluggable through `EMAIL_PROVIDER`: `console` (default — logs the email/link instead of sending, no credentials needed) or `smtp` (real send via `smtplib`, needs `SMTP_HOST`/`PORT`/`USER`/`PASSWORD`/`FROM_EMAIL`). **`EMAIL_PROVIDER=smtp` was configured and verified end-to-end against the real deployment `.env` on 2026-09-12** (Gmail + app password) — password registration/verification/reset are live in that deployment, not blocked. The credentials live only in the deployment's gitignored `.env`; `backend/.env` (non-Docker local runs) still has no SMTP vars, so running without Docker still falls back to `EMAIL_PROVIDER=console` unless those vars are added there too. Frontend pages that consume these links live at `app/(auth)/forgot-password`, `reset-password`, `verify-email`.

Money is always `Decimal` in schemas and `Numeric(14,2)` in models — never float.

**Backend is the source of truth for all financial calculations** (account balances, budget progress, dashboard aggregates). The frontend must never recompute these.

### Frontend (`frontend/`)

Next.js App Router with two route groups: `app/(auth)/` (login, register, forgot-password, reset-password, verify-email — minimal layout, no sidebar) and `app/(dashboard)/` (the authenticated shell — sidebar + all domain pages: dashboard root, `analytics/`, `transactions/`, `accounts/[id]`, `categories/[id]`, `budgets/`). There is also a standalone authenticated route outside both groups, `app/capture/` (`/capture`, the post-login capture screen from Phase 10) — minimalist centered layout like `(auth)`, no sidebar/FAB, guarded by the shared `useRequireAuth` hook with an explicit "Ver dashboard" exit link.

State layering is intentional and split three ways — don't blur these:
- **TanStack Query** — all server state. `QueryProvider` creates one `QueryClient` for the session (`staleTime` 1 min, `refetchOnWindowFocus` off). Mutations must invalidate related queries (see `frontend/docs/STATE_AND_FETCHING.md` for the key/invalidation map). `frontend/lib/hooks/{useAccounts,useCategories,useTransactions}.ts` (added Phase 25) wrap the repeated read-only `useQuery`+`queryFn` pattern — prefer these over an inline `useQuery` for accounts/categories/transactions reads; mutations still live inline per page.
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

## Agent skills

### Issue tracker

Local markdown, not GitHub Issues despite the GitHub remote: specs at `docs/specs/fase_NN_spec.md` (existing per-phase convention), tickets/wayfinder tracking under `.scratch/<feature>/`. See `docs/agents/issue-tracker.md`.

### Domain docs

Single-context: root `CONTEXT.md` + `docs/adr/` (neither exists yet — created lazily by `/domain-modeling`, not upfront). See `docs/agents/domain.md`.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
