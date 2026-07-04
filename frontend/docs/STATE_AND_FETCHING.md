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

### Editar transacción

Después de editar:

- `transactions`
- vista específica por cuenta o categoría si aplica
- `accounts`
- `dashboardSummary`
- `budgets-progress`

### Eliminar transacción

Después de borrar:

- `transactions`
- `accounts`
- `dashboardSummary`
- `budgets-progress`

### Crear/editar/eliminar cuenta

Después de mutar una cuenta:

- `accounts`
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
- filtros de pantalla;
- selección temporal de fecha, cuenta o categoría.

Ejemplos actuales:

- `TransactionModal`
- filtros del feed de transacciones
- formularios de cuentas, categorías y presupuestos
- edición inline en detalles por cuenta y categoría

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

## Patrones recomendados

- Mantener `queryKey` estables y predecibles.
- No mezclar estado remoto con estado de formulario.
- Invalidar por dominio, no por componente.
- En filtros de listas, convertir controles de UI en parámetros de query.
- Si una query depende de un modal abierto, usar `enabled: isOpen`.

## Casos específicos actuales

### Dashboard

- Resumen: `dashboardSummary`
- Progreso de presupuestos: `budgets-progress`
- Transacciones recientes: `recent-transactions`

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
