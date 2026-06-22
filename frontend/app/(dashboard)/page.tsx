"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, RefreshCw, PieChart } from "lucide-react";
import { api } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";
import { useState } from "react";
import BudgetRing from "@/components/charts/BudgetRing";

interface DashboardSummary {
  total_balance: number;
  monthly_budget: number;
  monthly_expenses: number;
}

// Adaptaremos esta interfaz a lo que devuelva tu backend
interface BudgetProgress {
  category_id: number;
  category_name: string;
  amount_limit: number; // El amount_limit
  spent: number;
}

export default function DashboardPage() {
  const queryClient = useQueryClient();
  const [isRefreshing, setIsRefreshing] = useState(false);

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

  const handleManualRefresh = async () => {
    setIsRefreshing(true);
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["dashboardSummary"] }),
      queryClient.invalidateQueries({ queryKey: ["budgets-progress"] })
    ]);
    setIsRefreshing(false);
  };

  const isLoading = loadingSummary || loadingBudgets;

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
          <h1 className="text-3xl font-bold tracking-tight font-sans">Buenas tardes, Alejandro</h1>
          <p className="text-text-muted text-sm mt-1">Aquí tienes el estado actual de tus finanzas orgánicas.</p>
        </div>
        
        <button 
          onClick={handleManualRefresh}
          disabled={isRefreshing}
          className="flex items-center space-x-2 bg-surface hover:bg-neutral-800 border border-neutral-800/60 px-4 py-2 rounded-xl text-sm font-medium text-text-muted hover:text-primary transition-colors disabled:opacity-50 cursor-pointer"
        >
          <RefreshCw size={16} className={isRefreshing ? "animate-spin text-primary" : ""} />
          <span>{isRefreshing ? "Actualizando..." : "Sincronizar"}</span>
        </button>
      </div>

      {/* Tarjetas de Métricas Principales */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="p-6 bg-surface border border-neutral-800/40 rounded-2xl shadow-sm transition-transform hover:scale-[1.02] duration-300">
          <p className="text-xs font-medium text-text-muted uppercase tracking-wider">Balance Total</p>
          <p className="text-3xl font-semibold text-text mt-2 font-sans">
            {formatCurrency(summary?.total_balance || 0)}
          </p>
        </div>
        <div className="p-6 bg-surface border border-neutral-800/40 rounded-2xl shadow-sm transition-transform hover:scale-[1.02] duration-300">
          <p className="text-xs font-medium text-text-muted uppercase tracking-wider">Presupuesto Mensual</p>
          <p className="text-3xl font-semibold text-primary mt-2 font-sans">
            {formatCurrency(summary?.monthly_budget || 0)}
          </p>
        </div>
        <div className="p-6 bg-surface border border-neutral-800/40 rounded-2xl shadow-sm transition-transform hover:scale-[1.02] duration-300">
          <p className="text-xs font-medium text-text-muted uppercase tracking-wider">Gastos del Mes</p>
          <p className="text-3xl font-semibold text-text mt-2 font-sans">
            {formatCurrency(summary?.monthly_expenses || 0)}
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
          <div className="p-12 border border-neutral-800/40 border-dashed rounded-3xl text-center flex flex-col items-center text-text-muted">
            <p className="text-sm">Aún no hay datos de progreso. Asegúrate de tener presupuestos definidos y gastos registrados en este mes.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
            {budgetsProgress.map((budget) => (
              <BudgetRing 
                key={budget.category_id}
                categoryName={budget.category_name}
                budgetAmount={budget.amount_limit}
                spentAmount={budget.spent}
              />
            ))}
          </div>
        )}
      </div>

    </div>
  );
}