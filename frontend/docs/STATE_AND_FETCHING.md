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
- `accounts`
- `categories`
- `budgets`
- `transactions`
- `dashboardSummary`
- `budgets-progress`
- `recent-transactions`
- `dashboard-category-breakdown` (Fase 11 §11.4)
- `accounts-summary` (Fase 11 §11.5)

### Vista específica

- `account`
- `category`
- `transactions`, `account`, `id`
- `transactions`, `category`, `id`
- `analytics-cashflow`
- `analytics-categories`

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

- Inserta el JWT de `localStorage` en cada request.
- Redirige a `/login` ante `401`.

Consecuencias para el estado:

- La sesión expirada se resuelve limpiando el token y dejando que la app vuelva al login.
- No se debe construir otra capa paralela de auth en páginas individuales.

## Hooks compartidos

### `useCurrentUser`

- Consulta `/api/users/me`.
- Debe usarse en vistas autenticadas donde el nombre o identidad del usuario sea relevante.

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

Reglas:

- **Requerido `<Suspense>`**: como consume `useSearchParams`, el componente debe envolverse
  en `<Suspense>` (mismo requisito que login/reset-password). El default export de la página
  es un wrapper que envuelve el contenido real.
- La capa URL comunica strings: los consumidores que esperan uniones literales (p. ej.
  `BarPeriod`) hacen un cast al tipar, p. ej. `const barPeriodTyped = barPeriod as BarPeriod;`.
  Los setters se pasan tal cual (un string cubre la unión).
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

- Cashflow: `analytics-cashflow`
- Categorías: `analytics-categories` (incluye `neto` como cuarto segmento de la key)

### Transacciones

- Feed global: `transactions`
- Feed por cuenta o categoría: queries derivadas con el mismo prefijo
- Filtros: fecha, cuenta y categoría

## Validación

Antes de introducir un nuevo patrón de fetching:

1. Confirmar que no duplica una query existente.
2. Confirmar que la invalidación impacta la vista correcta.
3. Verificar que la UI no quede desincronizada después de una mutación.
