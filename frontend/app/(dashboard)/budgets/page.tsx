'use client';

import { useRef, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, PieChart, Edit2, Trash2, CalendarDays, Repeat, AlertCircle } from 'lucide-react';
import { toast } from 'sonner';
import { api } from '@/lib/api';
import { formatCurrency, getApiError } from '@/lib/utils';
import { validateAmountText } from '@/lib/validateAmount';
import { queryKeys } from '@/lib/queryKeys';
import { useCategories } from '@/lib/hooks/useCategories';
import { useAccounts } from '@/lib/hooks/useAccounts';
import ModalShell from '@/components/ui/ModalShell';
import Button from '@/components/ui/Button';
import Skeleton from '@/components/ui/Skeleton';
import EmptyState from '@/components/ui/EmptyState';
import Input from '@/components/ui/Input';
import Select from '@/components/ui/Select';
import Label from '@/components/ui/Label';
import { useConfirmStore } from '@/store/useConfirmStore';
import type { Budget, BudgetPayload } from '@/types/api';

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
  // Fase 17 §17.2.4 (Decisión 17.2.4): moneda del presupuesto, derivada de las cuentas reales
  // del usuario (never una lista fija). Se setea al abrir el modal; default 'COP' mientras las
  // cuentas no cargaron.
  const [currency, setCurrency] = useState('COP');
  const [isRecurring, setIsRecurring] = useState(false);
  const getCurrentMonthYear = () => {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
  };
  const [monthYear, setMonthYear] = useState(getCurrentMonthYear);
  // Fase 12 §12.8: errores por campo (no globo nativo del navegador) + foco en el primero.
  const [fieldErrors, setFieldErrors] = useState<{
    categoryId?: string;
    amount?: string;
    monthYear?: string;
  }>({});
  const categoryRef = useRef<HTMLSelectElement>(null);
  const amountRef = useRef<HTMLInputElement>(null);
  const monthYearRef = useRef<HTMLInputElement>(null);

  const {
    data: budgets,
    isLoading: loadingBudgets,
    isError: budgetsError,
    refetch: refetchBudgets,
  } = useQuery<Budget[]>({
    queryKey: queryKeys.budgets.all(),
    queryFn: async () => (await api.get('budgets/')).data,
  });

  // QA-023: la carga inicial falló y no hay presupuestos en pantalla — la app no sabe si hay o
  // no, así que no puede mostrar el vacío de "No has definido ningún límite para este mes"
  // (mentiría). Mismo criterio que `initialLoadFailed` en `transactions/page.tsx` (Fase 31 F6):
  // el error solo reemplaza la lista cuando no llegó ningún dato; si hay presupuestos cacheados
  // y lo que falla es un refetch posterior, se sigue mostrando la lista.
  const budgetsFailedToLoad = budgetsError && !budgets;
  // El error le gana al skeleton (durante los reintentos automáticos de React Query `isLoading`
  // puede seguir en true, y el mensaje de error es más honesto que los placeholders girando);
  // también le gana al vacío: solo una respuesta exitosa con lista vacía autoriza el `EmptyState`.
  // Al reintentar a mano el error permanece en pantalla en vez de parpadear a skeleton.
  const loadingInitial = loadingBudgets && !budgetsFailedToLoad;

  const { data: categories } = useCategories();

  // Fase 17 §17.2.4: las monedas del selector salen de las cuentas reales del usuario
  // (misma queryKey que accounts/, ya cacheada por QueryProvider si otra página la cargó).
  const { data: accounts } = useAccounts();
  const availableCurrencies = Array.from(new Set(accounts?.map((a) => a.currency) ?? []));

  const expenseCategories = categories?.filter((c) => c.type === 'expense') || [];

  const saveMutation = useMutation({
    mutationFn: async (budgetData: BudgetPayload) => {
      if (editingBudget) {
        return (await api.put(`budgets/${editingBudget.id}`, budgetData)).data;
      } else {
        return (await api.post('budgets/', budgetData)).data;
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.budgets.all() });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.summary() });
      queryClient.invalidateQueries({ queryKey: queryKeys.budgets.progress() });
      // Fase 17 §17.2.4: progreso por cuenta (vista accounts/[id]) también depende de
      // presupuestos — el prefijo matchea todas las claves ['account-budgets-progress', id].
      queryClient.invalidateQueries({ queryKey: ['account-budgets-progress'] });
      toast.success('Presupuesto guardado');
      closeModal();
    },
    onError: (error: unknown) => {
      toast.error(getApiError(error));
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`budgets/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.budgets.all() });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.summary() });
      queryClient.invalidateQueries({ queryKey: queryKeys.budgets.progress() });
      queryClient.invalidateQueries({ queryKey: ['account-budgets-progress'] });
      toast.success('Presupuesto eliminado');
    },
    onError: (error: unknown) => {
      toast.error(getApiError(error));
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const [yearStr, monthStr] = monthYear.split('-');

    const errors: typeof fieldErrors = {};
    if (!categoryId) errors.categoryId = 'Elige una categoría.';
    // Fase 31 F2 (Q6, QA-013): mismo validador de montos que el resto de la app (decimales
    // y dígitos exactos, no solo `Number(amount) <= 0`).
    const amountError = validateAmountText(amount);
    if (amountError) errors.amount = amountError;
    // Required nativo neutralizado por noValidate: el mes/año se reimplementa igual que el resto.
    if (!monthYear) errors.monthYear = 'Elige un mes y año.';
    setFieldErrors(errors);

    if (errors.categoryId) return categoryRef.current?.focus();
    if (errors.amount) return amountRef.current?.focus();
    if (errors.monthYear) return monthYearRef.current?.focus();

    saveMutation.mutate({
      category_id: Number(categoryId),
      amount_limit: Number(amount),
      // Fase 17 §17.2.4: BudgetPayload.currency ya existía en types/api.ts; el formulario
      // ahora lo envía siempre (Decisión 17.2.4 — el backend no valida contra las cuentas).
      currency,
      month: Number(monthStr),
      year: Number(yearStr),
      is_recurring: isRecurring,
    });
  };

  const openCreateModal = () => {
    setEditingBudget(null);
    setCategoryId('');
    setAmount('');
    // Fase 17 §17.2.4: default a la primera moneda disponible entre las cuentas (COP si aún
    // no cargaron) — nunca una lista fija de monedas.
    setCurrency(availableCurrencies[0] ?? 'COP');
    setIsRecurring(false);
    setMonthYear(getCurrentMonthYear());
    setFieldErrors({});
    setIsModalOpen(true);
  };

  const openEditModal = (budget: Budget) => {
    setEditingBudget(budget);
    setCategoryId(budget.category_id.toString());
    setAmount(budget.amount_limit.toString());
    setCurrency(budget.currency);
    setIsRecurring(budget.is_recurring);
    const formattedMonth = budget.month < 10 ? `0${budget.month}` : budget.month;
    setMonthYear(`${budget.year}-${formattedMonth}`);
    setFieldErrors({});
    setIsModalOpen(true);
  };

  const closeModal = () => {
    setIsModalOpen(false);
    setEditingBudget(null);
  };

  // QA-023 (mismo criterio que Fase 31 F6 en /transactions): el encabezado y el botón "Nuevo
  // Presupuesto" quedan siempre visibles — solo el área de la grilla cambia entre skeleton,
  // error y lista, así el usuario nunca queda encerrado en un error ni sin salida.
  return (
    <div className="relative space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-text font-sans text-2xl font-bold">Tus Presupuestos</h1>
          <p className="text-text-muted text-sm">
            Establece límites y controla tus gastos mensuales.
          </p>
        </div>
        <Button variant="primary" onClick={openCreateModal} className="shrink-0">
          <Plus size={18} />
          <span className="hidden sm:inline">Nuevo Presupuesto</span>
          <span className="sm:hidden">Nuevo</span>
        </Button>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {loadingInitial ? (
          <>
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-32 rounded-2xl" />
            ))}
          </>
        ) : budgetsFailedToLoad ? (
          // QA-023: `GET /budgets/` puede devolver 500 — el backend no validaba `?month=&year=`
          // y dejaba filas basura que rompían la respuesta. Decimos lo que pasó en vez de
          // afirmar que no hay presupuestos. Mismo bloque que `TransactionList` (QA-010) y que
          // el progreso de presupuestos del dashboard: `EmptyState` + `AlertCircle` + "Reintentar".
          <div className="col-span-full">
            <EmptyState
              icon={<AlertCircle size={48} className="opacity-20" />}
              message="No se pudieron cargar tus presupuestos. Intenta de nuevo más tarde."
              action={
                <Button variant="secondary" size="sm" onClick={() => refetchBudgets()}>
                  Reintentar
                </Button>
              }
            />
          </div>
        ) : !budgets || budgets.length === 0 ? (
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
                        {budget.is_recurring && (
                          <span
                            title="Se repite cada mes"
                            className="text-primary inline-flex items-center"
                          >
                            <Repeat size={12} />
                          </span>
                        )}
                      </p>
                    </div>
                  </div>
                  <div className="flex gap-2 opacity-0 transition-opacity group-hover:opacity-100">
                    <button
                      onClick={() => openEditModal(budget)}
                      className="text-text-muted hover:text-primary p-1 transition-colors active:scale-95"
                      aria-label="Editar presupuesto"
                    >
                      <Edit2 size={16} />
                    </button>
                    <button
                      onClick={() =>
                        useConfirmStore.getState().confirm(
                          // QA-024: borrar una fila recurrente saltea ese mes (lápida): el
                          // siguiente se regenera desde la plantilla de un mes anterior, si la
                          // hay; si la serie nació este mes, el borrado la termina. El confirm decía solo "¿Eliminar este
                          // presupuesto?", que dejaba al usuario sin forma de saber qué pasa
                          // con "Repetir cada mes". Para no recurrente el borrado es el de
                          // siempre, así que el mensaje se arma según el flag.
                          budget.is_recurring
                            ? '¿Eliminar este presupuesto? Se borra el de este mes. Si venía de meses anteriores, el siguiente se vuelve a generar desde ahí.'
                            : '¿Eliminar este presupuesto?',
                          () => deleteMutation.mutate(budget.id)
                        )
                      }
                      className="text-text-muted hover:text-danger p-1 transition-colors active:scale-95"
                      aria-label="Eliminar presupuesto"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </div>
                <div className="border-border/40 mt-4 border-t pt-4">
                  <p className="text-text-muted mb-1 text-xs tracking-wider uppercase">
                    Límite mensual
                  </p>
                  <p className="text-text font-sans text-2xl font-semibold tabular-nums">
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
        <form onSubmit={handleSubmit} className="space-y-4" noValidate>
          <Select
            ref={categoryRef}
            label="Categoría a limitar"
            required
            value={categoryId}
            onChange={(e) => setCategoryId(e.target.value)}
            error={fieldErrors.categoryId}
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

          {/* Fase 17 §17.2.4 (Decisión 17.2.4): se muestra SIEMPRE, aunque solo haya una
              moneda — sin casos de UI oculta. Derivado de las cuentas reales del usuario. */}
          <Select
            label="Moneda"
            required
            value={currency}
            onChange={(e) => setCurrency(e.target.value)}
            className="bg-background appearance-none"
          >
            {availableCurrencies.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </Select>

          <Input
            ref={amountRef}
            label="Monto Máximo"
            type="number"
            required
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            error={fieldErrors.amount}
            className="bg-background"
            placeholder="0"
          />

          <Input
            ref={monthYearRef}
            label="Mes y Año"
            type="month"
            required
            value={monthYear}
            onChange={(e) => setMonthYear(e.target.value)}
            error={fieldErrors.monthYear}
            className="bg-background style-color-scheme-dark"
          />

          <div className="flex items-center gap-2">
            <input
              id="budget-recurring"
              type="checkbox"
              checked={isRecurring}
              onChange={(e) => setIsRecurring(e.target.checked)}
              className="accent-primary h-4 w-4 cursor-pointer"
            />
            <Label htmlFor="budget-recurring">Repetir cada mes</Label>
          </div>
          <p className="text-text-muted text-xs">
            Se creará automáticamente cada mes con el mismo monto. Si la desmarcas, no se generará
            en los meses siguientes (los anteriores no cambian).
          </p>

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
