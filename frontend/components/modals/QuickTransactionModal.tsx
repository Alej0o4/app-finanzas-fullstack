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

interface QuickTransactionModalProps {
  isOpen: boolean;
  onClose: () => void;
  defaultType?: 'income' | 'expense';
}

const todayAsInputValue = () => new Date().toISOString().split('T')[0];

export default function QuickTransactionModal({
  isOpen,
  onClose,
  defaultType = 'expense',
}: QuickTransactionModalProps) {
  const queryClient = useQueryClient();

  const [amount, setAmount] = useState('');
  const [type, setType] = useState<'income' | 'expense'>(defaultType);
  const [accountId, setAccountId] = useState('');
  const [categoryId, setCategoryId] = useState('');
  const [date, setDate] = useState(todayAsInputValue());
  const [description, setDescription] = useState('');

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

  const filteredCategories = useMemo(
    () => categories?.filter((c) => c.type === type) || [],
    [categories, type]
  );

  const effectiveAccountId = accountId || (accounts?.length ? String(accounts[0].id) : '');

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

      toast.success(type === 'expense' ? 'Gasto registrado' : 'Ingreso registrado');

      setAmount('');
      setCategoryId('');
      setDate(todayAsInputValue());
      setDescription('');
      onClose();
    },
    onError: (error: unknown) => {
      toast.error(getApiError(error));
    },
  });

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!effectiveAccountId || !categoryId || !amount) return;

    createMutation.mutate({
      description,
      amount: Number(amount),
      type,
      date,
      account_id: Number(effectiveAccountId),
      category_id: Number(categoryId),
    });
  };

  const handleTypeChange = (newType: 'income' | 'expense') => {
    setType(newType);
    setCategoryId('');
  };

  const title = type === 'expense' ? 'Gasto rápido' : 'Ingreso rápido';

  return (
    <ModalShell isOpen={isOpen} onClose={onClose} title={title}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => handleTypeChange('expense')}
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
            onClick={() => handleTypeChange('income')}
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
          autoFocus
          value={amount}
          onChange={(event) => setAmount(event.target.value)}
          className="bg-background"
          placeholder="0"
        />

        <div className="grid grid-cols-2 gap-3">
          <Select
            label="Cuenta"
            required
            value={effectiveAccountId}
            onChange={(event) => setAccountId(event.target.value)}
            className="bg-background"
          >
            <option value="" disabled>
              Selecciona...
            </option>
            {accounts?.map((account) => (
              <option key={account.id} value={account.id}>
                {account.name} ({account.currency})
              </option>
            ))}
          </Select>
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
            {filteredCategories.map((category) => (
              <option key={category.id} value={category.id}>
                {category.name}
              </option>
            ))}
          </Select>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <Input
            label="Fecha"
            type="date"
            required
            value={date}
            onChange={(event) => setDate(event.target.value)}
            className="bg-background"
          />
          <Input
            label="Descripción"
            type="text"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            className="bg-background"
            placeholder="Opcional"
          />
        </div>

        <div className="flex gap-3 pt-2">
          <Button type="button" variant="ghost" onClick={onClose} className="flex-1">
            Cancelar
          </Button>
          <Button
            type="submit"
            variant="primary"
            loading={createMutation.isPending}
            className="flex-1"
          >
            Registrar
          </Button>
        </div>
      </form>
    </ModalShell>
  );
}
