import { formatDate } from '@/lib/utils';
import type { Fund, FundKind, FundPace } from '@/types/api';

export const KIND_LABELS: Record<FundKind, string> = {
  annual_expense: 'Gasto anual',
  emergency: 'Fondo de emergencia',
  goal: 'Meta',
};

const PACE_STYLES: Record<FundPace, { label: string; className: string }> = {
  completed: { label: 'Cumplido', className: 'bg-success/10 text-success border-success/30' },
  on_track: { label: 'Al día', className: 'bg-primary/10 text-primary border-primary/30' },
  behind: { label: 'Atrasado', className: 'bg-danger/10 text-danger border-danger/30' },
};

/** D10 (Fase 36): sobre activo, vaciado por gastos enlazados. Presentación de campos del backend
 *  (`balance`, `linked_expenses_count`). El backend no cambió `pace` ni `required_contribution`: la UI
 *  oculta el atraso y el aporte sugerido de un sobre pagado (chip, barra y `FundProgress`). */
export function isFundPaid(fund: Fund): boolean {
  return fund.status === 'active' && Number(fund.balance) === 0 && fund.linked_expenses_count > 0;
}

/** Chip de estado del sobre: "Pagado" (D10) o, si no, el ritmo. */
export function FundStatusChip({ fund }: { fund: Fund }) {
  if (isFundPaid(fund)) {
    return (
      <span className="bg-success/10 text-success border-success/30 inline-flex shrink-0 items-center rounded-full border px-2 py-0.5 text-xs font-medium">
        Pagado
      </span>
    );
  }
  return <PaceChip pace={fund.pace} />;
}

function PaceChip({ pace }: { pace: FundPace | null }) {
  if (!pace) return null;
  const { label, className } = PACE_STYLES[pace];
  return (
    <span
      className={`inline-flex shrink-0 items-center rounded-full border px-2 py-0.5 text-xs font-medium ${className}`}
    >
      {label}
    </span>
  );
}

/** `target_date` llega como día `YYYY-MM-DD` (zona del usuario): se pinta como día fijo, sin
 *  reinterpretarlo en otra zona. */
export function formatTargetDay(day: string): string {
  return formatDate(`${day}T12:00:00Z`, 'es-CO', 'UTC', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

export function monthsLabel(months: number): string {
  return months === 1 ? '1 mes' : `${months} meses`;
}

/** Texto del progreso y la meta, tal como los calculó el servidor. */
export function hasTarget(fund: Fund): boolean {
  return fund.target_amount !== null;
}
