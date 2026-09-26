# Contrato de API del Frontend

## Propósito

Este documento define cómo el frontend consume el backend de Oikos y qué supuestos puede hacer sobre los datos recibidos.

La regla base es simple: el frontend no recalcula saldos, progreso de presupuestos ni agregados financieros. El backend es la fuente de verdad.

## Base URL y autenticación

- Base URL: `NEXT_PUBLIC_API_URL`
- Fallback local: `http://localhost:8000`
- Prefijo de versión: `/api/v1` — está centralizado en el `baseURL` del cliente Axios en `lib/api.ts` (`` `${NEXT_PUBLIC_API_URL}/api/v1` ``), no repetido en cada call site. Los ~45 call sites de la app llaman a rutas relativas sin prefijo (ej. `api.get('accounts/')`); las rutas documentadas abajo omiten `/api/v1` por brevedad pero es lo que efectivamente se resuelve en runtime.
- Autenticación por **cookies httpOnly** (Fase 26, `docs/specs/fase_26_spec.md`): el backend setea tres cookies de sesión al autenticar — `access_token` (HttpOnly, 15 min), `refresh_token` (HttpOnly, 30 días, Path acotado a `/api/v1/auth`) y `csrf_token` (NO HttpOnly, legible por JS, mismo Max-Age que el refresh).
- El frontend **ya no** lee/escribe JWT en `localStorage` (Decisión F1/F3/B9): la instancia Axios usa `withCredentials: true` y el cookie viaja solo en cada request al mismo origen.
- El frontend **ya no** arma `Authorization: Bearer <token>` (Decisión F1): ese header queda reservado para clientes no-browser (API keys `oikos_pat_...`, que no usan cookies).
- Mutaciones (todo método que no sea `GET`/`HEAD`): el interceptor de request de `lib/api.ts` agrega el header `X-CSRF-Token` con el valor del cookie `csrf_token` (patrón double-submit cookie, Decisión B5). Si el backend recibe una mutación con cookie de sesión pero sin ese header (o con valor distinto), responde `403` `{"detail": "Token CSRF inválido o ausente."}`.

Si el backend responde `401`, el frontend intenta renovar la sesión con `POST /api/v1/auth/refresh` **sin body** — el cookie `refresh_token` (HttpOnly) viaja solo gracias a `withCredentials`, y también aplica en esta llamada puntual porque usa la instancia `api` configurada (Hallazgo 3/Decisión F1, no `axios` crudo). Si la renovación falla, redirige a `/login`.

El access token expira en 15 min (bajado de 60 min en Fase 7, §2.5 de `docs/specs/fase_07_spec.md`) — el interceptor de refresh de `lib/api.ts` se dispara ~4 veces más seguido que antes. El código tiene protección contra refreshes concurrentes (flag `isRefreshing` + cola `failedQueue`), verificado como parte de Fase 7 y mantenido en la reescritura de Fase 26 (Decisión F1).

El backend expone además `POST /api/v1/auth/password-reset/request`, `POST /api/v1/auth/password-reset/confirm` y `GET /api/v1/auth/verify-email` (Fase 7, §2.1/§2.2), consumidos por `app/(auth)/forgot-password`, `reset-password` y `verify-email` respectivamente — ver detalle de payloads en `backend/docs/API_REFERENCE.md`.

**Desde 2026-09-12, `POST /api/v1/auth/login` exige email verificado** (reversa la decisión original de Fase 7 de no bloquear el login): un `403` con `detail` como objeto (`{code: "EMAIL_NOT_VERIFIED", mensaje: "..."}`, no un string) distingue este caso de credenciales inválidas. `login/page.tsx` chequea `detail.code` y, si coincide, muestra un botón "Reenviar correo de verificación" que llama a `POST /api/v1/auth/resend-verification` (`{email}`, enumeration-safe, siempre 200, 5 req/min).

## Endpoints consumidos por el frontend

### Autenticación

- `POST /api/v1/auth/login` → autentica con `OAuth2PasswordRequestForm` (x-www-form-urlencoded:
  `username` + `password`). La respuesta setea los tres cookies de sesión (Decisión B6). El body
  sigue devolviendo `access_token` + `refresh_token` + `token_type` por compatibilidad con
  clientes no-browser, pero el frontend **ya no los lee** (Fase 26, Decisión F3): el `Set-Cookie`
  de la respuesta deja la sesión lista.
