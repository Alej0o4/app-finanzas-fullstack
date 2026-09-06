'use client';

import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '@/lib/queryKeys';
import type { CashflowItem, CategoryDistributionItem } from '@/types/api';
import { api } from '@/lib/api';
import { useCurrentUser } from '@/lib/hooks/useCurrentUser';
import { useState, useMemo, Suspense } from 'react';
import { useQueryParamState, useQueryParamsBatch } from '@/hooks/useQueryParamState';
import CashflowChart, { type AnalyticsSeries } from '@/components/CashflowChart';
import CategoryDonutChart, { type CategoryType } from '@/components/CategoryDonutChart';
import AnalyticsSummary from '@/components/AnalyticsSummary';
import Input from '@/components/ui/Input';
import Skeleton from '@/components/ui/Skeleton';

export type AnalyticsPeriod = 'week' | 'month' | 'year' | 'custom';

const PERIOD_OPTIONS: { value: AnalyticsPeriod; label: string }[] = [
  { value: 'week', label: 'Esta semana' },
  { value: 'month', label: 'Este mes' },
  { value: 'year', label: 'Este año' },
  { value: 'custom', label: 'Personalizado' },
];

// Un solo rango de fechas alimenta la tarjeta de KPIs, el gráfico de barras y la dona — antes
// cada uno tenía su propio selector de período independiente, y solo el de barras afectaba los
// números de arriba, lo cual era confuso (Fase de discusión UX, 2026-09-06).
//
// .toISOString() manda el instante UTC real. Un string armado a mano con los getters locales
// (getHours() etc.) sin sufijo de zona horaria se interpretaba como UTC en el backend (sesión
// de Postgres en UTC) — con el servidor en America/Bogota (UTC-5), eso recortaba "ahora" 5 horas
// antes del real y excluía del todo las transacciones recién creadas de estos rangos.
const buildDateRange = (period: AnalyticsPeriod, customStart: string, customEnd: string) => {
  const now = new Date();

  if (period === 'week') {
    const start = new Date(now);
    start.setDate(now.getDate() - 6);
    return {
      start_date: start.toISOString(),
      end_date: now.toISOString(),
      granularity: 'day' as const,
    };
  }

  if (period === 'year') {
    // Date.UTC (no el constructor local `new Date(y, 0, 1)`): un límite de calendario como
    // "inicio de año" debe anclarse en UTC porque el backend guarda y compara fechas en UTC
    // (sesión de Postgres en UTC) — construirlo con getters locales lo desplaza por el offset
    // de la zona horaria del navegador y excluye transacciones del borde del período (mismo
    // bug ya corregido para el dashboard, ver comentario de buildDateRange más arriba).
    return {
      start_date: new Date(Date.UTC(now.getUTCFullYear(), 0, 1)).toISOString(),
      end_date: now.toISOString(),
      granularity: 'month' as const,
    };
  }

  if (period === 'custom' && customStart && customEnd) {
    // 'Z' explícito: el input type=date entrega "YYYY-MM-DD" sin zona horaria — sin el
    // sufijo, `new Date(...)` lo interpreta en hora local y desplaza el límite (mismo
    // problema que el de 'year'/'month').
    const start = new Date(`${customStart}T00:00:00Z`);
    const end = new Date(`${customEnd}T23:59:59Z`);
    const spanDays = (end.getTime() - start.getTime()) / (1000 * 60 * 60 * 24);
    // El backend de cashflow-series solo agrupa por 'day' o 'month' (sin 'week') — un rango
    // personalizado largo usa 'month' para no devolver cientos de barras diarias.
    return {
      start_date: start.toISOString(),
      end_date: end.toISOString(),
      granularity: spanDays > 60 ? ('month' as const) : ('day' as const),
    };
  }

  // 'month' (default) y fallback de 'custom' mientras el usuario no completa el rango.
  return {
    start_date: new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), 1)).toISOString(),
    end_date: now.toISOString(),
    granularity: 'day' as const,
  };
};

