'use client';

import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { AlertCircle, PieChart } from 'lucide-react';
import { toast } from 'sonner';
import { useSearchParams } from 'next/navigation';
import { api } from '@/lib/api';
import { formatCurrency, getApiError } from '@/lib/utils';
import { validateAmountText } from '@/lib/validateAmount';
import { useCurrentUser } from '@/lib/hooks/useCurrentUser';
import { useSetMonthlyIncome } from '@/lib/hooks/useSetMonthlyIncome';
import { useAppConfig } from '@/providers/AppConfigProvider';
import { Suspense, useMemo, useRef, useState, useSyncExternalStore } from 'react';
import BudgetRing from '@/components/charts/BudgetRing';
import CategoryBreakdownSection from '@/components/charts/CategoryBreakdownSection';
import RecentTransactionsSection from '@/components/transactions/RecentTransactionsSection';
import PeriodNavigator from '@/components/PeriodNavigator';
import SummaryCard from '@/components/ui/SummaryCard';
import Button from '@/components/ui/Button';
import EmptyState from '@/components/ui/EmptyState';
import QueryErrorState from '@/components/ui/QueryErrorState';
import Input from '@/components/ui/Input';
import Skeleton from '@/components/ui/Skeleton';
import { useQueryParamState } from '@/hooks/useQueryParamState';
import { queryKeys } from '@/lib/queryKeys';
import {
  compareMonth,
  monthOfDay,
  formatMonthLabel,
  formatMonthName,
  formatMonthParam,
  monthTransactionsHref,
  parseMonthParam,
  shiftMonth,
  monthRange as buildMonthRange,
} from '@/lib/dateRanges';
import { hourInZone, todayInZone } from '@/lib/dates';
import { useTimezone } from '@/lib/hooks/useTimezone';
import type { CalendarMonth } from '@/lib/dateRanges';
import type { BudgetProgress, DashboardSummary } from '@/types/api';

/**
 * Fase 29 §F5.1 (Q6, H10, supuesto 3): validador read-time de `?month=YYYY-MM`, mismo patrón
 * que `validateDateParam` de transactions/page.tsx (Fase 13 §13.6). Un link con `?month=basura`,
 * `?month=2026-13` o con un mes futuro devuelve el mes actual en vez de dejar la vista rota
 * (User Story 8); la URL no se reescribe con el valor corregido, el re-normalizado por render
 * alcanza. Cubre los 422 de `core/periods.resolver_mes` (H13) antes de pedirle el mes al server.
 */
const validateMonthParam = (raw: string, current: CalendarMonth): string => {
  const parsed = parseMonthParam(raw);
  if (!parsed || compareMonth(parsed, current) > 0) {
    return formatMonthParam(current);
  }
  return raw;
};

/** Determina el saludo según la hora en la zona del usuario (Fase 30 F6, Fase 34 F7). */
const getGreeting = (hours: number): string => {
  if (hours >= 5 && hours < 12) return 'Buenos días';
  if (hours >= 12 && hours < 19) return 'Buenas tardes';
  return 'Buenas noches';
};

// "¿Ya se montó en el cliente?" con `useSyncExternalStore` (Q9): el snapshot de servidor es
// `false` y el de cliente `true`, así la hidratación usa `false` (igual que el SSR, sin
// mismatch) y React re-renderiza una vez con `true`. No hay nada a lo que suscribirse: el valor
// no cambia después del montaje. Evita `useState` + `useEffect` y su `eslint-disable`.
const subscribeNoop = () => () => {};
const useIsMounted = (): boolean =>
  useSyncExternalStore(
    subscribeNoop,
    () => true,
    () => false
  );

