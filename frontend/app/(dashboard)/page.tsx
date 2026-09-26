'use client';

import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { AlertCircle, PieChart } from 'lucide-react';
import { toast } from 'sonner';
import { useSearchParams } from 'next/navigation';
import { api } from '@/lib/api';
import { formatCurrency, getApiError } from '@/lib/utils';
import { useCurrentUser } from '@/lib/hooks/useCurrentUser';
import { useSetMonthlyIncome } from '@/lib/hooks/useSetMonthlyIncome';
import { useAppConfig } from '@/providers/AppConfigProvider';
import { Suspense, useMemo, useRef, useState } from 'react';
import BudgetRing from '@/components/charts/BudgetRing';
import CategoryBreakdownSection from '@/components/charts/CategoryBreakdownSection';
import RecentTransactionsSection from '@/components/transactions/RecentTransactionsSection';
import PeriodNavigator from '@/components/PeriodNavigator';
import SummaryCard from '@/components/ui/SummaryCard';
import Button from '@/components/ui/Button';
import EmptyState from '@/components/ui/EmptyState';
import Input from '@/components/ui/Input';
import Skeleton from '@/components/ui/Skeleton';
import { useQueryParamState } from '@/hooks/useQueryParamState';
import { queryKeys } from '@/lib/queryKeys';
import {
  compareMonth,
  currentUtcMonth,
  formatMonthLabel,
  monthTransactionsHref,
  parseMonthParam,
  shiftMonth,
  utcMonthRange,
  type UtcMonth,
} from '@/lib/dateRanges';
import type { BudgetProgress, DashboardSummary } from '@/types/api';

const toMonthParam = ({ year, month }: UtcMonth) => `${year}-${String(month).padStart(2, '0')}`;

/**
 * Fase 29 §F5.1 (Q6, H10, supuesto 3): validador read-time de `?month=YYYY-MM`, mismo patrón
 * que `validateDateParam` de transactions/page.tsx (Fase 13 §13.6). Un link con `?month=basura`,
 * `?month=2026-13` o con un mes futuro devuelve el mes actual en vez de dejar la vista rota
 * (User Story 8); la URL no se reescribe con el valor corregido, el re-normalizado por render
 * alcanza. Cubre los 422 de `core/periods.resolver_mes` (H13) antes de pedirle el mes al server.
 */
const validateMonthParam = (raw: string): string => {
  const current = currentUtcMonth(new Date());
  const parsed = parseMonthParam(raw);
  if (!parsed || compareMonth(parsed, current) > 0) {
    return toMonthParam(current);
  }
  return raw;
};

/**
 * Fase 29 §F5.3: nombre del mes en minúscula y sin año (`"agosto"`) para los rótulos que ya
 * viven debajo del `PeriodNavigator`, donde el año está a la vista: "Balance de agosto" y no
 * "Balance de agosto 2026". `formatMonthLabel` ("Agosto 2026") es el rótulo del navegador.
 */
