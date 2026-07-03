"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, PieChart, Loader2, Edit2, Trash2, CalendarDays } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";
import { useConfirmStore } from "@/store/useConfirmStore";

// 1. Interfaces
interface Category { id: number; name: string; type: string; }
interface Budget {
  id: number;
  category_id: number;
  amount_limit: number;
  month: number;
  year: number;
}

// Utilidad para mostrar el mes en texto (ej. "Junio 2026")
const getMonthName = (month: number, year: number) => {
  const date = new Date(year, month - 1);
  return new Intl.DateTimeFormat('es-CO', { month: 'long', year: 'numeric' }).format(date);
};

export default function BudgetsPage() {
  const queryClient = useQueryClient();
  
  // Estados para Crear/Editar
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingBudget, setEditingBudget] = useState<Budget | null>(null);
  
  const [categoryId, setCategoryId] = useState("");
  const [amount, setAmount] = useState("");
  const getCurrentMonthYear = () => {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
  };
  const [monthYear, setMonthYear] = useState(getCurrentMonthYear);

  // 2. Traer datos
  const { data: budgets, isLoading: loadingBudgets } = useQuery<Budget[]>({
    queryKey: ["budgets"],
    queryFn: async () => (await api.get("/api/budgets/")).data,
  });

  const { data: categories } = useQuery<Category[]>({
    queryKey: ["categories"],
    queryFn: async () => (await api.get("/api/categories/")).data,
  });

  // Filtramos solo categorías de gasto para los presupuestos
  const expenseCategories = categories?.filter(c => c.type === "expense") || [];

  // 3. Mutaciones
  interface BudgetPayload {
    category_id: number;
    amount_limit: number;
    month: number;
    year: number;
  }

  const saveMutation = useMutation({
    mutationFn: async (budgetData: BudgetPayload) => {
      if (editingBudget) {
        return (await api.put(`/api/budgets/${editingBudget.id}`, budgetData)).data;
      } else {
        return (await api.post("/api/budgets/", budgetData)).data;
      }
    },
    onSuccess: () => {
      // Invalidamos presupuestos y el dashboard donde mostraremos el progreso
      queryClient.invalidateQueries({ queryKey: ["budgets"] });
      queryClient.invalidateQueries({ queryKey: ["dashboardSummary"] });
      queryClient.invalidateQueries({ queryKey: ["budgets-progress"] });
      closeModal();
    },
    onError: (error: unknown) => {
      const detail = (error as { response?: { data?: { detail?: string } } }).response?.data?.detail;
      toast.error(detail || "Error al guardar el presupuesto");
    }
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/api/budgets/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["budgets"] });
      queryClient.invalidateQueries({ queryKey: ["dashboardSummary"] });
      queryClient.invalidateQueries({ queryKey: ["budgets-progress"] });
    }
  });

  // Handlers
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // Extraemos el año y el mes del input "YYYY-MM"
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
    // Formateamos para el input type="month" (añadimos 0 al mes si es menor a 10)
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

      {/* Grid de Presupuestos */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {(!budgets || budgets.length === 0) ? (
          <div className="col-span-full p-12 text-center flex flex-col items-center text-text-muted bg-surface border border-border/70 rounded-3xl">
            <PieChart size={48} className="mb-4 opacity-20" />
            <p>No has definido ningún límite para este mes.</p>
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
                    {formatCurrency(budget.amount_limit)}
                  </p>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Modal UNIFICADO (Crear/Editar) */}
      {isModalOpen && (
        <div className="fixed inset-0 bg-background/80 backdrop-blur-sm z-50 flex items-center justify-center p-4 animate-in fade-in duration-200">
          <div className="bg-surface border border-border/70 rounded-3xl p-6 w-full max-w-md shadow-2xl">
            <h2 className="text-xl font-bold mb-4 font-sans text-text">
              {editingBudget ? "Editar Presupuesto" : "Definir Presupuesto"}
            </h2>
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
                <button type="button" onClick={closeModal} className="flex-1 px-4 py-2.5 rounded-xl border border-border/70 text-text-muted hover:text-text hover:bg-surface-elevated transition-colors text-sm font-medium">Cancelar</button>
                <button type="submit" disabled={saveMutation.isPending} className="flex-1 px-4 py-2.5 rounded-xl bg-primary hover:bg-primary-dark text-background transition-colors text-sm font-medium flex justify-center items-center cursor-pointer">
                  {saveMutation.isPending ? <Loader2 size={16} className="animate-spin" /> : "Guardar"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}