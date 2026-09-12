'use client';

import { useParams, useRouter } from 'next/navigation';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ArrowLeft,
  Wallet,
  ArrowDownRight,
  ArrowUpRight,
  Pencil,
  Trash2,
  Circle,
  PieChart,
  Tags,
} from 'lucide-react';
import { toast } from 'sonner';
import { api } from '@/lib/api';
import { formatCurrency, formatDate, getApiError } from '@/lib/utils';
import { useAppConfig } from '@/providers/AppConfigProvider';
import { useConfirmStore } from '@/store/useConfirmStore';
import { queryKeys } from '@/lib/queryKeys';
import Input from '@/components/ui/Input';
import Select from '@/components/ui/Select';
import ModalShell from '@/components/ui/ModalShell';
import Skeleton from '@/components/ui/Skeleton';
import Button from '@/components/ui/Button';
import EmptyState from '@/components/ui/EmptyState';
import CategoryIcon from '@/components/ui/CategoryIcon';
import BudgetRing from '@/components/charts/BudgetRing';
import CategoryBreakdownBars from '@/components/charts/CategoryBreakdownBars';
import AccountMonthlyBalanceCard from '@/components/charts/AccountMonthlyBalanceCard';
import { useState } from 'react';
import type {
  Account,
  Transaction,
  Category,
  UpdateTransactionPayload,
  PaginatedResponse,
  BudgetProgress,
  CategoryDistributionItem,
  AccountMonthlySummary,
} from '@/types/api';
import type { components } from '@/types/generated/api';

type AccountReconcileResponse = components['schemas']['AccountReconcileResponse'];

