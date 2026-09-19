# Estado y Fetching

## Objetivo

Este documento define cómo manejar estado remoto y estado de UI en el frontend de Oikos.

La separación es estricta:

- React Query para estado de servidor.
- Zustand para estado de interfaz.
- Estado local de React para formularios y controles temporales.

## Capa de servidor

### React Query

`components/QueryProvider.tsx` crea una única instancia de `QueryClient` para toda la app.

Configuración base actual:

- `staleTime`: 1 minuto.
- `refetchOnWindowFocus`: `false`.

Reglas de uso:

- Cada pantalla de negocio debe tener su propia `queryKey`.
- Las mutaciones deben invalidar las queries relacionadas.
- No duplicar cálculos derivados del backend en el cliente.

## Query keys utilizadas

Las claves deben mantenerse consistentes entre páginas y componentes.

### Globales

- `currentUser`
- `userPreferences` (Fase 21/22 §22.1) — `GET/PATCH /users/me/preferences`; la usan
  `useUserPreferences.ts` y `settings/page.tsx`. Se invalida tras cambiar moneda/locale/tema.
- `accounts`
- `categories`
  - Nota (Fase 25 §25.6/M2): **no existe una key separada para "categorías ocultas"**.
    `is_hidden` es un campo más de la respuesta de `GET /categories/` (Fase 18); el filtrado
    se hace client-side sobre esta misma key (`categories?.filter((c) => c.is_hidden)` en
    `categories/page.tsx`), sin key nueva que invalidar.
- `budgets`
- `transactions`
- `dashboardSummary`
- `budgets-progress`
- `recent-transactions`
- `dashboard-category-breakdown` (Fase 11 §11.4)
- `accounts-summary` (Fase 11 §11.5)
- `notifications` (Fase 13 §13.5)
- `notifications-unread-count` (Fase 13 §13.5)
- `apiKeys` (Fase 16 §16.1) — lista de API keys propias (`GET /api-keys/`); se invalida tras
  `POST /api-keys/` (crear) y `DELETE /api-keys/{id}` (revocar).

### Vista específica

- `account`
- `category`
- `transactions`, `account`, `id`
- `transactions`, `category`, `id`
- `account-monthly-summary` (Fase 17 §17.1) — balance del mes de una cuenta puntual
  (`GET /accounts/{id}/monthly-summary`). Clave por cuenta, no reutiliza `dashboardSummary`.
- `account-category-breakdown` (Fase 17 §17.1) — desglose de gastos del mes por categoría,
  restringido a una cuenta.
- `account-budgets-progress` (Fase 17 §17.1, Decisión 17.1.3/P4) — progreso de presupuestos
  filtrado a la moneda de una cuenta. El prefijo matchea la invalidación por prefix desde
  el módulo de presupuestos.
- `analytics-cashflow` — la key incluye, tras el período, dos segmentos opcionales por
  cuenta/moneda (Fase 17): `['analytics-cashflow', start, end, period, accountId?, currency?]`.
- `analytics-categories` — idem, con `type`/`neto` y `accountId?`/`currency?`:
  `['analytics-categories', start, end, type, neto?, accountId?, currency?]`. Cuando el
  selector de cuenta de `/analytics` está en una moneda distinta a la preferida, `currency`
  viaja explícito en la key (corrección del Bug real documentado en Fase 19,
  "Analítica sin selector de cuenta").

## Invalidation patterns

### Crear transacción

Cuando se crea una transacción, se invalidan como mínimo:

- `transactions`
- `recent-transactions`
- `accounts`
- `dashboardSummary`
- `budgets-progress`
- `analytics-cashflow`, `analytics-categories`
- `dashboard-category-breakdown`, `accounts-summary` (Fase 11 — la card de flujo mensual y
  el desglose por categoría del dashboard, y el total de `/accounts`, dependen de datos
  agregados de transacciones)

### Editar transacción

Después de editar:

- `transactions`
- vista específica por cuenta o categoría si aplica
- `accounts`
- `dashboardSummary`
- `budgets-progress`
- `analytics-cashflow`, `analytics-categories`
- `dashboard-category-breakdown`, `accounts-summary`

### Eliminar transacción

Después de borrar:

- `transactions`
- `accounts`
- `dashboardSummary`
- `budgets-progress`
- `analytics-cashflow`, `analytics-categories`
- `dashboard-category-breakdown`, `accounts-summary`

### Crear/editar/eliminar cuenta

Después de mutar una cuenta:

- `accounts`
- `accounts-summary` (Fase 11 §11.5)
- `dashboardSummary`

### Crear/editar/eliminar categoría

Después de mutar una categoría:

- `categories`

### Crear/editar/eliminar presupuesto

Después de mutar un presupuesto:

- `budgets`
- `dashboardSummary`
- `budgets-progress`

### Marcar notificaciones como leídas (Fase 13 §13.5)

Las dos mutaciones (`PATCH /notifications/{id}/read` y `PATCH /notifications/read-all`)
invalidan **ambas** keys de notificaciones:

- `notifications`
- `notifications-unread-count`

