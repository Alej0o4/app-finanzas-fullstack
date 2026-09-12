# Spec — Fase 17: Análisis por cuenta y presupuestos multi-moneda

> Plan de implementación detallado para los 2 ítems de Fase 17 del [ROADMAP](../ROADMAP.md).
> Fuente de verdad de alcance: `docs/ROADMAP.md` (sección "Fase 17 — Análisis por cuenta y
> presupuestos multi-moneda", decidida en sesión de grilling del 2026-09-12). Este documento
> no cambia el alcance ahí definido — lo desglosa en tareas ejecutables, con archivos
> concretos, esquemas de datos y decisiones de diseño numeradas, para que
> backend-engineer/frontend-engineer puedan partir directamente de aquí.
>
> **No implementa nada.** Ningún archivo del repositorio fuera de
> `docs/specs/fase_17_spec.md` fue modificado al producir este documento. Los hallazgos de
> exploración de código fueron verificados directamente contra `backend/` y `frontend/` el
> 2026-09-12 (lectura completa de `accounts.py`, `budgets.py`, `dashboard.py`,
> `models.py`/`schemas.py`, `accounts/[id]/page.tsx`, `budgets/page.tsx`,
> `CategoryDonutChart.tsx`, `CategoryBreakdownBars.tsx`, `BudgetRing.tsx`,
> `queryKeys.ts`, `types/api.ts`), no inferidos del texto del ROADMAP. Las decisiones de
> arquitectura más delicadas (P1–P6 abajo) fueron evaluadas por el agente `software-architect`
> a partir de ese mismo código, con cita de línea exacta.

Estado del repo al momento de escribir esto (2026-09-12): Fases 7–16 están completas, más la
parada de correcciones de UX post-pivote. Fase 17 es la primera fase post-MVP decidida en una
sesión de grilling con una semana de uso real desde celular — no en el mismo lote que Fases
8–16 (que ya venían escritas desde el pivote del 2026-08-22). A diferencia de esas fases,
Fase 17 depende de dos decisiones de diseño previas que el ROADMAP no resuelve del todo (ver
Hallazgos 5 y 6) y de una fase posterior aún no implementada (Fase 19, ver Hallazgo 6) — este
documento resuelve ambas para poder entregar Fase 17 sin bloquearse en ninguna de las dos.

---

## Hallazgos de exploración que corrigen/precisan el ROADMAP

1. **`accounts/[id]/page.tsx` hoy no tiene ningún gráfico, confirmado línea por línea.**
   `frontend/app/(dashboard)/accounts/[id]/page.tsx` (422 líneas): balance actual +
   `opening_balance` (Fase 16 §16.4) + botón "Recalcular saldo"
   (`POST /accounts/{id}/reconcile`) + historial plano de transacciones con
   editar/eliminar vía modal. Cero analítica, exactamente como dice el encabezado de la
   fase en el ROADMAP.

2. **`budgets/page.tsx` no tiene campo de moneda, confirmado en el payload exacto que arma el
   formulario.** `handleSubmit` (línea 96-121) construye
   `{category_id, amount_limit, month, year, is_recurring}` — sin `currency`.
   `BudgetBase.currency: str = "COP"` (`backend/app/schemas/schemas.py:240`) nunca se toca
   desde la UI, tal como dice el ROADMAP. Curiosamente, `frontend/types/api.ts:144` ya
   declara `BudgetPayload.currency?: string` — el tipo lo anticipaba, pero ni el formulario
   ni el submit lo usan todavía.

3. **El índice único de `Budget` no incluye `currency` — esto vuelve cosmético el selector de
   moneda del ítem 2 si no se corrige.** `backend/app/models/models.py:99-129`: el índice
   único parcial `uq_budgets_user_category_period_active` es
   `(user_id, category_id, month, year)` — sin moneda, `WHERE deleted_at IS NULL`. Hoy, con
   moneda fija en `"COP"` para todos, esto es invisible. En cuanto el ítem 2 permita elegir
   moneda, un usuario con cuentas en COP y USD que intente crear un presupuesto de "Mercado"
   en USD, teniendo ya uno en COP para el mismo mes, choca contra el mismo `400` que ya
   prueba `backend/tests/test_budgets.py:27` (`test_duplicate_budget_via_api_returns_400...`)
   — pensado para detectar duplicados reales, no para bloquear monedas distintas. El ROADMAP
   dice explícitamente "no se agrega `account_id` a `Budget`" pero no discute este punto del
   índice — moneda y cuenta son dimensiones distintas (varias cuentas pueden compartir
   moneda), así que ensanchar el índice no reabre esa decisión.

4. **El motor de alertas de Fase 13 tiene el mismo punto ciego, y es más grave porque falla en
   silencio.** `backend/app/core/budget_alerts.py:97-118`
   (`evaluate_budget_thresholds_for_category`) busca el presupuesto con `.first()` filtrado
   solo por `(user_id, category_id, month, year)` — sin `currency`. En cuanto el índice único
   permita dos presupuestos por categoría/período en monedas distintas (Hallazgo 3), esta
   función solo evalúa umbrales para **uno** de los dos — el otro nunca dispara aviso de 80%
   ni de 100%, sin ningún error visible. `dashboard.obtener_progreso_presupuestos`
   (`dashboard.py:134-140`) ya trata "presupuestos del período" como lista (`.all()`) — el
   motor de alertas debe seguir el mismo patrón, no es un diseño nuevo.

5. **La superficie de moneda en `dashboard.py` ya tiene precedente, pero no cubre
   `budgets-progress`.** `GET /dashboard/cashflow-series` y `GET /dashboard/category-distribution`
   (`dashboard.py:175-284`) ya aceptan `currency: str | None = Query(None, ...)`, con fallback a
   `current_user.preferred_currency` (Decisión 11.1.1 de Fase 11). `GET /dashboard/budgets-progress`
   (líneas 126-172) no tiene ningún query param hoy — siempre calcula todos los presupuestos
   del mes en curso, cada uno en su propia moneda vía `Budget.currency`.

6. **La "balance del mes" de la vista por cuenta cita literalmente un componente que no
   existe todavía — Fase 17 depende de una porción del trabajo de Fase 19.** El ROADMAP dice
   que la card de balance de `accounts/[id]` usa "el mismo componente que rediseña Fase 19 más
   abajo" (Fase 19, ítem 2: "Rediseño de la card 'Balance del mes'"). Fase 19 **no está
   implementada** (checkbox sin marcar en `docs/ROADMAP.md`). Hoy, la card "Balance del mes"
   del dashboard (`frontend/app/(dashboard)/page.tsx:157-206`) es JSX inline dentro de
   `<SummaryCard>` — no es un componente extraído ni reutilizable, e incluye lógica propia
   (formulario inline para fijar `monthly_income` cuando es `null`) que no aplica al caso de
   una cuenta individual. Resuelto en Decisión 17.1.2 abajo: se construye un componente nuevo,
   propio de esta fase, sin tocar ni anticipar el rediseño de Fase 19.

7. **`CategoryDonutChart` no es reutilizable "tal cual" para una vista de solo lectura — el
   ROADMAP pide reusar un componente cuya razón de ser choca con una decisión ya tomada en
   Fase 11.** `frontend/components/CategoryDonutChart.tsx` exige que el padre controle
   `categoryType`/`onCategoryTypeChange`, `netMode`/`onNetModeChange` y
   `hiddenCategories`/`onHiddenCategoriesChange` — los controles de tipo/modo
   (`ChartControlsPopover`, líneas ~102-156) y la leyenda clicable para ocultar categorías
   (líneas ~212-249) están renderizados **dentro** del propio componente, no inyectados por
   un toolbar externo — no hay forma de "usarlo sin exponer los controles" sin bifurcarlo.
   Más importante: `docs/specs/fase_11_spec.md` (Decisión 11.4.1) ya resolvió exactamente esta
   pregunta con una razón explícita: *"son audiencias distintas (exploración detallada con
   toggles de período/tipo/neto en Analítica, vistazo rápido sin controles en el dashboard)"*
   — por eso existe `CategoryBreakdownBars` en primer lugar. `accounts/[id]` es, hoy, exactamente
   ese tipo de página de "vistazo rápido" (Hallazgo 1) — la misma audiencia que el dashboard, no
   la de `/analytics`. Resuelto en Decisión 17.1.1: se omite `CategoryDonutChart` en la vista por
   cuenta.

