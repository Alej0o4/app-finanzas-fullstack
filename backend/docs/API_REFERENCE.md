# Referencia de API

## Convenciones generales

- Base path: `/api/v1`
- Autenticación: `Authorization: Bearer <token>` en rutas protegidas. Además del JWT del
  flujo OAuth2, se aceptan **API keys personales** con prefijo `oikos_pat_` en el mismo
  header (Fase 16 §16.1) — ver sección "API keys" abajo.
- Content type esperado: `application/json`, excepto login, que usa formulario OAuth2.
- Rate limiting: `/api/v1/auth/login`, `POST /api/v1/users/`, `/api/v1/auth/password-reset/request`
  y `POST /api/v1/api-keys/` (5 req/min por IP via `slowapi`), y `POST /api/v1/transactions/`
  (60 req/min — keyed por usuario cuando la autenticación es con API key, resuelto contra la
  DB para que todas las keys de un mismo usuario compartan un balde; por IP en el resto,
  Fase 16 §16.1, corregido en la revisión de seguridad post-16.1 — ver `docs/TODO.md`).
- CORS: orígenes permitidos vía `ALLOWED_ORIGINS` (env) + regex para IPs de Tailscale (100.x.x.x).
- Uvicorn escucha en `0.0.0.0` para soportar acceso remoto via Tailscale.
- Borrado lógico (Fase 8): los endpoints `DELETE` de cuentas/categorías/transacciones/presupuestos marcan
  `deleted_at` en lugar de borrar la fila. Los recursos "eliminados" dejan de aparecer en cualquier `GET`
  y no pueden verse ni editarse — el mecanismo es invisible para el cliente.

## Autenticación

### `POST /api/v1/auth/login`

Inicia sesión y devuelve un JWT + refresh token.

Entrada (form-urlencoded):

- `username`: email del usuario.
- `password`: contraseña en texto plano.

Salida:

- `access_token`: JWT firmado (expira en 15 min — bajado de 60 min en Fase 7, ver
  `docs/specs/fase_07_spec.md` §2.5; se apoya en el refresh token para sesiones largas).
- `refresh_token`: token opaco para renovar sesión (expira en 30 días).
- `token_type`: `bearer`.

Errores esperados:

- `403` si las credenciales son inválidas.
- `429` si se exceden 5 intentos por minuto (rate limiting).

### `POST /api/v1/auth/refresh`

Rota el refresh token y devuelve un nuevo JWT.

Entrada:

- `refresh_token`: el refresh token actual.

Salida:

- `access_token`: nuevo JWT firmado.
- `refresh_token`: nuevo refresh token (el anterior queda invalidado).

Errores esperados:

- `401` si el refresh token es inválido o expiró.

### `POST /api/v1/auth/logout`

Revoca el refresh token, cerrando la sesión.

Entrada:

- `refresh_token`: el refresh token a revocar.

Salida:

- `{"estado": "OK", "mensaje": "Sesion cerrada exitosamente."}`

### `POST /api/v1/auth/password-reset/request`

Solicita un token de restablecimiento de contraseña (Fase 7, §2.1). Genera el token y lo
envía por email si el correo existe — **siempre responde 200**, exista o no el correo, para
no revelar qué emails están registrados. Rate limited (5 req/min por IP).

Entrada:

- `email`

Salida:

- `{"estado": "OK", "mensaje": "Si el correo está registrado, recibirás instrucciones para restablecer tu contraseña."}`

### `POST /api/v1/auth/password-reset/confirm`

Aplica una nueva contraseña usando el token recibido por email. El token expira a los 45
min y es de un solo uso. Al confirmar, revoca todos los refresh tokens activos del usuario
(cierra cualquier sesión vieja).

Entrada:

- `token`
- `new_password` (misma política que en el registro, ver abajo)

Salida:

- `{"estado": "OK", "mensaje": "Contraseña actualizada exitosamente. Iniciá sesión nuevamente."}`

Errores esperados:

- `400` si el token es inválido, ya fue usado o expiró.
- `422` si `new_password` no cumple la política de contraseñas.

### `GET /api/v1/auth/verify-email`

Verifica el email del usuario a partir del token enviado en el registro (Fase 7, §2.2). El
token expira a las 48h y es de un solo uso. **No verificar el email no bloquea el login** —
es una decisión de producto para no agregar fricción al onboarding.

