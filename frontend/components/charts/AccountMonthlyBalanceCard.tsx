import SummaryCard from '@/components/ui/SummaryCard';
import Skeleton from '@/components/ui/Skeleton';
import { formatCurrency } from '@/lib/utils';

interface AccountMonthlyBalanceCardProps {
  label: string;
  balance: number;
  currency: string;
  isLoading: boolean;
}

/**
 * Balance del mes de una cuenta puntual (Fase 17 §17.1, Decisión 17.1.2).
 *
 * Puramente presentacional: recibe `balance` ya calculado por el backend
 * (GET /accounts/{id}/monthly-summary, campo `monthly_flow_balance`) y solo lo pinta — el
 * backend es la fuente de verdad del dato. Fase 19 §19.2.3 cerró el recalculo
 * (`income - expense`) que este componente hacía en cliente (Hallazgo 7 del spec).
 * Intencionalmente más simple que la card inline del dashboard: no describe un "sin definir"
 * posible (a diferencia de monthly_flow_balance del dashboard).
 */
export default function AccountMonthlyBalanceCard({
  label,
  balance,
  currency,
  isLoading,
}: AccountMonthlyBalanceCardProps) {
  // balance ya viene calculado por el backend — sin resta en cliente (Fase 19 §19.2.3,
  // cierra el Hallazgo 7 de docs/specs/fase_19_spec.md).
  const isPositive = balance >= 0;
  const trend = isPositive ? ('up' as const) : ('down' as const);
  const color = isPositive ? 'var(--color-success)' : 'var(--color-danger)';

  return (
    <SummaryCard label={label} size="lg" elevated trend={trend} color={color}>
      {isLoading ? (
        <Skeleton className="h-9 w-40" />
      ) : (
        <span className={isPositive ? '' : 'text-danger'}>{formatCurrency(balance, currency)}</span>
      )}
    </SummaryCard>
  );
}