- `POST /api/v1/auth/google` (Fase 20 §20.3) → login/registro con Google Identity Services.
  Body `{ id_token: string }` (el `credential` del callback de GIS). Respuesta con **la misma
  forma exacta** que `POST /auth/login`: `{ access_token, refresh_token, token_type }` + los
  tres cookies de sesión (Decisión B6). El backend resuelve internamente si es registro nuevo
  (crea el `User` con `email_verified=True` + cuenta por defecto + categorías ocultas) o
  vinculación automática de un email ya existente con contraseña. Consumido por
  `components/auth/GoogleAuthButton.tsx`, que hace `GET /users/me` y redirige según
  `has_transaction_history` (mismo criterio que `login/page.tsx`); desde Fase 26 no guarda
  tokens en `localStorage` (Decisión F3). Errores: `401` token de Google inválido/rechazado
  (firma/audiencia), `403` correo de Google no verificado en el claim, `503` backend sin
  `GOOGLE_CLIENT_ID` configurado. El frontend no renderiza el botón si
  `NEXT_PUBLIC_GOOGLE_CLIENT_ID` falta en build time, así que el `503` solo ocurre si ambas
  variables divergen (botón visible pero backend desconfigurado). Rate limit: 5 req/min, mismo
  que el resto de endpoints de auth anónimos.
- `POST /api/v1/auth/refresh` → rota el refresh token y setea cookies nuevos. Desde Fase 26 el
  frontend lo llama **sin body** (el cookie `refresh_token`, HttpOnly con Path
  `/api/v1/auth`, viaja solo — Decisión F1/Hallazgo 3); el body `{ refresh_token }`
  sigue siendo aceptado para clientes no-browser.
- `POST /api/v1/auth/logout` → revoca el refresh token y limpia los tres cookies de sesión en
  su propia respuesta (Decisión B7). Desde Fase 26 el frontend lo llama **sin body** (Decisión
  F4) — el cookie viaja solo; el body `{ refresh_token }` sigue siendo aceptado para clientes
  no-browser.
- `GET /api/v1/users/me`
- `PATCH /api/v1/users/me` (acepta `{ monthly_income }` — usado por la card "Balance del mes" del dashboard para fijar el ingreso mensual inline, Fase 11 §11.3)
- `GET /api/v1/users/me/preferences`
- `PATCH /api/v1/users/me/preferences`
- `DELETE /api/v1/users/me` — elimina la cuenta del usuario autenticado (Fase 21 §21.2). Body `{ password }`; `204` si ok, `403` si la contraseña es incorrecta, `401` sin token. Irreversible (hard delete de todo el usuario).

### Cuentas

- `GET /api/v1/accounts/`
- `GET /api/v1/accounts/summary` — saldo total por moneda de **TODAS** las cuentas del usuario, sin filtro de destacadas (Fase 11 §11.5). Devuelve `BalanceByCurrency[]`. Es distinto de `GET /dashboard/summary`, cuyo array `balances` sí filtra por cuentas destacadas cuando existen; este endpoint alimenta el encabezado de `accounts/page.tsx`, cuya lista tampoco filtra, para que el total coincida con las tarjetas listadas.
- `GET /api/v1/accounts/{account_id}`
- `GET /api/v1/accounts/{account_id}/monthly-summary` (Fase 17 §17.1.2, Decisión 17.1.2) —
  saldo/balance del mes de **una sola cuenta**, derivado de sus transacciones del mes actual
  (`monthly_income − monthly_expense`). A diferencia del `monthly_flow_balance` del dashboard
  (que usa ingreso declarado y puede ser `null`), este endpoint **nunca** devuelve `null` para
  `monthly_flow_balance`: sin transacciones devuelve `0`. Responde `AccountMonthlySummary`:
  `{ currency, monthly_income, monthly_expense, monthly_flow_balance }`. Los montos
  `Decimal` llegan serializados como `string` (Decisión 15.6) — el frontend los normaliza
  con `Number(...)` antes de formatear (ver `AccountMonthlyBalanceCard`).
