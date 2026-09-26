# Spec — Fase 29: Navegación por mes en el dashboard y selector de moneda

> Sintetiza el `/grilling` del 2026-09-26, registrado en `docs/ROADMAP.md` §"Fase 29 — en
> definición" (decisiones **Q1–Q16** y 6 supuestos aceptados). Esas decisiones las tomó el dueño
> y esta spec no las reabre. Las cita por su número y las baja a decisiones implementables
> **B** (backend), **F** (frontend), **T** (testing) y **D** (docs), con la misma convención que
> `fase_26_spec.md`.
>
> Antes de escribirla, un `software-architect` contrastó el grilling con el código real
> (2026-09-26). Encontró dos contradicciones entre decisiones Q y el código, y un bug que bloquea
> Q5/Q14. Están en "Hallazgos de exploración". Las dos que necesitaban al dueño (**B5**, **B7**)
> se resolvieron el mismo día, ver "Decisiones resueltas con el usuario".
>
> **No implementa nada.** Solo se agregó este archivo y el pointer en `docs/ROADMAP.md`.

**Estado:** spec escrita el 2026-09-26. Los 2 marcadores `[NEEDS CLARIFICATION]` (B5, B7) se
resolvieron con el dueño ese mismo día. **Implementada y cerrada el 2026-09-26**
(`/analyze-spec 29 cierre` sin hallazgos CRÍTICO/ALTO pendientes). Desviaciones y fixes del
`/code-review` registrados en la entrada de `docs/CHANGELOG.md`.

---

## Problem Statement

El dashboard solo muestra el mes en curso. No hay forma de mirar cuánto gasté en agosto, cómo
cerró julio o qué presupuestos tenía hace dos meses sin ir a Analítica y armar un rango a mano.
Además, Analítica no tiene cómo moverse al período anterior: "semana", "mes" y "año" siempre
terminan hoy.

La moneda es el segundo problema. "Gastos por categoría" del dashboard solo muestra la moneda
preferida, y la única forma de ver los gastos en USD es cambiar la moneda preferida en la
configuración. Analítica deriva la moneda de la cuenta elegida y, con "Todas las cuentas", se
limita a avisar que las cuentas en otra moneda "no están incluidas".

A esto se suman tres bugs de presentación en la misma superficie. "Transacciones recientes"
formatea montos USD como COP. Las barras por categoría pierden toda transacción fechada el día 1.
Los tres componentes de Analítica formatean con la moneda preferida aunque los montos sean de otra.

## Solution

- **Dashboard navegable por mes completo**, con `◀ Agosto 2026 ▶` en el encabezado y el estado en
  `?month=YYYY-MM`. Todo el dashboard sigue al mes elegido: tarjeta de ingresos/gastos/balance,
  presupuestos, "Gastos por categoría" y las últimas 5 transacciones **del mes**, con un link
  "Ver todas" a `/transactions` filtrado a ese mes. El mes actual se ve igual que hoy. En los
  meses cerrados, el balance pasa a ser **ingresos reales − gastos reales**, calculado en el
  backend.
- **Analítica navegable**: `◀ ▶` sobre el preset elegido (semana calendario lunes–domingo, mes o
  año), con el período en la URL (`?ref=YYYY-MM-DD`). El rango personalizado sigue como está.
- **Selector de moneda** con chips (`COP | USD`) en "Gastos por categoría" del dashboard y en
  Analítica (solo con "Todas las cuentas"). Queda oculto si hay una sola moneda. Reemplaza el
  aviso de "cuentas en otra moneda no incluidas".
- Se arreglan los tres bugs de formato y de borde de mes, porque viven en las mismas pantallas que
  se modifican.

## User Stories

**Dashboard: navegación por mes**

1. Como dueño, quiero ir al mes anterior con `◀` desde el dashboard, para ver cuánto gasté en
   agosto sin armar un rango a mano.
2. Como dueño, quiero ver el mes elegido como título legible ("Agosto 2026"), para saber siempre
   qué período estoy mirando.
3. Como dueño, quiero que `▶` esté deshabilitado en el mes actual, para no navegar a meses futuros
   sin datos.
4. Como dueño, quiero que `◀` se deshabilite en el mes de mi primera transacción, para no navegar
   a meses vacíos anteriores a que empezara a usar Oikos.
5. Como dueño, quiero un botón "Volver a este mes" cuando estoy en un mes pasado, para regresar
   sin pulsar `▶` varias veces.
6. Como dueño, quiero que el mes elegido quede en la URL (`?month=2026-08`), para recargar o
   compartir el enlace y caer en el mismo mes.
7. Como dueño, quiero que en el mes actual la URL quede limpia (sin `?month=`), para que el
   dashboard de siempre sea exactamente el mismo que hoy.
8. Como dueño, quiero que un `?month=` inválido o futuro me muestre el mes actual en vez de romper
   la página, para que un enlace viejo o mal escrito no me deje en un error.
9. Como dueño, quiero que al navegar entre meses no vuelvan a aparecer los skeletons de toda la
   página, para que ir y volver se sienta inmediato.

**Dashboard: tarjeta de flujo**

10. Como dueño, quiero que en el mes actual la tarjeta siga mostrando "Te quedan…" (ingreso
    declarado − gastos), para no perder la vista de flujo que ya uso a diario.
11. Como dueño, quiero que en un mes cerrado la tarjeta muestre el "Balance de agosto" como
    ingresos reales registrados − gastos reales, para saber si ese mes gasté más de lo que entró.
12. Como dueño, quiero que en un mes cerrado el balance nunca aparezca vacío, aunque no tenga
    ingreso mensual declarado, para que el histórico siempre tenga un número.
