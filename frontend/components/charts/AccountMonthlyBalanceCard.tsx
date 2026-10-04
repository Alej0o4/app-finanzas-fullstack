import SummaryCard from '@/components/ui/SummaryCard';
import Skeleton from '@/components/ui/Skeleton';
import { formatCurrency } from '@/lib/utils';
import QueryErrorState from '@/components/ui/QueryErrorState';

interface AccountMonthlyBalanceCardProps {
  label: string;
  balance: number;
  currency: string;
  isLoading: boolean;
  isError?: boolean;
  onRetry?: () => void;
}

/**
 * Balance del mes de una cuenta puntual (Fase 17 §17.1, Decisión 17.1.2).
 *
 * Puramente presentacional: recibe `balance` ya calculado por el backend
 * (GET /accounts/{id}/monthly-summary, campo `monthly_flow_balance`) y solo lo pinta — el
 * backend es la fuente de verdad del dato. Fase 19 §19.2.3 cerró el recalculo
 * (`income - expense`) que este componente hacía en cliente (Hallazgo 7 del spec).
 * Desde Fase 31 (Decisión B9) el balance del dashboard también es siempre real (nunca
 * "sin definir"), igual que este — el contraste que había acá quedó obsoleto.
 */
export default function AccountMonthlyBalanceCard({
  label,
  balance,
  currency,
  isLoading,
  isError,
  onRetry,
}: AccountMonthlyBalanceCardProps) {
  // balance ya viene calculado por el backend — sin resta en cliente (Fase 19 §19.2.3,
  // cierra el Hallazgo 7 de docs/specs/fase_19_spec.md).
  const isPositive = balance >= 0;
  const trend = isPositive ? ('up' as const) : ('down' as const);
  const color = isPositive ? 'var(--color-success)' : 'var(--color-danger)';

  if (isError) {
    return (
      <QueryErrorState
        message="No se pudo cargar el balance del mes. Intenta de nuevo más tarde."
        onRetry={onRetry}
      />
    );
  }

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
