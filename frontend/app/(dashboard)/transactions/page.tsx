'use client';

import { useState, useEffect, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Plus,
  ArrowRightLeft,
  ArrowDownRight,
  ArrowUpRight,
  Loader2,
  Trash2,
  Pencil,
  FilterX,
  Circle,
} from 'lucide-react';
import { toast } from 'sonner';
import { api } from '@/lib/api';
import { formatCurrency, formatDate, getApiError } from '@/lib/utils';
import { useAppConfig } from '@/providers/AppConfigProvider';
import { queryKeys } from '@/lib/queryKeys';
import EmptyState from '@/components/ui/EmptyState';
import { useConfirmStore } from '@/store/useConfirmStore';
import TransactionModal from '@/components/modals/TransactionModal';
import CategoryIcon from '@/components/ui/CategoryIcon';
import ModalShell from '@/components/ui/ModalShell';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import Select from '@/components/ui/Select';
import type {
  Account,
  Category,
  Transaction,
  UpdateTransactionPayload,
  PaginatedResponse,
} from '@/types/api';

type DatePreset = 'all' | '7d' | 'month' | 'year' | 'custom';

const PAGE_SIZE = 50;

const formatDateBoundaryForBackend = (value: string, boundary: 'start' | 'end') => {
  if (!value) {
    return null;
  }

  return boundary === 'start' ? `${value}T00:00:00` : `${value}T23:59:59`;
};

const getPresetDates = (preset: Exclude<DatePreset, 'custom'>) => {
  const today = new Date();
  const endDate = today.toISOString().slice(0, 10);

  if (preset === 'all') {
    return { startDate: '', endDate: '' };
  }

  if (preset === '7d') {
    const start = new Date(today);
    start.setDate(today.getDate() - 6);
    return { startDate: start.toISOString().slice(0, 10), endDate };
  }

  if (preset === 'month') {
    return {
      startDate: `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-01`,
      endDate,
    };
  }

  return {
    startDate: `${today.getFullYear()}-01-01`,
    endDate,
  };
};

