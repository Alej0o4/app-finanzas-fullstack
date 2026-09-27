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
- Filtra categorías por tipo de transacción, o por todas (toggle "+ Mostrar todas las
  categorías", Fase 31 F3) vía `lib/categoryVisibility.ts` — ver la misma regla documentada
  en `EditTransactionModal` arriba, compartida entre los dos modales.
- `noValidate` con errores de campo por debajo de cada input (Fase 31 F2/H13) — antes
  dependía de los globos nativos del navegador, a diferencia del resto de la app; el monto
  se valida con `lib/validateAmount.ts`.
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
- Validación por campo con foco automático en el primer error (mismo patrón que `TransactionModal`),
  con `lib/validateAmount.ts` para el monto (Fase 31 F2).
- **Toggle de categorías "+ Mostrar todas las categorías / ← Solo del tipo"** (Fase 31 F3,
  igual que `TransactionModal`): arranca **activado** si la categoría original de la
  transacción es de la otra naturaleza que su tipo (un reembolso — un ingreso en una
  categoría de gasto). La lista visible sale de `lib/categoryVisibility.ts`
  (`getVisibleCategories`), compartida con `TransactionModal` — categorías ocultas
  ("oculta para mí", Fase 18) no se listan salvo la categoría original de la transacción, que
  siempre aparece (así el `<select>` nunca arranca en blanco). Si al cambiar el tipo o al
  apagar el toggle la categoría elegida deja de estar entre las opciones visibles, se resetea
  a "Selecciona…" y el error de campo pide elegir una — lo que se ve en el `<select>` es
  siempre lo que se envía.

Reglas:

- No duplicar este formulario en otras pantallas.
- No duplicar la regla de categorías visibles — usar `getVisibleCategories`.

### `components/charts/BudgetRing.tsx`

Responsabilidad:

- Pintar el estado de ejecución de un presupuesto.

Props principales:

- `categoryName`
- `budgetAmount`
- `spentAmount`
- `percentage` — **Fase 31 F9 (Q12, QA-012)**: el porcentaje real que ya calcula el backend
  (`BudgetProgress.percentage`). El componente ya NO lo recalcula con `spent / limit` — regla
  de `CLAUDE.md` de no recomputar agregados del backend en el cliente. Los dos consumidores
  (`app/(dashboard)/page.tsx` y `app/(dashboard)/accounts/[id]/page.tsx`) lo pasan.

Comportamiento:

- El texto muestra `percentage` redondeado a entero, **sin tope** (106%, no 100%) — el mismo
  número que la notificación de presupuesto excedido.
- El anillo se dibuja en dos vueltas superpuestas (Fase 31 F9, Q16): la primera es
  `min(percentage, 100)`, con los colores de siempre (primario, warning desde 80%, danger
  desde 100%); la segunda, solo cuando `percentage > 100`, es `min(percentage − 100, 100)` —
  el exceso, dibujado en el token `--color-danger-strong` (ver `UI_SYSTEM.md`). Tope visual en
  200% (una segunda vuelta completa); el texto sigue mostrando el valor real sin tope.
- Usa colores semánticos para estados normal, warning y danger.

Reglas:

- No pasarle cadenas sin convertir a número.
- No depender de variables CSS dentro de SVG si el render es inestable; preferir colores compatibles con SVG/Recharts.
- No recalcular `percentage` en el componente ni en los consumidores — viene del backend.

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

### `components/AnalyticsSummary.tsx`

Responsabilidad:

- Pintar la tarjeta de KPIs de Analítica (Ingresos / Gastos / Balance Neto).

Props principales:

- `totalIncome: number`
- `totalExpense: number`
- `net: number` — **Fase 30 F3 (H3)**: neto del período (ingresos − gastos), calculado por el backend. El frontend ya no resta; usa este valor directamente.
- `currency?: string` — Fase 29 §F7: moneda en la que vienen los montos. Si se omite, cae a la preferida global (`config.currency`); la página siempre pasa la moneda efectiva de la vista, para que una cuenta USD no se formatee como COP.

Comportamiento:

- Calcula `color` del balance neto en función de `net` (no de `totalIncome - totalExpense`).
- Usa `formatCurrency` con la moneda activa.

Reglas:

- No recalcular totales en el componente: el backend es la fuente de verdad.

### `components/CategoryDonutChart.tsx`

Responsabilidad:

- Pintar la distribución por categorías (dona de Recharts) con controles de tipo (gastos/ingresos), modo (bruto/neto), referencia (% de gastos vs % del ingreso total) y categorías ocultas.

Props principales:

- `data: CategoryDistributionItem[] | undefined`
- `categoryType`, `onCategoryTypeChange`
- `netMode`, `onNetModeChange`
- `hiddenCategories`, `onHiddenCategoriesChange`
- `referenceMode`, `onReferenceModeChange`
- `totalIncomeForPeriod: number` — **Fase 19 §19.3.4, actualizado Fase 30 F3**: ingreso total del período. Ahora viene de `cashflow-series.total_income` (calculado por el backend), no se suma en el cliente. Denominador cuando `referenceMode === 'income-total'`.
- `currency?: string` — Fase 29 §F7: moneda de los montos (tooltip y leyenda).

Comportamiento:

- Calcula porcentaje de cada categoría contra el denominador correcto (subtotal de gastos o `totalIncomeForPeriod`).
- `hiddenCategories` filtra visualmente; el porcentaje de items visibles NO se re-normaliza si se usa referencia al ingreso total.

Reglas:

- No sumar `totalIncomeForPeriod` en el cliente: viene del backend.

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
- Las fechas y rótulos se arman con los helpers de `lib/dateRanges.ts` (`formatMonthLabel`, `formatMonthName`, `formatMonthParam`, `formatPeriodLabel`, `shiftMonth`, `shiftPeriodRef`), no inline en la página.

## Componentes por dominio

### Dashboard

- Usa `BudgetRing`.
- Puede incluir bloques de métricas y transacciones recientes.
- Debe delegar el formulario de creación a `TransactionModal`.
- Navega por mes con `PeriodNavigator` (`?month=YYYY-MM`, Fase 29 §F5). Dos secciones viven en componente propio porque arrastran su propia query y sus estados de carga/error/vacío:
  - `components/charts/CategoryBreakdownSection.tsx` — "Gastos por Categoría" del mes visible: chips de moneda (`SegmentedControl`, solo con más de una moneda) sobre `CategoryBreakdownBars`. Props: `monthKey?` (segmento de mes de la query key, `undefined` en el mes en curso), `range` (rango ISO del mes; en el mes en curso termina al fin del día UTC de hoy), `currencyOptions`, `preferredCurrency`, `emptyMessage?`. La moneda elegida es estado local (`string | null`, donde `null` = "la preferida", así sigue a `preferredCurrency` si llega o cambia después del primer render); si no tiene gastos en el mes visible, se vuelve a la preferida en el render (sin `useEffect`).
  - `components/transactions/RecentTransactionsSection.tsx` — "Últimas 5 de {mes}" vía `useTransactions` (key `transactions`, así que editar o borrar también la refresca). Props: `range`, `monthName` (en minúscula), `viewAllHref` (link a `/transactions` filtrado al mes, de `monthTransactionsHref`). Formatea cada monto en la moneda de la transacción, no en la preferida.
- El padre arma el rango y las opciones de moneda; las secciones solo los consumen.

### Analytics

- Usa Recharts directamente.
- La lógica de colores para categorías debe mantenerse local a la vista mientras no exista un componente compartido.
- Presets de período y chips de moneda con `SegmentedControl`; navegación del período con `PeriodNavigator` (salvo en `custom`, que no tiene período de calendario que navegar) — Fase 29 §F6.
- `AnalyticsSummary`, `CashflowChart` y `CategoryDonutChart` reciben `currency?` (Fase 29 §F7): la moneda en que se formatean sus montos. Si se omite, caen a la preferida global (`config.currency`); la página siempre pasa la moneda efectiva de la vista, para que una cuenta USD no se formatee como COP.
- **`CashflowChart` y la opción `integer` de `formatCurrency`** (Fase 31 F7, Q8, QA-007):
  `lib/formatters.ts` muestra decimales por default (COP con mínimo 0/máximo 2; el resto con
  2 siempre — antes todo se redondeaba a la unidad, incluido USD). `CashflowChart` es el único
  consumidor de `formatCurrency(amount, currency, locale, { integer: true })`: lo usa el
  `tickFormatter` del eje Y, el cálculo de `yAxisWidth` y el `formatter` de los `LabelList`
  sobre las barras, para que ejes y etiquetas sigan compactos y sin decimales. El tooltip del
  mismo gráfico (`formatAmount`, sin la opción) sí muestra decimales, como el resto de la app.

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
