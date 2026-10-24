# Fase 40 — Dashboard navegable y detalle de categoría con presupuesto

**Estado:** especificada el 2026-10-24 tras un `/grilling` con el dueño (Q1–Q16). Marcadores
`[NEEDS CLARIFICATION]` abiertos: **1** (D9, hallazgo de código posterior al grilling). Sin resolverlo
no está lista para implementar.

**Numeración:** esta fase toma el número 40. "Págate primero" pasa a la **41** y el cierre de mes con
puntaje a la **42** (corrida de numeración en `docs/ROADMAP.md` y `docs/VISION_FINANZAS_RESPONSABLES.md`,
paso 9 del orden de ejecución).

## Problem Statement

En el dashboard, "Ejecución de Presupuestos" y "Gastos por Categoría" muestran datos pero no se pueden
presionar. El dueño siente el impulso de tocar una tarjeta o una barra para ver el detalle y no pasa
nada. La vista de detalle de categoría existe, pero no sabe de mes ni de moneda, no muestra el
presupuesto y solo lista las últimas 20 transacciones de todo el historial, así que tampoco responde
"¿cómo voy con este presupuesto y en qué lo gasté?".

## Solution

Las tarjetas de presupuesto y las filas de gasto por categoría del dashboard llevan al detalle de la
categoría, con el mes y la moneda que se estaban viendo. El detalle pasa a ser una vista por mes y
moneda. Si la categoría tiene presupuesto en ese mes, muestra el avance del presupuesto junto a las
transacciones del mes. Si no, solo las transacciones. Todo en la misma URL `/categories/[id]`.

## User Stories

1. Como dueño, quiero presionar una tarjeta de "Ejecución de Presupuestos", para ver el detalle de esa categoría.
2. Como dueño, quiero presionar una fila de "Gastos por Categoría", para ver en qué se fue ese gasto.
3. Como dueño, quiero que el clic respete el mes que estoy viendo en el dashboard, para que las cifras coincidan.
4. Como dueño, quiero que el clic respete la moneda de la tarjeta o del chip activo, para no mezclar COP y USD.
5. Como dueño, quiero que las filas y tarjetas parezcan presionables (cursor, foco, resaltado), para saber que puedo tocarlas.
6. Como dueño, quiero llegar a la fila o tarjeta con el teclado y activarla con Enter, para no depender del mouse.
7. Como dueño, quiero ver en el detalle el avance del presupuesto del mes (porcentaje, gastado, límite, restante), para saber cuánto me queda.
8. Como dueño, quiero ver "Excedido por X" cuando me pasé del 100%, para notarlo sin calcular.
9. Como dueño, quiero ver el presupuesto y las transacciones lado a lado en escritorio, para relacionarlos de un vistazo.
10. Como dueño, quiero que en móvil el presupuesto quede arriba y las transacciones debajo, para no hacer scroll horizontal.
11. Como dueño, quiero ver todas las transacciones del mes y la moneda de esa categoría, no solo las últimas 20.
12. Como dueño, quiero "Cargar más" cuando el mes tiene muchas transacciones, para no cargar todo de golpe.
13. Como dueño, quiero ver el total del mes de la categoría, para cotejarlo con la barra del presupuesto.
14. Como dueño, quiero cambiar de mes dentro del detalle con el mismo selector del dashboard, para comparar meses.
15. Como dueño, quiero que cambiar de mes actualice la URL, para que el botón atrás y los enlaces funcionen.
16. Como dueño, quiero que un `?month=` inválido o futuro caiga al mes actual, para que la vista nunca quede rota.
17. Como dueño, quiero cambiar entre COP y USD con un chip cuando la categoría tiene datos en ambas, para ver cada presupuesto por separado.
18. Como dueño, quiero que sin `?currency=` la vista elija la moneda del presupuesto, o la principal si no hay presupuesto.
19. Como dueño, quiero que una categoría sin presupuesto ese mes muestre solo el total y los movimientos, para no ver un bloque vacío.
20. Como dueño, quiero una línea "Sin presupuesto este mes" con un enlace a `/budgets`, para saber dónde crearlo.
21. Como dueño, quiero seguir editando y borrando transacciones desde esta vista, y que el avance del presupuesto se actualice.
22. Como dueño, quiero un enlace "Ver en Movimientos" filtrado por categoría y mes, para ver el detalle completo.
23. Como dueño, quiero que entrar desde la página de Categorías abra el mes actual, para tener un punto de partida claro.
24. Como dueño, quiero que si falla la carga haya un estado de error con "Reintentar", como en el resto de la app.

## Implementation Decisions

