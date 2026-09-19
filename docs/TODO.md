# Deuda Técnica Consciente — Oikos

> Este archivo documenta atajos tomados a propósito y hallazgos de auditoría pendientes.
> Repriorizado el **2026-08-22** tras el cambio de enfoque a producto multi-usuario
> (ver [ROADMAP.md](ROADMAP.md)).

Formato: `[ ]` pendiente · `[x]` resuelto — marcar con fecha al resolver.

> **Contexto del cambio:** varios items estaban clasificados como baja prioridad bajo el
> supuesto "solo lo uso yo, en red privada Tailscale". Ese supuesto ya no aplica.

> **2026-09-15 — Auditoría completa** (seguridad, arquitectura/mantenibilidad, UX/frontend)
> corrida a pedido del usuario. Ítems nuevos marcados `(auditoría 2026-09-15)` abajo. También
> corrigió una afirmación desactualizada en `CLAUDE.md` sobre `EMAIL_PROVIDER` (decía
> "console en todos lados"; en realidad `smtp` está configurado y verificado en el
> despliegue real desde 2026-09-12 — solo falta en `backend/.env` para correr sin Docker).

> **2026-09-06 — Tailscale Funnel activado para uso personal diario.** Oikos ahora es
> alcanzable en `https://<host>.<tailnet>.ts.net` desde fuera de la red privada (celular,
> datos móviles), no solo desde IPs `100.x.x.x` del tailnet. Sigue siendo de un solo usuario
> (vos), así que los bloqueantes de abajo no aplican todavía en el sentido estricto de
> "usuario que no seas vos" — pero el tráfico ya no está contenido a una VPN privada, así que
> vale la pena no postergar demasiado el envío real de email (recuperación de contraseña si
> perdés acceso) y el cron de backup.

---

## 🔴 Bloqueantes — antes de que exista un usuario que no seas tú

- [x] **Account takeover vía auto-link de Google OAuth (auditoría de seguridad 2026-09-15) —
  resuelto.** *(2026-09-18, Fase 23, `docs/specs/fase_23_spec.md`, commit `6e4d11a`)*
  - `login_google` ahora anula `password_hash` al auto-linkear una cuenta que todavía no
    estaba verificada (`not user.email_verified` capturado antes de mutar nada) — cualquier
    contraseña plantada por un atacante deja de ser válida contra `POST /auth/login` en
    cuanto la víctima real hace login con Google. Una cuenta ya verificada antes de vincular
    Google conserva su contraseña sin cambios.
  - Test de regresión del bug original (`test_existing_unverified_password_account_is_
    autolinked`) corregido + test nuevo del escenario hostil completo
    (`test_autolink_on_unverified_account_nullifies_attacker_planted_password`) +
    regresión sobre la cuenta ya verificada.
  - Nada pendiente de esta entrada — no quedó ningún ítem sin implementar de Fase 23 sobre
    este hallazgo.

---

## 🟠 Bugs confirmados (auditoría 2026-08-22 + 2026-09-15)

- [x] **El dashboard confunde "error de red" con "no hay datos" (auditoría 2026-09-15) —
  resuelto.** *(2026-09-18, Fase 24 §24.1, `docs/specs/fase_24_spec.md`, commit `529de0c`)*
  - Las 4 queries del dashboard (summary/budgets-progress/recent-transactions/category-
    breakdown) ahora exponen `isError`/`refetch`; cada sección muestra un mensaje
    específico + botón "Reintentar" independiente (reutilizando `EmptyState` con un slot
    `action` nuevo) en vez de caer en el mismo estado visual que "sin datos todavía".

- [x] **Formulario de ingreso mensual inline en el dashboard falla en silencio
  (auditoría 2026-09-15) — resuelto.** *(2026-09-18, Fase 24 §24.2, commit `529de0c`)*
  - El `<form>` ahora tiene `noValidate`, el guard custom setea un error de campo visible
    (prop `error` de `Input`) y mueve el foco al input en vez de hacer `return` silencioso
    — mismo patrón que Fase 12 §12.8.

- [x] **`POST /push/subscribe` no valida ownership del `endpoint` (auditoría 2026-09-15) —
  resuelto.** *(2026-09-18, Fase 23, commit `6e4d11a`)*
  - No se bloqueó la reasignación cross-usuario: bloquear rompería el caso legítimo, ya
    documentado a propósito en el propio docstring, de un dispositivo compartido entre dos
    usuarios distintos — y con los datos del request no hay forma de distinguir ambos casos
    del lado del servidor. En vez de eso, cada reasignación que cruza de un usuario a otro
    queda auditada con `logger.warning(...)`, visible vía `docker compose logs -f backend`.
    Severidad ya tasada como baja (el `endpoint` no es adivinable) — visibilidad, no bloqueo.
  - Test nuevo: `test_subscribe_reassigns_ownership_across_users_and_logs_it`
    (`backend/tests/test_push.py`).

