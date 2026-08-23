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
- `GET /api/v1/users/me/preferences`
- `PATCH /api/v1/users/me/preferences`

### Cuentas

- `GET /api/v1/accounts/`
- `GET /api/v1/accounts/{account_id}`
- `POST /api/v1/accounts/`
- `PUT /api/v1/accounts/{account_id}`
- `PATCH /api/v1/accounts/{account_id}/highlighted`
- `DELETE /api/v1/accounts/{account_id}`

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

### Presupuestos

- `GET /api/v1/budgets/`
- `POST /api/v1/budgets/`
- `PUT /api/v1/budgets/{budget_id}`
- `DELETE /api/v1/budgets/{budget_id}`

### Dashboard

- `GET /api/v1/dashboard/summary`
- `GET /api/v1/dashboard/budgets-progress`
- `GET /api/v1/dashboard/cashflow-series`
- `GET /api/v1/dashboard/category-distribution` (soporta `neto=true` para calcular gasto neto por categoría)

## Contratos de datos importantes

### Usuario autenticado

`GET /api/v1/users/me` devuelve al menos:

- `id`
- `email`
- `full_name`
- `preferred_currency` (default `"COP"`)
- `preferred_locale` (default `"es-CO"`)
- `preferred_theme` (default `"dark"`)
- `monthly_income` (`number | null`) — dato financiero del perfil, editable vía `PATCH /api/v1/users/me`. Sin UI que lo consuma todavía (onboarding de Fase 13).

### Preferencias de usuario

`GET /api/v1/users/me/preferences` devuelve:

- `preferred_currency`: string
- `preferred_locale`: string
- `preferred_theme`: string

`PATCH /api/v1/users/me/preferences` acepta campos opcionales: `preferred_currency`, `preferred_locale`, `preferred_theme`.

### Cuenta

El frontend asume:

- `id`
- `name`
- `type`
- `balance`
- `currency`
- `user_id`

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
