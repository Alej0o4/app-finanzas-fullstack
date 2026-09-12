# Contrato de API del Frontend

## Propósito

Este documento define cómo el frontend consume el backend de Oikos y qué supuestos puede hacer sobre los datos recibidos.

La regla base es simple: el frontend no recalcula saldos, progreso de presupuestos ni agregados financieros. El backend es la fuente de verdad.

## Base URL y autenticación

- Base URL: `NEXT_PUBLIC_API_URL`
- Fallback local: `http://localhost:8000`
- Prefijo de versión: `/api/v1` — está centralizado en el `baseURL` del cliente Axios en `lib/api.ts` (`` `${NEXT_PUBLIC_API_URL}/api/v1` ``), no repetido en cada call site. Los ~45 call sites de la app llaman a rutas relativas sin prefijo (ej. `api.get('accounts/')`); las rutas documentadas abajo omiten `/api/v1` por brevedad pero es lo que efectivamente se resuelve en runtime.
- Autenticación: `Authorization: Bearer <token>`
- El token se lee desde `localStorage` en `lib/api.ts`
- El refresh token se almacena en `localStorage` como `refresh_token`

Si el backend responde `401`, el frontend intenta renovar el token via `POST /api/v1/auth/refresh` con el `refresh_token`. Si la renovación falla, limpia el token y redirige a `/login`.

El access token expira en 15 min (bajado de 60 min en Fase 7, §2.5 de `docs/specs/fase_07_spec.md`) — el interceptor de refresh de `lib/api.ts` se dispara ~4 veces más seguido que antes. El código actual ya tiene protección contra refreshes concurrentes (flag `isRefreshing` + cola `failedQueue`), verificado como parte de Fase 7.

El backend expone además `POST /api/v1/auth/password-reset/request`, `POST /api/v1/auth/password-reset/confirm` y `GET /api/v1/auth/verify-email` (Fase 7, §2.1/§2.2) — **el frontend todavía no tiene pantallas que los consuman**, quedan documentados en `backend/docs/API_REFERENCE.md` para cuando se construya esa UI.

## Endpoints consumidos por el frontend

### Autenticación

- `POST /api/v1/auth/login` → devuelve `access_token` + `refresh_token`
- `POST /api/v1/auth/refresh` → rota refresh token, devuelve nuevo JWT
- `POST /api/v1/auth/logout` → revoca refresh token
- `GET /api/v1/users/me`
- `PATCH /api/v1/users/me` (acepta `{ monthly_income }` — usado por la card "Balance del mes" del dashboard para fijar el ingreso mensual inline, Fase 11 §11.3)
- `GET /api/v1/users/me/preferences`
- `PATCH /api/v1/users/me/preferences`

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
- `PUT /api/v1/accounts/{account_id}`
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

- `GET /api/v1/dashboard/summary` — incluye `monthly_flow_balance: number | null` desde Fase 11 §11.3 (ver "Contratos de datos" abajo)
- `GET /api/v1/dashboard/budgets-progress` — cada fila incluye `currency` desde Fase 11 §11.1.
  Desde Fase 17 §17.2.3 acepta además un query param opcional `currency: string` (Decisión
  17.2.3): si se pasa, el backend filtra las filas a esa moneda **sin recalcular `spent`**
  (el gasto de cada presupuesto es la suma cruzada de todas las cuentas del usuario en esa
  moneda — filtrar cambia qué filas se muestran, nunca cuánto gastó cada una). El frontend
  lo usa en `accounts/[id]` (las queries propias por cuenta pasan la moneda de la cuenta,
  no la preferida global). Si se omite, se devuelven todas las monedas.
