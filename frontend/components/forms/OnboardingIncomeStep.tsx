'use client';

import { useRef, useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import Input from '@/components/ui/Input';
import Button from '@/components/ui/Button';
import { useSetMonthlyIncome } from '@/lib/hooks/useSetMonthlyIncome';
import { useAccounts } from '@/lib/hooks/useAccounts';
import { useCategories } from '@/lib/hooks/useCategories';
import { api } from '@/lib/api';
import { queryKeys } from '@/lib/queryKeys';
import { getApiError } from '@/lib/utils';
import { validateAmountText } from '@/lib/validateAmount';

/** Categoría de sistema que siembra el ingreso declarado (ver seed_default_categories en
 * backend/app/main.py) — nunca la crea ni la borra el usuario. */
const SEED_INCOME_CATEGORY_NAME = 'Salario';

// Fase 22 §22.1 (Decisión A3): solo placeholders de UI a una escala razonable por moneda —
// sin tasas de cambio, no son cálculos.
const PLACEHOLDER_BY_CURRENCY: Record<string, string> = {
  COP: 'Ej. 3000000',
  USD: 'Ej. 3000',
  EUR: 'Ej. 2800',
  MXN: 'Ej. 50000',
  ARS: 'Ej. 900000',
};

export default function OnboardingIncomeStep({
  currency,
  onDone,
}: {
  // Fase 22 §22.1 (Decisión A6): la moneda ya elegida en el paso anterior (o la preferida
  // del usuario) — llega por prop desde el wizard, no se lee de cache react-query.
  currency: string;
  onDone: () => void;
}) {
  const [value, setValue] = useState('');
  // Fase 31 F2 (Q6, QA-013): error de campo visible — antes un ingreso vacío o negativo
  // hacía un `return` silencioso y "Continuar" parecía roto.
  const [amountError, setAmountError] = useState<string | null>(null);
  const amountRef = useRef<HTMLInputElement>(null);
  const queryClient = useQueryClient();
  const setIncomeMutation = useSetMonthlyIncome();

  const { data: accounts } = useAccounts();
  const { data: categories } = useCategories();

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
        queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.categoryBreakdown() }),
        queryClient.invalidateQueries({ queryKey: queryKeys.transactions.all() }),
        queryClient.invalidateQueries({ queryKey: ['analytics-cashflow'] }),
        queryClient.invalidateQueries({ queryKey: ['analytics-categories'] }),
      ]);
    },
  });

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();

    const error = validateAmountText(value, { allowZero: true });
    setAmountError(error);
    if (error) {
      amountRef.current?.focus();
      return;
    }

    const parsed = Number(value);

    // Fase 31 F2 (QA-013): el `mutateAsync` se envuelve — si el servidor rechaza el
    // ingreso (ej. un 422 de B3, fuera del rango de `Numeric(14,2)`), se muestra y el paso
    // NO avanza. Antes el error quedaba como una promesa rechazada sin capturar: ni toast
    // ni bloqueo del `onDone()` siguiente.
    try {
      await setIncomeMutation.mutateAsync(parsed);
    } catch (mutationError) {
      toast.error(getApiError(mutationError));
      return;
    }

    if (parsed > 0) {
      try {
        await seedIncomeMutation.mutateAsync(parsed);
      } catch (mutationError) {
        toast.error(getApiError(mutationError));
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
      {/* Fase 31 F8 (Q14, H3): ya no promete un cálculo ("cuánto te queda") — el ingreso
          declarado es una referencia visual junto a los ingresos reales del mes, nunca se
          resta ni se compara. */}
      <p className="text-text-muted text-sm">
        Es solo una referencia que se muestra junto a los ingresos del mes. Puedes cambiarlo
        después.
      </p>
      <Input
        ref={amountRef}
        type="number"
        inputMode="decimal"
        autoFocus
        min={0}
        step="0.01"
        aria-label="Ingreso mensual aproximado"
        value={value}
        onChange={(event) => setValue(event.target.value)}
        error={amountError ?? undefined}
        className="bg-background"
        placeholder={PLACEHOLDER_BY_CURRENCY[currency] ?? 'Ej. 3000000'}
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
