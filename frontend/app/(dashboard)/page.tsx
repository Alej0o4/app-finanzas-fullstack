"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { PieChart } from "lucide-react";
import { api } from "@/lib/api";
import { formatCurrency, formatDate } from "@/lib/utils";
import { useCurrentUser } from "@/lib/hooks/useCurrentUser";
import { useState } from "react";
import BudgetRing from "@/components/charts/BudgetRing";
import TransactionModal from "@/components/modals/TransactionModal";
import SummaryCard from "@/components/ui/SummaryCard";
import EmptyState from "@/components/ui/EmptyState";
import Skeleton from "@/components/ui/Skeleton";
import { queryKeys } from "@/lib/queryKeys";
import type { DashboardSummary, BudgetProgress, Transaction, PaginatedResponse } from "@/types/api";

export default function DashboardPage() {
  const { data: user } = useCurrentUser();
  const queryClient = useQueryClient();
  const [isTransactionModalOpen, setIsTransactionModalOpen] = useState(false);

  const { data: summary, isLoading: loadingSummary } = useQuery<DashboardSummary>({
    queryKey: queryKeys.dashboard.summary(),
    queryFn: async () => (await api.get("/api/dashboard/summary")).data,
  });

  const { data: budgetsProgress, isLoading: loadingBudgets } = useQuery<BudgetProgress[]>({
    queryKey: queryKeys.budgets.progress(),
    queryFn: async () => (await api.get("/api/dashboard/budgets-progress")).data,
  });

  const { data: recentTransactionsData, isLoading: loadingRecentTransactions } = useQuery<PaginatedResponse<Transaction>>({
    queryKey: queryKeys.dashboard.recentTransactions(),
    queryFn: async () => (await api.get("/api/transactions/", { params: { limit: 5 } })).data,
  });

  const recentTransactions = recentTransactionsData?.items;

  const isLoading = loadingSummary || loadingBudgets;
  const isRecentLoading = loadingRecentTransactions;

  return (
    <div className="space-y-10 pb-10">

      {/* Encabezado */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight font-sans">Buenas tardes, {user?.full_name?.split(" ")[0] || "de nuevo"}</h1>
          <p className="text-text-muted text-sm mt-1">Aquí tienes el estado actual de tus finanzas orgánicas.</p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setIsTransactionModalOpen(true)}
            className="flex items-center space-x-2 bg-primary hover:bg-primary-dark text-background px-4 py-2 rounded-xl text-sm font-medium transition-colors cursor-pointer"
          >
            <span>Nuevo movimiento</span>
          </button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {isLoading ? (
          <>
            <Skeleton className="h-32 rounded-2xl" />
            <Skeleton className="h-32 rounded-2xl" />
            <Skeleton className="h-32 rounded-2xl" />
          </>
        ) : (
          <>
            <SummaryCard label="Balance Total" value={formatCurrency(summary?.total_balance || 0)} />
            <SummaryCard label="Ingresos del Mes" value={formatCurrency(summary?.monthly_income || 0)} trend="up" color="#34d399" />
            <SummaryCard label="Gastos del Mes" value={formatCurrency(summary?.monthly_expense || 0)} trend="down" color="#fb7185" />
          </>
        )}
      </div>

      {/* Budget Rings */}
      <div>
        <div className="flex items-center space-x-2 mb-6">
          <PieChart className="text-primary" size={20} />
          <h2 className="text-xl font-bold font-sans text-text">Ejecución de Presupuestos</h2>
        </div>

        {isLoading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="flex flex-col items-center gap-3 p-6">
                <Skeleton className="h-24 w-24 rounded-full" />
                <Skeleton className="h-4 w-20" />
                <Skeleton className="h-3 w-16" />
              </div>
            ))}
          </div>
        ) : (!budgetsProgress || budgetsProgress.length === 0) ? (
          <EmptyState
            icon={<PieChart size={48} className="opacity-20" />}
            message="Aún no hay datos de progreso."
            description="Asegúrate de tener presupuestos definidos y gastos registrados en este mes."
          />
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
            {budgetsProgress.map((budget, index) => (
              <BudgetRing
                key={budget.budget_id || `budget-ring-${index}`}
                categoryName={budget.category_name}
                budgetAmount={Number(budget.amount_limit)}
                spentAmount={Number(budget.spent)}
              />
            ))}
          </div>
        )}
      </div>

      {/* Recent Transactions */}
      <div>
        <div className="flex items-center justify-between gap-3 mb-6">
          <div>
            <h2 className="text-xl font-bold font-sans text-text">Transacciones recientes</h2>
            <p className="text-sm text-text-muted mt-1">Últimos movimientos registrados en tu cuenta.</p>
          </div>
        </div>

        <div className="bg-surface border border-border/70 rounded-3xl overflow-hidden shadow-sm">
          {isRecentLoading ? (
            <div className="divide-y divide-border/40">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="p-4 sm:px-6 flex items-center justify-between gap-4">
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
          ) : (!recentTransactions || recentTransactions.length === 0) ? (
            <EmptyState
              icon={<PieChart size={48} className="opacity-20" />}
              message="No hay transacciones recientes."
            />
          ) : (
            <div className="divide-y divide-border/40">
              {recentTransactions.map((tx) => {
                const isExpense = tx.type === "expense";

                return (
                  <div key={tx.id} className="p-4 sm:px-6 hover:bg-surface-elevated transition-colors flex items-center justify-between gap-4">
                    <div>
                      <p className="font-medium text-text text-sm">{tx.description}</p>
                      <p className="text-xs text-text-muted capitalize mt-0.5">{formatDate(tx.date)}</p>
                    </div>
                    <p className={`font-semibold font-sans ${isExpense ? "text-text" : "text-primary"}`}>
                      {isExpense ? "-" : "+"}{formatCurrency(tx.amount)}
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