// Fase 13 §13.6: validadores read-time de los query params de analytics. Un link inválido
// (?period=abc) devolvía strings crudos que luego se casteaban a ciegas; ahora el hook devuelve
// el valor ya validado y tipado por estos validators, sin casts en la página. El tipo de retorno
// del validator es lo que el hook infiere como tipo del valor.
const validatePeriod = (raw: string): AnalyticsPeriod =>
  (['week', 'month', 'year', 'custom'] as const).includes(raw as AnalyticsPeriod)
    ? (raw as AnalyticsPeriod)
    : 'month';

// Mismo patrón que transactions/page.tsx: whitelist de formato para start/end (rango
// personalizado), sin reescribir la URL con el valor corregido.
const validateDateParam = (raw: string) => (/^\d{4}-\d{2}-\d{2}$/.test(raw) ? raw : '');

const validateSeriesMode = (raw: string): AnalyticsSeries =>
  (['both', 'income', 'expense'] as const).includes(raw as AnalyticsSeries)
    ? (raw as AnalyticsSeries)
    : 'both';

const validateCategoryType = (raw: string): CategoryType =>
  (['expense', 'income'] as const).includes(raw as CategoryType)
    ? (raw as CategoryType)
    : 'expense';

const validateNeto = (raw: string): 'true' | 'false' => (raw === 'true' ? 'true' : 'false');

