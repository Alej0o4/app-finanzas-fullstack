import { AlertTriangle } from 'lucide-react';
import { formatCurrency } from '@/lib/utils';
import { formatTargetDay, hasTarget, monthsLabel } from '@/components/funds/fundPresentation';
import type { Fund } from '@/types/api';

/** Barra de progreso + saldo/meta + aporte sugerido + runway + alerta de respaldo. Compartido
 *  por la tarjeta de la lista y el detalle; todo viene calculado por el servidor. */
export default function FundProgress({ fund }: { fund: Fund }) {
  const balance = Number(fund.balance);
  const pct = fund.progress_pct === null ? null : Math.min(Math.max(fund.progress_pct, 0), 100);
  const shortfall = Number(fund.backing_shortfall);
  const isEmergency = fund.kind === 'emergency';

  return (
    <div className="space-y-3">
      {pct !== null && (
        <div
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={Math.round(pct)}
          aria-label="Progreso del sobre"
          className="bg-surface-elevated h-2 w-full overflow-hidden rounded-full"
        >
          <div
            className={`h-full rounded-full transition-[width] ${fund.pace === 'behind' ? 'bg-danger' : 'bg-primary'}`}
            style={{ width: `${pct}%` }}
          />
        </div>
      )}

      <p className="text-text text-sm tabular-nums">
        <span className="font-semibold">{formatCurrency(balance, fund.currency)}</span>
        {hasTarget(fund) && (
          <span className="text-text-muted">
            {' '}
            de {formatCurrency(Number(fund.target_amount), fund.currency)}
            {pct !== null && ` · ${Math.round(pct)}%`}
          </span>
        )}
      </p>

      {isEmergency && !hasTarget(fund) && (
        <p className="text-text-muted text-xs">
          Aún no hay historial completo de gastos para calcular tu meta
          {fund.target_months ? ` de ${monthsLabel(fund.target_months)}` : ''}.
        </p>
      )}

      {isEmergency && fund.runway_months !== null && (
        <p className="text-text-muted text-xs">
          Cubre aproximadamente{' '}
          <span className="text-text font-medium">
            {Number(fund.runway_months).toLocaleString('es-CO', { maximumFractionDigits: 1 })} meses
          </span>{' '}
          de tus gastos.
        </p>
      )}

      {fund.target_date && (
        <p className="text-text-muted text-xs">
          Fecha objetivo: {formatTargetDay(fund.target_date)}
        </p>
      )}

      {fund.required_contribution !== null && Number(fund.required_contribution) > 0 && (
        <p className="text-text-muted text-xs">
          Aporta{' '}
          <span className="text-text font-medium tabular-nums">
            {formatCurrency(Number(fund.required_contribution), fund.currency)}
          </span>{' '}
          este mes
          {fund.months_remaining !== null && fund.months_remaining > 0
            ? ` (te quedan ${monthsLabel(fund.months_remaining)})`
            : ''}
          .
        </p>
      )}

      {shortfall > 0 && (
        <p
          role="status"
          className="bg-danger/10 text-danger border-danger/30 flex items-start gap-2 rounded-xl border p-2.5 text-xs"
        >
          <AlertTriangle size={14} className="mt-0.5 shrink-0" aria-hidden="true" />
          <span>
            Sobre sin respaldo: en tu cuenta faltan{' '}
            <span className="font-semibold tabular-nums">
              {formatCurrency(shortfall, fund.currency)}
            </span>{' '}
            para cubrir lo que apartaste.
          </span>
        </p>
      )}
    </div>
  );
}
