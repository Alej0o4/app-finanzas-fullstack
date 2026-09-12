import SummaryCard from '@/components/ui/SummaryCard';
import Skeleton from '@/components/ui/Skeleton';
import { formatCurrency } from '@/lib/utils';

interface AccountMonthlyBalanceCardProps {
  label: string;
  income: number;
  expense: number;
  currency: string;
  isLoading: boolean;
}

/**
 * Balance del mes de una cuenta puntual (Fase 17 §17.1, Decisión 17.1.2).
 *
 * Puramente presentacional: recibe `income`/`expense` ya calculados por el backend
 * (GET /accounts/{id}/monthly-summary) y solo resta para mostrar el balance — el backend es
 * la fuente de verdad del dato; este componente no describe un "sin definir" posible
 * (a diferencia de monthly_flow_balance del dashboard). Intencionalmente más simple que la
 * card inline del dashboard: Fase 19 decidirá si unifica ambos usos, no se anticipa ese
 * diseño aquí.
 */
export default function AccountMonthlyBalanceCard({
  label,
  income,
  expense,
  currency,
  isLoading,
}: AccountMonthlyBalanceCardProps) {
  const balance = income - expense;
  const isPositive = balance >= 0;
  const trend = isPositive ? ('up' as const) : ('down' as const);
  const color = isPositive ? 'var(--color-success)' : 'var(--color-danger)';

  return (
    <SummaryCard label={label} size="lg" elevated trend={trend} color={color}>
      {isLoading ? (
        <Skeleton className="h-9 w-40" />
      ) : (
        <span className={isPositive ? '' : 'text-danger'}>
          {formatCurrency(Number(balance), currency)}
        </span>
      )}
    </SummaryCard>
  );
}
