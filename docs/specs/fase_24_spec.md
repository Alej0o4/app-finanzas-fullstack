# Spec — Fase 24: UX — fallos silenciosos del flujo principal

> Plan de implementación detallado para los 4 ítems (checkboxes) de Fase 24 del
> [ROADMAP](../ROADMAP.md) (sección "Fase 24 — UX: fallos silenciosos del flujo principal",
> líneas ~987–1014, originada en la auditoría completa del 2026-09-15 — `CODE_REVIEW.md` raíz,
> secciones UX y 🟠 Bugs confirmados de `docs/TODO.md`). Este documento no cambia el alcance ahí
> definido — lo desglosa en tareas ejecutables, con archivos concretos, snippets de código reales
> y decisiones de arquitectura numeradas, separadas explícitamente en Backend/Frontend por ítem,
> para que agentes `backend-engineer`/`frontend-engineer` distintos puedan tomar cada mitad en
> paralelo.
>
> **No implementa nada.** Ningún archivo del repositorio fuera de `docs/specs/fase_24_spec.md`
> fue modificado al producir este documento. Los hallazgos fueron verificados directamente contra
> el código el 2026-09-18: lectura completa de `frontend/app/(dashboard)/page.tsx`,
> `frontend/components/charts/CategoryBreakdownBars.tsx`, `frontend/components/charts/
> BudgetRing.tsx`, `frontend/components/CashflowChart.tsx`, `frontend/components/
> CategoryDonutChart.tsx` (precedente de `isError` sin retry), `frontend/components/
> NotificationBell.tsx` (precedente de `isError`), `frontend/components/ui/EmptyState.tsx`,
> `frontend/components/ui/Input.tsx`, `frontend/components/ui/CategoryIcon.tsx`,
> `frontend/components/QueryProvider.tsx` (política de retry por defecto de TanStack Query),
> `frontend/app/(dashboard)/accounts/page.tsx` (modal de edición completo), `frontend/lib/
> hooks/useSetMonthlyIncome.ts`, `frontend/types/api.ts`, `frontend/package.json` (confirmando
> que no hay test runner de frontend configurado), `backend/app/api/accounts.py` (los 5
> endpoints completos), `backend/app/api/dashboard.py` (las 4 queries completas),
> `backend/app/core/budget_alerts.py` (`spent_por_categoria_y_moneda`), `backend/app/core/
> database.py` (mecanismo del filtro global de soft-delete), `backend/app/models/models.py`
> (modelo `Account`, sin índice único de `currency`), `backend/app/schemas/schemas.py`
> (`AccountBase`/`AccountUpdate`/`BudgetProgress`/`CategoryDistributionData`), `backend/app/api/
> categories.py`, `backend/app/api/transactions.py` (herencia de `currency` por transacción),
> `backend/tests/test_accounts.py`, `backend/tests/test_soft_delete.py`, `backend/tests/
> test_dashboard.py`, `backend/tests/conftest.py` (fixtures `make_account`/`make_category`),
> `backend/docs/API_REFERENCE.md` y `frontend/docs/API_CONTRACT.md` (secciones de Cuentas y
> Dashboard), `docs/specs/fase_12_spec.md` §12.8 (patrón de validación por campo), `docs/specs/
> fase_17_spec.md`/`fase_22_spec.md` (precedentes de guards multi-moneda) y `CODE_REVIEW.md` +
> `docs/TODO.md` — no inferidos del texto del ROADMAP en aislado.

Estado del repo al momento de escribir esto (2026-09-18): Fases 7–23 completas (Fase 23 cerró el
account takeover de Google OAuth, ver `docs/specs/fase_23_spec.md`). Fase 24 nace de la misma
auditoría del 2026-09-15 que originó la 23, pero acota su alcance a UX (no seguridad): tres bugs
de "falla silenciosa" en el flujo de mayor tráfico (dashboard + su formulario inline) más dos
bugs de datos de bajo esfuerzo (`AccountUpdate.currency`, `category_icon`). Ninguno es
bloqueante de otra fase — a diferencia de la 23, esta puede resolverse en cualquier orden interno
sin dependencias cruzadas reales (ver "Orden de ejecución recomendado").

---

## Problem Statement

El dashboard es la pantalla que el usuario abre primero y con más frecuencia, y hoy no distingue
"todavía no tengo datos" de "algo se rompió": un fallo de red en cualquiera de sus 4 queries, o
un dato inválido en su único formulario inline, se resuelven con un `return` silencioso — sin
aviso, sin botón de reintentar, sin error de campo. A eso se suman dos bugs de datos de bajo
esfuerzo (una edición de cuenta que no aplica el cambio de moneda sin avisar, y un ícono
genérico donde debería haber uno real) que refuerzan la misma sensación de "la app no me dice
qué pasó".

## User Stories

1. Como usuario que abre el dashboard con la red caída (o el backend caído), quiero ver un
   aviso claro por cada sección afectada y un botón de reintentar, en vez de una pantalla vacía
   indistinguible de "todavía no tengo presupuestos/transacciones".
2. Como usuario que escribe un valor inválido (vacío o negativo) en el campo de ingreso mensual
   del dashboard, quiero ver el error marcado junto al campo, no que el formulario no haga nada
   visible al enviarlo.
3. Como usuario que edita la moneda de una cuenta desde una integración que sí envía ese campo
   (hoy no hay ninguna en la UI, ver Hallazgo 3), quiero que el cambio se aplique de verdad o que
   me digan explícitamente por qué no puede aplicarse — no un `200 OK` que no cambia nada.
4. Como usuario con presupuestos por categoría, quiero ver el ícono real de cada categoría en el
   desglose de gastos del dashboard, igual que ya lo veo en los anillos de presupuesto.

---

## Hallazgos de exploración que corrigen/precisan el ROADMAP

1. **Las 4 queries del dashboard ya no viven exactamente en `page.tsx:45-64` — el rango real es
   45-79, y la de `category-distribution` es la que más se movió.** El ROADMAP cita el rango de
   cuando se escribió (16-09), pero código posterior (probablemente ajustes de Fase 19-22) corrió
   las líneas: `summary` (45-48), `budgetsProgress` (50-53), `recentTransactionsData` (55-60), y
   `categoryBreakdown` (64-79, la más larga por los parámetros `start_date`/`end_date`/`type`/
   `currency`). Las 4 siguen siendo exactamente las que el ROADMAP nombra — ningún hallazgo de
   alcance, solo de línea exacta.

2. **El formulario de ingreso mensual está exactamente donde dice el ROADMAP, con su guard
   custom en una sola línea.** `frontend/app/(dashboard)/page.tsx:202-235` — el `<form>` (línea
   202) no tiene `noValidate`, el `<Input type="number" required min={0} ...>` (línea 219-230)
   deja que el navegador intercepte primero, y el guard manual (línea 207) es:

   ```tsx
   if (monthlyIncomeInput.trim() === '' || Number.isNaN(parsed) || parsed < 0) return;
   ```

   Sin `setFieldErrors`, sin `toast`, sin `ref`/foco — un `return` puro. Coincide 1:1 con la
   descripción del ROADMAP y de `CODE_REVIEW.md`.

