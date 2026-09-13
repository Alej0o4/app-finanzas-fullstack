'use client';

import { useState } from 'react';
import { toast } from 'sonner';
import Select from '@/components/ui/Select';
import Button from '@/components/ui/Button';
import { useUserPreferences } from '@/lib/hooks/useUserPreferences';
import { getApiError } from '@/lib/utils';

// Fase 22 §22.1 (Hallazgo 3, ajustado en revisión pre-merge del 2026-09-13): la lista
// original de la spec tenía 5 monedas (+ MXN/ARS), pero el resto de la app hoy solo
// soporta 3 — `accounts/page.tsx` no ofrece MXN/ARS al crear una cuenta y no tiene
// ningún campo de moneda al editar una (`AccountUpdate.currency` existe en el schema
// pero `accounts.py` lo ignora silenciosamente, ver TODO en `docs/ROADMAP.md`). Elegir
// MXN/ARS acá dejaría al usuario sin ninguna forma de crear una segunda cuenta en esa
// moneda ni de corregir a mano una cascada que el guard de `preferences.py` saltee.
// Acotada a las 3 que el resto de la app ya soporta de punta a punta; ampliar cuando se
// resuelva ese TODO.
const CURRENCY_OPTIONS = ['COP', 'USD', 'EUR'] as const;

export default function OnboardingCurrencyStep({
  onDone,
}: {
  // Decisión A6 — el padre recibe el valor elegido y lo pasa por prop al paso siguiente;
  // no se lee de la cache de React Query (invalidateQueries es asíncrono).
  onDone: (currency: string) => void;
}) {
  const [currency, setCurrency] = useState<string>('COP');
  const { updatePreferences } = useUserPreferences();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await updatePreferences.mutateAsync({
        preferred_currency: currency,
        // Única diferencia con el uso de Settings (Fase 21): pide la cascada a la cuenta
        // por defecto en el mismo PATCH (Decisiones A2/A5, mismo commit del handler).
        apply_to_default_account: true,
      });
      onDone(currency);
    } catch (error) {
      // Sin esto el usuario quedaba varado en el paso sin ninguna señal (encontrado en
      // revisión pre-merge): el spinner se apaga, pero nada avisa que no se guardó nada.
      toast.error(getApiError(error));
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4" noValidate>
      <h1 className="text-text font-sans text-xl font-bold tracking-tight">
        ¿En qué moneda manejás tus finanzas?
      </h1>
      <p className="text-text-muted text-sm">Podés cambiarla después desde Configuración.</p>
      <Select
        label="Moneda principal"
        value={currency}
        onChange={(e) => setCurrency(e.target.value)}
        className="bg-background"
      >
        {CURRENCY_OPTIONS.map((c) => (
          <option key={c} value={c}>
            {c}
          </option>
        ))}
      </Select>
      <div className="flex gap-3 pt-2">
        {/* Sin PATCH: `preferred_currency` ya defaultea a "COP" server-side (Decisión 22.1.3)
            — omitir es literalmente no escribir nada, mismo criterio que el omitir de
            OnboardingIncomeStep. */}
        <Button type="button" variant="ghost" onClick={() => onDone('COP')} className="flex-1">
          Omitir por ahora
        </Button>
        <Button
          type="submit"
          variant="primary"
          loading={updatePreferences.isPending}
          className="flex-1"
        >
          Continuar
        </Button>
      </div>
    </form>
  );
}