**Decisiones del grilling (confirmadas por el dueño, 2026-10-24)**

- **D1 — Una sola vista.** `/categories/[id]` cubre los dos casos. No hay ruta nueva. Con presupuesto en el mes y la moneda, aparece el bloque de presupuesto; sin presupuesto, solo la lista.
- **D2 — Mes por URL.** `?month=YYYY-MM`. Sin parámetro, mes actual. Inválido o futuro, mes actual (misma regla que el dashboard; no hay meses futuros). El progreso del presupuesto, el total y la lista salen del mismo mes.
- **D3 — Moneda por URL.** `?currency=XXX`. Sin parámetro o inválida: la moneda del presupuesto de la categoría ese mes; si no hay, la moneda principal del usuario. El chip COP/USD aparece solo si la categoría tiene movimientos o presupuesto en más de una moneda ese mes.
- **D4 — Transacciones.** Todas las del mes y la moneda, "Cargar más" de 20 en 20, con editar y borrar como hoy. Se muestra el total del mes.
- **D5 — Clics.** Tarjetas de presupuesto y filas de gasto por categoría van al mismo destino: `/categories/[id]?month=YYYY-MM&currency=XXX`, con el mes visible y la moneda de la tarjeta o del chip activo. La fila completa es el elemento clicable (enlace real, con foco por teclado y cursor), no solo el texto.
- **D6 — Sin presupuesto.** Solo total del mes y movimientos, una línea discreta "Sin presupuesto este mes" con enlace a `/budgets`. No se crea ni edita un presupuesto desde aquí.
- **D7 — Bloque de presupuesto.** Anillo con porcentaje, gastado, límite y restante; si pasa del 100%, "Excedido por X" con el color de alerta ya usado en presupuestos. Sin proyecciones ni ritmo diario. Reutiliza `BudgetRing`; el porcentaje es el del backend (`BudgetProgress.percentage`), nunca se recalcula en el cliente.
- **D8 — Diseño.** Escritorio: presupuesto a la izquierda, transacciones a la derecha. Móvil: apilado, presupuesto arriba. Sin presupuesto: la lista ocupa todo el ancho.
- **D9 — Backend: `category_id` en `BudgetProgress`.** Campo aditivo en el schema y en `GET /dashboard/budgets-progress`; sin migración. La vista pide `budgets-progress?year=&month=` y busca por `category_id` y moneda. Sin endpoint nuevo para esto.
- **D10 — Selector de mes compartido.** El selector de mes y el validador de `?month=` hoy viven dentro de `app/(dashboard)/page.tsx`. Se extraen a un componente y un hook compartidos, sin cambiar el comportamiento del dashboard. Es el único refactor de la fase.
- **D11 — Historial.** Se navega mes a mes con el selector. El enlace "Ver todos los movimientos (N)" pasa a "Ver en Movimientos", hacia `/transactions` filtrado por la categoría y el mes (`monthTransactionsHref` + `category_id`). No hay modo "todo el historial".
- **D12 — Docs de contrato.** Se actualizan `backend/docs/API_REFERENCE.md` y `frontend/docs/API_CONTRACT.md` en el mismo cambio, y `frontend/docs/STATE_AND_FETCHING.md` con las query keys nuevas.

**Hallazgos de código posteriores al grilling (a revisar por el dueño)**

- **D13 — Filtro `currency` en `GET /transactions/`.** Hoy ese endpoint filtra por `category_id`, `start_date` y `end_date`, **pero no por moneda**. Filtrar en el cliente rompería la paginación y `total`. Se agrega un parámetro opcional `currency` (aditivo, sin migración; `Transaction.currency` ya existe). Esto amplía D9: el backend no se queda en solo `category_id`.
- **D14 — Total del mes desde el backend.** `PaginatedResponse` solo trae el conteo (`total: int`), no una suma, y el frontend no debe sumar (regla del repo). El total del mes y la moneda sale de `GET /dashboard/category-distribution` (`start_date`/`end_date` del mes, `currency`, `type=expense`), tomando la fila de esa categoría. Se reutiliza un endpoint existente, sin campo nuevo. Cae a `0` si la categoría no tiene fila.
- **D15 — Tipo de la categoría.** El total y el presupuesto aplican a categorías de gasto. Si la categoría es de ingreso, la vista no muestra el bloque de presupuesto y el total se pide con `type=income`. `[NEEDS CLARIFICATION: ¿el total del mes de una categoría de ingreso se muestra con ese mismo rótulo, o se oculta el total y se deja solo la lista? Recomendado: mostrarlo como "Total del mes" con `type=income`.]`

## Testing Decisions

