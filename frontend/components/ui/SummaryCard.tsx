import { type ReactNode } from "react";
import { TrendingDown, TrendingUp } from "lucide-react";

interface SummaryCardProps {
  label: string;
  value?: string;
  children?: ReactNode;
  trend?: "up" | "down";
  color?: string;
}

export default function SummaryCard({
  label,
  value,
  children,
  trend,
  color,
}: SummaryCardProps) {
  return (
    <div
      className={`rounded-2xl border border-border bg-surface p-5 transition-all duration-200 hover:scale-[1.02] ${
        color ? `border-l-4` : ""
      }`}
      style={color ? { borderLeftColor: color } : undefined}
    >
      <p className="text-sm text-text-muted">{label}</p>
      <div className="mt-1 flex items-center gap-2">
        {children ? (
          <div className="text-2xl font-bold text-text">{children}</div>
        ) : (
          <p className="text-2xl font-bold text-text">{value}</p>
        )}
        {trend === "up" && <TrendingUp className="h-5 w-5 text-success" />}
        {trend === "down" && <TrendingDown className="h-5 w-5 text-danger" />}
      </div>
    </div>
  );
}
