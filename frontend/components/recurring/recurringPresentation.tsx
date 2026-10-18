import { capitalizeFirst, formatCurrency, formatDate } from '@/lib/utils';
import type { RecurringFrequency } from '@/types/api';

// Fase 37: solo presentación de campos que ya llegan calculados del backend.

export const FREQUENCY_LABELS: Record<RecurringFrequency, string> = {
  weekly: 'Semanal',
  monthly: 'Mensual',
  yearly: 'Anual',
};

/** Texto corto de la cadencia para junto al monto ("/ mes"). */
export const FREQUENCY_SUFFIX: Record<RecurringFrequency, string> = {
  weekly: 'por semana',
  monthly: 'por mes',
  yearly: 'por año',
};

/** Un día de calendario `YYYY-MM-DD` (zona del usuario) se pinta como día fijo: no se reinterpreta
 *  en otra zona (mediodía UTC + `timeZone: 'UTC'`, igual que `formatTargetDay` de sobres). */
export function formatDay(day: string): string {
  return formatDate(`${day}T12:00:00Z`, 'es-CO', 'UTC', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

/** `YYYY-MM` → "Octubre de 2026". */
export function formatMonthLabel(month: string): string {
  return capitalizeFirst(
    formatDate(`${month}-01T12:00:00Z`, 'es-CO', 'UTC', { month: 'long', year: 'numeric' })
  );
}

export function money(amount: number | string, currency: string | null): string {
  return formatCurrency(Number(amount), currency ?? 'COP');
}

export function Chip({
  children,
  tone = 'neutral',
}: {
  children: React.ReactNode;
  tone?: 'neutral' | 'primary' | 'danger' | 'success';
}) {
  const tones = {
    neutral: 'bg-surface-elevated text-text-muted border-border',
    primary: 'bg-primary/10 text-primary border-primary/30',
    danger: 'bg-danger/10 text-danger border-danger/30',
    success: 'bg-success/10 text-success border-success/30',
  };
  return (
    <span
      className={`inline-flex shrink-0 items-center rounded-full border px-2 py-0.5 text-xs font-medium ${tones[tone]}`}
    >
      {children}
    </span>
  );
}
