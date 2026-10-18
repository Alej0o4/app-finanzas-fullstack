'use client';

import { Plus } from 'lucide-react';
import Button from '@/components/ui/Button';
import QueryErrorState from '@/components/ui/QueryErrorState';
import { formatDay, money } from '@/components/recurring/recurringPresentation';
import { useRecurringSuggestions } from '@/lib/hooks/useRecurring';
import type { RecurringSuggestion } from '@/types/api';

interface RecurringSuggestionsSectionProps {
  onAccept: (suggestion: RecurringSuggestion) => void;
  /** Sin cuentas o categorías cargadas el formulario no puede abrirse. */
  disabled?: boolean;
}

/** Cargos anuales que el backend detectó en el historial (D15). Aceptar abre el formulario
 *  prellenado (D16); los descartes no se persisten, así que no hay botón de "descartar". */
export default function RecurringSuggestionsSection({
  onAccept,
  disabled,
}: RecurringSuggestionsSectionProps) {
  const { data: suggestions, isLoading, isError, refetch } = useRecurringSuggestions();

  // Sin sugerencias la sección no aporta nada: no se muestra (ni mientras carga).
  if (isLoading || (!isError && (!suggestions || suggestions.length === 0))) return null;

  return (
    <section aria-labelledby="recurring-suggestions-title" className="space-y-3">
      <h2 id="recurring-suggestions-title" className="text-text text-lg font-bold">
        Sugerencias
      </h2>
      {isError ? (
        <QueryErrorState
          message="No se pudieron cargar las sugerencias."
          onRetry={() => refetch()}
        />
      ) : (
        <>
          <p className="text-text-muted text-sm">
            Estos gastos se repitieron con un año de distancia. ¿Los agregas como recurrentes
            anuales?
          </p>
          <ul className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            {suggestions?.map((s) => (
              <li
                key={`${s.account_id}-${s.name}`}
                className="border-border bg-surface flex flex-wrap items-center justify-between gap-3 rounded-2xl border p-4"
              >
                <div className="min-w-0">
                  <p className="text-text truncate font-semibold">{s.name}</p>
                  <p className="text-text-muted text-xs">
                    Último cargo {formatDay(s.last_date)} · {money(s.amount, s.currency)} · próximo{' '}
                    {formatDay(s.suggested_start_date)}
                  </p>
                </div>
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={disabled}
                  onClick={() => onAccept(s)}
                  aria-label={`Agregar ${s.name} como recurrente anual`}
                >
                  <Plus size={14} aria-hidden="true" />
                  Agregar
                </Button>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
