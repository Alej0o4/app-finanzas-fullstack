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
import { BarChart3, Loader2 } from 'lucide-react';
import EmptyState from '@/components/ui/EmptyState';
import QueryErrorState from '@/components/ui/QueryErrorState';
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
  /** QA-040 (Fase 33): "Reintentar" vuelve a pedir solo el flujo, no toda la pantalla. */
  onRetry?: () => void;
}

export default function CashflowChart({
  data,
  isLoading,
  isError,
  seriesMode,
  onSeriesModeChange,
  periodType,
  currency,
  onRetry,
}: CashflowChartProps) {
  const { config } = useAppConfig();
  const activeCurrency = currency ?? config.currency;
  const formatAmount = (amount: number) => formatCurrency(amount, activeCurrency);
  // Fase 31 F7 (Q8, QA-007): el eje Y, su cálculo de ancho y las etiquetas sobre las
  // barras siguen compactos (sin decimales) aunque `formatCurrency` ya no redondee todo a
  // la unidad por defecto — el tooltip (`formatAmount`) sigue mostrando decimales.
  const formatAmountInteger = (amount: number) =>
    formatCurrency(amount, activeCurrency, undefined, { integer: true });
  const yAxisWidth = useMemo(() => {
    if (data.length === 0) return 84;
    const maxValue = Math.max(
      ...data.flatMap((item) => [Number(item.income), Number(item.expense)]),
      0
    );
    // Se formatea acá y no con `formatAmountInteger` a propósito: la función se recrea en
    // cada render, entonces meterla en las deps del useMemo lo dejaría sin memoizar.
    const labelLength = formatCurrency(maxValue, activeCurrency, undefined, {
      integer: true,
    }).length;
    return Math.min(Math.max(labelLength * 8 + 30, 84), 160);
  }, [data, activeCurrency]);

  // QA-018b: sin movimientos en el período el gráfico quedaba como un eje vacío sin
  // explicación. Se distingue de "cargando" y de "error" con un estado vacío propio.
  const isEmpty = data.every((item) => Number(item.income) === 0 && Number(item.expense) === 0);

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
        <div className="border-border flex h-72 items-center justify-center rounded-xl border border-dashed">
          <QueryErrorState message="No se pudo cargar el flujo de caja." onRetry={onRetry} />
        </div>
      ) : isLoading ? (
        <div className="flex h-72 items-center justify-center">
          <Loader2 className="text-info h-6 w-6 animate-spin" />
        </div>
      ) : isEmpty ? (
        <div className="border-border flex h-72 items-center justify-center rounded-xl border border-dashed">
          <EmptyState
            icon={<BarChart3 size={28} />}
            message="Sin movimientos en este período"
            description="Cuando registres ingresos o gastos, aparecerán aquí."
          />
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
                tickFormatter={(value) => formatAmountInteger(Number(value))}
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
                      formatter={(v) => formatAmountInteger(Number(v))}
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
                      formatter={(v) => formatAmountInteger(Number(v))}
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
