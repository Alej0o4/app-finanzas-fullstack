# Deuda Técnica Consciente — Oikos

> Este archivo documenta atajos tomados a propósito y hallazgos de auditoría pendientes.
> Repriorizado el **2026-08-22** tras el cambio de enfoque a producto multi-usuario
> (ver [ROADMAP.md](ROADMAP.md)).

Formato: `[ ]` pendiente · `[x]` resuelto — marcar con fecha al resolver.

> **Contexto del cambio:** varios items estaban clasificados como baja prioridad bajo el
> supuesto "solo lo uso yo, en red privada Tailscale". Ese supuesto ya no aplica.

---

## 🔴 Bloqueantes — antes de que exista un usuario que no seas tú

- [ ] **Sin recuperación de contraseña.**
  - Un usuario que olvida su clave pierde la cuenta de forma permanente.
  - Ver ROADMAP Fase 7.

- [ ] **Sin verificación de email.**
  - Registro abierto → cuentas basura, y sin canal validado para la recuperación.

- [ ] **Sin backup automático de PostgreSQL (volumen Docker `pgdata`).**
  - Riesgo: perder el historial financiero completo si se elimina el volumen.
  - Con datos de terceros pasa de molesto a inaceptable.
  - Acción: `scripts/backup.sh` con rotación de 7 días.

- [ ] **Sin migraciones versionadas (Alembic).**
  - `create_all()` + `ALTER TABLE` ad-hoc en cada arranque.
  - Con un solo usuario, si algo se rompe se restaura a mano. Con usuarios reales, no.
  - **Bloquea el resto del roadmap**: todas las fases siguientes agregan columnas.

- [ ] **Sin tests en la lógica que mueve dinero.**
  - El impacto contable (aplicar/revertir deltas) está duplicado en 3 endpoints
    con los signos invertidos a mano, y no tiene ninguna prueba.
  - Es el código de mayor riesgo del proyecto.

- [ ] **Secretos hardcodeados en `docker-compose.yml`.**
  - `POSTGRES_PASSWORD: oikos_secret` literal.
  - `SECRET_KEY: ${SECRET_KEY:-changeme_in_production}` — el default silencioso permite
    arrancar en producción con una clave conocida. Debe fallar el arranque, no continuar.

- [ ] **Sin versionado de API (`/api/v1/`).**
  - Sin esto no se puede evolucionar el contrato sin romper clientes externos.
  - Barato ahora, carísimo cuando existan atajos o apps instaladas.

---

## 🟠 Bugs confirmados (auditoría 2026-08-22)

- [ ] **`preferred_theme` nunca se agrega a DBs existentes.**
  - `_ensure_user_preference_columns()` en `main.py` agrega `preferred_currency` y
    `preferred_locale`, pero **no** `preferred_theme`, aunque el modelo sí lo declara.
  - Solo afecta a bases creadas antes de que existiera esa columna.

- [ ] **Los 3 endpoints restantes del dashboard mezclan monedas.**
  - Mismo defecto que ya se corrigió en `/summary` (2026-07-14), pero quedó en:
    - `budgets-progress` — suma gastos sin filtrar por moneda, los compara contra `Budget.currency`.
    - `cashflow-series` — suma todas las monedas en una sola serie.
    - `category-distribution` — mezcla monedas en los totales por categoría.
  - Sigue siendo alcanzable porque las cuentas quedan visibles (decisión 2026-08-22).

- [ ] **`actualizar_transaccion` no actualiza `currency`.**
  - Mover una transacción de una cuenta COP a una USD la deja con `currency="COP"`
    viviendo en una cuenta USD.

- [ ] **Un usuario nuevo no puede registrar nada.**
  - `account_id` es obligatorio y un usuario recién registrado tiene 0 cuentas.
  - `QuickTransactionModal` hace `if (!effectiveAccountId || ...) return;` — **falla en silencio**:
    el botón "Registrar" no hace nada, sin error ni aviso.
  - Doble fix: cuenta por defecto al registrarse + señal de error en el submit.

- [ ] **Los presupuestos no sobreviven al cambio de mes.**
  - `Budget` exige `month` + `year` fijos, sin recurrencia.
  - El presupuesto de enero desaparece en febrero → dashboard vacío → se rompe el loop
    de retención (registro → feedback → ajuste).

- [ ] **`Account PUT` ignora cambios de `currency` silenciosamente.**
  - `AccountUpdate` hereda `currency` de `AccountBase`, pero `accounts.py` solo actualiza
    `name`, `type` y `highlighted`. El frontend envía `currency` sin efecto.

---

## 🟡 Integridad y escala

- [ ] **Sin índices en `transactions`.**
  - `user_id`, `account_id`, `category_id`, `date` sin índice.
  - Todas las queries filtran por `user_id + date` → table scans conforme crezca el historial.

