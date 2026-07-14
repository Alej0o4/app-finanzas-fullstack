'use client';

import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';
import { formatCurrency } from '@/lib/utils';
import { Loader2 } from 'lucide-react';
import { useMemo } from 'react';
import ChartControlsPopover from '@/components/ChartControlsPopover';
import { useAppConfig } from '@/providers/AppConfigProvider';
import type { CategoryDistributionItem } from '@/types/api';

export type DonutPeriod = 'month' | '3months' | 'year';
export type CategoryType = 'expense' | 'income';

const PERIOD_OPTIONS: { value: DonutPeriod; label: string }[] = [
  { value: 'month', label: 'Este mes' },
  { value: '3months', label: '3 meses' },
  { value: 'year', label: 'Este año' },
];

const TYPE_OPTIONS: { value: CategoryType; label: string }[] = [
  { value: 'expense', label: 'Gastos' },
  { value: 'income', label: 'Ingresos' },
];

const CATEGORY_COLORS = [
  'var(--color-chart-1)',
  'var(--color-chart-2)',
  'var(--color-chart-3)',
  'var(--color-chart-4)',
  'var(--color-chart-5)',
  'var(--color-chart-6)',
  'var(--color-chart-7)',
  'var(--color-chart-8)',
  'var(--color-chart-9)',
  'var(--color-chart-10)',
  'var(--color-chart-1)',
  'var(--color-chart-2)',
];

const getCategoryColor = (index: number) => {
  return CATEGORY_COLORS[index % CATEGORY_COLORS.length];
};

interface CategoryDonutChartProps {
  data: CategoryDistributionItem[] | undefined;
  isFetching: boolean;
  isError: boolean;
  donutPeriod: DonutPeriod;
  onDonutPeriodChange: (period: DonutPeriod) => void;
  categoryType: CategoryType;
  onCategoryTypeChange: (type: CategoryType) => void;
  netMode: boolean;
  onNetModeChange: (net: boolean) => void;
  hiddenCategories: Set<string>;
  onHiddenCategoriesChange: (set: Set<string>) => void;
}

