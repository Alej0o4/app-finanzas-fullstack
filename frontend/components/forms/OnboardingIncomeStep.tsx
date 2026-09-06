'use client';

import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import Input from '@/components/ui/Input';
import Button from '@/components/ui/Button';
import { useSetMonthlyIncome } from '@/lib/hooks/useSetMonthlyIncome';
import { api } from '@/lib/api';
import { queryKeys } from '@/lib/queryKeys';
import { getApiError } from '@/lib/utils';
import type { Account, Category } from '@/types/api';

/** Categoría de sistema que siembra el ingreso declarado (ver seed_default_categories en
 * backend/app/main.py) — nunca la crea ni la borra el usuario. */
const SEED_INCOME_CATEGORY_NAME = 'Salario';

export default function OnboardingIncomeStep({ onDone }: { onDone: () => void }) {
  const [value, setValue] = useState('');
  const queryClient = useQueryClient();
  const setIncomeMutation = useSetMonthlyIncome();

  const { data: accounts } = useQuery<Account[]>({
    queryKey: queryKeys.accounts.all(),
    queryFn: async () => (await api.get('accounts/')).data,
  });
  const { data: categories } = useQuery<Category[]>({
    queryKey: queryKeys.categories.all(),
    queryFn: async () => (await api.get('categories/')).data,
  });

  // El ingreso declarado solo alimentaba `monthly_flow_balance` (Fase 11 §11.3) — la cuenta
  // nunca recibía la plata, así que arrancaba en $0 pese a que el usuario acababa de decir
  // cuánto gana. Sembrar una transacción real de ingreso resuelve eso con el mismo mecanismo
  // que ya usa el resto de la app (un ingreso ES una transacción), sin tocar el backend.
  // Best-effort a propósito: si falla, el ingreso declarado ya quedó guardado igual y el
  // onboarding sigue — no vale la pena bloquear los 3 minutos por esto.
  const seedIncomeMutation = useMutation({
    mutationFn: async (amount: number) => {
      const account = accounts?.find((a) => a.highlighted) ?? accounts?.[0];
      const category = categories?.find(
        (c) => c.user_id === null && c.type === 'income' && c.name === SEED_INCOME_CATEGORY_NAME
      );
      if (!account || !category) return null;

      return (
        await api.post(
          'transactions/',
          {
            description: 'Ingreso mensual declarado',
            amount,
            type: 'income',
            account_id: account.id,
            category_id: category.id,
          },
          { headers: { 'Idempotency-Key': crypto.randomUUID() } }
        )
      ).data;
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.accounts.all() }),
        queryClient.invalidateQueries({ queryKey: queryKeys.accounts.summary() }),
        queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.summary() }),
        queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.recentTransactions() }),
        queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.categoryBreakdown() }),
        queryClient.invalidateQueries({ queryKey: queryKeys.transactions.all() }),
        queryClient.invalidateQueries({ queryKey: ['analytics-cashflow'] }),
        queryClient.invalidateQueries({ queryKey: ['analytics-categories'] }),
      ]);
    },
  });

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    const parsed = Number(value);
    if (!value.trim() || Number.isNaN(parsed) || parsed < 0) return;

    await setIncomeMutation.mutateAsync(parsed);
    if (parsed > 0) {
      try {
        await seedIncomeMutation.mutateAsync(parsed);
      } catch (error) {
        toast.error(getApiError(error));
      }
    }
    onDone();
  };

  const isSubmitting = setIncomeMutation.isPending || seedIncomeMutation.isPending;

  return (
    <form onSubmit={handleSubmit} className="space-y-4" noValidate>
      <h1 className="text-text font-sans text-xl font-bold tracking-tight">
        ¿Cuál es tu ingreso mensual aproximado?
      </h1>
      <p className="text-text-muted text-sm">
        Lo usamos para mostrarte cuánto te queda cada mes. Puedes cambiarlo después.
      </p>
      <Input
        type="number"
        inputMode="decimal"
        autoFocus
        min={0}
        step="0.01"
        aria-label="Ingreso mensual aproximado"
        value={value}
        onChange={(event) => setValue(event.target.value)}
        className="bg-background"
        placeholder="Ej. 3000000"
      />
      <div className="flex gap-3 pt-2">
        <Button type="button" variant="ghost" onClick={onDone} className="flex-1">
          Omitir por ahora
        </Button>
        <Button type="submit" variant="primary" loading={isSubmitting} className="flex-1">
          Continuar
        </Button>
      </div>
    </form>
  );
}