function AnalyticsPageContent() {
  // Decisión 11.1.1 (Fase 11): se pasa `currency` explícito a los endpoints de dashboard
  // aunque el backend ya defaultea a la moneda preferida — deja la intención explícita.
  const { data: user } = useCurrentUser();
  // Fase 12 §12.1, Decisión 12.1.2: la vista vive en la URL, no en localStorage — se
  // abandona usePersistedState (un link limpio vuelve a defaults; esa es la semántica
  // esperada de un link compartible). hiddenCategories sigue en useState (Decisión 12.1.3).
  // Fase 13 §13.6: cada valor sale validado del hook (whitelist tipada), sin casts locales.
  const [period] = useQueryParamState('period', 'month', validatePeriod);
  const [customStart] = useQueryParamState('start', '', validateDateParam);
  const [customEnd] = useQueryParamState('end', '', validateDateParam);
  const setPeriodParams = useQueryParamsBatch();
  const [seriesMode, setSeriesMode] = useQueryParamState('series', 'both', validateSeriesMode);
  const [categoryType, setCategoryType] = useQueryParamState(
    'type',
    'expense',
    validateCategoryType
  );
  const [netoRaw, setNetMode] = useQueryParamState('neto', 'false', validateNeto);
  const [hiddenCategories, setHiddenCategories] = useState<Set<string>>(new Set());

  const netMode = netoRaw === 'true';

  // Un solo rango de fechas para las 3 secciones (KPIs, barras, dona) — ver buildDateRange.
  const dateRange = useMemo(
    () => buildDateRange(period, customStart, customEnd),
    [period, customStart, customEnd]
  );

  const handlePeriodChange = (next: AnalyticsPeriod) => {
    if (next === 'custom') {
      setPeriodParams({ period: 'custom' });
    } else {
      setPeriodParams({ period: next === 'month' ? null : next, start: null, end: null });
    }
  };

  const {
    data: trendData,
    isLoading: loadingTrends,
    isError: trendError,
  } = useQuery({
    queryKey: queryKeys.analytics.cashflow(
      dateRange.start_date,
      dateRange.end_date,
      dateRange.granularity
    ),
    queryFn: async () => {
      const res = await api.get('dashboard/cashflow-series', {
        params: {
          start_date: dateRange.start_date,
          end_date: dateRange.end_date,
          period: dateRange.granularity,
          currency: user?.preferred_currency,
        },
      });
      return res.data;
    },
  });

  const {
    data: categoryData,
    isLoading: loadingCategories,
    isFetching: fetchingCategories,
    isError: categoryError,
  } = useQuery({
    queryKey: queryKeys.analytics.categories(
      dateRange.start_date,
      dateRange.end_date,
      categoryType,
      netMode
    ),
    queryFn: async () => {
      const res = await api.get('dashboard/category-distribution', {
        params: {
          start_date: dateRange.start_date,
          end_date: dateRange.end_date,
          type: netMode ? 'expense' : categoryType,
          neto: netMode || undefined,
          currency: user?.preferred_currency,
        },
      });
      return res.data;
    },
  });

  const parsedTrendData = useMemo(() => {
    return (
      (trendData as CashflowItem[])?.map((item) => ({
        ...item,
        expense: Number(item.expense),
        income: Number(item.income),
      })) || []
    );
  }, [trendData]);

  const visibleTrendData = useMemo(() => {
    return parsedTrendData.map((item) => ({
      ...item,
      income: seriesMode === 'expense' ? 0 : item.income,
      expense: seriesMode === 'income' ? 0 : item.expense,
    }));
  }, [parsedTrendData, seriesMode]);

  const totals = useMemo(() => {
    const totalIncome = parsedTrendData.reduce((sum, item) => sum + item.income, 0);
    const totalExpense = parsedTrendData.reduce((sum, item) => sum + item.expense, 0);
    return { totalIncome, totalExpense };
  }, [parsedTrendData]);

  if (loadingTrends && loadingCategories) {
    return (
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Skeleton className="h-96 rounded-2xl" />
        <Skeleton className="h-96 rounded-2xl" />
      </div>
    );
  }

  return (
    <div className="animate-in fade-in space-y-8 duration-500">
      <div>
        <h1 className="text-text text-2xl font-semibold">Analítica Financiera</h1>
        <p className="text-text-muted mt-1 text-sm">
          Visualiza el flujo de tu dinero y la distribución de tus finanzas.
        </p>
      </div>

      {/* Selector de período único: controla la tarjeta de KPIs, el gráfico de barras y la
          dona a la vez — antes cada gráfico tenía su propio selector y solo uno de ellos
          afectaba los números de arriba, lo cual generaba confusión. */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="border-border/70 bg-background/40 flex items-center gap-1 rounded-lg border p-0.5">
          {PERIOD_OPTIONS.map((option) => (
            <button
              key={option.value}
              type="button"
              onClick={() => handlePeriodChange(option.value)}
              className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                period === option.value
                  ? 'bg-primary text-background'
                  : 'text-text-muted hover:text-text'
              }`}
            >
              {option.label}
            </button>
          ))}
        </div>

        {period === 'custom' && (
          <div className="flex flex-wrap items-center gap-2">
            <Input
              type="date"
              value={customStart}
              onChange={(event) =>
                setPeriodParams({ period: 'custom', start: event.target.value || null })
              }
              className="bg-background"
              aria-label="Fecha inicial"
            />
            <span className="text-text-muted text-sm">a</span>
            <Input
              type="date"
              value={customEnd}
              onChange={(event) =>
                setPeriodParams({ period: 'custom', end: event.target.value || null })
              }
              className="bg-background"
              aria-label="Fecha final"
            />
          </div>
        )}
      </div>

      <AnalyticsSummary totalIncome={totals.totalIncome} totalExpense={totals.totalExpense} />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <CashflowChart
          data={visibleTrendData}
          isLoading={loadingTrends}
          isError={trendError}
          seriesMode={seriesMode}
          onSeriesModeChange={setSeriesMode}
          periodType={dateRange.granularity}
        />

        <CategoryDonutChart
          data={categoryData as CategoryDistributionItem[]}
          isFetching={fetchingCategories}
          isError={categoryError}
          categoryType={categoryType}
          onCategoryTypeChange={setCategoryType}
          netMode={netMode}
          onNetModeChange={(net) => setNetMode(String(net))}
          hiddenCategories={hiddenCategories}
          onHiddenCategoriesChange={setHiddenCategories}
        />
      </div>
    </div>
  );
}

// Fase 12 §12.1: useSearchParams requiere Suspense (mismo patrón que login/reset-password).
export default function AnalyticsPage() {
  return (
    <Suspense fallback={<Skeleton className="h-96 rounded-2xl" />}>
      <AnalyticsPageContent />
    </Suspense>
  );
}