3. **El ROADMAP describe `AccountUpdate.currency` como si el frontend ya lo enviara y el backend
   lo ignorara — falso contra el código actual: el frontend HOY NUNCA envía `currency` en este
   PUT.** `frontend/app/(dashboard)/accounts/page.tsx:84-97` (`updateAccountMutation`) tipa su
   payload como `{ name: string; type: string }` — sin `currency` ni `highlighted` — y
   `handleUpdate` (líneas 152-165) construye literalmente `data: { name: editAccountName, type:
   editAccountType }`. El modal de edición (líneas 394-427) no tiene ningún campo de moneda en su
   JSX. Verificado con `grep -rn "api.put(\`accounts"` en todo `frontend/`: un solo call site, el
   de arriba. **Esto no invalida el ítem** (el ROADMAP y `CODE_REVIEW.md` documentan
   correctamente que el *schema* lo permite y el *endpoint* lo ignora — un futuro selector de
   moneda, o cualquier caller directo de la API, chocaría con el mismo silencio), pero sí cambia
   su impacto real: hoy es una inconsistencia de contrato sin superficie de UI que la dispare, no
   un bug que un usuario esté pisando en producción. Ver Decisión C3 (frontend: sin cambios,
   justificado).

4. **Encontrado al verificar el Hallazgo 3: `PUT /accounts/{id}` ya tiene, HOY, el mismo patrón
   de bug para `highlighted` que el ROADMAP quiere evitar para `currency` — y por el mismo
   mecanismo.** `backend/app/api/accounts.py:196-198`:

   ```python
   cuenta.name = cuenta_actualizada.name
   cuenta.type = cuenta_actualizada.type
   cuenta.highlighted = cuenta_actualizada.highlighted
   ```

   `AccountUpdate` hereda `highlighted: bool = False` de `AccountBase` (`schemas.py:209`) — un
   *default*, no un campo requerido. Como el frontend nunca envía `highlighted` en este PUT
   (Hallazgo 3), Pydantic completa el campo faltante con `False` en cada request, y la línea de
   arriba lo aplica sin condición: **cada edición de nombre/tipo de una cuenta destacada la
   des-destaca silenciosamente**, hoy, en producción. No es uno de los 4 ítems de esta fase (no
   está en el ROADMAP ni en `CODE_REVIEW.md`), pero es la prueba concreta de que "escribir el
   campo del schema sin más" —la lectura ingenua del ítem 3— reproduciría el mismo bug para
   `currency` en cuanto exista cualquier caller que omita ese campo (el propio frontend actual
   sería justo ese caller si algún día agrega un selector de moneda sin también enviar
   `highlighted`). Ver Decisión C1 — la solución elegida para el ítem 3 corrige este bug gratis,
   sin ampliar el alcance pedido (es un prerrequisito técnico, no una funcionalidad nueva).

5. **El filtro global de soft-delete ya cubre `eliminar_cuenta`'s guard de transacciones —
   confirma que ese guard, tal como está escrito hoy, solo cuenta transacciones ACTIVAS, no
   "cualquier fila".** `backend/app/core/database.py:46-50`:

   ```python
   @event.listens_for(Session, "do_orm_execute")
   def _filtro_global_soft_delete(execute_state):
       if execute_state.is_select and not execute_state.is_column_load...:
           execute_state.statement = execute_state.statement.options(
               with_loader_criteria(SoftDeleteMixin, lambda cls: cls.deleted_at.is_(None), include_aliases=True)
           )
   ```

   `Transaction` hereda `SoftDeleteMixin` (`models.py:78`), así que **todo** `db.query(...)`
   ORM-enabled sobre `Transaction` ya excluye filas borradas automáticamente — incluido el guard
   literal de `eliminar_cuenta` (`accounts.py:229`: `db.query(models.Transaction).filter(...).
   first()`), que no lleva ningún `.filter(deleted_at.is_(None))` explícito porque no lo
   necesita. Esto es el precedente exacto que el enunciado de esta tarea pidió verificar: el
   guard de borrado de cuenta ya bloquea solo cuando hay **transacciones activas**, no
   históricas-pero-borradas. La Decisión C2 (guard de moneda) reutiliza el mismo patrón, con el
   mismo alcance, sin necesitar ningún filtro adicional.

6. **Las 4 queries de `dashboard.py` filtran por `Transaction.currency` (por transacción), no
   por `Account.currency` — confirmado leyendo las 4 funciones completas, no solo el nombre.**
   `obtener_resumen` (`summary`, líneas 69-100): agrupa ingresos/gastos por
   `models.Transaction.currency`. `obtener_progreso_presupuestos` (`budgets-progress`, líneas
   133-188) delega en `spent_por_categoria_y_moneda` (`budget_alerts.py:32-`), que agrupa por
   `(category_id, currency)` explícitamente — "Fase 11 §11.1" en su propio docstring.
   `obtener_serie_flujo_caja` (`cashflow-series`, línea 224) y `obtener_distribucion_categorias`
   (`category-distribution`, línea 281) filtran ambas con `models.Transaction.currency ==
   filtro_moneda`. **Estas 4 vistas ya son seguras frente a una cuenta que termine con
   transacciones de más de una moneda** — es exactamente el filtrado estricto que Fase 11/17 ya
   construyeron para este problema recurrente del proyecto.

7. **Pero dos endpoints de `accounts.py` (ninguno de los 4 del dashboard) NO filtran por moneda
   de transacción — y son los que sí se romperían si `currency` cambia libremente sobre una
   cuenta con historial.** `reconciliar_cuenta` (líneas 68-112) y `obtener_resumen_mensual_cuenta`
   / `AccountMonthlySummary` (líneas 119-169, alimenta `AccountMonthlyBalanceCard` de Fase 17)
   suman `models.Transaction.amount` filtrando solo por `account_id`/`type`/fecha —
   **nunca** por `Transaction.currency` — y etiquetan el resultado con `cuenta.currency` (la
   moneda ACTUAL de la cuenta):

   ```python
   # accounts.py:146-159, obtener_resumen_mensual_cuenta._total()
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
   ...
   return {"currency": cuenta.currency, "monthly_income": ingreso, ...}
   ```

   Si `PUT /accounts/{id}` aplicara `currency` sin ningún guard, una cuenta que cambia de moneda
   mientras conserva transacciones activas en la moneda vieja haría que estos dos endpoints sumen
   montos de dos monedas distintas y los etiqueten con la moneda nueva — **exactamente el patrón
   de bug multi-moneda que Fases 11/17/19 ya corrigieron en otros lugares** (ver
   `docs/ROADMAP.md`, "3 bugs multi-moneda" de Fase 11). Esta es la base concreta de la Decisión
   C2 (bloquear, no permitir libremente).

8. **`CategoryDistributionData` no trae `category_icon`, confirmado contra el schema real —
   y el frontend hoy ni siquiera intenta pasar un ícono.** `backend/app/schemas/schemas.py:
   378-384` (`CategoryDistributionData`: `category_id`, `category_name`, `total` — sin
   `category_icon`) vs. `BudgetProgress` (líneas 315-322), que sí lo tiene desde antes.
   `frontend/components/charts/CategoryBreakdownBars.tsx:64-67`:

   ```tsx
   {/* El contrato de category-distribution no incluye ícono; CategoryIcon cae
       al fallback genérico mientras eso no cambie. */}
   <CategoryIcon fallback={<Wallet size={16} className="text-text-muted" />} />
   ```

   No pasa ningún prop `icon` — el comentario ya documenta la causa exacta. `CategoryIcon`
   (`components/ui/CategoryIcon.tsx:6`) acepta `icon?: string | null`, y `BudgetRing.tsx:93` ya
   lo usa así (`<CategoryIcon icon={categoryIcon} size={16} />`) — el fix de frontend es agregar
   ese mismo prop, no construir nada nuevo.

