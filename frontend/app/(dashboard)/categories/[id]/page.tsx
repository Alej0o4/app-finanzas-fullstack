'use client';

import { useParams, useRouter } from 'next/navigation';
import {
  keepPreviousData,
  useQuery,
  useQueries,
  useMutation,
  useQueryClient,
} from '@tanstack/react-query';
import { ArrowLeft, Tag, ArrowDownRight, ArrowUpRight, Pencil, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import Link from 'next/link';
import { api } from '@/lib/api';
import { formatCurrency, formatDateLabel, getApiError } from '@/lib/utils';
import { dayInZone, todayInZone } from '@/lib/dates';
import { useTimezone } from '@/lib/hooks/useTimezone';
import { useAppConfig } from '@/providers/AppConfigProvider';
import { useConfirmStore } from '@/store/useConfirmStore';
import { queryKeys } from '@/lib/queryKeys';
import { fundSpendNotice } from '@/lib/fundSpendNotice';
import QueryErrorState from '@/components/ui/QueryErrorState';
import { useAccounts } from '@/lib/hooks/useAccounts';
import { useCategories } from '@/lib/hooks/useCategories';
import ModalShell from '@/components/ui/ModalShell';
import Skeleton from '@/components/ui/Skeleton';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import Select from '@/components/ui/Select';
import { useState } from 'react';
import CategoryIcon from '@/components/ui/CategoryIcon';
import BudgetRing from '@/components/charts/BudgetRing';
import MonthNavigator from '@/components/MonthNavigator';
import SegmentedControl from '@/components/ui/SegmentedControl';
import { useMonthParam } from '@/hooks/useMonthParam';
import { useQueryParamState } from '@/hooks/useQueryParamState';
import { useCurrentUser } from '@/lib/hooks/useCurrentUser';
import { monthTransactionsHref } from '@/lib/dateRanges';
import type {
  BudgetProgress,
  Category,
  CategoryDistributionItem,
  DashboardSummary,
  Transaction,
  UpdateTransactionPayload,
  PaginatedResponse,
} from '@/types/api';

const PAGE_SIZE = 20;

// Fase 40 (D3): `?currency=` es un código ISO de 3 letras; cualquier otra cosa se ignora y cae
// al default (la moneda del presupuesto o la preferida). La URL no se reescribe.
const validateCurrencyParam = (raw: string) => (/^[A-Za-z]{3}$/.test(raw) ? raw.toUpperCase() : '');

export default function CategoryDetailPage() {
  const { config } = useAppConfig();
  const { id } = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { displayTimezone } = useTimezone();

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [selectedTransaction, setSelectedTransaction] = useState<Transaction | null>(null);
  const [description, setDescription] = useState('');
  const [amount, setAmount] = useState('');
  const [type, setType] = useState('expense');
  const [transactionDate, setTransactionDate] = useState('');
  const [accountId, setAccountId] = useState('');
  const [categoryId, setCategoryId] = useState(String(id));

  const {
    data: category,
    isLoading: loadingCategory,
    isError: categoryError,
    refetch: refetchCategory,
  } = useQuery<Category>({
    queryKey: queryKeys.categories.byId(id as string),
    queryFn: async () => (await api.get(`categories/${id}`)).data,
  });

  // Fase 40 (D2/D10): mes por URL, compartido con el dashboard. El piso del selector sale de
  // `summary.first_transaction_month` (D18) — misma query y key que el dashboard.
  const monthState = useMonthParam();
  const { apiMonth, periodParams, monthRange, isCurrentMonth, monthNameLower, year, month, ready } =
    monthState;
  const { data: user } = useCurrentUser();
  const preferredCurrency = user?.preferred_currency ?? config.currency;

  const { data: summary } = useQuery<DashboardSummary>({
    queryKey: queryKeys.dashboard.summary(apiMonth),
    enabled: ready,
    queryFn: async () => (await api.get('dashboard/summary', { params: periodParams })).data,
    placeholderData: keepPreviousData,
  });

  const { data: accounts } = useAccounts();

  const isExpense = category?.type !== 'income';
  const categoryType = category?.type ?? 'expense';

  // Presupuestos del mes (D9): se busca el de esta categoría por `category_id` y moneda. Es la
  // misma query que el dashboard (`budgets.progress(apiMonth)`), sin `currency`.
  const {
    data: budgetsProgress,
    isLoading: loadingBudgetsInitial,
    isPlaceholderData: budgetsStale,
    isError: budgetsError,
    refetch: refetchBudgets,
  } = useQuery<BudgetProgress[]>({
    queryKey: queryKeys.budgets.progress(apiMonth),
    enabled: ready && isExpense,
    queryFn: async () =>
      (await api.get('dashboard/budgets-progress', { params: periodParams })).data,
    placeholderData: keepPreviousData,
  });
  // Con `keepPreviousData` los datos del mes anterior se tratan como "cargando".
  const loadingBudgets = loadingBudgetsInitial || budgetsStale;
  const categoryBudgets = (budgetsProgress ?? []).filter((b) => b.category_id === Number(id));
  const budgetCurrencies = categoryBudgets.map((b) => b.currency);

  // Monedas conocidas (D17): las de las cuentas, la preferida y las de los presupuestos de la
  // categoría. Se consulta el total de cada una, así que la moneda activa siempre tiene query.
  const probeCurrencies = [
    ...new Set([
      preferredCurrency,
      ...(accounts ?? []).map((a) => a.currency),
      ...budgetCurrencies,
    ]),
  ].sort();

  const totalQueries = useQueries({
    queries: probeCurrencies.map((cur) => ({
      queryKey: queryKeys.dashboard.categoryBreakdown(apiMonth, cur, id as string),
      enabled: ready && !!category,
      queryFn: async (): Promise<CategoryDistributionItem[]> =>
        (
          await api.get('dashboard/category-distribution', {
            params: {
              start_date: monthRange.start_date,
              end_date: monthRange.end_date,
              type: categoryType,
              currency: cur,
            },
          })
        ).data,
      placeholderData: keepPreviousData,
    })),
  });
  const totalsSettled = totalQueries.every((q) => !q.isPending && !q.isPlaceholderData);
  const totalFor = (cur: string) => {
    const q = totalQueries[probeCurrencies.indexOf(cur)];
    return q && !q.isPlaceholderData
      ? q.data?.find((row) => row.category_id === Number(id))
      : undefined;
  };

  // Candidatas del chip (D17): monedas con presupuesto o con total en el mes.
  const candidateCurrencies = [
    ...new Set([...budgetCurrencies, ...probeCurrencies.filter((cur) => totalFor(cur))]),
  ].sort();

  const [currencyParam, setCurrencyParam] = useQueryParamState(
    'currency',
    '',
    validateCurrencyParam
  );
  const defaultCurrency =
    budgetCurrencies.length === 0
      ? preferredCurrency
      : budgetCurrencies.length === 1
        ? budgetCurrencies[0]
        : budgetCurrencies.includes(preferredCurrency)
          ? preferredCurrency
          : [...budgetCurrencies].sort()[0];
  // Moneda activa: la de `?currency=` si tiene presupuesto o datos; si no, la default (D3/D17).
  const currency =
    currencyParam && candidateCurrencies.includes(currencyParam) ? currencyParam : defaultCurrency;
  // No se pide la lista hasta conocer usuario, cuentas, presupuestos y totales del mes visible
  // (con datos del mes anterior o la moneda de config la moneda activa podría cambiar).
  const currencyReady =
    ready && !!category && !!user && !!accounts && (!isExpense || !loadingBudgets) && totalsSettled;
  const chipOptions = candidateCurrencies;

  const budget = isExpense ? categoryBudgets.find((b) => b.currency === currency) : undefined;
  const totalQuery = totalQueries[probeCurrencies.indexOf(currency)];
  const totalLoading = !totalQuery || totalQuery.isPending || totalQuery.isPlaceholderData;
  const monthTotal = Number(totalFor(currency)?.total ?? 0);

  // Lista paginada (D4/D19): una query por página (`skip` de 20 en 20), todas bajo el prefijo
  // `transactions.byCategory(id)`; las páginas cargadas se concatenan y una invalidación las
  // refresca todas. La página se reinicia sola al cambiar de mes o moneda (el contexto cambia).
  const listContext = `${apiMonth ?? 'current'}|${currency}`;
  const [pagination, setPagination] = useState({ context: listContext, skip: 0 });
  // Cambió el mes o la moneda: se reinicia el estado de verdad (patrón "ajustar estado en el
  // render"), así volver al mismo contexto no resucita un `skip` viejo.
  if (pagination.context !== listContext) {
    setPagination({ context: listContext, skip: 0 });
  }
  const skip = pagination.context === listContext ? pagination.skip : 0;
  const pageSkips = Array.from({ length: skip / PAGE_SIZE + 1 }, (_, i) => i * PAGE_SIZE);

  const pageQueries = useQueries({
    queries: pageSkips.map((pageSkip) => ({
      queryKey: queryKeys.transactions.byCategoryList(id as string, apiMonth, currency, pageSkip),
      enabled: currencyReady,
      queryFn: async (): Promise<PaginatedResponse<Transaction>> =>
        (
          await api.get('transactions/', {
            params: {
              category_id: Number(id),
              start_date: monthRange.start_date,
              end_date: monthRange.end_date,
              currency,
              type: categoryType,
              skip: pageSkip,
              limit: PAGE_SIZE,
            },
          })
        ).data,
    })),
  });
  const firstPage = pageQueries[0];
  const lastPage = pageQueries[pageQueries.length - 1];
  const transactions: Transaction[] = [];
  const seenIds = new Set<number>();
  for (const q of pageQueries) {
    for (const tx of q.data?.items ?? []) {
      if (!seenIds.has(tx.id)) {
        seenIds.add(tx.id);
        transactions.push(tx);
      }
    }
  }
  const totalCount = firstPage?.data?.total ?? 0;
  const loadingTx = !currencyReady || (firstPage?.isLoading ?? true);
  const transactionsError = !!firstPage?.isError && !firstPage.data;
  const hasMore = transactions.length < totalCount;

  const handleLoadMore = () => {
    // Si falló la página pedida, reintentar esa misma en vez de avanzar `skip`: avanzar
    // saltaría una página entera (mismo criterio que /transactions, Fase 31 F6).
    if (lastPage?.isError) {
      lastPage.refetch();
      return;
    }
    setPagination({ context: listContext, skip: skip + PAGE_SIZE });
  };

  const { data: categories } = useCategories();

  const filteredCategories = categories?.filter((c) => c.type === type) || [];

  const updateMutation = useMutation({
    mutationFn: async (payload: UpdateTransactionPayload) => {
      const response = await api.put(`transactions/${payload.id}`, payload);
      return response.data as Transaction;
    },
    onSuccess: (updated, variables) => {
      // Antes de invalidar: el nombre del sobre sale del caché de la lista de sobres.
      const fundNotice = fundSpendNotice(
        queryClient,
        updated,
        variables.fund_id,
        selectedTransaction
      );
      queryClient.invalidateQueries({ queryKey: queryKeys.transactions.all() });
      queryClient.invalidateQueries({ queryKey: queryKeys.transactions.byCategory(id as string) });
      queryClient.invalidateQueries({ queryKey: queryKeys.categories.byId(id as string) });
      queryClient.invalidateQueries({ queryKey: queryKeys.accounts.all() });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.summary() });
      queryClient.invalidateQueries({ queryKey: queryKeys.budgets.progress() });
      queryClient.invalidateQueries({ queryKey: ['analytics-cashflow'] });
      queryClient.invalidateQueries({ queryKey: ['analytics-categories'] });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.categoryBreakdown() });
      queryClient.invalidateQueries({ queryKey: queryKeys.accounts.summary() });
      // Fase 36: un gasto enlazado cambia el saldo y los gastos enlazados de algún sobre.
      queryClient.invalidateQueries({ queryKey: queryKeys.funds.all() });
      queryClient.invalidateQueries({ queryKey: queryKeys.funds.details() });
      toast.success('Transacción actualizada', { description: fundNotice });
      setIsModalOpen(false);
      setSelectedTransaction(null);
    },
    onError: (error: unknown) => {
      toast.error(getApiError(error));
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (txId: number) => {
      await api.delete(`transactions/${txId}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.transactions.all() });
      queryClient.invalidateQueries({ queryKey: queryKeys.transactions.byCategory(id as string) });
      queryClient.invalidateQueries({ queryKey: queryKeys.categories.byId(id as string) });
      queryClient.invalidateQueries({ queryKey: queryKeys.accounts.all() });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.summary() });
      queryClient.invalidateQueries({ queryKey: queryKeys.budgets.progress() });
      queryClient.invalidateQueries({ queryKey: ['analytics-cashflow'] });
      queryClient.invalidateQueries({ queryKey: ['analytics-categories'] });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.categoryBreakdown() });
      queryClient.invalidateQueries({ queryKey: queryKeys.accounts.summary() });
      // Fase 36: un gasto enlazado cambia el saldo y los gastos enlazados de algún sobre.
      queryClient.invalidateQueries({ queryKey: queryKeys.funds.all() });
      queryClient.invalidateQueries({ queryKey: queryKeys.funds.details() });
      toast.success('Transacción eliminada');
    },
    onError: (error: unknown) => {
      toast.error(getApiError(error));
    },
  });

  const openEditModal = (tx: Transaction) => {
    setSelectedTransaction(tx);
    setDescription(tx.description || '');
    setAmount(String(tx.amount));
    setType(tx.type);
    // Fase 34 F4: el día del instante en la zona del usuario (`Intl`), no el día UTC.
    setTransactionDate(dayInZone(tx.date, displayTimezone) || todayInZone(displayTimezone));
    setAccountId(String(tx.account_id));
    setCategoryId(String(tx.category_id));
    setIsModalOpen(true);
  };

  const handleUpdate = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedTransaction) return;

    updateMutation.mutate({
      id: selectedTransaction.id,
      description: description.trim() || null,
      amount: Number(amount),
      type: type as 'income' | 'expense',
      // Fase 34 B9: solo si el usuario cambió la fecha (no re-estampar la hora al editar el monto).
      date:
        transactionDate !== dayInZone(selectedTransaction.date, displayTimezone)
          ? transactionDate
          : undefined,
      account_id: Number(accountId),
      category_id: Number(categoryId),
    });
  };

  if (loadingCategory)
    return (
      <div className="space-y-6">
        <Skeleton className="h-10 w-64 rounded-xl" />
        <Skeleton className="h-40 rounded-2xl" />
        <Skeleton className="h-96 rounded-3xl" />
      </div>
    );
  if (categoryError && !category) {
    return (
      <QueryErrorState
        message="No se pudieron cargar tus categorías. Intenta de nuevo más tarde."
        onRetry={() => refetchCategory()}
        className="col-span-full"
      />
    );
  }
  if (!category)
    return <div className="text-text-muted p-8">No se encontró la categoría especificada.</div>;

  // "Restante" / "Excedido por": diferencia de dos cifras del backend solo para mostrarla; el
  // porcentaje y la condición de exceso (`percentage > 100`) salen del backend.
  const budgetDiff = budget ? Number(budget.amount_limit) - Number(budget.spent) : 0;
  const budgetExceeded = !!budget && Number(budget.percentage) > 100;

  const totalBlock = (
    <div className="bg-surface border-border/70 rounded-2xl border p-4 sm:p-6">
      <p className="text-text-muted text-xs font-medium">Total del mes</p>
      {totalQuery?.isError ? (
        <QueryErrorState
          message="No se pudo cargar el total del mes."
          onRetry={() => totalQuery.refetch()}
        />
      ) : totalLoading ? (
        <Skeleton className="mt-1 h-7 w-36" />
      ) : (
        <p className="text-text mt-0.5 font-sans text-2xl font-bold tabular-nums">
          {formatCurrency(monthTotal, currency)}
        </p>
      )}
    </div>
  );

  const budgetBlock = !isExpense ? null : loadingBudgets ? (
    <Skeleton className="h-64 rounded-2xl" />
  ) : budgetsError ? (
    <QueryErrorState message="No se pudo cargar el presupuesto." onRetry={() => refetchBudgets()} />
  ) : budget ? (
    <div className="space-y-4">
      <BudgetRing
        categoryName={category.name}
        categoryIcon={category.icon}
        budgetAmount={Number(budget.amount_limit)}
        spentAmount={Number(budget.spent)}
        percentage={Number(budget.percentage)}
        currency={budget.currency}
      />
      <dl className="bg-surface border-border/70 space-y-2 rounded-2xl border p-4 text-sm sm:p-6">
        <div className="flex justify-between gap-3">
          <dt className="text-text-muted">Gastado</dt>
          <dd className="text-text tabular-nums">
            {formatCurrency(Number(budget.spent), budget.currency)}
          </dd>
        </div>
        <div className="flex justify-between gap-3">
          <dt className="text-text-muted">Límite</dt>
          <dd className="text-text tabular-nums">
            {formatCurrency(Number(budget.amount_limit), budget.currency)}
          </dd>
        </div>
        <div className="flex justify-between gap-3">
          <dt className="text-text-muted">{budgetExceeded ? 'Excedido por' : 'Restante'}</dt>
          <dd
            className={`font-semibold tabular-nums ${budgetExceeded ? 'text-danger' : 'text-text'}`}
          >
            {formatCurrency(Math.abs(budgetDiff), budget.currency)}
          </dd>
        </div>
      </dl>
    </div>
  ) : (
    <p className="text-text-muted text-sm">
      Sin presupuesto este mes.{' '}
      <Link href="/budgets" className="text-primary hover:text-primary-dark font-medium">
        Ir a Presupuestos
      </Link>
    </p>
  );
  const twoColumns = isExpense && (loadingBudgets || budgetsError || !!budget);

  return (
    <div className="space-y-6 sm:space-y-8">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div className="flex items-center space-x-4">
          <button
            onClick={() => router.back()}
            className="bg-surface hover:bg-surface-elevated border-border/70 text-text-muted hover:text-text cursor-pointer rounded-xl border p-2 transition-colors active:scale-95"
            aria-label="Volver"
          >
            <ArrowLeft size={18} />
          </button>
          <div>
            <div className="text-text-muted flex items-center space-x-2 text-xs tracking-wider uppercase">
              <CategoryIcon icon={category.icon} size={12} fallback={<Tag size={12} />} />
              <span>Detalle de categoría</span>
            </div>
            <h1 className="text-text mt-0.5 font-sans text-2xl font-bold">{category.name}</h1>
          </div>
        </div>
        <MonthNavigator
          state={monthState}
          firstTransactionMonth={summary?.first_transaction_month}
        />
      </div>

      {chipOptions.length > 1 && (
        <SegmentedControl
          options={chipOptions.map((value) => ({ value, label: value }))}
          value={currency}
          onChange={(next) => setCurrencyParam(next)}
          ariaLabel="Moneda de la categoría"
        />
      )}

      {/* Escritorio: presupuesto a la izquierda, movimientos a la derecha; móvil apilado con
          el presupuesto arriba (D8). Sin presupuesto, la lista ocupa todo el ancho. */}
      <div className={twoColumns ? 'grid gap-6 lg:grid-cols-3' : 'space-y-6'}>
        <div className="min-w-0 space-y-4 lg:col-span-1">
          {totalBlock}
          {budgetBlock}
        </div>

        <div className="min-w-0 space-y-4 lg:col-span-2">
          <h2 className="text-text font-sans text-lg font-bold">Movimientos de {monthNameLower}</h2>

          <div className="bg-surface border-border/70 shadow-background/20 overflow-hidden rounded-3xl border shadow-sm">
            {transactionsError ? (
              <QueryErrorState
                message="No se pudieron cargar los movimientos."
                onRetry={() => firstPage?.refetch()}
              />
            ) : loadingTx ? (
              <div className="space-y-3 p-4">
                {Array.from({ length: 4 }).map((_, i) => (
                  <Skeleton key={i} className="h-12 rounded-xl" />
                ))}
              </div>
            ) : transactions.length === 0 ? (
              <div className="text-text-muted p-12 text-center text-sm">
                {isCurrentMonth
                  ? 'No hay transacciones de esta categoría este mes.'
                  : `No hay transacciones de esta categoría en ${monthNameLower}.`}
              </div>
            ) : (
              <div className="divide-border/40 divide-y">
                {transactions.map((tx) => {
                  const account = accounts?.find((a) => a.id === tx.account_id);

                  return (
                    <div
                      key={tx.id}
                      className="group hover:bg-surface-elevated flex items-center justify-between gap-4 p-4 transition-colors sm:px-6"
                    >
                      <div className="flex items-center space-x-4">
                        <div
                          className={`bg-background border-border/60 rounded-full border p-2.5 ${isExpense ? 'text-text-muted' : 'text-primary'}`}
                        >
                          {isExpense ? <ArrowDownRight size={18} /> : <ArrowUpRight size={18} />}
                        </div>
                        <div>
                          <p className="text-text text-sm font-medium">
                            {tx.description || category.name}
                          </p>
                          <p className="text-text-muted mt-0.5 text-xs">
                            {account?.name || 'Cuenta eliminada'}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        <div className="text-right">
                          <p
                            className={`font-sans font-semibold tabular-nums ${isExpense ? 'text-text' : 'text-primary'}`}
                          >
                            {isExpense ? '-' : '+'}
                            {formatCurrency(tx.amount, tx.currency)}
                          </p>
                          <p className="text-text-muted text-[11px]">
                            {formatDateLabel(tx.date, config.locale, displayTimezone)}
                          </p>
                        </div>
                        <div className="flex items-center gap-1 opacity-100 sm:opacity-0 sm:transition-opacity sm:group-focus-within:opacity-100 sm:group-hover:opacity-100">
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
            )}
          </div>

          {!loadingTx && !transactionsError && (hasMore || lastPage?.isError) && (
            <div className="flex justify-center">
              <Button
                variant="secondary"
                onClick={handleLoadMore}
                loading={!!lastPage?.isFetching && pageQueries.length > 1}
              >
                {lastPage?.isError ? 'Reintentar' : 'Cargar más'}
              </Button>
            </div>
          )}

          {/* D11: el historial completo vive en /transactions, filtrado por categoría y mes. */}
          {!transactionsError && !loadingTx && (
            <Link
              href={monthTransactionsHref(year, month, id as string)}
              className="text-primary hover:text-primary-dark block text-center text-sm font-medium transition-colors"
            >
              Ver en Movimientos
            </Link>
          )}
        </div>
      </div>

      <ModalShell
        isOpen={isModalOpen && !!selectedTransaction}
        onClose={() => setIsModalOpen(false)}
        title="Editar movimiento"
      >
        {selectedTransaction && (
          <form onSubmit={handleUpdate} className="space-y-4">
            <div className="flex gap-4">
              <button
                type="button"
                onClick={() => setType('expense')}
                className={`flex-1 cursor-pointer rounded-xl border py-2 text-sm font-medium transition-colors ${type === 'expense' ? 'bg-background border-border text-text' : 'text-text-muted hover:text-text border-transparent'}`}
              >
                Gasto
              </button>
              <button
                type="button"
                onClick={() => setType('income')}
                className={`flex-1 cursor-pointer rounded-xl border py-2 text-sm font-medium transition-colors ${type === 'income' ? 'bg-primary/10 border-primary/20 text-primary' : 'text-text-muted hover:text-text border-transparent'}`}
              >
                Ingreso
              </button>
            </div>

            <Input
              label="Valor"
              type="number"
              required
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              className="bg-background"
            />

            <Input
              label="Descripción"
              placeholder="Opcional"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="bg-background"
            />

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Select
                label="Cuenta"
                required
                value={accountId}
                onChange={(e) => setAccountId(e.target.value)}
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
                label="Categoría"
                required
                value={categoryId}
                onChange={(e) => setCategoryId(e.target.value)}
                className="bg-background appearance-none"
              >
                <option value="" disabled>
                  Selecciona...
                </option>
                {filteredCategories.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </Select>
            </div>

            <Input
              label="Fecha"
              type="date"
              required
              value={transactionDate}
              onChange={(e) => setTransactionDate(e.target.value)}
              className="bg-background"
            />

            <div className="mt-6 flex gap-3">
              <Button
                type="button"
                variant="ghost"
                onClick={() => setIsModalOpen(false)}
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
