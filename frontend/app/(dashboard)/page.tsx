'use client';

import { useQuery } from '@tanstack/react-query';
import { PieChart, Tags } from 'lucide-react';
import { toast } from 'sonner';
import { useSearchParams } from 'next/navigation';
import { api } from '@/lib/api';
import { formatCurrency, formatDate, getApiError } from '@/lib/utils';
import { useCurrentUser } from '@/lib/hooks/useCurrentUser';
import { useSetMonthlyIncome } from '@/lib/hooks/useSetMonthlyIncome';
import { useAppConfig } from '@/providers/AppConfigProvider';
import { Suspense, useState } from 'react';
import BudgetRing from '@/components/charts/BudgetRing';
import CategoryBreakdownBars from '@/components/charts/CategoryBreakdownBars';
import SummaryCard from '@/components/ui/SummaryCard';
import Button from '@/components/ui/Button';
import EmptyState from '@/components/ui/EmptyState';
import Input from '@/components/ui/Input';
import Skeleton from '@/components/ui/Skeleton';
import { queryKeys } from '@/lib/queryKeys';
import type {
  DashboardSummary,
  BudgetProgress,
  Transaction,
  PaginatedResponse,
  CategoryDistributionItem,
} from '@/types/api';

function DashboardScreen() {
  const { config } = useAppConfig();
  const { data: user } = useCurrentUser();
  const searchParams = useSearchParams();
  const [monthlyIncomeInput, setMonthlyIncomeInput] = useState('');

  const now = new Date();
  // .toISOString() (no formateo manual): manda el instante UTC real. Un string armado a mano
  // con los getters locales (getHours() etc.) sin sufijo de zona horaria se interpretaba como
  // UTC en el backend (sesión de Postgres en UTC) — con el servidor en America/Bogota (UTC-5),
  // eso recortaba "ahora" 5 horas antes del real y excluía las transacciones recién creadas.
  const monthStartISO = new Date(now.getFullYear(), now.getMonth(), 1).toISOString();
  const todayISO = now.toISOString();
  // La moneda preferida del usuario; config.currency es su espejo desde preferencias.
  const preferredCurrency = user?.preferred_currency ?? config.currency;

  const { data: summary, isLoading: loadingSummary } = useQuery<DashboardSummary>({
    queryKey: queryKeys.dashboard.summary(),
    queryFn: async () => (await api.get('dashboard/summary')).data,
  });

  const { data: budgetsProgress, isLoading: loadingBudgets } = useQuery<BudgetProgress[]>({
    queryKey: queryKeys.budgets.progress(),
    queryFn: async () => (await api.get('dashboard/budgets-progress')).data,
  });

  const { data: recentTransactionsData, isLoading: loadingRecentTransactions } = useQuery<
    PaginatedResponse<Transaction>
  >({
    queryKey: queryKeys.dashboard.recentTransactions(),
    queryFn: async () => (await api.get('transactions/', { params: { limit: 5 } })).data,
  });

  // Desglose de gastos del mes por categoría (Fase 11 §11.4). Decisión 11.1.1: se pasa
  // `currency` explícito aunque el backend ya defaultea a la moneda preferida.
  const { data: categoryBreakdown, isLoading: loadingCategoryBreakdown } = useQuery<
    CategoryDistributionItem[]
  >({
    queryKey: queryKeys.dashboard.categoryBreakdown(),
    queryFn: async () =>
      (
        await api.get('dashboard/category-distribution', {
          params: {
            start_date: monthStartISO,
            end_date: todayISO,
            type: 'expense',
            currency: user?.preferred_currency,
          },
        })
      ).data,
  });

  const recentTransactions = recentTransactionsData?.items;

  // Fase 11 §11.3, Decisión 11.3.2: vía de escape inline para fijar el ingreso mensual sin
  // salir del dashboard (el flujo guiado completo llega con el onboarding de Fase 15).
  const setMonthlyIncomeMutation = useSetMonthlyIncome();

  const isLoading = loadingSummary || loadingBudgets;
  const isRecentLoading = loadingRecentTransactions;

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

  // Fase 15 §15.5, Decisión 15.0.1 (revisada): originalmente `total === 1`, pero eso se
  // rompió al agregar la transacción semilla del ingreso declarado (§15.3.3) — con ella, la
  // captura guiada del primer gasto ya es la SEGUNDA transacción del usuario, y el banner
  // nunca se mostraba. Se reemplaza por el mismo mecanismo que ya usa /capture (`?onboarding=1`,
  // Decisión 15.0.2): TransactionCaptureForm redirige aquí con ese query param solo al terminar
  // la captura guiada, sin importar cuántas transacciones existan.
  const cameFromOnboardingCapture = searchParams.get('onboarding') === '1';
  const preferredExpense =
    summary?.monthly_expense_by_currency.find((b) => b.currency === preferredCurrency)?.total ?? 0;

  // Fase 19 §19.2.1/19.2.2: fila secundaria compacta dentro de la card principal — reemplaza
  // el grid de 2 columnas (Ingresos/Gastos). Se muestra siempre, aún con monthly_flow_balance
  // null (son sumas de transacciones del mes, no el ingreso declarado).
  const secondaryStats = (
    <>
      <div className="flex-1">
        <p className="text-text-muted text-xs font-medium">Ingresos del Mes</p>
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
        <p className="text-text-muted text-xs font-medium">Gastos del Mes</p>
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
          Los montos Decimal llegan como string (Decisión 15.6), de ahí los Number(...). */}
      {cameFromOnboardingCapture && (
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
      </div>

      {/* Summary Cards — la card principal mide flujo mensual (Fase 11 §11.3); el saldo total
          de cuentas vive ahora en /accounts como vista secundaria (§11.5). */}
      <div className="space-y-6">
        {loadingSummary ? (
          <Skeleton className="h-44 rounded-2xl" />
        ) : (
          <SummaryCard
            label="Balance del mes"
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
            ) : summary ? (
              <form
                className="mt-2 w-full space-y-2"
                onSubmit={(e) => {
                  e.preventDefault();
                  const parsed = Number(monthlyIncomeInput);
                  if (monthlyIncomeInput.trim() === '' || Number.isNaN(parsed) || parsed < 0)
                    return;
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
                    type="number"
                    inputMode="decimal"
                    required
                    min={0}
                    step="0.01"
                    aria-label="Ingreso mensual"
                    placeholder={`Ej. 3000000 (${preferredCurrency})`}
                    value={monthlyIncomeInput}
                    onChange={(e) => setMonthlyIncomeInput(e.target.value)}
                    className="bg-background"
                  />
                  <Button type="submit" loading={setMonthlyIncomeMutation.isPending}>
                    Guardar
                  </Button>
                </div>
              </form>
            ) : (
              <p>{formatCurrency(0, preferredCurrency)}</p>
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
        ) : !budgetsProgress || budgetsProgress.length === 0 ? (
          <EmptyState
            icon={<PieChart size={48} className="opacity-20" />}
            message="Aún no hay datos de progreso."
            description="Asegúrate de tener presupuestos definidos y gastos registrados en este mes."
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

      {/* Gastos por categoría del mes en curso (Fase 11 §11.4) */}
      <div>
        <div className="mb-6 flex items-center space-x-2">
          <Tags className="text-primary" size={20} />
          <h2 className="text-text font-sans text-xl font-bold">Gastos por Categoría</h2>
        </div>

        <CategoryBreakdownBars data={categoryBreakdown} isLoading={loadingCategoryBreakdown} />
      </div>

      {/* Recent Transactions */}
      <div>
        <div className="mb-6 flex items-center justify-between gap-3">
          <div>
            <h2 className="text-text font-sans text-xl font-bold">Transacciones recientes</h2>
            <p className="text-text-muted mt-1 text-sm">
              Últimos movimientos registrados en tu cuenta.
            </p>
          </div>
        </div>

        <div className="bg-surface border-border/70 shadow-background/20 overflow-hidden rounded-3xl border shadow-sm">
          {isRecentLoading ? (
            <div className="divide-border/40 divide-y">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="flex items-center justify-between gap-4 p-4 sm:px-6">
                  <div className="flex items-center gap-3">
                    <Skeleton className="h-10 w-10 rounded-full" />
                    <div className="space-y-2">
                      <Skeleton className="h-4 w-40" />
                      <Skeleton className="h-3 w-24" />
                    </div>
                  </div>
                  <Skeleton className="h-5 w-20" />
                </div>
              ))}
            </div>
          ) : !recentTransactions || recentTransactions.length === 0 ? (
            <EmptyState
              icon={<PieChart size={48} className="opacity-20" />}
              message="No hay transacciones recientes."
            />
          ) : (
            <div className="divide-border/40 divide-y">
              {recentTransactions.map((tx) => {
                const isExpense = tx.type === 'expense';

                return (
                  <div
                    key={tx.id}
                    className="hover:bg-surface-elevated flex items-center justify-between gap-3 p-3 transition-colors sm:gap-4 sm:p-4 sm:px-6"
                  >
                    <div className="min-w-0">
                      <p className="text-text truncate text-sm font-medium">{tx.description}</p>
                      <p className="text-text-muted mt-0.5 text-xs capitalize">
                        {formatDate(tx.date, config.locale)}
                      </p>
                    </div>
                    <p
                      className={`shrink-0 font-sans text-sm font-semibold tabular-nums sm:text-base ${isExpense ? 'text-text' : 'text-primary'}`}
                    >
                      {isExpense ? '-' : '+'}
                      {formatCurrency(tx.amount, config.currency)}
                    </p>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// useSearchParams() exige un límite <Suspense> propio (mismo patrón que capture/page.tsx
// y analytics/page.tsx) — sin esto, Next falla el build.
export default function DashboardPage() {
  return (
    <Suspense fallback={null}>
      <DashboardScreen />
    </Suspense>
  );
}
