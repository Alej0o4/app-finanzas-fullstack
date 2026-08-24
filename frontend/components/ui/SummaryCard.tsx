import { type ReactNode } from 'react';
import { TrendingDown, TrendingUp } from 'lucide-react';

interface SummaryCardProps {
  label: string;
  value?: string;
  children?: ReactNode;
  trend?: 'up' | 'down';
  color?: string;
  /** 'lg' eleva la jerarquía visual de la card principal (Fase 11 §11.3). Default 'md'. */
  size?: 'md' | 'lg';
}

export default function SummaryCard({
  label,
  value,
  children,
  trend,
  color,
  size = 'md',
}: SummaryCardProps) {
  const isLarge = size === 'lg';

  return (
    <div
      className={`border-border bg-surface rounded-2xl border transition-transform duration-200 hover:scale-[1.02] active:scale-100 max-sm:hover:scale-100 sm:hover:scale-[1.02] ${
        color ? 'border-l-4' : ''
      } ${isLarge ? 'p-5 sm:p-7' : 'p-4'}`}
      style={color ? { borderLeftColor: color } : undefined}
    >
      <p className={`text-text-muted ${isLarge ? 'text-sm sm:text-base' : 'text-xs sm:text-sm'}`}>
        {label}
      </p>
      <div className={`mt-1 flex min-w-0 items-center gap-2 ${isLarge ? 'sm:gap-3' : ''}`}>
        {children ? (
          <div
            className={`text-text min-w-0 font-bold ${
              isLarge ? 'text-3xl sm:text-4xl' : 'text-xl sm:text-2xl'
            }`}
          >
            {children}
          </div>
        ) : (
          <p
            className={`text-text min-w-0 font-bold ${
              isLarge ? 'text-3xl sm:text-4xl' : 'text-xl sm:text-2xl'
            }`}
          >
            {value}
          </p>
        )}
        {trend === 'up' && (
          <TrendingUp className={`text-success shrink-0 ${isLarge ? 'h-7 w-7' : 'h-5 w-5'}`} />
        )}
        {trend === 'down' && (
          <TrendingDown className={`text-danger shrink-0 ${isLarge ? 'h-7 w-7' : 'h-5 w-5'}`} />
        )}
      </div>
    </div>
  );
}
