# Guía de Componentes

## Objetivo

Este documento resume los componentes reutilizables del frontend y las reglas para extenderlos sin romper consistencia visual o de datos.

## Principio general

Antes de crear un nuevo componente, revisar si ya existe una pieza reutilizable para:

- navegación;
- modales;
- gráficos;
- layout de listas;
- formularios de alta y edición.

## Componentes principales

### `components/QueryProvider.tsx`

Responsabilidad:

- Proveer `QueryClientProvider` a toda la app.

Cuándo tocarlo:

- Solo si cambian las reglas globales de caché o refetch.

### `components/Sidebar.tsx`

Responsabilidad:

- Navegación principal del dashboard.
- Toggle de colapso/expansión.
- Resaltar ruta activa.

Reglas:

- No meter lógica de negocio en el sidebar.
- Mantener el mapa de rutas alineado con el dashboard real.

### `components/modals/TransactionModal.tsx`

Responsabilidad:

- Crear transacciones desde un modal reutilizable.

Props principales:

- `isOpen`
- `onClose`
- `onSuccess?`
- `defaultType?`
- `title?`

Comportamiento:

- Carga cuentas y categorías solo cuando el modal está abierto.
- Filtra categorías por tipo de transacción.
- Invalida las queries afectadas al guardar.

Reglas:

- No duplicar este formulario en otras pantallas.
- Si se modifica el payload, actualizar también la documentación de API.

### `components/modals/EditTransactionModal.tsx`

Responsabilidad:

- Editar una transacción existente (contraparte de `TransactionModal`, que solo crea).

Props principales:

- `isOpen`, `transaction`, `accounts`, `categories`, `isSaving`, `onClose`, `onSave`.

Comportamiento:

- Extraído de `transactions/page.tsx` en Fase 27 (`docs/specs/fase_27_spec.md`) — antes vivía
  inline en la página.
- Owns el estado del formulario internamente; el padre lo monta con `key={editSessionKey}`
  (incrementado en cada apertura) para forzar un reset limpio en vez de un `useEffect`
  sincronizando props → estado.
- Validación por campo con foco automático en el primer error (mismo patrón que `TransactionModal`).

Reglas:

- No duplicar este formulario en otras pantallas.

### `components/charts/BudgetRing.tsx`

Responsabilidad:

- Pintar el estado de ejecución de un presupuesto.

Props principales:

- `categoryName`
- `budgetAmount`
- `spentAmount`

Comportamiento:

- Calcula porcentaje consumido.
- Limita el porcentaje entre 0 y 100.
- Usa colores semánticos para estados normal, warning y danger.

Reglas:

- No pasarle cadenas sin convertir a número.
- No depender de variables CSS dentro de SVG si el render es inestable; preferir colores compatibles con SVG/Recharts.

### `components/ui/Switch.tsx`

Responsabilidad:

- Toggle booleano accesible: un `<input type="checkbox" role="switch">` estilizado (Fase 14 §14.6.2, primera página de Ajustes).

Props principales:

- `label?: string`
- `description?: string`
- Hereda todas las props estándar de input incluyendo `checked`, `onChange`, `disabled` e `id`.

Reglas:

- Para estados binarios de preferencias (p. ej. `weekly_summary_enabled`), no para acción destructiva.
- Mientras una mutación persiste el cambio, pasar `disabled` para evitar toggles encadenados; si la mutación falla, revertir al valor confirmado por el servidor y mostrar error.

### `components/ui/SegmentedControl.tsx`

Responsabilidad:

- Grupo de opciones excluyentes (Fase 29 §F4). Extraído del selector de período inline de Analítica y reutilizado por los chips de moneda del dashboard y de Analítica.

Props principales:

- `options: { value: string; label: string }[]`
- `value: string`
- `onChange: (value: string) => void`
- `ariaLabel?: string` — nombre accesible del grupo (`role="group"`).
- `className?: string`

Comportamiento:

- Cada opción es un `<button>` con `aria-pressed`, no un `radiogroup`.
- Es genérico: no sabe de meses ni de monedas. Devuelve `string`; si el caller maneja una unión literal, la conversión se apoya en que las opciones solo salen de su propia lista.

Reglas:

- El estado lo decide el caller (`useQueryParamState`, `useState`…); el control no guarda nada.
- Pasar siempre `ariaLabel`: los chips de moneda y los presets de período se ven idénticos y sin él un lector de pantalla no distingue qué son.
- Con una sola opción no tiene sentido renderizarlo (así lo hacen los chips de moneda del dashboard y de Analítica).