Query params:

- `token`

Salida:

- `{"estado": "OK", "mensaje": "Correo verificado exitosamente."}`

Errores esperados:

- `400` si el token es inválido, ya fue usado o expiró.

## API keys (Fase 16 §16.1)

API keys personales revocables que habilitan clientes que no pueden hacer el flujo OAuth2
password + refresh (shortcuts de iOS/Android; en el futuro, la nota de voz con IA). Se envían
en el mismo header `Authorization: Bearer <key>` que el JWT, pero con prefijo
`oikos_pat_` (el backend las distingue del JWT por ese prefijo antes de intentar decodificar).

Características:

- **Sin scopes en v1**: una API key tiene exactamente los mismos permisos que el JWT del
  mismo usuario — la autorización real vive en cada router, filtrada por `user_id`.
- **Revocación inmediata**: `revoked_at` se valida en cada request; la siguiente petición con
  una key revocada falla con `401` (a diferencia del JWT, que vive hasta 15 min sin blacklist).
- **Sin expiración obligatoria en v1** (mismo criterio que un PAT de GitHub) — decisión de
  producto revisada y mantenida explícitamente en la revisión de seguridad de la Decisión
  16.1.8 (ver `docs/TODO.md`), no un olvido.
- **Máximo 20 API keys activas por usuario** y `POST /api/v1/api-keys/` limitado a 5 req/min
  por IP (mismo patrón que login/registro/reset) — agregado en la revisión de seguridad
  post-16.1 para que un JWT de corta vida robado no alcance para mintear un número
  arbitrario de credenciales de larga vida.
- **Un reset de contraseña revoca también todas las API keys activas del usuario**, igual que
  ya hacía con los refresh tokens — agregado en la misma revisión (antes una key sobrevivía
  sin cambios a la acción que el usuario toma para recuperar el control de su cuenta).
- La key en texto plano **solo** se devuelve en la respuesta del `POST` — nunca se puede
  volver a consultar.

### `POST /api/v1/api-keys/`

Crea una API key nueva para el usuario autenticado.

Entrada:

- `name`: etiqueta elegida por el usuario (1–100 chars), p. ej. `"Shortcut iPhone"`.

Salida (`ApiKeyCreateResponse`):

- `id`
- `name`
- `key`: **la key en texto plano — SOLO aparece en esta respuesta.** Prefijo `oikos_pat_`
  + 43 caracteres urlsafe.
- `key_prefix`: primeros 12 caracteres de la key (no es secreto — solo discrimina keys en
  la lista).
- `created_at`

Errores esperados:

- `400` si el usuario ya tiene 20 API keys activas (revocá alguna antes de crear otra).
- `429` si se exceden 5 intentos por minuto (rate limiting).

### `GET /api/v1/api-keys/`

