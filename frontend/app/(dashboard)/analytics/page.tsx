"use client";

import { useQuery } from "@tanstack/react-query";
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LabelList,
  PieChart, Pie, Cell
} from "recharts";
import { formatCurrency } from "@/lib/utils";
import { api } from "@/lib/api";
import { Loader2 } from "lucide-react";
import { useState, useMemo } from "react";

type BarPeriod = "7d" | "30d" | "12m";
type DonutPeriod = "month" | "3months" | "year";
type AnalyticsSeries = "both" | "income" | "expense";
type CategoryType = "expense" | "income";

interface CashflowItem {
  date_label: string;
  expense: number;
  income: number;
}

interface CategoryDistributionItem {
  category_id: number;
  category_name: string;
  total: number;
  percentage?: number;
}

// Función auxiliar para formatear fechas en hora local al estándar requerido por el backend
const formatISOForBackend = (date: Date) => {
  const pad = (value: number) => String(value).padStart(2, "0");

  return [
    date.getFullYear(),
    pad(date.getMonth() + 1),
    pad(date.getDate())
  ].join("-") + `T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
};

const CATEGORY_COLORS = [
  "#38bdf8",
  "#0ea5e9",
  "#2563eb",
  "#4f46e5",
  "#7c3aed",
  "#db2777",
  "#10b981",
  "#14b8a6",
  "#f97316",
  "#8b5cf6",
  "#22c55e",
  "#06b6d4",
];

const buildBarDateRange = (period: BarPeriod) => {
  const now = new Date();
  const start = new Date(now);

  if (period === "7d") start.setDate(now.getDate() - 7);
  else if (period === "30d") start.setDate(now.getDate() - 30);
  else start.setFullYear(now.getFullYear() - 1);

  return {
    start_date: formatISOForBackend(start),
    end_date: formatISOForBackend(now),
    period: period === "12m" ? "month" as const : "day" as const,
  };
};

const buildDonutDateRange = (period: DonutPeriod) => {
  const now = new Date();

  if (period === "3months") {
    const start = new Date(now);
    start.setMonth(now.getMonth() - 3);
    return {
      start_date: formatISOForBackend(start),
      end_date: formatISOForBackend(now),
    };
  }

  if (period === "year") {
    return {
      start_date: formatISOForBackend(new Date(now.getFullYear(), 0, 1)),
      end_date: formatISOForBackend(now),
    };
  }

  return {
    start_date: formatISOForBackend(new Date(now.getFullYear(), now.getMonth(), 1)),
    end_date: formatISOForBackend(now),
  };
};

const getCategoryColor = (item: { category_id?: number }, index: number) => {
  const seed = Number(item.category_id ?? index);

  return CATEGORY_COLORS[Math.abs(seed) % CATEGORY_COLORS.length];
};

const formatXAxisLabel = (label: string, period: "day" | "month") => {
  if (period === "month") {
    const [year, month] = label.split("-");
    const parsedDate = new Date(Number(year), Number(month) - 1, 1);

    return new Intl.DateTimeFormat("es-ES", {
      month: "short",
      year: "numeric",
    }).format(parsedDate);
  }

  return label.split("-").pop() || label;
};

export default function AnalyticsPage() {
  const [barPeriod, setBarPeriod] = useState<BarPeriod>("30d");
  const [seriesMode, setSeriesMode] = useState<AnalyticsSeries>("both");
  const [donutPeriod, setDonutPeriod] = useState<DonutPeriod>("month");
  const [categoryType, setCategoryType] = useState<CategoryType>("expense");
  const [hiddenCategories, setHiddenCategories] = useState<Set<string>>(new Set());

  const barDateRange = useMemo(() => buildBarDateRange(barPeriod), [barPeriod]);
  const donutDateRange = useMemo(() => buildDonutDateRange(donutPeriod), [donutPeriod]);

  const { data: trendData, isLoading: loadingTrends } = useQuery({
    queryKey: ["analytics-cashflow", barDateRange.start_date, barDateRange.end_date, barDateRange.period],
    refetchOnMount: "always",
    queryFn: async () => {
      const res = await api.get("/api/dashboard/cashflow-series", {
        params: {
          start_date: barDateRange.start_date,
          end_date: barDateRange.end_date,
          period: barDateRange.period
        }
      });
      return res.data;
    }
  });

  const { data: categoryData, isLoading: loadingCategories, isFetching: fetchingCategories, isError: categoryError } = useQuery({
    queryKey: ["analytics-categories", donutDateRange.start_date, donutDateRange.end_date, categoryType],
    refetchOnMount: "always",
    queryFn: async () => {
      const res = await api.get("/api/dashboard/category-distribution", {
        params: {
          start_date: donutDateRange.start_date,
          end_date: donutDateRange.end_date,
          type: categoryType
        }
      });
      return res.data;
    }
  });

  // Transformación de datos respetando la regla estricta de casteo a Number
  const parsedTrendData = useMemo(() => {
    return (trendData as CashflowItem[])?.map((item) => ({
      ...item,
      expense: Number(item.expense),
      income: Number(item.income)
    })) || [];
  }, [trendData]);

  const visibleTrendData = useMemo(() => {
    return parsedTrendData.map((item) => ({
      ...item,
      income: seriesMode === "expense" ? 0 : item.income,
      expense: seriesMode === "income" ? 0 : item.expense,
    }));
  }, [parsedTrendData, seriesMode]);

  const originalCategoryData = useMemo(() => {
    const items = (categoryData as CategoryDistributionItem[])?.map((item) => ({
      ...item,
      value: Number(item.total),
    })) || [];

    const totalAmount = items.reduce((sum, item) => sum + item.value, 0);

    return items.map((item) => ({
      ...item,
      percentage: totalAmount > 0 ? (item.value / totalAmount) * 100 : 0,
    }));
  }, [categoryData]);

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

  const yAxisWidth = useMemo(() => {
    if (visibleTrendData.length === 0) {
      return 84;
    }

    const maxValue = Math.max(
      ...visibleTrendData.flatMap((item) => [Number(item.income), Number(item.expense)]),
      0
    );
    const labelLength = formatCurrency(maxValue).length;

    return Math.min(Math.max(labelLength * 8 + 30, 84), 160);
  }, [visibleTrendData]);

  if (loadingTrends && loadingCategories) {
    return (
      <div className="flex h-[50vh] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-[#60a5fa]" />
      </div>
    );
  }

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <div>
        <h1 className="text-2xl font-semibold text-text">Analítica Financiera</h1>
        <p className="text-text-muted text-sm mt-1">
          Visualiza el flujo de tu dinero y la distribución de tus finanzas.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Gráfico de Barras: Flujo de Caja */}
        <div className="bg-surface/80 border border-border/70 p-6 rounded-2xl shadow-sm backdrop-blur-sm">
          <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <h2 className="text-lg font-medium text-text-soft">Flujo de Caja</h2>
            <div className="flex items-center gap-2 flex-wrap">
              <div className="flex items-center gap-1 rounded-lg border border-border/70 bg-background/40 p-0.5">
                {([
                  { value: "7d", label: "7 días" },
                  { value: "30d", label: "30 días" },
                  { value: "12m", label: "12 meses" },
                ] as const).map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => setBarPeriod(option.value)}
                    className={`rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors ${
                      barPeriod === option.value
                        ? "bg-primary text-background"
                        : "text-text-muted hover:text-text"
                    }`}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
              <div className="flex items-center gap-1 rounded-lg border border-border/70 bg-background/40 p-0.5">
                {([
                  { value: "both", label: "Ambos" },
                  { value: "income", label: "Ingresos" },
                  { value: "expense", label: "Gastos" },
                ] as const).map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => setSeriesMode(option.value)}
                    className={`rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors ${
                      seriesMode === option.value
                        ? "bg-surface-elevated text-text"
                        : "text-text-muted hover:text-text"
                    }`}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
          {loadingTrends ? (
            <div className="h-72 flex items-center justify-center">
              <Loader2 className="h-6 w-6 animate-spin text-[#60a5fa]" />
            </div>
          ) : (
            <div className="h-72 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={visibleTrendData} margin={{ top: 24, right: 10, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#24314a" vertical={false} />
                  <XAxis 
                    dataKey="date_label"
                    stroke="#9aa7bd" 
                    fontSize={12} 
                    tickLine={false} 
                    axisLine={false} 
                    tickFormatter={(val) => formatXAxisLabel(String(val), barPeriod === "12m" ? "month" : "day")}
                  />
                  <YAxis 
                    stroke="#9aa7bd" 
                    fontSize={12} 
                    tickLine={false} 
                    axisLine={false}
                    width={yAxisWidth}
                    tickMargin={10}
                    tickFormatter={(value) => formatCurrency(Number(value))} 
                  />
                  <Tooltip 
                    cursor={{ fill: '#24314a', opacity: 0.35 }}
                    contentStyle={{ backgroundColor: '#162338', borderColor: '#24314a', borderRadius: '8px', color: '#eef4ff' }}
                    formatter={(value: number) => [formatCurrency(Number(value)), ""]}
                    labelFormatter={(label) => `Fecha: ${label}`}
                  />
                  {seriesMode !== "expense" && (
                    <Bar dataKey="income" name="Ingresos" fill="#34d399" radius={[4, 4, 0, 0]} maxBarSize={40}>
                      {barPeriod === "12m" && <LabelList dataKey="income" position="top" formatter={(v) => formatCurrency(Number(v))} style={{ fill: '#9aa7bd', fontSize: 11 }} />}
                    </Bar>
                  )}
                  {seriesMode !== "income" && (
                    <Bar dataKey="expense" name="Gastos" fill="#fb7185" radius={[4, 4, 0, 0]} maxBarSize={40}>
                      {barPeriod === "12m" && <LabelList dataKey="expense" position="top" formatter={(v) => formatCurrency(Number(v))} style={{ fill: '#9aa7bd', fontSize: 11 }} />}
                    </Bar>
                  )}
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>

        {/* Gráfico de Dona: Distribución por Categorías */}
        <div className="bg-surface/80 border border-border/70 p-6 rounded-2xl shadow-sm backdrop-blur-sm">
          <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <h2 className="text-lg font-medium text-text-soft">Distribución por Categorías</h2>
            <div className="flex items-center gap-2 flex-wrap">
              <div className="flex items-center gap-1 rounded-lg border border-border/70 bg-background/40 p-0.5">
                {([
                  { value: "month", label: "Este mes" },
                  { value: "3months", label: "3 meses" },
                  { value: "year", label: "Este año" },
                ] as const).map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => setDonutPeriod(option.value)}
                    className={`rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors ${
                      donutPeriod === option.value
                        ? "bg-primary text-background"
                        : "text-text-muted hover:text-text"
                    }`}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
              <div className="flex items-center gap-1 rounded-lg border border-border/70 bg-background/40 p-0.5">
                {([
                  { value: "expense", label: "Gastos" },
                  { value: "income", label: "Ingresos" },
                ] as const).map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => setCategoryType(option.value)}
                    className={`rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors ${
                      categoryType === option.value
                        ? "bg-surface-elevated text-text"
                        : "text-text-muted hover:text-text"
                    }`}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
          {categoryError ? (
            <div className="h-72 flex items-center justify-center rounded-xl border border-dashed border-border text-sm text-text-muted">
              No se pudieron cargar las categorías.
            </div>
          ) : fetchingCategories && originalCategoryData.length === 0 ? (
            <div className="h-72 flex items-center justify-center">
              <Loader2 className="h-6 w-6 animate-spin text-[#60a5fa]" />
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
                          <Cell key={`cell-${index}`} fill={getCategoryColor(_entry, index)} />
                        ))}
                      </Pie>
                      <Tooltip 
                        content={({ active, payload }) => {
                          const item = payload?.[0]?.payload;

                          if (!active || !item) {
                            return null;
                          }

                          return (
                            <div className="rounded-lg border border-border bg-surface-elevated px-3 py-2 text-sm shadow-lg">
                              <p className="font-medium text-text">{item.category_name}</p>
                              <p className="mt-1 text-text-soft">Total: {formatCurrency(Number(item.value))}</p>
                              <p className="text-text-muted">{item.percentage.toFixed(1)}% del subtotal</p>
                            </div>
                          );
                        }}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-72 flex items-center justify-center rounded-xl border border-dashed border-border text-sm text-text-muted">
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
                    return (
                      <div
                        key={`${item.category_id ?? index}-legend`}
                        className={`flex items-center justify-between gap-3 text-sm cursor-pointer transition-opacity hover:opacity-80 ${isHidden ? 'opacity-30' : ''}`}
                        onClick={() => {
                          const id = String(item.category_id);
                          setHiddenCategories((prev) => {
                            const next = new Set(prev);
                            if (next.has(id)) next.delete(id);
                            else next.add(id);
                            return next;
                          });
                        }}
                      >
                        <div className="flex items-center gap-2 min-w-0">
                          <span
                            className="h-2.5 w-2.5 shrink-0 rounded-full"
                            style={{ backgroundColor: getCategoryColor(item, index) }}
                          />
                          <span className={`truncate ${isHidden ? 'line-through text-text-muted' : 'text-text-soft'}`}>
                            {item.category_name}{!isHidden && <span className="text-text-muted"> ({displayPercentage.toFixed(1)}%)</span>}
                          </span>
                        </div>
                        <span className="shrink-0 text-text-muted">{formatCurrency(Number(item.value))}</span>
                      </div>
                    );
                  })}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}