### `components/PeriodNavigator.tsx`

Responsabilidad:

- Navegador `◀ label ▶` de períodos (Fase 29 §F4), compartido por el dashboard (mes) y Analítica (semana, mes o año según el preset).

Props principales:

- `label: string` — rótulo del período visible (p. ej. `"Agosto 2026"`).
- `onPrev`, `onNext: () => void`
- `prevDisabled`, `nextDisabled: boolean`
- `prevLabel?`, `nextLabel?` — `aria-label` de las flechas (default `"Mes anterior"` / `"Mes siguiente"`; Analítica pasa `"Período anterior"` / `"Período siguiente"`).
- `onReset?: () => void` — si se pasa, renderiza el botón de vuelta al período actual.
- `resetLabel?` — texto de ese botón (default `"Volver a este mes"`).

Comportamiento:

- No sabe de fechas: solo dispara handlers. Los límites los calcula el caller (el dashboard, con `first_transaction_month` del summary y el mes en curso; Analítica, con la posición del `ref` en la URL).
- Usa `Button` (`variant="ghost"`, `size="sm"`) y un ancho mínimo en el rótulo para que el control no cambie de ancho al navegar.

Reglas:

- Pasar `onReset` solo cuando el período visible no es el actual; en el período actual el botón no tiene sentido.
- Las fechas y rótulos se arman con los helpers de `lib/dateRanges.ts` (`formatMonthLabel`, `formatPeriodLabel`, `shiftMonth`, `shiftPeriodRef`), no inline en la página.

## Componentes por dominio

### Dashboard

- Usa `BudgetRing`.
- Puede incluir bloques de métricas y transacciones recientes.
- Debe delegar el formulario de creación a `TransactionModal`.
- Navega por mes con `PeriodNavigator` (`?month=YYYY-MM`, Fase 29 §F5). Dos secciones viven en componente propio porque arrastran su propia query y sus estados de carga/error/vacío:
  - `components/charts/CategoryBreakdownSection.tsx` — "Gastos por Categoría" del mes visible: chips de moneda (`SegmentedControl`, solo con más de una moneda) sobre `CategoryBreakdownBars`. Props: `monthKey?` (segmento de mes de la query key, `undefined` en el mes en curso), `range` (rango ISO del mes), `currencyOptions`, `preferredCurrency`, `emptyMessage?`. La moneda elegida es estado local; si no tiene gastos en el mes visible, se vuelve a la preferida en el render (sin `useEffect`).
  - `components/transactions/RecentTransactionsSection.tsx` — "Últimas 5 de {mes}" vía `useTransactions` (key `transactions`, así que editar o borrar también la refresca). Props: `range`, `monthName` (en minúscula), `viewAllHref` (link a `/transactions` filtrado al mes, de `monthTransactionsHref`). Formatea cada monto en la moneda de la transacción, no en la preferida.
- El padre arma el rango y las opciones de moneda; las secciones solo los consumen.

### Analytics

- Usa Recharts directamente.
- La lógica de colores para categorías debe mantenerse local a la vista mientras no exista un componente compartido.
- Presets de período y chips de moneda con `SegmentedControl`; navegación del período con `PeriodNavigator` (salvo en `custom`, que no tiene período de calendario que navegar) — Fase 29 §F6.
- `AnalyticsSummary`, `CashflowChart` y `CategoryDonutChart` reciben `currency?` (Fase 29 §F7): la moneda en que se formatean sus montos. Si se omite, caen a la preferida global (`config.currency`); la página siempre pasa la moneda efectiva de la vista, para que una cuenta USD no se formatee como COP.

### Cuentas y categorías

- Usan tarjetas con lista y acciones flotantes.
- Los modales de creación/edición todavía son específicos de cada pantalla, salvo que se extraigan en una iteración futura.

## Reglas de diseño para nuevos componentes

- Deben usar tokens semánticos del sistema visual.
- Deben recibir props claras y serializables.
- Deben evitar lógica de negocio pesada.
- Si necesitan datos del servidor, hacerlo mediante React Query y no con fetch suelto.

## Convenciones de composición

- Las páginas deben componer componentes pequeños en lugar de contener JSX repetido.
- Los componentes reutilizables deben tener responsabilidad única.
- Los componentes con side effects deben documentar sus invalidaciones de queries.

## Recomendación práctica

Si una UI aparece dos veces, primero pensar en un componente compartido. Si una regla de negocio aparece dos veces, primero pensar en una abstracción de contrato o una query compartida.