Lista las API keys del usuario autenticado (incluidas las revocadas, para auditar "¿se usó
recientemente una key comprometida?").

Salida: array de `ApiKeyResponse`:

- `id`
- `name`
- `key_prefix`
- `last_used_at` (`null` si nunca se usó)
- `revoked_at` (`null` si sigue activa)
- `created_at`

**Nunca** expone `key` ni `key_hash`.

### `DELETE /api/v1/api-keys/{api_key_id}`

Revoca una API key (marca `revoked_at`, no borra la fila — conserva `last_used_at` para
auditoría).

Errores esperados:

- `404` si la key no existe, no pertenece al usuario o ya fue revocada.

## Usuarios

### `POST /api/v1/users/`

Crea un usuario nuevo y su cuenta por defecto "Cuenta principal" (tipo `debit`, saldo 0,
destacada, en la moneda preferida — Fase 8 §5, renombrada de "Efectivo"/`cash` en un ajuste
posterior a Fase 15). Tras crearlo, envía un email de verificación (ver
`GET /api/v1/auth/verify-email` arriba) — no bloquea la respuesta del registro si falla el
envío. Rate limited (5 req/min por IP).

Entrada:

- `full_name`
- `email`
- `password` — política de contraseñas (Fase 7, §2.3): mínimo 10 caracteres, máximo 128, no
  puede ser solo dígitos ni solo letras, y no puede estar en una lista corta de contraseñas
  comunes. La misma política aplica a `new_password` en `password-reset/confirm`.

Salida:

- `id`
- `full_name`
- `email`
- `preferred_currency` (default: `"COP"`)
- `preferred_locale` (default: `"es-CO"`)
- `preferred_theme` (default: `"dark"`)
- `monthly_income` (`null` hasta que se defina vía `PATCH /api/v1/users/me`)

Errores esperados:

- `400` si el correo ya existe.
- `422` si `password` no cumple la política de contraseñas.
- `429` si se exceden 5 intentos por minuto (rate limiting).

### `GET /api/v1/users/me`

Devuelve el usuario autenticado actual.

Salida:

- `id`
- `full_name`
- `email`
- `preferred_currency`
- `preferred_locale`
- `preferred_theme`
- `monthly_income`

### `PATCH /api/v1/users/me`

Actualiza el perfil financiero del usuario autenticado. Separado de
`PATCH /me/preferences` a propósito: `monthly_income` es un dato financiero de dominio,
no una preferencia cosmética (Fase 8 §1, Decisión 1.1).

Entrada (campos opcionales):

- `monthly_income`: número ≥ 0 con hasta 2 decimales.

Limitación conocida: el endpoint ignora campos `null` (`exclude_none`), así que un
`monthly_income` ya definido no se puede volver `null` desde la API.

Salida: `UserResponse` actualizada (mismo shape que `GET /me`).

### `GET /api/v1/users/me/preferences`

Devuelve las preferencias del usuario autenticado.

Salida:

- `preferred_currency`: string (default `"COP"`)
- `preferred_locale`: string (default `"es-CO"`)
- `preferred_theme`: string (default `"dark"`)
- `weekly_summary_enabled`: bool (default `true`, Fase 14) — si el usuario recibe el
  resumen semanal automático

### `PATCH /api/v1/users/me/preferences`

Actualiza preferencias del usuario autenticado.

Entrada (campos opcionales):

- `preferred_currency`: string
- `preferred_locale`: string
- `preferred_theme`: string
- `weekly_summary_enabled`: bool (Fase 14)

## Cuentas

### `POST /api/v1/accounts/`

Crea una cuenta para el usuario autenticado.

Entrada:

- `name`
- `type`: `cash | debit | credit`
- `balance`: saldo inicial permitido solo en creación (Fase 16 §16.4: alimenta las dos
  columnas `balance` y `opening_balance` al mismo valor — `opening_balance` queda inmutable).
- `currency`: código de moneda (default `"COP"`). Ej: `"COP"`, `"USD"`, `"EUR"`.
- `highlighted`: si la cuenta es destacada (default `false`).

Salida:

- `id`
- `name`
- `type`
- `balance` — saldo actual (mutado por las operaciones de transacciones)
- `opening_balance` — saldo de apertura, inmutable tras la creación (Fase 16 §16.4)
- `currency`
- `highlighted`
- `user_id`

### `GET /api/v1/accounts/summary`

Saldo total por moneda de TODAS las cuentas del usuario, agrupado por moneda. A diferencia
de `GET /api/v1/dashboard/summary`, **no** filtra por cuentas destacadas — el total coincide
con la suma de todas las tarjetas listadas en la vista de cuentas (Fase 11 §11.5).

Salida: array de `{currency, total}`.

### `GET /api/v1/accounts/{account_id}`

Devuelve una cuenta del usuario autenticado.

### `GET /api/v1/accounts/`

Lista las cuentas del usuario autenticado.

### `PUT /api/v1/accounts/{account_id}`

Actualiza nombre, tipo y destacada de la cuenta. Nunca modifica `balance` ni `opening_balance`
(regla de negocio: el saldo solo lo mueven las transacciones).

### `PATCH /api/v1/accounts/{account_id}/highlighted`

Alterna el estado `highlighted` de una cuenta (toggle).

Salida: `AccountResponse` actualizada.

### `POST /api/v1/accounts/{account_id}/reconcile` (Fase 16 §16.4)

Recalcula el saldo de la cuenta desde `opening_balance` + el historial de transacciones NO
eliminadas (`SUM(ingresos) - SUM(gastos)`) y aplica la corrección de inmediato, sin paso de
confirmación previo. Útil para detectar/corregir cuentas desviadas por un bug o una
intervención manual que haya mutado `balance` fuera de los endpoints de transacciones.

Salida (`AccountReconcileResponse`):

- `account_id`
- `previous_balance`: saldo que tenía antes del recálculo.
- `recalculated_balance`: valor corregido.
- `discrepancy`: `recalculated_balance - previous_balance` — `0.00` si no había desviación.
- `opening_balance`

Errores esperados:

- `404` si la cuenta no existe o no pertenece al usuario autenticado.

### `DELETE /api/v1/accounts/{account_id}`

Elimina la cuenta si no tiene transacciones asociadas.

Errores esperados:

- `400` si la cuenta tiene transacciones asociadas.

## Categorías

### `POST /api/v1/categories/`

Crea una categoría personalizada.

Entrada:

- `name`
- `type`: `income | expense`

### `GET /api/v1/categories/`

Lista categorías base del sistema y categorías propias del usuario.

### `PUT /api/v1/categories/{category_id}`

Actualiza una categoría personalizada.

### `DELETE /api/v1/categories/{category_id}`

Elimina una categoría personalizada solo si no tiene transacciones ni presupuestos asociados.

## Transacciones

### `POST /api/v1/transactions/`

Registra un ingreso o gasto y actualiza el saldo de la cuenta asociada. Rate limit:
60 req/min (Fase 16 §16.1).

Entrada:

- `amount`: mayor a cero.
- `type`: `income | expense`
- `description`: opcional.
- `date`: fecha de la transación (formato ISO, default: ahora).
- `account_id` **opcional** (Fase 16 §16.2): si se omite, se usa la única cuenta del usuario.
  Con más de una cuenta y sin `account_id` → `400` (no se adivina cuál).
- `category_id` **o** `category`: exactamente uno de los dos (Fase 16 §16.2).
  - `category_id`: el ID de la categoría (comportamiento histórico).
  - `category`: nombre de la categoría, resuelto por el backend. Match case y
    acento-insensible, filtrado por `type` (una categoría de gasto y una de ingreso con el
    mismo nombre no se pisan). Precedencia: categoría propia del usuario > categoría de
    sistema. `409` si hay más de una categoría propia con el mismo nombre+tipo; `404` si no
    matchea ninguna (la respuesta lista las categorías válidas del tipo).
- `payment_method` (opcional): tag de método de pago — `cash | card | transfer`. Es un dato
  de la transacción, independiente del `type` de la cuenta asociada (Fase 8 §2).

Header opcional:

- `Idempotency-Key` (opcional, máximo 255 caracteres): hace el POST idempotente para
  reintentos seguros (Fase 10 §10.4). Si la clave ya fue usada antes por el mismo usuario:
  - con un payload idéntico → se devuelve la transacción original sin crear otra ni volver
    a mover el saldo (replay);
  - con un payload distinto → `409 Conflict` ("Esta Idempotency-Key ya se usó con datos
    distintos"); si la transacción original fue eliminada, también `409`.
  El cliente debe generar una clave nueva por captura lógica (p. ej. `crypto.randomUUID()`)
  y reusarla solo en reintentos del mismo envío. Este header **solo aplica a este endpoint**;
  `GET`/`PUT`/`DELETE` lo ignoran.

Nota: `currency` se hereda automáticamente de la cuenta asociada.

### `GET /api/v1/transactions/`

Lista transacciones del usuario autenticado con paginación.

Filtros opcionales:

- `skip` (default: 0)
- `limit` (default: 100, usado internamente: 50)
- `account_id`
- `category_id`
- `start_date`
- `end_date`

Salida paginada:

- `items`: `Transaction[]` — transacciones de la página solicitada
- `total`: `int` — total de transacciones que coinciden con los filtros
- `page`: `int` — página actual (calculada como `skip/limit + 1`)
- `page_size`: `int` — número de items por página (`limit`)

### `PUT /api/v1/transactions/{transaction_id}`

Actualiza una transacción y recalcula saldos de forma inversa y luego aplicada. Si
`payment_method` no se reenvía, conserva su valor actual.

### `DELETE /api/v1/transactions/{transaction_id}`

Elimina (lógicamente) una transacción y revierte el impacto sobre el saldo de la cuenta.

## Presupuestos

### `POST /api/v1/budgets/`

Crea un presupuesto por categoría, mes y año.

Entrada:

- `amount_limit`: mayor a cero.
- `currency`: código de moneda (default `"COP"`).
- `month`: entre 1 y 12.
- `year`
- `category_id`
- `is_recurring` (opcional, default `false`): si es `true`, la fila actúa como plantilla —
  el presupuesto se genera automáticamente para los períodos futuros que se consulten
  (Fase 8 §3). Editar el monto del presupuesto de un mes también actualiza el monto de los
  meses futuros, porque la plantilla siempre es la fila recurrente más reciente. Para
  "apagar" la recurrencia se edita con `is_recurring: false`; borrar la fila no corta la
  generación de los meses siguientes.

Errores esperados:

- `400` si ya existe un presupuesto (activo) para la misma categoría, mes y año.

### `GET /api/v1/budgets/`

Lista presupuestos del usuario autenticado, con filtros opcionales por mes y año.

Filtros opcionales:

- `month`
- `year`

Cuando se pasan `month` y `year`, antes de listar se generan las filas recurrentes
pendientes de ese período (generación perezosa). Sin filtros devuelve el historial completo
sin generar nada.

### `PUT /api/v1/budgets/{budget_id}`

Actualiza un presupuesto existente (incluido `is_recurring`).

### `DELETE /api/v1/budgets/{budget_id}`

Elimina (lógicamente) un presupuesto del usuario autenticado. La categoría/período queda
disponible para crear uno nuevo de inmediato.

## Dashboard

### `GET /api/v1/dashboard/summary`

Devuelve resumen financiero del mes actual. Solo incluye cuentas marcadas como destacadas (`highlighted=true`); si no hay destacadas, incluye todas. Las monedas se ordenan por la moneda preferida del usuario primero.

Devuelve:

- `balances`: array de `{currency, total}` — saldo total por moneda.
- `monthly_income_by_currency`: array de `{currency, total}` — ingresos del mes por moneda.
- `monthly_expense_by_currency`: array de `{currency, total}` — gastos del mes por moneda.
- `monthly_flow_balance` (Fase 11 §11.3): ingreso mensual declarado por el usuario
  (`User.monthly_income`) menos el gasto del mes en su moneda preferida; `null` si el
  usuario aún no ha fijado `monthly_income` (el frontend distingue "0" de "sin definir").
  Los gastos en otras monedas no restan — misma limitación de "una moneda a la vez"
  documentada para `cashflow-series` y `category-distribution`.

### `GET /api/v1/dashboard/budgets-progress`

Devuelve progreso de presupuestos del mes actual con:

- `budget_id`
- `category_name`
- `amount_limit`
- `spent`
- `percentage`
- `currency` — moneda del presupuesto (`Budget.currency`); `spent` solo suma los gastos
  de esa misma moneda (Fase 11 §11.1)

Antes de calcular, genera las filas de presupuestos recurrentes pendientes del mes en
curso — por eso los presupuestos "reaparecen" solos cada mes al entrar al dashboard.

### `GET /api/v1/dashboard/cashflow-series`

Devuelve una serie temporal de flujo de caja agrupada por día o por mes.

Parámetros:

- `start_date`
- `end_date`
- `period`: `day | month`
- `currency` (opcional): moneda a filtrar; por defecto la preferida del usuario. La serie
  nunca mezcla monedas — se filtra por una sola, no se agrupa (Fase 11 §11.1).

Salida:

- `date_label`
- `income`
- `expense`

### `GET /api/v1/dashboard/category-distribution`

Devuelve la distribución por categoría en un rango de fechas.

Parámetros:

- `start_date`
- `end_date`
- `type` (opcional, default `"expense"`): `income | expense`
- `neto` (opcional, default `false`): si es `true`, calcula gasto neto (`SUM(expense) - SUM(income)`) por categoría. Ignora el parámetro `type`. Solo devuelve categorías con neto positivo.
- `currency` (opcional): moneda a filtrar; por defecto la preferida del usuario. Se aplica
  en ambas ramas (`neto=true` y `neto=false`) — los totales nunca mezclan monedas
  (Fase 11 §11.1).

Salida:

- `category_id`
- `category_name`
- `total` — cuando `neto=true`, representa el gasto neto

## Notificaciones (Fase 13 §13.5)

Las notificaciones las escriben el motor de alertas de presupuestos (`GET /api/v1/budgets/` +
transacciones de gasto que cruzan el 80 %/100 % del límite, ver §13.3) y el resumen semanal
automático (Fase 14 §14.3, un `weekly_summary` por usuario y semana ISO cada lunes). Estos
endpoints solo leen/escriben el estado de la bandeja. Auth: `Bearer`, sin rate limiting
(mismo criterio que budgets/dashboard).

### `GET /api/v1/notifications/`

Lista las notificaciones del usuario actual, más recientes primero, con paginación simple
(`skip`/`limit`, mismo patrón que `GET /api/v1/transactions/`).

Salida (paginada):

- `items`: array de notificaciones con `id`, `type` (`budget_threshold_80` |
  `budget_threshold_100` | `weekly_summary`), `title`, `body`, `budget_id` (nullable),
  `period_key` (nullable, Fase 14 — semana ISO como `"2026-W37"` para
  `weekly_summary`), `read_at` (nullable), `created_at`
- `total`, `page`, `page_size`

### `GET /api/v1/notifications/unread-count`

Conteo de no leídas para el badge de la campana — `{"count": N}`. Query barata
(`COUNT(*) WHERE user_id=? AND read_at IS NULL`, cubierta por el índice compuesto
`ix_notifications_user_id_created_at`).

### `PATCH /api/v1/notifications/{notification_id}/read`

Marca una notificación como leída (`read_at = now()`). Idempotente.

Errores esperados:

- `404` si la notificación no existe o no es del usuario autenticado (nunca `403`, no filtra
  existencia ajena).

### `PATCH /api/v1/notifications/read-all`

Marca todas las no leídas del usuario como leídas. Devuelve el nuevo conteo de no leídas
(siempre `{"count": 0}` tras la acción) — idempotente.

### `DELETE /api/v1/notifications/read` (Fase 13 §13.7)

Elimina todas las notificaciones **ya leídas** del usuario autenticado — las no leídas nunca
se tocan. Devuelve `{"estado": "OK", "mensaje": "Se eliminaron N notificaciones leídas."}`.

> Nota de orden de rutas: esta ruta se registra ANTES de `DELETE /{notification_id}` — es
> literal, no un parámetro, y FastAPI resuelve por orden de declaración.

### `DELETE /api/v1/notifications/{notification_id}` (Fase 13 §13.7)

Elimina una notificación puntual del usuario autenticado.

Errores esperados:

- `404` si la notificación no existe o no es del usuario autenticado (mismo criterio que el
  resto del archivo: nunca `403`).

## Push web (Fase 13 §13.2)

Suscripciones Web Push para avisos de presupuestos. Las claves del servidor se configuran con
`VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY` y `VAPID_SUBJECT` (ver `docker-compose.yml` y `.env`).

### `GET /api/v1/push/vapid-public-key`

Devuelve la clave pública VAPID (base64url) que el frontend necesita para crear la suscripción
del navegador. Endpoint público (sin auth): el `navigator.serviceWorker` lo consulta antes de
tener tokens.

Salida:

- `public_key`

Errores esperados:

- `503` si `VAPID_PUBLIC_KEY` no está configurado en el entorno.

### `POST /api/v1/push/subscribe`

Registra (o actualiza, "upsert" por `endpoint`) la suscripción del navegador del usuario
autenticado.

Entrada:

- `endpoint`: URL asignada por el push service.
- `keys.p256dh` y `keys.auth`: claves base64url que emite el navegador.

Salida: la suscripción con `id`, `endpoint`, `created_at`.

### `DELETE /api/v1/push/subscribe`

Da de baja la suscripción del usuario autenticado. El cuerpo JSON lleva el `endpoint` (el
frontend no guarda el `id` persistido: solo tiene la suscripción que devuelve el navegador).

Entrada:

- `endpoint`

Errores esperados:

- `404` si la suscripción no existe o no pertenece al usuario autenticado.

Cuando un push falla con `404/410 Gone` (el navegador revocó la suscripción), el backend borra
la fila automáticamente al intentar enviar — no requiere acción del cliente.