Aunque `read-all` solo afecte el conteo, se invalida también la lista: React Query puede
revalidar una fila individual con `read_at` seteado sin que el popover haga fetch extra
(cada mutación es barata y poco frecuente; no vale la pena optimizar con updateQueryData).
El `unread-count` tiene `refetchInterval: 60_000` (Decisión 13.5.4): el badge se refresca
solo, sin disparar la query de lista completa.

### Actualizar preferencias / fijar ingreso mensual (Settings, Fase 21/22)

`useUserPreferences.ts` invalida tras un `PATCH /users/me/preferences` (Decisión 22.1.6):

- `userPreferences`
- `currentUser`
- `dashboard-category-breakdown`
- `accounts` — condicionalmente: solo si la moneda preferida cambió (las cuentas no cambian
  de moneda, pero los agregados del dashboard que dependen de `preferred_currency` sí
  necesitan revalidarse).

## Estado local

### React

Usar `useState` para:

- formularios;
- modales;
- selección temporal de fecha, cuenta o categoría dentro de un formulario.

Los filtros de pantalla que deben ser compartibles por URL ya NO van en `useState`:
usar `useQueryParamState` (ver sección de hooks). Ejemplos actuales de `useState`:

- `TransactionModal`
- formularios de cuentas, categorías y presupuestos
- edición inline en detalles por cuenta y categoría
- `hiddenCategories` en analytics (decisión explícita: no es estado compartible)

## Estado global de UI

### Zustand

`store/useUiStore.ts` mantiene estado puramente visual:

- `isSidebarOpen`
- `toggleSidebar`

Regla:

- No guardar datos de dominio en Zustand si pertenecen al backend.

## Cliente HTTP

### `lib/api.ts`

Comportamiento:

- Adjunta los cookies de sesión con `withCredentials: true` y agrega `X-CSRF-Token` (valor del cookie `csrf_token`) en todo método que no sea `GET`/`HEAD` (Fase 26).
- Redirige a `/login` ante `401` (tras intentar renovar la sesión con `POST auth/refresh` sin body).

Consecuencias para el estado:

- La sesión expirada se resuelve limpiando el token y dejando que la app vuelva al login.
- No se debe construir otra capa paralela de auth en páginas individuales.

## Tipos generados desde OpenAPI (Fase 16 §16.3)

Desde Fase 16 conviven dos fuentes de tipos (Decisión 16.3.2/16.3.3 del spec de Fase 16):

- `types/generated/api.ts` — **tipos exactos del contrato**, generados con
  `pnpm gen:types` desde el `openapi.json` del backend local
  (`http://localhost:8000/openapi.json`, NO bajo `/api/v1/`). Es la fuente de verdad para
  **código nuevo**: campos y endpoints que no existían antes de Fase 16
  (API keys, reconciliación de saldos) se tipan con
  `components['schemas']['...']`, no a mano.
- `types/api.ts` — tipos manuales **existentes** (interfaces ergonómicas para el código que
  ya las consume). Se mantienen tal cual; no se migran call sites existentes en este ítem.
  Si se toca por otra razón, se puede migrar oportunistamente.

Reglas:

- **Código nuevo usa tipos generados** (`import type { components } from '@/types/generated/api'`).
- **Código existente sigue usando tipos manuales** — no mezclar en el mismo call site salvo
  que el campo nuevo solo exista en el schema generado.
- **Regenerar y commitear** `types/generated/api.ts` como parte del mismo PR que cambie un
  schema del backend, mismo criterio manual que `API_REFERENCE.md`/`API_CONTRACT.md`. El
  archivo generado se commitea: un clon fresco sin backend corriendo necesita compilar.
- **Drift conocido**: los campos monetarios (`amount`, `balance`, `spent`, `discrepancy`,
  etc.) son `string` en los tipos generados — así los serializa el backend (`Decimal` →
  string). Los tipos manuales los tipan como `number`; al leer datos nuevos tipados como
  `string`, convertir con `Number(...)` donde el código existente espera número (p. ej.
  `formatCurrency`).

Comando de regeneración (desde `frontend/`):

```sh
pnpm gen:types
```

Requiere un backend corriendo en local; sin backend, el comando falla y el archivo
commiteado sigue siendo válido para compilar.

## Hooks compartidos

### `useCurrentUser`

- Consulta `/api/users/me`.
- Debe usarse en vistas autenticadas donde el nombre o identidad del usuario sea relevante.

### `useAccounts` / `useCategories` / `useTransactions` (Fase 25 §25.4)

Extraídos en Fase 25 desde los `useQuery` inline que cada página repetía
(`lib/hooks/use{Accounts,Categories,Transactions}.ts`, mismo `queryKey`/`queryFn` que usaban
los call sites — no cambia ningún comportamiento de cacheo):

- `useAccounts(options?)` — `GET /accounts/` → `Account[]`. Segundo parámetro opcional
  `{ enabled }` para queries condicionales (p. ej. `TransactionModal` con `enabled: isOpen`).