function DashboardScreen() {
  const { config } = useAppConfig();
  const { data: user } = useCurrentUser();
  const searchParams = useSearchParams();
  const [monthlyIncomeInput, setMonthlyIncomeInput] = useState('');
  // Fase 24 §24.2 (Decisión B1-B2): error de campo inline + ref para mover el foco al fallar
  // la validación. Mismo patrón que la Decisión 12.8.1 de Fase 12, sin librería nueva.
  const [monthlyIncomeError, setMonthlyIncomeError] = useState<string | null>(null);
  const monthlyIncomeRef = useRef<HTMLInputElement>(null);

  // Fase 29 §F5.1 (Q6): el mes visible vive en `?month=YYYY-MM` (User Story 6) y el default
  // nunca se escribe — `setMonthParam('')` borra la clave y deja la URL del mes en curso limpia
  // (User Story 7).
  // Fase 34 F1/F2: "hoy" y el mes en curso se resuelven en la zona del usuario. `today` es un
  // string `YYYY-MM-DD` (estable durante el día): sirve de dep de memo y de techo del rango. Hasta
  // que `/users/me` carga (`ready`) las queries que dependen del mes no se disparan.
  const { displayTimezone, ready } = useTimezone();
  const today = todayInZone(displayTimezone);
  const { year: currentYear, month: currentMonth } = monthOfDay(today);

  const [monthParam, setMonthParam] = useQueryParamState('month', '', (raw) =>
    validateMonthParam(raw, { year: currentYear, month: currentMonth })
  );

  // Fase 30 F6 (Q5/Q9): detecta si ya se montó en el cliente para evitar hydration mismatch
  // en el saludo dinámico. SSR renderiza 'Hola'; cliente tras montaje muestra el saludo por hora.
  const isMounted = useIsMounted();

  // `?? { year: currentYear, month: currentMonth }` es defensivo: `validateMonthParam` ya
  // garantiza un valor parseable, pero un `null` aquí dejaría el mes sin año ni número.
  const selectedMonth = parseMonthParam(monthParam) ?? { year: currentYear, month: currentMonth };
  const { year, month } = selectedMonth;
  const isCurrentMonth = year === currentYear && month === currentMonth;

  // H10: el mes en curso NUNCA viaja como `year`/`month`. El 422 de "mes futuro" lo evalúa el
  // reloj del servidor y el del navegador puede ir atrasado justo en el cambio de mes, así que
  // pedirlo explícito devolvería un 422 falso. De paso, la key del mes en curso es la de siempre
  // (supuesto 4) y las ~17 invalidaciones por prefijo siguen matcheando (H7).
  const apiMonth = isCurrentMonth ? undefined : monthParam;
  const periodParams = isCurrentMonth ? undefined : { year, month };

  // Rango del mes visible como días `YYYY-MM-DD` (Fase 34 F3): el backend los interpreta en la
  // zona del usuario. El techo del mes en curso es `today`.
  const monthRange = useMemo(() => buildMonthRange(year, month, today), [year, month, today]);
  const monthLabel = formatMonthLabel(year, month);
  const monthNameLower = formatMonthName(year, month);

  // La moneda preferida del usuario; config.currency es su espejo desde preferencias.
  const preferredCurrency = user?.preferred_currency ?? config.currency;

  const {
    data: summary,
    isLoading: loadingSummary,
    isPlaceholderData: summaryIsStale,
    isError: summaryError,
    refetch: refetchSummary,
  } = useQuery<DashboardSummary>({
    queryKey: queryKeys.dashboard.summary(apiMonth),
    enabled: ready,
    queryFn: async () => (await api.get('dashboard/summary', { params: periodParams })).data,
    // Fase 29 §F5.1 (User Story 9): `◀ ▶` no devuelven la página a sus skeletons, muestran el
    // mes anterior mientras llega el nuevo.
    placeholderData: keepPreviousData,
  });

  const {
    data: budgetsProgress,
    isLoading: loadingBudgets,
    isError: budgetsError,
    refetch: refetchBudgets,
  } = useQuery<BudgetProgress[]>({
    queryKey: queryKeys.budgets.progress(apiMonth),
    enabled: ready,
    queryFn: async () =>
      (await api.get('dashboard/budgets-progress', { params: periodParams })).data,
    placeholderData: keepPreviousData,
  });

  // Fase 29 §F5.4 (Q4, B7): opciones de los chips = `summary.expense_currencies` (monedas con
  // gasto en el mes, sobre TODAS las cuentas) más la preferida, con la preferida primera. El
  // backend ya la ordena así cuando tiene gasto; el `Set` la agrega si no.
  const currencyOptions = useMemo(() => {
    const fromBackend = summary?.expense_currencies ?? [];
    return [...new Set([preferredCurrency, ...fromBackend])];
  }, [summary?.expense_currencies, preferredCurrency]);

  // Fase 11 §11.3, Decisión 11.3.2: vía de escape inline para fijar el ingreso mensual sin
  // salir del dashboard (el flujo guiado completo llega con el onboarding de Fase 15).
  const setMonthlyIncomeMutation = useSetMonthlyIncome();

  const isLoading = loadingSummary || loadingBudgets || !ready;

  // Balance del mes calculado POR EL BACKEND (summary.monthly_flow_balance). Nunca se resta
  // en el cliente.
  // Fase 31 B9/F8 (Q9, Q14): el balance ya no es `null` en ningún mes — ingresos reales
  // menos gastos reales, en cualquier mes, puede ser negativo (a principio de mes, antes
  // de cobrar, es un dato normal). `monthly_income` ya no participa de este número; es una
  // referencia visual aparte ("· esperado <monto>", más abajo). `undefined` sigue
  // significando "la query está en carga o en error" (esos casos ya salen antes de leer
  // este valor, ver el render).
  // Fase 15 §15.6: normaliza Decimal→string que el backend serializa en JSON (Decisión 15.6).
  const flowBalanceValue = summary ? Number(summary.monthly_flow_balance) : undefined;
  const flowIsPositive = (flowBalanceValue ?? 0) >= 0;
  const flowTrend =
    flowBalanceValue === undefined || summaryIsStale
      ? undefined
      : flowIsPositive
        ? ('up' as const)
        : ('down' as const);
  const flowColor =
    flowBalanceValue === undefined || summaryIsStale
      ? undefined
      : flowIsPositive
        ? 'var(--color-success)'
        : 'var(--color-danger)';

  // Fase 31 F8 (Q9, Q14): el rótulo es siempre "Balance de <mes>", también en el mes en
  // curso — ya no hay dos bases que distinguir (B9 retira `monthly_flow_basis` del cálculo;
  // el campo sigue en el contrato mismo pero deprecado, ver types/api.ts).
  const flowLabel = `Balance de ${monthNameLower}`;

  // Fase 31 F8 (Q14): "esperado <monto>" solo tiene sentido en el mes en curso — el ingreso
  // declarado no tiene historial (Fase 29 User Story 14), así que mostrarlo junto a un mes
  // cerrado sugeriría que aplicó a ESE mes.
  const showExpectedIncomeReference = isCurrentMonth && user?.monthly_income != null;
  // Fase 31 F8 (H3): el formulario inline vivía en la rama `null` de un balance que ya no
  // existe (B9) — se reubica acá, debajo de las cifras secundarias, solo en el mes en curso
  // y solo mientras el usuario no fijó su ingreso esperado. `!summaryIsStale` evita que el
  // placeholder de `keepPreviousData` lo haga parpadear al navegar hacia un mes pasado.
  const showInlineIncomeForm =
    isCurrentMonth && !!summary && !summaryIsStale && user?.monthly_income == null;

  // Fase 15 §15.5, Decisión 15.0.1 (revisada): originalmente `total === 1`, pero eso se
  // rompió al agregar la transacción semilla del ingreso declarado (§15.3.3) — con ella, la
  // captura guiada del primer gasto ya es la SEGUNDA transacción del usuario, y el banner
  // nunca se mostraba. Se reemplaza por el mismo mecanismo que ya usa /capture (`?onboarding=1`,
  // Decisión 15.0.2): TransactionCaptureForm redirige aquí con ese query param solo al terminar
  // la captura guiada, sin importar cuántas transacciones existan.
  const cameFromOnboardingCapture = searchParams.get('onboarding') === '1';
  const preferredExpense =
    summary?.monthly_expense_by_currency.find((b) => b.currency === preferredCurrency)?.total ?? 0;

  // Q9: `◀` no baja del mes de la primera transacción; con `first_transaction_month = null` no
  // hay mes anterior al que llegar, así que queda siempre deshabilitado. `undefined` (summary
  // aún en carga) NO deshabilita: con `keepPreviousData` los datos anteriores persisten y el
  // piso se recalcula solo — solo en la carga inicial el piso se desconoce.
  const floorMonth = summary?.first_transaction_month
    ? parseMonthParam(summary.first_transaction_month)
    : null;
  // El objeto literal y no `selectedMonth`: si el objeto del que salieron `year`/`month` escapa
  // a una llamada externa, el compilador de React los marca como "quizás mutados después" y
  // termina invalidando el `useMemo` del rango (`preserve-manual-memoization`).
  const prevDisabled =
    floorMonth === null
      ? summary?.first_transaction_month === null
      : compareMonth({ year, month }, floorMonth) <= 0;

  // User Story 7: el mes en curso se ve con la URL limpia. Si `▶` aterriza en el mes actual se
  // borra `?month=` en vez de escribirlo explícito — si no, el link queda fijado a ese mes y
  // un marcador guardado hoy seguiría abriendo este mes después del cambio de mes.
  const handleNextMonth = () => {
    const target = shiftMonth(selectedMonth, 1);
    const isTargetCurrent = compareMonth(target, { year: currentYear, month: currentMonth }) >= 0;
    setMonthParam(isTargetCurrent ? '' : formatMonthParam(target));
  };

  // Fase 19 §19.2.1/19.2.2: fila secundaria compacta dentro de la card principal — reemplaza
  // el grid de 2 columnas (Ingresos/Gastos). Son sumas de transacciones del mes (no el
  // ingreso declarado), se muestran siempre. En meses cerrados el rótulo nombra el mes
  // (User Story 13).
  const incomeStatLabel = isCurrentMonth ? 'Ingresos del Mes' : `Ingresos de ${monthNameLower}`;
  const expenseStatLabel = isCurrentMonth ? 'Gastos del Mes' : `Gastos de ${monthNameLower}`;

  // Fase 31 F8 (Q14): "· esperado <monto>" junto a "Ingresos del mes", en la línea de la
  // moneda preferida — sin cálculo, no se resta ni se compara contra lo real.
  const expectedIncomeLabel =
    showExpectedIncomeReference && user?.monthly_income != null
      ? `· esperado ${formatCurrency(Number(user.monthly_income), preferredCurrency)}`
      : null;

  // Placeholder del mes anterior en vuelo: los rótulos ya nombran el mes destino, así que las
  // cifras (del mes anterior) se reemplazan por skeletons en vez de quedar bajo un rótulo ajeno.
  // Fase 31 F8 (H3): el formulario inline de ingreso (cuando no está fijado) vive acá abajo,
  // debajo de la fila de Ingresos/Gastos, en vez de reemplazar la cifra principal — la tarjeta
  // ya no tiene una rama "sin balance" que ocupar (B9: el balance nunca es `null`).
  const secondaryStats = (
    <div className="w-full space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:gap-6">
        <div className="flex-1">
          <p className="text-text-muted text-xs font-medium">{incomeStatLabel}</p>
          <div className="text-success mt-0.5 font-semibold tabular-nums">
            {summaryIsStale ? (
              <Skeleton className="mt-1 h-5 w-28" />
            ) : summary?.monthly_income_by_currency.length ? (
              summary.monthly_income_by_currency.map((b) => (
                <p key={b.currency}>
                  {formatCurrency(b.total, b.currency)}
                  {b.currency === preferredCurrency && expectedIncomeLabel && (
                    <span className="text-text-muted ml-1.5 text-xs font-normal">
                      {expectedIncomeLabel}
                    </span>
                  )}
                </p>
              ))
            ) : (
              <p>
                {formatCurrency(0, preferredCurrency)}
                {expectedIncomeLabel && (
                  <span className="text-text-muted ml-1.5 text-xs font-normal">
                    {expectedIncomeLabel}
                  </span>
                )}
              </p>
            )}
          </div>
        </div>
        <div className="flex-1">
          <p className="text-text-muted text-xs font-medium">{expenseStatLabel}</p>
          <div className="text-danger mt-0.5 font-semibold tabular-nums">
            {summaryIsStale ? (
              <Skeleton className="mt-1 h-5 w-28" />
            ) : summary?.monthly_expense_by_currency.length ? (
              summary.monthly_expense_by_currency.map((b) => (
                <p key={b.currency}>{formatCurrency(b.total, b.currency)}</p>
              ))
            ) : (
              <p>{formatCurrency(0, preferredCurrency)}</p>
            )}
          </div>
        </div>
      </div>

      {showInlineIncomeForm && (
        <form
          className="border-border/40 space-y-2 border-t pt-4"
          noValidate
          onSubmit={(e) => {
            e.preventDefault();
            const validationError = validateAmountText(monthlyIncomeInput, { allowZero: true });
            if (validationError) {
              setMonthlyIncomeError(validationError);
              return monthlyIncomeRef.current?.focus();
            }
            setMonthlyIncomeError(null);
            setMonthlyIncomeMutation.mutate(Number(monthlyIncomeInput), {
              onSuccess: () => toast.success('Ingreso mensual guardado'),
              onError: (error) => toast.error(getApiError(error)),
            });
          }}
        >
          {/* Fase 31 F8 (Q14): ya no promete "calcular tu balance" — el ingreso esperado es
              solo una referencia visual junto a "Ingresos del mes". */}
          <p className="text-text-muted text-sm font-normal">
            ¿Cuánto esperas ganar al mes? Es solo una referencia.
          </p>
          <div className="flex items-center gap-2">
            <Input
              ref={monthlyIncomeRef}
              type="number"
              inputMode="decimal"
              min={0}
              step="0.01"
              aria-label="Ingreso mensual"
              placeholder={`Ej. 3000000 (${preferredCurrency})`}
              value={monthlyIncomeInput}
              onChange={(e) => setMonthlyIncomeInput(e.target.value)}
              error={monthlyIncomeError ?? undefined}
              className="bg-background"
            />
            <Button type="submit" loading={setMonthlyIncomeMutation.isPending}>
              Guardar
            </Button>
          </div>
        </form>
      )}
    </div>
  );

  return (
    <div className="space-y-6 pb-10 sm:space-y-10">
      {/* Aha moment (Fase 15 §15.5, Decisión 15.5.1) — se muestra solo llegando desde la
          captura guiada del onboarding (?onboarding=1); desaparece en cuanto el usuario
          navega a cualquier otro lado, sin estado adicional que mantener.
          Los montos Decimal llegan como string (Decisión 15.6), de ahí los Number(...).
          Fase 29 §F5.3 (User Story 15): el banner habla del ingreso declarado y del gasto
          acumulado del mes, así que solo tiene sentido en el mes en curso. */}
      {cameFromOnboardingCapture && isCurrentMonth && (
        <div
          role="status"
          className="bg-primary/10 border-primary/20 text-text rounded-2xl border p-4 text-sm"
        >
          {user?.monthly_income != null ? (
            <>
              Has gastado {formatCurrency(Number(preferredExpense), preferredCurrency)} de tus{' '}
              {formatCurrency(Number(user.monthly_income), preferredCurrency)} de ingreso mensual.
            </>
          ) : (
            // Fase 31 F8 (Q14): ya no promete "para ver cuánto te queda cada mes" — el
            // ingreso declarado es una referencia visual, no alimenta ningún cálculo.
            '¡Registraste tu primer movimiento! Define tu ingreso mensual abajo.'
          )}
        </div>
      )}

      {/* Encabezado */}
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h1 className="font-sans text-2xl font-bold tracking-tight sm:text-3xl">
            {(() => {
              if (!isMounted) return 'Hola'; // SSR: mismo contenido que cliente inicial
              const hours = hourInZone(displayTimezone);
              const greeting = getGreeting(hours);
              const name = user?.full_name?.split(' ')[0];
              return name ? `${greeting}, ${name}` : greeting;
            })()}
          </h1>
          <p className="text-text-muted mt-1 text-xs sm:text-sm">
            Aquí tienes el estado actual de tus finanzas orgánicas.
          </p>
        </div>
        {/* Fase 29 §F5.2 (Q9, Q15): `◀ Agosto 2026 ▶` en el encabezado, sobre la tarjeta
            principal y NO sticky a propósito — el rótulo del mes acompaña el contexto y no
            debe flotar sobre el scroll. "Volver a este mes" solo fuera del mes en curso. */}
        <PeriodNavigator
          label={monthLabel}
          onPrev={() => setMonthParam(formatMonthParam(shiftMonth(selectedMonth, -1)))}
          onNext={() => handleNextMonth()}
          prevDisabled={prevDisabled}
          nextDisabled={isCurrentMonth}
          onReset={isCurrentMonth ? undefined : () => setMonthParam('')}
        />
      </div>

      {/* Summary Cards — la card principal mide flujo mensual (Fase 11 §11.3); el saldo total
          de cuentas vive ahora en /accounts como vista secundaria (§11.5). */}
      <div className="space-y-6" aria-busy={summaryIsStale}>
        {/* Fase 24 §24.1 (Decisión A2): bloque de error inline, mismo tono visual que
            CashflowChart.tsx:96-99 — distingue "falló la query" de "sin datos todavía". */}
        {loadingSummary ? (
          <Skeleton className="h-44 rounded-2xl" />
        ) : summaryError ? (
          <div className="border-border text-text-muted flex h-44 flex-col items-center justify-center gap-2 rounded-2xl border border-dashed text-sm">
            <AlertCircle size={20} />
            <p>No se pudo cargar el resumen del mes.</p>
            <Button variant="secondary" size="sm" onClick={() => refetchSummary()}>
              Reintentar
            </Button>
          </div>
        ) : (
          <SummaryCard
            label={flowLabel}
            size="lg"
            elevated
            trend={flowTrend}
            color={flowColor}
            secondaryStats={secondaryStats}
          >
            {summaryIsStale || flowBalanceValue === undefined ? (
              <Skeleton className="h-9 w-48 sm:h-10" />
            ) : (
              <span className={flowIsPositive ? '' : 'text-danger'}>
                {formatCurrency(flowBalanceValue, preferredCurrency)}
              </span>
            )}
          </SummaryCard>
        )}
      </div>

      {/* Budget Rings */}
      <div>
        <div className="mb-6 flex items-center space-x-2">
          <PieChart className="text-primary" size={20} />
          <h2 className="text-text font-sans text-xl font-bold">Ejecución de Presupuestos</h2>
        </div>

        {isLoading ? (
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="flex flex-col items-center gap-3 p-6">
                <Skeleton className="h-24 w-24 rounded-full" />
                <Skeleton className="h-4 w-20" />
                <Skeleton className="h-3 w-16" />
              </div>
            ))}
          </div>
        ) : budgetsError ? (
          <QueryErrorState
            message="No se pudo cargar el progreso de presupuestos."
            onRetry={() => refetchBudgets()}
          />
        ) : !budgetsProgress || budgetsProgress.length === 0 ? (
          // Fase 29 §F5.4 (Q7, User Story 17): en un mes cerrado el backend solo devuelve los
          // presupuestos que existían (no genera recurrentes retroactivos), así que "vacío"
          // significa "no había" y no "todavía no definiste". El caso del mes en curso — que sí
          // genera los recurrentes al abrir el dashboard — queda como estaba.
          <EmptyState
            icon={<PieChart size={48} className="opacity-20" />}
            message={
              isCurrentMonth
                ? 'Aún no hay datos de progreso.'
                : `No había presupuestos en ${monthNameLower}`
            }
            description={
              isCurrentMonth
                ? 'Asegúrate de tener presupuestos definidos y gastos registrados en este mes.'
                : undefined
            }
          />
        ) : (
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
            {budgetsProgress.map((budget, index) => (
              <BudgetRing
                key={budget.budget_id || `budget-ring-${index}`}
                categoryName={budget.category_name}
                categoryIcon={budget.category_icon}
                budgetAmount={Number(budget.amount_limit)}
                spentAmount={Number(budget.spent)}
                percentage={Number(budget.percentage)}
                currency={budget.currency}
              />
            ))}
          </div>
        )}
      </div>

      {/* Gastos por categoría del mes visible (Fase 11 §11.4 + Fase 29 §F5.4) */}
      <CategoryBreakdownSection
        monthKey={apiMonth}
        range={monthRange}
        enabled={ready}
        currencyOptions={currencyOptions}
        preferredCurrency={preferredCurrency}
        emptyMessage={
          isCurrentMonth ? undefined : `No hay gastos registrados en ${monthNameLower}.`
        }
      />

      {/* Últimas 5 del mes visible (Fase 29 §F5.5) */}
      <RecentTransactionsSection
        range={monthRange}
        enabled={ready}
        monthName={monthNameLower}
        viewAllHref={monthTransactionsHref(year, month)}
      />
    </div>
  );
}

// useSearchParams() exige un límite <Suspense> propio (mismo patrón que capture/page.tsx
// y analytics/page.tsx) — sin esto, Next falla el build. Lo usan el screen de abajo y
// `useQueryParamState` de `?month=`.
export default function DashboardPage() {
  return (
    <Suspense fallback={null}>
      <DashboardScreen />
    </Suspense>
  );
}
