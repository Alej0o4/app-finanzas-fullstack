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
- `dashboardSummary` — con segmento opcional de mes (Fase 29 §F2, ver "Keys con mes" abajo).
- `budgets-progress` — idem.
- `dashboard-category-breakdown` (Fase 11 §11.4) — con segmentos opcionales de mes y moneda
  (Fase 29 §F2).
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

### Keys con mes (Fase 29 §F2)

El dashboard navega por mes (`?month=YYYY-MM`, Fase 29 §F5.1), así que tres factories de
`lib/queryKeys.ts` ganaron argumentos opcionales. **Regla: un segmento opcional se omite del
array cuando no se pasa, nunca queda como `undefined`**:

| Factory                                          | Sin argumentos                     | Con argumentos                                                   |
| ------------------------------------------------ | ---------------------------------- | ---------------------------------------------------------------- |
| `dashboard.summary(month?)`                      | `['dashboardSummary']`             | `['dashboardSummary', 'YYYY-MM']`                                |
| `budgets.progress(month?)`                       | `['budgets-progress']`             | `['budgets-progress', 'YYYY-MM']`                                |
| `dashboard.categoryBreakdown(month?, currency?)` | `['dashboard-category-breakdown']` | `['dashboard-category-breakdown', month \| undefined, currency]` |

- **Por qué:** TanStack compara el prefijo elemento a elemento. Todas las invalidaciones
  existentes llaman a estas factories **sin argumentos**
  (`invalidateQueries({ queryKey: queryKeys.dashboard.summary() })`); con la key sin segmento
  siguen matcheando todos los meses cacheados. Si la factory devolviera
  `['dashboardSummary', undefined]`, dejarían de matchear y capturar una transacción no
  refrescaría el resumen. Por eso ningún call site de invalidación cambió en Fase 29.
- **El mes en curso se cachea con la key sin mes** — la misma de antes de Fase 29. El
  dashboard pasa `month` solo si el mes visible no es el actual (y tampoco envía
  `year`/`month` al backend en ese caso, para no depender del reloj del navegador en el
  cambio de mes).
- `dashboard.categoryBreakdown` es la excepción parcial: la moneda de los chips siempre se
  pasa, así que en el mes en curso la key queda `['dashboard-category-breakdown', undefined,
'COP']`. La invalidación sin argumentos la sigue cubriendo por prefijo.
- El mes entra como `'YYYY-MM'` (segmento estable), nunca como un ISO de instante: un valor
  que cambia en cada render generaría una key nueva por render.

### Navegación de mes sin skeletons (`keepPreviousData`)

Las queries que dependen del mes visible del dashboard usan
`placeholderData: keepPreviousData` (Fase 29 §F5.1): al tocar `◀ ▶` se sigue mostrando el mes
anterior hasta que llega el nuevo, en vez de volver a los skeletons. Aplica a:

- `dashboardSummary` y `budgets-progress` (`app/(dashboard)/page.tsx`);
- `dashboard-category-breakdown` (`components/charts/CategoryBreakdownSection.tsx`);
- "Últimas 5 del mes" vía `useTransactions` (`components/transactions/RecentTransactionsSection.tsx`).

Con `keepPreviousData`, `isLoading` solo es `true` en la carga inicial; si un componente
necesita distinguir "dato del mes anterior en pantalla", leer `isPlaceholderData` (el dashboard
lo usa para que el formulario inline de ingreso mensual, que solo existe en el mes en curso, no
parpadee con el placeholder al navegar hacia un mes pasado).

## Invalidation patterns

### Crear transacción

Cuando se crea una transacción, se invalidan como mínimo:

- `transactions` (cubre también "Últimas 5 del mes" del dashboard, Fase 29)
- `accounts`
- `dashboardSummary`
- `budgets-progress`
- `analytics-cashflow`, `analytics-categories`
- `dashboard-category-breakdown`, `accounts-summary` (Fase 11 — la card de flujo mensual y
  el desglose por categoría del dashboard, y el total de `/accounts`, dependen de datos
  agregados de transacciones)

### Editar transacción

Después de editar:

- `transactions` (cubre también "Últimas 5 del mes" del dashboard, Fase 29)
- vista específica por cuenta o categoría si aplica
- `accounts`
- `dashboardSummary`
- `budgets-progress`
- `analytics-cashflow`, `analytics-categories`
- `dashboard-category-breakdown`, `accounts-summary`

### Eliminar transacción

Después de borrar:

