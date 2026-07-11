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
| 2026-07-10 | **Fase 3** — Documentación actualizada: keys preferencias corregidas, errores API, ARCHITECTURE con RefreshToken y migraciones, AGENTS actualizado, TODO_TECH_DEBT con 3 items nuevos |
| 2026-07-11 | **Fase 4A** — Tailscale: CORS regex, uvicorn 0.0.0.0, WSL2 tailscale IP 100.124.221.83, login verificado |
| 2026-07-11 | **Fase 4B** — Docker: Dockerfiles (backend python:3.12-slim, frontend node:22-alpine multi-stage), docker-compose.yml (postgres + backend + frontend), .dockerignore x2, fix pnpm install (pnpm@9 + --frozen-lockfile + onlyBuiltDependencies en package.json), seed en PostgreSQL |

---

## Fase 1 — Fixes inmediatos (bugs + seguridad)

- [x] **Fix bug CSS dashboard** — `frontend/app/(dashboard)/layout.tsx:33` (2026-07-10)
  - `lg:p-12max-w-[1600px]` → `lg:p-12 max-w-[1600px]` (falta un espacio)
  - El `max-w-[1600px]` nunca se aplica actualmente.

- [x] **Excluir `finanzas.db` de git** — agregar a `.gitignore` (2026-07-10)
  - Riesgo de commitear datos financieros reales por accidente.

- [x] **Verificar rate limiting en login** — `backend/app/main.py` (2026-07-10)
  - El `TODO_TECH_DEBT.md` dice "sin rate limiting" pero `slowapi` parece estar configurado.
  - Confirmar que funciona y documentar el estado real.

---

## Fase 2 — Transacción rápida (FAB)

**Objetivo:** Poder registrar un gasto en <5 segundos desde cualquier pantalla. Este es el feature con mayor impacto en que la app se use diariamente. (2026-07-10)

- [x] **Crear componente `FloatingActionButton.tsx`** (2026-07-10)
  - Botón flotante fijo en esquina inferior derecha del dashboard.
  - Visible en todas las pantallas del dashboard (no en auth).
  - Icono: `Plus` de Lucide, fondo `--color-primary`.
  - Menú expandible con 2 opciones: "Gasto rápido" y "Nueva transacción".
  - Click fuera cierra el menú. Z-index z-30 (debajo de sidebar y modales).

- [x] **Crear componente `QuickTransactionModal.tsx`** (2026-07-10)
  - Modal simplificado basado en `ModalShell`.
  - Campos: monto (autofocus), tipo toggle, cuenta (select), categoría (filtrada por tipo), fecha (default hoy), descripción (opcional).
  - Cuenta se auto-selecciona (primera cuenta del usuario).
  - Al guardar: `POST /api/transactions/`, invalidar 5 queries, toast de éxito, cerrar modal.

- [x] **Crear componente `FabManager.tsx`** (2026-07-10)
  - Orquestador que maneja el estado del menú FAB y los dos modales.
  - "Gasto rápido" → `QuickTransactionModal`.
  - "Nueva transacción" → `TransactionModal` (existente).

- [x] **Integrar FAB en dashboard layout** (2026-07-10)
  - `frontend/app/(dashboard)/layout.tsx` — `<FabManager />` junto a Sidebar y ConfirmDialog.

- [x] **Feedback visual post-guardado** (2026-07-10)
  - Toast "Gasto registrado" o "Ingreso registrado" (Sonner).
  - Cerrar modal automáticamente.
  - Actualizar datos del dashboard (query invalidation).

---

## Fase 3 — Documentación actualizada

**Objetivo:** Que la documentación refleje el estado real del código. Acelera desarrollo futuro con agentes IA.

- [x] **Actualizar `backend/docs/API_REFERENCE.md`** (2026-07-10)
  - Agregar: refresh tokens, campos currency en accounts/transactions/budgets,
    preferencias de usuario (GET/PATCH), endpoint `/auth/refresh`, `/auth/logout`.

- [x] **Actualizar `backend/docs/ARCHITECTURE.md`** (2026-07-10)
  - Corregir: "no hay refresh tokens" → documentar refresh token rotation.
  - Documentar columnas `preferred_currency`, `preferred_locale`, `preferred_theme`.

- [x] **Actualizar `AGENTS.md`** (2026-07-10)
  - Reflejar comandos y arquitectura actuales.

- [x] **Actualizar `TODO_TECH_DEBT.md`** (2026-07-10)
  - Marcar como resueltos los items que ya se completaron (rate limiting, CORS, refresh tokens).
  - Reorganizar prioridades según el nuevo estado.

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

- [x] **Healthchecks** en docker-compose para postgres y backend (2026-07-11).
  - Frontend no tiene healthcheck (Next.js standalone no expone endpoint de salud).

---

## Fase 5 — Backup + Multi-moneda simple

**Objetivo:** Proteger datos y corregir el bug del saldo total multi-moneda.

### Backup

- [ ] **Script `scripts/backup.sh`** — copiar `finanzas.db` a `backups/` con timestamp.
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

## Fuera de scope (no hacer)

- ~~**i18n (Internacionalización)**~~ — Innecesario para un solo usuario que habla español.
- ~~**Multi-Moneda Completo (tasas de cambio)**~~ — Overengineering para gastos personales.
- ~~**Alembic**~~ — `create_all()` es suficiente para un solo usuario.
- ~~**CI/CD**~~ — Innecesario para proyecto personal.
- ~~**Testing automatizado**~~ — Por ahora. Revisar cuando el código crezca.
- ~~**Service layer backend**~~ — Los routers están delgados; resolver cuando dualen.
