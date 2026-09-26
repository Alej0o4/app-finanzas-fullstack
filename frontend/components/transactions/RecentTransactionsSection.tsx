'use client';

import { useMemo } from 'react';
import { keepPreviousData } from '@tanstack/react-query';
import { AlertCircle, PieChart } from 'lucide-react';
import Link from 'next/link';
import { formatCurrency, formatDate } from '@/lib/utils';
import { useTransactions } from '@/lib/hooks/useTransactions';
import { useAppConfig } from '@/providers/AppConfigProvider';
import Button from '@/components/ui/Button';
import EmptyState from '@/components/ui/EmptyState';
import Skeleton from '@/components/ui/Skeleton';
import type { DateRange } from '@/lib/dateRanges';

interface RecentTransactionsSectionProps {
  /** Rango ISO del mes visible, ya anclado en UTC por `utcMonthRange` (Fase 29 §F1). */
  range: Pick<DateRange, 'start_date' | 'end_date'>;
  /** Nombre del mes en minúscula (`"agosto"`): título, subtítulo y mensajes lo nombran. */
  monthName: string;
  /** Link a `/transactions` filtrado al mes completo (trae `preset=custom`, H5). */
  viewAllHref: string;
}

/**
 * "Últimas 5 del mes" del dashboard (Fase 29 §F5.5).
 *
 * Antes era un `useQuery` inline contra `queryKeys.dashboard.recentTransactions()`, que solo se
 * invalidaba al crear transacciones (H8): editar o borrar dejaba la lista vieja. Ahora usa
 * `useTransactions`, que comparte la key `transactions.all()` que ya invalidan todas las
 * mutaciones, y acota por el rango del mes visible.
 *
 * Componente propio (riesgo R2 de la spec) para que la página no crezca: la lista, sus estados
 * de carga/error/vacío y el link "Ver todas" no dependen de nada del resto del dashboard.
 */
export default function RecentTransactionsSection({
  range,
  monthName,
  viewAllHref,
}: RecentTransactionsSectionProps) {
  const { config } = useAppConfig();

  // `useMemo` porque `params` entra en la query key: un objeto nuevo en cada render
  // generaría una key distinta y un refetch por render.
  const params = useMemo(
    () => ({ limit: 5, start_date: range.start_date, end_date: range.end_date }),
    [range.start_date, range.end_date]
  );

  const { data, isLoading, isError, refetch } = useTransactions(params, {
    // Fase 29 §F5.1 (User Story 9): la lista no vuelve al skeleton al navegar de mes.
    placeholderData: keepPreviousData,
  });

  const transactions = data?.items ?? [];

  return (
    <div>
      <div className="mb-6 flex items-center justify-between gap-3">
        <div>
          <h2 className="text-text font-sans text-xl font-bold">Últimas 5 de {monthName}</h2>
          <p className="text-text-muted mt-1 text-sm">Movimientos registrados en {monthName}.</p>
        </div>
        <Link
          href={viewAllHref}
          className="text-primary hover:text-primary-dark shrink-0 text-sm font-medium transition-colors"
        >
          Ver todas
        </Link>
      </div>

      <div className="bg-surface border-border/70 shadow-background/20 overflow-hidden rounded-3xl border shadow-sm">
        {isLoading ? (
          <div className="divide-border/40 divide-y">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="flex items-center justify-between gap-4 p-4 sm:px-6">
                <div className="flex items-center gap-3">
                  <Skeleton className="h-10 w-10 rounded-full" />
                  <div className="space-y-2">
                    <Skeleton className="h-4 w-40" />
                    <Skeleton className="h-3 w-24" />
                  </div>
                </div>
                <Skeleton className="h-5 w-20" />
              </div>
            ))}
          </div>
        ) : isError ? (
          <EmptyState
            icon={<AlertCircle size={48} className="opacity-20" />}
            message={`No se pudieron cargar las transacciones de ${monthName}.`}
            action={
              <Button variant="secondary" size="sm" onClick={() => refetch()}>
                Reintentar
              </Button>
            }
          />
        ) : transactions.length === 0 ? (
          <EmptyState
            icon={<PieChart size={48} className="opacity-20" />}
            message={`No hay transacciones en ${monthName}.`}
          />
        ) : (
          <div className="divide-border/40 divide-y">
            {transactions.map((tx) => {
              const isExpense = tx.type === 'expense';

              return (
                <div
                  key={tx.id}
                  className="hover:bg-surface-elevated flex items-center justify-between gap-3 p-3 transition-colors sm:gap-4 sm:p-4 sm:px-6"
                >
                  <div className="min-w-0">
                    <p className="text-text truncate text-sm font-medium">{tx.description}</p>
                    <p className="text-text-muted mt-0.5 text-xs capitalize">
                      {formatDate(tx.date, config.locale)}
                    </p>
                  </div>
                  <p
                    className={`shrink-0 font-sans text-sm font-semibold tabular-nums sm:text-base ${isExpense ? 'text-text' : 'text-primary'}`}
                  >
                    {isExpense ? '-' : '+'}
                    {/* Fase 29 §F5.5 (Q10): la moneda es la de la transacción, no la
                        preferida global — un gasto de 20 USD salía como $20 COP. Mismo
                        criterio que TransactionList.tsx. */}
                    {formatCurrency(tx.amount, tx.currency)}
                  </p>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