8. **Precedente de orden de rutas en `accounts.py`, ya establecido y a seguir sin cambios.**
   `accounts.py:44-46` y `64-66` documentan en comentario por qué `/summary` y
   `/{account_id}/reconcile` se declaran **antes** de `/{account_id}` — FastAPI resuelve rutas
   en orden de declaración. El endpoint nuevo de este documento
   (`/{account_id}/monthly-summary`, Decisión 17.1.4) tiene una profundidad de ruta distinta a
   `/{account_id}` (dos segmentos contra uno), así que no hay colisión posible
   independientemente del orden — pero se declara junto a `/{account_id}/reconcile`, agrupando
   las sub-rutas de una cuenta puntual, por legibilidad, no por necesidad.

9. **`GET /transactions/` ya soporta `account_id` como filtro opcional** (precedente ya
   existente, usado hoy por `accounts/[id]/page.tsx` para el historial de movimientos) — mismo
   patrón que se extiende a `cashflow-series`/`category-distribution` en la Decisión 17.1.3.

---

## Decisiones de arquitectura (P1–P6, evaluadas por `software-architect` el 2026-09-12)

Estas seis preguntas no tenían una respuesta única y correcta derivable solo del ROADMAP —
requerían leer el código real y, en el caso de P1/P6, ponderar contra una decisión de fase
anterior. Se documentan aquí antes del desglose por ítem porque varias decisiones de
implementación (abajo) dependen de ellas.

- **P1 (Hallazgo 7).** Omitir `CategoryDonutChart` en `accounts/[id]`; usar solo
  `CategoryBreakdownBars` + `BudgetRing`. Ver Decisión 17.1.1.
- **P2 (Hallazgo 6).** Construir un componente presentacional nuevo y pequeño para "balance del
  mes por cuenta", sin tocar la card inline del dashboard ni anticipar el diseño de Fase 19.
  Ver Decisión 17.1.2.
- **P3 (Hallazgo 3).** Ensanchar el índice único a
  `(user_id, category_id, month, year, currency)` vía migración Alembic, y corregir el
  `.first()` de `budget_alerts.py` a `.all()` + loop (Hallazgo 4) — no basta con documentar la
  limitación, Fase 17 es la que cambia la premisa que la hacía inofensiva. Ver Decisión 17.2.2.
