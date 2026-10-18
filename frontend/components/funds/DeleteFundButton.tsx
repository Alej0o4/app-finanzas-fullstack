'use client';

import { toast } from 'sonner';
import { Trash2 } from 'lucide-react';
import Button from '@/components/ui/Button';
import { useDeleteFund } from '@/lib/hooks/useFunds';
import { formatCurrency, getApiError } from '@/lib/utils';
import { useConfirmStore } from '@/store/useConfirmStore';
import type { Fund } from '@/types/api';

interface DeleteFundButtonProps {
  fund: Fund;
  /** `icon`: botón compacto de la tarjeta; `button`: botón con texto del detalle. */
  variant?: 'icon' | 'button';
  onDeleted?: () => void;
}

/** Eliminar un sobre (A1): pide confirmación diciendo cuánto se libera. El saldo vuelve al
 *  disponible porque el sobre deja de contar; las cuentas no se tocan. */
export default function DeleteFundButton({
  fund,
  variant = 'button',
  onDeleted,
}: DeleteFundButtonProps) {
  const deleteMutation = useDeleteFund(fund.id);
  const balance = Number(fund.balance);

  const askConfirmation = () => {
    const base =
      balance > 0
        ? `¿Eliminar el sobre "${fund.name}"? Se liberan ${formatCurrency(balance, fund.currency)} al disponible y se borra el historial del sobre.`
        : `¿Eliminar el sobre "${fund.name}"? Se borra el historial del sobre.`;
    // D12 (Fase 36): N y total vienen del backend; solo se ajusta el número gramatical.
    const n = fund.linked_expenses_count;
    const linkedNote =
      n > 0
        ? ` Este sobre tiene ${n} ${n === 1 ? 'gasto enlazado' : 'gastos enlazados'} (${formatCurrency(Number(fund.linked_expenses_total), fund.currency)}). Si lo borras, ${n === 1 ? 'queda' : 'quedan'} como gasto normal, sin marca de planeado. Si solo quieres cerrarlo, archívalo.`
        : '';
    const message = base + linkedNote;
    useConfirmStore.getState().confirm(
      message,
      () =>
        deleteMutation.mutate(undefined, {
          onSuccess: () => {
            toast.success('Sobre eliminado');
            onDeleted?.();
          },
          onError: (error) => toast.error(getApiError(error)),
        }),
      'Eliminar'
    );
  };

  if (variant === 'icon') {
    return (
      <button
        type="button"
        onClick={askConfirmation}
        disabled={deleteMutation.isPending}
        aria-label={`Eliminar el sobre ${fund.name}`}
        className="text-text-muted hover:text-danger focus-visible:ring-primary relative z-10 rounded-lg p-1.5 transition-colors focus-visible:ring-2 focus-visible:outline-none disabled:opacity-50"
      >
        <Trash2 size={16} aria-hidden="true" />
      </button>
    );
  }

  return (
    <Button variant="ghost" loading={deleteMutation.isPending} onClick={askConfirmation}>
      <Trash2 size={16} aria-hidden="true" />
      Eliminar
    </Button>
  );
}
