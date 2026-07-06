"use client";

import { useQuery } from "@tanstack/react-query";
import { queryKeys } from "@/lib/queryKeys";
import type { CashflowItem, CategoryDistributionItem } from "@/types/api";
import { api } from "@/lib/api";
import { Loader2 } from "lucide-react";
import { useState, useMemo } from "react";
import { usePersistedState } from "@/hooks/usePersistedState";
import CashflowChart, { type BarPeriod, type AnalyticsSeries } from "@/components/CashflowChart";
import CategoryDonutChart, { type DonutPeriod, type CategoryType } from "@/components/CategoryDonutChart";
import AnalyticsSummary from "@/components/AnalyticsSummary";

const formatISOForBackend = (date: Date) => {
  const pad = (value: number) => String(value).padStart(2, "0");

  return [
    date.getFullYear(),
    pad(date.getMonth() + 1),
    pad(date.getDate())
  ].join("-") + `T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
};

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

export default function AnalyticsPage() {
  const [barPeriod, setBarPeriod] = usePersistedState<BarPeriod>("analytics-barPeriod", "30d");
  const [seriesMode, setSeriesMode] = usePersistedState<AnalyticsSeries>("analytics-seriesMode", "both");
  const [donutPeriod, setDonutPeriod] = usePersistedState<DonutPeriod>("analytics-donutPeriod", "month");
  const [categoryType, setCategoryType] = usePersistedState<CategoryType>("analytics-categoryType", "expense");
  const [netMode, setNetMode] = usePersistedState<boolean>("analytics-netMode", false);
  const [hiddenCategories, setHiddenCategories] = useState<Set<string>>(new Set());

  const barDateRange = useMemo(() => buildBarDateRange(barPeriod), [barPeriod]);
  const donutDateRange = useMemo(() => buildDonutDateRange(donutPeriod), [donutPeriod]);

  const { data: trendData, isLoading: loadingTrends } = useQuery({
    queryKey: queryKeys.analytics.cashflow(barDateRange.start_date, barDateRange.end_date, barDateRange.period),
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
    queryKey: queryKeys.analytics.categories(donutDateRange.start_date, donutDateRange.end_date, categoryType, netMode),
    queryFn: async () => {
      const res = await api.get("/api/dashboard/category-distribution", {
        params: {
          start_date: donutDateRange.start_date,
          end_date: donutDateRange.end_date,
          type: netMode ? "expense" : categoryType,
          neto: netMode || undefined,
        }
      });
      return res.data;
    }
  });

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

  const totals = useMemo(() => {
    const totalIncome = parsedTrendData.reduce((sum, item) => sum + item.income, 0);
    const totalExpense = parsedTrendData.reduce((sum, item) => sum + item.expense, 0);
    return { totalIncome, totalExpense };
  }, [parsedTrendData]);

  if (loadingTrends && loadingCategories) {
    return (
      <div className="flex h-[50vh] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-info" />
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

      <AnalyticsSummary totalIncome={totals.totalIncome} totalExpense={totals.totalExpense} />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <CashflowChart
          data={visibleTrendData}
          isLoading={loadingTrends}
          barPeriod={barPeriod}
          onBarPeriodChange={setBarPeriod}
          seriesMode={seriesMode}
          onSeriesModeChange={setSeriesMode}
          periodType={barPeriod === "12m" ? "month" : "day"}
        />

        <CategoryDonutChart
          data={categoryData as CategoryDistributionItem[]}
          isFetching={fetchingCategories}
          isError={categoryError}
          donutPeriod={donutPeriod}
          onDonutPeriodChange={setDonutPeriod}
          categoryType={categoryType}
          onCategoryTypeChange={setCategoryType}
          netMode={netMode}
          onNetModeChange={setNetMode}
          hiddenCategories={hiddenCategories}
          onHiddenCategoriesChange={setHiddenCategories}
        />
      </div>
    </div>
  );
}
