'use client';

import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { api } from '@/lib/api';
import { queryKeys } from '@/lib/queryKeys';
import { getApiError } from '@/lib/utils';
import ModalShell from '@/components/ui/ModalShell';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import Select from '@/components/ui/Select';
import type { Account, Category, CreateTransactionPayload } from '@/types/api';

interface TransactionModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: () => void;
  defaultType?: 'income' | 'expense';
  title?: string;
}

const todayAsInputValue = () => new Date().toISOString().split('T')[0];

export default function TransactionModal({
  isOpen,
  onClose,
  onSuccess,
  defaultType = 'expense',
  title = 'Registrar movimiento',
}: TransactionModalProps) {
  const queryClient = useQueryClient();

  const [description, setDescription] = useState('');
  const [amount, setAmount] = useState('');
  const [type, setType] = useState<'income' | 'expense'>(defaultType);
  const [date, setDate] = useState(todayAsInputValue());
  const [accountId, setAccountId] = useState('');
  const [categoryId, setCategoryId] = useState('');
  const [showAllCategories, setShowAllCategories] = useState(false);

  const { data: accounts } = useQuery<Account[]>({
    queryKey: queryKeys.accounts.all(),
    queryFn: async () => (await api.get('/api/accounts/')).data,
    enabled: isOpen,
  });

  const { data: categories } = useQuery<Category[]>({
    queryKey: queryKeys.categories.all(),
    queryFn: async () => (await api.get('/api/categories/')).data,
    enabled: isOpen,
  });

  const displayedCategories = useMemo(() => {
    if (showAllCategories) return categories || [];
    return categories?.filter((category) => category.type === type) || [];
  }, [categories, type, showAllCategories]);

  const createMutation = useMutation({
    mutationFn: async (newTx: CreateTransactionPayload) => {
      const response = await api.post('/api/transactions/', newTx);
      return response.data;
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.transactions.all() }),
        queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.recentTransactions() }),
        queryClient.invalidateQueries({ queryKey: queryKeys.accounts.all() }),
        queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.summary() }),
        queryClient.invalidateQueries({ queryKey: queryKeys.budgets.progress() }),
        queryClient.invalidateQueries({ queryKey: ['analytics-cashflow'] }),
        queryClient.invalidateQueries({ queryKey: ['analytics-categories'] }),
      ]);

      toast.success('Transacción creada correctamente');
      onSuccess?.();
      onClose();
    },
    onError: (error: unknown) => {
      toast.error(getApiError(error));
    },
  });

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();

    createMutation.mutate({
      description,
      amount: Number(amount),
      type,
      date,
      account_id: Number(accountId),
      category_id: Number(categoryId),
    });
  };

  return (
    <ModalShell isOpen={isOpen} onClose={onClose} title={title}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="flex gap-4">
          <button
            type="button"
            onClick={() => setType('expense')}
            className={`flex-1 cursor-pointer rounded-xl border py-2 text-sm font-medium transition-colors ${
              type === 'expense'
                ? 'bg-background border-border text-text'
                : 'text-text-muted hover:text-text border-transparent'
            }`}
          >
            Gasto
          </button>
          <button
            type="button"
            onClick={() => setType('income')}
            className={`flex-1 cursor-pointer rounded-xl border py-2 text-sm font-medium transition-colors ${
              type === 'income'
                ? 'bg-primary/15 border-primary/30 text-primary'
                : 'text-text-muted hover:text-text border-transparent'
            }`}
          >
            Ingreso
          </button>
        </div>

        <Input
          label="Valor"
          type="number"
          required
          value={amount}
          onChange={(event) => setAmount(event.target.value)}
          className="bg-background"
          placeholder="0"
        />

        <Input
          label="Descripción"
          required
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          className="bg-background"
          placeholder="Ej. Almuerzo il forno..."
        />

        <div className="grid grid-cols-2 gap-4">
          <Select
            label="Cuenta"
            required
            value={accountId}
            onChange={(event) => setAccountId(event.target.value)}
            className="bg-background"
          >
            <option value="" disabled>
              Selecciona...
            </option>
            {accounts?.map((account) => (
              <option key={account.id} value={account.id}>
                {account.name}
              </option>
            ))}
          </Select>
          <div>
            <Select
              label="Categoría"
              required
              value={categoryId}
              onChange={(event) => setCategoryId(event.target.value)}
              className="bg-background"
            >
              <option value="" disabled>
                Selecciona...
              </option>
              {displayedCategories.map((category) => (
                <option key={category.id} value={category.id}>
                  {category.name}
                  {showAllCategories
                    ? ` (${category.type === 'income' ? 'Ingreso' : 'Gasto'})`
                    : ''}
                </option>
              ))}
            </Select>
            <button
              type="button"
              onClick={() => setShowAllCategories(!showAllCategories)}
              className="text-primary/70 hover:text-primary mt-1 text-xs transition-colors"
            >
              {showAllCategories ? '← Solo del tipo' : '+ Mostrar todas las categorías'}
            </button>
          </div>
        </div>

        <Input
          label="Fecha"
          type="date"
          required
          value={date}
          onChange={(event) => setDate(event.target.value)}
          className="bg-background"
        />

        <div className="mt-6 flex gap-3">
          <Button type="button" variant="ghost" onClick={onClose} className="flex-1">
            Cancelar
          </Button>
          <Button
            type="submit"
            variant="primary"
            loading={createMutation.isPending}
            className="flex-1"
          >
            Guardar
          </Button>
        </div>
      </form>
    </ModalShell>
  );
}
