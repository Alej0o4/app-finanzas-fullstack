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

export type AnalyticsSeries = 'both' | 'income' | 'expense';

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
  seriesMode: AnalyticsSeries;
  onSeriesModeChange: (mode: AnalyticsSeries) => void;
  periodType: 'day' | 'month';
  /** Fase 29 §F7 (H3): moneda de los montos del gráfico (ejes, tooltip y rótulos de las
   *  barras). Antes se usaba siempre la preferida, y con una cuenta USD el eje salía con
   *  formato COP. Si se omite, cae a la preferida global. */
  currency?: string;
}

export default function CashflowChart({
  data,
  isLoading,
  isError,
  seriesMode,
  onSeriesModeChange,
  periodType,
  currency,
}: CashflowChartProps) {
  const { config } = useAppConfig();
  const activeCurrency = currency ?? config.currency;
  const formatAmount = (amount: number) => formatCurrency(amount, activeCurrency);
  const yAxisWidth = useMemo(() => {
    if (data.length === 0) return 84;
    const maxValue = Math.max(
      ...data.flatMap((item) => [Number(item.income), Number(item.expense)]),
      0
    );
    // Se formatea acá y no con `formatAmount` a propósito: la función se recrea en cada render,
    // entonces meterla en las deps del useMemo lo dejaría sin memoizar.
    const labelLength = formatCurrency(maxValue, activeCurrency).length;
    return Math.min(Math.max(labelLength * 8 + 30, 84), 160);
  }, [data, activeCurrency]);

  return (
    <div className="bg-surface/80 border-border/70 shadow-background/20 rounded-2xl border p-6 shadow-sm backdrop-blur-sm">
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h2 className="text-text-soft text-lg font-medium">Flujo de Caja</h2>
        <div className="flex flex-wrap items-center gap-2 self-end sm:self-auto">
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
                tickFormatter={(value) => formatAmount(Number(value))}
              />
              <Tooltip
                cursor={{ fill: 'var(--color-border)', opacity: 0.35 }}
                contentStyle={{
                  backgroundColor: 'var(--color-surface-elevated)',
                  borderColor: 'var(--color-border)',
                  borderRadius: '8px',
                  color: 'var(--color-text)',
                }}
                formatter={(value) => [formatAmount(Number(value) || 0), '']}
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
                      formatter={(v) => formatAmount(Number(v))}
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
                      formatter={(v) => formatAmount(Number(v))}
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
