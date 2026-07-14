# Roadmap — Oikos

> Plan de desarrollo priorizado por impacto real en uso diario.
> Cada fase es independiente (salvo que se indique lo contrario).
>
> Formato: `[ ]` pendiente · `[x]` resuelto (con fecha).

---

## Historial — Completado

| Fecha | Item |
|-------|------|
| 2026-07-06 | **Fase 0** — Security wins: SECRET_KEY regenerada, EmailStr, email normalization, model_dump(), CORS en env var |
| 2026-07-06 | **Fase 1** — Factoría de formateo + AppConfigProvider: columnas preferred_currency/locale, endpoint preferences, formatters.ts, useUserPreferences, migración formatCurrency/formatDate |
| 2026-07-06 | **Fase 2** — Tokenización tema CSS: paleta light/dark con custom properties, ThemeToggle, hardcoded colors eliminados de gráficos |
| 2026-07-08 | **Fase 3** — Columna currency en DB: modelos Account/Transaction/Budget, schemas, types, UI selector + display multi-moneda |
| 2026-07-08 | Seed data: script `backend/app/core/seed.py` con usuario test, 3 cuentas, 45 transacciones, 6 presupuestos |
| 2026-07-08 | Post-auditoría: migración `.dict()` → `model_dump()`, eliminación hex hardcodeados, corrección categories |
| 2026-07-09 | Feature Multi-Tema: preferred_theme en backend, ThemeToggle sincronizado, transiciones CSS, WCAG AA verificado |
| 2026-07-10 | Feature FAB + Transacción Rápida: FloatingActionButton, FabManager, QuickTransactionModal, integrado en dashboard layout |
| 2026-07-10 | **Fase 1** — Fixes inmediatos: CSS bug dashboard, finanzas.db excluido de git, rate limiting verificado y documentado |
| 2026-07-10 | **Fase 2** — Transacción rápida FAB: FloatingActionButton, FabManager, QuickTransactionModal, integrado en dashboard layout |
| 2026-07-10 | **Fase 3** — Documentación actualizada: keys preferencias corregidas, errores API, ARCHITECTURE con RefreshToken y migraciones, AGENTS actualizado, docs/TODO.md con 3 items nuevos |
| 2026-07-11 | **Fase 4A** — Tailscale: CORS regex, uvicorn 0.0.0.0, WSL2 tailscale IP 100.124.221.83, login verificado |
| 2026-07-11 | **Fase 4B** — Docker: Dockerfiles (backend python:3.12-slim, frontend node:22-alpine multi-stage), docker-compose.yml (postgres + backend + frontend), .dockerignore x2, fix pnpm install (pnpm@9 + --frozen-lockfile + onlyBuiltDependencies en package.json), seed en PostgreSQL |

---

## Fase 4 — Acceso remoto + Docker

**Objetivo:** Acceder a Oikos desde el celular y cualquier dispositivo, de forma segura.

### Parte A — Tailscale (acceso remoto seguro)

- [x] **Modificar CORS** para aceptar IPs de Tailscale (100.x.x.x) vía `allow_origin_regex` en `main.py` (2026-07-11)
- [x] **Modificar uvicorn** para escuchar en `0.0.0.0` en vez de `localhost` (AGENTS.md actualizado) (2026-07-11)
- [x] **Instalar Tailscale en Windows** (`winget install Tailscale.Tailscale`), autenticar, obtener IP (2026-07-10)
- [x] **Instalar Tailscale en WSL2** — `curl -fsSL https://tailscale.com/install.sh | sh` + `tailscale up`. IP: `100.124.221.83` (2026-07-11)
  - WSL2 tiene red aislada (NAT). Tailscale en Windows no es accesible desde WSL2. Solución: instalar Tailscale dentro de WSL2.
  - Windows Firewall bloquea TCP desde WSL2 al host (ARP funciona pero TCP timeout).
- [x] **Verificar conectividad** WSL2 ↔ iPhone: ping OK (0% loss, ~100ms) (2026-07-11)
- [x] **Iniciar backend** con `uvicorn app.main:app --reload --host 0.0.0.0` — accesible vía `http://100.124.221.83:8000` (2026-07-11)
- [x] **Login verificado** vía Tailscale: `POST /api/auth/login` retorna JWT correctamente (2026-07-11)
- [ ] **Acceder** desde celular a `http://100.124.221.83:8000` (API)
- [ ] **Verificar** login, transacciones, dashboard completo por Tailscale desde celular

### Parte B — Docker + PostgreSQL

- [x] **Actualizar `app/core/database.py`** para leer `DATABASE_URL` de variable de entorno
      con fallback a SQLite (`sqlite:///./finanzas.db`). (2026-07-11)

- [x] **Crear `backend/Dockerfile`** con `python:3.12-slim`:
  - Copiar `requirements.txt`, instalar dependencias.
  - Exponer puerto `8000`.
  - Comando: `uvicorn app.main:app --host 0.0.0.0 --port 8000`. (2026-07-11)

- [x] **Crear `frontend/Dockerfile`** con `node:22-alpine` (multi-stage):
  - Build stage: copiar código, `pnpm install`, `pnpm build`.
  - Production stage: copilar `.next/standalone`, expone `3000`.
  - Variable de build: `NEXT_PUBLIC_API_URL`.
  - Fix: `pnpm@9` (no `@latest`), `--frozen-lockfile`, `onlyBuiltDependencies` en `package.json` (no workspace yaml). (2026-07-11)

- [x] **Crear `docker-compose.yml`** en la raíz con 3 servicios:
  - `postgres` — imagen externa, volumen persistente.
  - `backend` — build local, depende de `postgres`.
  - `frontend` — build local, depende de `backend`. (2026-07-11)