export default function AccountDetailPage() {
  const { config } = useAppConfig();
  const { id } = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();

  // Fechas del mes en curso (mismo patrón EXACTO que dashboard/page.tsx:35-41 —
  // .toISOString() sin armar strings con getters locales: el backend interpreta las fechas
  // como UTC y los getters locales recortaban "ahora" 5 horas en America/Bogota, excluyendo
  // transacciones recién creadas — precedente de bugs de zona horaria Fase 15/parada UX).
  const now = new Date();
  const monthStartISO = new Date(now.getFullYear(), now.getMonth(), 1).toISOString();
  const todayISO = now.toISOString();

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [selectedTransaction, setSelectedTransaction] = useState<Transaction | null>(null);
  const [description, setDescription] = useState('');
  const [amount, setAmount] = useState('');
  const [type, setType] = useState('expense');
  const [transactionDate, setTransactionDate] = useState(new Date().toISOString().split('T')[0]);
  const [accountId, setAccountId] = useState(String(id));
  const [categoryId, setCategoryId] = useState('');

  const { data: account, isLoading: loadingAccount } = useQuery<Account>({
    queryKey: queryKeys.accounts.byId(id as string),
    queryFn: async () => (await api.get(`accounts/${id}`)).data,
  });

  const { data: transactionsData, isLoading: loadingTx } = useQuery<PaginatedResponse<Transaction>>(
    {
      queryKey: queryKeys.transactions.byAccount(id as string),
      queryFn: async () =>
        (await api.get(`transactions/`, { params: { account_id: Number(id) } })).data,
    }
  );

  const transactions = transactionsData?.items;

  const { data: categories } = useQuery<Category[]>({
    queryKey: queryKeys.categories.all(),
    queryFn: async () => (await api.get('categories/')).data,
  });
  const { data: allAccounts } = useQuery<Account[]>({
    queryKey: queryKeys.accounts.all(),
    queryFn: async () => (await api.get('accounts/')).data,
  });

  // ── Fase 17 §17.1: analítica por cuenta ──────────────────────────────────────────────
  // Balance del mes de esta cuenta (GET /accounts/{id}/monthly-summary, Decisión 17.1.4).
  // El valor siempre se calcula del lado del backend — sin estado "sin definir".
  const { data: monthlySummary, isLoading: loadingMonthlySummary } =
    useQuery<AccountMonthlySummary>({
      queryKey: queryKeys.accounts.monthlySummary(id as string),
      queryFn: async () => (await api.get(`accounts/${id}/monthly-summary`)).data,
    });

  // Gastos del mes por categoría restringidos a esta cuenta (Fase 17 §17.1.3). `currency`
  // se pasa EXPLÍCITO junto con `account_id` — el backend no deriva la moneda de la cuenta
  // (son ortogonales); la moneda de una cuenta no tiene por qué coincidir con la preferida.
  const { data: categoryBreakdown, isLoading: loadingCategoryBreakdown } = useQuery<
    CategoryDistributionItem[]
  >({
    queryKey: queryKeys.accounts.categoryBreakdown(id as string),
    queryFn: async () =>
      (
        await api.get('dashboard/category-distribution', {
          params: {
            start_date: monthStartISO,
            end_date: todayISO,
            type: 'expense',
            account_id: Number(id),
            currency: account?.currency,
          },
        })
      ).data,
    enabled: !!account, // necesita account.currency ya cargado
  });

  // Progreso de presupuestos filtrado a la moneda de la cuenta (Decisión 17.1.3/P4: Budget no
  // tiene account_id — "presupuestos de esta cuenta" significa "presupuestos en la moneda de
  // esta cuenta"; el spend de cada fila no se recalcula por cuenta).
  const { data: budgetsProgress, isLoading: loadingBudgets } = useQuery<BudgetProgress[]>({
    queryKey: queryKeys.accounts.budgetsProgress(id as string),
    queryFn: async () =>
      (
        await api.get('dashboard/budgets-progress', {
          params: { currency: account?.currency },
        })
      ).data,
    enabled: !!account,
  });

  const accountOptions: Account[] = allAccounts || (account ? [account] : []);

  const filteredCategories = categories?.filter((c) => c.type === type) || [];

  const updateMutation = useMutation({
    mutationFn: async (payload: UpdateTransactionPayload) => {
      const response = await api.put(`transactions/${payload.id}`, payload);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.transactions.all() });
      queryClient.invalidateQueries({ queryKey: queryKeys.transactions.byAccount(id as string) });
      queryClient.invalidateQueries({ queryKey: queryKeys.accounts.byId(id as string) });
      queryClient.invalidateQueries({ queryKey: queryKeys.accounts.all() });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.summary() });
      queryClient.invalidateQueries({ queryKey: queryKeys.budgets.progress() });
      queryClient.invalidateQueries({ queryKey: ['analytics-cashflow'] });
      queryClient.invalidateQueries({ queryKey: ['analytics-categories'] });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.categoryBreakdown() });
      queryClient.invalidateQueries({ queryKey: queryKeys.accounts.summary() });
      // Fase 17 §17.1: monthly-summary, desglose por categoría y progreso de presupuestos de
      // esta cuenta dependen de las transacciones — invalidar las claves propias por cuenta.
      queryClient.invalidateQueries({ queryKey: queryKeys.accounts.monthlySummary(id as string) });
      queryClient.invalidateQueries({
        queryKey: queryKeys.accounts.categoryBreakdown(id as string),
      });
      queryClient.invalidateQueries({ queryKey: queryKeys.accounts.budgetsProgress(id as string) });
      toast.success('Transacción actualizada');
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
      queryClient.invalidateQueries({ queryKey: queryKeys.transactions.byAccount(id as string) });
      queryClient.invalidateQueries({ queryKey: queryKeys.accounts.byId(id as string) });
      queryClient.invalidateQueries({ queryKey: queryKeys.accounts.all() });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.summary() });
      queryClient.invalidateQueries({ queryKey: queryKeys.budgets.progress() });
      queryClient.invalidateQueries({ queryKey: ['analytics-cashflow'] });
      queryClient.invalidateQueries({ queryKey: ['analytics-categories'] });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.categoryBreakdown() });
      queryClient.invalidateQueries({ queryKey: queryKeys.accounts.summary() });
      // Fase 17 §17.1: monthly-summary, desglose por categoría y progreso de presupuestos de
      // esta cuenta dependen de las transacciones — invalidar las claves propias por cuenta.
      queryClient.invalidateQueries({ queryKey: queryKeys.accounts.monthlySummary(id as string) });
      queryClient.invalidateQueries({
        queryKey: queryKeys.accounts.categoryBreakdown(id as string),
      });
      queryClient.invalidateQueries({ queryKey: queryKeys.accounts.budgetsProgress(id as string) });
      toast.success('Transacción eliminada');
    },
    onError: (error: unknown) => {
      toast.error(getApiError(error));
    },
  });

  // Fase 16 §16.4: recalcula `balance` desde opening_balance + historial de transacciones
  // (POST accounts/{id}/reconcile). El backend aplica la corrección de inmediato y devuelve
  // la discrepancia encontrada — el frontend solo la muestra (Decisión 16.4.2, sin preview).
  const reconcileMutation = useMutation({
    mutationFn: async () => {
      const response = await api.post(`accounts/${id}/reconcile`);
      return response.data as AccountReconcileResponse;
    },
    onSuccess: (data) => {
      const discrepancy = Number(data.discrepancy);
      toast.success(
        discrepancy === 0
          ? 'El saldo está correcto'
          : `Se corrigió una diferencia de ${formatCurrency(discrepancy, account?.currency || 'COP')}`
      );
      queryClient.invalidateQueries({ queryKey: queryKeys.accounts.byId(id as string) });
      queryClient.invalidateQueries({ queryKey: queryKeys.accounts.all() });
      queryClient.invalidateQueries({ queryKey: queryKeys.accounts.summary() });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.summary() });
      // Fase 17 §17.1: por coherencia se invalidan también las claves propias de la cuenta;
      // el recálculo cambia el saldo, no el balance del mes, pero la invalidación es barata.
      queryClient.invalidateQueries({ queryKey: queryKeys.accounts.monthlySummary(id as string) });
      queryClient.invalidateQueries({
        queryKey: queryKeys.accounts.categoryBreakdown(id as string),
      });
      queryClient.invalidateQueries({ queryKey: queryKeys.accounts.budgetsProgress(id as string) });
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
    setTransactionDate(tx.date ? tx.date.split('T')[0] : new Date().toISOString().split('T')[0]);
    setAccountId(String(tx.account_id));
    setCategoryId(String(tx.category_id));
    setIsModalOpen(true);
  };

  const handleUpdate = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedTransaction) return;

    updateMutation.mutate({
      id: selectedTransaction.id,
      description,
      amount: Number(amount),
      type: type as 'income' | 'expense',
      date: transactionDate,
      account_id: Number(accountId),
      category_id: Number(categoryId),
    });
  };

  const isLoading = loadingAccount || loadingTx;

  if (isLoading)
    return (
      <div className="space-y-6">
        <Skeleton className="h-10 w-64 rounded-xl" />
        <Skeleton className="h-40 rounded-2xl" />
        <Skeleton className="h-96 rounded-3xl" />
      </div>
    );
  if (!account)
    return <div className="text-text-muted p-8">No se encontró la cuenta especificada.</div>;

  return (
    <div className="space-y-8">
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
            <Wallet size={12} />
            <span>Detalle de cuenta</span>
          </div>
          <h1 className="text-text mt-0.5 font-sans text-2xl font-bold">{account.name}</h1>
        </div>
      </div>

      <div className="bg-surface border-border/70 max-w-sm rounded-3xl border p-6">
        <p className="text-text-muted text-xs font-medium tracking-wider uppercase">
          Saldo disponible
        </p>
        <p className="text-text mt-2 font-sans text-4xl font-bold tabular-nums">
          {formatCurrency(account.balance, account.currency)}
        </p>
        {/* Saldo de apertura (Fase 16 §16.4): ancla para el recálculo, inmutable tras la
            creación de la cuenta — el backend lo entrega y acá solo se muestra. */}
        <p className="text-text-muted mt-1 text-xs">
          Saldo inicial: {formatCurrency(account.opening_balance, account.currency)}
        </p>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => reconcileMutation.mutate()}
          loading={reconcileMutation.isPending}
          className="mt-4"
        >
          Recalcular saldo
        </Button>
      </div>

      {/* ── Fase 17 §17.1: analítica por cuenta (solo lectura, sin controles de filtro) ── */}

      {/* Balance del mes de esta cuenta (Decisión 17.1.2). El cálculo vive en el backend
          (GET /accounts/{id}/monthly-summary); acá solo se restan los dos montos para
          pintar, y los Decimal→string se normalizan con Number(...) (Decisión 15.6). */}
      <AccountMonthlyBalanceCard
        label="Balance del mes"
        income={Number(monthlySummary?.monthly_income)}
        expense={Number(monthlySummary?.monthly_expense)}
        currency={account.currency}
        isLoading={loadingMonthlySummary}
      />

      {/* Ejecución de Presupuestos — mismo mapeo y estados que dashboard/page.tsx:244-281,
          filtrado a la moneda de esta cuenta (Decisión 17.1.3/P4). */}
      <div>
        <div className="mb-6 flex items-center space-x-2">
          <PieChart className="text-primary" size={20} />
          <h2 className="text-text font-sans text-xl font-bold">Ejecución de Presupuestos</h2>
        </div>

        {loadingBudgets ? (
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="flex flex-col items-center gap-3 p-6">
                <Skeleton className="h-24 w-24 rounded-full" />
                <Skeleton className="h-4 w-20" />
                <Skeleton className="h-3 w-16" />
              </div>
            ))}
          </div>
        ) : !budgetsProgress || budgetsProgress.length === 0 ? (
          <EmptyState
            icon={<PieChart size={48} className="opacity-20" />}
            message="Aún no hay datos de progreso."
            description="Asegúrate de tener presupuestos definidos y gastos registrados en este mes."
          />
        ) : (
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
            {budgetsProgress.map((budget, index) => (
              <BudgetRing
                key={budget.budget_id || `budget-ring-${index}`}
                categoryName={budget.category_name}
                categoryIcon={budget.category_icon}
                budgetAmount={Number(budget.amount_limit)}
                spentAmount={Number(budget.spent)}
                currency={budget.currency}
              />
            ))}
          </div>
        )}
      </div>

      {/* Gastos por Categoría de esta cuenta (Fase 17 §17.1.3) — la moneda de la cuenta se
          pasa explícita; el dashboard sigue formateando con la preferida global. */}
      <div>
        <div className="mb-6 flex items-center space-x-2">
          <Tags className="text-primary" size={20} />
          <h2 className="text-text font-sans text-xl font-bold">
            Gastos por Categoría de esta cuenta
          </h2>
        </div>

        <CategoryBreakdownBars
          data={categoryBreakdown}
          isLoading={loadingCategoryBreakdown}
          currency={account.currency}
        />
      </div>

      <div className="space-y-4">
        <h2 className="text-text font-sans text-lg font-bold">Historial de movimientos</h2>

        <div className="bg-surface border-border/70 shadow-background/20 overflow-hidden rounded-3xl border shadow-sm">
          {!transactions || transactions.length === 0 ? (
            <div className="text-text-muted p-12 text-center text-sm">
              No hay transacciones registradas con esta cuenta.
            </div>
          ) : (
            <div className="divide-border/40 divide-y">
              {transactions.map((tx) => {
                const isExpense = tx.type === 'expense';
                const category = categories?.find((c) => c.id === tx.category_id);

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
                        <p className="text-text text-sm font-medium">{tx.description}</p>
                        <p className="text-text-muted mt-0.5 inline-flex items-center gap-1 text-xs">
                          <CategoryIcon
                            icon={category?.icon}
                            size={12}
                            fallback={<Circle size={12} className="opacity-30" />}
                          />
                          {category?.name || 'Sin categoría'}
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
              required
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
                className="bg-background"
              >
                <option value="" disabled>
                  Selecciona...
                </option>
                {accountOptions.map((a) => (
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
                className="bg-background"
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
