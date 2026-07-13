# Deuda Técnica Consciente — Oikos

> Este archivo documenta atajos tomados a propósito durante la fase de MVP.
> Revisar antes de pasar a la fase de "hardening" (seguridad/escalabilidad).

Formato: `[ ]` pendiente · `[x]` resuelto — marcar con fecha al resolver.

---

## 🔴 Resolver antes de seguir acumulando datos reales

- [x] **Montos como `float` en vez de `Decimal`/enteros en centavos.** (resuelto 2026-07-08)
  - Migrado a `Decimal`/`Numeric(14,2)` en models.py, schemas.py y dashboard.py.

- [ ] **Sin backup automático de PostgreSQL (volumen Docker `pgdata`).**
  - Riesgo: perder el historial financiero completo si se elimina el volumen.
  - Acción: script `scripts/backup.sh` con rotación de 7 días. Ver REFACTOR_ROADMAP Fase 5.

- [ ] **Dashboard suma saldos de diferentes monedas.**
  - `total_balance` en `dashboard.py` mezcla COP + USD + EUR = número sin sentido.
  - Ver REFACTOR_ROADMAP Fase 5.

---

## 🟡 Revisar antes de exponer la app fuera de localhost

- [ ] **JWT guardado en `localStorage`** (`frontend/lib/api.ts`).
  - Riesgo: robo de token vía XSS.
  - Alternativa: cookie `httpOnly` + `secure` + `sameSite`.
  - Prioridad baja para uso personal con Tailscale (red privada).

- [x] **CORS hardcodeado → variable de entorno `ALLOWED_ORIGINS`.** (resuelto 2026-07-06)

- [x] **Sin refresh tokens.** (resuelto 2026-07-08)
  - Implementado: refresh token rotation con `RefreshToken` model, `/auth/refresh`, `/auth/logout`.

- [x] **Sin rate limiting en login.** (resuelto 2026-07-10)
  - `slowapi` configurado: `Limiter` en `app/core/rate_limit.py`, `@limiter.limit("5/minute")` en `app/api/auth.py:16`, handler registrado en `main.py:128`.

- [ ] **`datetime.utcnow()`** — deprecated en Python 3.12+.
  - Migrar a `datetime.now(datetime.UTC)` cuando se toque el código relacionado.

- [ ] **`Account PUT` ignora cambios de `currency` silenciosamente.**
  - `AccountUpdate` hereda `currency` de `AccountBase`, pero `accounts.py` solo actualiza `name` y `type`.
  - El frontend envía `currency` en PUT pero no tiene efecto. Fix: o actualizar `currency` en el PUT o no aceptar el campo en el schema de update.

- [ ] **Migración runtime de preferencias frágil.**
  - `_ensure_user_preference_columns()` ejecuta `ALTER TABLE ADD COLUMN` en cada arranque.
  - Funciona pero es ad-hoc; si se agregan columnas con constraints, puede fallar silenciosamente.

- [ ] **Migración de categorías legacy en cada startup.**
  - `main.py` renombra "Otro (Gasto)" → "Otro" y migra "Otro (Ingreso)" en cada arranque.
  - Ejecuta UPDATE/INSERT sin idempotencia robusta; puede fallar si la migración ya corrió.

---

## 🟢 Revisar cuando el código empiece a doler al modificarlo

- [ ] **Lógica de negocio embebida en routers FastAPI.**
  - Los routers hacen de controller + service + repository.
  - Señal: cuando quieras testear sin FastAPI, o reusar desde CLI/job.

- [ ] **`schemas.py` y `models.py` como archivos únicos.**
  - Manejable a 5 entidades; partir por dominio si se agregan 2-3 más.

- [ ] **Sin capa de excepciones de dominio.**
  - Todo `raise HTTPException` mezclado con reglas de negocio.

- [ ] **Frontend: fetching duplicado por página.**
  - `useQuery` + `queryFn` inline repetido en accounts/budgets/transactions.
  - Extraer a hooks compartidos (`useAccounts`, `useCategories`, etc.).

- [ ] **Tipos de dominio no compartidos backend→frontend.**
  - `AccountType`, `CategoryType` son enums en Python pero string unions en TS.
  - Riesgo de drift silencioso.

- [ ] **Formularios usan `<input>` raw en vez de componentes `Input`/`Select` existentes.**
  - UI components existen pero están mayormente sin usar.

---

## 🔵 Solo si el proyecto crece

- [ ] Migrar `create_all()` → Alembic.
- [x] Migrar SQLite → PostgreSQL (ya preparado con `psycopg2-binary`). (resuelto 2026-07-11)
- [ ] CI/CD (lint + test + build en cada cambio).
- [ ] Testing automatizado (pytest/httpx backend, Vitest/RTL frontend).
- [ ] Versionado de API (`/api/v1/...`).
- [ ] OpenAPI codegen para eliminar drift de tipos.

---

## Resueltos

| Fecha | Item |
|-------|------|
| 2026-07-11 | Migración SQLite → PostgreSQL via Docker |
| 2026-07-10 | Rate limiting en login verificado y documentado |
| 2026-07-10 | CSS bug dashboard corregido (max-w-[1600px] no se aplicaba) |
| 2026-07-10 | finanzas.db excluido de git (*.db en .gitignore) |
| 2026-07-08 | Montos float → Decimal/Numeric(14,2) |
| 2026-07-06 | CORS → variable de entorno ALLOWED_ORIGINS |
| 2026-07-08 | Refresh tokens implementados |
| 2026-07-06 | SECRET_KEY regenerada criptográficamente |
| 2026-07-06 | EmailStr + normalización email |
| 2026-07-06 | .dict() → model_dump() |
