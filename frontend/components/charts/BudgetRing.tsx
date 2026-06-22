import { formatCurrency } from "@/lib/utils";
import { AlertCircle } from "lucide-react";

interface BudgetRingProps {
  categoryName: string;
  budgetAmount: number; // El límite (amount_limit en backend)
  spentAmount: number;  // Lo que se ha gastado
}

export default function BudgetRing({ categoryName, budgetAmount, spentAmount }: BudgetRingProps) {
  // Evitamos división por cero y limitamos el porcentaje máximo visual al 100%
  const safeBudget = budgetAmount > 0 ? budgetAmount : 1;
  const rawPercentage = (spentAmount / safeBudget) * 100;
  const percentage = Math.min(Math.max(rawPercentage, 0), 100);

  // Matemáticas orgánicas del SVG
  const radius = 45;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (percentage / 100) * circumference;

  // Lógica de colores semánticos
  const isDanger = percentage >= 90;
  const isWarning = percentage >= 75 && percentage < 90;
  
  const ringColorClass = isDanger 
    ? "text-danger" 
    : isWarning 
      ? "text-amber-500" 
      : "text-primary";

  return (
    <div className="bg-surface border border-neutral-800/60 rounded-2xl p-6 flex flex-col items-center justify-center relative group hover:border-neutral-700 transition-colors">
      
      {/* Icono de alerta si se superó el presupuesto */}
      {rawPercentage > 100 && (
        <div className="absolute top-4 right-4 text-danger animate-pulse" title="Presupuesto excedido">
          <AlertCircle size={18} />
        </div>
      )}

      {/* El Anillo SVG */}
      <div className="relative w-32 h-32 flex items-center justify-center">
        {/* Texto central */}
        <div className="absolute flex flex-col items-center justify-center text-center">
          <span className={`text-xl font-bold font-sans ${ringColorClass}`}>
            {percentage.toFixed(0)}%
          </span>
          <span className="text-[10px] text-text-muted uppercase tracking-wider">Gastado</span>
        </div>

        <svg className="w-full h-full transform -rotate-90" viewBox="0 0 100 100">
          {/* Pista de fondo (El límite total) */}
          <circle
            cx="50"
            cy="50"
            r={radius}
            className="text-neutral-800/50"
            strokeWidth="6"
            stroke="currentColor"
            fill="transparent"
          />
          {/* Línea de progreso (Lo gastado) */}
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

      {/* Información inferior */}
      <div className="mt-4 w-full text-center">
        <h3 className="font-medium text-text text-sm truncate">{categoryName}</h3>
        <div className="flex justify-between items-center mt-2 text-xs">
          <span className="text-text-muted">{formatCurrency(spentAmount)}</span>
          <span className="text-text-muted/50">/</span>
          <span className="text-text">{formatCurrency(budgetAmount)}</span>
        </div>
      </div>
    </div>
  );
}