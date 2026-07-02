# Referencia de API

## Convenciones generales

- Base path: `/api`
- Autenticación: `Authorization: Bearer <token>` en rutas protegidas.
- Content type esperado: `application/json`, excepto login, que usa formulario OAuth2.

## Autenticación

### `POST /api/auth/login`

Inicia sesión y devuelve un JWT.

Entrada:

- `username`: email del usuario.
- `password`: contraseña en texto plano.

Salida:

- `access_token`: JWT firmado.
- `token_type`: `bearer`.

Errores esperados:

- `403` si las credenciales son inválidas.

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

Errores esperados:

- `400` si el correo ya existe.

### `GET /api/users/me`

Devuelve el usuario autenticado actual.

Salida:

- `id`
- `full_name`
- `email`

## Cuentas

### `POST /api/accounts/`

Crea una cuenta para el usuario autenticado.

Entrada:

- `name`
- `type`: `cash | debit | credit`
- `balance`: saldo inicial permitido solo en creación.

Salida:

- `id`
- `name`
- `type`
- `balance`
- `user_id`

### `GET /api/accounts/{account_id}`

Devuelve una cuenta del usuario autenticado.

### `GET /api/accounts/`

Lista las cuentas del usuario autenticado.

### `PUT /api/accounts/{account_id}`

Actualiza nombre y tipo de la cuenta.

### `DELETE /api/accounts/{account_id}`

Elimina la cuenta si no tiene transacciones asociadas.

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
- `account_id`
- `category_id`

### `GET /api/transactions/`

Lista transacciones del usuario autenticado.

Filtros opcionales:

- `skip`
- `limit`
- `account_id`
- `category_id`
- `start_date`
- `end_date`

### `PUT /api/transactions/{transaction_id}`

Actualiza una transacción y recalcula saldos de forma inversa y luego aplicada.

### `DELETE /api/transactions/{transaction_id}`

Elimina una transacción y revierte el impacto sobre el saldo de la cuenta.

## Presupuestos

### `POST /api/budgets/`

Crea un presupuesto por categoría, mes y año.

Entrada:

- `amount_limit`: mayor a cero.
- `month`: entre 1 y 12.
- `year`
- `category_id`

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

Devuelve la distribución de gastos por categoría en un rango de fechas.

Parámetros:

- `start_date`
- `end_date`

Salida:

- `category_id`
- `category_name`
- `total`