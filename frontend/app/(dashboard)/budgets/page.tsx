"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, PieChart, Loader2, Edit2, Trash2, CalendarDays } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { formatCurrency, getApiError } from "@/lib/utils";
import { queryKeys } from "@/lib/queryKeys";
import ModalShell from "@/components/ui/ModalShell";
import Button from "@/components/ui/Button";
import EmptyState from "@/components/ui/EmptyState";
import { useConfirmStore } from "@/store/useConfirmStore";
import type { Category, Budget, BudgetPayload } from "@/types/api";

const getMonthName = (month: number, year: number) => {
  const date = new Date(year, month - 1);
  return new Intl.DateTimeFormat('es-CO', { month: 'long', year: 'numeric' }).format(date);
};

export default function BudgetsPage() {
  const queryClient = useQueryClient();

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingBudget, setEditingBudget] = useState<Budget | null>(null);

  const [categoryId, setCategoryId] = useState("");
  const [amount, setAmount] = useState("");
  const getCurrentMonthYear = () => {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
  };
  const [monthYear, setMonthYear] = useState(getCurrentMonthYear);

  const { data: budgets, isLoading: loadingBudgets } = useQuery<Budget[]>({
    queryKey: queryKeys.budgets.all(),
    queryFn: async () => (await api.get("/api/budgets/")).data,
  });

  const { data: categories } = useQuery<Category[]>({
    queryKey: queryKeys.categories.all(),
    queryFn: async () => (await api.get("/api/categories/")).data,
  });

  const expenseCategories = categories?.filter(c => c.type === "expense") || [];

  const saveMutation = useMutation({
    mutationFn: async (budgetData: BudgetPayload) => {
      if (editingBudget) {
        return (await api.put(`/api/budgets/${editingBudget.id}`, budgetData)).data;
      } else {
        return (await api.post("/api/budgets/", budgetData)).data;
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.budgets.all() });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.summary() });
      queryClient.invalidateQueries({ queryKey: queryKeys.budgets.progress() });
      toast.success("Presupuesto guardado");
      closeModal();
    },
    onError: (error: unknown) => {
      toast.error(getApiError(error));
    }
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/api/budgets/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.budgets.all() });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.summary() });
      queryClient.invalidateQueries({ queryKey: queryKeys.budgets.progress() });
      toast.success("Presupuesto eliminado");
    },
    onError: (error: unknown) => {
      toast.error(getApiError(error));
    }
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const [yearStr, monthStr] = monthYear.split("-");

    saveMutation.mutate({
      category_id: Number(categoryId),
      amount_limit: Number(amount),
      month: Number(monthStr),
      year: Number(yearStr)
    });
  };

  const openCreateModal = () => {
    setEditingBudget(null);
    setCategoryId("");
    setAmount("");
    setMonthYear(getCurrentMonthYear());
    setIsModalOpen(true);
  };

  const openEditModal = (budget: Budget) => {
    setEditingBudget(budget);
    setCategoryId(budget.category_id.toString());
    setAmount(budget.amount_limit.toString());
    const formattedMonth = budget.month < 10 ? `0${budget.month}` : budget.month;
    setMonthYear(`${budget.year}-${formattedMonth}`);
    setIsModalOpen(true);
  };

  const closeModal = () => {
    setIsModalOpen(false);
    setEditingBudget(null);
  };

  if (loadingBudgets) return <div className="p-8 text-text-muted flex items-center gap-2"><Loader2 className="animate-spin" /> Cargando presupuestos...</div>;

  return (
    <div className="space-y-6 relative">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold font-sans text-text">Tus Presupuestos</h1>
          <p className="text-sm text-text-muted">Establece límites y controla tus gastos mensuales.</p>
        </div>
        <button
          onClick={openCreateModal}
          className="bg-primary hover:bg-primary-dark text-background font-semibold px-4 py-2 rounded-xl flex items-center space-x-2 transition-colors cursor-pointer"
        >
          <Plus size={18} />
          <span>Nuevo Presupuesto</span>
        </button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {(!budgets || budgets.length === 0) ? (
          <div className="col-span-full">
            <EmptyState
              icon={<PieChart size={48} className="opacity-20" />}
              message="No has definido ningún límite para este mes."
            />
          </div>
        ) : (
          budgets.map((budget) => {
            const category = categories?.find(c => c.id === budget.category_id);
            return (
              <div key={budget.id} className="bg-surface border border-border/70 rounded-2xl p-5 hover:border-primary/30 transition-colors group">
                <div className="flex justify-between items-start mb-4">
                  <div className="flex items-center space-x-3">
                    <div className="p-2 bg-background rounded-lg text-primary">
                      <PieChart size={20} />
                    </div>
                    <div>
                      <h3 className="font-medium text-text">{category?.name || "Categoría eliminada"}</h3>
                      <p className="text-xs text-text-muted capitalize flex items-center gap-1 mt-0.5">
                        <CalendarDays size={12} />
                        {getMonthName(budget.month, budget.year)}
                      </p>
                    </div>
                  </div>
                  <div className="flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button onClick={() => openEditModal(budget)} className="text-text-muted hover:text-primary p-1 transition-colors">
                      <Edit2 size={16} />
                    </button>
                    <button
                      onClick={() => useConfirmStore.getState().confirm("¿Eliminar este presupuesto?", () => deleteMutation.mutate(budget.id))}
                      className="text-text-muted hover:text-danger p-1 transition-colors"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </div>
                <div className="mt-4 pt-4 border-t border-border/40">
                  <p className="text-xs text-text-muted uppercase tracking-wider mb-1">Límite mensual</p>
                  <p className="text-2xl font-semibold font-sans text-text">
                    {formatCurrency(budget.amount_limit, budget.currency)}
                  </p>
                </div>
              </div>
            );
          })
        )}
      </div>

      <ModalShell isOpen={isModalOpen} onClose={closeModal} title={editingBudget ? "Editar Presupuesto" : "Definir Presupuesto"}>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-text-muted uppercase tracking-wider pl-1">Categoría a limitar</label>
            <select required value={categoryId} onChange={(e) => setCategoryId(e.target.value)} className="w-full bg-background border border-border/70 rounded-xl px-4 py-2.5 text-sm text-text focus:outline-none focus:ring-2 focus:ring-primary/50 transition-all appearance-none">
              <option value="" disabled>Selecciona un gasto...</option>
              {expenseCategories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-text-muted uppercase tracking-wider pl-1">Monto Máximo</label>
            <input type="number" required value={amount} onChange={(e) => setAmount(e.target.value)} className="w-full bg-background border border-border/70 rounded-xl px-4 py-2.5 text-sm text-text focus:outline-none focus:ring-2 focus:ring-primary/50 transition-all" placeholder="0" />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-text-muted uppercase tracking-wider pl-1">Mes y Año</label>
            <input
              type="month"
              required
              value={monthYear}
              onChange={(e) => setMonthYear(e.target.value)}
              className="w-full bg-background border border-border/70 rounded-xl px-4 py-2.5 text-sm text-text focus:outline-none focus:ring-2 focus:ring-primary/50 transition-all style-color-scheme-dark"
            />
          </div>

          <div className="flex gap-3 mt-6">
            <Button type="button" variant="ghost" onClick={closeModal} className="flex-1">Cancelar</Button>
            <Button type="submit" variant="primary" loading={saveMutation.isPending} className="flex-1">Guardar</Button>
          </div>
        </form>
      </ModalShell>
    </div>
  );
}