- [ ] **`docker-compose.yml` publica backend (8000) y frontend (3000) en todas las
  interfaces, no solo Tailscale (auditoría 2026-09-15).**
  - Los puertos se publican como `"8000:8000"`/`"3000:3000"` (bind a `0.0.0.0`).
  - **Verificado con el usuario (2026-09-16): el host no tiene ninguna otra interfaz de red
    pública** (solo Tailscale) — el riesgo queda confirmado como teórico/bajo por ahora. Se
    deja anotado, sin tarea de fase: revisar de nuevo si el despliegue alguna vez gana otra
    ruta de red (IP pública directa, otra VPN, NAT de nube).

- [x] **Un usuario nuevo no puede registrar nada — obsoleto, ya resuelto.** *(detectado como
  desactualizado el 2026-09-16, al convertir el audit en fases del ROADMAP)*
  - Este ítem quedó sin marcar tras la Fase 8 (2026-08-23, "Cuenta por defecto al registrarse"):
    `inicializar_datos_usuario_nuevo` (`backend/app/api/users.py:48-90`) ya crea una cuenta por
    defecto en el registro desde esa fecha. Verificado contra el código actual — el bug no
    existe más.

- [x] **Los presupuestos no sobreviven al cambio de mes — obsoleto, ya resuelto.** *(detectado
  como desactualizado el 2026-09-16, misma pasada que el ítem anterior)*
  - `Budget.is_recurring` (`backend/app/models/models.py:107`) y `budget_recurrence.py`
    (`ensure_recurring_budgets_for_period`) ya resuelven esto desde Fase 8 (2026-08-23,
    "Presupuestos recurrentes"). Verificado contra el código actual. El único gap real
    relacionado es la falta de test directo sobre esa función — ver Fase 25 del ROADMAP.

- [x] **`Account PUT` ignora cambios de `currency` silenciosamente — resuelto.** *(2026-09-18,
  Fase 24 §24.3, commit `529de0c`)*
  - `actualizar_cuenta` ahora aplica `currency` cuando cambia de verdad y la cuenta no tiene
    transacciones activas; si las tiene, responde `400` (mismo criterio que `eliminar_cuenta`)
    en vez de ignorar el campo en silencio. De paso pasó a actualización parcial real
    (`model_fields_set`), lo que también corrigió un bug encontrado en el camino: un `PUT`
    que omitía `highlighted` lo reseteaba a `false` en cada edición de nombre/tipo.
  - Verificado que hoy ningún caller de la UI web envía `currency` en este endpoint (el modal
    de edición no tiene selector de moneda) — el efecto observable es para callers directos
    de la API por ahora.

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

- [ ] **`frontend/docs/STATE_AND_FETCHING.md` (el mapa de query keys/invalidación) está
  congelado en Fase 16 (auditoría 2026-09-15).**
  - No menciona nada de Fases 17-22: `queryKeys.accounts.monthlySummary`/`budgetsProgress`
    por cuenta (`frontend/lib/queryKeys.ts`), los params `account_id`/`currency` agregados
    a `analytics.cashflow`/`analytics.categories`, las keys de categorías ocultas, ni las
    mutations de settings de Fase 21/22. CLAUDE.md lo señala como el mapa autoritativo —
    hoy es engañoso para cualquiera (agente o humano) que confíe en él en vez de grepear.
    Mismo nivel de disciplina que ya se exige para `API_REFERENCE.md`/`API_CONTRACT.md`:
    actualizar en el próximo touch a cualquiera de estas áreas.
  - **→ Programado en `docs/ROADMAP.md` Fase 25** (2026-09-16).

- [ ] **JWT guardado en `localStorage`** (`frontend/lib/api.ts`).
  - Riesgo de robo vía XSS. Alternativa: cookie `httpOnly` + `secure` + `sameSite`.
  - Sube de prioridad al salir de la red privada Tailscale. Mitigado parcialmente en Fase 7:
    el TTL del access token bajó de 60 a 15 min, así que la ventana de robo es más corta.
  - **→ Programado en `docs/ROADMAP.md` Fase 25** (2026-09-16).

---

## 🟢 Modularidad — revisar cuando el código duela al modificarlo

- [ ] **Lógica de negocio embebida en routers FastAPI — y la excepción ya existente apunta
  al lado equivocado (actualizado 2026-09-15).**
  - Los routers hacen de controller + service + repository. `app/services/` no existe
    formalmente, pero ya emergió una capa de servicio ad-hoc dentro de `app/core/`:
    `budget_alerts.py`, `budget_recurrence.py`, `notification_dispatch.py`,
    `weekly_summary.py`, `user_deletion.py` — cada uno usado por 2+ routers o el scheduler.
  - El problema: la extracción pasó para notificaciones/scheduling, **no** para el código
    de mayor riesgo. La lógica contable (signo del delta: `income → +` / `expense → -`)
    sigue copy-pasteada tres veces en `transactions.py` (`crear_transaccion`,
    `actualizar_transaccion`, `eliminar_transaccion`) — es el código que mueve la plata de
    otras personas, y es el que debería haberse extraído primero, no al final.
  - Cuando se cree `app/services/`, empezar por un `ledger.py`/`transaction_accounting.py`
    con esa lógica, usando `budget_alerts.py` como plantilla de cómo ya funciona
    core/-como-service en este repo.
  - **→ Programado en `docs/ROADMAP.md` Fase 25** (2026-09-16).

