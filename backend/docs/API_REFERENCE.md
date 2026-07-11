# Referencia de API

## Convenciones generales

- Base path: `/api`
- Autenticación: `Authorization: Bearer <token>` en rutas protegidas.
- Content type esperado: `application/json`, excepto login, que usa formulario OAuth2.
- Rate limiting: solo en `/api/auth/login` (5 req/min por IP via `slowapi`).

## Autenticación

### `POST /api/auth/login`

Inicia sesión y devuelve un JWT + refresh token.

Entrada (form-urlencoded):

- `username`: email del usuario.
- `password`: contraseña en texto plano.

Salida:

- `access_token`: JWT firmado (expira en 60 min).
- `refresh_token`: token opaco para renovar sesión (expira en 30 días).
- `token_type`: `bearer`.

Errores esperados:

- `403` si las credenciales son inválidas.
- `429` si se exceden 5 intentos por minuto (rate limiting).

### `POST /api/auth/refresh`

Rota el refresh token y devuelve un nuevo JWT.

Entrada:

- `refresh_token`: el refresh token actual.

Salida:

- `access_token`: nuevo JWT firmado.
- `refresh_token`: nuevo refresh token (el anterior queda invalidado).

Errores esperados:

- `401` si el refresh token es inválido o expiró.

### `POST /api/auth/logout`

Revoca el refresh token, cerrando la sesión.

Entrada:

- `refresh_token`: el refresh token a revocar.

Salida:

- `{"estado": "OK", "mensaje": "Sesion cerrada exitosamente."}`

## Usuarios

### `POST /api/users/`

Crea un usuario nuevo.

Entrada:

- `full_name`
- `email`
- `password`

Salida:

- `id`
- `full_name`
- `email`
- `preferred_currency` (default: `"COP"`)
- `preferred_locale` (default: `"es-CO"`)
- `preferred_theme` (default: `"dark"`)

Errores esperados:

- `400` si el correo ya existe.

### `GET /api/users/me`

Devuelve el usuario autenticado actual.

Salida:

- `id`
- `full_name`
- `email`
- `preferred_currency`
- `preferred_locale`
- `preferred_theme`

### `GET /api/users/me/preferences`

Devuelve las preferencias del usuario autenticado.

Salida:

- `preferred_currency`: string (default `"COP"`)
- `preferred_locale`: string (default `"es-CO"`)
- `preferred_theme`: string (default `"dark"`)

### `PATCH /api/users/me/preferences`

Actualiza preferencias del usuario autenticado.

Entrada (campos opcionales):

- `preferred_currency`: string
- `preferred_locale`: string
- `preferred_theme`: string

## Cuentas

### `POST /api/accounts/`

Crea una cuenta para el usuario autenticado.

Entrada:

- `name`
- `type`: `cash | debit | credit`
- `balance`: saldo inicial permitido solo en creación.
- `currency`: código de moneda (default `"COP"`). Ej: `"COP"`, `"USD"`, `"EUR"`.

Salida:

- `id`
- `name`
- `type`
- `balance`
- `currency`
- `user_id`

### `GET /api/accounts/{account_id}`

Devuelve una cuenta del usuario autenticado.

### `GET /api/accounts/`

Lista las cuentas del usuario autenticado.

### `PUT /api/accounts/{account_id}`

Actualiza nombre y tipo de la cuenta.

### `DELETE /api/accounts/{account_id}`

Elimina la cuenta si no tiene transacciones asociadas.

Errores esperados:

- `400` si la cuenta tiene transacciones asociadas.

## Categorías

### `POST /api/categories/`

Crea una categoría personalizada.

Entrada:

- `name`
- `type`: `income | expense`

### `GET /api/categories/`

Lista categorías base del sistema y categorías propias del usuario.

### `PUT /api/categories/{category_id}`

Actualiza una categoría personalizada.

### `DELETE /api/categories/{category_id}`

Elimina una categoría personalizada solo si no tiene transacciones ni presupuestos asociados.

## Transacciones

### `POST /api/transactions/`

Registra un ingreso o gasto y actualiza el saldo de la cuenta asociada.

Entrada:

- `amount`: mayor a cero.
- `type`: `income | expense`
- `description`: opcional.
- `date`: fecha de la transación (formato ISO, default: ahora).
- `account_id`
- `category_id`

Nota: `currency` se hereda automáticamente de la cuenta asociada.

### `GET /api/transactions/`

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

### `PUT /api/transactions/{transaction_id}`

Actualiza una transacción y recalcula saldos de forma inversa y luego aplicada.

### `DELETE /api/transactions/{transaction_id}`

Elimina una transacción y revierte el impacto sobre el saldo de la cuenta.

## Presupuestos

### `POST /api/budgets/`

Crea un presupuesto por categoría, mes y año.

Entrada:

- `amount_limit`: mayor a cero.
- `currency`: código de moneda (default `"COP"`).
- `month`: entre 1 y 12.
- `year`
- `category_id`

Errores esperados:

- `400` si ya existe un presupuesto para la misma categoría, mes y año.

### `GET /api/budgets/`

Lista presupuestos del usuario autenticado, con filtros opcionales por mes y año.

Filtros opcionales:

- `month`
- `year`

### `PUT /api/budgets/{budget_id}`

Actualiza un presupuesto existente.

### `DELETE /api/budgets/{budget_id}`

Elimina un presupuesto del usuario autenticado.

## Dashboard

### `GET /api/dashboard/summary`

Devuelve:

- `total_balance`
- `monthly_income`
- `monthly_expense`
- `currency`: moneda del resumen (default `"COP"`)

### `GET /api/dashboard/budgets-progress`

Devuelve progreso de presupuestos del mes actual con:

- `budget_id`
- `category_name`
- `amount_limit`
- `spent`
- `percentage`

### `GET /api/dashboard/cashflow-series`

Devuelve una serie temporal de flujo de caja agrupada por día o por mes.

Parámetros:

- `start_date`
- `end_date`
- `period`: `day | month`

Salida:

- `date_label`
- `income`
- `expense`

### `GET /api/dashboard/category-distribution`

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