- `GET /api/v1/dashboard/cashflow-series` — parámetro opcional `currency` (Fase 11 §11.1): filtra la serie a una sola moneda; si se omite, el backend usa `preferred_currency` del usuario. El frontend lo pasa explícito (Decisión 11.1.1 del spec de Fase 11)
- `GET /api/v1/dashboard/category-distribution` — mismo parámetro opcional `currency` que cashflow-series; soporta además `neto=true` para calcular gasto neto por categoría. Desde
  Fase 17 §17.1.3 acepta `account_id: int` (Decisión 17.1.3) para restringir el desglose a
  las transacciones de una sola cuenta — el frontend de `accounts/[id]` pasa `account_id` y
  `currency` **ambos explícitos** (son ortogonales: la moneda de una cuenta no tiene por qué
  coincidir con la preferida global). `404` si la cuenta no existe o no es del usuario.

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

### Preferencias de usuario

`GET /api/v1/users/me/preferences` devuelve:

- `preferred_currency`: string
- `preferred_locale`: string
- `preferred_theme`: string
- `weekly_summary_enabled`: boolean (Fase 14 §14.6.1; opt-out, default `true`)

`PATCH /api/v1/users/me/preferences` acepta campos opcionales: `preferred_currency`, `preferred_locale`, `preferred_theme`, `weekly_summary_enabled`.

El frontend escribe estas preferencias desde dos lugares: `ThemeToggle.tsx` (tema, con
aplicación inmediata en cliente + persistencia) y la página de Ajustes
(`/settings`, Fase 14 §14.6.2 — único control: el resumen semanal). Ambos pasan por la
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

Reglas:

- `user_id = null` significa categoría compartida del sistema.
- Las categorías base no se editan ni eliminan desde el frontend.
- El detalle de categoría debe funcionar tanto para categorías base como personalizadas.

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

- Con `is_recurring: true`, el backend genera automáticamente la fila del siguiente período la primera vez que ese período se consulta (`GET /api/v1/dashboard/budgets-progress` o `GET /api/v1/budgets/?month=&year=`); la llamada sin filtros devuelve el historial completo sin generar nada.
- Editar el monto de una fila recurrente lo convierte en la plantilla de los meses futuros.

En el dashboard, el progreso de presupuesto llega ya calculado desde el backend.

### Dashboard

El frontend asume:

- `balances` (`BalanceByCurrency[]`) — saldos por moneda de las cuentas **destacadas** (o todas si no hay destacadas). Desde Fase 11 §11.3 el dashboard ya no renderiza este array como card "Balance Total": esa vista vive en `/accounts` vía `GET /accounts/summary`, que no filtra por destacadas.
- `monthly_income_by_currency` / `monthly_expense_by_currency` (`BalanceByCurrency[]`)
- `monthly_flow_balance` (`number | null`, Fase 11 §11.3) — ingreso mensual declarado por el usuario menos el gasto del mes **en su moneda preferida**, calculado por el backend. `null` significa que el usuario no fijó `monthly_income` todavía (el frontend lo distingue del estado de carga y muestra un formulario inline). Limitación conocida, aceptada a propósito: el gasto en monedas distintas a la preferida no resta (misma limitación de una-sola-moneda que cashflow-series/category-distribution).

Para el progreso de presupuestos, el backend devuelve valores listos para pintar:

- `category_id`
- `category_name`
- `amount_limit`
- `spent`
- `percentage`
- `currency` (Fase 11 §11.1) — moneda real del presupuesto; `spent` y `amount_limit` viven en esta moneda. `BudgetRing` la usa para formatear en vez de la moneda preferida global.

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
- `429`: rate limiting excedido (`/api/v1/auth/login`, `POST /api/v1/users/`, `/api/v1/auth/password-reset/request`, todos 5 req/min).

## Reglas de consumo

- No enviar `user_id` desde el frontend.
- No enviar `balance` en edición de cuentas.
- No calcular balances ni agregados financieros en el cliente.
- No asumir que una categoría es editable si `user_id` es `null`.
- Usar `queryKey` explícitas y invalidación después de mutaciones.

## Relación con la documentación del backend

La documentación canónica del contrato vive en el backend. Este archivo existe para explicar cómo consumirlo desde la app Next.js sin duplicar lógica de negocio.
