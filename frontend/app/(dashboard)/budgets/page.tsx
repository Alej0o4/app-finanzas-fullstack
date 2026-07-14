'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, PieChart, Loader2, Edit2, Trash2, CalendarDays } from 'lucide-react';
import { toast } from 'sonner';
import { api } from '@/lib/api';
import { formatCurrency, getApiError } from '@/lib/utils';
import { queryKeys } from '@/lib/queryKeys';
import ModalShell from '@/components/ui/ModalShell';
import Button from '@/components/ui/Button';
import EmptyState from '@/components/ui/EmptyState';
import Input from '@/components/ui/Input';
import Select from '@/components/ui/Select';
import { useConfirmStore } from '@/store/useConfirmStore';
import type { Category, Budget, BudgetPayload } from '@/types/api';

const getMonthName = (month: number, year: number) => {
  const date = new Date(year, month - 1);
  return new Intl.DateTimeFormat('es-CO', { month: 'long', year: 'numeric' }).format(date);
};

export default function BudgetsPage() {
  const queryClient = useQueryClient();

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingBudget, setEditingBudget] = useState<Budget | null>(null);

  const [categoryId, setCategoryId] = useState('');
  const [amount, setAmount] = useState('');
  const getCurrentMonthYear = () => {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
  };
  const [monthYear, setMonthYear] = useState(getCurrentMonthYear);

  const { data: budgets, isLoading: loadingBudgets } = useQuery<Budget[]>({
    queryKey: queryKeys.budgets.all(),
    queryFn: async () => (await api.get('/api/budgets/')).data,
  });

  const { data: categories } = useQuery<Category[]>({
    queryKey: queryKeys.categories.all(),
    queryFn: async () => (await api.get('/api/categories/')).data,
  });

  const expenseCategories = categories?.filter((c) => c.type === 'expense') || [];

  const saveMutation = useMutation({
    mutationFn: async (budgetData: BudgetPayload) => {
      if (editingBudget) {
        return (await api.put(`/api/budgets/${editingBudget.id}`, budgetData)).data;
      } else {
        return (await api.post('/api/budgets/', budgetData)).data;
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.budgets.all() });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.summary() });
      queryClient.invalidateQueries({ queryKey: queryKeys.budgets.progress() });
      toast.success('Presupuesto guardado');
      closeModal();
    },
    onError: (error: unknown) => {
      toast.error(getApiError(error));
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/api/budgets/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.budgets.all() });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.summary() });
      queryClient.invalidateQueries({ queryKey: queryKeys.budgets.progress() });
      toast.success('Presupuesto eliminado');
    },
    onError: (error: unknown) => {
      toast.error(getApiError(error));
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const [yearStr, monthStr] = monthYear.split('-');

    saveMutation.mutate({
      category_id: Number(categoryId),
      amount_limit: Number(amount),
      month: Number(monthStr),
      year: Number(yearStr),
    });
  };

  const openCreateModal = () => {
    setEditingBudget(null);
    setCategoryId('');
    setAmount('');
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

  if (loadingBudgets)
    return (
      <div className="text-text-muted flex items-center gap-2 p-8">
        <Loader2 className="animate-spin" /> Cargando presupuestos...
      </div>
    );

  return (
    <div className="relative space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-text font-sans text-2xl font-bold">Tus Presupuestos</h1>
          <p className="text-text-muted text-sm">
            Establece límites y controla tus gastos mensuales.
          </p>
        </div>
        <Button
          variant="primary"
          onClick={openCreateModal}
        >
          <Plus size={18} />
          <span>Nuevo Presupuesto</span>
        </Button>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {!budgets || budgets.length === 0 ? (
          <div className="col-span-full">
            <EmptyState
              icon={<PieChart size={48} className="opacity-20" />}
              message="No has definido ningún límite para este mes."
            />
          </div>
        ) : (
          budgets.map((budget) => {
            const category = categories?.find((c) => c.id === budget.category_id);
            return (
              <div
                key={budget.id}
                className="bg-surface border-border/70 hover:border-primary/30 group rounded-2xl border p-5 transition-colors"
              >
                <div className="mb-4 flex items-start justify-between">
                  <div className="flex items-center space-x-3">
                    <div className="bg-background text-primary rounded-lg p-2">
                      <PieChart size={20} />
                    </div>
                    <div>
                      <h3 className="text-text font-medium">
                        {category?.name || 'Categoría eliminada'}
                      </h3>
                      <p className="text-text-muted mt-0.5 flex items-center gap-1 text-xs capitalize">
                        <CalendarDays size={12} />
                        {getMonthName(budget.month, budget.year)}
                      </p>
                    </div>
                  </div>
                  <div className="flex gap-2 opacity-0 transition-opacity group-hover:opacity-100">
                    <button
                      onClick={() => openEditModal(budget)}
                      className="text-text-muted hover:text-primary p-1 transition-colors"
                    >
                      <Edit2 size={16} />
                    </button>
                    <button
                      onClick={() =>
                        useConfirmStore
                          .getState()
                          .confirm('¿Eliminar este presupuesto?', () =>
                            deleteMutation.mutate(budget.id)
                          )
                      }
                      className="text-text-muted hover:text-danger p-1 transition-colors"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </div>
                <div className="border-border/40 mt-4 border-t pt-4">
                  <p className="text-text-muted mb-1 text-xs tracking-wider uppercase">
                    Límite mensual
                  </p>
                  <p className="text-text font-sans text-2xl font-semibold">
                    {formatCurrency(budget.amount_limit, budget.currency)}
                  </p>
                </div>
              </div>
            );
          })
        )}
      </div>

      <ModalShell
        isOpen={isModalOpen}
        onClose={closeModal}
        title={editingBudget ? 'Editar Presupuesto' : 'Definir Presupuesto'}
      >
        <form onSubmit={handleSubmit} className="space-y-4">
          <Select
            label="Categoría a limitar"
            required
            value={categoryId}
            onChange={(e) => setCategoryId(e.target.value)}
            className="bg-background appearance-none"
          >
            <option value="" disabled>
              Selecciona un gasto...
            </option>
            {expenseCategories.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </Select>

          <Input
            label="Monto Máximo"
            type="number"
            required
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            className="bg-background"
            placeholder="0"
          />

          <Input
            label="Mes y Año"
            type="month"
            required
            value={monthYear}
            onChange={(e) => setMonthYear(e.target.value)}
            className="bg-background style-color-scheme-dark"
          />

          <div className="mt-6 flex gap-3">
            <Button type="button" variant="ghost" onClick={closeModal} className="flex-1">
              Cancelar
            </Button>
            <Button
              type="submit"
              variant="primary"
              loading={saveMutation.isPending}
              className="flex-1"
            >
              Guardar
            </Button>
          </div>
        </form>
      </ModalShell>
    </div>
  );
}