const monthName = (year: number, month: number) => {
  const label = formatMonthLabel(year, month);
  const name = label.slice(0, label.lastIndexOf(' '));
  return name.charAt(0).toLowerCase() + name.slice(1);
};

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
  const [monthParam, setMonthParam] = useQueryParamState('month', '', validateMonthParam);

  const now = new Date();
  // Primitivos, no el objeto de `currentUtcMonth(now)`: dentro de las deps de un `useMemo` o de
  // una query, un objeto nuevo por render produce una dependencia distinta en cada render y
  // con ella un refetch constante.
  const { year: currentYear, month: currentMonth } = currentUtcMonth(now);
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

  // Techo del mes en curso recortado al inicio del día UTC. `utcMonthRange` corta el mes
  // abierto en "ahora", y `now` es un objeto nuevo en cada render: ponerlo en las deps
  // generaría una key distinta por render y un refetch constante. Recortarlo a las 00:00 UTC
  // del día agrupa el mismo conjunto de transacciones (las fechas son por día a las 00:00 UTC,
  // ver §F1) y solo cambia una vez al día.
  const todayUtcStart = Date.UTC(currentYear, currentMonth - 1, now.getUTCDate());
  const monthRange = useMemo(
    () => utcMonthRange(year, month, new Date(todayUtcStart)),
    [year, month, todayUtcStart]
  );
  const monthLabel = formatMonthLabel(year, month);
  const monthNameLower = monthName(year, month);

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

  const isLoading = loadingSummary || loadingBudgets;

  // Balance del mes calculado POR EL BACKEND (summary.monthly_flow_balance). Nunca se resta
  // en el cliente. Tres estados distinguidos: undefined = query en carga/error, null = el
  // usuario no ha fijado monthly_income, number = valor listo para pintar.
  // Fase 15 §15.6: normaliza Decimal→string que el backend serializa en JSON (Decisión 15.6).
  // Destraba la card "Balance del mes" cuando el onboarding fija ingresos.
  const flowBalance = summary?.monthly_flow_balance;
  const flowBalanceValue = flowBalance == null ? null : Number(flowBalance);
  const flowIsPositive = (flowBalanceValue ?? 0) >= 0;
  const flowTrend =
    flowBalanceValue === null ? undefined : flowIsPositive ? ('up' as const) : ('down' as const);
  const flowColor =
    flowBalanceValue === null
      ? undefined
      : flowIsPositive
        ? 'var(--color-success)'
        : 'var(--color-danger)';

  // Fase 29 §F5.3 (Q8, Q12): el rótulo sale de `monthly_flow_basis`, no de comparar fechas
  // locales — el backend decide con su reloj y en meses cerrados el balance es ingresos −
  // gastos reales, nunca `null` (User Story 12). Un balance negativo real (riesgo R1: el
  // sueldo no se registra como transacción) es un número, no un error.
  const flowLabel =
    summary?.monthly_flow_basis === 'actual' ? `Balance de ${monthNameLower}` : 'Te quedan…';

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

  // Fase 19 §19.2.1/19.2.2: fila secundaria compacta dentro de la card principal — reemplaza
  // el grid de 2 columnas (Ingresos/Gastos). Se muestra siempre, aún con monthly_flow_balance
  // null (son sumas de transacciones del mes, no el ingreso declarado). En meses cerrados el
  // rótulo nombra el mes (User Story 13).
  const incomeStatLabel = isCurrentMonth ? 'Ingresos del Mes' : `Ingresos de ${monthNameLower}`;
  const expenseStatLabel = isCurrentMonth ? 'Gastos del Mes' : `Gastos de ${monthNameLower}`;

  const secondaryStats = (
    <>
      <div className="flex-1">
        <p className="text-text-muted text-xs font-medium">{incomeStatLabel}</p>
        <div className="text-success mt-0.5 font-semibold tabular-nums">
          {summary?.monthly_income_by_currency.length ? (
            summary.monthly_income_by_currency.map((b) => (
              <p key={b.currency}>{formatCurrency(b.total, b.currency)}</p>
            ))
          ) : (
            <p>{formatCurrency(0, preferredCurrency)}</p>
          )}
        </div>
      </div>
      <div className="flex-1">
        <p className="text-text-muted text-xs font-medium">{expenseStatLabel}</p>
        <div className="text-danger mt-0.5 font-semibold tabular-nums">
          {summary?.monthly_expense_by_currency.length ? (
            summary.monthly_expense_by_currency.map((b) => (
              <p key={b.currency}>{formatCurrency(b.total, b.currency)}</p>
            ))
          ) : (
            <p>{formatCurrency(0, preferredCurrency)}</p>
          )}
        </div>
      </div>
    </>
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
            '¡Registraste tu primer movimiento! Define tu ingreso mensual abajo para ver cuánto te queda cada mes.'
          )}
        </div>
      )}

      {/* Encabezado */}
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h1 className="font-sans text-2xl font-bold tracking-tight sm:text-3xl">
            Buenas tardes, {user?.full_name?.split(' ')[0] || 'de nuevo'}
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
          onPrev={() => setMonthParam(toMonthParam(shiftMonth(selectedMonth, -1)))}
          onNext={() => setMonthParam(toMonthParam(shiftMonth(selectedMonth, 1)))}
          prevDisabled={prevDisabled}
          nextDisabled={isCurrentMonth}
          onReset={isCurrentMonth ? undefined : () => setMonthParam('')}
        />
      </div>

      {/* Summary Cards — la card principal mide flujo mensual (Fase 11 §11.3); el saldo total
          de cuentas vive ahora en /accounts como vista secundaria (§11.5). */}
      <div className="space-y-6">
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
            {flowBalanceValue !== null ? (
              <span className={flowIsPositive ? '' : 'text-danger'}>
                {formatCurrency(flowBalanceValue, preferredCurrency)}
              </span>
            ) : isCurrentMonth && summary && !summaryIsStale ? (
              // Fase 29 §F5.3 (User Story 14): el ingreso declarado es un valor único sin
              // historial, así que editarlo mirando un mes pasado no significa nada — el
              // formulario solo existe en el mes en curso. `!summaryIsStale` evita además que
              // el placeholder del `keepPreviousData` lo haga parpadear durante la
              // navegación hacia un mes pasado.
              <form
                className="mt-2 w-full space-y-2"
                noValidate
                onSubmit={(e) => {
                  e.preventDefault();
                  const parsed = Number(monthlyIncomeInput);
                  if (monthlyIncomeInput.trim() === '' || Number.isNaN(parsed) || parsed < 0) {
                    setMonthlyIncomeError('Ingresa un monto válido (0 o mayor).');
                    return monthlyIncomeRef.current?.focus();
                  }
                  setMonthlyIncomeError(null);
                  setMonthlyIncomeMutation.mutate(parsed, {
                    onSuccess: () => toast.success('Ingreso mensual guardado'),
                    onError: (error) => toast.error(getApiError(error)),
                  });
                }}
              >
                <p className="text-text-muted text-sm font-normal">
                  Define tu ingreso mensual para calcular tu balance.
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
            ) : (
              // `basis: "actual"` nunca devuelve `null` (User Story 12): esta rama solo
              // alcanza si el balance llega vacío sin ser el mes en curso, y muestra 0 en vez
              // de dejar la cifra en blanco.
              <p>{formatCurrency(flowBalanceValue ?? 0, preferredCurrency)}</p>
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
          <EmptyState
            icon={<AlertCircle size={48} className="opacity-20" />}
            message="No se pudo cargar el progreso de presupuestos."
            action={
              <Button variant="secondary" size="sm" onClick={() => refetchBudgets()}>
                Reintentar
              </Button>
            }
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
        currencyOptions={currencyOptions}
        preferredCurrency={preferredCurrency}
        emptyMessage={
          isCurrentMonth ? undefined : `No hay gastos registrados en ${monthNameLower}.`
        }
      />

      {/* Últimas 5 del mes visible (Fase 29 §F5.5) */}
      <RecentTransactionsSection
        range={monthRange}
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