- **Qué es un buen test aquí:** solo comportamiento externo: lo que devuelve la API y lo que el dueño ve en el navegador. Nada de pruebas de implementación interna de componentes.
- **Seam principal (único alto):** la API HTTP. Tests de `pytest` con el cliente de FastAPI, igual que `backend/tests/test_zona_horaria.py` y `test_transfers.py`, que ya consultan `budgets-progress` por HTTP.
  - `budgets-progress` devuelve `category_id` y coincide con la categoría del presupuesto.
  - `GET /transactions/` con `currency` filtra bien, respeta `skip`/`limit` y el `total` cuenta solo esa moneda.
  - `category-distribution` del mes y la moneda coincide con la suma de las transacciones listadas (invariante entre el total mostrado y la lista).
- **Seam secundario:** el navegador contra el stack de dev (`:3001`, nunca producción), con seed, vía Playwright, en escritorio y móvil. El repo no tiene tests de componentes. Casos: clic desde tarjeta y desde barra (URL con mes y moneda), categoría sin presupuesto, presupuesto excedido, cambio de mes con el botón atrás, chip de moneda, `?month=` inválido, "Cargar más", y que el dashboard se comporte igual tras extraer el selector.
- **Cierre:** `/run-tests` completo (pytest, ruff, eslint, prettier) antes del PR.

## Out of Scope

- Crear o editar presupuestos desde la vista.
- Proyecciones, ritmo diario y alertas nuevas.
- Meses futuros.
- Modo "todo el historial".
- Gráficos de la categoría en el tiempo.
- Cambios en otras páginas que no sean la extracción del selector de mes.
- Seguridad, auth o permisos (sigue siendo un solo dueño).

## Further Notes

- El anillo de presupuesto del dashboard (`BudgetRing`) se reutiliza tal cual; si hace falta una variante más grande, es una prop, no un componente nuevo.
- Los presupuestos son únicos por (categoría, mes, año, moneda): una categoría puede tener uno en COP y otro en USD el mismo mes. Por eso la moneda forma parte de la clave de búsqueda.
- Invalidación: editar o borrar una transacción desde esta vista ya invalida `budgets.progress` y el desglose por categoría; se mantiene.
- Si al implementar el filtro `currency` de `GET /transactions/` (D13) aparece un cambio de contrato mayor al descrito, se pasa a un cambio de spec, no se improvisa.

## Orden de ejecución

1. [backend] `schemas/dashboard.py` + `api/dashboard.py` — `category_id` en `BudgetProgress` — Decisión D9.
   Depende de: —
2. [backend] [P] `api/transactions.py` — filtro opcional `currency` en `GET /transactions/` — Decisión D13.
   Depende de: —
3. [backend] Tests de HTTP: `category_id`, filtro `currency`, invariante total vs. lista — Decisiones D9, D13, D14.
   Depende de: 1, 2
4. [docs] `backend/docs/API_REFERENCE.md` + `frontend/docs/API_CONTRACT.md` — contrato nuevo — Decisión D12.
   Depende de: 1, 2
5. [frontend] Extraer selector de mes y validador de `?month=` a componente y hook compartidos, sin cambiar el dashboard — Decisión D10.
   Depende de: —
6. [frontend] `types/api.ts` + `lib/queryKeys.ts` + `frontend/docs/STATE_AND_FETCHING.md` — `category_id` en `BudgetProgress` y keys por categoría, mes y moneda — Decisiones D9, D12.
   Depende de: 1
7. [frontend] Dashboard: tarjetas y filas clicables con `?month=` y `?currency=`, foco por teclado — Decisión D5.
   Depende de: 5, 6
8. [frontend] `categories/[id]/page.tsx`: vista por mes y moneda, bloque de presupuesto, total, "Cargar más", chip de moneda, estado sin presupuesto, enlace "Ver en Movimientos" — Decisiones D1–D4, D6–D8, D11, D14, D15.
   Depende de: 2, 5, 6
9. [docs] `docs/ROADMAP.md` + `docs/VISION_FINANZAS_RESPONSABLES.md` — corrida de numeración (41 y 42) — Numeración.
   Depende de: —
10. [verif] Playwright en dev (`:3001`) en escritorio y móvil, y `/run-tests` completo.
    Depende de: 3, 7, 8
11. [docs] Cierre: `docs/CHANGELOG.md`, `docs/ROADMAP.md`, `AGENTS.md`, spec; `/analyze-spec 40 cierre`.
    Depende de: 10

## Decisiones resueltas con el usuario (2026-10-24)

- Q1–Q16 del `/grilling`, todas con la recomendación propuesta (D1–D12 y la numeración).
