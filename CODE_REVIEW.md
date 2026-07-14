# Auditoría de Proyecto: Oikos — Finanzas Personales

**Fecha**: 14 de julio de 2026
**Analista**: Opencode AI
**Tipo de Proyecto**: Fullstack (Backend + Frontend)
**Stack**: FastAPI + SQLAlchemy + PostgreSQL / Next.js 16 + React 19 + TanStack Query + Zustand + Recharts + Tailwind CSS 4

---

## 1. Resumen Ejecutivo

### Estado General: 7.0/10

**Veredicto**: ACEPTABLE — Proyecto MVP funcional con documentación excepcional y arquitectura sólida. Deuda técnica conocida y documentada. Requiere tests, corrección del bug multi-moneda, y migración de JWT a cookies httpOnly antes de exponerse fuera de red privada.

### Top 3 Problemas Críticos

1. **Sin tests automatizados (backend ni frontend)**
   - Impacto: Alto
   - Ubicación: Proyecto completo
   - Solución: Agregar pytest + httpx para backend, Vitest + React Testing Library para frontend. Cobertura mínima 60% en endpoints de autenticación y lógica contable.

2. **Dashboard suma saldos de diferentes monedas**
   - Impacto: Alto
   - Ubicación: `backend/app/api/dashboard.py:21`
   - Solución: Cambiar `total_balance` a `balances_by_currency` (array de `{currency, total}`). Actualizar schema y frontend.

3. **JWT guardado en `localStorage`**
   - Impacto: Medio
   - Ubicación: `frontend/lib/api.ts:22`, `frontend/app/(auth)/login/page.tsx:38`
   - Solución: Migrar a cookies `httpOnly` + `secure` + `sameSite`. Baja prioridad para uso personal con Tailscale.

### Fortalezas Destacadas

- ✅ Documentación excepcional (11 archivos docs + AGENTS.md + TODO_TECH_DEBT.md + REFACTOR_ROADMAP.md)
- ✅ Arquitectura backend limpia con validación de ownership en todos los endpoints
- ✅ Multi-moneda implementada correctamente en modelos, schemas y transacciones

---

## 2. Análisis por Área

### 2.1 Estructura
**Score**: 7/10 | **Prioridad**: Media

**Hallazgos Positivos**:
- Organización clara backend: `app/api/`, `app/core/`, `app/models/`, `app/schemas/`, `app/services/`
- Frontend con Next.js App Router y route groups `(auth)` y `(dashboard)` bien separados
- Componentes UI reutilizables en `components/ui/` (Button, Input, Select, ModalShell, Skeleton, etc.)
- Separación por responsabilidades: `hooks/`, `lib/`, `providers/`, `store/`, `types/`
- Nombres descriptivos y consistentes (snake_case Python, camelCase TypeScript)

**Áreas de Mejora**:
- `backend/app/services/` vacío — la lógica de negocio está embebida en routers
- `schemas.py` (162 líneas) y `models.py` (89 líneas) como archivos únicos — manejable pero crece
- `transactions/page.tsx` (380 líneas) es el archivo más grande del frontend
- `accounts/page.tsx` (265 líneas) mezcla UI + lógica de mutaciones + modales

**Recomendaciones**:
1. Cuando se agreguen 2-3 entidades más, partir `schemas.py` y `models.py` por dominio
2. Extraer lógica de mutaciones de `transactions/page.tsx` a custom hooks

---

### 2.2 Arquitectura
**Score**: 7/10 | **Prioridad**: Alta

**Hallazgos Positivos**:
- Backend es fuente de verdad para saldos, presupuestos y agregados — frontend no recalcula métricas financieras
- Separación clara frontend/backend con contratos documentados (`API_CONTRACT.md`, `API_REFERENCE.md`)
- React Query para estado de servidor (staleTime 1 min) + Zustand para UI (solo sidebar) + useState para formularios
- CORS configurable via variable de entorno `ALLOWED_ORIGINS`
- Rate limiting en login via `slowapi` (5 req/min)
- Refresh token rotation implementada correctamente
- Docker multi-stage build para frontend (producción optimizada)

**Áreas de Mejora**:
- Rutas FastAPI monolíticas: routers hacen de controller + service + repository
- `main.py` ejecuta migraciones (`ALTER TABLE`) y seed de categorías en cada arranque — frágil
- Dependencias Docker hardcoded: IP Tailscale (`100.124.221.83`) en `docker-compose.yml:39`
- Sin capa de excepciones de dominio — todo `raise HTTPException` mezclado con reglas de negocio
- `seed_default_categories()` en `main.py` ejecuta UPDATE/INSERT sin idempotencia robusta