- [ ] **Sin constraint `UNIQUE(user_id, category_id, month, year)` en `budgets`.**
  - Se valida solo en Python → dos requests concurrentes crean duplicados.

- [ ] **FKs de `transactions` sin `nullable=False`.**
  - `user_id`, `account_id`, `category_id` aceptan NULL. Integridad débil.

- [ ] **Saldos de cuenta sin reconciliación posible.**
  - `Account.balance` se muta con deltas y no existe la operación "recalcular desde movimientos".
  - Si un saldo se desvía, no hay forma de detectarlo ni corregirlo.
  - `AccountCreate.balance` mezcla saldo de apertura con saldo derivado.
  - Sigue en scope porque las cuentas quedan visibles (decisión 2026-08-22).

- [ ] **Sin idempotencia en `POST /transactions`.**
  - Un reintento por mala señal crea una transacción duplicada y descuadra el saldo.
  - Crítico para los atajos móviles del backlog.

- [ ] **Rate limiting en memoria (`slowapi`).**
  - No funciona con múltiples workers ni múltiples instancias.

- [ ] **El logout no invalida el access token.**
  - El JWT sigue siendo válido hasta 60 min después de cerrar sesión.

- [ ] **Migración legacy de categorías en cada arranque.**
  - `seed_default_categories()` renombra `"Otro (Gasto)"` y migra `"Otro (Ingreso)"`
    en **cada** startup, asignando transacciones de tipo `income` a una categoría `expense`.
  - Debe convertirse en migración Alembic de una sola vez.

- [ ] **JWT guardado en `localStorage`** (`frontend/lib/api.ts`).
  - Riesgo de robo vía XSS. Alternativa: cookie `httpOnly` + `secure` + `sameSite`.
  - Sube de prioridad al salir de la red privada Tailscale.

- [ ] **Sin logging estructurado ni observabilidad.**
  - No se puede diagnosticar el reporte de un usuario.

---

## 🟢 Modularidad — revisar cuando el código duela al modificarlo

- [ ] **Lógica de negocio embebida en routers FastAPI.**
  - Los routers hacen de controller + service + repository. `app/services/` no existe.
  - El caso más grave es la lógica contable, duplicada en crear/actualizar/eliminar transacción.

- [ ] **Sin capa de excepciones de dominio.**
  - Todo `raise HTTPException` mezclado con reglas de negocio.

- [ ] **`schemas.py` y `models.py` como archivos únicos.**
  - Manejable a 6 entidades; el nuevo MVP agrega varias (tokens API, suscripciones push,
    avisos) → partir por dominio.

- [ ] **Frontend: fetching duplicado por página.**
  - `useQuery` + `queryFn` inline repetido. Extraer a `useAccounts`, `useCategories`, etc.

- [ ] **`transactions/page.tsx` creció a 604 líneas.**
  - El code review de julio reportaba 380. La tendencia importa más que el número.

- [ ] **Tipos de dominio no compartidos backend→frontend.**
  - Enums en Python vs string unions en TS, mantenidos a mano.
  - Con una app nativa serían tres copias. Resolver con codegen desde OpenAPI.

- [ ] **Nomenclatura mezclada español/inglés** dentro del mismo módulo.
  - `crear_transaccion` devuelve `TransactionResponse`; variables `cuenta`/`transaccion`
    junto a `models.Account`. Irrelevante en solitario, molesto si el proyecto se abre.

---

## 🔵 Solo si el proyecto crece

- [ ] CI/CD (lint + test + build en cada cambio).
- [ ] Tests de frontend (Vitest + React Testing Library).
- [ ] Sincronización offline (las columnas `updated_at` de la Fase 8 la dejan preparada).

---

## Resueltos

| Fecha | Item |
|-------|------|
| 2026-07-14 | datetime.utcnow() migrado a datetime.now(timezone.utc) |
| 2026-07-14 | Formularios migrados de raw input/select a componentes UI |
| 2026-07-14 | Bug multi-moneda en `/dashboard/summary` (agrupación por moneda) |
| 2026-07-14 | Headers de seguridad vía middleware FastAPI |
| 2026-07-14 | Sanitización de errores en `cashflow-series` |
| 2026-07-11 | Migración SQLite → PostgreSQL via Docker |
| 2026-07-10 | Rate limiting en login verificado y documentado |
| 2026-07-10 | CSS bug dashboard corregido (max-w-[1600px] no se aplicaba) |
| 2026-07-10 | finanzas.db excluido de git (*.db en .gitignore) |
| 2026-07-08 | Montos float → Decimal/Numeric(14,2) |
| 2026-07-08 | Refresh tokens implementados |
| 2026-07-06 | CORS → variable de entorno ALLOWED_ORIGINS |
| 2026-07-06 | SECRET_KEY regenerada criptográficamente |
| 2026-07-06 | EmailStr + normalización email |
| 2026-07-06 | .dict() → model_dump() |