13. Como dueño, quiero ver los ingresos y gastos rotulados con el nombre del mes ("Gastos de
    agosto"), para no confundirlos con los del mes actual.
14. Como dueño, quiero que el formulario de ingreso mensual (Fase 11) solo aparezca en el mes
    actual, para no editar por error mi ingreso declarado mirando un mes pasado.
15. Como dueño, quiero que el banner de onboarding solo aparezca en el mes actual, para que no
    aparezca al revisar el histórico.

**Dashboard: presupuestos**

16. Como dueño, quiero ver los presupuestos que tenía en un mes pasado con su gasto real de ese
    mes, para saber cuáles cumplí.
17. Como dueño, quiero ver "No había presupuestos en julio" si ese mes no tuvo presupuestos, en
    vez de una lista vacía sin explicación.
18. Como dueño, quiero que mirar un mes pasado nunca cree presupuestos en ese mes, para que el
    histórico refleje lo que existió y no lo que la plantilla recurrente habría generado.
19. Como dueño, quiero que los presupuestos recurrentes del mes actual se sigan generando solos al
    abrir el dashboard, como hasta ahora.

**Dashboard: gastos por categoría y moneda**

20. Como dueño, quiero que las barras de "Gastos por categoría" muestren el mes elegido, para
    comparar en qué gasté mes a mes.
21. Como dueño con gastos en COP y USD, quiero chips `COP | USD` en el encabezado de la sección,
    para ver las barras en USD sin cambiar mi moneda preferida.
22. Como dueño que solo gasta en una moneda, quiero que los chips no aparezcan, para no tener un
    control inútil en pantalla.
23. Como dueño, quiero que los chips arranquen en mi moneda preferida, para que el dashboard se vea
    como siempre al abrirlo.
24. Como dueño, quiero que si elegí USD y me muevo a un mes sin gastos en USD la selección vuelva a
    la preferida, para no ver una sección vacía sin entender por qué.
25. Como dueño, quiero que una transacción del día 1 del mes aparezca en las barras, para que las
    barras cuadren con el total de la tarjeta.

**Dashboard: transacciones**

26. Como dueño, quiero ver las últimas 5 transacciones **del mes elegido**, para revisar qué pasó
    en agosto desde el propio dashboard.
27. Como dueño, quiero un link "Ver todas" que me lleve a `/transactions` ya filtrado a ese mes y
    con el filtro de fecha visiblemente activo, para seguir revisando sin reconfigurar filtros.
28. Como dueño, quiero que cada transacción muestre su monto en su propia moneda, para que un gasto
    de 20 USD no aparezca como "$20 COP".
29. Como dueño, quiero que editar o borrar una transacción actualice la lista del dashboard, para no
    ver datos viejos al volver.
30. Como dueño, quiero que el FAB de captura siga registrando con fecha de hoy aunque esté mirando
    un mes pasado, para que capturar siga siendo un solo toque.
31. Como dueño, quiero que capturar una transacción estando en un mes pasado refresque también el
    mes actual en caché, para verla al volver a este mes.

**Analítica: navegación por período**

32. Como dueño, quiero que "Semana" signifique la semana calendario lunes–domingo ("Esta semana" =
    lunes → hoy), para que las semanas se comparen entre sí.
33. Como dueño, quiero `◀ ▶` en Analítica para ir a la semana, mes o año anterior según el preset
    elegido, para analizar períodos cerrados completos.
34. Como dueño, quiero que los períodos pasados se muestren completos y el actual termine hoy, para
    no mezclar días futuros vacíos.
35. Como dueño, quiero que `▶` esté bloqueado en el período actual, igual que en el dashboard.
36. Como dueño, quiero que el período elegido quede en la URL como una fecha absoluta
    (`?ref=2026-08-01`), para que el enlace siga apuntando al mismo período mañana.
37. Como dueño, quiero que un `?ref=` a mitad de período se normalice al inicio del período, y que
    uno inválido o futuro me muestre el período actual.
38. Como dueño, quiero que al cambiar de preset (semana → mes) se vuelva al período actual, para no
    quedar en un período inesperado.
39. Como dueño, quiero que el rango personalizado siga funcionando igual, sin `◀ ▶`, para
    seguir armando rangos arbitrarios.
40. Como dueño, quiero ver un título del período elegido ("Semana del 18 al 24 de agosto", "Julio
    2026", "2025"), para saber qué rango estoy mirando.

**Analítica: moneda**

41. Como dueño, quiero chips de moneda en Analítica cuando elijo "Todas las cuentas", para ver mis
    gastos e ingresos en USD de todas las cuentas USD juntas.
42. Como dueño, quiero que los chips de Analítica ofrezcan las monedas de mis cuentas, para elegir
    cualquier moneda en la que tenga dinero.
43. Como dueño, quiero que al elegir una cuenta concreta la moneda sea la de esa cuenta y los chips
    desaparezcan, como hoy.
44. Como dueño, quiero que la moneda elegida quede en la URL (`?currency=USD`), como los demás
    filtros de Analítica.
45. Como dueño, quiero que desaparezca el aviso "cuentas en otra moneda no incluidas", porque ahora
    puedo verlas eligiendo la moneda.
46. Como dueño, quiero que los totales, el gráfico de flujo y la dona formateen los montos en la
    moneda que estoy viendo, para no leer USD como COP.

**Contrato y calidad**

47. Como dueño (y cliente de la API vía Atajos), quiero que `GET /dashboard/summary` y
    `/budgets-progress` sin parámetros sigan respondiendo exactamente como hoy, para que nada
    existente se rompa.
48. Como dueño, quiero que pedir un mes futuro, un mes fuera de 1–12 o solo `year` sin `month`
    devuelva un 422 claro, para detectar errores de integración rápido.
49. Como dueño, quiero que la respuesta diga si el balance es "declarado" o "real"
    (`monthly_flow_basis`), para que el front elija el rótulo sin adivinar por fecha local.

## Hallazgos de exploración

Verificados contra el código el 2026-09-26. Corrigen o precisan el "Estado del código relevado"
del ROADMAP.

**H1 — Q4 choca con Q16: el chip USD no aparecería en el caso que motivó la fase.** 🔴
Q4 toma las opciones de los chips de `summary.monthly_expense_by_currency`, pero ese campo solo
suma **cuentas destacadas** (`backend/app/api/dashboard.py:66-100`). Las barras
(`category-distribution`, `dashboard.py:257+`) cuentan todas las cuentas. El filtro de destacadas
no es un caso raro "si hay alguna": todo usuario nace con su cuenta por defecto destacada
(`backend/app/api/users.py:58-65`, `highlighted=True`) y toda cuenta nueva nace sin destacar
(`backend/app/schemas/accounts.py:20`). Una cuenta USD creada después del onboarding no genera su
chip, aunque las barras sí tendrían datos en USD. → Decisión **B7** / **F5.4**, con marcador.

**H2 — Q7 ("nada de filas retroactivas") no se cumple hoy por otra vía.** 🟠
`ensure_recurring_budgets_for_period` tiene tres callers, no uno:
`dashboard.py:144` (mes actual), `backend/app/api/budgets.py:75` (`GET /budgets/?month=&year=`,
el front no lo usa con período) y **`backend/app/core/budget_alerts.py:114`**, dentro de
`evaluate_budget_thresholds_for_category`, llamado con el mes **de la fecha de la transacción**.
Registrar o editar un gasto con fecha de un mes cerrado clona la plantilla recurrente más reciente
en ese mes, aunque la plantilla sea de un mes posterior (`core/budget_recurrence.py:14+`). Puede
además disparar un aviso de umbral de un mes que ya terminó. Con la Fase 29 esto se vuelve
visible: un mes pasado mostraría presupuestos que no existieron. → Decisión **B5**, con marcador.

**H3 — Los componentes de Analítica ignoran la moneda de los datos.** 🔴 Bloquea Q5/Q14.
`components/AnalyticsSummary.tsx`, `components/CashflowChart.tsx` y
`components/CategoryDonutChart.tsx` formatean con `config.currency`, la moneda preferida. Hoy, al
elegir una cuenta USD, ya muestran USD con formato COP, y con el selector de Q14 el bug pasaría al
camino principal. Solo los consume `analytics/page.tsx`. `components/charts/CategoryBreakdownBars.tsx`
ya acepta una prop `currency`, pero el dashboard no se la pasa. → **F7**.

**H4 — El bug de borde de mes (supuesto 1) es frecuente y está en dos sitios.**
`app/(dashboard)/page.tsx:44` arma el inicio de mes en hora local. `TransactionModal` envía la
fecha elegida como `YYYY-MM-DD` y el backend la guarda a las 00:00 UTC, así que **toda**
transacción fechada el día 1 desde el modal queda fuera de las barras del dashboard, no solo las
de 00:00–05:00 UTC. El mismo código está copiado en `app/(dashboard)/accounts/[id]/page.tsx:59`.
→ **F1**.

**H5 — El link "Ver todas" necesita `&preset=custom`.**
`/transactions` lee `?start=&end=` (`transactions/page.tsx:78-79`), pero sin `preset=custom`, la
validación del preset cae en `'all'` (`:60-66`) y el chip "Todo el histórico" queda resaltado con
un rango activo. → **F1**/**F5.5**.

**H6 — Definición concreta de "ingresos reales" (Q8).**
Solo existen los tipos `income`/`expense` (`schemas/transactions.py:11-13`). `transfer` es un
`payment_method`, y la reconciliación de cuentas no crea transacciones, así que no hay nada que
excluir. No hay conversión de moneda en ningún lado: el balance declarado ya se calcula solo en la
moneda preferida (`dashboard.py:115-124`). La transacción semilla del onboarding ("Ingreso
mensual declarado") es un `income` real y cuenta en su mes. El precedente más cercano es
`GET /accounts/{id}/monthly-summary` (`api/accounts.py:120-170`), que ya calcula "ingreso − gasto
real, nunca null" por cuenta. Ese endpoint no pone techo en "hoy" y aquí no se copia su criterio
(ver B1).

**H7 — Las invalidaciones por prefijo solo sobreviven si la key omite el segmento vacío (supuesto 4).**
Unos 15 call sites invalidan con `queryKeys.dashboard.summary()`, `queryKeys.budgets.progress()` y
`queryKeys.dashboard.categoryBreakdown()` sin argumentos. TanStack compara el prefijo elemento a
elemento: si `summary(month?)` devolviera `['dashboardSummary', undefined]`, dejaría de coincidir
con `['dashboardSummary', '2026-08']`. → **F2**.

**H8 — "Transacciones recientes" hoy no se refresca al editar o borrar.**
`queryKeys.dashboard.recentTransactions()` solo se invalida al crear (`TransactionModal`,
`TransactionCaptureForm`, `OnboardingIncomeStep`), como ya documenta
`frontend/docs/STATE_AND_FETCHING.md`. Si "últimas 5 del mes" pasa a `useTransactions`, lo cubre
el `transactions.all()` que ya invalidan todas las mutaciones. → **F2**/**F5.5**.

**H9 — La lógica de rango de mes está copiada en tres sitios del backend.**
`dashboard.py:54-64` (summary, techo `min(fin, ahora)`), `budget_alerts.py:52-53` (techo `ahora`
solo en el mes en curso) y `accounts.py:142-145` (sin techo). Con `?year=&month=`, el summary
necesita la semántica que ya tiene `budget_alerts`. → **B1**.

**H10 — El reloj del dispositivo puede producir un 422 falso.**
El 422 por "mes futuro" (Q11) se evalúa con el reloj del servidor. Si el front siempre mandara el
mes calculado con su propio reloj, un desfase en el cambio de mes daría 422. → **F5.1**: el mes
actual nunca envía `year`/`month`.

**H11 — Mes UTC contra la hora local del dueño (UTC-5).**
Es preexistente y la fase no lo empeora, pero lo vuelve visible. Desde las 19:00 hora Bogotá del
último día, el "mes actual" UTC ya es el siguiente. Además, el resumen semanal usa semanas en
`America/Bogota` (`core/weekly_summary.py`), mientras que la semana calendario de Analítica (Q13)
será UTC, así que los totales pueden diferir en el borde domingo noche/lunes. Se acepta
(supuesto 1) y se registra en `docs/TODO.md` (**D**).

**H12 — Sin impacto:** el scheduler (`run_weekly_summary_job` usa queries propias), las API keys y
Atajos (los parámetros son opcionales) y `accounts/[id]/page.tsx`, que consume
`budgets-progress?currency=` sin mes y queda igual. `summary.balances` no lo consume el front. En
meses pasados sigue siendo el saldo **actual** (stock), no un saldo histórico. Se documenta, no se
cambia.

**H13 — Primer uso de `ValidationError` de dominio.** `app/core/exceptions.py` define
`ValidationError` (422), pero ningún router lo usa todavía. Su nombre choca en lectura con el de
Pydantic. Un `year=abc` lo rechaza FastAPI antes, con otra forma de respuesta
(`{"detail": [ ... ]}`). Hay que proteger `year < 1`, porque `datetime(0, …)` lanza `ValueError`
y terminaría en un 500.

## Implementation Decisions

Toda decisión cita las Q del grilling que implementa. **⚠️ contrato compartido** marca un nombre o
valor del que depende el otro lado: nadie debería asumirlo sin mirar esta sección.

### Backend

**B1 — Helper de período UTC compartido** (Q11, supuesto 1, H9, H13).
Módulo nuevo `backend/app/core/periods.py`. Va en `core/` porque lo importa
`budget_alerts.py`, con el mismo criterio que `budget_recurrence.py`. Tiene dos funciones puras con
`ahora` inyectado:
- `resolver_mes(year, month, ahora) -> (year, month, es_mes_actual)`. Si ambos son `None`, devuelve
  el mes actual UTC. Levanta `ValidationError` (422) si viene uno solo, si `month ∉ 1..12`, si
  `year < 1` o si `(year, month)` es posterior al mes actual.
- `limites_mes_utc(year, month, ahora) -> (inicio, limite)`, en datetimes naive UTC. El techo es
  `ahora` si es el mes en curso y fin de mes 23:59:59 si no lo es. Es la semántica exacta de
  `budget_alerts.py:52-53`.
- Se importa como `ValidationError as DomainValidationError` para no confundirlo con el de
  Pydantic.

**B2 — `GET /dashboard/summary?year=&month=`** (Q6, Q8, Q9, Q11, Q12, Q16, H6).
- Parámetros `year: int | None`, `month: int | None` → `resolver_mes`. Rango vía
  `limites_mes_utc`, que reemplaza el cálculo inline actual.
- **Mes actual:** `monthly_flow_basis = "declared"` y `monthly_flow_balance = monthly_income −
  gasto en moneda preferida`, o `null` sin `monthly_income`. Sin cambios respecto a hoy.
- **Mes pasado:** `monthly_flow_basis = "actual"` y `monthly_flow_balance = ingresos − gastos en
  moneda preferida`, a partir de las mismas filas agrupadas que ya calcula. **Nunca `null`**: sin
  filas vale `0.00`. Las demás monedas se ignoran, como hoy.
- Se mantiene el universo de destacadas (Q16) para ingresos, gastos y balance, en ambos casos.
- `first_transaction_month` es el `min(Transaction.date)` del usuario sobre **todas las cuentas**,
  porque `◀` gobierna la página entera y barras, presupuestos y lista usan todas. Se expresa como
  mes UTC `"YYYY-MM"` o `null` sin transacciones, respetando el filtro global de soft delete. Se
  normaliza con `astimezone(UTC)` si viene con tz (Postgres) y se usa tal cual si viene naive
  (SQLite en tests).
- `balances` no cambia: siempre es el stock actual (H12).

**B3 — `GET /dashboard/budgets-progress?year=&month=`** (Q6, Q7, Q11).
Mismos parámetros y `resolver_mes`. `ensure_recurring_budgets_for_period` se llama **solo si
`es_mes_actual`**. Filtra `Budget.month/year` y calcula el gasto con el período resuelto. El
parámetro `currency` existente se mantiene y se combina con el mes.

**B4 — `spent_por_categoria_y_moneda` usa `limites_mes_utc`** (H9).
Refactor sin cambio de comportamiento de `budget_alerts.py:32-60`, cubierto por los tests
existentes de `test_budget_alerts.py` y `test_dashboard.py`. Si genera fricción, se puede diferir
sin bloquear la fase: el summary usaría B1 y el motor de alertas conservaría su copia.

**B5 — Presupuestos recurrentes retroactivos desde el motor de alertas** (Q7, H2). Resuelta con
el dueño el 2026-09-26. En `evaluate_budget_thresholds_for_category`,
`ensure_recurring_budgets_for_period` se llama solo si `(year, month) >= mes actual UTC`. Así se
conserva la Decisión 13.3.3 (gasto el día 1 del mes nuevo antes de abrir el dashboard) y deja de
clonar plantillas en meses cerrados. Cambio de comportamiento aceptado: un gasto cargado con
fecha atrasada en un mes cerrado ya no crea el presupuesto recurrente de ese mes, así que tampoco
avisa umbrales de un mes pasado. Los presupuestos que sí existían en ese mes siguen evaluándose
como hoy. El guard aplica **solo** al motor de alertas: `GET /budgets/?month=&year=`
(`budgets.py:75`), el otro caller que puede generar meses pasados, queda como está, fuera de
alcance (decisión del dueño, 2026-09-26, tras `/analyze-spec`). El frontend no lo llama con
período.

**B6 — Schema `DashboardSummary`** (Q9, Q12). ⚠️ contrato compartido con F3.

```python
class DashboardSummary(BaseModel):
    balances: list[BalanceByCurrency]                          # sin cambio: stock actual
    monthly_income_by_currency: list[BalanceByCurrency]
    monthly_expense_by_currency: list[BalanceByCurrency]
    monthly_flow_balance: Decimal | None = None                # null solo con basis "declared"
    monthly_flow_basis: Literal["declared", "actual"]          # nuevo
    first_transaction_month: str | None = None                 # nuevo, "YYYY-MM" UTC
    expense_currencies: list[str] = []                         # nuevo (B7)
```

El re-export de `schemas/schemas.py` no cambia, porque la clase conserva el nombre.

**B7 — Monedas que ofrecen los chips del dashboard** (Q4, Q16, H1). ⚠️ contrato compartido con
F5.4. Resuelta con el dueño el 2026-09-26. Se agrega el campo `expense_currencies: string[]` al
summary, con las monedas distintas que tienen gasto (`type == "expense"`) en el mes pedido, sobre
**todas las cuentas** (el mismo universo que las barras que el chip filtra, no solo destacadas),
con la preferida primero y el resto en orden alfabético (mismo `sort_key` que
`monthly_expense_by_currency`). La preferida **no** se agrega si no tiene gasto: el front la suma
a las opciones (F5.4). Cuesta un campo y un `DISTINCT` más.

**Resumen del contrato ⚠️**

| Elemento | Valor |
|---|---|
| Query params de `/dashboard/summary` y `/dashboard/budgets-progress` | `year: int`, `month: int`, opcionales, ambos o ninguno. Ninguno = mes actual UTC |
| 422 de dominio | `{"detail": "<mensaje>"}` si viene solo uno de los dos, `month ∉ 1..12`, `year < 1` o el mes es futuro |
| 422 de FastAPI | `{"detail": [ ... ]}` si `year`/`month` no son enteros |
| `monthly_flow_basis` | `"declared"` (mes actual) \| `"actual"` (mes pasado) |
| `monthly_flow_balance` | `Decimal \| null`; `null` solo es posible con `"declared"` |
| `first_transaction_month` | `"YYYY-MM"` (UTC, todas las cuentas) \| `null` |
| `expense_currencies` (B7) | `string[]`, todas las cuentas, gasto en el mes, preferida primero |
| Semántica de mes | UTC. Mes actual con techo "ahora"; mes pasado hasta fin de mes 23:59:59 |
| `balances` | Siempre el stock actual; no depende del mes pedido |

### Frontend

**F1 — Helpers de fecha UTC** (supuestos 1 y 3, Q6, Q9, Q13, H4, H5). Módulo nuevo
`frontend/lib/dateRanges.ts`:
- Helpers de mes: `currentUtcMonth(now)`, `parseMonthParam(raw)` (devuelve `{year, month}` o
  `null`), `shiftMonth` y `compareMonth`.
- `utcMonthRange(year, month, now)` devuelve `{start_date, end_date}`. El fin es hoy en el mes
  actual y el último día a las 23:59:59.999Z en un mes pasado.
- `monthTransactionsHref(year, month)` →
  `/transactions?start=YYYY-MM-01&end=YYYY-MM-DD&preset=custom`.
- `formatMonthLabel(year, month)` usa `Intl.DateTimeFormat` con `timeZone: 'UTC'` y capitaliza la
  primera letra.
- `buildDateRange` se mueve aquí desde `analytics/page.tsx` y se reescribe como
  `(period, ref, customStart, customEnd, now)`: semana lunes–domingo UTC, mes y año, más
  `normalizeRef(period, ref, now)`.
- Los dos sitios del bug de borde de mes pasan a usar estos helpers:
  `app/(dashboard)/accounts/[id]/page.tsx:59` se corrige en el mismo paso que F1 (paso 5), y
  `app/(dashboard)/page.tsx:44` dentro de F5 (paso 9), porque ese archivo se reescribe ahí.

**F2 — Query keys** (supuesto 4, H7, H8). ⚠️ contrato de caché. En `frontend/lib/queryKeys.ts`,
el segmento opcional **se omite** cuando no se pasa:
- `dashboard.summary(month?)` → `['dashboardSummary']` \| `['dashboardSummary', 'YYYY-MM']`.
- `budgets.progress(month?)` → `['budgets-progress']` \| `['budgets-progress', 'YYYY-MM']`.
- `dashboard.categoryBreakdown(month?, currency?)` solo agrega los argumentos definidos.
- Convención: el mes actual se cachea con la key sin mes, la misma que usa hoy (encaja con H10).
- "Últimas 5 del mes" usa `useTransactions({limit: 5, start_date, end_date})`. Para cumplir el
  `keepPreviousData` de F5.1, `useTransactions` (`lib/hooks/useTransactions.ts`) gana un segundo
  parámetro opcional de opciones de `useQuery` (al menos `placeholderData`). Los callers actuales
  no cambian.
  `dashboard.recentTransactions` se queda sin consumidor, así que se eliminan la factory y sus 3
  invalidaciones (`TransactionModal`, `TransactionCaptureForm`, `OnboardingIncomeStep`).
- Los ~15 call sites de invalidación no cambian.

**F3 — Tipos** (B6). `frontend/types/api.ts`: se agregan `monthly_flow_basis`,
`first_transaction_month` y `expense_currencies`. `types/generated/api.ts` ya
está desactualizado desde antes. Regenerarlo es opcional, porque la convivencia de ambos archivos
es deliberada desde la Fase 16.

**F4 — Componentes compartidos nuevos** (Q2, Q4, Q13, Q14, Q15).
- `components/ui/SegmentedControl.tsx` se extrae del selector de período inline de Analítica. Es
  genérico (`options`, `value`, `onChange`) y usa `aria-pressed`. Tendrá tres usos en esta fase:
  presets de Analítica, chips del dashboard y chips de Analítica. `COMPONENTS_GUIDE.md` pide
  extraer un patrón en cuanto aparece dos veces.
- `components/PeriodNavigator.tsx`: `◀ label ▶`, con `prevDisabled`/`nextDisabled`, `aria-label`
  en las flechas y un `onReset` opcional que muestra "Volver a este mes" / "Volver al período
  actual".

**F5 — Dashboard navegable** (`app/(dashboard)/page.tsx`).
- **F5.1 Estado del mes** (Q6, Q15, supuesto 3, H10). `?month=YYYY-MM` con `useQueryParamState` y
  un validator. Si el mes es futuro o inválido, se usa el mes actual. El mes actual nunca se
  escribe en la URL ni se envía como `year`/`month`. Las queries usan
  `placeholderData: keepPreviousData` para que `◀ ▶` no vuelvan a mostrar los skeletons.
- **F5.2 Navegador** (Q9, Q15). `PeriodNavigator` va en el encabezado de la página, sobre la
  tarjeta principal, y no es sticky. `▶` se deshabilita en el mes actual. `◀` se deshabilita en
  `min(first_transaction_month, mes actual)`, o siempre si `first_transaction_month` es `null`.
  "Volver a este mes" solo aparece fuera del mes actual.
- **F5.3 Tarjeta** (Q8, Q12, Q15). El rótulo sale de `monthly_flow_basis`, no de comparar fechas
  locales: "Te quedan…" con `declared`, "Balance de <mes>" con `actual`. En meses pasados las
  etiquetas son "Ingresos de <mes>" / "Gastos de <mes>". El formulario inline de ingreso mensual y
  el banner de onboarding solo se muestran en el mes actual.
- **F5.4 Presupuestos y barras** (Q4, Q6, Q7, Q16, supuesto 2). Si un mes pasado no tiene
  presupuestos, se muestra "No había presupuestos en <mes>". Las barras reciben el rango del mes
  vía F1 (`utcMonthRange`), que reemplaza el inicio de mes local de `page.tsx:44`. Los chips (`SegmentedControl`) ofrecen las monedas de B7 más la preferida, y se ocultan
  si hay una sola. La selección vive en `useState` con la preferida por defecto. La moneda efectiva
  es `opciones.includes(sel) ? sel : preferida`, así el supuesto 2 se cumple sin `useEffect`. Se
  pasa `currency` a `CategoryBreakdownBars` y el mensaje vacío menciona el mes. Opciones =
  `summary.expense_currencies` ∪ preferida (B7).
- **F5.5 Transacciones** (Q6, Q10, H5, H8). "Últimas 5 de <mes>" con `useTransactions` y un link
  "Ver todas" que usa `monthTransactionsHref`. El monto se formatea con `tx.currency`, no con
  `config.currency` (el bug de `page.tsx:404`).
- FAB y captura no cambian: siempre registran con la fecha de hoy.

**F6 — Analítica** (`app/(dashboard)/analytics/page.tsx`).
- **F6.1 Período** (Q2, Q13, supuesto 3). "Esta semana" pasa a ser lunes → hoy (UTC). El estado va
  en `?ref=YYYY-MM-DD` y se normaliza al inicio del período. `PeriodNavigator` aparece solo con
  semana, mes o año, y su título es dinámico fuera del período actual. Al cambiar de preset se
  limpia `ref`. El personalizado sigue sin navegador.
- **F6.2 Moneda** (Q5, Q14). `?currency=` se valida con `^[A-Z]{3}$` y solo se muestra con "Todas
  las cuentas". Las opciones son las monedas distintas de `accounts` más la preferida, y los chips
  se ocultan si hay una sola. Elegir una cuenta limpia `currency` en el mismo batch de URL. La
  moneda efectiva es `selectedAccount?.currency ?? (param válido ∈ opciones ? param : preferida)`.
  Mientras `accounts` no haya cargado y haya `?currency=` en la URL, las queries quedan en
  `enabled: false`, para no pedir primero la preferida y después la correcta.
- **F6.3** Se eliminan el aviso "cuentas en otra moneda no incluidas" y el sufijo de moneda de la
  opción "Todas las cuentas (COP)".

**F7 — Prop `currency` en los componentes de Analítica** (H3). `AnalyticsSummary`,
`CashflowChart` y `CategoryDonutChart` reciben `currency` y dejan de leer `config.currency` para
formatear montos.

### Docs

**D — Documentación.**
- Contrato de API (obligatorio según `CLAUDE.md`, en el mismo cambio):
  `backend/docs/API_REFERENCE.md` y `frontend/docs/API_CONTRACT.md` documentan los parámetros, los
  422, los campos nuevos y que `balances` es el stock actual. En la sección de generación de
  recurrentes (`API_REFERENCE.md` §`GET /dashboard/budgets-progress` y §notificaciones del motor
  de alertas) se documenta que la dispara además el motor de alertas, pero solo para el mes actual
  o posteriores (B5), y que `budgets-progress` genera solo en el mes actual (B3).
- `backend/docs/BUSINESS_RULES.md`:
  - Las destacadas aplican solo al summary.
  - El progreso de presupuestos se calcula por el período consultado.
  - La unicidad de presupuestos incluye `currency` desde la Fase 17 (ya desactualizado).
- `frontend/docs/STATE_AND_FETCHING.md`: keys con mes y retiro de `recent-transactions`.
- `frontend/docs/COMPONENTS_GUIDE.md`: `SegmentedControl` y `PeriodNavigator`.
- `docs/TODO.md`:
  - Unificar el criterio de destacadas (Q16).
  - Mes UTC contra hora Bogotá y la semana del resumen semanal (H11).
  - Cambiar `preferred_currency` no invalida `dashboardSummary` ni `budgets-progress`
    (`useUserPreferences.ts`; preexistente, mitigado por el `staleTime`).
  - Techo inconsistente en `accounts/{id}/monthly-summary`.
  - `GET /budgets/?month=&year=` sigue generando recurrentes en meses pasados (fuera del guard
    de B5).
- Al cierre: `docs/ROADMAP.md` y `docs/CHANGELOG.md`.

## Testing Decisions

Un buen test aquí prueba comportamiento observable por HTTP (status, forma y valores de la
respuesta, filas creadas o no), no la estructura interna. La excepción son las funciones puras de
B1, que se prueban directamente porque los bordes de calendario son más claros sin HTTP. Los tests
HTTP usan fechas **relativas a `datetime.now(UTC)`**, el patrón existente en
`tests/test_dashboard.py`, y **no** `freeze_time`. `freezegun` está disponible, pero congelar el
reloj invalida el JWT de 15 minutos de `auth_headers` (`tests/conftest.py`). Su único precedente,
`test_weekly_summary.py`, prueba funciones puras.

- **T1** — `tests/test_periods.py` (nuevo): `resolver_mes`/`limites_mes_utc` con `ahora`
  inyectado. Cubre ninguno/uno/ambos parámetros, `month` 0 y 13, `year` 0, mes futuro, el cruce
  diciembre→enero, febrero bisiesto, el mes actual con techo y el mes pasado sin techo.
- **T2** — `test_dashboard.py`, summary: devuelve 422 con solo `year`, solo `month`, `month=13` y
  mes futuro. Sin parámetros se comporta igual que hoy (la suite existente es la regresión). El mes
  actual explícito da lo mismo que sin parámetros, con `basis = "declared"`.
- **T3** — Mes pasado: `basis = "actual"`, `ingreso − gasto` en moneda preferida, otras monedas
  ignoradas y solo destacadas (Q16). Sin transacciones devuelve `"0.00"`, no `null`. Con
  `monthly_income = None` sigue sin ser `null`. Una transacción soft-deleted no cuenta.
- **T4** — `first_transaction_month`: `null` sin transacciones. Gana la más antigua aunque esté en
  una cuenta **no** destacada. La más antigua soft-deleted se ignora.
- **T5** — `budgets-progress` en un mes pasado: con una plantilla recurrente vigente, un mes pasado
  sin filas devuelve `[]` y el conteo de `Budget` no cambia. Un presupuesto que sí existió muestra el
  gasto de ese mes. El mes actual explícito sigue generando los recurrentes.
- **T6** — B5: un gasto con fecha de un mes cerrado no crea filas recurrentes en ese
  mes, y `test_budget_alerts.py` (gasto el día 1 del mes nuevo) sigue en verde.
- **T7** — B7: `expense_currencies` incluye la moneda de una cuenta no destacada y
  excluye una moneda sin gasto en el mes.
- **T8** — `[verif]` Playwright en desktop y en 390×844:
  - Dashboard: `◀ ▶`, los dos límites, "Volver a este mes", chips que aparecen y desaparecen, y el
    link a `/transactions` con el chip de fecha correcto resaltado.
  - Tras capturar una transacción desde un mes pasado, el mes actual aparece refrescado.
  - Analítica: semana, mes y año hacia atrás.
  - `?currency=USD` sobrevive al recargar y los montos USD se formatean como USD.
  - No hay suite de tests de frontend (fuera de alcance desde la Fase 26, `docs/TODO.md`).

Prior art: `tests/test_dashboard.py` (summary, destacadas, progreso con `currency`),
`tests/test_budget_alerts.py` (generación del día 1) y `tests/test_weekly_summary.py` (funciones de
período puras).

## Orden de ejecución

```
1. [backend] app/core/periods.py (nuevo) + tests/test_periods.py — Decisiones B1, T1.
   Depende de: —
2. [backend] app/core/budget_alerts.py: spent_por_categoria_y_moneda usa B1 (+ guard de B5) + tests/test_budget_alerts.py — Decisiones B4, B5, T6.
   Depende de: 1
3. [backend] app/schemas/dashboard.py + app/api/dashboard.py (summary y budgets-progress)
   + tests/test_dashboard.py — Decisiones B2, B3, B6, B7, T2, T3, T4, T5, T7.
   Depende de: 1   (no [P] con 2: T5 depende del cálculo de gasto que toca B4)
4. [docs] API_REFERENCE.md + API_CONTRACT.md + BUSINESS_RULES.md — Decisión D (contrato,
   incluida la generación de recurrentes según B3/B5).
   Depende de: 3
5. [frontend] [P] lib/dateRanges.ts (nuevo) + fix accounts/[id]/page.tsx:59 — Decisión F1.
   Depende de: —
6. [frontend] [P] components/ui/SegmentedControl.tsx + components/PeriodNavigator.tsx — Decisión F4.
   Depende de: —
7. [frontend] [P] AnalyticsSummary.tsx, CashflowChart.tsx, CategoryDonutChart.tsx (prop currency)
   — Decisión F7.
   Depende de: —
8. [frontend] lib/queryKeys.ts + lib/hooks/useTransactions.ts (opciones) + types/api.ts + retiro de recentTransactions en
   TransactionModal / TransactionCaptureForm / OnboardingIncomeStep — Decisiones F2, F3.
   Depende de: 3 (forma del contrato)
9. [frontend] app/(dashboard)/page.tsx — Decisión F5.
   Depende de: 5, 6, 8   (verificable solo con 3 corriendo)
10. [frontend] [P] app/(dashboard)/analytics/page.tsx — Decisión F6.
   Depende de: 5, 6, 7   (no toca archivos de 9; no consume endpoints nuevos)
11. [docs] STATE_AND_FETCHING.md + COMPONENTS_GUIDE.md + TODO.md — Decisión D (front y deuda).
   Depende de: 8, 9, 10
12. [verif] pytest + ruff + pnpm lint + Playwright desktop y 390×844 — Decisión T8.
   Depende de: 2, 3, 9, 10
```

El paso 1 bloquea todo el backend y el 3 fija el contrato del que dependen el 8 y el 9. Analítica
(10) no depende del backend y puede cerrarse antes que el dashboard (9).

## Resumen de archivos tocados

| Decisión | Backend | Frontend |
|---|---|---|
| B1 | `app/core/periods.py` (nuevo) | — |
| B2, B3, B7 | `app/api/dashboard.py` | — |
| B4, B5 | `app/core/budget_alerts.py` | — |
| B6 | `app/schemas/dashboard.py` | — |
| F1 | — | `lib/dateRanges.ts` (nuevo), `app/(dashboard)/accounts/[id]/page.tsx` |
| F2 | — | `lib/queryKeys.ts`, `lib/hooks/useTransactions.ts`, `components/modals/TransactionModal.tsx`, `components/forms/TransactionCaptureForm.tsx`, `components/forms/OnboardingIncomeStep.tsx` |
| F3 | — | `types/api.ts` |
| F4 | — | `components/ui/SegmentedControl.tsx` (nuevo), `components/PeriodNavigator.tsx` (nuevo) |
| F5 | — | `app/(dashboard)/page.tsx`, `components/charts/CategoryBreakdownBars.tsx` (mensaje vacío por mes) |
| F6 | — | `app/(dashboard)/analytics/page.tsx` |
| F7 | — | `components/AnalyticsSummary.tsx`, `components/CashflowChart.tsx`, `components/CategoryDonutChart.tsx` |
| T1–T7 | `tests/test_periods.py` (nuevo), `tests/test_dashboard.py`, `tests/test_budget_alerts.py` | — |
| D | `backend/docs/API_REFERENCE.md`, `backend/docs/BUSINESS_RULES.md` | `frontend/docs/API_CONTRACT.md`, `frontend/docs/STATE_AND_FETCHING.md`, `frontend/docs/COMPONENTS_GUIDE.md`; `docs/TODO.md` |

## Out of Scope

- **Filtro por categoría** en el dashboard o Analítica (Q3): tiene su propia fila en el backlog.
- Presets "últimos 3 / 12 meses" en Analítica; el personalizado ya los cubre.
- Navegación por mes en `/budgets`.
- Unificar el criterio de cuentas destacadas entre `summary` y el resto (Q16 → `docs/TODO.md`).
- Historial de `monthly_income`: sin migración ni modelo nuevo.
- Saldo histórico por cuenta: `balances` sigue siendo el stock actual en cualquier mes.
- Alinear el mes UTC con la hora local, o la semana UTC de Analítica con la del resumen semanal en
  Bogotá (H11 → `docs/TODO.md`).
- Unificar el techo de `accounts/{id}/monthly-summary` con el del summary.
- Extender el guard de B5 a `GET /budgets/?month=&year=`, que sigue pudiendo generar recurrentes
  en meses pasados (→ `docs/TODO.md`).
- Suite de tests de frontend.

## Decisiones resueltas con el usuario (2026-09-26)

Las decisiones Q1–Q16 y los supuestos 1–6 de `docs/ROADMAP.md` §"Fase 29 — en definición" se
resolvieron en el `/grilling` del 2026-09-26 y esta spec las toma como base.

Los dos marcadores `[NEEDS CLARIFICATION]` de la primera versión se resolvieron el mismo día,
aceptando la recomendación en ambos:

1. **B5 — ¿guard contra presupuestos retroactivos en el motor de alertas?** Sí, dentro de la
   Fase 29. El motor de alertas solo genera recurrentes para el mes actual o posteriores. Se acepta
   que un gasto atrasado en un mes cerrado ya no dispare avisos de ese mes.
2. **B7 — ¿de dónde salen las opciones de los chips del dashboard?** De un campo nuevo
   `expense_currencies` en `GET /dashboard/summary`, que cubre todas las cuentas con gasto en el
   mes pedido, más la preferida agregada por el front. Se descarta usar las monedas de las cuentas
   (la opción sin cambio de contrato), porque ofrecería monedas sin gasto en el mes.

`/analyze-spec 29` (2026-09-26) dio 0 hallazgos CRÍTICO/ALTO, 2 MEDIO y 2 BAJO, y el dueño pidió
aplicar los cuatro:

3. **`GET /budgets/?month=&year=` fuera del guard de B5** — queda fuera de alcance y va a
   `docs/TODO.md`.
4. **`useTransactions` acepta opciones de `useQuery`** (F2), para el `keepPreviousData` de F5.1.
5. **El fix de `page.tsx:44` va en F5 (paso 9)**, no en el paso 5.
6. **Los docs de contrato documentan B3/B5** en la sección de generación de recurrentes (paso 4).

## Further Notes

- **Riesgo R1: balance "real" negativo si el sueldo no se registra como transacción** (consecuencia
  directa de Q8). Si el dueño solo declara `monthly_income` y no carga el ingreso como transacción,
  todos los meses pasados muestran un balance igual a −gastos. Conviene revisarlo contra los datos
  reales antes de cerrar la fase. No cambia el diseño.
- **Riesgo R2: tamaño de las páginas.** `page.tsx` tiene 425 líneas y `analytics/page.tsx` 407, y
  las dos crecen. F1 y F4 lo mitigan. Si alguna pasa de ~500 líneas, se extrae la sección de
  recientes o la de chips como subcomponente, para no volver al umbral que motivó la Fase 27.
- **Verificación manual de la invalidación (H7):** estando en un mes pasado, crear una transacción
  y volver al mes actual. Tiene que aparecer sin recargar la página.
- El análisis completo del `software-architect`, con las citas `file:line` de cada hallazgo, se
  resumió en la sección "Hallazgos de exploración". Los números de línea son del 2026-09-26.
