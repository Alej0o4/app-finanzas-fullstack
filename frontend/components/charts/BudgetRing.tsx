"use client";

import { formatCurrency } from "@/lib/utils";
import { useAppConfig } from "@/providers/AppConfigProvider";
import { AlertCircle } from "lucide-react";

interface BudgetRingProps {
  categoryName: string;
  budgetAmount: number; 
  spentAmount: number;  
}

export default function BudgetRing({ categoryName, budgetAmount, spentAmount }: BudgetRingProps) {
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
  
  const ringColorClass = isDanger 
    ? "text-danger" 
    : isWarning 
      ? "text-warning" 
      : "text-primary";

  return (
    <div className="bg-surface border border-border/70 rounded-2xl p-6 flex flex-col items-center justify-center relative group hover:border-text-muted/30 transition-colors">
      
      {rawPercentage > 100 && (
        <div className="absolute top-4 right-4 text-danger animate-pulse" title="Presupuesto excedido">
          <AlertCircle size={18} />
        </div>
      )}

      <div className="relative w-32 h-32 flex items-center justify-center">
        <div className="absolute flex flex-col items-center justify-center text-center">
          <span className={`text-xl font-bold font-sans ${ringColorClass}`}>
            {percentage.toFixed(0)}%
          </span>
          <span className="text-[10px] text-text-muted uppercase tracking-wider">Gastado</span>
        </div>

        <svg className="w-full h-full transform -rotate-90" viewBox="0 0 100 100">
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

      <div className="mt-4 w-full text-center">
        <h3 className="font-medium text-text text-sm truncate">{categoryName || "Sin Nombre"}</h3>
        <div className="flex justify-between items-center mt-2 text-xs">
          <span className="text-text-muted">{formatCurrency(safeSpent, config.currency)}</span>
          <span className="text-text-muted/60">/</span>
          <span className="text-text">{formatCurrency(safeBudget === 1 && budgetAmount === 0 ? 0 : safeBudget, config.currency)}</span>
        </div>
      </div>
    </div>
  );
}