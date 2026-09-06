'use client';

import { useState } from 'react';
import { toast } from 'sonner';
import Switch from '@/components/ui/Switch';
import Skeleton from '@/components/ui/Skeleton';
import { useUserPreferences } from '@/lib/hooks/useUserPreferences';
import { getApiError } from '@/lib/utils';

// Fase 14 §14.6.2: primera superficie de ajustes del producto — deliberadamente un
// solo control (el resumen semanal). No es el lugar para anticipar ajustes de cuenta
// (contraseña, email, etc.) que esta fase no pide.
export default function SettingsPage() {
  const { preferences, isLoading, error, updatePreferences } = useUserPreferences();

  // Valor del switch durante una mutación en vuelo: la query aún no lo confirma, así
  // que un "override" local deja que el switch responda al instante y se descarta
  // (revirtiendo a `preferences`) si el PATCH falla. Sin esto, el switch quedaría
  // desincronizado visualmente hasta la invalidación post-mutación.
  const [optimisticValue, setOptimisticValue] = useState<boolean | null>(null);

  // El default (true) coincide con el opt-out de la Decisión 14.1.1.
  const weeklySummaryEnabled = optimisticValue ?? preferences?.weekly_summary_enabled ?? true;

  const handleToggle = (checked: boolean) => {
    setOptimisticValue(checked);
    updatePreferences.mutate(
      { weekly_summary_enabled: checked },
      {
        onError: (err) => {
          // Revertir al valor confirmado por el servidor (el cache no se optimizó,
          // así que `preferences` sigue siendo el último valor confirmado).
          setOptimisticValue(null);
          toast.error(getApiError(err));
        },
      }
    );
  };

  if (isLoading) {
    return (
      <div className="relative space-y-6">
        <div>
          <h1 className="text-text font-sans text-xl font-bold sm:text-2xl">Ajustes</h1>
          <p className="text-text-muted text-xs sm:text-sm">Preferencias de tu cuenta.</p>
        </div>
        <Skeleton className="h-24 rounded-2xl" />
      </div>
    );
  }

  return (
    <div className="relative space-y-6">
      <div>
        <h1 className="text-text font-sans text-xl font-bold sm:text-2xl">Ajustes</h1>
        <p className="text-text-muted text-xs sm:text-sm">Preferencias de tu cuenta.</p>
      </div>

      {error ? (
        <div className="bg-surface border-border/70 rounded-2xl border p-4 sm:p-5">
          <p className="text-text-muted text-sm">
            No se pudieron cargar las preferencias. Intenta de nuevo más tarde.
          </p>
        </div>
      ) : (
        <section className="bg-surface border-border/70 rounded-2xl border p-4 sm:p-5">
          <Switch
            label="Resumen semanal"
            description="Recibe cada lunes un resumen de tus gastos de la semana"
            checked={weeklySummaryEnabled}
            onChange={(e) => handleToggle(e.target.checked)}
            disabled={updatePreferences.isPending}
          />
        </section>
      )}
    </div>
  );
}
