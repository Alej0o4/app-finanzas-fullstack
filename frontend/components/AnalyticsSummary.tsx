"use client";

import SummaryCard from "@/components/ui/SummaryCard";
import { formatCurrency } from "@/lib/utils";
import { useAppConfig } from "@/providers/AppConfigProvider";

interface AnalyticsSummaryProps {
  totalIncome: number;
  totalExpense: number;
}

export default function AnalyticsSummary({ totalIncome, totalExpense }: AnalyticsSummaryProps) {
  const { config } = useAppConfig();
  const total = totalIncome - totalExpense;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
      <SummaryCard label="Ingresos" value={formatCurrency(totalIncome, config.currency)} trend="up" color="#34d399" />
      <SummaryCard label="Gastos" value={formatCurrency(totalExpense, config.currency)} trend="down" color="#fb7185" />
      <SummaryCard label="Balance Neto" value={formatCurrency(total, config.currency)} color={total >= 0 ? "#34d399" : "#fb7185"} />
    </div>
  );
}