**Recomendaciones**:
1. **Corto plazo**: Extraer lógica contable de `transactions.py` a un módulo `app/services/accounting.py`
2. **Corto plazo**: Hacer `docker-compose.yml` paramétrico con `.env` para IPs y SECRET_KEY
3. **Mediano plazo**: Crear capa de excepciones de dominio (`app/core/exceptions.py`)

---

### 2.3 Mantenibilidad
**Score**: 6/10 | **Prioridad**: Alta

**Hallazgos Positivos**:
- Código Python limpio con snake_case consistente y docstrings útiles
- TypeScript estricto (`strict: true` en `tsconfig.json`)
- Validación robusta de inputs en Pydantic schemas (`Field(..., gt=0, decimal_places=2)`)
- Query keys centralizadas en `queryKeys.ts` — fáciles de mantener
- Deuda técnica documentada y priorizada (`TODO_TECH_DEBT.md`, `REFACTOR_ROADMAP.md`)

**Áreas de Mejora**:
- **Sin tests automatizados** — el item más crítico
- Sin typecheck configurado en ninguna capa
- Sin formateador configurado (no hay black/ruff en backend, no hay prettier en frontend)
- `datetime.utcnow()` deprecated en Python 3.12+ — usado en `security.py:49`
- Duplicación de fetch logic: `queryFn` inline repetido en accounts/budgets/transactions/dashboard
- Components/ui existen pero casi no se usan — forms usan `<input>` raw
- `eslint-disable` en `transactions/page.tsx:108` para `react-hooks/set-state-in-effect`

**Recomendaciones**:
1. **Quick win**: Agregar `ruff` (backend) y `prettier` (frontend) — 1h cada uno
2. **Quick win**: Reemplazar `datetime.utcnow()` por `datetime.now(timezone.utc)` — 1h
3. **Corto plazo**: Extraer custom hooks (`useAccounts`, `useCategories`, `useTransactions`) — 4h
4. **Mediano plazo**: Configurar pytest + httpx y Vitest — 1-2 días

---

### 2.4 Modularidad
**Score**: 6/10 | **Prioridad**: Media

**Hallazgos Positivos**:
- Componentes UI reutilizables: `Button`, `Input`, `Select`, `ModalShell`, `Skeleton`, `EmptyState`, `SummaryCard`
- Custom hooks compartidos: `useCurrentUser`, `useUserPreferences`
- `queryKeys.ts` centraliza todas las claves de React Query
- `AppConfigProvider` para preferencias globales (currency, locale, theme)
- `useConfirmStore` (Zustand) para diálogos de confirmación globales

**Áreas de Mejora**:
- UI components existen pero casi no se usan — forms en accounts, categories, transactions usan `<input>` raw
- No hay custom hooks para queries (cada página hace `useQuery` + `queryFn` inline)
- `AccountUpdate` schema hereda `currency` de `AccountBase` pero `accounts.py:59` solo actualiza `name` y `type` — drift silencioso
- Lógica de negocio embebida en routers — no reutilizable desde CLI/job/test
- Tipos de dominio no compartidos backend→frontend (enums Python vs string unions TypeScript)

**Recomendaciones**:
1. **Quick win**: Reemplazar `<input>` raw por componentes `Input`/`Select` existentes — 2h
2. **Corto plazo**: Extraer custom hooks de queries — 3h
3. **Mediano plazo**: Decidir sobre `AccountUpdate.currency` (actualizar o excluir del schema) — 1h

---

### 2.5 Seguridad
**Score**: 7/10 | **Prioridad**: Alta

**Hallazgos Positivos**:
- JWT con expiración (60 min) + refresh tokens (30 días) con rotation
- Bcrypt para hashing de contraseñas (`passlib`)
- Rate limiting en login (5 req/min por IP via `slowapi`)
- Validación de ownership en TODOS los endpoints (account, transaction, budget, category)
- CORS configurable via env var + regex para Tailscale
- `.gitignore` excluye `.env`, `.db`, `venv/`
- SECRET_KEY generada criptográficamente
- Refresh tokens hasheados con SHA-256 antes de almacenar
- Email normalizado (lowercase + strip)

**Áreas de Mejora**:
- **JWT en `localStorage`** — riesgo XSS (conocido, baja prioridad para red privada)
- `docker-compose.yml:25` tiene `SECRET_KEY: ${SECRET_KEY:-changeme_in_production}` — fallback inseguro
- Sin headers de seguridad (CSP, HSTS, X-Frame-Options, X-Content-Type-Options)
- `dashboard.py:135` expone `str(e)` en errores — puede filtrar información interna
- Sin backup automático de PostgreSQL (volumen `pgdata`)
- `seed.py` tiene credenciales hardcodeadas (`test@test.com` / `testpass123`) — aceptable para seed

