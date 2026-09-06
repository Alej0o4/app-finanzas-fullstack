'use client';

import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '@/lib/queryKeys';
import type { CashflowItem, CategoryDistributionItem } from '@/types/api';
import { api } from '@/lib/api';
import { useCurrentUser } from '@/lib/hooks/useCurrentUser';
import { useState, useMemo, Suspense } from 'react';
import { useQueryParamState } from '@/hooks/useQueryParamState';
import CashflowChart, { type BarPeriod, type AnalyticsSeries } from '@/components/CashflowChart';
import CategoryDonutChart, {
  type DonutPeriod,
  type CategoryType,
} from '@/components/CategoryDonutChart';
import AnalyticsSummary from '@/components/AnalyticsSummary';
import Skeleton from '@/components/ui/Skeleton';

const formatISOForBackend = (date: Date) => {
  const pad = (value: number) => String(value).padStart(2, '0');

  return (
    [date.getFullYear(), pad(date.getMonth() + 1), pad(date.getDate())].join('-') +
    `T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
  );
};

const buildBarDateRange = (period: BarPeriod) => {
  const now = new Date();
  const start = new Date(now);

  if (period === '7d') start.setDate(now.getDate() - 7);
  else if (period === '30d') start.setDate(now.getDate() - 30);
  else start.setFullYear(now.getFullYear() - 1);

  return {
    start_date: formatISOForBackend(start),
    end_date: formatISOForBackend(now),
    period: period === '12m' ? ('month' as const) : ('day' as const),
  };
};

const buildDonutDateRange = (period: DonutPeriod) => {
  const now = new Date();

  if (period === '3months') {
    const start = new Date(now);
    start.setMonth(now.getMonth() - 3);
    return {
      start_date: formatISOForBackend(start),
      end_date: formatISOForBackend(now),
    };
  }

  if (period === 'year') {
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

function AnalyticsPageContent() {
  // Decisión 11.1.1 (Fase 11): se pasa `currency` explícito a los endpoints de dashboard
  // aunque el backend ya defaultea a la moneda preferida — deja la intención explícita.
  const { data: user } = useCurrentUser();
  // Fase 12 §12.1, Decisión 12.1.2: la vista vive en la URL, no en localStorage — se
  // abandona usePersistedState (un link limpio vuelve a defaults; esa es la semántica
  // esperada de un link compartible). hiddenCategories sigue en useState (Decisión 12.1.3).
  const [barPeriod, setBarPeriod] = useQueryParamState('bar', '30d');
  const [seriesMode, setSeriesMode] = useQueryParamState('series', 'both');
  const [donutPeriod, setDonutPeriod] = useQueryParamState('donut', 'month');
  const [categoryType, setCategoryType] = useQueryParamState('type', 'expense');
  const [netModeRaw, setNetMode] = useQueryParamState('neto', 'false');
  const [hiddenCategories, setHiddenCategories] = useState<Set<string>>(new Set());

  // La capa de URL comunica strings; los charts esperan uniones literales. Los setters se
  // pasan tal cual (aceptan string, que cubre la unión); los valores se afinan al tipar.
  const barPeriodTyped = barPeriod as BarPeriod;
  const seriesModeTyped = seriesMode as AnalyticsSeries;
  const donutPeriodTyped = donutPeriod as DonutPeriod;
  const categoryTypeTyped = categoryType as CategoryType;
  const netMode = netModeRaw === 'true';

  const barDateRange = useMemo(() => buildBarDateRange(barPeriodTyped), [barPeriodTyped]);
  const donutDateRange = useMemo(() => buildDonutDateRange(donutPeriodTyped), [donutPeriodTyped]);

  const {
    data: trendData,
    isLoading: loadingTrends,
    isError: trendError,
  } = useQuery({
    queryKey: queryKeys.analytics.cashflow(
      barDateRange.start_date,
      barDateRange.end_date,
      barDateRange.period
    ),
    queryFn: async () => {
      const res = await api.get('dashboard/cashflow-series', {
        params: {
          start_date: barDateRange.start_date,
          end_date: barDateRange.end_date,
          period: barDateRange.period,
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
      donutDateRange.start_date,
      donutDateRange.end_date,
      categoryTypeTyped,
      netMode
    ),
    queryFn: async () => {
      const res = await api.get('dashboard/category-distribution', {
        params: {
          start_date: donutDateRange.start_date,
          end_date: donutDateRange.end_date,
          type: netMode ? 'expense' : categoryTypeTyped,
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
      income: seriesModeTyped === 'expense' ? 0 : item.income,
      expense: seriesModeTyped === 'income' ? 0 : item.expense,
    }));
  }, [parsedTrendData, seriesModeTyped]);

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

      <AnalyticsSummary totalIncome={totals.totalIncome} totalExpense={totals.totalExpense} />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <CashflowChart
          data={visibleTrendData}
          isLoading={loadingTrends}
          isError={trendError}
          barPeriod={barPeriodTyped}
          onBarPeriodChange={setBarPeriod}
          seriesMode={seriesModeTyped}
          onSeriesModeChange={setSeriesMode}
          periodType={barPeriodTyped === '12m' ? 'month' : 'day'}
        />

        <CategoryDonutChart
          data={categoryData as CategoryDistributionItem[]}
          isFetching={fetchingCategories}
          isError={categoryError}
          donutPeriod={donutPeriodTyped}
          onDonutPeriodChange={setDonutPeriod}
          categoryType={categoryTypeTyped}
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
