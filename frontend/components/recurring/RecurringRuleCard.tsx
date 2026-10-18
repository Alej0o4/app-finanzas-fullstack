'use client';

import { toast } from 'sonner';
import { Pause, Pencil, Play, Trash2 } from 'lucide-react';
import Button from '@/components/ui/Button';
import {
  Chip,
  FREQUENCY_LABELS,
  FREQUENCY_SUFFIX,
  formatDay,
  money,
} from '@/components/recurring/recurringPresentation';
import { useDeleteRecurring, useUpdateRecurring } from '@/lib/hooks/useRecurring';
import { getApiError } from '@/lib/utils';
import { useConfirmStore } from '@/store/useConfirmStore';
import type { RecurringRule } from '@/types/api';

interface RecurringRuleCardProps {
  rule: RecurringRule;
  onEdit: (rule: RecurringRule) => void;
}

/** Tarjeta de una regla. Costo mensualizado, `is_due` y los avisos de cuenta/categoría faltante
 *  vienen del backend; aquí solo se presentan. */
export default function RecurringRuleCard({ rule, onEdit }: RecurringRuleCardProps) {
  const updateMutation = useUpdateRecurring(rule.id);
  const deleteMutation = useDeleteRecurring(rule.id);
  const isPaused = rule.status === 'paused';
  const isIncome = rule.type === 'income';
  const broken = rule.account_missing || rule.category_missing;

  const toggleStatus = () =>
    updateMutation.mutate(
      { status: isPaused ? 'active' : 'paused' },
      {
        onSuccess: () => toast.success(isPaused ? 'Regla reanudada' : 'Regla pausada'),
        onError: (error) => toast.error(getApiError(error)),
      }
    );

  const askDelete = () =>
    useConfirmStore
      .getState()
      .confirm(
        `¿Eliminar la regla "${rule.name}"? Las transacciones que ya confirmaste no se tocan, pero dejará de proponer nuevas.`,
        () => deleteMutation.mutate(),
        'Eliminar'
      );

  return (
    <li
      className={`border-border bg-surface rounded-2xl border p-4 ${isPaused ? 'opacity-75' : ''}`}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className="text-text truncate font-semibold">{rule.name}</h3>
          <p className="text-text-muted text-xs">
            {FREQUENCY_LABELS[rule.frequency]} · {isIncome ? 'Ingreso' : 'Gasto'}
          </p>
        </div>
        <div className="flex flex-wrap items-center justify-end gap-1.5">
          {rule.is_annual && <Chip tone="primary">Anual</Chip>}
          {isPaused && <Chip>Pausada</Chip>}
          {rule.is_due && <Chip tone="danger">Por confirmar</Chip>}
        </div>
      </div>

      <p
        className={`mt-3 text-lg font-bold tabular-nums ${isIncome ? 'text-success' : 'text-text'}`}
      >
        {money(rule.amount, rule.currency)}{' '}
        <span className="text-text-muted text-xs font-normal">
          {FREQUENCY_SUFFIX[rule.frequency]}
        </span>
      </p>
      {rule.frequency !== 'monthly' && !isIncome && (
        <p className="text-text-muted text-xs">
          Equivale a {money(rule.monthly_equivalent, rule.currency)} al mes
        </p>
      )}
      <p className="text-text-muted mt-1 text-xs">
        {isPaused ? 'Pausada' : `Próxima: ${formatDay(rule.next_date)}`}
      </p>

      {broken && (
        <p role="alert" className="bg-danger/10 text-text mt-3 rounded-xl p-2.5 text-xs">
          {rule.account_missing && rule.category_missing
            ? 'La cuenta y la categoría de esta regla se borraron.'
            : rule.account_missing
              ? 'La cuenta de esta regla se borró.'
              : 'La categoría de esta regla se borró.'}{' '}
          No propone ni proyecta cargos hasta que la edites o la elimines.
        </p>
      )}

      <div className="mt-3 flex flex-wrap gap-2">
        <Button
          size="sm"
          variant="secondary"
          onClick={toggleStatus}
          loading={updateMutation.isPending}
          disabled={deleteMutation.isPending}
        >
          {isPaused ? (
            <Play size={14} aria-hidden="true" />
          ) : (
            <Pause size={14} aria-hidden="true" />
          )}
          {isPaused ? 'Reanudar' : 'Pausar'}
        </Button>
        <Button size="sm" variant="ghost" onClick={() => onEdit(rule)}>
          <Pencil size={14} aria-hidden="true" />
          Editar
        </Button>
        <Button
          size="sm"
          variant="ghost"
          onClick={askDelete}
          loading={deleteMutation.isPending}
          aria-label={`Eliminar la regla ${rule.name}`}
        >
          <Trash2 size={14} aria-hidden="true" />
          Eliminar
        </Button>
      </div>
    </li>
  );
}