- **P4 (Hallazgos 3/5).** El `spent` de cada `BudgetProgress` en la vista por cuenta **no** se
  recalcula restringido a esa cuenta — se sigue calculando exactamente como hoy (agregado por
  moneda a través de todas las cuentas del usuario). Solo se filtra **qué filas** se muestran
  (`currency == account.currency`). Razón: `Budget` no tiene `account_id` — es "esta
  categoría, en esta moneda", nunca "el presupuesto de esta cuenta"; recalcular por cuenta
  haría que el mismo `budget_id` mostrara porcentajes distintos según qué cuenta lo consulta,
  divergiendo del invariante que el Hallazgo 4 de `docs/specs/fase_11_spec.md` ya estableció
  (dashboard y motor de alertas comparten una sola definición de "cuánto gasté" para no
  desacordar nunca). Ver Decisión 17.1.3.
- **P5 (Hallazgos 5/8/9).** Superficie de API concreta — ver Decisión 17.1.3 (`account_id` en
  `category-distribution` — no se toca `cashflow-series`, ver nota de la decisión), Decisión
  17.1.4 (`GET /accounts/{account_id}/monthly-summary`, nuevo, en `accounts.py`) y Decisión
  17.2.3 (`currency` en `budgets-progress`).
- **P6 (Hallazgo 2).** El selector de moneda de presupuestos es una restricción de UI, no de
  backend — `BudgetCreate.currency` sigue aceptando cualquier string, sin validar contra las
  cuentas reales del usuario. Ver Decisión 17.2.1 para la justificación completa.

---

## Orden de ejecución recomendado

```
1. Backend: ensanchar el índice único de Budget + fix del motor de alertas (§17.2.2)
   ── Independiente de todo lo demás; es una corrección de un bug latente que el propio
      ítem 2 activa. Conviene primero porque el ítem 2 (selector de moneda) sin esto es
      cosmético (Hallazgo 3) — enviar el selector antes de este fix dejaría una ventana
      donde la UI promete algo que el backend todavía rechaza.

2. Backend: selector de moneda en presupuestos — query param en budgets-progress +
   payload/schema (§17.2.1, §17.2.3, §17.2.5)
   ── Depende de (1): sin el índice ensanchado, crear un segundo presupuesto en otra
      moneda para la misma categoría/período sigue fallando con 400.

3. Frontend: selector de moneda en budgets/page.tsx (§17.2.4)
   ── Depende de (2) para tener el campo `currency` real en el contrato de API.

4. Backend: account_id en category-distribution + nuevo endpoint monthly-summary (§17.1.3,
   §17.1.4)
   ── Independiente de (1)-(3); toca `dashboard.py` y `accounts.py`, no `budgets.py`.
      Puede hacerse en paralelo a los pasos 1-3 por otro agente/persona.

5. Frontend: analítica por cuenta en accounts/[id] (§17.1.1, §17.1.2, §17.1.5)
   ── Depende de (4) para los datos, y de (3) solo en el sentido de que la vista por cuenta
      filtra presupuestos por moneda (§17.1.3) — reutiliza el query param de (2), así que
      construirla antes de (2)/(3) dejaría esa parte sin datos reales que mostrar hasta que
      el otro ítem exista, pero no bloquea el desarrollo del resto de la página.
```

Los pasos 1-3 y 4-5 son, en la práctica, dos líneas de trabajo independientes que pueden
asignarse a dos agentes backend-engineer/frontend-engineer en paralelo — mismo criterio que
`docs/specs/fase_11_spec.md` aplicó a sus ítems sin dependencia cruzada.

---

## 17.1 Analítica por cuenta en `accounts/[id]`

### Backend

**Decisión 17.1.1 — `CategoryDonutChart` queda fuera de esta fase.** Ver Hallazgo 7 y P1. La
vista por cuenta reutiliza únicamente `CategoryBreakdownBars` (alimentado por
`category-distribution`) y `BudgetRing` (alimentado por `budgets-progress`). Esto es una
corrección explícita del texto del ROADMAP, no una omisión — mismo criterio que la reescritura
de Fase 11 (sidebar) y la Decisión 10.1.4 de Fase 10: no implementar literalmente un ítem del
ROADMAP cuando el propio código ya documenta, con una decisión previa y su razón, por qué esa
lectura literal reabre un problema ya resuelto.

**Decisión 17.1.3 — `account_id` opcional en `GET /dashboard/category-distribution`,
validado contra la propiedad de la cuenta; NO se toca `cashflow-series`.** El ROADMAP nombra
tres componentes a reusar (Hallazgo 7 resuelve que son en realidad dos): `CategoryBreakdownBars`
consume `category-distribution`; `BudgetRing` consume `budgets-progress` (Decisión 17.1.3
continúa abajo). Ningún componente de esta fase consume una serie temporal
(`CashflowChart`/`cashflow-series` no está en la lista del ROADMAP) — se deja `cashflow-series`
sin tocar, a propósito, para no construir una superficie de API que ningún componente de este
alcance usa (mismo criterio de disciplina de alcance que Fase 11 §11.4 aplicó al no forzar
`CategoryDonutChart` sobre el dashboard).

