import type { QueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/lib/queryKeys';
import { formatCurrency } from '@/lib/formatters';
import type { Fund, Transaction } from '@/types/api';

/** Nombre de un sobre leído del caché de TanStack (la lista, con o sin archivados). */
function fundNameFromCache(queryClient: QueryClient, fundId: number): string | undefined {
  const lists = queryClient.getQueriesData<Fund[]>({ queryKey: queryKeys.funds.all() });
  for (const [, funds] of lists) {
    const found = funds?.find((f) => f.id === fundId);
    if (found) return found.name;
  }
  return undefined;
}

/**
 * Fase 36 (D14): texto del aviso tras guardar un gasto, a partir de lo que respondió el backend.
 * Devuelve `undefined` si el gasto no tuvo que ver con un sobre.
 *
 * - `requestedFundId`: sobre que el usuario eligió en el formulario (para detectar el caso
 *   "pediste sobre pero estaba en 0", donde la respuesta trae `fund_id: null`).
 * - `previous`: en una edición, el enlace que tenía antes la transacción.
 * - La única cuenta del lado del cliente es `amount − fund_applied_amount`, y solo para el
 *   texto (en centavos enteros, sin acumular flotantes); el backend sigue siendo la fuente de
 *   verdad de lo aplicado.
 */
export function fundSpendNotice(
  queryClient: QueryClient,
  tx: Transaction,
  requestedFundId?: number | null,
  previous?: Pick<Transaction, 'fund_id' | 'fund_applied_amount'> | null
): string | undefined {
  // Edición: si el enlace y lo aplicado no cambiaron (p. ej. solo se editó la descripción),
  // no se avisa que "salió dinero del sobre": no se movió nada.
  if (
    previous &&
    previous.fund_id === tx.fund_id &&
    Number(previous.fund_applied_amount ?? 0) === Number(tx.fund_applied_amount ?? 0)
  ) {
    return undefined;
  }
  if (tx.fund_id != null) {
    const name = fundNameFromCache(queryClient, tx.fund_id);
    const appliedCents = Math.round(Number(tx.fund_applied_amount ?? 0) * 100);
    const amountCents = Math.round(Number(tx.amount) * 100);
    const where = name ? `del sobre «${name}»` : 'del sobre';
    let text = `${formatCurrency(appliedCents / 100, tx.currency)} salieron ${where}`;
    if (appliedCents < amountCents) {
      text += ` y ${formatCurrency((amountCents - appliedCents) / 100, tx.currency)} salieron del disponible libre`;
    }
    return text;
  }
  if (requestedFundId != null && tx.fund_applied_amount != null) {
    return 'El sobre no tenía saldo; el gasto se registró como gasto normal';
  }
  return undefined;
}