- [x] **Agregar `.dockerignore`** para backend y frontend (node_modules, venv, __pycache__,
      .db, .env). (2026-07-11)

- [x] **Verificar** que `docker compose up --build` funcione de cero. (2026-07-11)

- [ ] **Seed automático** — ejecutar seed en PostgreSQL después del primer startup
      (alternativa: comando `docker compose exec backend python -c "from app.core.seed import run_seed; run_seed()"`).

- [ ] **Script `scripts/deploy.sh`** que automatice: git pull → docker compose up --build -d.

### Calidad de vida

- [x] **Healthchecks** en docker-compose para postgres, backend y frontend (2026-07-11).
  - Frontend tiene healthcheck en el compose (Next.js dev mode expone `/`).

---

## Fase 5 — Backup + Multi-moneda simple

**Objetivo:** Proteger datos y corregir el bug del saldo total multi-moneda.

### Backup

- [ ] **Script `scripts/backup.sh`** — hacer `docker compose exec postgres pg_dump -U oikos oikos` y guardar en `backups/` con timestamp.
  - Ejecutar antes de cada sesión de cambios significativos.
  - Mantener últimos 7 backups (rotación).

### Dashboard multi-moneda (solo agrupación)

- [ ] **Corregir `backend/app/api/dashboard.py`**
  - El `total_balance` actual suma saldos de COP + USD + EUR = número sin sentido.
  - Cambiar: agrupar saldos por moneda, devolver `{ balances: [{ currency: "COP", total: 1500000 }, { currency: "USD", total: 850 }] }`.

- [ ] **Actualizar schema `DashboardSummary`**
  - Nuevo campo `balances_by_currency` (array de `{ currency, total }`).
  - Mantener `total_balance` como deprecated o eliminarlo.

- [ ] **Actualizar frontend `app/(dashboard)/page.tsx`**
  - Mostrar tarjeta de saldo por cada moneda (en vez de una sola suma).
  - Formato: `$1.234.567 COP`, `$850.00 USD`.

---

## Fase 6 — Code Review Roadmap

**Objetivo:** Atender los hallazgos de la auditoría de código (`CODE_REVIEW.md`, 2026-07-14).
Mejoras priorizadas por impacto: bug multi-moneda, seguridad, testing, modularidad, arquitectura.

### Quick Wins (horas)

- [x] **Fix bug multi-moneda dashboard** — agrupar saldos por moneda en vez de sumar COP+USD+EUR (2026-07-14)
  - `balances` (array por moneda), `monthly_income_by_currency`, `monthly_expense_by_currency`.
  - `SummaryCard` refactorizado para aceptar children multi-moneda.

- [x] **Sanitizar errores en `dashboard.py:cashflow-series`** — `str(e)` reemplazado por mensaje genérico (2026-07-14)
  - `import logging` movido a cabecera del módulo.

- [x] **Headers de seguridad** via middleware FastAPI (X-Frame-Options, X-Content-Type-Options, etc.) (2026-07-14)

- [x] **Crear `README.md`** en raíz del proyecto — entry point de documentación (2026-07-14)

- [ ] **Reemplazar `datetime.utcnow()`** — ya resuelto en `security.py`. Archivado.

- [ ] **Fix input raw → componentes UI** — reemplazar `<input>` por `Input`/`Select` existentes en forms de accounts, categories, transactions — 2h

- [ ] **Agregar `ruff`** (linter/formatter Python) al backend — 1h

- [ ] **Agregar `prettier`** al frontend — 1h

### Testing (días)

- [ ] **Configurar pytest + httpx** para tests de integración backend (endpoints auth + transacciones) — 2d
  - Cobertura mínima 60% en endpoints de autenticación y lógica contable.

- [ ] **Configurar Vitest + React Testing Library** para tests frontend — 2d

### Modularidad frontend (1 día)

- [ ] **Extraer custom hooks de queries** — `useAccounts`, `useCategories`, `useTransactions` — 1d
  - Cada página hace `useQuery` + `queryFn` inline; consolidar en hooks reutilizables.

- [ ] **Decidir `AccountUpdate.currency`** — schema hereda `currency` de `AccountBase` pero `accounts.py:59` solo actualiza `name` y `type` — 1h
  - Resolver: agregar al endpoint o excluir del schema.

### Seguridad avanzada (días)

- [ ] **Migrar JWT** de `localStorage` a cookies httpOnly + secure + sameSite — 2d
  - Elimina riesgo de robo de token vía XSS.

- [ ] **Script `scripts/backup.sh`** para PostgreSQL con rotación de 7 días — 1d
  - `docker compose exec postgres pg_dump` → `backups/` con timestamp.

### Arquitectura backend (semanas)

- [ ] **Hacer `docker-compose.yml` paramétrico** — IPs y SECRET_KEY via `.env` en vez de hardcodear — 1d

- [ ] **Crear capa `app/services/`** — lógica de negocio (accounting, budget) fuera de routers — 2s

- [ ] **Crear `app/core/exceptions.py`** — excepciones de dominio en vez de `HTTPException` mezclados con reglas de negocio — 1s

- [ ] **Partir `schemas.py` y `models.py`** por dominio (user, transaction, account, budget, category) — 1s

---

## Fuera de scope (no hacer)

- ~~**i18n (Internacionalización)**~~ — Innecesario para un solo usuario que habla español.
- ~~**Multi-Moneda Completo (tasas de cambio)**~~ — Overengineering para gastos personales.
- ~~**Alembic**~~ — `create_all()` es suficiente para un solo usuario.
- ~~**CI/CD**~~ — Innecesario para proyecto personal.
- ~~**Testing automatizado**~~ — Por ahora. Revisar cuando el código crezca.
- ~~**Service layer backend**~~ — Los routers están delgados; resolver cuando dualen.
