'use client';

import { useState } from 'react';
import { Check, SkipForward } from 'lucide-react';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import QueryErrorState from '@/components/ui/QueryErrorState';
import Skeleton from '@/components/ui/Skeleton';
import {
  Chip,
  FREQUENCY_LABELS,
  formatDay,
  money,
} from '@/components/recurring/recurringPresentation';
import {
  useConfirmRecurring,
  usePendingRecurring,
  useSkipRecurring,
} from '@/lib/hooks/useRecurring';
import { useConfirmStore } from '@/store/useConfirmStore';
import { validateAmountText } from '@/lib/validateAmount';
import type { PendingOccurrence } from '@/types/api';

/** Una ocurrencia vencida. Solo la `is_next` de cada regla se puede resolver (el backend exige
 *  resolver en orden); las demás se muestran deshabilitadas con el motivo a la vista. */
function PendingRow({ item }: { item: PendingOccurrence }) {
  const confirmMutation = useConfirmRecurring();
  const skipMutation = useSkipRecurring();
  const [editing, setEditing] = useState(false);
  const [amountText, setAmountText] = useState(String(Number(item.amount)));
  const [amountError, setAmountError] = useState<string>();
  const busy = confirmMutation.isPending || skipMutation.isPending;

  const confirm = () => {
    let amount: number | undefined;
    if (editing) {
      const error = validateAmountText(amountText);
      setAmountError(error ?? undefined);
      if (error) return;
      // Solo se manda si cambió; si no, el backend usa el de la regla.
      if (Number(amountText) !== Number(item.amount)) amount = Number(amountText);
    }
    confirmMutation.mutate({ ruleId: item.rule_id, occurrenceDate: item.occurrence_date, amount });
  };

  const skip = () =>
    useConfirmStore
      .getState()
      .confirm(
        `¿Saltar "${item.name}" del ${formatDay(item.occurrence_date)}? No se registra ninguna transacción y esta ocurrencia no se puede recuperar.`,
        () => skipMutation.mutate({ ruleId: item.rule_id, occurrenceDate: item.occurrence_date }),
        'Saltar'
      );

  return (
    <li className="border-border bg-surface rounded-2xl border p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-text truncate font-semibold">{item.name}</p>
          <p className="text-text-muted text-xs">
            {formatDay(item.occurrence_date)} · {FREQUENCY_LABELS[item.frequency]}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Chip tone={item.type === 'income' ? 'success' : 'neutral'}>
            {item.type === 'income' ? 'Ingreso' : 'Gasto'}
          </Chip>
          <span
            className={`font-semibold tabular-nums ${item.type === 'income' ? 'text-success' : 'text-text'}`}
          >
            {money(item.amount, item.currency)}
          </span>
        </div>
      </div>

      {item.is_next ? (
        <div className="mt-3 space-y-3">
          {editing && (
            <Input
              label={`Monto real (${item.currency})`}
              type="number"
              inputMode="decimal"
              min={0}
              step="0.01"
              value={amountText}
              onChange={(e) => setAmountText(e.target.value)}
              error={amountError}
              className="bg-background"
            />
          )}
          <div className="flex flex-wrap gap-2">
            <Button size="sm" onClick={confirm} loading={confirmMutation.isPending} disabled={busy}>
              <Check size={14} aria-hidden="true" />
              Confirmar
            </Button>
            <Button
              size="sm"
              variant="secondary"
              disabled={busy}
              onClick={() => {
                setEditing((v) => !v);
                setAmountError(undefined);
                setAmountText(String(Number(item.amount)));
              }}
            >
              {editing ? 'Usar monto de la regla' : 'Editar monto'}
            </Button>
            <Button size="sm" variant="ghost" onClick={skip} disabled={busy}>
              <SkipForward size={14} aria-hidden="true" />
              Saltar
            </Button>
          </div>
        </div>
      ) : (
        <p className="text-text-muted mt-3 text-xs">
          Resuelve primero la ocurrencia anterior de esta regla.
        </p>
      )}
    </li>
  );
}

/** Bloque "Por confirmar": las ocurrencias vencidas que calcula el backend. Sin pendientes no
 *  ocupa lugar (el estado vacío se comunica en una línea). */
export default function PendingRecurringSection() {
  const { data: pending, isLoading, isError, refetch } = usePendingRecurring();

  return (
    <section aria-labelledby="recurring-pending-title" className="space-y-3">
      <h2 id="recurring-pending-title" className="text-text text-lg font-bold">
        Por confirmar
      </h2>
      {isLoading ? (
        <Skeleton className="h-28" />
      ) : isError ? (
        <QueryErrorState
          message="No se pudieron cargar los recurrentes por confirmar."
          onRetry={() => refetch()}
        />
      ) : !pending || pending.length === 0 ? (
        <p className="text-text-muted text-sm">No tienes recurrentes por confirmar.</p>
      ) : (
        <ul className="grid grid-cols-1 gap-3 lg:grid-cols-2">
          {pending.map((item) => (
            // El monto va en la clave: si la regla cambia de monto, la fila se remonta y el borrador
            // de "Editar monto" no manda un override obsoleto.
            <PendingRow
              key={`${item.rule_id}-${item.occurrence_date}-${item.amount}`}
              item={item}
            />
          ))}
        </ul>
      )}
    </section>
  );
}