- `transactions` (cubre también "Últimas 5 del mes" del dashboard, Fase 29)
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
- `useTransactions(params, options?)` — `GET /transactions/` → `PaginatedResponse<Transaction>`.
  `params` es el mismo objeto de filtros que armaba `transactions/page.tsx` (skip, limit,
  account_id, category_id, start_date, end_date); se pasa tal cual a
  `queryKeys.transactions.filtered(params)`. Como `params` entra en la key, el caller lo
  memoiza (`useMemo`) para que no cambie de identidad en cada render.
  - Fase 29 §F2: segundo argumento opcional con opciones de `useQuery` (todo salvo
    `queryKey`/`queryFn`, que fija el hook) — lo usa el dashboard para
    `placeholderData: keepPreviousData`. Los callers sin opciones quedan idénticos.
  - Consumidores: `transactions/page.tsx` y `RecentTransactionsSection` del dashboard
    (`{ limit: 5, start_date, end_date }` del mes visible).

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
- `dashboard` (Fase 29 §F5.1): `month` (`'YYYY-MM'`, default `''` = mes en curso; un mes
  futuro o inválido cae al actual). El mes en curso nunca se escribe en la URL.
- `analytics`: `period` (`'month'`), `ref` (`''` = período en curso; Fase 29 §F6), `start`/`end`
  (solo con `period=custom`), `currency` (`''` = moneda preferida; Fase 29 §F6.2), `account`
  (`'all'`), `series` (`'both'`), `type` (`'expense'`), `neto` (`'false'`), `reference`
  (`'expense-total'`). Los cambios que tocan varios params a la vez (preset + `ref`, cuenta +
  `currency`) van por `useQueryParamsBatch` en un solo `router.replace`: dos setters de
  `useQueryParamState` seguidos en el mismo handler se pisan.

## Patrones recomendados

- Mantener `queryKey` estables y predecibles.
- No mezclar estado remoto con estado de formulario.
- Invalidar por dominio, no por componente.
- En filtros de listas, convertir controles de UI en parámetros de query.
- Si una query depende de un modal abierto, usar `enabled: isOpen`.

## Casos específicos actuales

### Dashboard

Todas las queries siguen al mes visible (`?month=`) y usan `keepPreviousData` (ver "Keys con
mes" arriba).

- Resumen (incluye `monthly_flow_balance`, Fase 11 §11.3): `dashboardSummary` / `dashboardSummary, mes`
- Progreso de presupuestos: `budgets-progress` / `budgets-progress, mes`
- Últimas 5 del mes (Fase 29 §F5.5): `useTransactions({ limit: 5, start_date, end_date })` →
  `transactions, params`. Reemplaza a la antigua key `recent-transactions`
  (`queryKeys.dashboard.recentTransactions()`), que se retiró junto con sus 3 invalidaciones
  (`TransactionModal`, `TransactionCaptureForm`, `OnboardingIncomeStep`). Esa key solo se
  invalidaba al crear, así que editar o borrar dejaba la lista vieja; ahora la cubre la
  invalidación de `transactions` que ya hacen todas las mutaciones.
- Desglose por categoría del mes (Fase 11 §11.4): `dashboard-category-breakdown, mes?, moneda`
  — la moneda la eligen los chips de `CategoryBreakdownSection` (Fase 29 §F5.4).

### Analytics

- Cashflow: `analytics-cashflow` (con segmentos opcionales `accountId`/`currency`, ver
  "Vista específica" arriba)
- Categorías: `analytics-categories` (con `neto` y los mismos segmentos opcionales de cuenta/moneda)
- El rango de fechas de la key sale de `buildDateRange(period, ref, start, end, now)`
  (`lib/dateRanges.ts`) con un `now` congelado al montar (`useMemo`): el `end_date` del período
  en curso va dentro de la key, y un `now` nuevo por render daría una key nueva por render.
- `enabled` (Fase 29 §F6.2): las dos queries esperan a que haya moneda efectiva **y**, si la URL
  trae `?currency=`, a que `/accounts/` resuelva (o falle). Sin eso, mientras las cuentas cargan
  las opciones de moneda solo conocen la preferida, la moneda efectiva caería a la preferida y
  se haría un fetch en una moneda que no es la pedida, seguido de un segundo fetch correcto.

### Transacciones

- Feed global: `transactions`
- Feed por cuenta o categoría: queries derivadas con el mismo prefijo
- Filtros: fecha, cuenta y categoría

## Validación

Antes de introducir un nuevo patrón de fetching:

1. Confirmar que no duplica una query existente.
2. Confirmar que la invalidación impacta la vista correcta.
3. Verificar que la UI no quede desincronizada después de una mutación.
