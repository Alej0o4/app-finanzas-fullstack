'use client';

import { useState, useEffect, useMemo, Suspense } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { api } from '@/lib/api';
import { getApiError } from '@/lib/utils';
import { useQueryParamState, useQueryParamsBatch } from '@/hooks/useQueryParamState';
import { queryKeys } from '@/lib/queryKeys';
import { useTransactions } from '@/lib/hooks/useTransactions';
import { useAccounts } from '@/lib/hooks/useAccounts';
import { useCategories } from '@/lib/hooks/useCategories';
import TransactionFilters, { type DatePreset } from '@/components/transactions/TransactionFilters';
import TransactionList from '@/components/transactions/TransactionList';
import EditTransactionModal from '@/components/modals/EditTransactionModal';
import Skeleton from '@/components/ui/Skeleton';
import type { Transaction, UpdateTransactionPayload } from '@/types/api';

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
const validatePreset = (raw: string): DatePreset =>
  (['all', '7d', 'month', 'year', 'custom'] as const).includes(raw as DatePreset)
    ? (raw as DatePreset)
    : 'all';

const validateIdOrAll = (raw: string) => (raw === 'all' || /^\d+$/.test(raw) ? raw : 'all');

const validateDateParam = (raw: string) => (/^\d{4}-\d{2}-\d{2}$/.test(raw) ? raw : '');

function TransactionsPageContent() {
  const queryClient = useQueryClient();
  // Fase 12 §12.1: filtros sincronizados con la URL (start/end/category/account/preset).
  // El estado por defecto nunca aparece en el query string; un link copiado con filtros
  // activos reproduce la vista exacta en cualquier navegador/sesión. Fase 13 §13.6: cada
  // valor pasa por su validator a lectura (whitelist / formato), los seeds quedan normalizados.
  const [startDate] = useQueryParamState('start', '', validateDateParam);
  const [endDate] = useQueryParamState('end', '', validateDateParam);
  const [categoryFilter, setCategoryFilter] = useQueryParamState(
    'category',
    'all',
    validateIdOrAll
  );
  const [accountFilter, setAccountFilter] = useQueryParamState('account', 'all', validateIdOrAll);
  const [datePreset] = useQueryParamState('preset', 'all', validatePreset);
  const setFilterParams = useQueryParamsBatch();

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
      setFilterParams({ start: nextDates.startDate || null, end: nextDates.endDate || null });
    }
    // Seed de montaje: refleja intencionalmente el preset de la URL inicial, no los cambios
    // posteriores de filtros (que ya pasan por applyPreset/inputs y escriben start/end).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Edit modal state
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [editingTransaction, setEditingTransaction] = useState<Transaction | null>(null);
  // Cada apertura del modal incrementa esta key para forzar un remount de
  // EditTransactionModal: garantiza que el formulario siempre arranque desde los valores
  // actuales de la transacción, incluso si se reabre la misma fila tras cancelar una edición
  // sin guardar (mismo comportamiento que el openEditModal original, que reseteaba todos los
  // campos explícitamente en cada click).
  const [editSessionKey, setEditSessionKey] = useState(0);

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

  const { data, isFetching } = useTransactions(params);

  const { data: accounts } = useAccounts();

  const { data: categories } = useCategories();

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
    setFilterParams({
      start: nextDates.startDate || null,
      end: nextDates.endDate || null,
      preset: preset === 'all' ? null : preset,
    });
  };

  const clearFilters = () => {
    resetPagination();
    setFilterParams({ start: null, end: null, category: null, account: null, preset: null });
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
    setEditSessionKey((prev) => prev + 1);
    setIsEditModalOpen(true);
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
      </div>

      <TransactionFilters
        datePreset={datePreset}
        startDate={startDate}
        endDate={endDate}
        accountFilter={accountFilter}
        categoryFilter={categoryFilter}
        accounts={accounts}
        categories={categories}
        onApplyPreset={applyPreset}
        onStartDateChange={(value) => {
          resetPagination();
          setFilterParams({ start: value || null, preset: 'custom' });
        }}
        onEndDateChange={(value) => {
          resetPagination();
          setFilterParams({ end: value || null, preset: 'custom' });
        }}
        onAccountFilterChange={(value) => {
          resetPagination();
          setAccountFilter(value);
        }}
        onCategoryFilterChange={(value) => {
          resetPagination();
          setCategoryFilter(value);
        }}
        onClearFilters={clearFilters}
      />

      <TransactionList
        items={allItems}
        accounts={accounts}
        categories={categories}
        total={total}
        hasMore={hasMore}
        loadingMore={loadingMore}
        onEdit={openEditModal}
        onDelete={(id) => deleteMutation.mutate(id)}
        onLoadMore={handleLoadMore}
      />

      {editingTransaction && (
        <EditTransactionModal
          key={editSessionKey}
          isOpen={isEditModalOpen}
          transaction={editingTransaction}
          accounts={accounts}
          categories={categories}
          isSaving={updateMutation.isPending}
          onClose={() => setIsEditModalOpen(false)}
          onSave={(payload) => updateMutation.mutate(payload)}
        />
      )}
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
