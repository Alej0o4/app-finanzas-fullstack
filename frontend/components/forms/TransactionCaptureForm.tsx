'use client';

import { useMemo, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ChevronDown } from 'lucide-react';
import { toast } from 'sonner';
import { api } from '@/lib/api';
import { queryKeys } from '@/lib/queryKeys';
import { getApiError } from '@/lib/utils';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import Select from '@/components/ui/Select';
import CategoryIcon from '@/components/ui/CategoryIcon';
import type { Account, Category, CreateTransactionPayload } from '@/types/api';

type PaymentMethod = 'cash' | 'card' | 'transfer';

interface TransactionCaptureFormProps {
  onSuccess: () => void;
  defaultType?: 'income' | 'expense';
  /** Opcional: notifica cambios de tipo (el modal lo usa para el título dinámico). */
  onTypeChange?: (type: 'income' | 'expense') => void;
}

const paymentMethodOptions: Array<{ value: PaymentMethod; label: string }> = [
  { value: 'cash', label: 'Efectivo' },
  { value: 'card', label: 'Tarjeta' },
  { value: 'transfer', label: 'Transferencia' },
];

export default function TransactionCaptureForm({
  onSuccess,
  defaultType = 'expense',
  onTypeChange,
}: TransactionCaptureFormProps) {
  const queryClient = useQueryClient();

  const [amount, setAmount] = useState('');
  const [type, setType] = useState<'income' | 'expense'>(defaultType);
  const [accountId, setAccountId] = useState('');
  const [categoryId, setCategoryId] = useState('');
  const [description, setDescription] = useState('');
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>('cash');
  const [idempotencyKey, setIdempotencyKey] = useState(() => crypto.randomUUID());

  const amountRef = useRef<HTMLInputElement>(null);
  const categoryFieldsetRef = useRef<HTMLFieldSetElement>(null);

  const { data: accounts } = useQuery<Account[]>({
    queryKey: queryKeys.accounts.all(),
    queryFn: async () => (await api.get('accounts/')).data,
  });

  const { data: categories } = useQuery<Category[]>({
    queryKey: queryKeys.categories.all(),
    queryFn: async () => (await api.get('categories/')).data,
  });

  const filteredCategories = useMemo(
    () => categories?.filter((c) => c.type === type) || [],
    [categories, type]
  );

  const effectiveAccountId = accountId || (accounts?.length ? String(accounts[0].id) : '');

  const createMutation = useMutation({
    mutationFn: async (newTx: CreateTransactionPayload) => {
      const response = await api.post('transactions/', newTx, {
        headers: { 'Idempotency-Key': idempotencyKey },
      });
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
        queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.categoryBreakdown() }),
        queryClient.invalidateQueries({ queryKey: queryKeys.accounts.summary() }),
      ]);

      toast.success(type === 'expense' ? 'Gasto registrado' : 'Ingreso registrado');

      setAmount('');
      setCategoryId('');
      setDescription('');
      setPaymentMethod('cash');
      setIdempotencyKey(crypto.randomUUID());
      onSuccess();
    },
    onError: (error: unknown) => {
      toast.error(getApiError(error));
    },
  });

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();

    if (!amount && !categoryId) {
      toast.error('Ingresa un monto y elige una categoría');
      amountRef.current?.focus();
      return;
    }
    if (!effectiveAccountId) {
      toast.error('No tienes una cuenta disponible');
      return;
    }
    if (!amount) {
      toast.error('Ingresa un monto');
      amountRef.current?.focus();
      return;
    }
    if (!categoryId) {
      toast.error('Elige una categoría');
      categoryFieldsetRef.current?.focus();
      return;
    }

    createMutation.mutate({
      description,
      amount: Number(amount),
      type,
      account_id: Number(effectiveAccountId),
      category_id: Number(categoryId),
      payment_method: paymentMethod,
    });
  };

  const handleTypeChange = (newType: 'income' | 'expense') => {
    setType(newType);
    setCategoryId('');
    onTypeChange?.(newType);
  };

  return (
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
              ? 'bg-primary/10 border-primary/20 text-primary'
              : 'text-text-muted hover:text-text border-transparent'
          }`}
        >
          Ingreso
        </button>
      </div>

      <Input
        ref={amountRef}
        label="Valor"
        type="number"
        inputMode="decimal"
        autoFocus
        value={amount}
        onChange={(event) => setAmount(event.target.value)}
        className="bg-background"
        placeholder="0"
      />

      {accounts && accounts.length > 1 && (
        <Select
          label="Cuenta"
          value={effectiveAccountId}
          onChange={(event) => setAccountId(event.target.value)}
          className="bg-background"
        >
          <option value="" disabled>
            Selecciona...
          </option>
          {accounts.map((account) => (
            <option key={account.id} value={account.id}>
              {account.name} ({account.currency})
            </option>
          ))}
        </Select>
      )}

      <fieldset ref={categoryFieldsetRef} tabIndex={-1}>
        <legend className="sr-only">Categoría</legend>
        <div className="grid grid-cols-4 gap-2">
          {filteredCategories.map((category) => (
            <label key={category.id} className="cursor-pointer">
              <input
                type="radio"
                name="category"
                value={category.id}
                checked={categoryId === String(category.id)}
                onChange={() => setCategoryId(String(category.id))}
                className="peer sr-only"
              />
              <div className="peer-checked:border-primary peer-checked:bg-primary/10 peer-focus-visible:ring-primary/50 border-border/70 flex flex-col items-center gap-1 rounded-xl border p-3 transition-colors peer-focus-visible:ring-2">
                <CategoryIcon icon={category.icon} size={22} />
                <span className="text-xs">{category.name}</span>
              </div>
            </label>
          ))}
        </div>
        {filteredCategories.length === 0 && (
          <p className="text-text-muted mt-2 text-sm">
            {categories ? 'No hay categorías para este tipo.' : 'Cargando categorías…'}
          </p>
        )}
      </fieldset>

      <details className="group">
        <summary className="text-text-muted hover:text-text flex cursor-pointer list-none items-center gap-1 text-sm font-medium transition-colors [&::-webkit-details-marker]:hidden">
          Más opciones
          <ChevronDown className="h-4 w-4 transition-transform group-open:rotate-180" />
        </summary>
        <div className="mt-4 space-y-4">
          <Input
            label="Descripción"
            type="text"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            className="bg-background"
            placeholder="Opcional"
          />
          <div>
            <span className="text-text-soft mb-1.5 block text-sm font-medium">Método de pago</span>
            <div className="flex gap-2">
              {paymentMethodOptions.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => setPaymentMethod(option.value)}
                  className={`flex-1 cursor-pointer rounded-xl border py-2 text-sm font-medium transition-colors ${
                    paymentMethod === option.value
                      ? 'bg-background border-border text-text'
                      : 'text-text-muted hover:text-text border-transparent'
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </details>

      <div className="flex gap-3 pt-2">
        <Button type="button" variant="ghost" onClick={onSuccess} className="flex-1">
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
  );
}
