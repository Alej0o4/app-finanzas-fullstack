'use client';

import { useParams, useRouter } from 'next/navigation';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ArrowLeft,
  Wallet,
  Loader2,
  ArrowDownRight,
  ArrowUpRight,
  Pencil,
  Trash2,
  Circle,
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
import Button from '@/components/ui/Button';
import { useState } from 'react';
import CategoryIcon from '@/components/ui/CategoryIcon';
import type {
  Account,
  Transaction,
  Category,
  UpdateTransactionPayload,
  PaginatedResponse,
} from '@/types/api';

export default function AccountDetailPage() {
  const { config } = useAppConfig();
  const { id } = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();

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
    queryFn: async () => (await api.get(`/api/accounts/${id}`)).data,
  });

  const { data: transactionsData, isLoading: loadingTx } = useQuery<PaginatedResponse<Transaction>>(
    {
      queryKey: queryKeys.transactions.byAccount(id as string),
      queryFn: async () =>
        (await api.get(`/api/transactions/`, { params: { account_id: Number(id) } })).data,
    }
  );

  const transactions = transactionsData?.items;

  const { data: categories } = useQuery<Category[]>({
    queryKey: queryKeys.categories.all(),
    queryFn: async () => (await api.get('/api/categories/')).data,
  });
  const { data: allAccounts } = useQuery<Account[]>({
    queryKey: queryKeys.accounts.all(),
    queryFn: async () => (await api.get('/api/accounts/')).data,
  });

  const accountOptions: Account[] = allAccounts || (account ? [account] : []);

  const filteredCategories = categories?.filter((c) => c.type === type) || [];

  const updateMutation = useMutation({
    mutationFn: async (payload: UpdateTransactionPayload) => {
      const response = await api.put(`/api/transactions/${payload.id}`, payload);
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
      await api.delete(`/api/transactions/${txId}`);
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
      <div className="text-text-muted flex items-center gap-2 p-8">
        <Loader2 className="animate-spin" /> Cargando historial de cuenta...
      </div>
    );
  if (!account)
    return <div className="text-text-muted p-8">No se encontró la cuenta especificada.</div>;

  return (
    <div className="space-y-8">
      <div className="flex items-center space-x-4">
        <button
          onClick={() => router.back()}
          className="bg-surface hover:bg-surface-elevated border-border/70 text-text-muted hover:text-text cursor-pointer rounded-xl border p-2 transition-colors"
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
        <p className="text-text mt-2 font-sans text-4xl font-bold">
          {formatCurrency(account.balance, account.currency)}
        </p>
      </div>

      <div className="space-y-4">
        <h2 className="text-text font-sans text-lg font-bold">Historial de movimientos</h2>

        <div className="bg-surface border-border/70 overflow-hidden rounded-3xl border shadow-sm">
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
                          className={`font-sans font-semibold ${isExpense ? 'text-text' : 'text-primary'}`}
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
