'use client';

import { useState, useEffect, useMemo, useRef, Suspense } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Plus,
  ArrowRightLeft,
  ArrowDownRight,
  ArrowUpRight,
  Trash2,
  Pencil,
  FilterX,
  Circle,
} from 'lucide-react';
import { toast } from 'sonner';
import { api } from '@/lib/api';
import { formatCurrency, formatDate, getApiError } from '@/lib/utils';
import { useAppConfig } from '@/providers/AppConfigProvider';
import { useQueryParamState } from '@/hooks/useQueryParamState';
import { queryKeys } from '@/lib/queryKeys';
import EmptyState from '@/components/ui/EmptyState';
import { useConfirmStore } from '@/store/useConfirmStore';
import TransactionModal from '@/components/modals/TransactionModal';
import CategoryIcon from '@/components/ui/CategoryIcon';
import ModalShell from '@/components/ui/ModalShell';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import Select from '@/components/ui/Select';
import Skeleton from '@/components/ui/Skeleton';
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

// Fase 13 §13.6: whitelist read-time de los query params. Un link inválido
// (?category=abc, ?start=1-2-3) devolvía strings crudos que luego se casteaban a ciegas
// (Number(NaN)→422) o entraban directo al cast silencioso. Se valida a lectura y la URL
// no se reescribe con el valor corregido (el re-normalizado en cada render alcanza).
// 'custom' está en la whitelist de preset porque la propia página lo escribe cuando el
// usuario edita fechas a mano (setDatePreset('custom')) — sin él, el chip "Todo el
// histórico" se encendería por error con un rango custom activo.
const validatePreset = (raw: string) =>
  (['all', '7d', 'month', 'year', 'custom'] as const).includes(raw as DatePreset) ? raw : 'all';

const validateIdOrAll = (raw: string) => (raw === 'all' || /^\d+$/.test(raw) ? raw : 'all');

const validateDateParam = (raw: string) => (/^\d{4}-\d{2}-\d{2}$/.test(raw) ? raw : '');

