'use client';

import { formatCurrency } from '@/lib/utils';
import { useAppConfig } from '@/providers/AppConfigProvider';
import { AlertCircle } from 'lucide-react';
import CategoryIcon from '@/components/ui/CategoryIcon';

interface BudgetRingProps {
  categoryName: string;
  budgetAmount: number;
  spentAmount: number;
  categoryIcon?: string | null;
}

export default function BudgetRing({
  categoryName,
  budgetAmount,
  spentAmount,
  categoryIcon,
}: BudgetRingProps) {
  const { config } = useAppConfig();
  // PROGRAMACIÓN DEFENSIVA: Si el valor es undefined, usamos 0.
  const safeSpent = Number(spentAmount) || 0;
  const safeBudget = Number(budgetAmount) > 0 ? Number(budgetAmount) : 1;

  const rawPercentage = (safeSpent / safeBudget) * 100;
  const percentage = Math.min(Math.max(rawPercentage, 0), 100);

  // Matemáticas orgánicas del SVG
  const radius = 45;
  const circumference = 2 * Math.PI * radius;

  // Ahora estamos 100% seguros de que percentage es un número válido
  const strokeDashoffset = circumference - (percentage / 100) * circumference;

  // ... (el resto del código se mantiene igual desde la línea de colores semánticos hacia abajo)
  const isDanger = percentage >= 90;
  const isWarning = percentage >= 75 && percentage < 90;

  const ringColorClass = isDanger ? 'text-danger' : isWarning ? 'text-warning' : 'text-primary';

  return (
    <div className="bg-surface border-border/70 group hover:border-text-muted/30 relative flex flex-col items-center justify-center rounded-2xl border p-4 transition-colors sm:p-6">
      {rawPercentage > 100 && (
        <div
          className="text-danger absolute top-3 right-3 animate-pulse sm:top-4 sm:right-4"
          title="Presupuesto excedido"
        >
          <AlertCircle size={18} />
        </div>
      )}

      <div className="relative flex h-24 w-24 items-center justify-center sm:h-32 sm:w-32">
        <div className="absolute flex flex-col items-center justify-center text-center">
          <span className={`font-sans text-lg font-bold sm:text-xl ${ringColorClass}`}>
            {percentage.toFixed(0)}%
          </span>
          <span className="text-text-muted text-[9px] tracking-wider uppercase sm:text-[10px]">Gastado</span>
        </div>

        <svg className="h-full w-full -rotate-90 transform" viewBox="0 0 100 100">
          <circle
            cx="50"
            cy="50"
            r={radius}
            className="text-border/80"
            strokeWidth="6"
            stroke="currentColor"
            fill="transparent"
          />
          <circle
            cx="50"
            cy="50"
            r={radius}
            className={`${ringColorClass} transition-all duration-1000 ease-out`}
            strokeWidth="6"
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="round"
            stroke="currentColor"
            fill="transparent"
          />
        </svg>
      </div>

      <div className="mt-3 w-full text-center sm:mt-4">
        <div className="flex items-center justify-center gap-1.5">
          <CategoryIcon icon={categoryIcon} size={16} />
          <h3 className="text-text truncate text-sm font-medium">{categoryName || 'Sin Nombre'}</h3>
        </div>
        <div className="mt-2 flex items-center justify-between text-xs">
          <span className="text-text-muted">{formatCurrency(safeSpent, config.currency)}</span>
          <span className="text-text-muted/60">/</span>
          <span className="text-text">
            {formatCurrency(
              safeBudget === 1 && budgetAmount === 0 ? 0 : safeBudget,
              config.currency
            )}
          </span>
        </div>
      </div>
    </div>
  );
}