**Recomendaciones**:
1. **Quick win**: Agregar headers de seguridad via middleware FastAPI — 1h
2. **Quick win**: Sanitizar error messages en `cashflow-series` — 1h
3. **Corto plazo**: Migrar JWT a cookies httpOnly — 4h
4. **Mediano plazo**: Script `scripts/backup.sh` con rotación — 2h

---

### 2.6 Documentación
**Score**: 9/10 | **Prioridad**: Baja

**Hallazgos Positivos**:
- **AGENTS.md**: Startup, comandos, arquitectura, convenciones — completo y actualizado
- **Backend docs** (5 archivos): `API_REFERENCE.md` (318 líneas), `ARCHITECTURE.md`, `BUSINESS_RULES.md`, `DEPLOYMENT.md`, `FRONTEND_INTEGRATION.md`
- **Frontend docs** (6 archivos): `API_CONTRACT.md`, `ARCHITECTURE.md`, `COMPONENTS_GUIDE.md`, `DEPLOYMENT.md`, `STATE_AND_FETCHING.md`, `UI_SYSTEM.md`
- `TODO_TECH_DEBT.md`: Items priorizados por urgencia, con fechas de resolución
- `REFACTOR_ROADMAP.md`: Fases detalladas con historial completo
- `.env.example` presente con las 3 variables requeridas
- Seed data documentado con credenciales de prueba

**Áreas de Mejora**:
- Falta `README.md` en la raíz del proyecto (la app no tiene entry point de documentación para nuevos desarrolladores)
- No hay `CONTRIBUTING.md` (irrelevante para proyecto personal)
- Algunos emoji comments en el código (`🔒`, `🧮`, `🆕`) — subjetivo

**Recomendaciones**:
1. **Quick win**: Crear `README.md` en raíz que enlace a AGENTS.md y docs — 1h
2. No se requieren más cambios de documentación en esta etapa

---

### 2.7 UX/Usabilidad
**Score**: 7/10 | **Prioridad**: Media

**Hallazgos Positivos**:
- Sidebar colapsable con tooltips hover
- Skeleton loaders en dashboard (summary cards, budget rings, recent transactions)
- Empty states con guía y iconografía (`EmptyState` component)
- Toast feedback (Sonner) en todas las mutaciones (crear, editar, eliminar)
- Confirmación en acciones destructivas (`ConfirmDialog` + `useConfirmStore`)
- FAB (Floating Action Button) para transacción rápida desde cualquier pantalla
- Theme toggle (dark/light) sincronizado con backend
- Formularios con validación (required, type, min/max)
- Login con feedback de error claro
- Post-registro redirect con mensaje de éxito

**Áreas de Mejora**:
- Dashboard muestra `total_balance` que mezcla COP + USD + EUR — número sin sentido
- Sin optimistic updates en mutaciones (espera response para actualizar UI)
- Forms usan `<input>` raw en vez de componentes `Input`/`Select` — inconsistencia visual
- `transactions/page.tsx` usa "Cargar más" (infinite scroll manual) en vez de paginación
- No hay skeleton loaders en todas las páginas (solo dashboard)
- Login no tiene rate limiting visual (el usuario no ve cuántos intentos le quedan)

**Recomendaciones**:
1. **Quick win**: Corregir bug multi-moneda en dashboard — 2h
2. **Corto plazo**: Agregar optimistic updates en mutaciones principales — 4h
3. **Corto plazo**: Unificar forms con componentes UI existentes — 3h

---

## 3. Recomendaciones Priorizadas

### Quick Wins (Horas)

| # | Recomendación | Tiempo | Área |
|---|---------------|--------|------|
| 1 | Reemplazar `datetime.utcnow()` por `datetime.now(timezone.utc)` en `security.py` | 1h | Mantenibilidad |
| 2 | Sanitizar error messages en `dashboard.py:cashflow-series` (no exponer `str(e)`) | 1h | Seguridad |
| 3 | Agregar headers de seguridad (CSP, X-Frame-Options) via middleware FastAPI | 1h | Seguridad |
| 4 | Crear `README.md` en raíz del proyecto | 1h | Documentación |
| 5 | Corregir bug multi-moneda: cambiar `total_balance` a `balances_by_currency` | 2h | UX |
| 6 | Agregar `ruff` (Python linter/formatter) al backend | 1h | Mantenibilidad |
| 7 | Agregar `prettier` al frontend | 1h | Mantenibilidad |
| 8 | Reemplazar `<input>` raw por componentes `Input`/`Select` existentes en forms | 2h | Modularidad |

### Mejoras Medianas (Días)