9. **No existe hoy ningún componente compartido de "error + reintentar"; el precedente más
   cercano (`CashflowChart`/`CategoryDonutChart`, usados en Analítica) tiene `isError` pero SIN
   botón de retry.** `frontend/components/CashflowChart.tsx:96-99`:

   ```tsx
   {isError ? (
     <div className="border-border text-text-muted flex h-72 items-center justify-center rounded-xl border border-dashed text-sm">
       No se pudo cargar el flujo de caja.
     </div>
   ) : ...
   ```

   Mismo patrón en `CategoryDonutChart.tsx:212` y en `NotificationBell.tsx:159-162` (sin botón
   tampoco). El ROADMAP pide explícitamente "retry visible" — ninguno de estos 3 precedentes lo
   tiene todavía, así que el ítem 24.1 agrega ese botón por primera vez en el proyecto, no lo
   copia de otro lado. Se decide reutilizar `EmptyState` (ya usado por 2 de las 4 secciones del
   dashboard) en vez de construir un componente nuevo — ver Decisión A2.

10. **TanStack Query reintenta automáticamente 3 veces antes de que `isError` se vuelva
    verdadero — confirmado en `frontend/components/QueryProvider.tsx:8-18`, que no sobrescribe
    `retry` (default de la librería, v5.101 según `package.json:15`).** El botón "Reintentar"
    que este ítem agrega solo aparece, por diseño ya existente en toda la app, después de que las
    3 reintentas automáticas fallen — es el mismo comportamiento que ya rige `CashflowChart`/
    `CategoryDonutChart`/`NotificationBell` hoy. No hace falta (ni se recomienda) tocar la
    política de retry global para este ítem — sería un cambio de alcance mayor sin pedido
    explícito del ROADMAP.

11. **No hay ningún test hoy para `PUT /accounts/{id}` ni para el guard de transacciones de
    `DELETE /accounts/{id}` en particular — confirmado con `grep -n "def test_" backend/tests/
    test_accounts.py`: 14 tests, ninguno cubre `actualizar_cuenta`.** `test_soft_delete.py` cubre
    la desaparición de una cuenta borrada de los listados, pero ningún test ejercita el mensaje
    "No se puede eliminar la cuenta porque tiene transacciones asociadas." (`accounts.py:231-233`)
    directamente. Los tests de la Decisión C2 son cobertura neta nueva, no una corrección de un
    test existente (a diferencia de Fase 23).

12. **No hay test runner de frontend configurado — confirmado en `frontend/package.json`: sin
    script `test`, sin `vitest`/`jest` en dependencias.** Los ítems 24.1, 24.2 y la mitad
    frontend de 24.4 quedan con testing manual/checklist, igual que el resto del frontend del
    proyecto — no es una omisión de esta spec, es el estado real de la suite (mismo criterio que
    Fase 23 §G5 usó implícitamente al no proponer tests de frontend).

---

## Decisiones de arquitectura (evaluadas por `software-architect` el 2026-09-18)

### 24.1 — `isError` + retry en las 4 queries del dashboard (A1–A4)

