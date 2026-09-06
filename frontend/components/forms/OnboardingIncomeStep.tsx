'use client';

import { useState } from 'react';
import Input from '@/components/ui/Input';
import Button from '@/components/ui/Button';
import { useSetMonthlyIncome } from '@/lib/hooks/useSetMonthlyIncome';

export default function OnboardingIncomeStep({ onDone }: { onDone: () => void }) {
  const [value, setValue] = useState('');
  const mutation = useSetMonthlyIncome();

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    const parsed = Number(value);
    if (!value.trim() || Number.isNaN(parsed) || parsed < 0) return;
    mutation.mutate(parsed, { onSuccess: onDone });
  };

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
        <Button type="submit" variant="primary" loading={mutation.isPending} className="flex-1">
          Continuar
        </Button>
      </div>
    </form>
  );
}