export default function CategoryDonutChart({
  data,
  isFetching,
  isError,
  donutPeriod,
  onDonutPeriodChange,
  categoryType,
  onCategoryTypeChange,
  netMode,
  onNetModeChange,
  hiddenCategories,
  onHiddenCategoriesChange,
}: CategoryDonutChartProps) {
  const { config } = useAppConfig();
  const originalCategoryData = useMemo(() => {
    const items =
      (data as CategoryDistributionItem[])?.map((item) => ({
        ...item,
        value: Number(item.total),
      })) || [];

    const totalAmount = items.reduce((sum, item) => sum + item.value, 0);

    return items.map((item) => ({
      ...item,
      percentage: totalAmount > 0 ? (item.value / totalAmount) * 100 : 0,
    }));
  }, [data]);

  const visibleCategoryData = useMemo(() => {
    const items = originalCategoryData.filter(
      (item) => !hiddenCategories.has(String(item.category_id))
    );

    const totalAmount = items.reduce((sum, item) => sum + item.value, 0);

    return items.map((item) => ({
      ...item,
      percentage: totalAmount > 0 ? (item.value / totalAmount) * 100 : 0,
    }));
  }, [originalCategoryData, hiddenCategories]);

  const visibleColorIndexMap = useMemo(() => {
    const map = new Map<string, number>();
    visibleCategoryData.forEach((item, i) => map.set(String(item.category_id), i));
    return map;
  }, [visibleCategoryData]);

  const toggleCategory = (id: string) => {
    const next = new Set(hiddenCategories);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    onHiddenCategoriesChange(next);
  };

  return (
    <div className="bg-surface/80 border-border/70 rounded-2xl border p-6 shadow-sm backdrop-blur-sm">
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h2 className="text-text-soft text-lg font-medium">
          {netMode ? 'Distribución Neta por Categoría' : 'Distribución por Categorías'}
        </h2>
        <div className="flex flex-wrap items-center gap-2">
          <div className="border-border/70 bg-background/40 flex items-center gap-1 rounded-lg border p-0.5">
            {PERIOD_OPTIONS.map((option) => (
              <button
                key={option.value}
                type="button"
                onClick={() => onDonutPeriodChange(option.value)}
                className={`rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors ${
                  donutPeriod === option.value
                    ? 'bg-primary text-background'
                    : 'text-text-muted hover:text-text'
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>
          <ChartControlsPopover>
            <div className="flex flex-col gap-3">
              <div className="flex flex-col gap-1">
                <p className="text-text-muted px-2 py-1 text-xs font-medium">Tipo</p>
                {TYPE_OPTIONS.map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => onCategoryTypeChange(option.value)}
                    className={`rounded-md px-2.5 py-1.5 text-left text-xs font-medium transition-colors ${
                      !netMode && categoryType === option.value
                        ? 'bg-surface text-text'
                        : 'text-text-muted hover:text-text hover:bg-surface/50'
                    } ${netMode ? 'pointer-events-none opacity-40' : ''}`}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
              <div className="border-border/50 my-1 border-t" />
              <div className="flex flex-col gap-1">
                <p className="text-text-muted px-2 py-1 text-xs font-medium">Modo</p>
                {(
                  [
                    { value: false, label: 'Bruto' },
                    { value: true, label: 'Neto' },
                  ] as const
                ).map((option) => (
                  <button
                    key={String(option.value)}
                    type="button"
                    onClick={() => {
                      onNetModeChange(option.value);
                      if (!option.value) onHiddenCategoriesChange(new Set());
                    }}
                    className={`rounded-md px-2.5 py-1.5 text-left text-xs font-medium transition-colors ${
                      netMode === option.value
                        ? 'bg-surface text-text'
                        : 'text-text-muted hover:text-text hover:bg-surface/50'
                    }`}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </div>
          </ChartControlsPopover>
        </div>
      </div>
      {isError ? (
        <div className="border-border text-text-muted flex h-72 items-center justify-center rounded-xl border border-dashed text-sm">
          No se pudieron cargar las categorías.
        </div>
      ) : isFetching && originalCategoryData.length === 0 ? (
        <div className="flex h-72 items-center justify-center">
          <Loader2 className="text-info h-6 w-6 animate-spin" />
        </div>
      ) : (
        <>
          <div className="h-72 w-full">
            {visibleCategoryData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={visibleCategoryData}
                    cx="50%"
                    cy="50%"
                    innerRadius={80}
                    outerRadius={110}
                    paddingAngle={2}
                    dataKey="value"
                    stroke="none"
                  >
                    {visibleCategoryData.map((_entry, index: number) => (
                      <Cell key={`cell-${index}`} fill={getCategoryColor(index)} />
                    ))}
                  </Pie>
                  <Tooltip
                    content={({ active, payload }) => {
                      const item = payload?.[0]?.payload;
                      if (!active || !item) return null;
                      return (
                        <div className="border-border bg-surface-elevated rounded-lg border px-3 py-2 text-sm shadow-lg">
                          <p className="text-text font-medium">{item.category_name}</p>
                          <p className="text-text-soft mt-1">
                            {netMode ? 'Gasto neto:' : 'Total:'}{' '}
                            {formatCurrency(Number(item.value), config.currency)}
                          </p>
                          <p className="text-text-muted">
                            {item.percentage.toFixed(1)}% del subtotal
                          </p>
                        </div>
                      );
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="border-border text-text-muted flex h-72 items-center justify-center rounded-xl border border-dashed text-sm">
                No hay datos para este período.
              </div>
            )}
          </div>
          {originalCategoryData.length > 0 && (
            <div className="mt-5 space-y-2">
              {originalCategoryData.map((item, index: number) => {
                const isHidden = hiddenCategories.has(String(item.category_id));
                const visibleItem = visibleCategoryData.find(
                  (d) => String(d.category_id) === String(item.category_id)
                );
                const displayPercentage = visibleItem ? visibleItem.percentage : item.percentage;
                const colorIndex = visibleColorIndexMap.get(String(item.category_id)) ?? index;
                return (
                  <div
                    key={`${item.category_id ?? index}-legend`}
                    className={`flex cursor-pointer items-center justify-between gap-3 text-sm transition-opacity hover:opacity-80 ${isHidden ? 'opacity-30' : ''}`}
                    onClick={() => toggleCategory(String(item.category_id))}
                  >
                    <div className="flex min-w-0 items-center gap-2">
                      <span
                        className="h-2.5 w-2.5 shrink-0 rounded-full"
                        style={{ backgroundColor: getCategoryColor(colorIndex) }}
                      />
                      <span
                        className={`truncate ${isHidden ? 'text-text-muted line-through' : 'text-text-soft'}`}
                      >
                        {item.category_name}
                        {!isHidden && (
                          <span className="text-text-muted">
                            {' '}
                            ({displayPercentage.toFixed(1)}%)
                          </span>
                        )}
                      </span>
                    </div>
                    <span className="text-text-muted shrink-0">
                      {formatCurrency(Number(item.value), config.currency)}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}
    </div>
  );
}
