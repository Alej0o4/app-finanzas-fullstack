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

type AnalyticsPeriod = "day" | "month";
type AnalyticsSeries = "both" | "income" | "expense";

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

const buildDateRange = (period: AnalyticsPeriod) => {
  const now = new Date();

  if (period === "month") {
    return {
      start_date: formatISOForBackend(new Date(now.getFullYear(), 0, 1, 0, 0, 0)),
      end_date: formatISOForBackend(new Date(now.getFullYear(), now.getMonth(), now.getDate(), 23, 59, 59)),
      period,
    };
  }

  return {
    start_date: formatISOForBackend(new Date(now.getFullYear(), now.getMonth(), 1, 0, 0, 0)),
    end_date: formatISOForBackend(new Date(now.getFullYear(), now.getMonth(), now.getDate(), 23, 59, 59)),
    period,
  };
};

const getCategoryColor = (item: any, index: number) => {
  const seed = Number(item.category_id ?? index);

  return CATEGORY_COLORS[Math.abs(seed) % CATEGORY_COLORS.length];
};

const formatXAxisLabel = (label: string, period: AnalyticsPeriod) => {
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
  // Estado para controlar la granularidad y el tipo de serie visible
  const [period, setPeriod] = useState<AnalyticsPeriod>("day");
  const [seriesMode, setSeriesMode] = useState<AnalyticsSeries>("both");

  const dateRange = useMemo(() => buildDateRange(period), [period]);

  // 1. Consulta del Flujo de Caja (Cashflow Series)
  const { data: trendData, isLoading: loadingTrends } = useQuery({
    // Forzamos refetch al montar Analytics para no depender de la caché entre entradas a la ruta
    queryKey: ["analytics-cashflow", dateRange.start_date, dateRange.end_date, dateRange.period], 
    refetchOnMount: "always",
    queryFn: async () => {
      const res = await api.get("/api/dashboard/cashflow-series", {
        params: {
          start_date: dateRange.start_date,
          end_date: dateRange.end_date,
          period: dateRange.period
        }
      });
      return res.data; 
    }
  });

  // 2. Consulta de Categorías (Asumiendo que también recibe fechas, ajusta si es necesario)
  const { data: categoryData, isLoading: loadingCategories, isError: categoryError } = useQuery({
    queryKey: ["analytics-categories", dateRange.start_date, dateRange.end_date],
    refetchOnMount: "always",
    queryFn: async () => {
      const res = await api.get("/api/dashboard/category-distribution", {
        params: {
          start_date: dateRange.start_date,
          end_date: dateRange.end_date
        }
      });
      return res.data;
    }
  });

  // Transformación de datos respetando la regla estricta de casteo a Number
  const parsedTrendData = useMemo(() => {
    return trendData?.map((item: any) => ({
      ...item,
      // Aplicamos casting por seguridad, aunque vengan como JSON numbers, 
      // esto nos protege si FastAPI envía Decimals como strings
      expense: Number(item.expense), 
      income: Number(item.income)
    })) || [];
  }, [trendData]);

  const visibleTrendData = useMemo(() => {
    return parsedTrendData.map((item: any) => ({
      ...item,
      income: seriesMode === "expense" ? 0 : item.income,
      expense: seriesMode === "income" ? 0 : item.expense,
    }));
  }, [parsedTrendData, seriesMode]);

  const parsedCategoryData = useMemo(() => {
    const items = categoryData?.map((item: any) => ({
      ...item,
      value: Number(item.total), // Ajusta 'total' según la respuesta real de este endpoint
    })) || [];

    const totalAmount = items.reduce((sum: number, item: any) => sum + item.value, 0);

    return items.map((item: any) => ({
      ...item,
      percentage: totalAmount > 0 ? (item.value / totalAmount) * 100 : 0,
    }));
  }, [categoryData]);

  const yAxisWidth = useMemo(() => {
    if (visibleTrendData.length === 0) {
      return 84;
    }

    const maxValue = Math.max(
      ...visibleTrendData.flatMap((item: any) => [Number(item.income), Number(item.expense)]),
      0
    );
    const labelLength = formatCurrency(maxValue).length;

    return Math.min(Math.max(labelLength * 8 + 30, 84), 160);
  }, [visibleTrendData]);

  const visibleSeriesLabel = seriesMode === "both"
    ? "Ingresos y gastos"
    : seriesMode === "income"
      ? "Solo ingresos"
      : "Solo gastos";

  const periodLabel = period === "day" ? "Diario (mes actual)" : "Mensual (año actual)";

  if (loadingTrends || loadingCategories) {
    return (
      <div className="flex h-[50vh] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-[#60a5fa]" />
      </div>
    );
  }

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-text">Analítica Financiera</h1>
          <p className="text-text-muted text-sm mt-1">
            Visualiza el flujo de tu dinero y la distribución de tus gastos.
          </p>
        </div>

        <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
          <div className="flex items-center gap-2 rounded-xl border border-border/70 bg-surface-elevated/80 p-1">
            {([
              { value: "day", label: "Diario" },
              { value: "month", label: "Mensual" },
            ] as const).map((option) => (
              <button
                key={option.value}
                type="button"
                onClick={() => setPeriod(option.value)}
                className={`rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                  period === option.value
                    ? "bg-primary text-background"
                    : "text-text-muted hover:text-text"
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-2 rounded-xl border border-border/70 bg-surface-elevated/80 p-1">
            {([
              { value: "both", label: "Ambos" },
              { value: "income", label: "Ingresos" },
              { value: "expense", label: "Gastos" },
            ] as const).map((option) => (
              <button
                key={option.value}
                type="button"
                onClick={() => setSeriesMode(option.value)}
                className={`rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
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

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Gráfico de Barras: Flujo de Caja */}
        <div className="bg-surface/80 border border-border/70 p-6 rounded-2xl shadow-sm backdrop-blur-sm">
          <div className="mb-6 flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
            <h2 className="text-lg font-medium text-text-soft">Flujo de Caja ({periodLabel})</h2>
            <span className="text-xs uppercase tracking-[0.2em] text-text-muted">{visibleSeriesLabel}</span>
          </div>
          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={visibleTrendData} margin={{ top: 24, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#24314a" vertical={false} />
                <XAxis 
                  dataKey="date_label" // <- ACTULIZADO según la spec
                  stroke="#9aa7bd" 
                  fontSize={12} 
                  tickLine={false} 
                  axisLine={false} 
                  tickFormatter={(val) => formatXAxisLabel(String(val), period)}
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
                  formatter={(value: any) => [formatCurrency(Number(value)), ""]}
                  labelFormatter={(label) => `Fecha: ${label}`}
                />
                {seriesMode !== "expense" && (
                  <Bar dataKey="income" name="Ingresos" fill="#34d399" radius={[4, 4, 0, 0]} maxBarSize={40}>
                    {period === "month" && <LabelList dataKey="income" position="top" formatter={(v) => formatCurrency(Number(v))} style={{ fill: '#9aa7bd', fontSize: 11 }} />}
                  </Bar>
                )}
                {seriesMode !== "income" && (
                  <Bar dataKey="expense" name="Gastos" fill="#fb7185" radius={[4, 4, 0, 0]} maxBarSize={40}>
                    {period === "month" && <LabelList dataKey="expense" position="top" formatter={(v) => formatCurrency(Number(v))} style={{ fill: '#9aa7bd', fontSize: 11 }} />}
                  </Bar>
                )}
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Gráfico de Dona: Distribución por Categorías */}
        <div className="bg-surface/80 border border-border/70 p-6 rounded-2xl shadow-sm backdrop-blur-sm">
          <h2 className="text-lg font-medium text-text-soft mb-6">Distribución por Categorías</h2>
          {categoryError ? (
            <div className="h-72 flex items-center justify-center rounded-xl border border-dashed border-border text-sm text-text-muted">
              No se pudieron cargar las categorías.
            </div>
          ) : (
            <>
              <div className="h-72 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={parsedCategoryData}
                      cx="50%"
                      cy="50%"
                      innerRadius={80}
                      outerRadius={110}
                      paddingAngle={2}
                      dataKey="value"
                      stroke="none"
                    >
                      {parsedCategoryData.map((_entry: any, index: number) => (
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
                            <p className="text-text-muted">{item.percentage.toFixed(1)}% del total</p>
                          </div>
                        );
                      }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              {parsedCategoryData.length > 0 && (
                <div className="mt-5 space-y-2">
                  {parsedCategoryData.map((item: any, index: number) => (
                    <div key={`${item.category_id ?? index}-legend`} className="flex items-center justify-between gap-3 text-sm">
                      <div className="flex items-center gap-2 min-w-0">
                        <span
                          className="h-2.5 w-2.5 shrink-0 rounded-full"
                          style={{ backgroundColor: getCategoryColor(item, index) }}
                        />
                        <span className="truncate text-text-soft">
                          {item.category_name} <span className="text-text-muted">({item.percentage.toFixed(1)}%)</span>
                        </span>
                      </div>
                      <span className="shrink-0 text-text-muted">{formatCurrency(Number(item.value))}</span>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}