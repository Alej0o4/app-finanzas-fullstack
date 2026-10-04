'use client';

import SummaryCard from '@/components/ui/SummaryCard';
import { formatCurrency } from '@/lib/utils';
import { useAppConfig } from '@/providers/AppConfigProvider';

import QueryErrorState from '@/components/ui/QueryErrorState';

interface AnalyticsSummaryProps {
  totalIncome: number;
  totalExpense: number;
  /** Neto del período (ingresos - gastos), calculado por el backend (Fase 30 F3, H3).
   *  El frontend ya no resta; usa este valor directamente. */
  net: number;
  /** Fase 29 §F7 (H3): moneda en la que vienen los montos. Antes se formateaban siempre con la
   *  preferida, así que una cuenta USD se leía como COP. Si se omite, cae a la preferida global
   *  (mismo criterio que `CategoryBreakdownBars`). */
  currency?: string;
  isError?: boolean;
  onRetry?: () => void;
}

export default function AnalyticsSummary({
  totalIncome,
  totalExpense,
  net,
  currency,
  isError,
  onRetry,
}: AnalyticsSummaryProps) {
  const { config } = useAppConfig();
  const activeCurrency = currency ?? config.currency;
  const formatAmount = (amount: number) => formatCurrency(amount, activeCurrency);

  if (isError) {
    return (
      <QueryErrorState
        message="No se pudieron cargar los totales del período. Intenta de nuevo más tarde."
        onRetry={onRetry}
        className="col-span-full"
      />
    );
  }

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
      <SummaryCard
        label="Ingresos"
        value={formatAmount(totalIncome)}
        trend="up"
        color="var(--color-success)"
      />
      <SummaryCard
        label="Gastos"
        value={formatAmount(totalExpense)}
        trend="down"
        color="var(--color-danger)"
      />
      <SummaryCard
        label="Balance Neto"
        value={formatAmount(net)}
        color={net >= 0 ? 'var(--color-success)' : 'var(--color-danger)'}
      />
    </div>
  );
}