function TransactionsPageContent() {
  const { config } = useAppConfig();
  const queryClient = useQueryClient();
  const [isModalOpen, setIsModalOpen] = useState(false);
  // Fase 12 §12.1: filtros sincronizados con la URL (start/end/category/account/preset).
  // El estado por defecto nunca aparece en el query string; un link copiado con filtros
  // activos reproduce la vista exacta en cualquier navegador/sesión. Fase 13 §13.6: cada
  // valor pasa por su validator a lectura (whitelist / formato), los seeds quedan normalizados.
  const [startDate, setStartDate] = useQueryParamState('start', '', validateDateParam);
  const [endDate, setEndDate] = useQueryParamState('end', '', validateDateParam);
  const [categoryFilter, setCategoryFilter] = useQueryParamState(
    'category',
    'all',
    validateIdOrAll
  );
  const [accountFilter, setAccountFilter] = useQueryParamState('account', 'all', validateIdOrAll);
  const [datePreset, setDatePreset] = useQueryParamState('preset', 'all', validatePreset);

  // Un link compartido puede traer solo `preset` explícito (ej. ?preset=month&category=3):
  // se derivan las fechas del preset una sola vez al montar, para que la vista reproducida
  // sea exactamente la misma que generó el link. Cuando la URL trae start/end, mandan ellos.
  useEffect(() => {
    if (
      !startDate &&
      !endDate &&
      (datePreset === '7d' || datePreset === 'month' || datePreset === 'year')
    ) {
      const nextDates = getPresetDates(datePreset);
      setStartDate(nextDates.startDate);
      setEndDate(nextDates.endDate);
    }
    // Seed de montaje: refleja intencionalmente el preset de la URL inicial, no los cambios
    // posteriores de filtros (que ya pasan por applyPreset/inputs y escriben start/end).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Edit modal state
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [editingTransaction, setEditingTransaction] = useState<Transaction | null>(null);
  const [editDescription, setEditDescription] = useState('');
  const [editAmount, setEditAmount] = useState('');
  const [editType, setEditType] = useState('expense');
  const [editDate, setEditDate] = useState(new Date().toISOString().split('T')[0]);
  const [editAccountId, setEditAccountId] = useState('');
  const [editCategoryId, setEditCategoryId] = useState('');
  // Fase 12 §12.8.3: errores por campo (no globo nativo del navegador) + foco en el primero.
  const [editErrors, setEditErrors] = useState<{
    amount?: string;
    description?: string;
    accountId?: string;
    categoryId?: string;
    date?: string;
  }>({});
  const editAmountRef = useRef<HTMLInputElement>(null);
  const editDescriptionRef = useRef<HTMLInputElement>(null);
  const editAccountRef = useRef<HTMLSelectElement>(null);
  const editCategoryRef = useRef<HTMLSelectElement>(null);
  const editDateRef = useRef<HTMLInputElement>(null);

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
    queryFn: async () => (await api.get('transactions/', { params })).data,
  });

  const { data: accounts } = useQuery<Account[]>({
    queryKey: queryKeys.accounts.all(),
    queryFn: async () => (await api.get('accounts/')).data,
  });

  const { data: categories } = useQuery<Category[]>({
    queryKey: queryKeys.categories.all(),
    queryFn: async () => (await api.get('categories/')).data,
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
      await api.delete(`transactions/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.transactions.all() });
      queryClient.invalidateQueries({ queryKey: queryKeys.accounts.all() });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.summary() });
      queryClient.invalidateQueries({ queryKey: queryKeys.budgets.progress() });
      queryClient.invalidateQueries({ queryKey: ['analytics-cashflow'] });
      queryClient.invalidateQueries({ queryKey: ['analytics-categories'] });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.categoryBreakdown() });
      queryClient.invalidateQueries({ queryKey: queryKeys.accounts.summary() });
      toast.success('Transacción eliminada');
    },
    onError: (error: unknown) => {
      toast.error(getApiError(error));
    },
  });

  const updateMutation = useMutation({
    mutationFn: async (payload: UpdateTransactionPayload) => {
      const response = await api.put(`transactions/${payload.id}`, payload);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.transactions.all() });
      queryClient.invalidateQueries({ queryKey: queryKeys.accounts.all() });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.summary() });
      queryClient.invalidateQueries({ queryKey: queryKeys.budgets.progress() });
      queryClient.invalidateQueries({ queryKey: ['analytics-cashflow'] });
      queryClient.invalidateQueries({ queryKey: ['analytics-categories'] });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.categoryBreakdown() });
      queryClient.invalidateQueries({ queryKey: queryKeys.accounts.summary() });
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
    setEditErrors({});
    setIsEditModalOpen(true);
  };

  const handleUpdate = (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingTransaction) return;

    const errors: typeof editErrors = {};
    const parsedAmount = Number(editAmount);
    if (!editAmount || Number.isNaN(parsedAmount) || parsedAmount <= 0) {
      errors.amount = 'Ingresa un monto mayor a cero.';
    }
    if (!editDescription.trim()) errors.description = 'Ingresa una descripción.';
    if (!editAccountId) errors.accountId = 'Elige una cuenta.';
    if (!editCategoryId) errors.categoryId = 'Elige una categoría.';
    if (!editDate) errors.date = 'Ingresa una fecha válida.';
    setEditErrors(errors);

    if (errors.amount) return editAmountRef.current?.focus();
    if (errors.description) return editDescriptionRef.current?.focus();
    if (errors.accountId) return editAccountRef.current?.focus();
    if (errors.categoryId) return editCategoryRef.current?.focus();
    if (errors.date) return editDateRef.current?.focus();

    updateMutation.mutate({
      id: editingTransaction.id,
      description: editDescription,
      amount: parsedAmount,
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
      <div className="space-y-6">
        <Skeleton className="h-10 w-64 rounded-xl" />
        <Skeleton className="h-40 rounded-2xl" />
        <Skeleton className="h-96 rounded-3xl" />
      </div>
    );
  }

  return (
    <div className="relative min-w-0 space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-text font-sans text-xl font-bold sm:text-2xl">Transacciones</h1>
          <p className="text-text-muted text-xs sm:text-sm">
            El registro histórico de tus movimientos.
          </p>
        </div>
        <Button variant="primary" onClick={() => setIsModalOpen(true)} className="shrink-0">
          <Plus size={18} />
          <span className="hidden sm:inline">Nuevo Movimiento</span>
          <span className="sm:hidden">Nuevo</span>
        </Button>
      </div>

      <div className="bg-surface border-border/70 shadow-background/20 min-w-0 space-y-4 overflow-x-hidden rounded-2xl border p-4 shadow-sm sm:p-5">
        <div className="flex items-center justify-between gap-3">
          <div className="text-text-soft flex items-center gap-2 text-sm font-medium">
            <FilterX size={16} className="text-text-muted" />
            Filtros de feed
          </div>
          <Button variant="ghost" size="sm" onClick={clearFilters}>
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

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-4">
            <Input
              label="Fecha inicial"
              type="date"
              value={startDate}
              onChange={(event) => {
                resetPagination();
                setStartDate(event.target.value);
                setDatePreset('custom');
              }}
              className="bg-background"
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
              className="bg-background"
            />

            <Select
              label="Cuenta"
              value={accountFilter}
              onChange={(event) => {
                resetPagination();
                setAccountFilter(event.target.value);
              }}
              className="bg-background"
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
              className="bg-background"
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

      <div className="bg-surface border-border/70 shadow-background/20 overflow-hidden rounded-3xl border shadow-sm">
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
                          className={`font-sans text-sm font-semibold tabular-nums sm:text-base ${isExpense ? 'text-text' : 'text-primary'}`}
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
                          className="text-text-muted hover:text-text hover:bg-surface-elevated rounded-lg p-2 transition-colors active:scale-95"
                          aria-label="Editar transacción"
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
                          className="text-text-muted hover:text-danger hover:bg-surface-elevated rounded-lg p-2 transition-colors active:scale-95"
                          aria-label="Eliminar transacción"
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
          <form onSubmit={handleUpdate} className="space-y-4" noValidate>
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

            <Input
              ref={editAmountRef}
              label="Valor"
              type="number"
              required
              value={editAmount}
              onChange={(e) => setEditAmount(e.target.value)}
              error={editErrors.amount}
              className="bg-background"
            />

            <Input
              ref={editDescriptionRef}
              label="Descripción"
              type="text"
              required
              value={editDescription}
              onChange={(e) => setEditDescription(e.target.value)}
              error={editErrors.description}
              className="bg-background"
            />

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Select
                ref={editAccountRef}
                label="Cuenta"
                required
                value={editAccountId}
                onChange={(e) => setEditAccountId(e.target.value)}
                error={editErrors.accountId}
                className="bg-background appearance-none"
              >
                <option value="" disabled>
                  Selecciona...
                </option>
                {accounts?.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                  </option>
                ))}
              </Select>
              <Select
                ref={editCategoryRef}
                label="Categoría"
                required
                value={editCategoryId}
                onChange={(e) => setEditCategoryId(e.target.value)}
                error={editErrors.categoryId}
                className="bg-background appearance-none"
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
              </Select>
            </div>

            <Input
              ref={editDateRef}
              label="Fecha"
              type="date"
              required
              value={editDate}
              onChange={(e) => setEditDate(e.target.value)}
              error={editErrors.date}
              className="bg-background"
            />

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

// Fase 12 §12.1: useSearchParams requiere Suspense (mismo patrón que login/reset-password).
export default function TransactionsPage() {
  return (
    <Suspense fallback={<Skeleton className="h-96 rounded-2xl" />}>
      <TransactionsPageContent />
    </Suspense>
  );
}
