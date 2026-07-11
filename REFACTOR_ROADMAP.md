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
| 2026-07-10 | **Fase 1** — Fixes inmediatos: CSS bug dashboard, finanzas.db excluido de git, rate limiting verificado y documentado |

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

**Objetivo:** Poder registrar un gasto en <5 segundos desde cualquier pantalla. Este es el feature con mayor impacto en que la app se use diariamente.

- [ ] **Crear componente `FloatingActionButton.tsx`**
  - Botón flotante fijo en esquina inferior derecha del dashboard.
  - Visible en todas las pantallas del dashboard (no en auth).
  - Icono: `Plus` de Lucide, fondo `--color-primary`.
  - Hover: escala + sombra. Z-index por encima de modales.

- [ ] **Crear componente `QuickTransactionModal.tsx`**
  - Modal simplificado (no el `TransactionModal` completo).
  - Campos:
    - **Monto** — input numérico, autofocus, formato COP.
    - **Tipo** — toggle gasto/ingreso (default: gasto).
    - **Cuenta** — select con cuentas del usuario (default: primera cuenta).
    - **Categoría** — select con categorías filtradas por tipo (gasto/ingreso).
    - **Fecha** — input date, default = hoy.
    - **Descripción** — textarea opcional, una línea.
  - Botón "Guardar" al fondo.
  - Al guardar: crear transacción vía `POST /api/transactions/`, invalidar queries de dashboard, transacciones, cuentas, presupuestos.
  - Cerrar modal y mostrar toast de éxito.

- [ ] **Integrar FAB en dashboard layout**
  - `frontend/app/(dashboard)/layout.tsx` — renderizar `FloatingActionButton` junto al contenido.
  - Al tocar: abrir `QuickTransactionModal`.

- [ ] **Feedback visual post-guardado**
  - Toast "Gasto registrado" o "Ingreso registrado" (Sonner).
  - Cerrar modal automáticamente.
  - Actualizar datos del dashboard (query invalidation).

---

## Fase 3 — Documentación actualizada

**Objetivo:** Que la documentación refleje el estado real del código. Acelera desarrollo futuro con agentes IA.

- [ ] **Actualizar `backend/docs/API_REFERENCE.md`**
  - Agregar: refresh tokens, campos currency en accounts/transactions/budgets,
    preferencias de usuario (GET/PATCH), endpoint `/auth/refresh`, `/auth/logout`.

- [ ] **Actualizar `backend/docs/ARCHITECTURE.md`**
  - Corregir: "no hay refresh tokens" → documentar refresh token rotation.
  - Documentar columnas `preferred_currency`, `preferred_locale`, `preferred_theme`.

- [ ] **Actualizar `AGENTS.md`**
  - Reflejar comandos y arquitectura actuales.

- [ ] **Actualizar `TODO_TECH_DEBT.md`**
  - Marcar como resueltos los items que ya se completaron (rate limiting, CORS, refresh tokens).
  - Reorganizar prioridades según el nuevo estado.

---

## Fase 4 — Self-Hosting con Docker + Tailscale

**Objetivo:** Acceder a Oikos desde celular y cualquier dispositivo, de forma segura.

### Migrar backend a PostgreSQL

- [ ] **Actualizar `app/core/database.py`** para leer `DATABASE_URL` de variable de entorno
      con fallback a SQLite (`sqlite:///./finanzas.db`).

- [ ] **Agregar servicio `postgres`** en docker-compose con imagen `postgres:16-alpine`,
      volumen persistente y credenciales vía variables de entorno.

- [ ] **Verificar** que el backend arranque correctamente apuntando a PostgreSQL.

### Dockerizar la aplicación

- [ ] **Crear `backend/Dockerfile`** con `python:3.12-slim`:
  - Copiar `requirements.txt`, instalar dependencias.
  - Exponer puerto `8000`.
  - Comando: `uvicorn app.main:app --host 0.0.0.0 --port 8000`.

- [ ] **Crear `frontend/Dockerfile`** con `node:22-alpine` (multi-stage):
  - Build stage: copiar código, `pnpm install`, `pnpm build`.
  - Production stage: copiar `.next/standalone`, expone `3000`.
  - Variable de build: `NEXT_PUBLIC_API_URL`.

- [ ] **Crear `docker-compose.yml`** en la raíz con 3 servicios:
  - `postgres` — imagen externa, volumen persistente.
  - `backend` — build local, depende de `postgres`.
  - `frontend` — build local, depende de `backend`.

- [ ] **Agregar `.dockerignore`** para backend y frontend (node_modules, venv, __pycache__,
      .db, .env).

- [ ] **Verificar** que `docker compose up --build` funcione de cero.

### Acceso remoto con Tailscale

- [ ] **Instalar Tailscale** en la máquina host.

- [ ] **Instalar Tailscale** en cada dispositivo cliente (celular Android/iOS, laptop).

- [ ] **Acceder** desde cualquier dispositivo por `http://<tailscale-ip>:3000`.

- [ ] **Verificar** que login, JWT y funcionalidad completa funcionen por Tailscale.

- [ ] **Opcional:** Configurar MagicDNS para acceder por nombre (`http://oikos:3000`).

### Calidad de vida

- [ ] **Healthchecks** en docker-compose para los 3 servicios.

- [ ] **Script `scripts/deploy.sh`** que automatice: git pull → docker compose up --build -d.

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
