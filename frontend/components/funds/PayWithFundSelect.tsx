'use client';

import Select from '@/components/ui/Select';
import { useFunds } from '@/lib/hooks/useFunds';
import { formatCurrency } from '@/lib/utils';

interface PayWithFundSelectProps {
  /** Cuenta elegida en el formulario (`''` si todavía no hay). */
  accountId: string;
  /** Sobre elegido (`''` = Ninguno). */
  value: string;
  onChange: (fundId: string) => void;
  /** Sobre ya enlazado a la transacción que se edita: se muestra aunque esté archivado. */
  linkedFundId?: number | null;
}

/**
 * Selector "Pagar con sobre" (Fase 36, D14). Solo se monta para gastos; no se pinta si la cuenta
 * no tiene sobres activos. Filtrar por cuenta/estado es presentación: cuánto se aplica lo decide
 * el backend. El formulario que lo usa limpia `value` al cambiar de tipo o de cuenta.
 */
export default function PayWithFundSelect({
  accountId,
  value,
  onChange,
  linkedFundId = null,
}: PayWithFundSelectProps) {
  const { data: funds } = useFunds({ includeArchived: linkedFundId !== null });

  const options =
    funds?.filter(
      (f) => String(f.account_id) === accountId && (f.status === 'active' || f.id === linkedFundId)
    ) ?? [];

  if (!accountId || options.length === 0) return null;

  return (
    <Select
      label="Pagar con sobre"
      value={value}
      onChange={(event) => onChange(event.target.value)}
      className="bg-background"
    >
      <option value="">Ninguno</option>
      {options.map((fund) => (
        <option key={fund.id} value={fund.id}>
          {fund.name} · {formatCurrency(Number(fund.balance), fund.currency)}
          {fund.status === 'archived' ? ' (archivado)' : ''}
        </option>
      ))}
    </Select>
  );
}
