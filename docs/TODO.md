# Deuda Técnica Consciente — Oikos

> Este archivo documenta atajos tomados a propósito y hallazgos de auditoría pendientes.
> Repriorizado el **2026-08-22** tras el cambio de enfoque a producto multi-usuario
> (ver [ROADMAP.md](ROADMAP.md)).

Formato: `[ ]` pendiente · `[x]` resuelto — marcar con fecha al resolver.

> **Contexto del cambio:** varios items estaban clasificados como baja prioridad bajo el
> supuesto "solo lo uso yo, en red privada Tailscale". Ese supuesto ya no aplica.

---

## 🔴 Bloqueantes — antes de que exista un usuario que no seas tú

- [ ] **Recuperación de contraseña y verificación de email implementadas, pero sin envío real de correo.**
  - El código de Fase 7 está completo y probado (`backend/app/api/auth.py`, `docs/specs/fase_07_spec.md`
    §2.1/§2.2): tokens de un solo uso, expiración, páginas de frontend en `/forgot-password`,
    `/reset-password`, `/verify-email`. Pero `EMAIL_PROVIDER` sigue en `console` en todos los
    entornos — el email nunca sale de verdad, solo se loguea (`docker compose logs backend`,
    buscar `"email_body"`).
  - **Sigue siendo un bloqueante real para un usuario que no seas vos**: sin `EMAIL_PROVIDER=smtp`
    + credenciales reales (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL`
    en el `.env` de la raíz), nadie externo puede recibir el link de reset ni el de verificación.
  - Acción: elegir un proveedor transaccional (Resend, Mailgun, SES, SMTP de un dominio propio),
    generar credenciales, y setear las variables en el `.env` de despliegue. No requiere cambios
    de código — `app/core/email.py` ya soporta el modo `smtp`.

- [ ] **Backup de PostgreSQL: script listo, sin programar.**
  - `scripts/backup.sh` existe y funciona (`pg_dump` + gzip + rotación de 7 días,
    `scripts/restore.sh` para restaurar), pero no hay ningún cron ni scheduler que lo dispare
    automáticamente todavía — hay que correrlo a mano o programarlo vos mismo.
  - Con datos de terceros, no tener el cron armado pasa de molesto a inaceptable.
  - Acción: `crontab -e` en el host de despliegue, ej. `0 3 * * * cd /ruta/al/repo && ./scripts/backup.sh`.

---

## 🟠 Bugs confirmados (auditoría 2026-08-22)

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

- [ ] **Saldos de cuenta sin reconciliación posible.**
  - `Account.balance` se muta con deltas y no existe la operación "recalcular desde movimientos".
  - Si un saldo se desvía, no hay forma de detectarlo ni corregirlo.
  - `AccountCreate.balance` mezcla saldo de apertura con saldo derivado.
  - Sigue en scope porque las cuentas quedan visibles (decisión 2026-08-22).

- [ ] **Sin idempotencia en `POST /transactions`.**
  - Un reintento por mala señal crea una transacción duplicada y descuadra el saldo.
  - Crítico para los atajos móviles del backlog.

- [ ] **Rate limiting en memoria (`slowapi`), sin backend distribuido.**
  - No funciona con múltiples workers ni múltiples instancias — pero hoy el backend corre en
    un solo worker sin réplicas, así que el problema no existe todavía. Diferido a propósito
    en Fase 7 (`docs/specs/fase_07_spec.md` §2.6.1): diseño listo (Redis + `storage_uri`),
    implementar cuando `Dockerfile`/`docker-compose.yml` pasen a `--workers > 1` o más de una
    réplica.

- [ ] **JWT guardado en `localStorage`** (`frontend/lib/api.ts`).
  - Riesgo de robo vía XSS. Alternativa: cookie `httpOnly` + `secure` + `sameSite`.
  - Sube de prioridad al salir de la red privada Tailscale. Mitigado parcialmente en Fase 7:
    el TTL del access token bajó de 60 a 15 min, así que la ventana de robo es más corta.

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

- [ ] **`category-distribution` no expone `icon` — el desglose por categoría del dashboard
  usa un ícono genérico en todas las filas.**
  - `CategoryBreakdownBars` (Fase 11 §11.4) siempre cae al fallback `Wallet`: el schema
    `CategoryDistributionData` no trae `category_icon` como sí lo hace `BudgetProgress`.
  - Bajo impacto: cosmético, no afecta montos ni orden. Agregar el campo al schema y al
    query de `obtener_distribucion_categorias` si se quiere ícono real por fila.

---

## 🔵 Solo si el proyecto crece

- [ ] CI/CD (lint + test + build en cada cambio).
- [ ] Tests de frontend (Vitest + React Testing Library).
- [ ] Sincronización offline (las columnas `updated_at` de la Fase 8 la dejan preparada).

---

## Resueltos

| Fecha | Item |
|-------|------|
| 2026-08-23 | Fase 11 — bugs multi-moneda del dashboard: `budgets-progress` agrupa el gasto por `(categoría, moneda)` y expone `currency`; `cashflow-series` y `category-distribution` filtran por una sola moneda (param `currency`, default la preferida) — ver `docs/specs/fase_11_spec.md` §11.1 |
| 2026-08-23 | Bug `actualizar_transaccion` no actualizaba `currency`: ahora siempre hereda la moneda de la cuenta destino, igual que en la creación (Fase 11 §11.2) |
| 2026-08-22 | Fase 7 completa — ver `docs/specs/fase_07_spec.md` para el detalle de cada ítem: |
| 2026-08-22 | Migraciones versionadas con Alembic (reemplaza `create_all()` + `_ensure_*_column()` ad-hoc) |
| 2026-08-22 | Bug `preferred_theme` nunca se agregaba a DBs existentes (resuelto por la migración baseline) |
| 2026-08-22 | Índices en `transactions` (`user_id`+`date` compuesto, `account_id`, `category_id`) |
| 2026-08-22 | Constraint `UNIQUE(user_id, category_id, month, year)` en `budgets` |
| 2026-08-22 | FKs de `transactions` con `nullable=False` |
| 2026-08-22 | Migración legacy de categorías retirada de `seed_default_categories()` (corría en cada arranque) |
| 2026-08-22 | Secretos fuera de `docker-compose.yml` — `POSTGRES_PASSWORD`/`SECRET_KEY` obligatorias, sin default silencioso |
| 2026-08-22 | Versionado de API bajo `/api/v1/` (backend + frontend, `lib/api.ts` centraliza el prefijo) |
| 2026-08-22 | Tests del módulo contable y de autenticación (pytest + httpx, `backend/tests/`) |
| 2026-08-22 | Recuperación de contraseña y verificación de email (código completo — ver bloqueante de envío real arriba) |
| 2026-08-22 | Política de contraseñas (`min_length=10` + validación de fuerza) |
| 2026-08-22 | Rate limiting en registro y en recuperación de contraseña |
| 2026-08-22 | Logout invalida efectivamente el access token (TTL bajado de 60 a 15 min) |
| 2026-08-22 | Regex CORS de Tailscale condicional a `ENABLE_TAILSCALE_CORS`, ya no incondicional |
| 2026-08-22 | Logging estructurado (JSON a stdout) + `X-Request-ID` |
| 2026-08-22 | `scripts/backup.sh` con rotación de 7 días (falta programar el cron, ver bloqueante arriba) |
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
