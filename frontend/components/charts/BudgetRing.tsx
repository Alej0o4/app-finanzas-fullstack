'use client';

import { formatCurrency } from '@/lib/utils';
import { useAppConfig } from '@/providers/AppConfigProvider';
import { AlertCircle } from 'lucide-react';
import CategoryIcon from '@/components/ui/CategoryIcon';

interface BudgetRingProps {
  categoryName: string;
  budgetAmount: number;
  spentAmount: number;
  /**
   * Fase 31 F9 (Q12, QA-012): porcentaje real, calculado por el backend
   * (`BudgetProgress.percentage`) — el componente ya no lo recalcula con `spent / limit`
   * (regla de `CLAUDE.md`: no recomputar agregados del backend en el cliente). El texto
   * muestra este valor redondeado, sin tope (106%, no 100%).
   */
  percentage: number;
  categoryIcon?: string | null;
  /** Moneda real del presupuesto (Fase 11 §11.1). Si se omite, cae a la preferida global. */
  currency?: string;
}

export default function BudgetRing({
  categoryName,
  budgetAmount,
  spentAmount,
  percentage,
  categoryIcon,
  currency,
}: BudgetRingProps) {
  const { config } = useAppConfig();
  // PROGRAMACIÓN DEFENSIVA: Si el valor es undefined, usamos 0.
  const safeSpent = Number(spentAmount) || 0;
  const safeBudget = Number(budgetAmount) > 0 ? Number(budgetAmount) : 1;
  const safePercentage = Number(percentage) || 0;

  // Matemáticas orgánicas del SVG
  const radius = 45;
  const circumference = 2 * Math.PI * radius;

  // Fase 31 F9 (Q16): primera vuelta topada en 100%, segunda vuelta superpuesta con el
  // exceso (percentage − 100), topada en 100% adicional (200% visual máximo) — el texto
  // sigue mostrando el valor real sin tope.
  const firstLapPercentage = Math.min(Math.max(safePercentage, 0), 100);
  const secondLapPercentage = Math.min(Math.max(safePercentage - 100, 0), 100);
  const isOverBudget = safePercentage > 100;

  const firstLapOffset = circumference - (firstLapPercentage / 100) * circumference;
  const secondLapOffset = circumference - (secondLapPercentage / 100) * circumference;

  // Alineado con el motor de alertas (§13.3/Decisión 13.4.1): 80% = warning, 100% = danger.
  const isDanger = safePercentage >= 100;
  const isWarning = safePercentage >= 80 && safePercentage < 100;

  const ringColorClass = isDanger ? 'text-danger' : isWarning ? 'text-warning' : 'text-primary';

  return (
    <div className="bg-surface border-border/70 group hover:border-text-muted/30 relative flex flex-col items-center justify-center rounded-2xl border p-4 transition-colors sm:p-6">
      {isOverBudget && (
        <div
          className="text-danger absolute top-3 right-3 animate-pulse sm:top-4 sm:right-4"
          title="Presupuesto excedido"
        >
          <AlertCircle size={18} />
        </div>
      )}

      <div className="relative flex h-24 w-24 items-center justify-center sm:h-32 sm:w-32">
        <div className="absolute flex flex-col items-center justify-center text-center">
          <span className={`font-sans text-lg font-bold tabular-nums sm:text-xl ${ringColorClass}`}>
            {safePercentage.toFixed(0)}%
          </span>
          <span className="text-text-muted text-[9px] tracking-wider uppercase sm:text-[10px]">
            Gastado
          </span>
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
            className={`${ringColorClass} transition-[stroke-dashoffset] duration-1000 ease-out`}
            strokeWidth="6"
            strokeDasharray={circumference}
            strokeDashoffset={firstLapOffset}
            strokeLinecap="round"
            stroke="currentColor"
            fill="transparent"
          />
          {/* Fase 31 F9 (Q16): segunda vuelta superpuesta, en --color-danger-strong, solo
              cuando el gasto pasa de 100% — el exceso dibujado encima de la primera vuelta
              ya completa. */}
          {isOverBudget && (
            <circle
              cx="50"
              cy="50"
              r={radius}
              className="text-danger-strong transition-[stroke-dashoffset] duration-1000 ease-out"
              strokeWidth="6"
              strokeDasharray={circumference}
              strokeDashoffset={secondLapOffset}
              strokeLinecap="round"
              stroke="currentColor"
              fill="transparent"
            />
          )}
        </svg>
      </div>

      <div className="mt-3 w-full text-center sm:mt-4">
        <div className="flex items-center justify-center gap-1.5">
          <CategoryIcon icon={categoryIcon} size={16} />
          <h3 className="text-text truncate text-sm font-medium">{categoryName || 'Sin Nombre'}</h3>
        </div>
        <div className="mt-2 flex items-center justify-between text-xs">
          <span className="text-text-muted tabular-nums">
            {formatCurrency(safeSpent, currency ?? config.currency)}
          </span>
          <span className="text-text-muted/60">/</span>
          <span className="text-text tabular-nums">
            {formatCurrency(
              safeBudget === 1 && budgetAmount === 0 ? 0 : safeBudget,
              currency ?? config.currency
            )}
          </span>
        </div>
      </div>
    </div>
  );
}
