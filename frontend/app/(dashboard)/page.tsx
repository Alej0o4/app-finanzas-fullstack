"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, PieChart } from "lucide-react";
import { api } from "@/lib/api";
import { formatCurrency, formatDate } from "@/lib/utils";
import { useCurrentUser } from "@/lib/hooks/useCurrentUser";
import { useState } from "react";
import BudgetRing from "@/components/charts/BudgetRing";
import TransactionModal from "@/components/modals/TransactionModal";

interface DashboardSummary {
  total_balance: number;
  monthly_income: number;
  monthly_expense: number;
}

// Adaptaremos esta interfaz a lo que devuelva tu backend
interface BudgetProgress {
  category_id: number;
  category_name: string;
  amount_limit: number; // El amount_limit
  spent: number;
}

interface RecentTransaction {
  id: number;
  description: string;
  amount: number;
  type: string;
  date: string;
  account_id: number;
  category_id: number;
}

export default function DashboardPage() {
  const { data: user } = useCurrentUser();
  const queryClient = useQueryClient();
  const [isTransactionModalOpen, setIsTransactionModalOpen] = useState(false);

  // 1. Petición del Resumen General
  const { data: summary, isLoading: loadingSummary } = useQuery<DashboardSummary>({
    queryKey: ["dashboardSummary"],
    queryFn: async () => (await api.get("/api/dashboard/summary")).data,
  });

  // 2. Petición del Progreso de Presupuestos
  const { data: budgetsProgress, isLoading: loadingBudgets } = useQuery<BudgetProgress[]>({
    queryKey: ["budgets-progress"],
    queryFn: async () => (await api.get("/api/dashboard/budgets-progress")).data,
  });

  const { data: recentTransactions, isLoading: loadingRecentTransactions } = useQuery<RecentTransaction[]>({
    queryKey: ["recent-transactions", 5],
    queryFn: async () => (await api.get("/api/transactions/", { params: { limit: 5 } })).data,
  });

  const isLoading = loadingSummary || loadingBudgets;
  const isRecentLoading = loadingRecentTransactions;

  if (isLoading) {
    return (
      <div className="h-[80vh] flex flex-col items-center justify-center space-y-4 text-text-muted">
        <Loader2 size={32} className="animate-spin text-primary" />
        <p className="text-sm">Analizando tu ecosistema financiero...</p>
      </div>
    );
  }

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

      {/* Tarjetas de Métricas Principales */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="p-6 bg-surface border border-border/50 rounded-2xl shadow-sm transition-transform hover:scale-[1.02] duration-300">
          <p className="text-xs font-medium text-text-muted uppercase tracking-wider">Balance Total</p>
          <p className="text-3xl font-semibold text-text mt-2 font-sans">
            {formatCurrency(summary?.total_balance || 0)}
          </p>
        </div>
        <div className="p-6 bg-surface border border-border/50 rounded-2xl shadow-sm transition-transform hover:scale-[1.02] duration-300">
          <p className="text-xs font-medium text-text-muted uppercase tracking-wider">Ingresos del Mes</p>
          <p className="text-3xl font-semibold text-primary mt-2 font-sans">
            {formatCurrency(summary?.monthly_income || 0)}
          </p>
        </div>
        <div className="p-6 bg-surface border border-border/50 rounded-2xl shadow-sm transition-transform hover:scale-[1.02] duration-300">
          <p className="text-xs font-medium text-text-muted uppercase tracking-wider">Gastos del Mes</p>
          <p className="text-3xl font-semibold text-text mt-2 font-sans">
            {formatCurrency(summary?.monthly_expense || 0)}
          </p>
        </div>
      </div>

      {/* Sección: Progreso de Presupuestos (Visual) */}
      <div>
        <div className="flex items-center space-x-2 mb-6">
          <PieChart className="text-primary" size={20} />
          <h2 className="text-xl font-bold font-sans text-text">Ejecución de Presupuestos</h2>
        </div>

        {(!budgetsProgress || budgetsProgress.length === 0) ? (
          <div className="p-12 border border-border/50 border-dashed rounded-3xl text-center flex flex-col items-center text-text-muted">
            <p className="text-sm">Aún no hay datos de progreso. Asegúrate de tener presupuestos definidos y gastos registrados en este mes.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
            {/* Agregamos el "index" como segundo parámetro del map */}
            {budgetsProgress.map((budget, index) => (
              <BudgetRing 
                // PLAN B PARA EL KEY: Si category_id no existe, usa el índice del array
                key={budget.category_id || `budget-ring-${index}`}
                
                categoryName={budget.category_name}
                // FORZAMOS LA CONVERSIÓN: Por si el Decimal de Python llega como String ("50.00")
                budgetAmount={Number(budget.amount_limit)} 
                spentAmount={Number(budget.spent)}
              />
            ))}
          </div>
        )}
      </div>

      <div>
        <div className="flex items-center justify-between gap-3 mb-6">
          <div>
            <h2 className="text-xl font-bold font-sans text-text">Transacciones recientes</h2>
            <p className="text-sm text-text-muted mt-1">Últimos movimientos registrados en tu cuenta.</p>
          </div>
        </div>

        <div className="bg-surface border border-border/70 rounded-3xl overflow-hidden shadow-sm">
          {isRecentLoading ? (
            <div className="p-8 text-text-muted flex items-center gap-2">
              <Loader2 className="animate-spin text-primary" size={18} />
              Cargando transacciones recientes...
            </div>
          ) : (!recentTransactions || recentTransactions.length === 0) ? (
            <div className="p-12 text-center flex flex-col items-center text-text-muted">
              <p>No hay transacciones recientes para mostrar.</p>
            </div>
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
          queryClient.invalidateQueries({ queryKey: ["recent-transactions"] });
        }}
        title="Registrar movimiento"
        defaultType="expense"
      />

    </div>
  );
}