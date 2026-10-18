import { Chip } from '@/components/recurring/recurringPresentation';
import type { Cdt } from '@/types/api';

// Fase 38: solo presentación de campos que ya llegan calculados del backend.

/** "11,5 % E.A." (la tasa viene en puntos porcentuales). */
export function formatRate(rate: string | number): string {
  return `${Number(rate).toLocaleString('es-CO', { maximumFractionDigits: 4 })} % E.A.`;
}

/** Texto de los días al vencimiento. `days` viene del backend (negativo = ya venció). */
export function daysToMaturityLabel(days: number | null | undefined): string {
  if (days === null || days === undefined) return '';
  if (days === 0) return 'Vence hoy';
  if (days === 1) return 'Vence mañana';
  if (days > 1) return `Vence en ${days} días`;
  if (days === -1) return 'Venció ayer';
  return `Venció hace ${Math.abs(days)} días`;
}

/** Insignia de aviso; nada si el CDT está redimido o en orden. */
export function CdtAlertBadge({ cdt }: { cdt: Cdt }) {
  if (cdt.status !== 'active') return null;
  if (cdt.alert === 'matured') return <Chip tone="danger">Vencido: redímelo</Chip>;
  if (cdt.alert === 'due_soon') return <Chip tone="primary">Por vencer</Chip>;
  return null;
}
