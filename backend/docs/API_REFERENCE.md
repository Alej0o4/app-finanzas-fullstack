# Referencia de API

## Convenciones generales

- Base path: `/api/v1`
- Autenticación: `Authorization: Bearer <token>` en rutas protegidas.
- Content type esperado: `application/json`, excepto login, que usa formulario OAuth2.
- Rate limiting: `/api/v1/auth/login`, `POST /api/v1/users/` y `/api/v1/auth/password-reset/request` (5 req/min por IP via `slowapi`).
- CORS: orígenes permitidos vía `ALLOWED_ORIGINS` (env) + regex para IPs de Tailscale (100.x.x.x).
- Uvicorn escucha en `0.0.0.0` para soportar acceso remoto via Tailscale.

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

## Usuarios

### `POST /api/v1/users/`

Crea un usuario nuevo. Tras crearlo, envía un email de verificación (ver
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

### `GET /api/v1/users/me/preferences`

Devuelve las preferencias del usuario autenticado.

Salida:

- `preferred_currency`: string (default `"COP"`)
- `preferred_locale`: string (default `"es-CO"`)
- `preferred_theme`: string (default `"dark"`)

### `PATCH /api/v1/users/me/preferences`

Actualiza preferencias del usuario autenticado.

Entrada (campos opcionales):

- `preferred_currency`: string
- `preferred_locale`: string
- `preferred_theme`: string

## Cuentas

### `POST /api/v1/accounts/`

Crea una cuenta para el usuario autenticado.

Entrada:

- `name`
- `type`: `cash | debit | credit`
- `balance`: saldo inicial permitido solo en creación.
- `currency`: código de moneda (default `"COP"`). Ej: `"COP"`, `"USD"`, `"EUR"`.
- `highlighted`: si la cuenta es destacada (default `false`).

Salida:

- `id`
- `name`
- `type`
- `balance`
- `currency`
- `highlighted`
- `user_id`

### `GET /api/v1/accounts/{account_id}`

Devuelve una cuenta del usuario autenticado.

### `GET /api/v1/accounts/`

Lista las cuentas del usuario autenticado.

### `PUT /api/v1/accounts/{account_id}`

Actualiza nombre, tipo y destacada de la cuenta.

### `PATCH /api/v1/accounts/{account_id}/highlighted`

Alterna el estado `highlighted` de una cuenta (toggle).

Salida: `AccountResponse` actualizada.

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

Registra un ingreso o gasto y actualiza el saldo de la cuenta asociada.

Entrada:

- `amount`: mayor a cero.
- `type`: `income | expense`
- `description`: opcional.
- `date`: fecha de la transación (formato ISO, default: ahora).
- `account_id`
- `category_id`

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

Actualiza una transacción y recalcula saldos de forma inversa y luego aplicada.

### `DELETE /api/v1/transactions/{transaction_id}`

Elimina una transacción y revierte el impacto sobre el saldo de la cuenta.

## Presupuestos

### `POST /api/v1/budgets/`

Crea un presupuesto por categoría, mes y año.

Entrada:

- `amount_limit`: mayor a cero.
- `currency`: código de moneda (default `"COP"`).
- `month`: entre 1 y 12.
- `year`
- `category_id`

Errores esperados:

- `400` si ya existe un presupuesto para la misma categoría, mes y año.

### `GET /api/v1/budgets/`

Lista presupuestos del usuario autenticado, con filtros opcionales por mes y año.

Filtros opcionales:

- `month`
- `year`

### `PUT /api/v1/budgets/{budget_id}`

Actualiza un presupuesto existente.

### `DELETE /api/v1/budgets/{budget_id}`

Elimina un presupuesto del usuario autenticado.

## Dashboard

### `GET /api/v1/dashboard/summary`

Devuelve resumen financiero del mes actual. Solo incluye cuentas marcadas como destacadas (`highlighted=true`); si no hay destacadas, incluye todas. Las monedas se ordenan por la moneda preferida del usuario primero.

Devuelve:

- `balances`: array de `{currency, total}` — saldo total por moneda.
- `monthly_income_by_currency`: array de `{currency, total}` — ingresos del mes por moneda.
- `monthly_expense_by_currency`: array de `{currency, total}` — gastos del mes por moneda.

### `GET /api/v1/dashboard/budgets-progress`

Devuelve progreso de presupuestos del mes actual con:

- `budget_id`
- `category_name`
- `amount_limit`
- `spent`
- `percentage`

### `GET /api/v1/dashboard/cashflow-series`

Devuelve una serie temporal de flujo de caja agrupada por día o por mes.

Parámetros:

- `start_date`
- `end_date`
- `period`: `day | month`

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

Salida:

- `category_id`
- `category_name`
- `total` — cuando `neto=true`, representa el gasto neto