- [ ] **`schemas.py` (462 líneas, 49 clases) está más forzado que `models.py` (341 líneas,
  14 clases) — priorizar partir schemas primero (auditoría 2026-09-15).**
  - Los modelos están bien comentados y cada clase es autocontenida; separarlos no es
    urgente. Los schemas mezclan auth/transacciones/notificaciones/push/API-keys en un solo
    archivo plano sin separación por dominio — es el candidato real si solo se hace uno.
  - **→ Programado en `docs/ROADMAP.md` Fase 25** (2026-09-16).

- [ ] **`budget_recurrence.py` sin test dedicado para la lógica de generación de períodos
  (auditoría 2026-09-15).**
  - `test_budgets.py` solo verifica que el flag `is_recurring` sobreviva el round-trip;
    nunca ejercita `ensure_recurring_budgets_for_period` directamente — es justo la lógica
    detrás de la resolución de Fase 8 ("los presupuestos no sobreviven al cambio de mes",
    ver nota de obsolescencia en 🟠 arriba) — vale la pena blindarlo con test antes de
    tocarlo de nuevo.
  - Nota positiva de la misma auditoría: Google OAuth, API keys y push sí están bien
    testeados (`test_auth.py`, `test_api_keys.py`, `test_push.py`) — mejor cobertura de lo
    que sugiere la narrativa de CLAUDE.md. El frontend sigue en cero tests, confirmado.
  - **→ Programado en `docs/ROADMAP.md` Fase 25** (2026-09-16).

- [ ] **Sin capa de excepciones de dominio.**
  - Todo `raise HTTPException` mezclado con reglas de negocio.
  - **→ Programado en `docs/ROADMAP.md` Fase 25** (2026-09-16).

- [ ] **`schemas.py` y `models.py` como archivos únicos.**
  - Manejable a 6 entidades; el nuevo MVP agrega varias (tokens API, suscripciones push,
    avisos) → partir por dominio.
  - **→ Programado en `docs/ROADMAP.md` Fase 25** (2026-09-16, mismo ítem que el de arriba
    sobre `schemas.py`/`models.py` — entrada duplicada preexistente, se deja para no perder
    historial pero apunta a la misma tarea).

- [ ] **Frontend: fetching duplicado por página.**
  - `useQuery` + `queryFn` inline repetido. Extraer a `useAccounts`, `useCategories`, etc.
  - **→ Programado en `docs/ROADMAP.md` Fase 25** (2026-09-16).

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

- [x] **`category-distribution` no expone `icon` — resuelto.** *(2026-09-18, Fase 24 §24.4,
  commit `529de0c`)*
  - `CategoryDistributionData`/`category-distribution` ahora exponen `category_icon` (mismo
    campo que `BudgetProgress`), y `CategoryBreakdownBars` lo consume — el desglose por
    categoría del dashboard muestra el ícono real en vez de caer siempre al fallback `Wallet`.

---

## 🔵 Solo si el proyecto crece

- [ ] CI/CD (lint + test + build en cada cambio).
- [ ] Tests de frontend (Vitest + React Testing Library).
- [ ] Sincronización offline (las columnas `updated_at` de la Fase 8 la dejan preparada).

---

## Resueltos

| Fecha | Item |
|-------|------|
| 2026-09-13 | `NEXT_PUBLIC_GOOGLE_CLIENT_ID` no llegaba al bundle del frontend en Docker — `docker-compose.yml` solo pasaba `NEXT_PUBLIC_API_URL` como build arg del servicio `frontend`, y `frontend/Dockerfile` no tenía el `ARG`/`ENV` correspondiente para `NEXT_PUBLIC_GOOGLE_CLIENT_ID`. Efecto: aunque se configurara la variable en `.env`, `GoogleAuthButton` nunca la vería y el botón de Google no aparecía en `login`/`register`. Corregido: build arg agregado en `docker-compose.yml` (prod) y `docker-compose.dev.yml` (dev, vía `environment:`), `ARG`/`ENV` agregado en `frontend/Dockerfile`. Sigue pendiente generar el Client ID real en Google Cloud Console y setearlo en el `.env` de despliegue — sin eso, el botón sigue sin aparecer aunque el plumbing ya esté arreglado |
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
| 2026-09-13 | Backup automático programado — servicio `backup` en docker-compose.yml (dispara en cada `docker compose up`, no cron de host) + subida cifrada a Google Drive (cuenta de Oikos) vía rclone crypt, retención 7d local / 30d nube. Ver docs/BACKUPS.md. Reemplaza el bloqueante de arriba |
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
