'use client';

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LabelList,
} from 'recharts';
import { formatCurrency } from '@/lib/utils';
import { Loader2 } from 'lucide-react';
import { useMemo } from 'react';
import ChartControlsPopover from '@/components/ChartControlsPopover';
import { useAppConfig } from '@/providers/AppConfigProvider';
import type { CashflowItem } from '@/types/api';

export type BarPeriod = '7d' | '30d' | '12m';
export type AnalyticsSeries = 'both' | 'income' | 'expense';

const PERIOD_OPTIONS: { value: BarPeriod; label: string }[] = [
  { value: '7d', label: '7 días' },
  { value: '30d', label: '30 días' },
  { value: '12m', label: '12 meses' },
];

const SERIES_OPTIONS: { value: AnalyticsSeries; label: string }[] = [
  { value: 'both', label: 'Ambos' },
  { value: 'income', label: 'Ingresos' },
  { value: 'expense', label: 'Gastos' },
];

const formatXAxisLabel = (label: string, period: 'day' | 'month') => {
  if (period === 'month') {
    const [year, month] = label.split('-');
    const parsedDate = new Date(Number(year), Number(month) - 1, 1);
    return new Intl.DateTimeFormat('es-ES', {
      month: 'short',
      year: 'numeric',
    }).format(parsedDate);
  }
  return label.split('-').pop() || label;
};

interface CashflowChartProps {
  data: CashflowItem[];
  isLoading: boolean;
  isError: boolean;
  barPeriod: BarPeriod;
  onBarPeriodChange: (period: BarPeriod) => void;
  seriesMode: AnalyticsSeries;
  onSeriesModeChange: (mode: AnalyticsSeries) => void;
  periodType: 'day' | 'month';
}

export default function CashflowChart({
  data,
  isLoading,
  isError,
  barPeriod,
  onBarPeriodChange,
  seriesMode,
  onSeriesModeChange,
  periodType,
}: CashflowChartProps) {
  const { config } = useAppConfig();
  const yAxisWidth = useMemo(() => {
    if (data.length === 0) return 84;
    const maxValue = Math.max(
      ...data.flatMap((item) => [Number(item.income), Number(item.expense)]),
      0
    );
    const labelLength = formatCurrency(maxValue, config.currency).length;
    return Math.min(Math.max(labelLength * 8 + 30, 84), 160);
  }, [data, config.currency]);

  return (
    <div className="bg-surface/80 border-border/70 rounded-2xl border p-6 shadow-sm backdrop-blur-sm">
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h2 className="text-text-soft text-lg font-medium">Flujo de Caja</h2>
        <div className="flex flex-wrap items-center gap-2">
          <div className="border-border/70 bg-background/40 flex items-center gap-1 rounded-lg border p-0.5">
            {PERIOD_OPTIONS.map((option) => (
              <button
                key={option.value}
                type="button"
                onClick={() => onBarPeriodChange(option.value)}
                className={`rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors ${
                  barPeriod === option.value
                    ? 'bg-primary text-background'
                    : 'text-text-muted hover:text-text'
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>
          <ChartControlsPopover>
            <div className="flex flex-col gap-1">
              <p className="text-text-muted px-2 py-1 text-xs font-medium">Serie</p>
              {SERIES_OPTIONS.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => {
                    onSeriesModeChange(option.value);
                  }}
                  className={`rounded-md px-2.5 py-1.5 text-left text-xs font-medium transition-colors ${
                    seriesMode === option.value
                      ? 'bg-surface text-text'
                      : 'text-text-muted hover:text-text hover:bg-surface/50'
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </ChartControlsPopover>
        </div>
      </div>
      {isError ? (
        <div className="border-border text-text-muted flex h-72 items-center justify-center rounded-xl border border-dashed text-sm">
          No se pudo cargar el flujo de caja.
        </div>
      ) : isLoading ? (
        <div className="flex h-72 items-center justify-center">
          <Loader2 className="text-info h-6 w-6 animate-spin" />
        </div>
      ) : (
        <div className="h-72 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ top: 24, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
              <XAxis
                dataKey="date_label"
                stroke="var(--color-text-muted)"
                fontSize={12}
                tickLine={false}
                axisLine={false}
                tickFormatter={(val) => formatXAxisLabel(String(val), periodType)}
              />
              <YAxis
                stroke="var(--color-text-muted)"
                fontSize={12}
                tickLine={false}
                axisLine={false}
                width={yAxisWidth}
                tickMargin={10}
                tickFormatter={(value) => formatCurrency(Number(value), config.currency)}
              />
              <Tooltip
                cursor={{ fill: 'var(--color-border)', opacity: 0.35 }}
                contentStyle={{
                  backgroundColor: 'var(--color-surface-elevated)',
                  borderColor: 'var(--color-border)',
                  borderRadius: '8px',
                  color: 'var(--color-text)',
                }}
                formatter={(value) => [formatCurrency(Number(value) || 0, config.currency), '']}
                labelFormatter={(label) => `Fecha: ${label}`}
              />
              {seriesMode !== 'expense' && (
                <Bar
                  dataKey="income"
                  name="Ingresos"
                  fill="var(--color-success)"
                  radius={[4, 4, 0, 0]}
                  maxBarSize={40}
                >
                  {periodType === 'month' && (
                    <LabelList
                      dataKey="income"
                      position="top"
                      formatter={(v) => formatCurrency(Number(v), config.currency)}
                      style={{ fill: 'var(--color-text-muted)', fontSize: 11 }}
                    />
                  )}
                </Bar>
              )}
              {seriesMode !== 'income' && (
                <Bar
                  dataKey="expense"
                  name="Gastos"
                  fill="var(--color-danger)"
                  radius={[4, 4, 0, 0]}
                  maxBarSize={40}
                >
                  {periodType === 'month' && (
                    <LabelList
                      dataKey="expense"
                      position="top"
                      formatter={(v) => formatCurrency(Number(v), config.currency)}
                      style={{ fill: 'var(--color-text-muted)', fontSize: 11 }}
                    />
                  )}
                </Bar>
              )}
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
