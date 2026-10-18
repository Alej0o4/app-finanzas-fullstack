import { Receipt } from 'lucide-react';
import EmptyState from '@/components/ui/EmptyState';
import { formatCurrency, formatDateLabel } from '@/lib/utils';
import type { FundLinkedExpense } from '@/types/api';

interface LinkedExpensesListProps {
  expenses: FundLinkedExpense[];
  currency: string;
  timezone: string;
}

/** "Gastos de este sobre" (Fase 36, D9/D14): gastos enlazados, tal como los devuelve el backend. */
export default function LinkedExpensesList({
  expenses,
  currency,
  timezone,
}: LinkedExpensesListProps) {
  if (expenses.length === 0) {
    return (
      <EmptyState
        icon={<Receipt size={40} className="opacity-20" />}
        message="Aún no hay gastos en este sobre."
        description="Cuando pagues un gasto con este sobre, aparecerá aquí."
        className="p-8"
      />
    );
  }

  return (
    <ul className="divide-border/50 divide-y">
      {expenses.map((expense) => {
        const partial = Number(expense.applied_amount) < Number(expense.amount);
        return (
          <li key={expense.transaction_id} className="flex items-center gap-3 py-3">
            <div className="min-w-0 flex-1">
              <p className="text-text truncate text-sm font-medium">
                {expense.description || expense.category_name || 'Sin descripción'}
              </p>
              <p className="text-text-muted text-xs">
                {formatDateLabel(expense.date, 'es-CO', timezone)}
                {expense.description && expense.category_name && ` · ${expense.category_name}`}
              </p>
            </div>
            <div className="shrink-0 text-right">
              <p className="text-text text-sm font-semibold tabular-nums">
                -{formatCurrency(Number(expense.amount), currency)}
              </p>
              {partial && (
                <p className="text-text-muted text-xs tabular-nums">
                  del sobre: {formatCurrency(Number(expense.applied_amount), currency)}
                </p>
              )}
            </div>
          </li>
        );
      })}
    </ul>
  );
}
