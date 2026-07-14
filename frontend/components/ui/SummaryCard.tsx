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
      className={`border-border bg-surface rounded-2xl border p-5 transition-all duration-200 hover:scale-[1.02] ${
        color ? `border-l-4` : ''
      }`}
      style={color ? { borderLeftColor: color } : undefined}
    >
      <p className="text-text-muted text-sm">{label}</p>
      <div className="mt-1 flex items-center gap-2">
        {children ? (
          <div className="text-text text-2xl font-bold">{children}</div>
        ) : (
          <p className="text-text text-2xl font-bold">{value}</p>
        )}
        {trend === 'up' && <TrendingUp className="text-success h-5 w-5" />}
        {trend === 'down' && <TrendingDown className="text-danger h-5 w-5" />}
      </div>
    </div>
  );
}