- `POST /api/v1/accounts/`
- `PUT /api/v1/accounts/{account_id}` — actualización **parcial** desde Fase 24 §24.3
  (Decisión C1): solo aplica los campos presentes en el body, sin resetear a los defaults del
  schema los que se omitan (antes, omitir `highlighted` lo dejaba en `false`). `currency` solo
  se aplica si la cuenta **no** tiene transacciones activas; en caso contrario responde `400`
  con `detail` como string plano ("No se puede cambiar la moneda de una cuenta con
  transacciones asociadas."). Reenviar la misma moneda nunca dispara el guard. El frontend web
  **no envía `currency` en este PUT** (el modal de edición no tiene selector de moneda) — el
  cambio queda efectivo solo para callers directos de la API.
- `PATCH /api/v1/accounts/{account_id}/highlighted`
- `DELETE /api/v1/accounts/{account_id}`
- `POST /api/v1/accounts/{account_id}/reconcile` (Fase 16 §16.4) — recalcula `balance` desde
  `opening_balance` + historial de transacciones no eliminadas y aplica la corrección de
  inmediato (sin preview). Devuelve `AccountReconcileResponse` con `account_id`,
  `previous_balance`, `recalculated_balance`, `discrepancy` (los montos llegan como `string`,
  consistente con la serialización `Decimal` → string) y `opening_balance`. El frontend solo
  muestra el resultado ("El saldo está correcto" si `discrepancy` es 0 o
  "Se corrigió una diferencia de $X") e invalida las queries que leen el saldo
  (`account`, `accounts`, `accounts-summary`, `dashboardSummary`).

### Categorías

- `GET /api/v1/categories/`
- `GET /api/v1/categories/{category_id}`
- `POST /api/v1/categories/`
- `PUT /api/v1/categories/{category_id}`
- `DELETE /api/v1/categories/{category_id}`
- `POST /api/v1/categories/{category_id}/hide` (Fase 18 §18.3) — oculta la categoría "para
  mí" (204, idempotente; afecta solo el selector de captura, no históricos ni analítica).
  Válido tanto para categorías de sistema como propias (Decisión Q6 de la spec de Fase 18).
- `DELETE /api/v1/categories/{category_id}/hide` (Fase 18 §18.3) — la vuelve visible (204,
  idempotente).

### Transacciones

- `GET /api/v1/transactions/`
- `POST /api/v1/transactions/`
- `PUT /api/v1/transactions/{transaction_id}`
- `DELETE /api/v1/transactions/{transaction_id}`

Filtros soportados por el feed:

- `skip` (default: 0)
- `limit` (default: 100, usado internamente: 50)
- `account_id`
- `category_id`
- `start_date`
- `end_date`

El endpoint devuelve una respuesta paginada:

- `items`: `Transaction[]`
- `total`: `int` — total de resultados sin paginación
- `page`: `int` — página actual
- `page_size`: `int` — items por página

Body de creación (`POST`) desde Fase 16 §16.2:

- `category_id` e `account_id` ya no son obligatorios.
- `category` (nombre, `string`, opcional) es una alternativa a `category_id` — **XOR**: se
  debe enviar exactamente uno de `category_id` o `category`. La resolución por nombre es
  case/acento-insensible, filtra por `type` y da precedencia a las categorías propias sobre
  las de sistema. `404` si el nombre no existe; `409` si el usuario tiene más de una
  categoría propia con ese nombre (usar `category_id` en ese caso).
- `account_id` opcional: si se omite y el usuario tiene exactamente una cuenta, se usa esa;
  con más de una cuenta, el backend responde `400` pidiendo `account_id` explícito.

> Nota: `TransactionCreate` tipado por codegen (§16.3) refleja esta forma — ver
> `types/generated/api.ts`. El frontend web no usa estos campos opcionales todavía; el
> `TransactionCaptureForm` sigue enviando `category_id` + `account_id`.

Header opcional en `POST`:

- `Idempotency-Key` (opcional, máximo 255 caracteres): hace el POST idempotente para reintentos
  seguros (Fase 10 §10.4; espejo de `backend/docs/API_REFERENCE.md`, que es el contrato canónico).
  Si la clave ya fue usada antes por el mismo usuario:
  - con un payload idéntico → se devuelve la transacción original sin crear otra ni volver a mover
    el saldo (replay);
  - con un payload distinto → `409 Conflict` ("Esta Idempotency-Key ya se usó con datos
    distintos"); si la transacción original fue eliminada, también `409`.

Cómo lo usa el frontend (`TransactionCaptureForm.tsx`): genera una clave con `crypto.randomUUID()`
una vez por montaje del formulario y la regenera tras cada envío exitoso — así, los reintentos de
un mismo envío fallido reusan la clave y una captura nueva usa una clave distinta. El header viaja
en el tercer argumento de `api.post(...)` y sobrevive el reintento interno del interceptor de
refresh de token sin cambios en `lib/api.ts`. Solo aplica a este endpoint; `GET`/`PUT`/`DELETE` lo
ignoran.

### Presupuestos

- `GET /api/v1/budgets/`
- `POST /api/v1/budgets/`
- `PUT /api/v1/budgets/{budget_id}`
- `DELETE /api/v1/budgets/{budget_id}`

### Dashboard

- `GET /api/v1/dashboard/summary` — incluye `monthly_flow_balance: number | null` desde Fase 11 §11.3 (ver "Contratos de datos" abajo). Desde Fase 29 acepta los query params `year`/`month` y devuelve tres campos nuevos: `monthly_flow_basis`, `first_transaction_month` y `expense_currencies` (ver "Navegación por mes del dashboard" y "Contratos de datos > Dashboard").
- `GET /api/v1/dashboard/budgets-progress` — cada fila incluye `currency` desde Fase 11 §11.1.
  Desde Fase 17 §17.2.3 acepta además un query param opcional `currency: string` (Decisión
  17.2.3): si se pasa, el backend filtra las filas a esa moneda **sin recalcular `spent`**
  (el gasto de cada presupuesto es la suma cruzada de todas las cuentas del usuario en esa
  moneda — filtrar cambia qué filas se muestran, nunca cuánto gastó cada una). El frontend
  lo usa en `accounts/[id]` (las queries propias por cuenta pasan la moneda de la cuenta,
  no la preferida global). Si se omite, se devuelven todas las monedas. Desde Fase 29 acepta
  los mismos `year`/`month` que `summary`, combinables con `currency`.
- `GET /api/v1/dashboard/cashflow-series` — parámetro opcional `currency` (Fase 11 §11.1): filtra la serie a una sola moneda; si se omite, el backend usa `preferred_currency` del usuario. El frontend lo pasa explícito (Decisión 11.1.1 del spec de Fase 11). Desde la corrección UX
  post-Fase 19 acepta también `account_id: int`, mismo contrato que en `category-distribution`
  (ortogonal a `currency`, `404` si la cuenta es ajena).
- `GET /api/v1/dashboard/category-distribution` — mismo parámetro opcional `currency` que cashflow-series; soporta además `neto=true` para calcular gasto neto por categoría. Desde
  Fase 17 §17.1.3 acepta `account_id: int` (Decisión 17.1.3) para restringir el desglose a
  las transacciones de una sola cuenta — el frontend de `accounts/[id]` pasa `account_id` y
  `currency` **ambos explícitos** (son ortogonales: la moneda de una cuenta no tiene por qué
  coincidir con la preferida global). `404` si la cuenta no existe o no es del usuario.
  `/analytics` (corrección UX post-Fase 19) usa el mismo patrón para su selector de cuenta,
  pasando `account_id` + `currency=account.currency` a ambos endpoints (`cashflow-series` y
  `category-distribution`) — si solo se pasara `account_id` sin la moneda de esa cuenta, el
  backend cae a `preferred_currency` y una cuenta en otra moneda muestra $0 en todo.
  Desde Fase 24 §24.4 cada fila de la respuesta incluye `category_icon: string | null` — el
  ícono real de la categoría (misma fuente que `BudgetProgress.category_icon`), `null` si la
  categoría no tiene uno asignado (el caso común de las creadas por el usuario vía
  `POST /categories/`).

**Navegación por mes del dashboard (Fase 29):**

- `summary` y `budgets-progress` aceptan `year` y `month` **ambos o ninguno**. Sin ninguno, el
  backend responde por el **mes actual UTC** y los valores de los campos que ya existían son los
  de siempre (solo se agregan los nuevos), así que el dashboard de siempre no se rompe.
- El frontend **solo manda `year`/`month` en meses ya cerrados**. En el mes actual la petición
  va sin params (y el mes no se escribe en la URL): el backend valida "no se puede consultar un
  mes futuro" con **su** reloj, así que mandar el mes actual calculado con el reloj del
  navegador daría un `422` espurio en el cambio de mes.
- El período es **UTC** en el backend y en el front (`lib/dateRanges.ts` ancla los límites con
  `Date.UTC`): un mes va del día 1 a las 00:00 UTC al último día a las 23:59:59 UTC. En el mes
  en curso el techo es "ahora", de modo que una transacción con fecha futura del mismo mes no
  cuenta como gasto del mes en `summary` (sí contaría en un rango mal armado en hora local). Los
  rangos que arma el front para el mes/período en curso (`utcMonthRange`, `buildDateRange`)
  terminan en cambio al fin del día UTC de hoy: así incluyen lo capturado hoy con hora real y
  no cambian en cada render (van en query keys).
- Un `?month=` inválido o futuro no debe romper la vista: el front lo valida antes de pedirlo
  (`parseMonthParam`) y cae al mes actual. Si aun así llega un `422`, **hay dos formas** y no
  son intercambiables: `detail` como **string** — "Se deben enviar `year` y `month`, o
  ninguno.", "`month` debe ser un número entre 1 y 12.", "`year` debe ser un año entre 1 y
  9999.", "No se puede consultar un mes futuro." — y `detail` como **lista** de errores por
  campo, que es la validación de FastAPI (`?year=abc`).
- `first_transaction_month` es el límite inferior de la navegación; con `null` (usuario sin
  transacciones) no hay hacia dónde ir.
- Cambio de contrato del frontend (Fase 29): la query key
  `queryKeys.dashboard.recentTransactions` **ya no existe** (se eliminó la factory y sus tres
  invalidaciones). "Últimas 5 del mes" ahora sale de `GET /api/v1/transactions/` con
  `limit: 5` más `start_date`/`end_date` del mes pedido — mismo endpoint del feed, con lo que
  la lista sigue el mes elegido y hereda la invalidación por `transactions.all()` que ya
  cubría crear/editar/borrar (antes esa lista no se refrescaba al editar o borrar). El monto
  de cada fila se formatea con `tx.currency`, no con la moneda preferida global.
- `balances` no cambia con el mes y el dashboard ni lo consume (la vista de saldos vive en
  `/accounts` vía `GET /accounts/summary`): sigue siendo el saldo **actual** de las cuentas,
  idéntico al de cualquier mes consultado (ver "Contratos de datos > Dashboard").

### Notificaciones (Fase 13 §13.5)

Los avisos los escribe el motor de alertas del backend (transacciones de gasto que cruzan
el 80/100 % de un presupuesto); estos endpoints solo leen/escriben el estado de la bandeja.
Todos requieren `Bearer` y devuelven los timestamps en ISO 8601.

- `GET /api/v1/notifications/?skip=0&limit=50` — bandeja del usuario, más recientes primero,
  paginada con el mismo shape que transacciones. Los consumidores usan `limit=50` (la lista
  completa de la bandeja) — sin paginación "load more": el popover muestra las primeras 50.
  Devuelve `PaginatedResponse<AppNotification>`.
- `GET /api/v1/notifications/unread-count` — `{ "count": number }` para el badge de la
  campana. Es la única query con `refetchInterval` corto (60 s, Decisión 13.5.4): un
  `COUNT(*)` barato en el backend; el badge no dispara la query de lista completa.
- `PATCH /api/v1/notifications/{notification_id}/read` — marca como leída
  (`read_at = now()`). Idempotente. `404` si no existe o no es del usuario.
- `PATCH /api/v1/notifications/read-all` — marca todas las no leídas y devuelve
  `{ "count": 0 }` (idempotente).
- `DELETE /api/v1/notifications/read` (§13.7) — elimina las notificaciones ya leídas del
  usuario; las no leídas nunca se tocan. Consumido por el botón "Eliminar leídas" del
  popover, deshabilitado cuando no hay ninguna leída en la lista cargada.
- `DELETE /api/v1/notifications/{notification_id}` (§13.7) — elimina una notificación
  puntual. `404` si no existe o no es del usuario. Consumido por el ícono `X` de cada fila.

### Push web (Fase 13 §13.2)

Suscripción del navegador al canal de avisos. Los consumidores son
`PushOptIn.tsx` (alta) y el service worker (recepción).

- `GET /api/v1/push/vapid-public-key` — **público** (sin auth; el SW lo consulta antes de
  tener tokens). Devuelve `{ "public_key": string }` en base64url. `503` si el backend no
  tiene `VAPID_PUBLIC_KEY` configurado — el frontend lo trata como fallo silencioso del
  opt-in, no como error de la app.
- `POST /api/v1/push/subscribe` — auth. Body `{ endpoint: string, keys: { p256dh: string,
auth: string } }` — el shape exacto de `subscription.toJSON()`. Upsert por `endpoint`:
  repetir el mismo POST actualiza la fila en vez de duplicar. Devuelve la suscripción con
  `id`, `endpoint`, `created_at`.
- `DELETE /api/v1/push/subscribe` — auth. Body `{ endpoint: string }` (el frontend no
  guarda el `id` persistido; solo tiene el objeto del navegador). `404` si la suscripción
  no existe o no es del usuario. El frontend no lo consume todavía: el backend limpia las
  suscripciones caducadas solo al fallar el envío (404/410 Gone), sin acción del cliente.

### API keys (Fase 16 §16.1)

Claves personales revocables para automatizaciones que no pueden hacer el flujo OAuth2
password + refresh (Shortcuts de iOS/Android, scripts). Se autentican con el mismo header
`Authorization: Bearer <token>` usando el prefijo `oikos_pat_`. El frontend web no las usa
para autenticarse (sigue con JWT) — solo las gestiona desde `/settings`.

- `GET /api/v1/api-keys/` — lista las keys del usuario (incluidas las revocadas, con
  `revoked_at` seteado, para auditoría). Devuelve `ApiKeyResponse[]`: `id`, `name`,
  `key_prefix` (primeros 12 caracteres — no es secreto, solo distingue keys en la lista),
  `last_used_at` (`string | null`), `revoked_at` (`string | null`), `created_at`.
  **Nunca expone la key completa.**
- `POST /api/v1/api-keys/` — body `{ name }` (`string`, 1–100 chars). Devuelve
  `ApiKeyCreateResponse` con la key **en texto plano** (`key`) — aparece una sola vez en la
  respuesta; el frontend la muestra con un botón "Copiar" y advierte que no se volverá a
  mostrar (los `last_used_at`/`revoked_at` no viajan en esta respuesta). Puede devolver `429`
  (más de 5 intentos por minuto) o `400` (ya hay 20 keys activas, el máximo) — ambos casos ya
  caen en el `onError` genérico del formulario (`getApiError`), sin manejo especial (agregado
  en la revisión de seguridad post-16.1, ver `docs/TODO.md`).
- `DELETE /api/v1/api-keys/{api_key_id}` — revoca (marca `revoked_at`, no borra la fila).
  Efectiva en el siguiente request con esa key (401). `404` si no existe o ya fue revocada.
  El frontend pide confirmación (`ConfirmDialog` con etiqueta "Revocar") y no permite revocar
  dos veces (filas revocadas muestran tag "Revocada").

Reglas de consumo:

- La key en texto plano SOLO se recibe en la respuesta del POST — no persistirla; el usuario
  es quien decide dónde guardarla.
- Los timestamps llegan en ISO 8601; el frontend muestra `last_used_at` como tiempo relativo
  ("Nunca" si es `null`).
- Mutaciones (crear/revocar) invalidan la query `['apiKeys']`.

## Contratos de datos importantes

### Usuario autenticado

`GET /api/v1/users/me` devuelve al menos:

- `id`
- `email`
- `full_name`
- `preferred_currency` (default `"COP"`)
- `preferred_locale` (default `"es-CO"`)
- `preferred_theme` (default `"dark"`)
- `monthly_income` (`number | null`) — dato financiero del perfil, editable vía `PATCH /api/v1/users/me`. El dashboard lo consume dos veces (Fase 11 §11.3): indirectamente a través de `monthly_flow_balance` en `/dashboard/summary`, y directamente vía el formulario inline de la card "Balance del mes" cuando ese valor es `null`.
- `has_transaction_history` (`boolean`, Fase 19 §19.1) — `true` si el usuario tiene 2+ transacciones. El login (`login/page.tsx`) lo lee para condicionar el redirect: `/dashboard` si es `true`, `/capture` si no (resuelve la Decisión 10.1.4 de Fase 10). Solo se calcula en `GET /users/me`; en `PATCH /me` llega como `false` fijo sin consultar — ningún call site de ese endpoint lee el campo (Decisión 19.1.3).
- `has_password` (`boolean`, Fase 22 §22.4, Decisión D4) — `true` si la cuenta tiene contraseña, `false` = cuenta creada solo con Google. Se computa en los tres endpoints de `UserResponse` via `model_validator` del schema (no hay que asignarlo por handler). El modal de "Eliminar mi cuenta" en `/settings` lo usa para no pedir contraseña a una cuenta Google-only (`requiresPassword = currentUser?.has_password !== false`).

### Preferencias de usuario

`GET /api/v1/users/me/preferences` devuelve:

- `preferred_currency`: string
- `preferred_locale`: string
- `preferred_theme`: string
- `weekly_summary_enabled`: boolean (Fase 14 §14.6.1; opt-out, default `true`)

`PATCH /api/v1/users/me/preferences` acepta campos opcionales: `preferred_currency`, `preferred_locale`, `preferred_theme`, `weekly_summary_enabled`.

Además acepta `apply_to_default_account?: boolean` (Fase 22 §22.1, Decisión A5) — instrucción
por-request, no se persiste: cuando es `true` junto con `preferred_currency`, el backend
cascadea la moneda a la cuenta por defecto (si sigue virgen: nombre `"Cuenta principal"`,
balance 0, sin transacciones) en la misma transacción. Solo lo envía el paso de moneda del
onboarding (`OnboardingCurrencyStep.tsx`); el selector de Settings **no** lo manda y por eso
el `useUserPreferences` invalida `accounts.all()` solo cuando viene `apply_to_default_account`
(la cuenta pudo haber cambiado de moneda server-side).

El frontend escribe estas preferencias desde tres lugares: `ThemeToggle.tsx` (tema, con
aplicación inmediata en cliente + persistencia), la página de Ajustes
(`/settings`, Fase 14 §14.6.2 — resumen semanal + moneda principal Fase 21) y el paso de
moneda del onboarding (`OnboardingCurrencyStep.tsx`, Fase 22). Todos pasan por la
mutación compartida de `useUserPreferences` (`updatePreferences`), que invalida la query
`userPreferences` tras el `PATCH`.

### Cuenta

El frontend asume:

- `id`
- `name`
- `type`
- `balance`
- `currency`
- `user_id`
- `opening_balance` (Fase 16 §16.4) — saldo de apertura, inmutable tras la creación de la
  cuenta. En los tipos generados es `string` (serialización `Decimal`); el tipo manual
  `Account` en `types/api.ts` lo tipa como `number`.

Reglas:

- `balance` se muestra, pero no debe recalcularse en cliente.
- En edición no se envía `balance`.
- `currency` se hereda al crear transacciones asociadas.

### Categoría

El frontend asume:

- `id`
- `name`
- `type`
- `user_id`
- `icon` (`string | undefined`)
- `is_hidden` (`boolean`, Fase 18 §18.3) — computado por usuario en el backend; cada
  categoría de `GET /api/v1/categories/` (y de los handlers puntuales) la trae explícita.
  Solo filtra el selector de captura (`TransactionCaptureForm`); el filtro y la edición de
  `/transactions`, el selector de `/budgets` y la resolución por nombre (Fase 16 §16.2)
  siguen viendo todas las categorías.

Reglas:

- `user_id = null` significa categoría compartida del sistema.
- Las categorías base no se editan ni eliminan desde el frontend.
- El detalle de categoría debe funcionar tanto para categorías base como personalizadas.
- Ocultar/mostrar no es editar los campos de la categoría: el toggle (`POST`/`DELETE
/categories/{id}/hide`) está disponible para categorías de sistema y propias por igual.

### Transacción

El frontend asume:

- `id`
- `description`
- `amount`
- `type`
- `currency`
- `date`
- `account_id`
- `category_id`
- `payment_method` (opcional: `"cash" | "card" | "transfer" | null`)

Reglas:

- `currency` se hereda de la cuenta al crear; no se envía en el payload.
- En edición, si no se reenvía `payment_method`, el backend conserva el valor actual.
- El feed principal debe ordenarse por fecha descendente desde el backend.
- Los detalles por cuenta y categoría reutilizan el mismo contrato.
- Al crear, editar o borrar una transacción, se deben invalidar las queries relacionadas.
- El feed usa paginación tipo "load more" con `skip`/`limit=50`; el frontend acumula páginas hasta que `total` coincida.
- La respuesta se tipa como `PaginatedResponse<Transaction>` en `types/api.ts`.

### Presupuesto

El frontend asume:

- `id`
- `category_id`
- `amount_limit`
- `currency`
- `month`
- `year`
- `is_recurring`

Reglas:

- Con `is_recurring: true`, el backend genera automáticamente la fila del siguiente período la primera vez que ese período se consulta; desde Fase 29 el frontend solo llega a ese caso por `GET /api/v1/dashboard/budgets-progress` **con el mes actual** (sin params): un mes pasado devuelve los presupuestos que existían, sin crear filas nuevas a partir de la plantilla, así que la lista vacía de un mes sin presupuestos es real y se puede explicar en pantalla. `GET /api/v1/budgets/?month=&year=` sigue generando para cualquier período, incluidos los ya cerrados, pero el frontend **no** lo llama con período (y sin filtros devuelve el historial completo sin generar nada).
- Editar el monto de una fila recurrente lo convierte en la plantilla de los meses futuros.

En el dashboard, el progreso de presupuesto llega ya calculado desde el backend, para el período consultado.

### Dashboard

El frontend asume:

- `balances` (`BalanceByCurrency[]`) — saldos por moneda de las cuentas **destacadas** (o todas si no hay destacadas). Desde Fase 11 §11.3 el dashboard ya no renderiza este array como card "Balance Total": esa vista vive en `/accounts` vía `GET /accounts/summary`, que no filtra por destacadas. **No depende del mes consultado** (Fase 29): sigue siendo el saldo actual de las cuentas, no un saldo histórico del mes que se está mirando.
- `monthly_income_by_currency` / `monthly_expense_by_currency` (`BalanceByCurrency[]`) — del mes consultado, también solo sobre cuentas destacadas.
- `monthly_flow_balance` (`number | null`, Fase 11 §11.3; Fase 29) — en la moneda preferida, calculado por el backend. **Su significado lo dice `monthly_flow_basis`**, no el frontend:
  - `"declared"` (mes en curso) — ingreso mensual declarado por el usuario menos el gasto del mes; `null` significa que el usuario no fijó `monthly_income` todavía (el frontend lo distingue del estado de carga y muestra un formulario inline).
  - `"actual"` (mes ya cerrado) — ingresos reales registrados menos gastos reales del mes; **nunca `null`** (sin filas, `0.00`).
    Limitación conocida, aceptada a propósito en ambos casos: el gasto en monedas distintas a la preferida no resta (misma limitación de una-sola-moneda que cashflow-series/category-distribution).
- `monthly_flow_basis` (`'declared' | 'actual'`, Fase 29) — el rótulo de la tarjeta sale de acá ("Te quedan…" vs. "Balance de <mes>"), no de comparar fechas locales con el mes actual: el mes es UTC y el reloj del navegador puede no coincidir con el del servidor.
- `first_transaction_month` (`string | null`, Fase 29) — mes UTC `"YYYY-MM"` de la transacción más antigua del usuario, sobre todas las cuentas. Es el límite inferior del `◀`; `null` = usuario sin transacciones, la navegación no tiene hacia dónde ir.
- `expense_currencies` (`string[]`, Fase 29) — monedas con gasto en el mes consultado, sobre **todas** las cuentas (no solo las destacadas), con la preferida primero. Alimenta los chips de moneda de "Gastos por categoría": las barras que el chip filtra cuentan todas las cuentas, así que el universo tiene que ser ese. La moneda preferida solo aparece si tiene gasto en el mes, y el frontend la suma igual a las opciones para que el chip nunca quede sin nada que mostrar.

Para el progreso de presupuestos, el backend devuelve valores listos para pintar:

- `category_id`
- `category_name`
- `amount_limit`
- `spent`
- `percentage`
- `currency` (Fase 11 §11.1) — moneda real del presupuesto; `spent` y `amount_limit` viven en esta moneda. `BudgetRing` la usa para formatear en vez de la moneda preferida global.

`spent` es el gasto del **período consultado** (Fase 29), no siempre el del mes actual, y suma transacciones de **todas** las cuentas del usuario en esa moneda (no solo las destacadas) — mismo criterio que el motor de alertas del backend, que no puede divergir del que muestra la vista.

Los endpoints de series (`cashflow-series`, `category-distribution`) devuelven una sola serie filtrada a una moneda (`currency` explícito o `preferred_currency` por defecto) — nunca suman monedas distintas en un mismo punto.

### Notificación

`GET /api/v1/notifications/` devuelve `PaginatedResponse<AppNotification>`; cada ítem:

- `id` — int
- `type` — string (`budget_threshold_80` | `budget_threshold_100` | `weekly_summary` desde Fase 14)
- `title` — string (título del aviso, listo para pintar)
- `body` — string (cuerpo, listo para pintar)
- `budget_id` — `number | null`; si no es `null`, el frontend enlaza el título a `/budgets`
- `period_key` — `string | null` (Fase 14: semana ISO, p. ej. `"2026-W37"`, que originó un
  `weekly_summary`; `null` para las alertas de presupuesto de Fase 13)
- `read_at` — `string | null` (ISO 8601; `null` = no leída)
- `created_at` — string (ISO 8601, usada para el tiempo relativo del popover)

El popover diferencia el ícono de cada fila según `type` (Decisión 14.5.1): calendario
para `weekly_summary`, alerta para `budget_threshold_*`. Las notificaciones con
`budget_id != null` enlazan a `/budgets`; las de `weekly_summary` no enlazan.

Reglas:

- La lista nunca se deriva ni se agrega en cliente: el backend escribe y entrega los avisos.
- "Marcar como leída" no se optimiza localmente: se hace `PATCH` y la invalidación recarga
  lista + badge (el `unread_count` se recalcula del server, nunca restando en el cliente).

## Errores esperados

- `400`: validación de negocio fallida o dato inválido. Ej: cuenta con transacciones, budget duplicado, categoría protegida.
- `401`: token ausente o inválido.
- `403`: acción no permitida (ej: editar/eliminar categoría base del sistema).
- `404`: recurso inexistente o fuera de alcance del usuario.
- `422`: validación de entrada — de esquema (`?year=abc` en `dashboard/summary` o `dashboard/budgets-progress`, con `detail` como **lista**) o de período del dashboard (con `detail` como **string**); ver "Navegación por mes del dashboard" para los mensajes.
- `429`: rate limiting excedido (`/api/v1/auth/login`, `POST /api/v1/users/`, `/api/v1/auth/password-reset/request`, `/api/v1/auth/resend-verification`, `/api/v1/auth/google`, todos 5 req/min).

## Reglas de consumo

- No enviar `user_id` desde el frontend.
- No enviar `balance` en edición de cuentas.
- No calcular balances ni agregados financieros en el cliente.
- No asumir que una categoría es editable si `user_id` es `null`.
- Usar `queryKey` explícitas y invalidación después de mutaciones.

## Relación con la documentación del backend

La documentación canónica del contrato vive en el backend. Este archivo existe para explicar cómo consumirlo desde la app Next.js sin duplicar lógica de negocio.