```python
# backend/app/api/dashboard.py — obtener_distribucion_categorias
@router.get("/category-distribution", response_model=list[schemas.CategoryDistributionData])
def obtener_distribucion_categorias(
    start_date: datetime,
    end_date: datetime,
    type: str = Query("expense", pattern="^(income|expense)$"),
    neto: bool = Query(False),
    currency: str | None = Query(None),
    account_id: int | None = Query(None, description="Filtra a las transacciones de una sola cuenta"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if account_id is not None:
        cuenta = (
            db.query(models.Account)
            .filter(models.Account.id == account_id, models.Account.user_id == current_user.id)
            .first()
        )
        if not cuenta:
            raise HTTPException(status_code=404, detail="La cuenta no existe o no tienes permisos.")

    filtro_moneda = currency or current_user.preferred_currency or "COP"
    # ... construir el filtro existente y, si account_id is not None, agregar
    # models.Transaction.account_id == account_id a la cláusula .filter(...) de ambas ramas
    # (neto=True / neto=False) — el resto de la función no cambia.
```

`account_id` y `currency` son ortogonales — **no** se deriva la moneda automáticamente de la
cuenta cuando se pasa `account_id`. El fallback existente (`currency or preferred_currency`)
seguiría siendo incorrecto para este caso (la moneda de una cuenta no tiene por qué coincidir
con la preferida del usuario) — el frontend, que ya tiene el objeto `Account` cargado
(`accounts/[id]/page.tsx` ya hace `useQuery` sobre `accounts/${id}`), debe pasar
`currency=account.currency` explícitamente junto con `account_id`. Se evita así agregar lógica
de derivación implícita nueva al backend por un ahorro marginal en el caller.

**Decisión 17.1.4 — nuevo endpoint `GET /accounts/{account_id}/monthly-summary`, en
`accounts.py`, no en `dashboard.py`.** El "balance del mes" de una cuenta
(`ingreso_de_esa_cuenta_este_mes − gasto_de_esa_cuenta_este_mes`) es un cálculo genuinamente
distinto a `GET /dashboard/summary` (Hallazgo 6/10 de la sección de arquitectura): ese endpoint
usa `User.monthly_income` (un valor declarado una sola vez, global, no por cuenta) — una cuenta
no tiene su propio "ingreso declarado". A diferencia de `monthly_flow_balance` (que puede ser
`null` si el usuario no fijó su ingreso), este valor **siempre se calcula** — se deriva
enteramente de transacciones reales de esa cuenta, sin ningún dato declarado de por medio. Vive
en `accounts.py` porque necesita la misma verificación de pertenencia de una sola cuenta que ya
tiene el patrón `reconciliar_cuenta` (Fase 16 §16.4), que `dashboard.py` no tiene.

```python
# backend/app/schemas/schemas.py
class AccountMonthlySummary(BaseModel):
    currency: str
    monthly_income: Decimal
    monthly_expense: Decimal
    monthly_flow_balance: Decimal  # monthly_income - monthly_expense; nunca None


# backend/app/api/accounts.py — declarado junto a reconciliar_cuenta, antes de GET /{account_id}
@router.get("/{account_id}/monthly-summary", response_model=schemas.AccountMonthlySummary)
def obtener_resumen_mensual_cuenta(
    account_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)
):
    cuenta = (
        db.query(models.Account)
        .filter(models.Account.id == account_id, models.Account.user_id == current_user.id)
        .first()
    )
    if not cuenta:
        raise HTTPException(status_code=404, detail="La cuenta no existe o no tienes permisos.")

    hoy = datetime.now(UTC)
    primer_dia = datetime(hoy.year, hoy.month, 1)
    ultimo_dia_mes = calendar.monthrange(hoy.year, hoy.month)[1]
    ultimo_dia = datetime(hoy.year, hoy.month, ultimo_dia_mes, 23, 59, 59)

    def _total(tipo: str) -> Decimal:
        return (
            db.query(func.sum(models.Transaction.amount))
            .filter(
                models.Transaction.account_id == account_id,
                models.Transaction.type == tipo,
                models.Transaction.date >= primer_dia,
                models.Transaction.date <= ultimo_dia,
                models.Transaction.deleted_at.is_(None),
            )
            .scalar()
        ) or Decimal("0.00")

    ingreso = _total("income")
    gasto = _total("expense")

    return {
        "currency": cuenta.currency,
        "monthly_income": ingreso,
        "monthly_expense": gasto,
        "monthly_flow_balance": ingreso - gasto,
    }
```

El filtro `deleted_at.is_(None)` sigue el mismo patrón que `reconciliar_cuenta` (Fase 16
§16.4) — no contar transacciones borradas lógicamente en el cálculo.

