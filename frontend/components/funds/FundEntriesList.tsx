import { ArrowDownRight, ArrowUpRight, History } from 'lucide-react';
import EmptyState from '@/components/ui/EmptyState';
import { formatCurrency, formatDateLabel } from '@/lib/utils';
import type { FundEntry } from '@/types/api';

const TYPE_LABELS: Record<FundEntry['type'], string> = {
  contribution: 'Aporte',
  withdrawal: 'Retiro',
  adjustment: 'Ajuste',
};

interface FundEntriesListProps {
  entries: FundEntry[];
  currency: string;
  timezone: string;
}

export default function FundEntriesList({ entries, currency, timezone }: FundEntriesListProps) {
  if (entries.length === 0) {
    return (
      <EmptyState
        icon={<History size={40} className="opacity-20" />}
        message="Aún no hay movimientos."
        description="Tus aportes y retiros aparecerán aquí."
        className="p-8"
      />
    );
  }

  return (
    <ul className="divide-border/50 divide-y">
      {entries.map((entry) => {
        const amount = Number(entry.amount);
        const positive = amount >= 0;
        const Icon = positive ? ArrowUpRight : ArrowDownRight;
        return (
          <li key={entry.id} className="flex items-center gap-3 py-3">
            <span
              className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full ${positive ? 'bg-success/10 text-success' : 'bg-danger/10 text-danger'}`}
            >
              <Icon size={16} aria-hidden="true" />
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-text truncate text-sm font-medium">
                {TYPE_LABELS[entry.type]}
                {entry.note && <span className="text-text-muted font-normal"> · {entry.note}</span>}
              </p>
              <p className="text-text-muted text-xs">
                {formatDateLabel(entry.occurred_at, 'es-CO', timezone)}
              </p>
            </div>
            <p
              className={`shrink-0 text-sm font-semibold tabular-nums ${positive ? 'text-success' : 'text-danger'}`}
            >
              {positive ? '+' : ''}
              {formatCurrency(amount, currency)}
            </p>
          </li>
        );
      })}
    </ul>
  );
}
