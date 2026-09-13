# Deuda Técnica Consciente — Oikos

> Este archivo documenta atajos tomados a propósito y hallazgos de auditoría pendientes.
> Repriorizado el **2026-08-22** tras el cambio de enfoque a producto multi-usuario
> (ver [ROADMAP.md](ROADMAP.md)).

Formato: `[ ]` pendiente · `[x]` resuelto — marcar con fecha al resolver.

> **Contexto del cambio:** varios items estaban clasificados como baja prioridad bajo el
> supuesto "solo lo uso yo, en red privada Tailscale". Ese supuesto ya no aplica.

> **2026-09-06 — Tailscale Funnel activado para uso personal diario.** Oikos ahora es
> alcanzable en `https://<host>.<tailnet>.ts.net` desde fuera de la red privada (celular,
> datos móviles), no solo desde IPs `100.x.x.x` del tailnet. Sigue siendo de un solo usuario
> (vos), así que los bloqueantes de abajo no aplican todavía en el sentido estricto de
> "usuario que no seas vos" — pero el tráfico ya no está contenido a una VPN privada, así que
> vale la pena no postergar demasiado el envío real de email (recuperación de contraseña si
> perdés acceso) y el cron de backup.

---

## 🔴 Bloqueantes — antes de que exista un usuario que no seas tú

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

