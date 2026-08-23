# Spec — Fase 11: Dashboard de flujo mensual

> Plan de implementación detallado para los 7 ítems de Fase 11 del [ROADMAP](../ROADMAP.md).
> Fuente de verdad de alcance: `docs/ROADMAP.md` (sección "Fase 11 — Dashboard de flujo
> mensual", reescrita el 2026-08-23). Este documento no cambia el alcance ahí definido — lo
> desglosa en tareas ejecutables, con archivos concretos, pasos, dependencias y decisiones de
> diseño.
>
> **No implementa nada.** Es el hand-off para quien vaya a codear (backend-engineer /
> frontend-engineer).

Estado del repo en el momento de escribir esto (2026-08-23): Fase 10 (captura en 3 toques) está
completa y mergeada — `/capture` como ruta principal, `TransactionCaptureForm` compartido,
idempotencia en `POST /transactions`. La Fase 11 del ROADMAP fue **reescrita el mismo día** tras
una auditoría que encontró que su redacción original (sacar Analítica y el editor de Categorías
del sidebar) partía de una premisa no verificada — fricción de navegación asumida, no medida, en
un sidebar de solo 6 ítems. Este spec parte de la versión ya corregida del ROADMAP, y la
exploración de código de abajo confirma (y en algunos puntos precisa más allá de lo que el propio
ROADMAP reescrito detalla) el estado real de cada pieza antes de tocarla.

---

## Hallazgos de exploración que corrigen/precisan el ROADMAP

1. **El sidebar tiene exactamente 6 ítems, confirmado.** `frontend/components/Sidebar.tsx:63-70`,
   `navItems`: Dashboard (`/`), Analítica (`/analytics`), Cuentas (`/accounts`), Transacciones
   (`/transactions`), Presupuestos (`/budgets`), Categorías (`/categories`). Ningún ítem oculto,
   ninguna ruta condicional. Confirma la premisa del ROADMAP reescrito.

2. **El dashboard ya muestra 3 summary cards lado a lado, confirmado.**
   `frontend/app/(dashboard)/page.tsx:68-112`: `Balance Total`, `Ingresos del Mes`, `Gastos del
   Mes`, cada una en un `<SummaryCard>` dentro de un grid de 3 columnas. No hay ningún gráfico de
   analítica (donut, barras de flujo) en esta página — `CashflowChart`, `CategoryDonutChart` y
   `ChartControlsPopover` se importan únicamente en `frontend/app/(dashboard)/analytics/page.tsx`
   (grep confirmado, cero referencias fuera de ese archivo). El objetivo "que el dashboard no se
   sature de gráficos de analítica" ya estaba cumplido antes de esta fase.

3. **`categories/page.tsx` y `accounts/page.tsx` son rutas de primer nivel completamente
   funcionales, sin ningún flag de "modo lectura".** `categories/page.tsx` (303 líneas) tiene
   botón "Nueva Categoría" (líneas 133-137), acciones de editar/eliminar por tarjeta
   (líneas 176-203) y dos `ModalShell` de creación/edición (líneas 209-300). `accounts/page.tsx`
   (376 líneas) tiene el mismo patrón completo, más el toggle de destacada. Ninguna de las dos
   tiene hoy ningún total agregado en el encabezado — son listados puros de tarjetas.

4. **El backend expone 4 endpoints de dashboard, y los 3 bugs de moneda del ítem 1 están
   confirmados línea por línea en `backend/app/api/dashboard.py`:**
   - `obtener_progreso_presupuestos` (líneas 113-173): `spent_rows` (136-150) agrupa el gasto
     **solo por `category_id`**, sin `currency`, y `spent_map` (152) queda indexado únicamente por
     `category_id`. La comparación final usa `presupuesto.amount_limit` (que vive en
     `presupuesto.currency`) contra un `gastado` que puede incluir montos de cualquier moneda. Con
     el seed de `test@test.com` (cuentas COP y USD, `backend/app/core/seed.py`) esto ya produce un
     `percentage` incorrecto en cuanto existan gastos en dos monedas para la misma categoría.
   - `obtener_serie_flujo_caja` (176-219): la query agrupa por `date_label` únicamente (208), sin
     filtrar ni agrupar por `currency` — dos transacciones del mismo día en monedas distintas se
     suman en el mismo punto de la serie.
   - `obtener_distribucion_categorias` (222-278): mismo patrón en ambas ramas (`neto=True` y
     `neto=False`) — `group_by(category_id, category_name)` sin `currency`.
   - Los tres endpoints comparten el mismo defecto que tenía `obtener_resumen` (`/summary`) antes
     de corregirse el 2026-07-14 (commit `9e6b4cb`, ver hallazgo 7 abajo).

5. **`actualizar_transaccion` (`backend/app/api/transactions.py:224-318`) confirma el bug tal
   cual lo describe el ROADMAP, y ya existe un test que lo documenta como fallo esperado.**
   Las líneas 300-309 copian campo por campo (`amount`, `type`, `description`, `account_id`,
   `category_id`, `payment_method`, `date`) pero **nunca** `currency` — a diferencia de
   `crear_transaccion` (línea 91: `nueva_transaccion.currency = cuenta.currency`). Más importante
   para el plan de trabajo: `backend/tests/test_transactions.py:400-439` ya tiene
   `test_update_moving_to_different_currency_account_updates_currency`, marcado
   `@pytest.mark.xfail(strict=True, reason="...Fix planeado para Fase 10...")` — el comentario del
   test está desactualizado (decía "Fase 10"; el fix quedó pospuesto a Fase 11 en la reescritura
   del ROADMAP), pero el test en sí es exactamente el caso que este ítem debe hacer pasar. No hay
   que escribir un test nuevo — hay que **quitarle el `xfail`** una vez aplicado el fix.

6. **Ni `BudgetProgress`, ni `CashflowData`, ni `CategoryDistributionData` exponen `currency` en
   su respuesta — hallazgo que va más allá de lo que dice el ROADMAP.** `backend/app/schemas/
   schemas.py:238-244` (`BudgetProgress`) y `276-291` (`CashflowData`, `CategoryDistributionData`)
   no tienen ningún campo `currency`. Consecuencia concreta para `BudgetProgress`:
   `frontend/components/charts/BudgetRing.tsx:94-100` formatea `spentAmount`/`budgetAmount` con
   `config.currency` — la moneda **preferida global** del usuario, no la moneda real del
   presupuesto (`Budget.currency`, que puede ser distinta). Es decir: **arreglar solo el cálculo
   de `budgets-progress` (comparar gasto y límite en la misma moneda) no alcanza** — un
   presupuesto en USD seguiría mostrándose con el símbolo/formato de COP si esa es la moneda
   preferida del usuario. El ítem 1 necesita, además del fix de agregación, agregar `currency` a
   `BudgetProgress` y propagarlo hasta `BudgetRing`. Ver Decisión 11.1.2.

7. **El fix de referencia (`/summary`, 2026-07-14) está confirmado en el commit `9e6b4cb`
   ("Fase 6 Quick Wins: dashboard multi-moneda...").** El patrón exacto: reemplazar
   `db.query(func.sum(...)).filter(...).scalar()` (un solo total) por
   `db.query(Modelo.currency, func.sum(...).label("total")).filter(...).group_by(Modelo.currency).all()`,
   y devolver un array `list[{currency, total}]` en vez de un escalar. El frontend
   (`dashboard/page.tsx:77-109`) ya sabe renderizar ese shape (`summary.balances.map(...)`, una
   línea por moneda). **Este patrón se reutiliza literalmente para `budgets-progress`** (agrupar
   `spent` también por `currency`), pero **no aplica igual a `cashflow-series` ni a
   `category-distribution`** — ver Decisión 11.1.1 sobre por qué esos dos usan un enfoque
   distinto (filtro por moneda, no array agrupado).

8. **`accounts/page.tsx` no tiene ningún total agregado, y `GET /dashboard/summary` no es
   reutilizable tal cual para ese total — hallazgo que contradice la lectura literal de "mover la
   card `Balance Total`" del ROADMAP.** `obtener_resumen` (`dashboard.py:20-32`) filtra
   explícitamente por cuentas **destacadas** (`highlighted=true`) si existe al menos una — es el
   comportamiento correcto para un dashboard que solo quiere las cuentas más relevantes
   (`backend/docs/BUSINESS_RULES.md:17`). Pero `accounts/page.tsx` lista **todas** las cuentas del
   usuario, destacadas o no (`sortedAccounts`, línea 145-154, solo reordena, no filtra). Si la
   "vista secundaria de saldos" reutiliza literalmente el array `balances` de `/summary` como
   encabezado, el total mostrado arriba **no coincidiría** con la suma de las tarjetas listadas
   debajo en cuanto el usuario tenga alguna cuenta no destacada — exactamente el tipo de
   inconsistencia que una vista cuyo propósito es "ver todos tus saldos" no puede permitirse. Ver
   Decisión 11.5.1: se necesita un endpoint nuevo, pequeño, sin el filtro de destacadas.

9. **El cálculo de "balance del mes" no puede hacerse en el cliente sin violar una regla explícita
   de `CLAUDE.md`.** `CLAUDE.md`: *"Backend is the source of truth for all financial
   calculations (account balances, budget progress, dashboard aggregates). The frontend must
   never recompute these."* `User.monthly_income` (`backend/app/models/models.py:28`) ya existe y
   ya se expone en `UserResponse.monthly_income` (`schemas.py:91`, consumible vía
   `useCurrentUser`), y `monthly_expense_by_currency` ya lo devuelve `/summary`. Restar ambos en
   `dashboard/page.tsx` sería trivial pero es exactamente el tipo de agregado financiero que la
   regla prohíbe recomputar en cliente — el ROADMAP habla de "agregar el cálculo de balance del
   mes" sin especificar dónde vive ese cálculo; este documento lo resuelve agregándolo a
   `GET /dashboard/summary` (ver Decisión 11.3.1), no en el componente de React.

10. **No existe hoy ninguna pantalla que permita fijar `User.monthly_income` — hallazgo que hace
    que la nueva card principal nazca vacía para el 100% de los usuarios actuales, incluida la
    cuenta de pruebas.** Confirmado en `docs/specs/fase_08_spec.md` (§1, "Frontend"): la decisión
    explícita de Fase 8 fue **no** construir esa UI todavía ("no existe página de perfil/ajustes";
    la captura de `monthly_income` queda para el onboarding de Fase 15). `grep -rn
    "monthly_income" frontend/` (fuera de `types/api.ts`) no devuelve ningún componente que lo
    lea o lo escriba. Consecuencia: si Fase 11 solo agrega el cálculo de flujo y le da prioridad
    visual sin ofrecer ninguna forma de fijar el ingreso, la card más prominente del dashboard
    queda permanentemente vacía para todo usuario hasta que Fase 15 exista — que depende
    explícitamente de que Fase 11 esté terminada (`docs/ROADMAP.md`, Fase 15: "Depende de Fases
    8, 10 y 11"), así que no hay ninguna fecha cercana en la que esto se resuelva solo. El ROADMAP
    del MVP lista "Dashboard mensual simple — gastado/ingresado/**balance**" como uno de los 5
    componentes centrales del producto — no es un detalle menor que se pueda dejar roto a
    propósito. Ver Decisión 11.3.2: se agrega un control mínimo de "fijar ingreso mensual" *en la
    propia card*, sin construir una pantalla de perfil completa.

11. **No existe ningún test de `backend/app/api/dashboard.py` hoy — archivo `backend/tests/
    test_dashboard.py` no existe.** `docs/specs/fase_07_spec.md` (Decisión 4.2.1) ya dejó esto
    documentado como alcance explícitamente fuera de Fase 7 ("`dashboard.py`... bifurca por
    dialecto... queda fuera del alcance de esta tarea"), pero seguía sin resolverse en Fases 8-10.
    Esta fase toca `dashboard.py` en 3 de sus 4 endpoints — es el momento natural de crear el
    archivo de tests que faltaba, no solo parchar sin cobertura.

---

## Orden de ejecución recomendado

La dependencia real entre tareas (no el orden del ROADMAP, aunque coincide en su mayoría):

```
1. Backend: 3 bugs multi-moneda (§11.1) + fix `actualizar_transaccion` (§11.2)
   ── ambos son correcciones puras de bugs ya confirmados, sin depender de
      ninguna decisión de diseño de UI pendiente; el propio ROADMAP ya dice
      que el ítem 1 "se adelanta al inicio de la fase". Agruparlos en un
      mismo PR es razonable (comparten el módulo de transacciones/dashboard)
      pero no obligatorio — son independientes entre sí.

2. Backend+Frontend: balance de flujo mensual + reordenar summary
   cards (§11.3)
   ── depende de (1) solo por tocar el mismo archivo (dashboard.py,
      `obtener_resumen`) — no depende técnicamente del fix de los otros 3
      endpoints. Agruparlo en el mismo PR que (1) evita reabrir
      dashboard.py dos veces.

3. Frontend: desglose por categoría en barras horizontales (§11.4)
   ── depende de (1): reusa `category-distribution`, que debe estar ya
      corregido para no construir una superficie nueva sobre datos con el
      bug de monedas mezcladas todavía presente.

4. Backend+Frontend: vista secundaria de saldos de cuentas (§11.5)
   ── independiente de (1)-(3); nuevo endpoint aislado en accounts.py.
      Puede hacerse en paralelo desde el día 1.

5. Frontend: ocultar controles de categorías personalizadas (§11.6)
   ── totalmente independiente; un solo archivo (categories/page.tsx), sin
      tocar backend. Puede hacerse en paralelo desde el día 1.

6. Frontend: reagrupar visualmente el sidebar (§11.7)
   ── totalmente independiente; un solo archivo (Sidebar.tsx). Puede
      hacerse en paralelo desde el día 1.
```

Los pasos 4, 5 y 6 no bloquean nada del resto — pueden implementarse en paralelo a 1-3 por
distintos agentes/personas, igual que el criterio ya usado en `docs/specs/fase_09_spec.md` y
`docs/specs/fase_10_spec.md` para las ramas sin dependencia.

Estimación total heredada del ROADMAP: 1d (§11.1) + 2h (§11.2) + 4h (§11.3) + 1d (§11.4) + 4h
(§11.5) + 4h (§11.6) + 2h (§11.7) = 8h + 2h + 4h + 8h + 4h + 4h + 2h = **32h (~4 días de trabajo de
8h)**. Único ajuste frente al número heredado: §11.1 probablemente necesita más de las 8h
asignadas si se incluye el fix de `BudgetRing`/`BudgetProgress.currency` del hallazgo 6 (no
nombrado explícitamente por el ROADMAP, pero necesario para que el fix sea correcto de punta a
punta) — estimar ~2h adicionales dentro de esa tarea, absorbibles en el total de 4 días sin
sobrepasarlo.

---

## 1. Corregir los 3 bugs multi-moneda restantes

### Backend

**Archivo a modificar:** `backend/app/api/dashboard.py`.

**Decisión de diseño 11.1.1 — dos patrones de corrección distintos, según lo que consume cada
endpoint.** El ROADMAP sugiere "agrupar por currency" como patrón único (el de `/summary`), pero
no todos los endpoints tienen el mismo consumidor:

- **`budgets-progress`**: cada fila de salida ya representa **un** presupuesto con **una** moneda
  fija (`Budget.currency`). El fix correcto es agrupar `spent` también por `currency` y comparar
  cada presupuesto contra el balde de su propia moneda — sin cambiar la forma de la respuesta
  (sigue siendo una fila por presupuesto), solo agregando el campo `currency` que faltaba
  (hallazgo 6).
- **`cashflow-series`** y **`category-distribution`** alimentan visualizaciones de **una sola
  serie** (`CashflowChart`, gráfico de barras; `CategoryDonutChart`, una dona) que hoy **ya**
  formatean sus valores con `config.currency` (la moneda preferida global, ver
  `CashflowChart.tsx:75`, `151`, `161`; `CategoryDonutChart.tsx:222`, `272`) — ninguno de los dos
  componentes tiene ninguna noción de "varias monedas a la vez". Devolver un array agrupado por
  moneda (como `/summary`) no arregla nada por sí solo: estos componentes no saben qué hacer con
  eso, y sin cambiarlos el bug simplemente se movería de "el backend suma monedas distintas" a
  "el frontend renderiza solo el primer grupo del array e ignora el resto en silencio". La
  corrección elegida es **filtrar por una sola moneda en el backend**, con un parámetro
  `currency` opcional que por defecto toma `current_user.preferred_currency` — el mismo criterio
  de "la moneda preferida es la vista por defecto" que ya usa `/summary` para *ordenar* sus
  arrays, aplicado aquí para *filtrar* en vez de agrupar. Esto no requiere ningún cambio en
  `CashflowChart.tsx` ni en `CategoryDonutChart.tsx` — coherente con que el ROADMAP dice
  explícitamente que `CategoryDonutChart` "queda intacto". El único cambio de frontend es que los
  call sites que arman los query params (`analytics/page.tsx`, y el nuevo consumidor de §11.4)
  empiecen a pasar `currency` explícitamente — no es estrictamente necesario para que el fix
  funcione (el backend ya defaultea a la moneda preferida sin que el cliente pase nada), pero deja
  la intención explícita en vez de depender de un default implícito. Backlog explícito, no de esta
  fase: un selector de moneda en Analítica para usuarios con más de una — ya está en
  `docs/ROADMAP.md`, "Backlog priorizado", como "Filtros de fecha y categoría en dashboard —
  Iteración 2, cuando haya datos de uso reales que lo justifiquen".

**Decisión de diseño 11.1.2 — agregar `currency` a `BudgetProgress` y propagarlo a `BudgetRing`,
como parte de este mismo ítem, no como una tarea aparte.** El hallazgo 6 confirma que sin esto el
fix de agregación es numéricamente correcto pero visualmente engañoso (símbolo/formato de la
moneda equivocada). El costo es mínimo (un campo de schema + una prop de componente ya diseñado
para recibir props claras, per `frontend/docs/COMPONENTS_GUIDE.md`) y directamente necesario para
que el ítem 1 del ROADMAP cumpla lo que promete ("corregir los bugs multi-moneda"), no una
ampliación de alcance — se documenta aquí en vez de en una tarea nueva porque no tiene sentido
como ítem independiente.

**`obtener_progreso_presupuestos` — diff concreto:**

```python
spent_rows = (
    db.query(
        models.Transaction.category_id,
        models.Transaction.currency,
        func.sum(models.Transaction.amount).label("spent"),
    )
    .filter(
        models.Transaction.user_id == current_user.id,
        models.Transaction.type == "expense",
        models.Transaction.category_id.in_(category_ids),
        models.Transaction.date >= primer_dia,
        models.Transaction.date <= ultimo_dia,
    )
    .group_by(models.Transaction.category_id, models.Transaction.currency)
    .all()
)

spent_map: dict[tuple[int, str], Decimal] = {(r.category_id, r.currency): r.spent for r in spent_rows}

...

for presupuesto in presupuestos:
    gastado = spent_map.get((presupuesto.category_id, presupuesto.currency), Decimal("0.00"))
    porcentaje = float(gastado / presupuesto.amount_limit) * 100 if presupuesto.amount_limit > 0 else 0
    cat_name, cat_icon = cat_info_map.get(presupuesto.category_id, ("Desconocida", None))
    progreso_lista.append(
        {
            "budget_id": presupuesto.id,
            "category_name": cat_name,
            "category_icon": cat_icon,
            "amount_limit": presupuesto.amount_limit,
            "spent": gastado,
            "percentage": round(porcentaje, 2),
            "currency": presupuesto.currency,
        }
    )
```

**`obtener_serie_flujo_caja` y `obtener_distribucion_categorias` — diff concreto (mismo patrón en
ambos):**

```python
@router.get("/cashflow-series", response_model=list[schemas.CashflowData])
def obtener_serie_flujo_caja(
    start_date: datetime,
    end_date: datetime,
    period: str = Query("day", pattern="^(day|month)$", description="Agrupar por 'day' o 'month'"),
    currency: str | None = Query(None, description="Moneda a filtrar; por defecto la preferida del usuario"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    filtro_moneda = currency or current_user.preferred_currency or "COP"
    try:
        ...
        rows = (
            db.query(...)
            .filter(
                models.Transaction.user_id == current_user.id,
                models.Transaction.currency == filtro_moneda,
                models.Transaction.date >= start_date,
                models.Transaction.date <= end_date,
            )
            ...
        )
```

Mismo agregado de `models.Transaction.currency == filtro_moneda` en ambas ramas (`neto`/no-`neto`)
de `obtener_distribucion_categorias`, con el mismo parámetro `currency: str | None = Query(None,
...)` agregado a la firma.

**Archivos a modificar:**
- `backend/app/api/dashboard.py` — los tres endpoints (diffs arriba).
- `backend/app/schemas/schemas.py` — `BudgetProgress` (línea 238-244): agregar `currency: str`.
- `backend/app/schemas/schemas.py` — `CashflowData`/`CategoryDistributionData`: **sin cambios**
  (Decisión 11.1.1 — se filtra, no se agrupa, así que la forma de la respuesta no cambia).

### Frontend

**Archivos a modificar:**
- `frontend/types/api.ts` — `BudgetProgress` (líneas 43-50): agregar `currency: string;`.
- `frontend/components/charts/BudgetRing.tsx` — nueva prop `currency?: string`; usar
  `formatCurrency(safeSpent, currency ?? config.currency)` y
  `formatCurrency(safeBudget === 1 && budgetAmount === 0 ? 0 : safeBudget, currency ?? config.currency)`
  en vez de `config.currency` a secas (líneas 94-100). El `?? config.currency` mantiene
  compatibilidad hacia atrás con cualquier otro consumidor futuro que no pase la prop.
- `frontend/app/(dashboard)/page.tsx` — línea 140-146, pasar `currency={budget.currency}` a cada
  `<BudgetRing ... />`.
- `frontend/app/(dashboard)/analytics/page.tsx` — `buildBarDateRange`/`buildDonutDateRange` (o los
  dos `useQuery` que arman `params`, líneas 96-105 y 120-129): agregar
  `currency: user?.preferred_currency` a ambos `params` (requiere leer `useCurrentUser()` en esta
  página, que hoy no lo hace — importarlo, mismo patrón que `accounts/page.tsx`). No es
  estrictamente necesario para que el fix funcione (el backend defaultea solo), pero deja la
  intención explícita — ver Decisión 11.1.1.

**Testing:**

Crear `backend/tests/test_dashboard.py` (no existe hoy, hallazgo 11) con:
- `TestBudgetsProgressCurrency`: crear dos cuentas (COP y USD) para el mismo usuario, categoría
  compartida, un presupuesto en COP para esa categoría, gastos en ambas monedas — verificar que
  `spent`/`percentage` del presupuesto solo reflejan el gasto en COP, y que la respuesta incluye
  `currency: "COP"`.
- `TestCashflowSeriesCurrency`: transacciones en COP y USD el mismo día — sin pasar `currency`,
  la serie devuelta corresponde solo a la moneda preferida del usuario (default `"COP"`); pasando
  `currency=USD` explícito, devuelve solo esas transacciones.
- `TestCategoryDistributionCurrency`: mismo patrón que el anterior, para ambas ramas (`neto=true`
  y `neto=false`).
- Regresión: sin ningún dato en más de una moneda (caso de la mayoría de usuarios reales), los
  tres endpoints se comportan igual que antes del fix — no debe haber ninguna diferencia
  observable para un usuario mono-moneda.

**Criterio de aceptación:**
- Un usuario con transacciones en dos monedas ve el progreso de presupuesto, la serie de flujo de
  caja y la distribución por categoría correctos para la moneda de cada presupuesto / la moneda
  preferida, sin sumar montos de monedas distintas en ningún punto.
- `BudgetRing` muestra el símbolo/formato de la moneda real del presupuesto, no la moneda
  preferida global si difieren.
- `docs/TODO.md`: mover la entrada "Los 3 endpoints restantes del dashboard mezclan monedas" (🟠
  Bugs confirmados) a "Resueltos" con la fecha de esta fase.

---

## 2. `actualizar_transaccion` no actualiza `currency`

### Backend

**Archivo a modificar:** `backend/app/api/transactions.py`, función `actualizar_transaccion`
(líneas 300-309).

**Diff concreto:**

```python
transaccion_db.amount = transaccion_actualizada.amount
transaccion_db.type = transaccion_actualizada.type
transaccion_db.description = transaccion_actualizada.description
transaccion_db.account_id = transaccion_actualizada.account_id
transaccion_db.category_id = transaccion_actualizada.category_id
transaccion_db.currency = cuenta_nueva.currency  # 🆕 hereda la moneda de la cuenta destino,
                                                   # igual que crear_transaccion (línea 91)
if transaccion_actualizada.payment_method is not None:
    transaccion_db.payment_method = transaccion_actualizada.payment_method
if transaccion_actualizada.date is not None:
    transaccion_db.date = transaccion_actualizada.date
```

Sin condición: a diferencia de `payment_method`/`date` (que se preservan si el cliente no los
reenvía), `currency` **nunca** debe conservar el valor viejo — es un dato derivado de la cuenta,
no un campo que el usuario edite directamente (mismo principio que ya aplica en la creación).
`cuenta_nueva` ya está resuelta y validada más arriba en la función (línea 243-250), no hace falta
ninguna query adicional.

**Testing:** `backend/tests/test_transactions.py:400-439` ya tiene el test exacto
(`test_update_moving_to_different_currency_account_updates_currency`). Único cambio necesario:
quitar el decorador `@pytest.mark.xfail(...)` (líneas 400-408) y actualizar el comentario de la
línea 437-438 si sigue mencionando "Hoy no ocurre" (ya no aplica). No se necesita ningún test
nuevo — el existente ya cubre el caso, incluido el `assert` de la moneda esperada.

**Criterio de aceptación:**
- El test dejado de `xfail` pasa en verde.
- Mover una transacción de una cuenta COP a una cuenta USD (vía `PUT
  /api/v1/transactions/{id}`) actualiza `currency` a `"USD"` en la respuesta y en la base de
  datos.
- `docs/TODO.md`: mover "`actualizar_transaccion` no actualiza `currency`" a "Resueltos". **No
  confundir con** la entrada distinta "`Account PUT` ignora cambios de `currency` silenciosamente"
  (`AccountUpdate.currency` en `accounts.py`) — ese es un bug distinto, en un archivo distinto, no
  tocado por este ítem ni por el ROADMAP de esta fase.

---

## 3. Reordenar la jerarquía de las summary cards del dashboard

### Backend

**Decisión de diseño 11.3.1 — `monthly_flow_balance` se calcula en `GET /dashboard/summary`, no
en el cliente.** Ver hallazgo 9: `CLAUDE.md` prohíbe explícitamente recomputar agregados
financieros en el frontend. Se extiende el endpoint ya existente en vez de crear uno nuevo —
`obtener_resumen` ya calcula `monthly_expense_by_currency` en la misma función, así que el nuevo
campo es una resta sobre datos que la función ya tiene en memoria, sin queries adicionales.

**Archivo a modificar:** `backend/app/api/dashboard.py`, función `obtener_resumen`
(líneas 20-110).

**Diff concreto:**

```python
    balances.sort(key=lambda x: sort_key(x["currency"]))
    income.sort(key=lambda x: sort_key(x["currency"]))
    expense.sort(key=lambda x: sort_key(x["currency"]))

    # Balance de flujo mensual (Fase 11 §11.3): ingreso mensual declarado por el usuario
    # menos el gasto del mes en su moneda preferida. None si el usuario no ha fijado
    # monthly_income todavía — el frontend debe distinguir "0" de "sin definir".
    monthly_flow_balance = None
    if current_user.monthly_income is not None:
        gasto_moneda_preferida = next(
            (item["total"] for item in expense if item["currency"] == preferred_currency),
            Decimal("0.00"),
        )
        monthly_flow_balance = current_user.monthly_income - gasto_moneda_preferida

    return {
        "balances": balances,
        "monthly_income_by_currency": income,
        "monthly_expense_by_currency": expense,
        "monthly_flow_balance": monthly_flow_balance,
    }
```

**Archivo a modificar:** `backend/app/schemas/schemas.py`, `DashboardSummary` (líneas 232-235):

```python
class DashboardSummary(BaseModel):
    balances: list[BalanceByCurrency]
    monthly_income_by_currency: list[BalanceByCurrency]
    monthly_expense_by_currency: list[BalanceByCurrency]
    monthly_flow_balance: Decimal | None = None
```

**Limitación conocida, documentada a propósito:** `monthly_flow_balance` solo considera el gasto
en la moneda preferida del usuario — si tiene gastos relevantes en una segunda moneda, esos no
restan del balance de flujo. Es la misma limitación de fondo que ya aceptan `cashflow-series` y
`category-distribution` tras la Decisión 11.1.1 (una sola moneda a la vez, la preferida por
defecto) — consistente en todo el dashboard, no una inconsistencia nueva de este ítem.

### Frontend

**Decisión de diseño 11.3.2 — control mínimo de "fijar ingreso mensual" dentro de la propia card,
no una pantalla de perfil.** Ver hallazgo 10: sin esto, la card con mayor prioridad visual del
dashboard queda vacía para todo usuario actual, sin ninguna fecha cercana en que se resuelva sola
(Fase 15 depende de que Fase 11 termine, no al revés). Construir una pantalla `/settings` completa
sería sobre-alcance para este ítem (4h asignadas en el ROADMAP) y se adelantaría a decisiones de
Fase 15 sobre cómo debe verse el onboarding completo. La solución mínima: cuando
`monthly_flow_balance` es `null`, la card muestra un estado vacío con un campo numérico inline
(no un modal, no una ruta nueva) que llama a `PATCH /api/v1/users/me` (ya existe, Fase 8 §1) al
confirmar. Una vez fijado, la card pasa a mostrar el balance calculado en cada carga futura. Esto
no reemplaza el flujo guiado de Fase 15 (que seguirá existiendo como la vía principal para
usuarios nuevos) — es una vía de escape para que la card no nazca rota hoy.

**Archivo a modificar:** `frontend/app/(dashboard)/page.tsx`.

**Pasos:**
1. Reordenar las 3 `SummaryCard` existentes (líneas 68-112): `Balance Total` deja de renderizarse
   aquí (se mueve por completo a `accounts/page.tsx`, ver §11.5 — no se deja una copia en ambos
   lados). El grid pasa a 2 columnas visualmente secundarias (`Ingresos del Mes`, `Gastos del
   Mes`) más una card nueva de mayor jerarquía visual arriba.
2. Nueva card `Balance del mes` (usa `summary?.monthly_flow_balance`), con prioridad visual
   explícita — tamaño mayor o posición destacada por encima del grid de 2 columnas, no dentro del
   mismo grid de 3 iguales que hoy trata las 3 cards como pares. Reusar `SummaryCard` (ya acepta
   `children`/`color`/`trend`) en vez de crear un componente nuevo, salvo que el tamaño mayor no
   quepa en las props actuales — si hace falta, extender `SummaryCard` con una prop `size?: 'md' |
   'lg'` en vez de duplicar el componente (`frontend/docs/COMPONENTS_GUIDE.md`: "si una UI
   aparece dos veces, primero pensar en un componente compartido").
3. Si `summary?.monthly_flow_balance == null` (no `undefined` por loading — distinguir el estado
   de carga del estado "sin definir"): renderizar, dentro de la misma card, un `<Input
   type="number" inputMode="decimal">` + botón "Guardar" en vez del monto. Mutación:
   ```tsx
   const setMonthlyIncomeMutation = useMutation({
     mutationFn: async (monthly_income: number) =>
       (await api.patch('users/me', { monthly_income })).data,
     onSuccess: () => {
       queryClient.invalidateQueries({ queryKey: queryKeys.currentUser() });
       queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.summary() });
       toast.success('Ingreso mensual guardado');
     },
     onError: (error: unknown) => toast.error(getApiError(error)),
   });
   ```
   (`api.patch` ya soportado por el cliente Axios existente, sin cambios en `lib/api.ts`).
4. Mostrar el monto con signo/color según sea positivo o negativo (`trend="up"`/`"down"` ya
   soportado por `SummaryCard`, mismo patrón que `Ingresos del Mes`/`Gastos del Mes`).

**Archivos a modificar:**
- `frontend/app/(dashboard)/page.tsx` (pasos 1-4).
- `frontend/types/api.ts` — `DashboardSummary` (líneas 57-61): agregar
  `monthly_flow_balance: number | null;`.
- `frontend/components/ui/SummaryCard.tsx` — solo si se necesita la prop `size` de mayor jerarquía
  visual (paso 2).

**Testing:**

Backend (`backend/tests/test_dashboard.py`, mismo archivo del §11.1):
- Usuario sin `monthly_income` fijado: `GET /dashboard/summary` devuelve `monthly_flow_balance:
  null`.
- Usuario con `monthly_income` fijado y sin gastos del mes: `monthly_flow_balance ==
  monthly_income`.
- Usuario con `monthly_income` y gastos en la moneda preferida: `monthly_flow_balance ==
  monthly_income - gasto_del_mes`.
- Usuario con gastos solo en una moneda distinta a la preferida: `monthly_flow_balance ==
  monthly_income` (el gasto en otra moneda no resta, ver limitación documentada arriba).

Frontend: verificación manual (no hay suite de tests de frontend, `docs/TODO.md` lo marca 🔵 "solo
si el proyecto crece") — confirmar que fijar el ingreso mensual desde la card actualiza el balance
sin recargar la página, y que un usuario que ya lo fijó ve el balance directamente sin el campo de
edición en cargas futuras.

**Criterio de aceptación:**
- `Balance del mes` tiene prioridad visual sobre `Ingresos del Mes`/`Gastos del Mes`.
- `Balance Total` ya no aparece en el dashboard (se verifica junto con §11.5, que confirma dónde
  quedó).
- Un usuario sin `monthly_income` puede fijarlo desde la misma card, sin salir del dashboard.
- El cálculo del balance nunca se hace en el cliente — se verifica que `dashboard/page.tsx` no
  contiene ninguna resta de `monthly_income - monthly_expense` en su código, solo lee
  `summary.monthly_flow_balance` ya calculado.

---

## 4. Desglose por categoría en barras horizontales

### Frontend

**Confirmado 100% frontend** (backend ya corregido en §11.1; `category-distribution` no necesita
ningún cambio adicional de forma para este ítem).

**Decisión de diseño 11.4.1 — nuevo componente `CategoryBreakdownBars.tsx`, no reutilizar
`CategoryDonutChart`.** El ROADMAP es explícito: "aditivo, no reemplazo" y "`CategoryDonutChart`
se queda intacto en `/analytics`". Son audiencias distintas (exploración detallada con toggles de
período/tipo/neto en Analítica, vistazo rápido sin controles en el dashboard) — forzar el mismo
componente a servir ambos casos añadiría props condicionales (`showControls?`, `variant?:
'donut'|'bars'`) a un componente que hoy tiene una responsabilidad única y bien definida. Un
componente nuevo, pequeño, en `frontend/components/charts/` (mismo directorio que `BudgetRing.tsx`
— es exactamente ese tipo de pieza: recibe datos ya calculados, sin controles de filtro propios).

**Diseño de datos:** rango de fechas = mes en curso (mismo `primer_dia`/`hoy` que ya usa el
backend para `budgets-progress`/`summary` — consistente con el resto del dashboard, que es
mensual por definición según el propio título de la fase). `type=expense` fijo (el dashboard
responde "¿cuánto gasté?", no necesita alternar a ingresos — ese control ya vive en Analítica).
`neto` no se pasa (default `false` del backend). El backend ya ordena descendente
(`order_by(func.sum(...).desc())` / `order_by(net_total.desc())`, `dashboard.py:274`, `253`) — no
hace falta ningún `.sort()` adicional en el cliente.

**Archivos a crear:**
- `frontend/components/charts/CategoryBreakdownBars.tsx`:
  ```tsx
  interface CategoryBreakdownBarsProps {
    data: CategoryDistributionItem[] | undefined;
    isLoading: boolean;
  }
  ```
  Estructura: card `bg-surface border-border/70 rounded-2xl border p-6` (mismo patrón visual que
  `BudgetRing`/`SummaryCard`), lista de filas — cada fila: `CategoryIcon` + nombre + monto
  formateado a la derecha + barra horizontal cuyo ancho es proporcional al valor máximo de la
  lista (`width: ${(item.total / maxTotal) * 100}%`), reusando `formatCurrency` de `lib/utils.ts`.
  Estado vacío: reusar `EmptyState` (ya usado en `dashboard/page.tsx` para presupuestos y
  transacciones recientes — mismo patrón, no un componente nuevo de "vacío").

**Archivos a modificar:**
- `frontend/app/(dashboard)/page.tsx`: nuevo `useQuery` (mismo patrón que los otros 3 ya
  existentes en este archivo):
  ```tsx
  const { data: categoryBreakdown, isLoading: loadingCategoryBreakdown } = useQuery<
    CategoryDistributionItem[]
  >({
    queryKey: queryKeys.dashboard.categoryBreakdown(),
    queryFn: async () =>
      (
        await api.get('dashboard/category-distribution', {
          params: { start_date: primerDiaDelMes, end_date: hoy, type: 'expense' },
        })
      ).data,
  });
  ```
  (`primerDiaDelMes`/`hoy` calculados igual que `analytics/page.tsx::formatISOForBackend`, o
  extraídos a un helper compartido si se prefiere no duplicar el formateo de fecha — no
  obligatorio para el alcance de este ítem, evaluar al implementar). Renderizar
  `<CategoryBreakdownBars data={categoryBreakdown} isLoading={loadingCategoryBreakdown} />` bajo
  la sección de "Ejecución de Presupuestos" y antes de "Transacciones recientes" (o donde encaje
  mejor visualmente — no especificado por el ROADMAP, decisión de implementación de bajo riesgo).
- `frontend/lib/queryKeys.ts`: agregar `dashboard.categoryBreakdown: () =>
  ['dashboard-category-breakdown'] as const` — clave propia, no reutilizar
  `queryKeys.analytics.categories(...)` (que además requiere 4 argumentos posicionales que no
  aplican aquí — el dashboard no tiene selector de período/tipo/neto). Consistente con
  `frontend/docs/STATE_AND_FETCHING.md`: "cada pantalla de negocio debe tener su propia
  `queryKey`".

**Testing:** frontend sin suite automatizada (igual que §11.3). Verificación manual: el orden de
las barras coincide con el orden de mayor a menor gasto; una categoría con gasto cero no aparece
(el backend ya no la incluye, `category-distribution` solo devuelve filas con `SUM > 0` de facto
al no haber transacciones que agregar); el estado vacío se muestra si no hay gastos este mes.

**Criterio de aceptación:**
- Las barras aparecen ordenadas de mayor a menor gasto, sin trabajo de ordenamiento en el cliente.
- `CategoryDonutChart` y `/analytics` no cambian de comportamiento (diff de esos archivos: cero
  líneas tocadas por este ítem).
- El componente nuevo no tiene controles de filtro propios (período/tipo/neto) — es una vista de
  solo lectura del mes en curso.

---

## 5. Vista secundaria de saldos de cuentas

### Backend

**Decisión de diseño 11.5.1 — endpoint nuevo `GET /api/v1/accounts/summary`, no reutilizar
`GET /api/v1/dashboard/summary`.** Ver hallazgo 8: `/dashboard/summary` filtra por cuentas
destacadas cuando existen, semántica correcta para el dashboard pero incorrecta para una vista
cuyo propósito es mostrar el saldo de *todas* las cuentas del usuario, listadas una por una debajo
del total. Reutilizar el campo `balances` de `/summary` produciría un total que no cuadra con la
suma de las tarjetas visibles apenas el usuario tenga alguna cuenta no destacada — el tipo de
inconsistencia que rompe la confianza de una vista de saldos. El nuevo endpoint es una copia
reducida (sin el filtro de `highlighted`) del bloque `balances_rows` que ya existe en
`obtener_resumen` — mismo patrón que el fix de moneda de §11.1, sin agrupar por período (no aplica
aquí, son saldos actuales, no flujo mensual).

**Archivo a modificar:** `backend/app/api/accounts.py`.

**⚠️ Nota de implementación — orden de declaración de rutas.** FastAPI/Starlette resuelve rutas en
el orden en que se declaran. `accounts.py` ya tiene `GET /{account_id}` (línea 36). Si
`GET /summary` se declara **después** de esa ruta, cualquier request a `/accounts/summary`
coincidiría primero con `/{account_id}` (interpretando `"summary"` como `account_id`, que fallaría
la validación de tipo `int` con un `422` en vez de ejecutar el endpoint nuevo). El nuevo endpoint
debe declararse **antes** de `@router.get("/{account_id}")` (líneas 36-46) — inmediatamente
después de `obtener_cuentas` es un buen lugar.

**Diff concreto:**

```python
@router.get("/summary", response_model=list[schemas.BalanceByCurrency])
def obtener_resumen_saldos(
    db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)
):
    """Saldo total por moneda de TODAS las cuentas del usuario (sin filtro de destacadas).

    Distinto de GET /dashboard/summary, que sí filtra por cuentas destacadas cuando existen
    (Fase 11 §11.5, Decisión 11.5.1) — este endpoint alimenta accounts/page.tsx, cuya lista
    de tarjetas tampoco filtra por destacadas, así que el total debe coincidir con esa lista.
    """
    rows = (
        db.query(models.Account.currency, func.sum(models.Account.balance).label("total"))
        .filter(models.Account.user_id == current_user.id)
        .group_by(models.Account.currency)
        .all()
    )
    return [{"currency": r.currency, "total": r.total} for r in rows]
```

`schemas.BalanceByCurrency` ya existe (`schemas.py:227-229`) — se reutiliza tal cual, sin schema
nuevo.

### Frontend

**Archivos a modificar:**
- `frontend/app/(dashboard)/accounts/page.tsx`:
  - Nuevo `useQuery` (mismo patrón que el resto de la página):
    ```tsx
    const { data: balancesSummary, isLoading: loadingBalances } = useQuery<BalanceByCurrency[]>({
      queryKey: queryKeys.accounts.summary(),
      queryFn: async () => (await api.get('accounts/summary')).data,
    });
    ```
  - Encabezado nuevo, antes del grid de tarjetas (línea 177): una o más `<SummaryCard
    label="Balance Total">`, una por moneda de `balancesSummary` — mismo patrón visual que ya usa
    `dashboard/page.tsx` hoy para "Balance Total" (líneas 77-87 actuales, que se retiran de ahí en
    §11.3). Es, en efecto, la misma card que se mueve, reapuntada a un endpoint distinto.
  - Invalidar `queryKeys.accounts.summary()` en las mutaciones que ya invalidan
    `queryKeys.accounts.all()` (crear, eliminar, destacar) — la creación/eliminación de cuentas
    cambia el total.
- `frontend/lib/queryKeys.ts`: agregar `accounts.summary: () => ['accounts-summary'] as const`.
- `frontend/types/api.ts`: `BalanceByCurrency` ya existe (líneas 52-55) — se reutiliza sin
  cambios.

**Testing:**

Backend (`backend/tests/test_transactions.py` no aplica; crear casos en un nuevo bloque dentro de
`backend/tests/test_dashboard.py` o, si se prefiere separar por dominio, un
`backend/tests/test_accounts.py` nuevo — no existe hoy, mismo hallazgo de falta de cobertura que
§11.1 señala para `dashboard.py`, extendido aquí a `accounts.py`, que tampoco tiene tests
dedicados):
- Usuario con cuentas destacadas y no destacadas en la misma moneda: `GET /accounts/summary`
  suma **todas**, a diferencia de `GET /dashboard/summary`.
- Usuario con cuentas en dos monedas: el resultado agrupa correctamente por moneda (mismo patrón
  que el test de `/summary` original).
- Ruta `/accounts/summary` no colisiona con `/accounts/{account_id}` — un test que pega a
  `/api/v1/accounts/summary` y confirma `200` con la forma esperada, no `422`.

**Criterio de aceptación:**
- `accounts/page.tsx` muestra un total por moneda que **coincide exactamente** con la suma de las
  tarjetas de cuenta listadas debajo, incluidas las no destacadas.
- El dashboard (`/`) ya no muestra ningún total de saldo de cuentas (verificado junto con §11.3).
- `GET /api/v1/accounts/summary` devuelve `200` y no es interceptado por
  `GET /api/v1/accounts/{account_id}`.

---

## 6. Ocultar solo los controles de creación/edición de categorías personalizadas

### Frontend

**Confirmado 100% frontend, sin cambios de backend** — `categories.py` sigue funcional para
cuando el editor vuelva (backlog: "Editor de categorías personalizable — el código ya existe,
solo está oculto", `docs/ROADMAP.md`, "Backlog priorizado").

**Decisión de diseño 11.6.1 — un flag local, no eliminar el código.** Consistente con el propio
ROADMAP ("el código ya existe, solo queda oculto") y con el criterio ya aplicado en el proyecto
para trabajo diferido (ej. `docs/specs/fase_07_spec.md` §2.6.1, rate limiting distribuido: "diseño
listo pero implementación diferida"). Se oculta la UI de entrada (botón "Nueva Categoría", los
íconos de editar/eliminar por tarjeta, los dos `ModalShell` de creación/edición) detrás de una
constante, dejando las mutaciones (`createCategoryMutation`, `updateCategoryMutation`,
`deleteCategoryMutation`) y el JSX de los modales intactos en el archivo — reactivar el editor en
el futuro es cambiar una línea, no reconstruir código borrado del historial de git.

**Archivo a modificar:** `frontend/app/(dashboard)/categories/page.tsx`.

**Pasos:**
1. Agregar cerca del top del archivo:
   ```tsx
   // Fase 11 §11.6: categorías curadas sin editor en v1 (consistente con Fase 8). El código de
   // creación/edición se mantiene funcional pero oculto — reactivar cambiando este flag cuando
   // el editor de categorías salga del backlog post-MVP (ver docs/ROADMAP.md, "Backlog
   // priorizado").
   const CUSTOM_CATEGORY_EDITING_ENABLED = false;
   ```
2. Botón "Nueva Categoría" (líneas 133-137): envolver en
   `{CUSTOM_CATEGORY_EDITING_ENABLED && (...)}`.
3. Bloque de acciones flotantes por tarjeta (líneas 176-203, ya condicionado a
   `!isSystemCategory`): cambiar la condición a
   `{!isSystemCategory && CUSTOM_CATEGORY_EDITING_ENABLED && (...)}` — no se toca la condición de
   `isSystemCategory`, que sigue siendo necesaria por sí sola si el flag vuelve a `true` (las
   categorías base nunca deben mostrar estas acciones, regla ya existente en
   `backend/docs/BUSINESS_RULES.md:23`).
4. Los dos `ModalShell` (líneas 209-253 creación, 255-300 edición): envolver ambos en
   `{CUSTOM_CATEGORY_EDITING_ENABLED && (...)}` — se mantiene el JSX completo, solo deja de
   montarse.
5. La lista de categorías (líneas 140-207, salvo las acciones del paso 3) **no se toca** — sigue
   mostrando todas las categorías (base + personalizadas del usuario) en modo solo lectura, tal
   como pide el ROADMAP ("la ruta se queda en el sidebar y la lista sigue visible").

**Testing:** sin suite de frontend (igual que §11.3/§11.4). Verificación manual: la ruta
`/categories` sigue accesible desde el sidebar, la lista muestra todas las categorías, ningún
botón de crear/editar/eliminar es visible, y revertir el flag a `true` restaura el comportamiento
completo sin ningún otro cambio.

**Criterio de aceptación:**
- `/categories` sigue en el sidebar y es navegable.
- La lista de categorías (base + personalizadas) sigue visible.
- No hay ningún botón de crear, editar ni eliminar categoría visible en la página.
- `POST /api/v1/categories/`, `PUT /api/v1/categories/{id}`, `DELETE /api/v1/categories/{id}`
  siguen funcionando a nivel de API (no se tocan, siguen alcanzables vía Swagger/`curl` si algún
  flujo interno los necesitara) — este ítem es puramente de superficie visual.

---

## 7. Reagrupar visualmente el sidebar

### Frontend

**Confirmado sin backend, un solo archivo** — `frontend/components/Sidebar.tsx`.

**Decisión de diseño 11.7.1 — reordenar el array `navItems` en dos grupos y extraer un helper de
render local, sin sacar nada del componente a un archivo nuevo.** El ROADMAP es explícito:
"ningún ítem se remueve del menú ni ninguna ruta se oculta — solo se reordena/agrupa". La
implementación actual (`navItems`, líneas 63-70, un solo `.map()`, líneas 116-155) necesita (a)
reordenar los ítems en primario/secundario y (b) insertar un separador visual entre ambos grupos
sin duplicar el JSX de cada `<Link>` (que incluye el tooltip flotante para el estado colapsado,
líneas 147-152) dos veces. Se extrae una función de render local dentro del mismo archivo — no un
componente nuevo en otro archivo, porque solo lo usa `Sidebar.tsx` (el criterio de
`COMPONENTS_GUIDE.md` de "componente compartido" aplica a reutilización entre pantallas, no dentro
del mismo archivo).

**Archivo a modificar:** `frontend/components/Sidebar.tsx`.

**Diff concreto (líneas 63-70 y 115-156):**

```tsx
const primaryNavItems = [
  { name: 'Dashboard', href: '/', icon: LayoutDashboard },
  { name: 'Transacciones', href: '/transactions', icon: ArrowLeftRight },
  { name: 'Presupuestos', href: '/budgets', icon: PieChart },
];

const secondaryNavItems = [
  { name: 'Analítica', href: '/analytics', icon: TrendingUp },
  { name: 'Cuentas', href: '/accounts', icon: Wallet },
  { name: 'Categorías', href: '/categories', icon: Tags },
];
```

```tsx
const renderNavItem = (item: (typeof primaryNavItems)[number]) => {
  const Icon = item.icon;
  const isActive = pathname === item.href;

  return (
    <Link
      key={item.href}
      href={item.href}
      onClick={() => {
        if (isMobile()) closeSidebar();
      }}
      className={/* ...idéntico al actual... */}
    >
      {/* ...idéntico al actual (ícono + label + tooltip flotante)... */}
    </Link>
  );
};
```

```tsx
<nav className="mt-6 space-y-1.5 px-3">
  {primaryNavItems.map(renderNavItem)}
</nav>
<div
  className={`border-border/40 mx-3 my-3 border-t ${isSidebarOpen ? '' : 'mx-4'}`}
  role="separator"
/>
<nav className="space-y-1.5 px-3">
  {secondaryNavItems.map(renderNavItem)}
</nav>
```

(El `role="separator"` es gratis y correcto semánticamente para un divisor puramente visual —
consistente con el nivel de cuidado de accesibilidad que Fase 9 ya estableció en el resto del
proyecto, aunque el ROADMAP no lo pida explícitamente para este ítem puntual.)

**Pasos:**
1. Reemplazar `navItems` por `primaryNavItems` + `secondaryNavItems` (arriba).
2. Extraer `renderNavItem` como función local dentro del componente `Sidebar` (necesita acceso a
   `pathname`, `isMobile`, `closeSidebar`, `isSidebarOpen` — todos ya disponibles en el scope del
   componente).
3. Reemplazar el único `<nav>` (línea 115-156) por los dos bloques + separador, arriba.
4. Verificar que el resaltado de ruta activa (`isActive`) sigue funcionando igual para los 6 ítems
   en su nuevo orden — no depende del índice ni del array de origen, solo de `pathname ===
   item.href`, así que no debería requerir ningún cambio adicional.

**Testing:** sin suite de frontend. Verificación manual: los 6 ítems siguen navegables, en el
orden nuevo (Dashboard, Transacciones, Presupuestos, separador, Analítica, Cuentas, Categorías);
el separador es visible tanto con el sidebar expandido como colapsado; la ruta activa se resalta
igual que antes sin importar en qué grupo esté.

**Criterio de aceptación:**
- Los 6 ítems del array original siguen presentes, ninguno removido.
- El orden visual es: Dashboard, Transacciones, Presupuestos — separador — Analítica, Cuentas,
  Categorías.
- Ninguna ruta cambia de URL ni de comportamiento — es un cambio puramente de presentación del
  menú.

---

## Resumen de archivos tocados por ítem

| Ítem | Backend | Frontend |
|---|---|---|
| 11.1 bugs multi-moneda | `api/dashboard.py`, `schemas/schemas.py` (`BudgetProgress.currency`), `tests/test_dashboard.py` (nuevo) | `types/api.ts`, `components/charts/BudgetRing.tsx`, `app/(dashboard)/page.tsx`, `app/(dashboard)/analytics/page.tsx` |
| 11.2 `actualizar_transaccion` | `api/transactions.py` | — |
| 11.3 balance de flujo mensual | `api/dashboard.py` (`obtener_resumen`), `schemas/schemas.py` (`DashboardSummary.monthly_flow_balance`) | `app/(dashboard)/page.tsx`, `types/api.ts`, `components/ui/SummaryCard.tsx` (si se agrega `size`) |
| 11.4 barras por categoría | — | `components/charts/CategoryBreakdownBars.tsx` (nuevo), `app/(dashboard)/page.tsx`, `lib/queryKeys.ts` |
| 11.5 vista secundaria de cuentas | `api/accounts.py` (`GET /summary`, nuevo), `tests/test_dashboard.py` o `tests/test_accounts.py` (nuevo) | `app/(dashboard)/accounts/page.tsx`, `lib/queryKeys.ts` |
| 11.6 ocultar edición de categorías | — | `app/(dashboard)/categories/page.tsx` |
| 11.7 reagrupar sidebar | — | `components/Sidebar.tsx` |
| Cruzando toda la fase | — | `docs/TODO.md` (marcar resueltos 2 ítems), `backend/docs/API_REFERENCE.md` + `frontend/docs/API_CONTRACT.md` (documentar `GET /accounts/summary`, `currency` en `budgets-progress`/`cashflow-series`/`category-distribution`, `monthly_flow_balance` en `/summary` — por convención de `CLAUDE.md` sobre contratos de API compartidos) |

---

## Cierre

Este documento no implementa ningún cambio en el repositorio — es el desglose ejecutable de la
sección "Fase 11" de `docs/ROADMAP.md` (ya reescrita el 2026-08-23), con archivos, líneas y
decisiones de diseño concretas para que un backend-engineer/frontend-engineer pueda partir
directamente de aquí sin tener que re-explorar el código para tomar las mismas decisiones. Todos
los hallazgos de este documento (estado real del sidebar y del dashboard, ausencia de `currency`
en 3 schemas de respuesta, ausencia de un total en `accounts/page.tsx`, ausencia de cualquier UI
para fijar `monthly_income`, ausencia de `tests/test_dashboard.py`, el test `xfail` ya existente
para el bug de `actualizar_transaccion`) fueron verificados contra el código real de `backend/` y
`frontend/` el 2026-08-23, no inferidos del texto del ROADMAP. Ningún archivo del repositorio
fuera de `docs/specs/fase_11_spec.md` fue modificado al producir este documento.
