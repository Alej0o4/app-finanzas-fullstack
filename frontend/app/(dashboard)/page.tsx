'use client';

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { PieChart } from 'lucide-react';
import { api } from '@/lib/api';
import { formatCurrency, formatDate } from '@/lib/utils';
import { useCurrentUser } from '@/lib/hooks/useCurrentUser';
import { useAppConfig } from '@/providers/AppConfigProvider';
import { useState } from 'react';
import BudgetRing from '@/components/charts/BudgetRing';
import TransactionModal from '@/components/modals/TransactionModal';
import SummaryCard from '@/components/ui/SummaryCard';
import Button from '@/components/ui/Button';
import EmptyState from '@/components/ui/EmptyState';
import Skeleton from '@/components/ui/Skeleton';
import { queryKeys } from '@/lib/queryKeys';
import type { DashboardSummary, BudgetProgress, Transaction, PaginatedResponse } from '@/types/api';

export default function DashboardPage() {
  const { config } = useAppConfig();
  const { data: user } = useCurrentUser();
  const queryClient = useQueryClient();
  const [isTransactionModalOpen, setIsTransactionModalOpen] = useState(false);

  const { data: summary, isLoading: loadingSummary } = useQuery<DashboardSummary>({
    queryKey: queryKeys.dashboard.summary(),
    queryFn: async () => (await api.get('/api/dashboard/summary')).data,
  });

  const { data: budgetsProgress, isLoading: loadingBudgets } = useQuery<BudgetProgress[]>({
    queryKey: queryKeys.budgets.progress(),
    queryFn: async () => (await api.get('/api/dashboard/budgets-progress')).data,
  });

  const { data: recentTransactionsData, isLoading: loadingRecentTransactions } = useQuery<
    PaginatedResponse<Transaction>
  >({
    queryKey: queryKeys.dashboard.recentTransactions(),
    queryFn: async () => (await api.get('/api/transactions/', { params: { limit: 5 } })).data,
  });

  const recentTransactions = recentTransactionsData?.items;

  const isLoading = loadingSummary || loadingBudgets;
  const isRecentLoading = loadingRecentTransactions;

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
          <Button
            variant="primary"
            onClick={() => setIsTransactionModalOpen(true)}
          >
            Nuevo movimiento
          </Button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
        {isLoading ? (
          <>
            <Skeleton className="h-32 rounded-2xl" />
            <Skeleton className="h-32 rounded-2xl" />
            <Skeleton className="h-32 rounded-2xl" />
          </>
        ) : (
          <>
            <SummaryCard label="Balance Total">
              {summary?.balances.length ? (
                <div className="space-y-1">
                  {summary.balances.map((b) => (
                    <p key={b.currency}>{formatCurrency(b.total, b.currency)}</p>
                  ))}
                </div>
              ) : (
                <p>{formatCurrency(0, config.currency)}</p>
              )}
            </SummaryCard>
            <SummaryCard label="Ingresos del Mes" trend="up" color="var(--color-success)">
              {summary?.monthly_income_by_currency.length ? (
                <div className="space-y-1">
                  {summary.monthly_income_by_currency.map((b) => (
                    <p key={b.currency}>{formatCurrency(b.total, b.currency)}</p>
                  ))}
                </div>
              ) : (
                <p>{formatCurrency(0, config.currency)}</p>
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
                <p>{formatCurrency(0, config.currency)}</p>
              )}
            </SummaryCard>
          </>
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
              />
            ))}
          </div>
        )}
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