**Decisión 17.1.3 (continuación) — `budgets-progress` filtrado por moneda para la vista por
cuenta.** Ver §17.2.3 abajo — el mismo query param `currency` que se agrega en el ítem 2 se
reutiliza aquí; no hay un query param separado "por cuenta" para presupuestos (P4: `Budget` no
tiene `account_id`, así que "presupuestos de esta cuenta" en realidad significa "presupuestos en
la moneda de esta cuenta").

### Frontend

**Decisión 17.1.2 — nuevo componente `AccountMonthlyBalanceCard`
(`frontend/components/charts/`), usado solo por `accounts/[id]` en esta fase — la card inline
del dashboard (`app/(dashboard)/page.tsx:157-206`) NO se toca.** Ver Hallazgo 6 y P2. Contrato
mínimo, puramente presentacional (sin fetching propio, sin estado de "no definido" — el dato
que consume siempre existe, a diferencia de `monthly_flow_balance` del dashboard):

```tsx
interface AccountMonthlyBalanceCardProps {
  label: string;
  income: number;
  expense: number;
  currency: string;
  isLoading: boolean;
}
```

Calcula `balance = income - expense` internamente; reusa `SummaryCard` (`size="lg" elevated`,
mismo patrón visual que la card del dashboard) para no introducir un segundo lenguaje visual de
tarjeta destacada. Este componente es intencionalmente más simple que la card del dashboard
(sin formulario inline de "fijar ingreso") porque no le hace falta — no hay estado "sin definir"
posible para el balance de una cuenta. Cuando Fase 19 rediseñe la card del dashboard, es esa
fase la que decide si unifica ambos usos — no se anticipa ese diseño aquí.

**Archivo a modificar:** `frontend/app/(dashboard)/accounts/[id]/page.tsx`.

**Pasos:**
1. Nuevo `useQuery` para `GET /accounts/{id}/monthly-summary`:
   ```tsx
   const { data: monthlySummary, isLoading: loadingMonthlySummary } =
     useQuery<AccountMonthlySummary>({
       queryKey: queryKeys.accounts.monthlySummary(id as string),
       queryFn: async () => (await api.get(`accounts/${id}/monthly-summary`)).data,
     });
   ```
2. Nuevo `useQuery` para `category-distribution` filtrado por `account_id` + `currency` de la
   cuenta, mes en curso, `type=expense` (mismos parámetros que ya usa el dashboard general,
   ver `docs/specs/fase_11_spec.md` §11.4):
   ```tsx
   const { data: categoryBreakdown, isLoading: loadingCategoryBreakdown } = useQuery<
     CategoryDistributionItem[]
   >({
     queryKey: queryKeys.accounts.categoryBreakdown(id as string),
     queryFn: async () =>
       (
         await api.get('dashboard/category-distribution', {
           params: {
             start_date: primerDiaDelMes,
             end_date: hoy,
             type: 'expense',
             account_id: Number(id),
             currency: account?.currency,
           },
         })
       ).data,
     enabled: !!account, // necesita account.currency ya cargado
   });
   ```
3. Nuevo `useQuery` para `budgets-progress?currency=${account.currency}` (ver §17.2.3):
   ```tsx
   const { data: budgetsProgress, isLoading: loadingBudgets } = useQuery<BudgetProgress[]>({
     queryKey: queryKeys.accounts.budgetsProgress(id as string),
     queryFn: async () =>
       (await api.get('dashboard/budgets-progress', { params: { currency: account?.currency } }))
         .data,
     enabled: !!account,
   });
   ```
4. Renderizar, entre el bloque de saldo actual y el historial de movimientos: la
   `<AccountMonthlyBalanceCard>`, luego un grid de `<BudgetRing>` (uno por fila de
   `budgetsProgress`, mismo mapeo que `dashboard/page.tsx:269-278`), luego
   `<CategoryBreakdownBars data={categoryBreakdown} isLoading={loadingCategoryBreakdown} />`.
   Estados vacíos: reusar `EmptyState` con los mismos mensajes que ya usa el dashboard para
   estas mismas piezas (consistencia de tono, `frontend/docs/COMPONENTS_GUIDE.md`).

**Archivos a modificar:**
- `frontend/app/(dashboard)/accounts/[id]/page.tsx` (pasos 1-4).
- `frontend/components/charts/AccountMonthlyBalanceCard.tsx` (nuevo, Decisión 17.1.2).
- `frontend/lib/queryKeys.ts`: agregar bajo `accounts`:
  ```ts
  monthlySummary: (id: string | number) => ['account-monthly-summary', id] as const,
  categoryBreakdown: (id: string | number) => ['account-category-breakdown', id] as const,
  budgetsProgress: (id: string | number) => ['account-budgets-progress', id] as const,
  ```
  Claves propias por cuenta (no reutilizar `queryKeys.dashboard.categoryBreakdown()` ni
  `queryKeys.budgets.progress()` — llevan parámetros distintos y deben invalidarse por
  separado cuando cambian los datos de una cuenta puntual, mismo criterio que
  `frontend/docs/STATE_AND_FETCHING.md`: "cada pantalla de negocio debe tener su propia
  `queryKey`").
- `frontend/types/api.ts`: nueva interfaz
  ```ts
  export interface AccountMonthlySummary {
    currency: string;
    monthly_income: number;
    monthly_expense: number;
    monthly_flow_balance: number;
  }
  ```

**Testing:**

Backend (`backend/tests/test_accounts.py`, ya existe):
- `GET /accounts/{id}/monthly-summary` de una cuenta con ingresos y gastos este mes devuelve
  `monthly_flow_balance == monthly_income - monthly_expense`, en la moneda de la cuenta.
- Cuenta sin transacciones este mes: los tres montos son `0.00`, no error ni `null`.
- Cuenta de otro usuario: `404`.
- `GET /dashboard/category-distribution?account_id=X`: filtra correctamente a las transacciones
  de esa cuenta (test con dos cuentas del mismo usuario, misma categoría, verificar que cada
  `account_id` devuelve solo su propio total). `account_id` de una cuenta ajena: `404`.

Frontend: sin suite automatizada (igual que fases anteriores, `docs/TODO.md` "Tests de
frontend" sigue en backlog). Verificación manual: `accounts/[id]` muestra balance del mes,
barras por categoría y anillos de presupuesto filtrados correctamente cuando el usuario tiene
más de una cuenta en monedas distintas; el dashboard general (`/`) no cambia ningún
comportamiento (diff de `dashboard/page.tsx`: cero líneas tocadas por este ítem).

**Criterio de aceptación:**
- `accounts/[id]` muestra: balance del mes de esa cuenta, barras de gasto por categoría de esa
  cuenta, y anillos de presupuesto filtrados a la moneda de esa cuenta.
- Ningún componente nuevo de esta página expone controles de filtro propios (ni tipo/modo, ni
  ocultar categorías) — es una vista de solo lectura, consistente con `CategoryBreakdownBars`.
- El dashboard general no gana un selector de cuenta ni cambia su agregación (decisión ya
  tomada en Fase 11, reafirmada).

---

## 17.2 Selector de moneda en el formulario de presupuestos

### Backend

**Decisión 17.2.1 — sin validación de moneda en el backend; el selector es una restricción de
UI.** Ver P6. `BudgetCreate.currency` sigue aceptando cualquier string, sin `Enum` ni chequeo
contra las cuentas del usuario. Razones: (1) el radio de impacto de un mismatch es bajo —
`spent_por_categoria_y_moneda` simplemente devuelve `0` para una moneda sin transacciones, el
presupuesto queda visible pero en cero, no se pierde ni corrompe nada; (2) no hay precedente de
whitelisting de moneda en el proyecto — `Account.currency`, `User.preferred_currency` y
`Budget.currency` son todos strings libres hoy, y agregar un chequeo solo para este campo sería
una inconsistencia puntual, contraria al criterio de "sin capa de servicios, lógica de negocio
delgada a esta escala" de `CLAUDE.md`; (3) ni siquiera cerraría el caso del todo — un
presupuesto válido al crearse puede quedar huérfano si el usuario borra después su única cuenta
en esa moneda, así que una validación en creación no garantiza el invariante a largo plazo de
todas formas. El desplegable, al derivarse de las monedas reales del usuario (Decisión 17.2.4),
ya hace que un mismatch solo sea posible vía uso directo de la API — categoría de riesgo ya
aceptada en otros lados del proyecto (`docs/TODO.md`).

**Decisión 17.2.2 — ensanchar el índice único de `Budget` a
`(user_id, category_id, month, year, currency)`, vía migración Alembic, y corregir
`evaluate_budget_thresholds_for_category` de `.first()` a `.all()` + loop.** Ver Hallazgos 3 y
4, y P3. Esto no es documentar una limitación aceptada — Fase 17 es la que cambia la premisa
que la hacía inofensiva (hoy todo presupuesto es `"COP"`, así que el índice actual nunca
colisiona con nada legítimo). Sin este cambio, el selector de moneda del ítem 2 es cosmético
para exactamente los usuarios multi-moneda a los que está dirigido.

```python
# backend/app/models/models.py, clase Budget
__table_args__ = (
    Index(
        "uq_budgets_user_category_period_active",
        "user_id",
        "category_id",
        "month",
        "year",
        "currency",  # 🆕 Fase 17 §17.2.2 — permite un presupuesto por (categoría, período)
                     # POR moneda, no uno total sin importar la moneda.
        unique=True,
        postgresql_where=text("deleted_at IS NULL"),
        sqlite_where=text("deleted_at IS NULL"),
    ),
)
```

```python
# backend/app/core/budget_alerts.py — evaluate_budget_thresholds_for_category
presupuestos = (
    db.query(models.Budget)
    .filter(
        models.Budget.user_id == user_id,
        models.Budget.category_id == category_id,
        models.Budget.month == month,
        models.Budget.year == year,
    )
    .all()  # 🆕 antes: .first() — con moneda en el índice, puede haber más de uno
)
for presupuesto in presupuestos:
    # ... el cuerpo existente de evaluación de umbrales, sin cambios, ahora dentro del loop
```

**Migración Alembic:** `alembic revision --autogenerate -m "fase_17_budget_currency_unique_index"`
— revisar a mano que autogenerate detecte el reemplazo del índice parcial existente (mismo
cuidado que ya documentó Fase 13/14 para índices únicos parciales — no siempre se infieren
limpios). Sin backfill de datos: los presupuestos existentes ya tienen `currency="COP"` por
default, así que ensanchar el índice no puede introducir una colisión retroactiva (todos los
existentes ya son únicos por `(user_id, category_id, month, year)` solo, que es un
sub-conjunto más estricto).

**Decisión 17.2.3 — nuevo query param `currency: str | None` en `GET /dashboard/budgets-progress`;
filtra filas, no recalcula `spent`.** Ver Hallazgo 5, P4 y P5.

```python
# backend/app/api/dashboard.py
@router.get("/budgets-progress", response_model=list[schemas.BudgetProgress])
def obtener_progreso_presupuestos(
    currency: str | None = Query(None, description="Si se pasa, solo devuelve presupuestos en esa moneda"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    ...  # sin cambios hasta construir progreso_lista
    if currency is not None:
        progreso_lista = [p for p in progreso_lista if p["currency"] == currency]
    return progreso_lista
```

Filtro aplicado sobre la lista ya construida (no en la query SQL) — el volumen de presupuestos
por usuario es pequeño (uno por categoría/moneda/período), así que no hay razón para
complicar la query cuando un filtro en memoria es igual de correcto y más simple de leer.
`spent` de cada fila filtrada **no cambia** — sigue siendo el agregado cruzado de todas las
cuentas del usuario en esa moneda (Decisión P4), consistente con que `Budget` no tiene
`account_id`.

**Decisión 17.2.5 — `actualizar_presupuesto` (PUT) empieza a asignar
`presupuesto_db.currency`, y ambos handlers (`POST`/`PUT`) filtran su chequeo de duplicado por
`currency` también.** Dos gaps concretos encontrados al releer `budgets.py` con el cambio de
índice en mente:

1. `crear_presupuesto` (líneas 34-46) ya hace una verificación manual de duplicado **antes**
   de depender del `IntegrityError` de la base — esa query filtra por
   `(user_id, category_id, month, year)` sin `currency`. Sin el `currency` en este filtro, la
   verificación manual seguiría rechazando con "Ya existe un presupuesto..." un segundo
   presupuesto en otra moneda, aunque el índice de la base ya lo permitiera — hay que agregar
   `models.Budget.currency == presupuesto.currency` a este filtro.
2. `actualizar_presupuesto` (líneas 98-133) actualiza `amount_limit`, `month`, `year`,
   `category_id`, `is_recurring` — **nunca `currency`**, aunque el body (`schemas.BudgetBase`)
   ya lo incluye (con default `"COP"`). Es el mismo patrón de bug que
   `AccountUpdate.currency` (pendiente en `docs/TODO.md`) — un campo que el schema acepta pero
   el handler ignora en silencio. Se agrega
   `presupuesto_db.currency = presupuesto_actualizado.currency`. Como editar la moneda de un
   presupuesto ahora puede chocar contra el índice único ensanchado (si ya existe otro
   presupuesto para esa categoría/período en la nueva moneda), `actualizar_presupuesto` gana el
   mismo `try/except IntegrityError` que ya tiene `crear_presupuesto` (líneas 49-57) — hoy no
   tiene ninguno, así que ese choque terminaría en un `500` no manejado en vez de un `400`
   explícito.

```python
# backend/app/api/budgets.py — crear_presupuesto, filtro de duplicado
presupuesto_existente = (
    db.query(models.Budget)
    .filter(
        models.Budget.user_id == current_user.id,
        models.Budget.category_id == presupuesto.category_id,
        models.Budget.month == presupuesto.month,
        models.Budget.year == presupuesto.year,
        models.Budget.currency == presupuesto.currency,  # 🆕
    )
    .first()
)
```

```python
# backend/app/api/budgets.py — actualizar_presupuesto
presupuesto_db.amount_limit = presupuesto_actualizado.amount_limit
presupuesto_db.month = presupuesto_actualizado.month
presupuesto_db.year = presupuesto_actualizado.year
presupuesto_db.category_id = presupuesto_actualizado.category_id
presupuesto_db.currency = presupuesto_actualizado.currency  # 🆕
presupuesto_db.is_recurring = presupuesto_actualizado.is_recurring

try:
    db.commit()
except IntegrityError:
    db.rollback()
    raise HTTPException(
        status_code=400,
        detail="Ya existe un presupuesto para esta categoría, moneda, mes y año.",
    ) from None
db.refresh(presupuesto_db)
return presupuesto_db
```

### Frontend

**Decisión 17.2.4 — selector de moneda derivado de `GET /accounts/`, no una lista fija.**
`budgets/page.tsx` ya carga `categories` con `useQuery` — se agrega un `useQuery` equivalente
sobre `accounts/` (o se reutiliza `queryKeys.accounts.all()` si ya está en caché desde otra
página, mismo `staleTime` de 1 min de `QueryProvider`) y se deriva la lista de monedas únicas
de `account.currency` con un `Set`. Si el usuario tiene una sola moneda entre sus cuentas, el
selector igual se muestra (consistencia con el resto del formulario, que siempre expone sus
campos) pero con una sola opción — no se oculta condicionalmente, para no introducir un caso de
UI oculta que Fase 10 §10.2 ya evitó para el selector de cuenta de captura por otra razón
(ahí sí se oculta con 1 cuenta porque es *la* cuenta por defecto; acá no hay un default de
moneda equivalente).

**Archivo a modificar:** `frontend/app/(dashboard)/budgets/page.tsx`.

**Pasos:**
1. Nuevo `useQuery<Account[]>` (mismo patrón que `categories`):
   ```tsx
   const { data: accounts } = useQuery<Account[]>({
     queryKey: queryKeys.accounts.all(),
     queryFn: async () => (await api.get('accounts/')).data,
   });
   const availableCurrencies = Array.from(new Set(accounts?.map((a) => a.currency) ?? []));
   ```
2. Nuevo estado `currency`, inicializado a la primera moneda disponible (o `'COP'` si
   `accounts` todavía no cargó):
   ```tsx
   const [currency, setCurrency] = useState('COP');
   ```
3. `openCreateModal`: `setCurrency(availableCurrencies[0] ?? 'COP')`.
   `openEditModal`: `setCurrency(budget.currency)` (hoy no se setea nada, el campo no existe
   en el estado del componente).
4. Nuevo `<Select>` en el formulario, entre "Categoría" y "Monto Máximo" (agrupado con
   categoría porque ambos determinan qué presupuesto es, a diferencia de monto/mes que son el
   valor del límite):
   ```tsx
   <Select
     label="Moneda"
     required
     value={currency}
     onChange={(e) => setCurrency(e.target.value)}
     className="bg-background"
   >
     {availableCurrencies.map((c) => (
       <option key={c} value={c}>
         {c}
       </option>
     ))}
   </Select>
   ```
5. `handleSubmit`: agregar `currency` al payload de `saveMutation.mutate({...})`.

**Archivos a modificar:**
- `frontend/app/(dashboard)/budgets/page.tsx` (pasos 1-5).
- `frontend/types/api.ts`: `BudgetPayload.currency` ya existe como opcional
  (`currency?: string`, línea 144) — se vuelve efectivamente siempre-enviado desde este ítem en
  adelante; no hace falta cambiar el tipo a requerido (mantenerlo opcional no rompe nada y
  evita un cambio de tipo que no aporta nada en tiempo de compilación, dado que el propio
  formulario ya lo envía siempre). `Budget.currency` (línea 39) ya existe, sin cambios.

**Testing:**

Backend (`backend/tests/test_budgets.py`, ya existe):
- Crear dos presupuestos para la misma categoría/mes/año en monedas distintas: ambos `201`,
  ya no chocan con el `400` de duplicado.
- Crear dos presupuestos para la misma categoría/mes/año/moneda (idéntico en las 4
  dimensiones): sigue devolviendo `400` — no se rompe el caso que
  `test_duplicate_budget_via_api_returns_400_not_500` ya prueba.
- Editar un presupuesto cambiando su `currency` a una que ya tiene otro presupuesto para esa
  categoría/período: `400`, no `500` (verifica el `try/except` nuevo de
  `actualizar_presupuesto`).
- Editar un presupuesto sin cambiar `currency`: el valor persiste sin cambios (regresión —
  antes de este ítem, el campo simplemente nunca se tocaba, así que este es el primer test que
  ejercita la línea nueva).

Backend (`backend/tests/test_budget_alerts.py`, ya existe): dos presupuestos para la misma
categoría/período en monedas distintas, cada uno con su propio gasto cruzando el 80% —
verificar que **ambos** generan su aviso (regresión directa del fix de Hallazgo 4 — antes de
este fix, `.first()` solo evaluaba uno de los dos).

Backend (`backend/tests/test_dashboard.py`, ya existe): `GET /dashboard/budgets-progress?currency=USD`
devuelve solo los presupuestos en USD, con el mismo `spent` que sin el filtro (verifica
Decisión P4 — no hay recálculo, solo filtro).

Frontend: sin suite automatizada. Verificación manual: el selector de moneda muestra las
monedas reales de las cuentas del usuario; crear un presupuesto en una moneda distinta a uno
ya existente para la misma categoría/mes no falla; editar la moneda de un presupuesto existente
la persiste.

**Criterio de aceptación:**
- Un usuario con cuentas en COP y USD puede crear un presupuesto de la misma categoría en
  ambas monedas para el mismo mes, sin error.
- El motor de alertas de Fase 13 evalúa umbrales para todos los presupuestos de una
  categoría/período, sin importar cuántas monedas distintas existan.
- `docs/TODO.md`: agregar la entrada de este hallazgo si no se completa por completo en el
  mismo PR (el gap de `actualizar_presupuesto.currency`, mismo patrón que la entrada existente
  de `AccountUpdate.currency`) — o marcarla resuelta junto con esta si se corrige aquí.

---

## Resumen de archivos tocados por ítem

| Ítem | Backend | Frontend |
|---|---|---|
| 17.1 analítica por cuenta | `api/accounts.py` (`GET /{id}/monthly-summary`, nuevo), `api/dashboard.py` (`account_id` en `category-distribution`), `schemas/schemas.py` (`AccountMonthlySummary`), `tests/test_accounts.py` | `components/charts/AccountMonthlyBalanceCard.tsx` (nuevo), `app/(dashboard)/accounts/[id]/page.tsx`, `lib/queryKeys.ts`, `types/api.ts` |
| 17.2 moneda en presupuestos | `models/models.py` (índice único ensanchado), `core/budget_alerts.py` (`.first()` → `.all()`), `api/dashboard.py` (`currency` en `budgets-progress`), `api/budgets.py` (filtro de duplicado + `actualizar_presupuesto.currency` + `try/except`), migración Alembic nueva, `tests/test_budgets.py`, `tests/test_budget_alerts.py`, `tests/test_dashboard.py` | `app/(dashboard)/budgets/page.tsx` |
| Cruzando toda la fase | — | `docs/TODO.md` (si aplica, ver criterio de aceptación de 17.2), `backend/docs/API_REFERENCE.md` + `frontend/docs/API_CONTRACT.md` (documentar `account_id`/`currency` nuevos en `category-distribution`/`budgets-progress`, y el endpoint nuevo `GET /accounts/{id}/monthly-summary` — convención de `CLAUDE.md` sobre contratos de API compartidos) |

---

## Cierre

Este documento no implementa ningún cambio en el repositorio — es el desglose ejecutable de la
sección "Fase 17" de `docs/ROADMAP.md`, con archivos, esquemas y decisiones de diseño concretas
para que un backend-engineer/frontend-engineer puedan partir directamente de aquí. A diferencia
de fases anteriores, dos de sus decisiones (P1/Decisión 17.1.1 y P3/Decisión 17.2.2) corrigen
explícitamente el texto del ROADMAP en vez de solo precisarlo — la primera porque pide reusar un
componente cuya razón de ser Fase 11 ya descartó para este mismo tipo de vista; la segunda
porque el ROADMAP no discute una consecuencia estructural (el índice único de `Budget`) que el
propio ítem 2 activa. Ambas fueron evaluadas por el agente `software-architect` contra el código
real (no contra el texto del ROADMAP en aislado) el 2026-09-12, con cita de línea exacta en cada
caso. Todos los hallazgos de este documento fueron verificados contra el código real de
`backend/` y `frontend/` el 2026-09-12 — ningún archivo del repositorio fuera de
`docs/specs/fase_17_spec.md` fue modificado al producirlo.
