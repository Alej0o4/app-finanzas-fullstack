"use client";

import { useQuery } from "@tanstack/react-query";
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell
} from "recharts";
import { formatCurrency } from "@/lib/utils";
import { api } from "@/lib/api";
import { Loader2 } from "lucide-react";
import { useState, useMemo } from "react";

const COLORS = ["#166534", "#22c55e", "#4ade80", "#bbf7d0", "#064e3b"];

// Función auxiliar para formatear fechas al estándar requerido por el backend
const formatISOForBackend = (date: Date) => {
  return date.toISOString().split('.')[0]; // Retorna YYYY-MM-DDTHH:MM:SS
};

export default function AnalyticsPage() {
  // Estado para controlar el rango de fechas (por defecto: mes actual)
  const [dateRange, setDateRange] = useState(() => {
    const now = new Date();
    const start = new Date(now.getFullYear(), now.getMonth(), 1, 0, 0, 0);
    const end = new Date(now.getFullYear(), now.getMonth() + 1, 0, 23, 59, 59);
    
    return {
      start_date: formatISOForBackend(start),
      end_date: formatISOForBackend(end),
      period: "day" // o "month" si quieres una vista anual
    };
  });

  // 1. Consulta del Flujo de Caja (Cashflow Series)
  const { data: trendData, isLoading: loadingTrends } = useQuery({
    // Incluimos dateRange en la queryKey para que React Query haga refetch si cambiamos las fechas
    queryKey: ["analytics-cashflow", dateRange], 
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
    queryKey: ["analytics-categories", dateRange],
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
    if (parsedTrendData.length === 0) {
      return 84;
    }

    const maxValue = Math.max(
      ...parsedTrendData.flatMap((item: any) => [Number(item.income), Number(item.expense)]),
      0
    );
    const labelLength = formatCurrency(maxValue).length;

    return Math.min(Math.max(labelLength * 8 + 25, 84), 160);
  }, [parsedTrendData]);

  if (loadingTrends || loadingCategories) {
    return (
      <div className="flex h-[50vh] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-green-700" />
      </div>
    );
  }

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <div>
        <h1 className="text-2xl font-semibold text-zinc-100">Analítica Financiera</h1>
        <p className="text-zinc-400 text-sm mt-1">
          Visualiza el flujo de tu dinero y la distribución de tus gastos.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Gráfico de Barras: Flujo de Caja */}
        <div className="bg-zinc-900/50 border border-zinc-800/50 p-6 rounded-2xl shadow-sm backdrop-blur-sm">
          <h2 className="text-lg font-medium text-zinc-200 mb-6">Flujo de Caja ({dateRange.period === 'day' ? 'Diario' : 'Mensual'})</h2>
          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={parsedTrendData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
                <XAxis 
                  dataKey="date_label" // <- ACTULIZADO según la spec
                  stroke="#a1a1aa" 
                  fontSize={12} 
                  tickLine={false} 
                  axisLine={false} 
                  // Formateador simple para mostrar solo el día si es formato YYYY-MM-DD
                  tickFormatter={(val) => val.split('-').pop() || val}
                />
                <YAxis 
                  stroke="#a1a1aa" 
                  fontSize={12} 
                  tickLine={false} 
                  axisLine={false}
                  width={yAxisWidth}
                  tickMargin={10}
                  tickFormatter={(value) => formatCurrency(Number(value))} 
                />
                <Tooltip 
                  cursor={{ fill: '#27272a', opacity: 0.4 }}
                  contentStyle={{ backgroundColor: '#18181b', borderColor: '#27272a', borderRadius: '8px', color: '#f4f4f5' }}
                  formatter={(value: any) => [formatCurrency(Number(value)), ""]}
                  labelFormatter={(label) => `Fecha: ${label}`}
                />
                <Bar dataKey="income" name="Ingresos" fill="#22c55e" radius={[4, 4, 0, 0]} maxBarSize={40} />
                <Bar dataKey="expense" name="Gastos" fill="#ef4444" radius={[4, 4, 0, 0]} maxBarSize={40} /> {/* <- ACTUALIZADO a expense singular */}
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Gráfico de Dona: Distribución por Categorías */}
        <div className="bg-zinc-900/50 border border-zinc-800/50 p-6 rounded-2xl shadow-sm backdrop-blur-sm">
          <h2 className="text-lg font-medium text-zinc-200 mb-6">Distribución por Categorías</h2>
          {categoryError ? (
            <div className="h-72 flex items-center justify-center rounded-xl border border-dashed border-zinc-800 text-sm text-zinc-500">
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
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip 
                      content={({ active, payload }) => {
                        const item = payload?.[0]?.payload;

                        if (!active || !item) {
                          return null;
                        }

                        return (
                          <div className="rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm shadow-lg">
                            <p className="font-medium text-zinc-100">{item.category_name}</p>
                            <p className="mt-1 text-zinc-300">Total: {formatCurrency(Number(item.value))}</p>
                            <p className="text-zinc-400">{item.percentage.toFixed(1)}% del total</p>
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
                          style={{ backgroundColor: COLORS[index % COLORS.length] }}
                        />
                        <span className="truncate text-zinc-300">
                          {item.category_name} <span className="text-zinc-500">({item.percentage.toFixed(1)}%)</span>
                        </span>
                      </div>
                      <span className="shrink-0 text-zinc-500">{formatCurrency(Number(item.value))}</span>
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