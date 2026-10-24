import { formatCurrency } from '@/lib/utils';
import type { Account, TransferWarning } from '@/types/api';

/** Copy del aviso `BELOW_COMMITTED` (Fase 39, D6). Los montos los calculó el backend; aquí solo
 *  se formatean. No bloquea nada: la transferencia ya se guardó. */
export function transferWarningText(warning: TransferWarning, accounts?: Account[]): string {
  const name = accounts?.find((a) => a.id === warning.account_id)?.name ?? 'una cuenta';
  return (
    `${name} quedó con ${formatCurrency(Number(warning.balance_after), warning.currency)}, ` +
    `por debajo de lo comprometido en sobres (${formatCurrency(Number(warning.committed), warning.currency)}).`
  );
}
