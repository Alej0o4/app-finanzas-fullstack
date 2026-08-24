'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { PieChart, Tags } from 'lucide-react';
import { toast } from 'sonner';
import { api } from '@/lib/api';
import { formatCurrency, formatDate, getApiError } from '@/lib/utils';
import { useCurrentUser } from '@/lib/hooks/useCurrentUser';
import { useAppConfig } from '@/providers/AppConfigProvider';
import { useState } from 'react';
import BudgetRing from '@/components/charts/BudgetRing';
import CategoryBreakdownBars from '@/components/charts/CategoryBreakdownBars';
import TransactionModal from '@/components/modals/TransactionModal';
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

// Mismo formato que analytics/page.tsx::formatISOForBackend. El spec (§11.4) permite duplicar
// este helper pequeño en lugar de extraerlo compartido para este alcance.
const formatISOForBackend = (date: Date) => {
  const pad = (value: number) => String(value).padStart(2, '0');

  return (
    [date.getFullYear(), pad(date.getMonth() + 1), pad(date.getDate())].join('-') +
    `T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
  );
};

export default function DashboardPage() {
  const { config } = useAppConfig();
  const { data: user } = useCurrentUser();
  const queryClient = useQueryClient();
  const [isTransactionModalOpen, setIsTransactionModalOpen] = useState(false);
  const [monthlyIncomeInput, setMonthlyIncomeInput] = useState('');

  const now = new Date();
  const monthStartISO = formatISOForBackend(new Date(now.getFullYear(), now.getMonth(), 1));
  const todayISO = formatISOForBackend(now);
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

  const isLoading = loadingSummary || loadingBudgets;
  const isRecentLoading = loadingRecentTransactions;

  // Balance del mes calculado POR EL BACKEND (summary.monthly_flow_balance). Nunca se resta
  // en el cliente. Tres estados distinguidos: undefined = query en carga/error, null = el
  // usuario no ha fijado monthly_income, number = valor listo para pintar.
  const flowBalance = summary?.monthly_flow_balance;
  const flowBalanceValue = typeof flowBalance === 'number' ? flowBalance : null;
  const flowIsPositive = (flowBalanceValue ?? 0) >= 0;
  const flowTrend =
    flowBalanceValue === null ? undefined : flowIsPositive ? ('up' as const) : ('down' as const);
  const flowColor =
    flowBalanceValue === null
      ? undefined
      : flowIsPositive
        ? 'var(--color-success)'
        : 'var(--color-danger)';

  return (
    <div className="space-y-6 pb-10 sm:space-y-10">
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

        <div className="flex items-center gap-3">
          <Button variant="primary" onClick={() => setIsTransactionModalOpen(true)}>
            Nuevo movimiento
          </Button>
        </div>
      </div>

      {/* Summary Cards — la card principal mide flujo mensual (Fase 11 §11.3); el saldo total
          de cuentas vive ahora en /accounts como vista secundaria (§11.5). */}
      <div className="space-y-6">
        {loadingSummary ? (
          <Skeleton className="h-36 rounded-2xl" />
        ) : (
          <SummaryCard label="Balance del mes" size="lg" trend={flowTrend} color={flowColor}>
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
                  setMonthlyIncomeMutation.mutate(parsed);
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

        <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
          {loadingSummary ? (
            <>
              <Skeleton className="h-32 rounded-2xl" />
              <Skeleton className="h-32 rounded-2xl" />
            </>
          ) : (
            <>
              <SummaryCard label="Ingresos del Mes" trend="up" color="var(--color-success)">
                {summary?.monthly_income_by_currency.length ? (
                  <div className="space-y-1">
                    {summary.monthly_income_by_currency.map((b) => (
                      <p key={b.currency}>{formatCurrency(b.total, b.currency)}</p>
                    ))}
                  </div>
                ) : (
                  <p>{formatCurrency(0, preferredCurrency)}</p>
                )}
              </SummaryCard>
              <SummaryCard label="Gastos del Mes" trend="down" color="var(--color-danger)">
                {summary?.monthly_expense_by_currency.length ? (
                  <div className="space-y-1">
                    {summary.monthly_expense_by_currency.map((b) => (
                      <p key={b.currency}>{formatCurrency(b.total, b.currency)}</p>
                    ))}
                  </div>
                ) : (
                  <p>{formatCurrency(0, preferredCurrency)}</p>
                )}
              </SummaryCard>
            </>
          )}
        </div>
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

        <div className="bg-surface border-border/70 overflow-hidden rounded-3xl border shadow-sm">
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
                      className={`shrink-0 font-sans text-sm font-semibold sm:text-base ${isExpense ? 'text-text' : 'text-primary'}`}
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

      <TransactionModal
        isOpen={isTransactionModalOpen}
        onClose={() => setIsTransactionModalOpen(false)}
        onSuccess={() => {
          queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.recentTransactions() });
        }}
        title="Registrar movimiento"
        defaultType="expense"
      />
    </div>
  );
}
