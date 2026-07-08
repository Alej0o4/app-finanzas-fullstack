# Roadmap de Refactor — Oikos

> Checklist estructurado basado en la auditoría integral (Julio 2026).
> Cada fase es prerrequisito de la siguiente. No saltarse fases sin marcar completas.
>
> Formato: `[ ]` pendiente · `[x]` resuelto (con fecha).

---

## Fase 0 — Quick Security Wins (bajo esfuerzo, alto impacto)

- [x] **Regenerar `SECRET_KEY` criptográficamente segura.** (2026-07-06)
  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(48))"
  ```
  Reemplazar en `backend/.env`. **No commitear la llave real.**

- [x] **Agregar `EmailStr` a `UserCreate.email`** para validar formato de email. (2026-07-06)
  Archivos: `backend/app/schemas/schemas.py`
  - Cambiar `email: str = Field(..., max_length=255)` → `email: EmailStr`
  - Agregar `from pydantic import EmailStr`

- [x] **Normalizar email a minúsculas en registro y login.** (2026-07-06)
  Archivos: `backend/app/api/auth.py`, `backend/app/api/users.py`
  - Hacer `.lower().strip()` antes de guardar y antes de buscar.

- [x] **Migrar `transaccion.dict()` → `transaccion.model_dump()`** (Pydantic v2 compat). (2026-07-06)
  Archivo: `backend/app/api/transactions.py` (línea 41)

- [x] **Mover CORS a variable de entorno `ALLOWED_ORIGINS`.** (2026-07-06)
  Archivos: `backend/app/main.py`, `backend/.env`
  - Default: `"http://localhost:3000,http://localhost:5173"`

---

## Fase 1 — Quick Win #1: Factoría de Formateo + Provider de Configuración

**Objetivo:** Eliminar dependencias duras de COP/es-CO/dark en la capa de presentación.

### Backend

- [x] **Crear endpoint `GET /api/users/me/preferences`** que devuelva `{ currency, locale, theme }`. (2026-07-06)
  - Valores iniciales: `{ currency: "COP", locale: "es-CO", theme: "dark" }`.
  - Archivo nuevo: `backend/app/api/preferences.py`
  - Registrar router en `backend/app/main.py`

- [x] **Agregar columna `preferred_currency` al modelo `User`.** (2026-07-06)
  Archivo: `backend/app/models/models.py`
  - `preferred_currency = Column(String(3), default="COP")`

- [x] **Agregar columna `preferred_locale` al modelo `User`.** (2026-07-06)
  - `preferred_locale = Column(String(10), default="es-CO")`

- [x] **Exponer preferencias en `UserResponse` schema.** (2026-07-06)
  Archivo: `backend/app/schemas/schemas.py`

### Frontend — Core

- [x] **Crear `frontend/lib/formatters.ts`** con funciones parametrizables: (2026-07-06)
  ```ts
  export function formatCurrency(amount: number, currency = "COP", locale = "es-CO"): string
  export function formatDate(isoString: string, locale = "es-CO", options?: Intl.DateTimeFormatOptions): string
  ```
  - Migrar implementación desde `lib/utils.ts`.

- [x] **Crear `frontend/providers/AppConfigProvider.tsx`** con React Context: (2026-07-06)
  - Estado: `{ currency: string; locale: string; theme: string }`
  - Valores default: `{ currency: "COP"; locale: "es-CO"; theme: "dark" }`
  - Hook: `useAppConfig()`

- [x] **Crear custom hook `useUserPreferences.ts`** que: (2026-07-06)
  - Haga fetch a `GET /api/users/me/preferences` (autenticado).
  - Sincronice el `AppConfigProvider` con los valores del backend.
  - Haga fallback a defaults si el fetch falla o no hay token.

- [x] **Envolver `frontend/app/layout.tsx`** con `AppConfigProvider`. (2026-07-06)

- [x] **Migrar `formatCurrency(amount)` → `formatCurrency(amount, currency)` en TODOS los usos.** (2026-07-06)
  Búsqueda: `formatCurrency(` en `*.tsx` y `*.ts`.
  Archivos a tocar (~15 ocurrencias):
  - `frontend/lib/utils.ts` (re-export)
  - `frontend/components/CashflowChart.tsx`
  - `frontend/components/CategoryDonutChart.tsx`
  - `frontend/components/charts/BudgetRing.tsx`
  - `frontend/components/AnalyticsSummary.tsx`
  - `frontend/app/(dashboard)/page.tsx`
  - `frontend/app/(dashboard)/transactions/page.tsx`
  - `frontend/app/(dashboard)/accounts/page.tsx`
  - `frontend/app/(dashboard)/accounts/[id]/page.tsx`
  - `frontend/app/(dashboard)/categories/[id]/page.tsx`
  - `frontend/app/(dashboard)/budgets/page.tsx`

- [x] **Migrar `formatDate(isoString)` → `formatDate(isoString, locale)` en TODOS los usos.** (2026-07-06)
  Archivos a tocar (~5 ocurrencias).

- [x] **Actualizar `types/api.ts`** para incluir `preferred_currency` y `preferred_locale` en `UserResponse`. (2026-07-06)

---

## Fase 2 — Quick Win #2: Tokenización de Tema (CSS Custom Properties)

**Objetivo:** Sistema de estilos que soporte light/dark sin colores hardcodeados en componentes.

### CSS

- [x] **Refactorizar `frontend/app/globals.css`:** (2026-07-06)
  - Convertir paleta actual en `:root, [data-theme="dark"] { ... }`.
  - Agregar `[data-theme="light"] { ... }` con paleta clara completa:

    | Variable | Dark (actual) | Light (nueva) |
    |---|---|---|
    | `--color-background` | `#0b1220` | `#f8fafc` |
    | `--color-surface` | `#111b2e` | `#ffffff` |
    | `--color-surface-elevated` | `#162338` | `#f1f5f9` |
    | `--color-border` | `#24314a` | `#e2e8f0` |
    | `--color-text` | `#eef4ff` | `#0f172a` |
    | `--color-text-muted` | `#9aa7bd` | `#64748b` |
    | `--color-text-soft` | `#c7d2e5` | `#334155` |
    | `--color-primary` | `#7dd3fc` | `#0284c7` |
    | `--color-primary-dark` | `#38bdf8` | `#0369a1` |
    | `--color-success` | `#34d399` | `#16a34a` |
    | `--color-warning` | `#f59e0b` | `#d97706` |
    | `--color-danger` | `#fb7185` | `#dc2626` |
    | `--color-info` | `#60a5fa` | `#2563eb` |
    | Chart tokens (1-10) | existing | versiones claras |

  - Agregar `@custom-variant dark (&:where([data-theme="dark"], [data-theme="dark"] *))`.

### Componentes — Eliminar colores hardcodeados

- [x] **`frontend/components/CashflowChart.tsx`:** (2026-07-06)
  - Reemplazar `text-[#60a5fa]` (spinner) → `text-info` o `fill="var(--color-info)"`.
  - Reemplazar `fill="#34d399"` → `fill="var(--color-success)"`.
  - Reemplazar `fill="#fb7185"` → `fill="var(--color-danger)"`.
  - Reemplazar tooltip inline styles:
    - `backgroundColor: "#162338"` → `var(--color-surface-elevated)`
    - `borderColor: "#24314a"` → `var(--color-border)`
    - `color: "#eef4ff"` → `var(--color-text)`
  - Reemplazar `stroke="#24314a"` (CartesianGrid) → `var(--color-border)`.
  - Reemplazar `stroke="#9aa7bd"` (ejes) → `var(--color-text-muted)`.
  - Reemplazar `fill="#24314a"` (cursor) → `var(--color-border)`.

- [x] **`frontend/components/CategoryDonutChart.tsx`:** (2026-07-06)
  - Reemplazar `text-[#60a5fa]` (spinner) → `text-info`.
  - Tooltip ya usaba clases Tailwind — sin cambios necesarios.
  - CATEGORY_COLORS migrado a `var(--color-chart-1..10)`.

### UI — ThemeToggle

- [x] **Crear `frontend/components/ThemeToggle.tsx`:** (2026-07-06)
  - Botón que alterne: `dark` ↔ `light` ↔ `system`.
  - Escriba `data-theme` en `<html>`.
  - Escuche `prefers-color-scheme` cuando está en modo `system`.
  - Persista preferencia en `localStorage` clave `oikos_theme`.

- [x] **Integrar `ThemeToggle` en `Sidebar.tsx`** (footer abierto y colapsado). (2026-07-06)

- [x] **Sincronizar tema con `AppConfigProvider`** (Fase 1) via `updateConfig({ theme })`. (2026-07-06)

---

## Fase 3 — Quick Win #3: Columna `currency` en DB

**Objetivo:** Almacenar moneda por cuenta/transacción para soporte multi-moneda.

### Backend — Modelos

- [x] **Agregar `currency = Column(String(3), default="COP")` a modelo `Account`.** (2026-07-08)
  Archivo: `backend/app/models/models.py`

- [x] **Agregar `currency = Column(String(3), default="COP")` a modelo `Transaction`.** (2026-07-08)
  - Heredar de la cuenta al crear transacción.

- [x] **Agregar `currency = Column(String(3), default="COP")` a modelo `Budget`.** (2026-07-08)
  - Moneda propia, no hereda de categoría.

### Backend — Schemas

- [x] **Agregar `currency: str = "COP"` a schemas:** (2026-07-08)
  - `AccountResponse`
  - `TransactionResponse` / `TransactionBase`
  - `BudgetResponse` / `BudgetBase`
  - `DashboardSummary` (la moneda del resumen puede ser la del usuario)

### Backend — Lógica

- [x] **Al crear transacción: heredar `currency` de la `Account` asociada.** (2026-07-08)
  Archivo: `backend/app/api/transactions.py`
  - `nueva_transaccion.currency = cuenta.currency`

- [x] **Al crear cuenta: asignar `currency` del payload (default "COP" si no se envía).** (2026-07-08)
  Archivo: `backend/app/api/accounts.py`

- [x] **Al crear presupuesto: asignar `currency` del payload (default "COP" si no se envía).** (2026-07-08)
  Archivo: `backend/app/api/budgets.py`

### Frontend — Tipos

- [x] **Agregar `currency: string` a interfaces en `types/api.ts`:** (2026-07-08)
  - `Account`, `Transaction`, `Budget`, `DashboardSummary`
  - Opcional: `CreateAccountPayload`, `CreateTransactionPayload`, `BudgetPayload`

### Frontend — UI

- [x] **Agregar selector de moneda en formulario de crear cuenta** (dropdown con COP, USD, EUR). (2026-07-08)
  Archivo: `frontend/app/(dashboard)/accounts/page.tsx`

- [x] **Agregar indicador de moneda en tarjetas de cuenta** (ej. "COP" junto al saldo). (2026-07-08)
  Archivo: `frontend/app/(dashboard)/accounts/page.tsx`

- [x] **Mostrar moneda en cada transacción de la lista.** (2026-07-08)
  Archivo: `frontend/app/(dashboard)/transactions/page.tsx`

---

## Post-Quick-Wins — Implementación de Features

> Completar las 3 fases anteriores antes de comenzar esta sección.

### Feature: Multi-Tema (Dark / Light / System)

- [ ] **Confirmar que Fase 2 está completa** (no hay colores hardcodeados).
- [ ] **Persistir preferencia de tema en backend** (`PATCH /api/users/me/preferences`).
- [ ] **Agregar `preferred_theme` a `AppConfigProvider`** con valor inicial del backend.
- [ ] **Sincronizar `ThemeToggle` con backend** al cambiar preferencia.
- [ ] **Probar transición suave** entre temas (CSS `transition` en variables).
- [ ] **Verificar contraste WCAG AA** en ambos temas (especialmente text-muted sobre surface).

### Feature: i18n (Internacionalización)

- [ ] **Crear `frontend/lib/i18n/`** con estructura:
  - `locales/es.json` — traducciones español
  - `locales/en.json` — traducciones inglés
  - `config.ts` — definición de idiomas soportados
  - `useTranslation.ts` — hook que consume el locale de `AppConfigProvider`

- [ ] **Extraer TODOS los strings de UI** a los archivos JSON:
  - Navegación (Sidebar)
  - Formularios (crear/editar cuentas, categorías, transacciones, presupuestos)
  - Dashboard (títulos, etiquetas, estados vacíos, errores)
  - Gráficos (tooltips, leyendas, botones de período)
  - Modales y confirmaciones
  - Páginas de autenticación

- [ ] **Reemplazar strings inline** por `t("key")` en todos los componentes.

- [ ] **Agregar selector de idioma** en `Sidebar.tsx` o página de preferencias.

- [ ] **Persistir `preferred_locale`** en backend (`PATCH /api/users/me/preferences`).

- [ ] **Actualizar `Intl.DateTimeFormat` y `Intl.NumberFormat`** para usar `locale` dinámico.

### Feature: Multi-Moneda Completo

- [ ] **Confirmar Fase 3 completa** (currency en DB, schemas, types).
- [ ] **Selector de moneda al crear transacción** (default de la cuenta, overridable).
- [ ] **Dashboard multi-moneda:**
  - Mostrar saldo total en la moneda del usuario (COP).
  - Convertir/agrupar por moneda: tarjeta separada por cada moneda.
  - O usar tasa de conversión (requiere feature de tasas).

- [ ] **API de tasas de cambio** (endpoint externo o tabla manual):
  - Endpoint `GET /api/rates` o servicio externo.
  - Cache de tasas con TTL configurable.

- [ ] **Visualización con código de moneda** en toda la UI:
  - Formato: `$1,234,567 COP` o `$850.00 USD`.
  - Usar `Intl.NumberFormat(locale, { style: "currency", currency })`.

---

## Historial de resolución

| Fecha | Item |
|-------|------|
| 2026-07-06 | Fase 0 completa: SECRET_KEY, EmailStr, email normalization, model_dump(), CORS env var |
| 2026-07-06 | Fase 1 completa: columnas preferred_currency/locale, endpoint preferences, formatters.ts, AppConfigProvider, useUserPreferences, migración formatCurrency/formatDate |
| 2026-07-06 | Fase 2 completa: Tokenización tema CSS (light/dark), ThemeToggle, Sidebar integration, hardcoded colors eliminados de gráficos |
| 2026-07-08 | Fase 3 completa: Columna currency en modelos Account/Transaction/Budget, schemas, types, UI selector + display multi-moneda |
| 2026-07-08 | Seed data: Script `backend/app/core/seed.py` con usuario test, 3 cuentas multi-moneda, 45 transacciones (3 meses), 6 presupuestos |