| # | Recomendación | Tiempo | Área |
|---|---------------|--------|------|
| 1 | Configurar pytest + httpx para tests de integración backend (endpoints críticos) | 2d | Mantenibilidad |
| 2 | Configurar Vitest + React Testing Library para tests frontend | 2d | Mantenibilidad |
| 3 | Extraer custom hooks de queries (`useAccounts`, `useCategories`, `useTransactions`) | 1d | Modularidad |
| 4 | Migrar JWT de `localStorage` a cookies `httpOnly` + `secure` | 2d | Seguridad |
| 5 | Script `scripts/backup.sh` para PostgreSQL con rotación de 7 días | 1d | Seguridad |
| 6 | Hacer `docker-compose.yml` paramétrico (IPs, SECRET_KEY via `.env`) | 1d | Arquitectura |

### Refactoring Mayor (Semanas)

| # | Recomendación | Tiempo | Área |
|---|---------------|--------|------|
| 1 | Crear capa `app/services/` para lógica de negocio (accounting, budget) | 2s | Arquitectura |
| 2 | Crear `app/core/exceptions.py` para excepciones de dominio | 1s | Arquitectura |
| 3 | Partir `schemas.py` y `models.py` por dominio (user, transaction, account, budget, category) | 1s | Estructura |

---

## 4. Próximos Pasos Sugeridos

### Acciones Inmediatas (Esta semana)

1. **Corregir bug multi-moneda en dashboard**
   - Por qué: El `total_balance` actual mezcla COP + USD + EUR = número sin sentido financiero
   - Cómo: Cambiar `DashboardSummary.total_balance` a `balances_by_currency: List[{currency, total}]`. Actualizar frontend para mostrar tarjeta por moneda.
   - Resultado esperado: Dashboard muestra saldos agrupados por moneda

2. **Agregar headers de seguridad + sanitizar errores**
   - Por qué: Prevención de ataques básicos y no filtrar info interna
   - Cómo: Agregar middleware en `main.py` con CSP, X-Frame-Options. Reemplazar `str(e)` en `cashflow-series` por mensaje genérico.
   - Resultado esperado: Headers presentes en responses, errores seguros

3. **Reemplazar `datetime.utcnow()`**
   - Por qué: Deprecated en Python 3.12+, generará warnings
   - Cómo: Buscar y reemplazar en `security.py` (2 occurrences)
   - Resultado esperado: Sin deprecation warnings

### Roadmap de Mejoras (Próximo mes)

1. **Configurar testing automatizado**
   - Impacto: Alto
   - Esfuerzo: 4 días (2 backend + 2 frontend)
   - Beneficio: Prevención de regresiones, confianza para refactoring

2. **Migrar JWT a cookies httpOnly**
   - Impacto: Alto (seguridad)
   - Esfuerzo: 2 días
   - Beneficio: Elimina riesgo de robo de token vía XSS

3. **Crear capa de servicios backend**
   - Impacto: Medio
   - Esfuerzo: 2 semanas
   - Beneficio: Lógica de negocio reutilizable, testeable, separada de HTTP

---

## 5. Métricas Clave

| Área | Score | Prioridad | Estado |
|------|-------|-----------|--------|
| Estructura | 7/10 | Media | ✅ |
| Arquitectura | 7/10 | Alta | ⚠️ |
| Mantenibilidad | 6/10 | Alta | ⚠️ |
| Modularidad | 6/10 | Media | ⚠️ |
| Seguridad | 7/10 | Alta | ⚠️ |
| Documentación | 9/10 | Baja | ✅ |
| UX/Usabilidad | 7/10 | Media | ✅ |

**Score General**: 7.0/10

---

## 6. Conclusión

Oikos es un proyecto MVP **sólido y funcional** que demuestra buenas prácticas en arquitectura backend, documentación y manejo de estado frontend. La documentación es excepcional (11 archivos docs + AGENTS.md + TODO + ROADMAP), lo cual es raro en proyectos de esta etapa y acelera significativamente el desarrollo futuro.

Los principales riesgos son la **ausencia de tests automatizados** (sin red de seguridad para cambios) y el **bug del dashboard multi-moneda** (datos financieros incorrectos). La seguridad es adecuada para uso personal con Tailscale, pero requiere hardening (cookies httpOnly, headers, backups) antes de exponerse más ampliamente.

La deuda técnica está **consciente y documentada** — el equipo sabe exactamente qué atajos se tomaron y por qué. El REFACTOR_ROADMAP está bien priorizado por impacto real.

**Siguiente paso recomendado**: Corregir el bug multi-moneda en dashboard (2h) y agregar testing mínimo en endpoints de autenticación y transacciones (2d).

---

*Reporte generado por Code Review Skill — Opencode*
