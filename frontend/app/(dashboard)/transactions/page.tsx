'use client';

import { useState, useEffect, useMemo, useRef, Suspense } from 'react';
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
import { currentCalendarPeriodRange } from '@/lib/dateRanges';

const PAGE_SIZE = 50;

const formatDateBoundaryForBackend = (value: string, boundary: 'start' | 'end') => {
  if (!value) {
    return null;
  }

  return boundary === 'start' ? `${value}T00:00:00` : `${value}T23:59:59`;
};

const getPresetDates = (preset: Exclude<DatePreset, 'custom'>) => {
  if (preset === 'all') {
    return { startDate: '', endDate: '' };
  }

  // Usa currentCalendarPeriodRange (F1) para week/month/year — misma lógica que Analítica
  // y el dashboard. El fin es "hoy" (endOfUtcDay), no el domingo ni fin de mes calendario.
  const now = new Date();
  const range = currentCalendarPeriodRange(preset, now);
  return { startDate: range.start_date, endDate: range.end_date };
};

// Fase 13 §13.6: whitelist read-time de los query params. Un link inválido
// (?category=abc, ?start=1-2-3) devolvía strings crudos que luego se casteaban a ciegas
// (Number(NaN)→422) o entraban directo al cast silencioso. Se valida a lectura y la URL
// no se reescribe con el valor corregido (el re-normalizado en cada render alcanza).
// 'custom' está en la whitelist de preset porque la propia página lo escribe cuando el
// usuario edita fechas a mano (setDatePreset('custom')) — sin él, el chip "Todo el
// histórico" se encendería por error con un rango custom activo.
// '7d' ya no está en la whitelist: un link viejo con ?preset=7d cae a 'all' (Q2), o a
// 'custom' si trae start/end (ver datePreset en el componente).
const validatePreset = (raw: string): DatePreset =>
  (['all', 'week', 'month', 'year', 'custom'] as const).includes(raw as DatePreset)
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
  const [rawDatePreset] = useQueryParamState('preset', 'all', validatePreset);
  // Un link viejo (?preset=7d&start=…&end=…) normaliza el preset a 'all' pero conserva las
  // fechas: con un rango activo el chip correcto es 'custom', no "Todo el histórico".
  const datePreset: DatePreset =
    rawDatePreset === 'all' && (startDate || endDate) ? 'custom' : rawDatePreset;
  const setFilterParams = useQueryParamsBatch();

  // Un link compartido puede traer solo `preset` explícito (ej. ?preset=month&category=3):
  // se derivan las fechas del preset una sola vez al montar, para que la vista reproducida
  // sea exactamente la misma que generó el link. Cuando la URL trae start/end, mandan ellos.
  useEffect(() => {
    if (
      !startDate &&
      !endDate &&
      (datePreset === 'week' || datePreset === 'month' || datePreset === 'year')
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

  // Fase 31 F6 (Q7, QA-010): rango invertido — comparación lexicográfica alcanza porque
  // las dos fechas son 'YYYY-MM-DD'. Con el rango invertido la consulta no se ejecuta
  // (`enabled: false` abajo) y no se ofrece ningún resultado de una consulta anterior.
  const dateRangeInverted = Boolean(startDate && endDate && startDate > endDate);

  const params = useMemo(() => {
    const p: Record<string, string | number> = { skip, limit: PAGE_SIZE };

    if (startDateParam) p.start_date = startDateParam;
    if (endDateParam) p.end_date = endDateParam;
    if (categoryFilter !== 'all') p.category_id = Number(categoryFilter);
    if (accountFilter !== 'all') p.account_id = Number(accountFilter);

    return p;
  }, [skip, startDateParam, endDateParam, categoryFilter, accountFilter]);

  const { data, isFetching, isError, error, refetch } = useTransactions(params, {
    enabled: !dateRangeInverted,
  });

  const { data: accounts } = useAccounts();

  const { data: categories } = useCategories();

  // Acumula páginas conforme llegan — sincroniza React Query con estado local
  /* eslint-disable react-hooks/set-state-in-effect, react-hooks/exhaustive-deps */
  useEffect(() => {
    if (!data) return;
    setTotal(data.total);
    // Sin repetir ids: la misma página puede llegar dos veces (reintento automático de
    // React Query + "Cargar más" reintentando esa página tras un error, QA Fase 31).
    setAllItems((prev) => {
      if (skip === 0) return data.items;
      const cargados = new Set(prev.map((t) => t.id));
      return [...prev, ...data.items.filter((t) => !cargados.has(t.id))];
    });
  }, [data]);

  // Fase 31 F6: un rango invertido limpia lo que hubiera cargado antes (como
  // resetPagination) — el área de la lista no debe mostrar ítems de un filtro previo ni
  // el mensaje de "Aún no tienes movimientos", solo el error de campo bajo "Fecha final".
  useEffect(() => {
    if (dateRangeInverted) {
      setSkip(0);
      setAllItems([]);
      setTotal(0);
    }
  }, [dateRangeInverted]);

  // Fase 31 F6 (QA-010): un error al pedir otra página ("Cargar más") no debe borrar lo
  // ya cargado ni tapar los filtros — se avisa con un toast y el botón vuelve a quedar
  // disponible para reintentar. Se dedupe con un ref para no repetir el toast mientras
  // React Query siga reportando el mismo error entre renders.
  const lastLoadMoreErrorRef = useRef<unknown>(null);
  useEffect(() => {
    if (isError && skip > 0 && error !== lastLoadMoreErrorRef.current) {
      lastLoadMoreErrorRef.current = error;
      toast.error(getApiError(error));
    }
    if (!isError) {
      lastLoadMoreErrorRef.current = null;
    }
  }, [isError, error, skip]);

  /* eslint-enable react-hooks/set-state-in-effect, react-hooks/exhaustive-deps */

  const hasMore = total > allItems.length;
  const loadingInitial = allItems.length === 0 && isFetching && !dateRangeInverted;
  const loadingMore = isFetching && allItems.length > 0;
  const initialLoadFailed = isError && allItems.length === 0 && !dateRangeInverted;

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
    // Si falló la página pedida, reintentar esa misma en vez de avanzar `skip`: avanzar
    // saltaría una página entera de movimientos (review de Fase 31, F6).
    if (isError) {
      refetch();
      return;
    }
    setSkip((prev) => prev + PAGE_SIZE);
  };

  // Fase 31 F6 (Q7, QA-010): los filtros se renderizan siempre — solo el área de la lista
  // cambia entre skeleton, error con "Reintentar" y la lista, para que los filtros sigan
  // visibles y usables mientras la app reintenta o mientras el rango está invertido.
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
        endDateError={dateRangeInverted ? 'La fecha final es anterior a la inicial' : undefined}
      />

      {dateRangeInverted ? null : loadingInitial ? (
        <Skeleton className="h-96 rounded-3xl" />
      ) : (
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
          isError={initialLoadFailed}
          onRetry={() => refetch()}
        />
      )}

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
