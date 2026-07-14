import { type ReactNode } from 'react';
import { TrendingDown, TrendingUp } from 'lucide-react';

interface SummaryCardProps {
  label: string;
  value?: string;
  children?: ReactNode;
  trend?: 'up' | 'down';
  color?: string;
}

export default function SummaryCard({ label, value, children, trend, color }: SummaryCardProps) {
  return (
    <div
      className={`border-border bg-surface rounded-2xl border p-4 transition-all duration-200 hover:scale-[1.02] max-sm:hover:scale-100 sm:hover:scale-[1.02] ${
        color ? `border-l-4` : ''
      }`}
      style={color ? { borderLeftColor: color } : undefined}
    >
      <p className="text-text-muted text-xs sm:text-sm">{label}</p>
      <div className="mt-1 flex min-w-0 items-center gap-2">
        {children ? (
          <div className="min-w-0 text-xl font-bold text-text sm:text-2xl">{children}</div>
        ) : (
          <p className="min-w-0 text-xl font-bold text-text sm:text-2xl">{value}</p>
        )}
        {trend === 'up' && <TrendingUp className="text-success h-5 w-5 shrink-0" />}
        {trend === 'down' && <TrendingDown className="text-danger h-5 w-5 shrink-0" />}
      </div>
    </div>
  );
}
