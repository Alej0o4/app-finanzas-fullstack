# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Oikos — a multi-currency personal-finance web app. FastAPI backend, Next.js App Router frontend, PostgreSQL database.

**As of 2026-08-22 the project pivoted from "single-user personal app" to a product anyone could use**, and **as of 2026-09-19 it pivoted back.** Oikos is not being shipped, marketed, or opened to outside users in the foreseeable future — it's a personal finance tool for its one owner/developer. This second pivot does **not** undo the first one architecturally: Alembic migrations, automated testing, and API versioning stay in scope, because they make the codebase easier to keep extending, not because of a multi-user threat model. What it does change is priority: **security hardening, auth features, and abuse-resistance work are no longer being actively pursued.** The baseline shipped through Phase 26 (see below) is considered sufficient for a single trusted user on a personal deployment — don't propose new security/auth work unless something is actually broken or the user asks. Default to spending effort on features that make tracking and analyzing spending better. Read `docs/ROADMAP.md` for the current backlog and `docs/CHANGELOG.md` for phase-by-phase history before proposing architecture.

The central conceptual shift from the first pivot still stands: the current app is **stock**-based (accounts hold balances; the dashboard answers *"how much do I have?"*). The MVP built in Phases 8-15 is **flow**-based (the dashboard answers *"how much did I spend this month and what's left?"*). Both coexist — account balances stay visible in a secondary view — but the dashboard's headline figure is monthly flow (`monthly_income − monthly expenses`).

**Phases 0–28 are complete** (2026-07-06 through 2026-09-19) — see `docs/CHANGELOG.md` for the full phase-by-phase history and `docs/specs/fase_NN_spec.md` for per-phase implementation detail. Live, not just planned: the flow-based dashboard, budget alerts + push notifications, the weekly summary, the 3-minute onboarding, API-key-based mobile shortcuts, per-account analytics, a customizable category system, branded transactional email, Google OAuth login, self-service account settings (currency + deletion), a services/schemas/domain-exceptions architecture layer (`app/services/ledger.py`, `app/schemas/*`, `app/core/exceptions.py` — the exceptions layer now covers every router, not just a pilot, since Phase 28), and session auth on `httpOnly` cookies with CSRF protection (Phase 26). Phases 27–28 (2026-09-19) closed out the last open modularity debt — `transactions/page.tsx` decomposed into subcomponents, `DomainError` rolled out repo-wide — deliberately, before resuming the feature backlog (see `docs/ROADMAP.md`).