- `useCategories(options?)` — `GET /categories/` → `Category[]` (incluye `is_hidden`, Fase 18).
- `useTransactions(params)` — `GET /transactions/` → `PaginatedResponse<Transaction>`.
  `params` es el mismo objeto de filtros que armaba `transactions/page.tsx` (skip, limit,
  account_id, category_id, start_date, end_date); se pasa tal cual a
  `queryKeys.transactions.filtered(params)`. Único consumidor: `transactions/page.tsx`.

Solo cubren **lecturas**. Las mutaciones quedan en cada página con sus listas de
invalidación heterogéneas (Decisión Q3 de la spec de Fase 25) — no forzarlas a un hook
compartido.

### `useQueryParamState` (Fase 12 §12.1)

`hooks/useQueryParamState.ts` sincroniza un string con un query param de la URL:

```ts
const [categoryFilter, setCategoryFilter] = useQueryParamState('category', 'all');
```

Comportamiento:

- El valor de la URL manda sobre el default: `searchParams.get(key) ?? defaultValue`.
- El setter escribe con `router.replace(..., { scroll: false })` — shallow, sin historial
  ni scroll jump. Un valor igual al default se elimina del query string (la URL canónica
  solo lleva filtros activos).
- Los links son la fuente de verdad de la vista: copiando la URL se reproduce el estado
  exacto de filtros en cualquier navegador/sesión (Decisión 12.1.2: reemplaza
  `usePersistedState` en analytics).
- **`validate` opcional (Fase 13 §13.6)** — normaliza el valor a lectura, antes de
  devolverlo:

  ```ts
  const [barPeriod, setBarPeriod] = useQueryParamState('bar', '30d', validateBarPeriod);
  ```

  - Es read-time: un link inválido (`?category=abc`, `?bar=foo`, `?start=1-2-3`) devuelve
    el fallback en vez de un string crudo que después se castea a ciegas — la frontera de
    entrada es el hook, no cada consumidor.
  - La URL **no** se reescribe con el valor corregido: el re-normalizado en cada render
    alcanza (los setters solo escriben valores que el propio UI produce; si el query string
    sigue mal formado, el siguiente render lo vuelve a normalizar igual). Evita un
    `router.replace` en bucle al montar.
  - Si el validator tiene tipo de retorno de unión (p. ej. `(raw: string): BarPeriod`), el
    hook infiere ese tipo como el valor devuelto — los casts directos
    (`barPeriod as BarPeriod`) desaparecen de las páginas. Sin `validate`, el hook devuelve
    `string`, retrocompatible con los callers de Fase 12.

Reglas:

- **Requerido `<Suspense>`**: como consume `useSearchParams`, el componente debe envolverse
  en `<Suspense>` (mismo requisito que login/reset-password). El default export de la página
  es un wrapper que envuelve el contenido real.
- La capa URL comunica strings; las uniones literales se garantizan con el `validate`
  del hook (Fase 13 §13.6): si el validator retorna la unión, el valor sale ya tipado y
  no hace falta cast en el consumidor. Los setters se pasan tal cual (aceptan string,
  que cubre la unión).
- Valores booleanos en URL se serializan como `'true'`/`'false'` y se leen con
  `raw === 'true'`; el setter recibe `String(value)`.
- NO usar para estado que no deba ser compartible (p. ej. categorías ocultas en el donut se
  quedan en `useState`, Decisión 12.1.3).
- No duplicar: un valor que vive en la URL no debe copiarse además a `useState`.

Uso actual:

- `transactions`: `start`, `end`, `category` (default `'all'`), `account` (default `'all'`),
  `preset` (default `'all'`). Un link con `?preset=month` sin `start`/`end` siembra las
  fechas del preset al montar.
- `analytics`: `bar` (`'30d'`), `series` (`'both'`), `donut` (`'month'`), `type`
  (`'expense'`), `neto` (`'false'`).

## Patrones recomendados

- Mantener `queryKey` estables y predecibles.
- No mezclar estado remoto con estado de formulario.
- Invalidar por dominio, no por componente.
- En filtros de listas, convertir controles de UI en parámetros de query.
- Si una query depende de un modal abierto, usar `enabled: isOpen`.

## Casos específicos actuales

### Dashboard

- Resumen (incluye `monthly_flow_balance`, Fase 11 §11.3): `dashboardSummary`
- Progreso de presupuestos: `budgets-progress`
- Transacciones recientes: `recent-transactions`
- Desglose por categoría del mes (Fase 11 §11.4): `dashboard-category-breakdown`

### Analytics

- Cashflow: `analytics-cashflow` (con segmentos opcionales `accountId`/`currency`, ver
  "Vista específica" arriba)
- Categorías: `analytics-categories` (con `neto` y los mismos segmentos opcionales de cuenta/moneda)

### Transacciones

- Feed global: `transactions`
- Feed por cuenta o categoría: queries derivadas con el mismo prefijo
- Filtros: fecha, cuenta y categoría

## Validación

Antes de introducir un nuevo patrón de fetching:

1. Confirmar que no duplica una query existente.
2. Confirmar que la invalidación impacta la vista correcta.
3. Verificar que la UI no quede desincronizada después de una mutación.