- [ ] **API keys: TTL opcional y scopes siguen siendo decisiones de producto abiertas
  (revisión de seguridad 2026-09-06, ver Resueltos más abajo para lo ya corregido).**
  - **TTL obligatorio**: sigue sin haber expiración forzada (criterio PAT de GitHub). El
    fix de revocación en reset de contraseña (ver Resueltos) reduce el escenario de mayor
    riesgo (persistencia tras un incidente detectado), pero no cubre una key filtrada en
    un canal que el usuario nunca conecta con "mi cuenta está comprometida" (ej. un backup
    de iCloud del Shortcut expuesto). Sugerido para v2 si se prioriza: TTL opcional con
    default largo (ej. 1 año) en vez de "nunca".
  - **Scopes**: se mantiene sin scopes en v1 (mismos permisos que el JWT). Dado que el
    caso de uso principal (Shortcuts/apps de terceros) es exactamente el que más se
    beneficiaría de un scope angosto ("solo crear transacciones"), vale la pena
    reconsiderar si el catálogo de integraciones crece más allá de 1-2 automatizaciones
    personales por usuario.

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
  - Resuelto a medias en Fase 16 §16.3: ya existe codegen desde OpenAPI
    (`frontend/types/generated/api.ts` + script `pnpm gen:types`), usado para código nuevo
    (API keys, reconciliación). Pendiente: migrar oportunistamente los call sites existentes
    que usan los tipos manuales (Decisión 16.3.2, convivencia deliberada sin fecha de
    deprecación).

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
| 2026-09-13 | Login con Google (Fase 20 §20.3, ítem 3) — `POST /api/v1/auth/google` con ID token de Google Identity Services: `users.password_hash` pasa a nullable + nueva columna `users.google_id` (migración `5b79ad1d27e4`), auto-link de cuentas existentes por email y `email_verified=true` de inmediato (Decisión P4), cuenta por defecto + categorías ocultas vía helper compartido `inicializar_datos_usuario_nuevo`, botón `GoogleAuthButton` en login/register (oculto si falta `NEXT_PUBLIC_GOOGLE_CLIENT_ID`). Nota P4 sobre el bloqueo de SMTP (ver entrada 2026-09-12): ya **no es un bloqueo total** — el login con Google es una vía de registro que funciona de punta a punta incluso con `EMAIL_PROVIDER=console`; el registro por contraseña sigue dependiendo de SMTP real. Ver `docs/specs/fase_20_spec.md` |
| 2026-09-13 | Plantilla de correo con marca (Fase 20) — los correos de verificación/reset ya no son un `<p>` con link pelado; ahora usan `render_email_html()` (header "Oikos", botón real, link de respaldo en texto) — ver `docs/ROADMAP.md` Fase 20 |
| 2026-09-12 | `EMAIL_PROVIDER=smtp` configurado y verificado de punta a punta contra el `.env` real de despliegue (Gmail + contraseña de aplicación): registro → email real entregado → click en el link → `email_verified=true` → login que antes daba `403 EMAIL_NOT_VERIFIED` ahora da `200`. Las credenciales viven solo en el `.env` del despliegue (gitignored, no en el repo) — `backend/.env` (modo sin Docker) sigue sin estas variables, así que correr sin Docker sigue cayendo a `EMAIL_PROVIDER=console` salvo que se agreguen ahí también |
| 2026-09-12 | Login ahora exige `email_verified` (reversa la decisión original de Fase 7 §2.2 de no bloquear el login): `POST /api/v1/auth/login` responde `403` con `detail.code == "EMAIL_NOT_VERIFIED"` para un usuario sin verificar; nuevo `POST /api/v1/auth/resend-verification` (enumeration-safe, 5 req/min) reenvía el link. `seed.py` marca el usuario de prueba como verificado para no romper el seed. Efecto secundario: el auto-login post-registro (Decisión 15.0.3) ahora falla para todo usuario nuevo y cae al fallback existente (`/login?registered=true`) — el onboarding instantáneo post-registro queda pausado hasta que el usuario verifique, ver bloqueante de envío real de correo arriba |
| 2026-09-12 | Fase 17 — presupuestos multi-moneda y analítica por cuenta: índice único de `budgets` ensanchado a `(user_id, category_id, month, year, currency)` (migración `b5a09d0bed5e`) + `actualizar_presupuesto` ahora asigna `currency` con `try/except IntegrityError` (antes el campo se ignoraba en silencio y editar la moneda a una ocupada daba 500, mismo patrón que el gap de `AccountUpdate.currency`) + filtro por moneda en `dashboard/budgets-progress` (filtra filas, no recalcula `spent`) + motor de alertas evaluado con `.all()` por presupuesto (antes `.first()` dejaba sin avisar al segundo presupuesto por categoría/período en otra moneda) + `account_id` en `dashboard/category-distribution` + nuevo `GET /accounts/{id}/monthly-summary` — ver `docs/specs/fase_17_spec.md` §17.1/17.2 |
| 2026-09-06 | Saldos de cuenta sin reconciliación posible — resuelto en Fase 16 §16.4: `opening_balance` inmutable (con backfill en la migración `e460a42926d7`) + `POST /accounts/{id}/reconcile`. Nota: el backfill solo establece línea de base hacia adelante, no audita desviaciones históricas (ver `BUSINESS_RULES.md`) |
| 2026-09-06 | API keys personales revocables (Fase 16 §16.1): tabla `api_keys` (migración `6c9bbf3564cc`), auth alternativa `oikos_pat_*` en `get_current_user`, CRUD `/api/v1/api-keys/`, UI en `/settings` |
| 2026-09-06 | Revisión de seguridad de API keys (Decisión 16.1.8) corrida y sus hallazgos accionables corregidos: reset de contraseña ahora revoca también las API keys activas (antes solo revocaba refresh tokens, dejando una key minteada durante un compromiso viva para siempre — `auth.py`); el rate limit de `POST /transactions` pasó de clavear por hash de la key a clavear por `user_id` resuelto en DB (antes un usuario con N keys multiplicaba por N su cuota real de 60/min — `rate_limit.py`); `POST /api-keys/` ganó rate limit `5/minute` + tope de 20 keys activas por usuario (antes no tenía ninguno de los dos — `api_keys.py`). TTL obligatorio y scopes quedan como recomendaciones de producto sin implementar, ver 🟡 |
| 2026-08-23 | Idempotencia en `POST /transactions` (`Idempotency-Key` + tabla `idempotency_keys`) — resuelto en Fase 10, ver `docs/ROADMAP.md` §10.4. Entrada corregida el 2026-09-06 al detectarse desactualizada durante el análisis de la Fase 16 (`docs/specs/fase_16_spec.md`, hallazgo 12) |
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