A few operational facts from that history remain true today, not just historical record:
- **Google login is currently down in production** — Google Cloud disabled the OAuth client (`disabled_client`, 2026-09-19), likely an automated antifraud false-positive on a new personal project; an appeal is pending. This is a real, personal-use-affecting bug (the owner's own daily login), not a hardening item — see `docs/TODO.md` 🟠 for the workaround in use and the fix if the appeal fails. Separately, `GOOGLE_CLIENT_ID`/`NEXT_PUBLIC_GOOGLE_CLIENT_ID` still need to be set per-environment or `GoogleAuthButton` silently renders nothing and `/auth/google` returns `503`.
- **Distributed rate limiting will not be implemented** — `slowapi` is in-memory, single-worker-only, which was already fine under the multi-user plan and is now permanently fine: the deployment isn't scaling past one worker/replica for a single-user app. Formerly "deferred," now out of scope — see `docs/ROADMAP.md`.
- **Session auth runs on `httpOnly` cookies (Phase 26)** — `access_token` (HttpOnly, 15 min), `refresh_token` (HttpOnly, Path `/api/v1/auth`, 30 days) and a non-HttpOnly `csrf_token` for the double-submit pattern on mutations (`X-CSRF-Token`). No JWT in `localStorage`. Non-browser clients (curl, API keys) still use the `Authorization` header as the primary path. Spec: `docs/specs/fase_26_spec.md`. This is the security baseline the project is standing on now — not a foundation for further hardening work, just where it stopped.
- A critical Google-OAuth account-takeover vulnerability (silent auto-link of an attacker-planted password) was found in the 2026-09-15 audit and fixed in Phase 23 — see `docs/CHANGELOG.md`. Findings of this class are why the security baseline was brought up to a reasonable bar before deprioritizing further security work, not evidence that more hardening is still owed.

**Tailscale Funnel was activated 2026-09-06** — Oikos is reachable from the public internet (`https://<host>.<tailnet>.ts.net`), not just from tailnet IPs, though usage is still single-user in practice. That exposure was the reason the JWT-in-`localStorage` tradeoff (see Phase 26 above) couldn't be deferred indefinitely — it's now closed: production login is consolidated on the Funnel HTTPS domain (`COOKIE_SECURE=true` by default), and direct-Tailnet-IP browser access is deprecated for session cookies, not for API keys (Decision B10/F6 of `docs/specs/fase_26_spec.md`).

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
- `core/` — `database.py` (SQLAlchemy engine/session, PostgreSQL via `DATABASE_URL` env var, falls back to SQLite), `security.py` (JWT + bcrypt), `rate_limit.py` (slowapi `Limiter` instance), `email.py` (pluggable email sender, see Auth flow below), `logging_config.py` (structured JSON logging to stdout), `exceptions.py` (`DomainError` + a generic taxonomy of subclasses by status code — `BadRequestError`/`UnauthorizedError`/`ForbiddenError`/`NotFoundError`/`ConflictError`/`ValidationError`/`InternalServerError`/`ServiceUnavailableError`, plus `AccountNotFoundError`/`CategoryNotFoundError`; started as a scoped pilot in Phase 25, extended to every router in Phase 28 — every router raises `DomainError` subclasses now, not `HTTPException` directly), `seed.py`.
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

`lib/api.ts` is the single Axios instance: `baseURL` is `` `${NEXT_PUBLIC_API_URL}/api/v1` `` (defaults to `http://localhost:8000/api/v1`) — every call site uses a path **relative to that** (e.g. `api.get('accounts/')`, never `/api/...`; Phase 7 centralized the version prefix here so a future `/api/v2/` only touches this one file). Uses `withCredentials: true` so the session cookies (`access_token` HttpOnly; `csrf_token` readable by JS) travel on every request; the request interceptor adds `X-CSRF-Token` on any method that is not `GET`/`HEAD`, and the response interceptor redirects to `/login` on 401 with a mutex/queue so concurrent 401s share a single refresh call (`api.post('auth/refresh')`, no body) instead of firing duplicates. Since Phase 26 it no longer reads/writes JWT in `localStorage` nor sets `Authorization: Bearer` (see `docs/specs/fase_26_spec.md`).

Import alias `@/*` resolves to the frontend root.

### Cross-cutting conventions

- If you change a shared API contract, update **both** `backend/docs/API_REFERENCE.md` and `frontend/docs/API_CONTRACT.md` in the same change.
- Categories with `user_id = NULL` are system-base categories — never editable or deletable via the API, seeded at startup.
- CORS is driven by the `ALLOWED_ORIGINS` env var. The Tailscale IP regex (100.x.x.x) only applies when `ENABLE_TAILSCALE_CORS=true` (set in `docker-compose.yml` for the current deploy) — leave it unset once the app moves off Tailscale, no code change needed (Phase 7 §3.3). The JWT-in-`localStorage` tradeoff that this section used to flag is resolved since Phase 26 (cookies httpOnly + CSRF).
- `POSTGRES_PASSWORD` and `SECRET_KEY` are required env vars for `docker compose up` (root `.env`, see `.env.example`) — there's no silent fallback to a known default anymore; a missing value fails the boot (Phase 7 §3.2).

## Where to look for more detail

This repo maintains its own detailed docs — check them before inferring behavior from code alone:

- `backend/docs/ARCHITECTURE.md`, `frontend/docs/ARCHITECTURE.md` — full architecture writeups.
- `backend/docs/BUSINESS_RULES.md` — domain invariants (ownership checks, deletion guards, budget uniqueness, etc.).
- `backend/docs/API_REFERENCE.md`, `frontend/docs/API_CONTRACT.md` — endpoint/payload contracts.
- `frontend/docs/STATE_AND_FETCHING.md` — React Query key/invalidation patterns.
- `frontend/docs/COMPONENTS_GUIDE.md`, `frontend/docs/UI_SYSTEM.md` — reusable components and visual tokens.
- `docs/TODO.md` — technical debt and confirmed bugs, tagged by urgency, with resolution dates. Reprioritized 2026-08-22 for the multi-user pivot.
- `docs/WORKFLOW.md` — **read this before starting any feature, phase, or bug fix.** The development sequence: when a change needs a spec, the full flow (`/grilling` → `/to-spec` → `/analyze-spec` → implement → `/run-tests` → `/code-review` → `/analyze-spec cierre` → closing docs → PR), and the short flow for bugs.
- `docs/ROADMAP.md` — **read this first for anything architectural.** Records the 2026-08-22 pivot, the five MVP components, what's still genuinely open (Phase 26 JWT-to-cookies, deferred items), the prioritized backlog, and what remains out of scope (broker integrations, credit-card rewards engines, dynamic themes, i18n). Phase-by-phase history (Phases 0–25, all complete) moved to `docs/CHANGELOG.md` to keep the roadmap itself short — each entry there is a 3–5 line summary pointing at its `docs/specs/fase_NN_spec.md`.
- `docs/specs/` — detailed per-phase implementation specs (file-level tasks, design decisions) written before implementing a phase. `fase_07_spec.md` covers everything implemented in Phase 7.

## Agent skills

### Issue tracker

Local markdown, not GitHub Issues despite the GitHub remote: specs at `docs/specs/fase_NN_spec.md` (existing per-phase convention), tickets/wayfinder tracking under `.scratch/<feature>/`. See `docs/agents/issue-tracker.md` — it also defines two Oikos additions to the `/to-spec` template (`[NEEDS CLARIFICATION: …]` markers, and a tagged `## Orden de ejecución` with `[backend]`/`[frontend]`/`[P]`/`Depende de:`). Run `/analyze-spec` before implementing a spec and again when closing the phase.

### Domain docs

Single-context: root `CONTEXT.md` + `docs/adr/` (neither exists yet — created lazily by `/domain-modeling`, not upfront). See `docs/agents/domain.md`.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
