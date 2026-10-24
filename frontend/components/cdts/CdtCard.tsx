'use client';

import { CheckCircle2, Pencil, Trash2 } from 'lucide-react';
import Button from '@/components/ui/Button';
import { Chip, formatDay, money } from '@/components/recurring/recurringPresentation';
import { CdtAlertBadge, daysToMaturityLabel, formatRate } from '@/components/cdts/cdtPresentation';
import { useDeleteCdt } from '@/lib/hooks/useCdts';
import { useConfirmStore } from '@/store/useConfirmStore';
import type { Cdt } from '@/types/api';

interface CdtCardProps {
  cdt: Cdt;
  onEdit: (cdt: Cdt) => void;
  onRedeem: (cdt: Cdt) => void;
}

/** Tarjeta de un CDT, vigente o redimido. Interés, valores, días y alerta vienen del backend;
 *  la barra solo pinta `elapsed_days / term_days`. */
export default function CdtCard({ cdt, onEdit, onRedeem }: CdtCardProps) {
  const deleteMutation = useDeleteCdt(cdt.id);
  const isActive = cdt.status === 'active';
  const pct =
    cdt.term_days > 0 ? Math.min(Math.max((cdt.elapsed_days / cdt.term_days) * 100, 0), 100) : 0;
  const realized = Number(cdt.realized_interest ?? 0);
  const barTone = cdt.alert === 'matured' ? 'bg-danger' : 'bg-primary';

  const askDelete = () =>
    useConfirmStore
      .getState()
      .confirm(
        `¿Eliminar el CDT "${cdt.name}"? Si tiene transferencias vinculadas se revierten los saldos de sus cuentas; si no, no se mueve ningún saldo. Deja de aparecer aquí${cdt.status === 'active' ? ' y de sumar a tu patrimonio' : ''}.`,
        () => deleteMutation.mutate(),
        'Eliminar'
      );

  return (
    <li
      className={`border-border bg-surface rounded-2xl border p-4 ${isActive ? '' : 'opacity-80'}`}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className="text-text truncate font-semibold">{cdt.name}</h3>
          <p className="text-text-muted text-xs">
            {formatRate(cdt.rate_ea)} · {cdt.currency}
          </p>
        </div>
        <div className="flex flex-wrap items-center justify-end gap-1.5">
          <CdtAlertBadge cdt={cdt} />
          {!isActive && <Chip>Redimido</Chip>}
        </div>
      </div>

      <p className="text-text mt-3 text-lg font-bold tabular-nums">
        {money(cdt.current_value, cdt.currency)}
      </p>
      <p className="text-text-muted text-xs">
        {isActive ? 'Valor hoy (capital + rendimiento)' : 'Monto recibido al redimir'}
      </p>

      {isActive && (
        <div className="mt-3">
          <div
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.round(pct)}
            aria-label={`Plazo transcurrido de ${cdt.name}`}
            className="bg-surface-elevated h-2 w-full overflow-hidden rounded-full"
          >
            <div
              className={`h-full rounded-full transition-[width] ${barTone}`}
              style={{ width: `${pct}%` }}
            />
          </div>
          <p className="text-text-muted mt-1 text-xs">
            Día {cdt.elapsed_days} de {cdt.term_days} · {daysToMaturityLabel(cdt.days_to_maturity)}
          </p>
        </div>
      )}

      <dl className="text-text-muted mt-3 space-y-1 text-xs">
        <div className="flex justify-between gap-2">
          <dt>Capital</dt>
          <dd className="text-text tabular-nums">{money(cdt.principal, cdt.currency)}</dd>
        </div>
        {isActive ? (
          <>
            <div className="flex justify-between gap-2">
              <dt>Rendimiento a hoy</dt>
              <dd className="text-success tabular-nums">
                + {money(cdt.accrued_interest, cdt.currency)}
              </dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt>Valor al vencimiento</dt>
              <dd className="text-text tabular-nums">{money(cdt.maturity_value, cdt.currency)}</dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt>Vencimiento</dt>
              <dd className="text-text">{formatDay(cdt.maturity_on)}</dd>
            </div>
          </>
        ) : (
          <>
            <div className="flex justify-between gap-2">
              <dt>Rendimiento realizado</dt>
              <dd className={`tabular-nums ${realized < 0 ? 'text-danger' : 'text-success'}`}>
                {realized > 0 ? '+ ' : ''}
                {money(realized, cdt.currency)}
              </dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt>Redimido el</dt>
              <dd className="text-text">{cdt.redeemed_on ? formatDay(cdt.redeemed_on) : '—'}</dd>
            </div>
          </>
        )}
      </dl>

      <div className="mt-3 flex flex-wrap gap-2">
        {isActive && (
          <>
            <Button
              size="sm"
              variant="secondary"
              onClick={() => onRedeem(cdt)}
              disabled={deleteMutation.isPending}
            >
              <CheckCircle2 size={14} aria-hidden="true" />
              Redimir
            </Button>
            <Button size="sm" variant="ghost" onClick={() => onEdit(cdt)}>
              <Pencil size={14} aria-hidden="true" />
              Editar
            </Button>
          </>
        )}
        <Button
          size="sm"
          variant="ghost"
          onClick={askDelete}
          loading={deleteMutation.isPending}
          aria-label={`Eliminar el CDT ${cdt.name}`}
        >
          <Trash2 size={14} aria-hidden="true" />
          Eliminar
        </Button>
      </div>
    </li>
  );
}
