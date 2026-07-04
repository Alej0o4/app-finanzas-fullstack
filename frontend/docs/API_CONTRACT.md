# Contrato de API del Frontend

## Propósito

Este documento define cómo el frontend consume el backend de Oikos y qué supuestos puede hacer sobre los datos recibidos.

La regla base es simple: el frontend no recalcula saldos, progreso de presupuestos ni agregados financieros. El backend es la fuente de verdad.

## Base URL y autenticación

- Base URL: `NEXT_PUBLIC_API_URL`
- Fallback local: `http://localhost:8000`
- Autenticación: `Authorization: Bearer <token>`
- El token se lee desde `localStorage` en `lib/api.ts`

Si el backend responde `401`, el cliente limpia el token y redirige a `/login`.

## Endpoints consumidos por el frontend

### Autenticación

- `POST /api/auth/login`
- `GET /api/users/me`

### Cuentas

- `GET /api/accounts/`
- `GET /api/accounts/{account_id}`
- `POST /api/accounts/`
- `PUT /api/accounts/{account_id}`
- `DELETE /api/accounts/{account_id}`

### Categorías

- `GET /api/categories/`
- `GET /api/categories/{category_id}`
- `POST /api/categories/`
- `PUT /api/categories/{category_id}`
- `DELETE /api/categories/{category_id}`

### Transacciones

- `GET /api/transactions/`
- `POST /api/transactions/`
- `PUT /api/transactions/{transaction_id}`
- `DELETE /api/transactions/{transaction_id}`

Filtros soportados por el feed:

- `skip`
- `limit`
- `account_id`
- `category_id`
- `start_date`
- `end_date`

### Presupuestos

- `GET /api/budgets/`
- `POST /api/budgets/`
- `PUT /api/budgets/{budget_id}`
- `DELETE /api/budgets/{budget_id}`

### Dashboard

- `GET /api/dashboard/summary`
- `GET /api/dashboard/budgets-progress`
- `GET /api/dashboard/cashflow-series`
- `GET /api/dashboard/category-distribution` (soporta `neto=true` para calcular gasto neto por categoría)

## Contratos de datos importantes

### Usuario autenticado

`GET /api/users/me` devuelve al menos:

- `id`
- `email`
- `full_name`

### Cuenta

El frontend asume:

- `id`
- `name`
- `type`
- `balance`
- `user_id`

Reglas:

- `balance` se muestra, pero no debe recalcularse en cliente.
- En edición no se envía `balance`.

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
- `date`
- `account_id`
- `category_id`

Reglas:

- El feed principal debe ordenarse por fecha descendente desde el backend.
- Los detalles por cuenta y categoría reutilizan el mismo contrato.
- Al crear, editar o borrar una transacción, se deben invalidar las queries relacionadas.

### Presupuesto

El frontend asume:

- `id`
- `category_id`
- `amount_limit`
- `month`
- `year`

En el dashboard, el progreso de presupuesto llega ya calculado desde el backend.

### Dashboard

El frontend asume:

- `total_balance`
- `monthly_income`
- `monthly_expense`

Para el progreso de presupuestos, el backend devuelve valores listos para pintar:

- `category_id`
- `category_name`
- `amount_limit`
- `spent`
- `percentage`

## Errores esperados

- `400`: validación de negocio fallida o dato inválido.
- `401`: token ausente o inválido.
- `403`: acción no permitida.
- `404`: recurso inexistente o fuera de alcance del usuario.

## Reglas de consumo

- No enviar `user_id` desde el frontend.
- No enviar `balance` en edición de cuentas.
- No calcular balances ni agregados financieros en el cliente.
- No asumir que una categoría es editable si `user_id` es `null`.
- Usar `queryKey` explícitas y invalidación después de mutaciones.

## Relación con la documentación del backend

La documentación canónica del contrato vive en el backend. Este archivo existe para explicar cómo consumirlo desde la app Next.js sin duplicar lógica de negocio.
