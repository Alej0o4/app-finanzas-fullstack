'use client';

import SummaryCard from '@/components/ui/SummaryCard';
import { formatCurrency } from '@/lib/utils';
import { useAppConfig } from '@/providers/AppConfigProvider';

interface AnalyticsSummaryProps {
  totalIncome: number;
  totalExpense: number;
}

export default function AnalyticsSummary({ totalIncome, totalExpense }: AnalyticsSummaryProps) {
  const { config } = useAppConfig();
  const total = totalIncome - totalExpense;

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
      <SummaryCard
        label="Ingresos"
        value={formatCurrency(totalIncome, config.currency)}
        trend="up"
        color="var(--color-success)"
      />
      <SummaryCard
        label="Gastos"
        value={formatCurrency(totalExpense, config.currency)}
        trend="down"
        color="var(--color-danger)"
      />
      <SummaryCard
        label="Balance Neto"
        value={formatCurrency(total, config.currency)}
        color={total >= 0 ? 'var(--color-success)' : 'var(--color-danger)'}
      />
    </div>
  );
}