**A1 — Reutilizar `EmptyState` agregándole un prop `action?: ReactNode` opcional, en vez de
construir un componente de error nuevo.** `EmptyState` (`components/ui/EmptyState.tsx`) ya se
usa para los estados vacíos de `budgetsProgress` y `recentTransactions` en el propio
`page.tsx` (líneas 260-265 y 319-323) — agregarle un slot de acción opcional (retrocompatible,
nadie más lo usa hoy) cubre el estado de error de esas dos secciones sin introducir un segundo
patrón visual para lo mismo. Mismo criterio que la Decisión 12.8.1 de Fase 12 ("conectar lo que
ya existe, no construir de más").

```tsx
// frontend/components/ui/EmptyState.tsx
interface EmptyStateProps {
  icon: ReactNode;
  message: string;
  description?: string;
  action?: ReactNode; // 🆕 Fase 24 §24.1 — botón opcional (ej. "Reintentar")
}

export default function EmptyState({ icon, message, description, action }: EmptyStateProps) {
  return (
    <div className="text-text-muted flex flex-col items-center p-12 text-center">
      <div className="mb-3">{icon}</div>
      <p className="text-sm font-medium">{message}</p>
      {description && <p className="text-text-muted/70 mt-1 text-xs">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
```

**A2 — Las 4 secciones se tratan distinto según si ya usaban `EmptyState`, no con una sola
plantilla cop/pegada 4 veces:**

- `budgetsProgress` y `recentTransactions`: agregar una rama `isError` ANTES de la rama de
  "sin datos", con `EmptyState` + `action`.
- `summary` (la card principal): no usa `EmptyState` hoy (usa `Skeleton`/`SummaryCard`
  directamente) — se agrega un bloque de error inline, mismo tono visual que
  `CashflowChart.tsx:96-99` (icono `AlertCircle` + mensaje + botón), en el lugar donde hoy se
  renderiza `<Skeleton>`/`<SummaryCard>`. No se modifica `SummaryCard` (no tiene noción de
  error, y agregársela para un solo caller sería sobre-diseño).
- `categoryBreakdown`: `CategoryBreakdownBars` recibe dos props nuevos (`isError`, `onRetry`),
  mismo shape que `CashflowChart`/`CategoryDonutChart` ya usan para `isError` (Hallazgo 9) —
  consistencia de interfaz entre los 3 componentes de gráficos del dashboard/analítica.

**A3 — El retry es literalmente `refetch()` de cada `useQuery`, sin lógica adicional.** Cada uno
de los 4 `useQuery` de `page.tsx:45-79` se re-desestructura para exponer `isError`/`refetch`:

```tsx
const {
  data: summary,
  isLoading: loadingSummary,
  isError: summaryError,
  refetch: refetchSummary,
} = useQuery<DashboardSummary>({
  queryKey: queryKeys.dashboard.summary(),
  queryFn: async () => (await api.get('dashboard/summary')).data,
});
```

Mismo patrón para las otras 3. El botón de cada bloque de error llama a su propio `refetch`
(`onClick={() => refetchBudgets()}`, etc.) — no hay un "reintentar todo" global: cada sección
puede fallar independientemente (por ejemplo, `recentTransactions` pega a `GET /transactions/`,
un endpoint distinto de los otros 3) y cada una se recupera independiente.

**A4 — Copys, uno por sección, mismo tono que `CashflowChart.tsx:98` ("No se pudo cargar el
flujo de caja"):**

| Sección | Mensaje |
|---|---|
| `summary` | "No se pudo cargar el resumen del mes." |
| `budgetsProgress` | "No se pudo cargar el progreso de presupuestos." |
| `recentTransactions` | "No se pudieron cargar las transacciones recientes." |
| `categoryBreakdown` | "No se pudo cargar el desglose por categoría." |

Todas con el mismo botón: `<Button variant="secondary" size="sm" onClick={...}>Reintentar</Button>`.

- *Alternativa descartada:* un solo banner de error global arriba de toda la página en vez de 4
  bloques independientes. Descartada porque las 4 queries son independientes entre sí (fallos de
  endpoints distintos, en momentos distintos) — un banner único no permite reintentar solo la
  que falló, y esconde qué sección específica se rompió.
- *Alternativa descartada:* mostrar un `toast.error` en vez de (o además de) el bloque inline.
  Descartada por redundante — el bloque inline ya es persistente y visible sin depender de que
  el usuario viera el toast a tiempo (los toasts de `sonner` desaparecen solos), y es el mismo
  criterio que ya usan `CashflowChart`/`CategoryDonutChart`/`NotificationBell`.

### 24.2 — Validación del formulario de ingreso mensual inline (B1–B2)

**B1 — Mismo patrón exacto de Fase 12 §12.8 (Decisión 12.8.1/12.8.2): `noValidate` + un
`fieldErrors` local + foco por `ref`, sin librería nueva.** Es un formulario de un solo campo, así
que no hace falta un objeto `fieldErrors` completo — alcanza con un `useState<string | null>` y
un `ref` sobre el único `<Input>`:

```tsx
// frontend/app/(dashboard)/page.tsx
const [monthlyIncomeInput, setMonthlyIncomeInput] = useState('');
const [monthlyIncomeError, setMonthlyIncomeError] = useState<string | null>(null); // 🆕
const monthlyIncomeRef = useRef<HTMLInputElement>(null); // 🆕

// ...dentro del <form>, reemplaza el onSubmit actual (líneas 204-213):
<form
  className="mt-2 w-full space-y-2"
  noValidate // 🆕
  onSubmit={(e) => {
    e.preventDefault();
    const parsed = Number(monthlyIncomeInput);
    if (monthlyIncomeInput.trim() === '' || Number.isNaN(parsed) || parsed < 0) {
      setMonthlyIncomeError('Ingresa un monto válido (0 o mayor).'); // 🆕, antes: return silencioso
      return monthlyIncomeRef.current?.focus(); // 🆕
    }
    setMonthlyIncomeError(null);
    setMonthlyIncomeMutation.mutate(parsed, {
      onSuccess: () => toast.success('Ingreso mensual guardado'),
      onError: (error) => toast.error(getApiError(error)),
    });
  }}
>
  ...
  <Input
    ref={monthlyIncomeRef} // 🆕
    type="number"
    inputMode="decimal"
    min={0}
    step="0.01"
    aria-label="Ingreso mensual"
    placeholder={`Ej. 3000000 (${preferredCurrency})`}
    value={monthlyIncomeInput}
    onChange={(e) => setMonthlyIncomeInput(e.target.value)}
    error={monthlyIncomeError ?? undefined} // 🆕
    className="bg-background"
  />
```

Se quita el `required` nativo (línea 222 actual) — con `noValidate` ya no aplica, y la validación
JS de arriba ya cubre "vacío" (`trim() === ''`).

**B2 — El error se limpia al reintentar enviar, no al tipear (mismo criterio que Fase 12: sin
debounce, sin validar on-change).** `setMonthlyIncomeError(null)` solo corre dentro del
`onSubmit`, cuando el nuevo valor sí pasa la validación — consistente con cómo el resto de la app
maneja `fieldErrors` (se recalculan enteros en cada submit, Decisión 12.8.1).

- *Alternativa descartada:* migrar este campo a un `fieldErrors: Record<string, string>` como los
  formularios multi-campo de Fase 12. Descartada por desproporcionado — es un solo campo, un
  objeto de un solo error sería la misma complejidad con una capa extra de indirección sin
  beneficio.

### 24.3 — `PUT /accounts/{id}` aplica cambios de `currency` (C1–C4)

**C1 — Prerrequisito: `actualizar_cuenta` pasa a semántica de actualización parcial real,
aplicando solo los campos presentes en el body (`model_fields_set`), no todos los campos del
schema con sus defaults de Pydantic de por medio.** Sin este cambio, aplicar `currency` a ciegas
reproduciría exactamente el bug ya confirmado para `highlighted` (Hallazgo 4): con el frontend
actual, que nunca envía `currency` en este PUT (Hallazgo 3), cada edición de nombre/tipo
resetearía la moneda de la cuenta a `"COP"` (el default de `AccountBase.currency`) sin que nadie
lo pidiera — una regresión nueva, peor que el bug actual (que al menos deja la moneda intacta).
Este cambio es la razón de que 24.3 aparezca en la sección "Backend" con más profundidad que un
simple `cuenta.currency = cuenta_actualizada.currency`; no es alcance ampliado, es el
prerrequisito mínimo para que el ítem no rompa nada.

```python
# backend/app/api/accounts.py — actualizar_cuenta(), reemplaza líneas 196-198
campos_enviados = cuenta_actualizada.model_fields_set

if "name" in campos_enviados:
    cuenta.name = cuenta_actualizada.name
if "type" in campos_enviados:
    cuenta.type = cuenta_actualizada.type
if "highlighted" in campos_enviados:
    cuenta.highlighted = cuenta_actualizada.highlighted
```

(El bloque de `currency` va aparte, ver C2 — necesita el guard antes de aplicarse.)

**C2 — La aplicación de `currency` se bloquea con `400` cuando el cambio es real (valor distinto
del actual) Y la cuenta tiene al menos una transacción activa — Opción (a) del enunciado de esta
tarea, mismo guard y mismo status code que `eliminar_cuenta` (Hallazgo 5), NO la opción (b)
"permitir libremente".** Razonamiento, verificado contra el código real, no asumido:

- Las 4 queries del dashboard (Hallazgo 6) ya filtran por `Transaction.currency` — para ELLAS,
  permitir el cambio libremente sería seguro. Pero `reconciliar_cuenta` y
  `obtener_resumen_mensual_cuenta` (Hallazgo 7) NO filtran por moneda de transacción y etiquetan
  su suma con `cuenta.currency` — para ESOS DOS, un cambio libre de moneda sobre una cuenta con
  transacciones activas en la moneda vieja produce una suma mezclada y mal etiquetada, silenciosa
  (ningún error, solo un número incorrecto). Es el mismo patrón de bug que motivó los 3 fixes
  multi-moneda de Fase 11 y el filtrado estricto de Fase 17/19 — el proyecto ya decidió, varias
  veces, que "una cuenta con transacciones de más de una moneda mezcladas sin que el código lo
  anticipe" es un bug de datos real, no un caso de borde ignorable.
- El precedente más cercano en el propio código (`eliminar_cuenta`, Hallazgo 5) ya bloquea con
  `400` una operación que "no tiene sentido con historial existente" — cambiar la moneda de una
  cuenta que ya tiene transacciones es la misma categoría de operación: deja el historial en un
  estado que ningún cálculo del proyecto anticipa. Bloquear reutiliza un patrón ya aceptado por
  el proyecto en vez de inventar uno nuevo.
- Gracias al filtro global de soft-delete (Hallazgo 5), el guard solo necesita mirar
  transacciones ACTIVAS — el mismo query que `eliminar_cuenta` ya usa, sin ningún filtro adicional
  de `deleted_at`.
- El guard solo dispara si el valor de `currency` en el body es distinto del ya guardado — una
  edición que reenvía la misma moneda (o que no toca el campo en absoluto, gracias a C1) nunca se
  bloquea, así que renombrar o retipear una cuenta con transacciones sigue funcionando exactamente
  igual que hoy.

```python
# backend/app/api/accounts.py — actualizar_cuenta(), bloque nuevo
if "currency" in campos_enviados and cuenta_actualizada.currency != cuenta.currency:
    tiene_transacciones = db.query(models.Transaction).filter(models.Transaction.account_id == account_id).first()
    if tiene_transacciones:
        raise HTTPException(
            status_code=400,
            detail="No se puede cambiar la moneda de una cuenta con transacciones asociadas.",
        )
    cuenta.currency = cuenta_actualizada.currency
```

**C3 — Frontend: sin cambios para este ítem — no se agrega ningún selector de moneda al modal de
edición.** Justificación, no solo "no aplica": (1) el ROADMAP y `CODE_REVIEW.md` piden que el
*endpoint* aplique el campo que el *schema* ya acepta, no que se construya una UI nueva para
dispararlo — es exactamente el criterio de "corrección sobre alcance ampliado" que esta tarea
pide explícitamente. (2) Con la semántica de C1, el frontend actual (que nunca envía `currency`,
Hallazgo 3) sigue comportándose exactamente igual que hoy — el campo simplemente no se toca. (3)
Agregar un selector de moneda a una cuenta ya usada abre una pregunta de producto propia (¿qué
pasa con el saldo ya expresado en la moneda vieja? ¿se re-etiqueta o se convierte?) que ni el
ROADMAP ni el enunciado de esta tarea piden resolver — queda anotado en "Out of scope". El efecto
observable de este ítem, tal como está acotado, es exclusivamente para callers directos de la API
(API keys, Postman, una futura integración) — no hay ninguna superficie de UI hoy que lo ejercite,
y eso es correcto dado el alcance pedido, no un defecto de esta spec.

**C4 — El código de error es `400` con `detail` como string plano (no el patrón `detail.code`
JSON que usa `EMAIL_NOT_VERIFIED`), por consistencia con `eliminar_cuenta`, la operación gemela
más cercana en el mismo archivo.** El patrón `detail.code` se reserva en este proyecto para casos
donde el frontend necesita bifurcar lógica sobre el tipo de error (ver `CLAUDE.md`, login con
email sin verificar) — acá el frontend ya maneja cualquier `400` genérico vía
`toast.error(getApiError(error))` en `updateAccountMutation.onError` (`accounts/page.tsx:94-96`,
sin cambios), así que un string plano es suficiente y consistente con el resto de guards de
`accounts.py`.

- *Alternativa descartada:* Opción (b) del enunciado — permitir el cambio libremente, confiando
  en que las 4 queries del dashboard ya filtran por moneda de transacción. Descartada porque el
  Hallazgo 7 confirma dos endpoints reales (`reconciliar_cuenta`,
  `obtener_resumen_mensual_cuenta`) que NO tienen ese filtro y se romperían en silencio —
  "permitir libremente" no es seguro contra el código real, solo contra las 4 queries que el
  enunciado pidió revisar explícitamente.
- *Alternativa descartada:* Opción (c) variante "permitir con confirmación explícita del
  usuario". Descartada por desproporcionada para el tamaño del fix (1h estimada en el ROADMAP) y
  porque agregar un flag de confirmación es, otra vez, construir una superficie de producto nueva
  que nadie pidió — el bloqueo simple ya resuelve el riesgo real sin fricción adicional para el
  caso común (cuenta nueva sin transacciones, que es exactamente cuándo tiene sentido fijar la
  moneda).
- *Alternativa descartada:* recalcular/reconvertir las transacciones existentes a la moneda
  nueva al cambiar `currency`. Fuera de alcance — el proyecto no tiene tasas de conversión entre
  monedas en ningún lado (es explícitamente multi-moneda sin conversión, ver `CLAUDE.md`), así
  que "reconvertir" no es una operación que el dominio soporte hoy.

### 24.4 — Exponer `category_icon` en `category-distribution` (D1–D2)

**D1 — Backend: agregar `category_icon: str | None = None` a `CategoryDistributionData`, mismo
shape que `BudgetProgress.category_icon` (Hallazgo 8), y poblarlo en la query ya existente sin
cambiar su forma (agrega una columna al `SELECT`, no un `JOIN` nuevo — ya hace `JOIN` con
`Category` para `category_name`).**

```python
# backend/app/schemas/schemas.py — CategoryDistributionData
class CategoryDistributionData(BaseModel):
    category_id: int
    category_name: str
    category_icon: str | None = None  # 🆕 Fase 24 §24.4 — mismo campo que BudgetProgress
    total: Decimal

    class Config:
        from_attributes = True
```

```python
# backend/app/api/dashboard.py — obtener_distribucion_categorias(), ambas ramas (neto=True/False)
# rama neto=True (líneas 296-311): agrega models.Category.icon al SELECT y al GROUP BY
rows = (
    db.query(
        models.Transaction.category_id,
        models.Category.name,
        models.Category.icon,  # 🆕
        net_total.label("total"),
    )
    .join(models.Category, models.Category.id == models.Transaction.category_id)
    .filter(*filtros)
    .group_by(models.Transaction.category_id, models.Category.name, models.Category.icon)  # 🆕
    .having(net_total > 0)
    .order_by(net_total.desc())
    .all()
)
# rama neto=False (líneas 313-327): mismo patrón — agrega models.Category.icon al SELECT/GROUP BY

# línea 329, return final:
return [
    {"category_id": r.category_id, "category_name": r.name, "category_icon": r.icon, "total": r.total}
    for r in rows
]
```

**D2 — Frontend: `CategoryDistributionItem` gana `category_icon?: string`, y
`CategoryBreakdownBars` le pasa el prop `icon` a `CategoryIcon` en vez de dejarlo sin ícono —
un cambio de una línea, mismo patrón que `BudgetRing.tsx:93` ya usa.**

```ts
// frontend/types/api.ts — CategoryDistributionItem
export interface CategoryDistributionItem {
  category_id: number;
  category_name: string;
  category_icon?: string; // 🆕 Fase 24 §24.4
  total: number;
}
```

```tsx
// frontend/components/charts/CategoryBreakdownBars.tsx:64-67
<CategoryIcon
  icon={item.category_icon} // 🆕 — antes: sin este prop, siempre caía al fallback
  fallback={<Wallet size={16} className="text-text-muted" />}
/>
```

El comentario que hoy explica el fallback ("El contrato de category-distribution no incluye
ícono...") se elimina — deja de ser cierto.

- *Alternativa descartada:* mover la resolución de ícono al frontend (un mapa `category_name →
  icon` hardcodeado). Descartada — el ícono ya vive en `Category.icon` en la base de datos
  (fuente única de verdad, ya usada por `BudgetProgress`/`CategoryResponse`); duplicarlo en el
  frontend diverge en cuanto alguien cambie el ícono de una categoría desde donde sea que eso se
  edite.

---

## Orden de ejecución recomendado

```
1. Backend: §24.3 — actualizar_cuenta() semántica parcial + guard de currency + tests nuevos
   ── Independiente de todo lo demás. Es el único ítem con una decisión de diseño no trivial
      (C1-C4) — conviene resolverlo primero para no bloquear una revisión de PR más larga
      detrás de los otros 3, que son mecánicos.

2. Backend: §24.4 — category_icon en schema + query (ambas ramas)
   ── Independiente de (1): archivo compartido (dashboard.py vs accounts.py, sin overlap de
      funciones) y de schemas.py (clases distintas, sin conflicto de merge).

3. Frontend: §24.4 (mitad frontend) — CategoryDistributionItem + CategoryBreakdownBars
   ── Depende de (2) solo en el sentido de que consume el campo nuevo del contrato — si se
      implementa en paralelo, el campo llega como `undefined` hasta que (2) mergee (fallback
      ya existente, sin romper nada mientras tanto).

4. Frontend: §24.1 — EmptyState.action + isError/refetch en las 4 queries + CategoryBreakdownBars
   (props isError/onRetry)
   ── Independiente de (1)-(3). Comparte archivo (`CategoryBreakdownBars.tsx`,
      `page.tsx`) con el paso 3 — mismo agente/PR que 3, o coordinar el merge si son agentes
      distintos, para no pisarse el diff de `CategoryBreakdownBars.tsx`.

5. Frontend: §24.2 — noValidate + fieldError en el formulario de ingreso mensual
   ── Independiente de todo lo demás (mismo archivo que 4, `page.tsx`, pero secciones de
      código no solapadas — el formulario inline vive en un bloque JSX separado de las
      queries). Mismo criterio de coordinación de merge que (4) si van en paralelo.
```

Los dos ítems de backend (§24.3, §24.4) no comparten ningún archivo entre sí y pueden resolverse
en paralelo por agentes `backend-engineer` distintos. Los tres ítems de frontend (§24.1, §24.2,
mitad de §24.4) sí comparten `page.tsx`/`CategoryBreakdownBars.tsx` — recomendable un solo
`frontend-engineer` para los tres, o coordinar el orden de merge si se reparten.

---

## 24.1 `isError` + retry visible en las 4 queries del dashboard

### Backend

**Sin cambios.** Este ítem es puramente de manejo de estado en el cliente — las 4 queries ya
devuelven errores HTTP estándar (4xx/5xx) que TanStack Query ya captura como `isError` sin
ningún cambio de contrato.

**Testing:** no aplica.

**Criterio de aceptación:** no aplica (sin cambios de backend).

### Frontend

**Archivos a modificar:** `frontend/components/ui/EmptyState.tsx` (prop `action`),
`frontend/app/(dashboard)/page.tsx` (las 4 queries + sus 4 bloques de render),
`frontend/components/charts/CategoryBreakdownBars.tsx` (props `isError`/`onRetry`).

**Decisión de implementación:** ver A1-A4 arriba (snippets completos). Resumen: `EmptyState`
gana un slot de acción opcional; las 4 queries se re-desestructuran para exponer
`isError`/`refetch`; `budgetsProgress`/`recentTransactions` usan `EmptyState` con `action` en su
rama `isError` (antes de la rama de "sin datos"); `summary` usa un bloque inline (no tiene
`EmptyState` hoy); `categoryBreakdown` delega en `CategoryBreakdownBars`, que gana los props
`isError`/`onRetry` con el mismo shape que `CashflowChart`/`CategoryDonutChart`.

**Testing:** sin test runner de frontend (Hallazgo 12) — verificación manual: simular un fallo
(cortar el backend con `docker compose stop backend` o bloquear la URL en devtools) y confirmar
que las 4 secciones muestran su mensaje + botón "Reintentar" tras los 3 reintentos automáticos de
TanStack Query (Hallazgo 10, unos segundos de espera con backoff), y que cada botón recupera solo
su propia sección al levantar el backend de nuevo.

**Criterio de aceptación:**
- Con el backend caído, las 4 secciones del dashboard muestran un mensaje de error específico y
  un botón "Reintentar" — ninguna se ve idéntica a su estado "sin datos todavía".
- Cada botón "Reintentar" dispara solo el `refetch` de su propia query — no hay un "reintentar
  todo" que recargue las 4 aunque solo una haya fallado.
- Con el backend disponible de nuevo, tocar "Reintentar" recupera el contenido normal de esa
  sección sin recargar la página.
- Ningún estado "sin datos todavía" (0 presupuestos, 0 transacciones) legítimo se confunde con
  un error — `isError` y "lista vacía" siguen siendo ramas distintas del render.

---

## 24.2 `noValidate` + error de campo en el formulario de ingreso mensual inline

### Backend

**Sin cambios.** `PATCH /users/me` (que consume `useSetMonthlyIncome`) ya valida `monthly_income`
del lado del servidor — este ítem es exclusivamente sobre la validación del lado del cliente
antes de siquiera llamar a la mutación.

**Testing:** no aplica.

**Criterio de aceptación:** no aplica (sin cambios de backend).

### Frontend

**Archivo a modificar:** `frontend/app/(dashboard)/page.tsx` (el `<form>` de ingreso mensual,
líneas 202-235).

**Decisión de implementación:** ver B1-B2 arriba (snippet completo). Resumen: se agrega
`noValidate` al `<form>`, se quita el `required` nativo del `<Input>`, se agrega un
`useState<string | null>` (`monthlyIncomeError`) + un `ref` (`monthlyIncomeRef`), y el `return`
silencioso del guard se reemplaza por `setMonthlyIncomeError(...)` + foco en el input vía `ref`.

**Testing:** sin test runner de frontend — verificación manual: dejar el campo vacío y enviar
(debe mostrar el error y NO limpiar el input), escribir un valor negativo y enviar (mismo
resultado), y escribir un valor válido tras un error previo (debe limpiar el error y completar el
submit normalmente, mostrando el `toast.success` existente).

**Criterio de aceptación:**
- Enviar el formulario vacío o con un valor negativo muestra un mensaje de error visible junto al
  campo (mismo estilo visual que el resto de la app vía el prop `error` de `Input`) y mueve el
  foco al campo — nunca un `return` silencioso.
- El navegador nativo no muestra su propio globo de validación (confirma `noValidate` activo).
- Un envío válido tras un error previo limpia el mensaje de error y completa la mutación
  exactamente como hoy (sin cambios en el camino feliz).

---

## 24.3 `PUT /accounts/{id}` aplica cambios de `currency`

### Backend

**Archivo a modificar:** `backend/app/api/accounts.py`, función `actualizar_cuenta()` (líneas
185-202 al momento de escribir esto).

**Decisión de implementación:** ver C1-C4 arriba (snippets completos). Resumen: (1) la función
pasa a aplicar solo los campos presentes en `cuenta_actualizada.model_fields_set` (prerrequisito
que también corrige, sin trabajo adicional, el bug ya confirmado de `highlighted` reseteándose
en cada edición — Hallazgo 4); (2) `currency` se aplica solo si cambia de verdad Y la cuenta no
tiene transacciones activas, con `400` y el mismo estilo de mensaje que `eliminar_cuenta` en caso
contrario.

**Testing — nuevo bloque `TestUpdateAccount` en `backend/tests/test_accounts.py`** (no existe
cobertura previa de este endpoint, Hallazgo 11):

```python
class TestUpdateAccount:
    def test_updates_name_and_type_without_touching_currency_or_highlighted(
        self, client, auth_headers, make_account
    ):
        """Fase 24 §24.3 (Decisión C1): un PUT que omite currency/highlighted no los
        resetea a los defaults del schema — regresión directa del bug confirmado para
        `highlighted` (Hallazgo 4)."""
        cuenta = make_account(auth_headers, name="Original", type="cash", currency="USD", highlighted=True)

        response = client.put(
            f"/api/v1/accounts/{cuenta['id']}",
            json={"name": "Renombrada", "type": "debit"},
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        actualizada = response.json()
        assert actualizada["name"] == "Renombrada"
        assert actualizada["type"] == "debit"
        assert actualizada["currency"] == "USD"  # sin tocar
        assert actualizada["highlighted"] is True  # sin tocar (antes: se reseteaba a False)

    def test_applies_currency_change_when_account_has_no_transactions(
        self, client, auth_headers, make_account
    ):
        """Fase 24 §24.3 (Decisión C2): el caso feliz — cuenta recién creada, sin
        historial, el cambio de moneda se aplica de verdad (antes: se ignoraba en
        silencio, 200 sin efecto)."""
        cuenta = make_account(auth_headers, currency="COP")

        response = client.put(
            f"/api/v1/accounts/{cuenta['id']}",
            json={"name": cuenta["name"], "type": cuenta["type"], "currency": "USD"},
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["currency"] == "USD"

    def test_blocks_currency_change_when_account_has_active_transaction(
        self, client, auth_headers, make_account, make_category
    ):
        """Fase 24 §24.3 (Decisión C2): el guard real — mismo status/estilo de mensaje
        que eliminar_cuenta (accounts.py:231-233), mismo criterio de 'operación que no
        tiene sentido con historial existente'."""
        cuenta = make_account(auth_headers, currency="COP")
        categoria = make_category(auth_headers, name="Comida", type="expense")
        tx = client.post(
            "/api/v1/transactions/",
            json={"amount": "50.00", "type": "expense", "account_id": cuenta["id"], "category_id": categoria["id"]},
            headers=auth_headers,
        )
        assert tx.status_code == 200, tx.text

        response = client.put(
            f"/api/v1/accounts/{cuenta['id']}",
            json={"name": cuenta["name"], "type": cuenta["type"], "currency": "USD"},
            headers=auth_headers,
        )
        assert response.status_code == 400
        assert "moneda" in response.json()["detail"].lower()

        # La cuenta conserva su moneda original — el bloqueo es real, no cosmético.
        sin_cambios = client.get(f"/api/v1/accounts/{cuenta['id']}", headers=auth_headers).json()
        assert sin_cambios["currency"] == "COP"

    def test_allows_update_with_same_currency_even_with_transactions(
        self, client, auth_headers, make_account, make_category
    ):
        """Fase 24 §24.3 (Decisión C2): el guard solo dispara si el valor cambia de
        verdad — renombrar/retipear una cuenta con transacciones sigue funcionando
        igual que hoy, incluso si el body reenvía la misma moneda."""
        cuenta = make_account(auth_headers, currency="COP")
        categoria = make_category(auth_headers, name="Comida", type="expense")
        client.post(
            "/api/v1/transactions/",
            json={"amount": "50.00", "type": "expense", "account_id": cuenta["id"], "category_id": categoria["id"]},
            headers=auth_headers,
        )

        response = client.put(
            f"/api/v1/accounts/{cuenta['id']}",
            json={"name": "Otro nombre", "type": cuenta["type"], "currency": "COP"},
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["name"] == "Otro nombre"
        assert response.json()["currency"] == "COP"

    def test_foreign_account_returns_404(self, client, auth_headers, other_user, make_account):
        cuenta = make_account(other_user["headers"])

        response = client.put(
            f"/api/v1/accounts/{cuenta['id']}",
            json={"name": "x", "type": "cash"},
            headers=auth_headers,
        )
        assert response.status_code == 404
```

Correr `cd backend && pytest tests/test_accounts.py -v -k TestUpdateAccount`.

**Criterio de aceptación:**
- Un `PUT` que omite `currency`/`highlighted` del body no los resetea a los defaults del schema.
- Una cuenta sin transacciones puede cambiar de moneda libremente vía este endpoint.
- Una cuenta con al menos una transacción activa que intenta cambiar de moneda recibe `400` con
  un mensaje claro, y su moneda queda sin cambios.
- Reenviar la misma moneda (sin cambio real) nunca dispara el guard, con o sin transacciones.
- `GET /accounts/{id}/monthly-summary` y `POST /accounts/{id}/reconcile` no pueden, tras este
  fix, terminar sumando transacciones de dos monedas distintas bajo una sola etiqueta de moneda
  — verificado indirectamente por el guard (no hace falta un test nuevo en esos dos endpoints:
  si `currency` nunca cambia con transacciones activas presentes, el escenario que los rompería
  no puede ocurrir).

### Frontend

**Sin cambios (Decisión C3).** Ver razonamiento completo arriba: el modal de edición
(`frontend/app/(dashboard)/accounts/page.tsx:394-427`) no gana un selector de moneda — no lo pide
el ROADMAP para este ítem, y agregar uno abre una pregunta de producto (qué pasa con el saldo
existente al cambiar de moneda) que esta spec no está resolviendo.

**Testing:** no aplica (sin cambios). Verificación manual opcional, no bloqueante: confirmar que
editar el nombre o el tipo de una cuenta destacada YA NO la des-destaca (regresión del bug del
Hallazgo 4, corregida como efecto colateral de C1) — antes de este fix, cualquier edición de
nombre/tipo sobre una cuenta con `highlighted: true` la dejaba en `highlighted: false` sin aviso.

**Criterio de aceptación:**
- Ningún archivo de `frontend/` cambia por este ítem.
- Editar el nombre o tipo de una cuenta ya destacada desde la UI existente conserva su estado
  `highlighted` (verificación manual del efecto colateral de C1, no un requisito nuevo de
  producto).

---

## 24.4 Exponer `category_icon` en `category-distribution`

### Backend

**Archivos a modificar:** `backend/app/schemas/schemas.py` (`CategoryDistributionData`),
`backend/app/api/dashboard.py` (`obtener_distribucion_categorias()`, ambas ramas `neto=True`/
`neto=False`, líneas 256-329 al momento de escribir esto).

**Decisión de implementación:** ver D1 arriba (snippets completos). Resumen: se agrega
`category_icon: str | None = None` al schema y `models.Category.icon` al `SELECT`/`GROUP BY` de
ambas ramas de la query — la función ya hace `JOIN` con `Category`, así que no hay `JOIN` nuevo
que agregar, solo una columna más.

**Testing — extensión de `backend/tests/test_dashboard.py` (clase `TestCategoryDistributionCurrency`
ya existente, un test nuevo):**

```python
def test_response_includes_category_icon(self, client, auth_headers, db_session, make_account, make_category):
    """Fase 24 §24.4: category-distribution expone category_icon, igual que
    BudgetProgress. El endpoint POST /categories/ no acepta icon en el body
    (CategoryCreate no tiene ese campo, ver categories.py:22-41), así que el icon
    se fija directo en la sesión de test — mismo criterio que register_and_login
    fija email_verified directo (conftest.py:130)."""
    cuenta = make_account(auth_headers, currency="COP")
    categoria = make_category(auth_headers, name="Comida", type="expense")
    db_session.query(models.Category).filter(models.Category.id == categoria["id"]).update({"icon": "Utensils"})
    db_session.commit()

    _create_transaction(
        client, auth_headers, amount="10000.00", type="expense",
        account_id=cuenta["id"], category_id=categoria["id"],
    )

    response = client.get(
        "/api/v1/dashboard/category-distribution",
        params=_current_month_range_params(),
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    fila = response.json()[0]
    assert fila["category_icon"] == "Utensils"
```

Requiere `from app.models import models` ya importado en `test_dashboard.py` (verificar antes de
duplicar el import). Correr `cd backend && pytest tests/test_dashboard.py -v -k category_icon`.

**Criterio de aceptación:**
- `GET /dashboard/category-distribution` devuelve `category_icon` (string o `null`) en cada fila,
  en ambas ramas (`neto=true`/`neto=false`).
- Una categoría sin ícono asignado (`Category.icon IS NULL`, el caso más común hoy para
  categorías creadas por el usuario vía `POST /categories/`) devuelve `category_icon: null`, sin
  romper el contrato existente.
- Ningún test existente de `TestCategoryDistributionCurrency`/`TestCategoryDistributionAccountFilter`
  cambia de resultado — el campo nuevo es aditivo, no reordena ni filtra filas.

### Frontend

**Archivos a modificar:** `frontend/types/api.ts` (`CategoryDistributionItem`),
`frontend/components/charts/CategoryBreakdownBars.tsx` (línea 64-67).

**Decisión de implementación:** ver D2 arriba (snippets completos). Resumen: el tipo gana
`category_icon?: string`, y el componente pasa `icon={item.category_icon}` a `CategoryIcon` —
mismo patrón de una línea que `BudgetRing.tsx:93` ya usa para el mismo componente compartido.

**Testing:** sin test runner de frontend — verificación manual: crear/usar una categoría con
ícono conocido (cualquiera de las categorías base sembradas por el seed, que sí tienen `icon`
poblado — ver `backend/app/core/seed.py`), registrar un gasto en el mes en curso, y confirmar en
el dashboard que el desglose por categoría muestra el ícono real en vez del `Wallet` genérico.

**Criterio de aceptación:**
- El desglose de gastos por categoría del dashboard muestra el ícono real de cada categoría
  cuando existe, y el fallback `Wallet` solo para categorías sin ícono asignado (`icon: null`) —
  no para todas, como hoy.
- El orden y los montos de las filas no cambian (el ítem es puramente cosmético, tal como lo
  acota el ROADMAP).

---

## Resumen de archivos tocados por ítem

| Ítem | Backend | Frontend |
|---|---|---|
| 24.1 `isError` + retry dashboard | — | `components/ui/EmptyState.tsx` (prop `action`), `app/(dashboard)/page.tsx` (4 queries + 4 bloques de render), `components/charts/CategoryBreakdownBars.tsx` (props `isError`/`onRetry`) |
| 24.2 Validación ingreso mensual inline | — | `app/(dashboard)/page.tsx` (formulario, líneas 202-235) |
| 24.3 `PUT /accounts/{id}` aplica `currency` | `api/accounts.py` (`actualizar_cuenta()`), `tests/test_accounts.py` (`TestUpdateAccount`, clase nueva) | — (Decisión C3) |
| 24.4 `category_icon` en category-distribution | `schemas/schemas.py` (`CategoryDistributionData`), `api/dashboard.py` (`obtener_distribucion_categorias()`, ambas ramas), `tests/test_dashboard.py` (1 test nuevo) | `types/api.ts` (`CategoryDistributionItem`), `components/charts/CategoryBreakdownBars.tsx` |
| Cruzando toda la fase | `backend/docs/API_REFERENCE.md` — actualizar la sección `PUT /api/v1/accounts/{account_id}` (línea 434-437, hoy dice "Actualiza nombre, tipo y destacada" — agregar el comportamiento de `currency` y su guard) y `GET /api/v1/dashboard/category-distribution` (agregar `category_icon` a la salida documentada) | `frontend/docs/API_CONTRACT.md` — mismo par de endpoints, por la convención de `CLAUDE.md` de actualizar ambos documentos en el mismo cambio cuando el contrato de API cambia (24.3 cambia comportamiento, 24.4 cambia forma de respuesta; 24.1/24.2 no tocan contrato) |

---

## Out of scope

- **Selector de moneda en el modal de edición de cuentas** (frontend de §24.3): no lo pide el
  ROADMAP para este ítem (que pide corregir el *endpoint*, no construir la UI que lo dispare,
  Decisión C3) — y abre una pregunta de producto sin resolver (qué pasa con el saldo/historial
  visual al cambiar de moneda una cuenta ya usada) que ni el ROADMAP ni el enunciado de esta
  tarea piden resolver.
- **Reconversión o re-etiquetado de transacciones existentes al cambiar la moneda de una
  cuenta**: descartada en la Decisión C4 — el dominio no tiene tasas de conversión entre monedas
  en ningún lado del proyecto (multi-moneda sin conversión es una decisión de producto ya
  tomada, ver `CLAUDE.md`).
- **Corregir el bug de `highlighted` como ítem independiente con su propio changelog/entrada de
  `docs/TODO.md`**: se corrige como efecto colateral necesario de la Decisión C1 (§24.3), no como
  un ítem nuevo de alcance — no había ningún checkbox del ROADMAP para esto, y el enunciado de
  esta tarea pide explícitamente no inventar decisiones de producto nuevas fuera de los 4 ítems.
  Queda documentado en el Hallazgo 4 y en el criterio de aceptación de §24.3 (frontend) para que
  no se pierda de vista, pero no genera una entrada propia en "Resumen de archivos tocados".
- **Agregar retry a `CashflowChart`/`CategoryDonutChart` (Analítica)**, que hoy tienen `isError`
  pero no botón de reintentar (Hallazgo 9) — mismo patrón de gap que el ítem 24.1 cierra en el
  dashboard, pero en una pantalla distinta que ningún ítem del ROADMAP de esta fase nombra. Queda
  anotado como deuda adyacente para una fase futura, no como parte de 24.1.
- **Cambiar la política global de `retry` de TanStack Query** (`QueryProvider.tsx`): fuera de
  alcance — afectaría a toda la app, no solo al dashboard, y ninguno de los 4 ítems lo pide
  (Hallazgo 10).
- **Migración de Alembic**: ningún ítem de esta fase agrega ni cambia columnas de base de datos —
  `category_icon` expone una columna (`Category.icon`) que ya existe desde antes; el guard de
  `currency` es puramente lógica de aplicación.
- **Extraer un componente `<QueryErrorState>` reutilizable en vez de usar `EmptyState` con
  `action`**: evaluado y descartado en la Decisión A1 — `EmptyState` ya cubre el caso con una
  extensión mínima y retrocompatible; un componente nuevo duplicaría la misma estructura visual
  sin beneficio claro a este tamaño.

---

## Further notes

- **Los cuatro checkboxes de la sección "Fase 24" del ROADMAP quedan cubiertos**: (1) `isError`
  + retry en las 4 queries del dashboard → §24.1 (Decisiones A1-A4); (2) `noValidate` + error de
  campo en el formulario de ingreso mensual → §24.2 (Decisiones B1-B2); (3) `PUT /accounts/{id}`
  aplica `currency` → §24.3 (Decisiones C1-C4, con el guard de transacciones activas como pieza
  central, justificado contra el código real de `reconciliar_cuenta`/
  `obtener_resumen_mensual_cuenta`, no contra una suposición); (4) `category_icon` en
  `category-distribution` → §24.4 (Decisiones D1-D2).
- **La decisión más delicada de esta spec (C2, el guard de moneda) fue verificada
  estructuralmente contra las 6 funciones que leen `Transaction`/`Account` con montos**, no solo
  contra el ejemplo genérico del ROADMAP: 4 de ellas (las del dashboard) ya son seguras porque
  filtran por `Transaction.currency`; las otras 2 (`reconciliar_cuenta`,
  `obtener_resumen_mensual_cuenta`, ambas en `accounts.py`) no lo son y se habrían roto en
  silencio con la Opción (b) del enunciado — bloquear (Opción (a)) es la única opción de las tres
  planteadas que no deja ningún hueco confirmado.
- **El Hallazgo 3/4 cambia el framing del ítem 3 respecto a cómo lo describen el ROADMAP y
  `CODE_REVIEW.md`**: no es un bug que un usuario esté pisando hoy (no hay UI que envíe
  `currency` en este PUT), es una corrección de contrato con un prerrequisito de diseño
  (actualización parcial real, C1) que además resuelve gratis un bug de `highlighted` ya
  confirmado en producción. Vale la pena que quien revise esta spec entienda que "1h estimada en
  el ROADMAP" subestima levemente el trabajo real una vez que se contabiliza C1 — sigue siendo un
  ítem chico, pero no un simple `cuenta.currency = cuenta_actualizada.currency`.
- Este documento no implementa ningún cambio en el repositorio — es el desglose ejecutable de la
  sección "Fase 24" de `docs/ROADMAP.md`, con archivos, snippets y decisiones de arquitectura
  concretas para que `backend-engineer`/`frontend-engineer` puedan partir directamente de acá.
- Ningún archivo del repositorio fuera de `docs/specs/fase_24_spec.md` fue modificado al producir
  este documento — sigue siendo, en su totalidad, un documento de planificación.
