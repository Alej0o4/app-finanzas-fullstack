"use client";

import SummaryCard from "@/components/ui/SummaryCard";
import { formatCurrency } from "@/lib/utils";

interface AnalyticsSummaryProps {
  totalIncome: number;
  totalExpense: number;
}

export default function AnalyticsSummary({ totalIncome, totalExpense }: AnalyticsSummaryProps) {
  const total = totalIncome - totalExpense;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
      <SummaryCard label="Ingresos" value={formatCurrency(totalIncome)} trend="up" color="#34d399" />
      <SummaryCard label="Gastos" value={formatCurrency(totalExpense)} trend="down" color="#fb7185" />
      <SummaryCard label="Balance Neto" value={formatCurrency(total)} color={total >= 0 ? "#34d399" : "#fb7185"} />
    </div>
  );
}