export default function TransactionsPage() {
  const { config } = useAppConfig();
  const queryClient = useQueryClient();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('all');
  const [accountFilter, setAccountFilter] = useState('all');
  const [datePreset, setDatePreset] = useState<DatePreset>('all');

  // Edit modal state
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [editingTransaction, setEditingTransaction] = useState<Transaction | null>(null);
  const [editDescription, setEditDescription] = useState('');
  const [editAmount, setEditAmount] = useState('');
  const [editType, setEditType] = useState('expense');
  const [editDate, setEditDate] = useState(new Date().toISOString().split('T')[0]);
  const [editAccountId, setEditAccountId] = useState('');
  const [editCategoryId, setEditCategoryId] = useState('');

  // Paginación
  const [skip, setSkip] = useState(0);
  const [allItems, setAllItems] = useState<Transaction[]>([]);
  const [total, setTotal] = useState(0);

  const resetPagination = () => {
    setSkip(0);
    setAllItems([]);
    setTotal(0);
  };

  const startDateParam = formatDateBoundaryForBackend(startDate, 'start');
  const endDateParam = formatDateBoundaryForBackend(endDate, 'end');

  const params = useMemo(() => {
    const p: Record<string, string | number> = { skip, limit: PAGE_SIZE };

    if (startDateParam) p.start_date = startDateParam;
    if (endDateParam) p.end_date = endDateParam;
    if (categoryFilter !== 'all') p.category_id = Number(categoryFilter);
    if (accountFilter !== 'all') p.account_id = Number(accountFilter);

    return p;
  }, [skip, startDateParam, endDateParam, categoryFilter, accountFilter]);

  const { data, isFetching } = useQuery<PaginatedResponse<Transaction>>({
    queryKey: queryKeys.transactions.filtered(params),
    queryFn: async () => (await api.get('/api/transactions/', { params })).data,
  });

  const { data: accounts } = useQuery<Account[]>({
    queryKey: queryKeys.accounts.all(),
    queryFn: async () => (await api.get('/api/accounts/')).data,
  });

  const { data: categories } = useQuery<Category[]>({
    queryKey: queryKeys.categories.all(),
    queryFn: async () => (await api.get('/api/categories/')).data,
  });

  // Acumula páginas conforme llegan — sincroniza React Query con estado local
  /* eslint-disable react-hooks/set-state-in-effect, react-hooks/exhaustive-deps */
  useEffect(() => {
    if (!data) return;
    setTotal(data.total);
    setAllItems((prev) => (skip === 0 ? data.items : [...prev, ...data.items]));
  }, [data]);

  /* eslint-enable react-hooks/set-state-in-effect, react-hooks/exhaustive-deps */

  const hasMore = total > allItems.length;
  const loadingInitial = allItems.length === 0 && isFetching;
  const loadingMore = isFetching && allItems.length > 0;

  const applyPreset = (preset: Exclude<DatePreset, 'custom'>) => {
    const nextDates = getPresetDates(preset);
    resetPagination();
    setStartDate(nextDates.startDate);
    setEndDate(nextDates.endDate);
    setDatePreset(preset);
  };

  const clearFilters = () => {
    resetPagination();
    setStartDate('');
    setEndDate('');
    setCategoryFilter('all');
    setAccountFilter('all');
    setDatePreset('all');
  };

  const deleteMutation = useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/api/transactions/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.transactions.all() });
      queryClient.invalidateQueries({ queryKey: queryKeys.accounts.all() });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.summary() });
      queryClient.invalidateQueries({ queryKey: queryKeys.budgets.progress() });
      queryClient.invalidateQueries({ queryKey: ['analytics-cashflow'] });
      queryClient.invalidateQueries({ queryKey: ['analytics-categories'] });
      toast.success('Transacción eliminada');
    },
    onError: (error: unknown) => {
      toast.error(getApiError(error));
    },
  });

  const updateMutation = useMutation({
    mutationFn: async (payload: UpdateTransactionPayload) => {
      const response = await api.put(`/api/transactions/${payload.id}`, payload);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.transactions.all() });
      queryClient.invalidateQueries({ queryKey: queryKeys.accounts.all() });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.summary() });
      queryClient.invalidateQueries({ queryKey: queryKeys.budgets.progress() });
      queryClient.invalidateQueries({ queryKey: ['analytics-cashflow'] });
      queryClient.invalidateQueries({ queryKey: ['analytics-categories'] });
      toast.success('Transacción actualizada');
      setIsEditModalOpen(false);
      setEditingTransaction(null);
    },
    onError: (error: unknown) => {
      toast.error(getApiError(error));
    },
  });

  const openEditModal = (tx: Transaction) => {
    setEditingTransaction(tx);
    setEditDescription(tx.description || '');
    setEditAmount(String(tx.amount));
    setEditType(tx.type);
    setEditDate(tx.date ? tx.date.split('T')[0] : new Date().toISOString().split('T')[0]);
    setEditAccountId(String(tx.account_id));
    setEditCategoryId(String(tx.category_id));
    setIsEditModalOpen(true);
  };

  const handleUpdate = (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingTransaction) return;

    updateMutation.mutate({
      id: editingTransaction.id,
      description: editDescription,
      amount: Number(editAmount),
      type: editType as 'income' | 'expense',
      date: editDate,
      account_id: Number(editAccountId),
      category_id: Number(editCategoryId),
    });
  };

  const handleLoadMore = () => {
    setSkip((prev) => prev + PAGE_SIZE);
  };

  if (loadingInitial) {
    return (
      <div className="text-text-muted flex items-center gap-2 p-8">
        <Loader2 className="animate-spin" /> Cargando movimientos...
      </div>
    );
  }

  return (
    <div className="relative space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-text font-sans text-xl font-bold sm:text-2xl">Transacciones</h1>
          <p className="text-text-muted text-xs sm:text-sm">El registro histórico de tus movimientos.</p>
        </div>
        <Button
          variant="primary"
          onClick={() => setIsModalOpen(true)}
          className="shrink-0"
        >
          <Plus size={18} />
          <span className="hidden sm:inline">Nuevo Movimiento</span>
          <span className="sm:hidden">Nuevo</span>
        </Button>
      </div>

      <div className="bg-surface border-border/70 space-y-4 rounded-2xl border p-4 shadow-sm sm:p-5">
        <div className="flex items-center justify-between gap-3">
          <div className="text-text-soft flex items-center gap-2 text-sm font-medium">
            <FilterX size={16} className="text-text-muted" />
            Filtros de feed
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={clearFilters}
          >
            Limpiar filtros
          </Button>
        </div>

        <div className="space-y-4">
          <div className="flex flex-wrap gap-2">
            {(
              [
                { key: 'all', label: 'Todo el histórico' },
                { key: '7d', label: 'Últimos 7 días' },
                { key: 'month', label: 'Este mes' },
                { key: 'year', label: 'Este año' },
              ] as const
            ).map((preset) => (
              <button
                key={preset.key}
                type="button"
                onClick={() => applyPreset(preset.key)}
                className={`rounded-full border px-3 py-1.5 text-sm transition-colors ${
                  datePreset === preset.key
                    ? 'border-primary bg-primary/10 text-text'
                    : 'border-border/70 bg-background text-text-muted hover:border-primary/60 hover:text-text'
                }`}
              >
                {preset.label}
              </button>
            ))}
          </div>

          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Input
              label="Fecha inicial"
              type="date"
              value={startDate}
              onChange={(event) => {
                resetPagination();
                setStartDate(event.target.value);
                setDatePreset('custom');
              }}
              className="bg-background px-3 py-2"
            />

            <Input
              label="Fecha final"
              type="date"
              value={endDate}
              onChange={(event) => {
                resetPagination();
                setEndDate(event.target.value);
                setDatePreset('custom');
              }}
              className="bg-background px-3 py-2"
            />

            <Select
              label="Cuenta"
              value={accountFilter}
              onChange={(event) => {
                resetPagination();
                setAccountFilter(event.target.value);
              }}
              className="bg-background px-3 py-2"
            >
              <option value="all">Todas las cuentas</option>
              {accounts?.map((account) => (
                <option key={account.id} value={account.id}>
                  {account.name}
                </option>
              ))}
            </Select>

            <Select
              label="Categoría"
              value={categoryFilter}
              onChange={(event) => {
                resetPagination();
                setCategoryFilter(event.target.value);
              }}
              className="bg-background px-3 py-2"
            >
              <option value="all">Todas las categorías</option>
              {categories?.map((category) => (
                <option key={category.id} value={category.id}>
                  {category.name}
                </option>
              ))}
            </Select>
          </div>
        </div>
      </div>

      <div className="bg-surface border-border/70 overflow-hidden rounded-3xl border shadow-sm">
        {allItems.length === 0 ? (
          <EmptyState
            icon={<ArrowRightLeft size={48} className="opacity-20" />}
            message="Aún no tienes movimientos registrados."
          />
        ) : (
          <>
            <div className="divide-border/40 divide-y">
              {allItems.map((tx) => {
                const isExpense = tx.type === 'expense';
                const account = accounts?.find((a) => a.id === tx.account_id);
                const category = categories?.find((c) => c.id === tx.category_id);

                return (
                  <div
                    key={tx.id}
                    className="hover:bg-surface-elevated group flex items-center justify-between gap-3 p-3 transition-colors sm:gap-4 sm:p-4 sm:px-6"
                  >
                    <div className="flex min-w-0 items-center space-x-3 sm:space-x-4">
                      <div
                        className={`bg-background border-border/60 hidden shrink-0 rounded-full border p-2.5 sm:block ${isExpense ? 'text-text-muted' : 'text-primary'}`}
                      >
                        {isExpense ? <ArrowDownRight size={18} /> : <ArrowUpRight size={18} />}
                      </div>
                      <div className="min-w-0">
                        <p className="text-text truncate text-sm font-medium">{tx.description}</p>
                        <div className="text-text-muted mt-0.5 flex space-x-2 text-xs">
                          <span className="truncate">{account?.name || 'Cuenta eliminada'}</span>
                          <span className="hidden sm:inline">•</span>
                          <span className="hidden items-center gap-1 sm:inline-flex">
                            <CategoryIcon
                              icon={category?.icon}
                              size={12}
                              fallback={<Circle size={12} className="opacity-30" />}
                            />
                            {category?.name || 'Sin categoría'}
                          </span>
                        </div>
                      </div>
                    </div>

                    <div className="flex shrink-0 items-center gap-2 sm:gap-6">
                      <div className="text-right">
                        <p
                          className={`font-sans text-sm font-semibold sm:text-base ${isExpense ? 'text-text' : 'text-primary'}`}
                        >
                          {isExpense ? '-' : '+'}
                          {formatCurrency(tx.amount, tx.currency)}
                        </p>
                        <p className="text-text-muted text-[11px] capitalize">
                          {formatDate(tx.date, config.locale)}
                        </p>
                      </div>
                      <div className="flex items-center gap-1 opacity-100 sm:opacity-0 sm:transition-opacity sm:group-hover:opacity-100">
                        <button
                          onClick={() => openEditModal(tx)}
                          className="text-text-muted hover:text-text hover:bg-surface-elevated rounded-lg p-2 transition-colors"
                        >
                          <Pencil size={16} />
                        </button>
                        <button
                          onClick={() =>
                            useConfirmStore
                              .getState()
                              .confirm('¿Borrar esta transacción?', () =>
                                deleteMutation.mutate(tx.id)
                              )
                          }
                          className="text-text-muted hover:text-danger hover:bg-surface-elevated rounded-lg p-2 transition-colors"
                        >
                          <Trash2 size={16} />
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            {hasMore && (
              <div className="border-border/40 flex justify-center border-t py-6">
                <Button
                  variant="secondary"
                  onClick={handleLoadMore}
                  disabled={loadingMore}
                  loading={loadingMore}
                >
                  {loadingMore ? 'Cargando...' : `Cargar más (${allItems.length} de ${total})`}
                </Button>
              </div>
            )}

            {!hasMore && allItems.length > 0 && (
              <p className="text-text-muted border-border/40 border-t py-4 text-center text-sm">
                Mostrando todas las {total} transacciones
              </p>
            )}
          </>
        )}
      </div>

      <TransactionModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSuccess={() => queryClient.invalidateQueries({ queryKey: queryKeys.transactions.all() })}
        title="Registrar movimiento"
        defaultType="expense"
      />

      <ModalShell
        isOpen={isEditModalOpen && !!editingTransaction}
        onClose={() => setIsEditModalOpen(false)}
        title="Editar movimiento"
      >
        {editingTransaction && (
          <form onSubmit={handleUpdate} className="space-y-4">
            <div className="flex gap-4">
              <button
                type="button"
                onClick={() => setEditType('expense')}
                className={`flex-1 cursor-pointer rounded-xl border py-2 text-sm font-medium transition-colors ${editType === 'expense' ? 'bg-background border-border text-text' : 'text-text-muted hover:text-text border-transparent'}`}
              >
                Gasto
              </button>
              <button
                type="button"
                onClick={() => setEditType('income')}
                className={`flex-1 cursor-pointer rounded-xl border py-2 text-sm font-medium transition-colors ${editType === 'income' ? 'bg-primary/10 border-primary/20 text-primary' : 'text-text-muted hover:text-text border-transparent'}`}
              >
                Ingreso
              </button>
            </div>

            <div className="space-y-1.5">
              <label className="text-text-muted pl-1 text-xs font-medium tracking-wider uppercase">
                Valor
              </label>
              <input
                type="number"
                required
                value={editAmount}
                onChange={(e) => setEditAmount(e.target.value)}
                className="bg-background border-border/70 text-text focus:ring-primary/50 focus:border-primary w-full rounded-xl border px-4 py-2.5 text-sm transition-all focus:ring-2 focus:outline-none"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-text-muted pl-1 text-xs font-medium tracking-wider uppercase">
                Descripción
              </label>
              <input
                required
                value={editDescription}
                onChange={(e) => setEditDescription(e.target.value)}
                className="bg-background border-border/70 text-text focus:ring-primary/50 focus:border-primary w-full rounded-xl border px-4 py-2.5 text-sm transition-all focus:ring-2 focus:outline-none"
              />
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <label className="text-text-muted pl-1 text-xs font-medium tracking-wider uppercase">
                  Cuenta
                </label>
                <select
                  required
                  value={editAccountId}
                  onChange={(e) => setEditAccountId(e.target.value)}
                  className="bg-background border-border/70 text-text focus:ring-primary/50 w-full appearance-none rounded-xl border px-4 py-2.5 text-sm transition-all focus:ring-2 focus:outline-none"
                >
                  <option value="" disabled>
                    Selecciona...
                  </option>
                  {accounts?.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-1.5">
                <label className="text-text-muted pl-1 text-xs font-medium tracking-wider uppercase">
                  Categoría
                </label>
                <select
                  required
                  value={editCategoryId}
                  onChange={(e) => setEditCategoryId(e.target.value)}
                  className="bg-background border-border/70 text-text focus:ring-primary/50 w-full appearance-none rounded-xl border px-4 py-2.5 text-sm transition-all focus:ring-2 focus:outline-none"
                >
                  <option value="" disabled>
                    Selecciona...
                  </option>
                  {categories
                    ?.filter((c) => c.type === editType)
                    .map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                </select>
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="text-text-muted pl-1 text-xs font-medium tracking-wider uppercase">
                Fecha
              </label>
              <input
                type="date"
                required
                value={editDate}
                onChange={(e) => setEditDate(e.target.value)}
                className="bg-background border-border/70 text-text focus:ring-primary/50 focus:border-primary w-full rounded-xl border px-4 py-2.5 text-sm transition-all focus:ring-2 focus:outline-none"
              />
            </div>

            <div className="mt-6 flex gap-3">
              <Button
                type="button"
                variant="ghost"
                onClick={() => setIsEditModalOpen(false)}
                className="flex-1"
              >
                Cancelar
              </Button>
              <Button
                type="submit"
                variant="primary"
                loading={updateMutation.isPending}
                className="flex-1"
              >
                Guardar
              </Button>
            </div>
          </form>
        )}
      </ModalShell>
    </div>
  );
}
