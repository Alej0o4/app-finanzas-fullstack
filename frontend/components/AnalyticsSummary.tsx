'use client';

import SummaryCard from '@/components/ui/SummaryCard';
import { formatCurrency } from '@/lib/utils';
import { useAppConfig } from '@/providers/AppConfigProvider';

interface AnalyticsSummaryProps {
  totalIncome: number;
  totalExpense: number;
  /** Fase 29 §F7 (H3): moneda en la que vienen los montos. Antes se formateaban siempre con la
   *  preferida, así que una cuenta USD se leía como COP. Si se omite, cae a la preferida global
   *  (mismo criterio que `CategoryBreakdownBars`). */
  currency?: string;
}

export default function AnalyticsSummary({
  totalIncome,
  totalExpense,
  currency,
}: AnalyticsSummaryProps) {
  const { config } = useAppConfig();
  const activeCurrency = currency ?? config.currency;
  const formatAmount = (amount: number) => formatCurrency(amount, activeCurrency);
  const total = totalIncome - totalExpense;

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
        value={formatAmount(total)}
        color={total >= 0 ? 'var(--color-success)' : 'var(--color-danger)'}
      />
    </div>
  );
}
