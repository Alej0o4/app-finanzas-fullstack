'use client';

import Link from 'next/link';
import { useFunds } from '@/lib/hooks/useFunds';
import { ChevronRight, Mail } from 'lucide-react';
import Skeleton from '@/components/ui/Skeleton';
import { formatCurrency } from '@/lib/utils';
import type { BalanceByCurrency, DashboardSummary } from '@/types/api';

interface AvailableCardProps {
  summary: DashboardSummary;
  preferredCurrency: string;
  /** `true` mientras se muestra el placeholder del mes anterior (la foto de hoy no cambia,
   *  pero se evita un salto visual al navegar). */
  isStale?: boolean;
}

const totalOf = (list: BalanceByCurrency[], currency: string) =>
  Number(list.find((b) => b.currency === currency)?.total ?? 0);

/**
 * Fase 35 F5: tarjeta SECUNDARIA "Disponible real" (saldo de cuentas - apartado en sobres). El
 * flujo mensual sigue siendo la cifra principal. Todo viene del servidor, nada se resta aquí.
 */
export default function AvailableCard({
  summary,
  preferredCurrency,
  isStale = false,
}: AvailableCardProps) {
  const { accounts_total, committed, free_to_spend } = summary;
  // "Tiene sobres" = hay sobres activos, no que haya algo apartado: uno recién creado (o vaciado)
  // tiene committed 0 y aun así la tarjeta debe mostrar el disponible real.
  // El estado vacío solo se muestra cuando la lista cargó y de verdad está vacía: mientras
  // carga (o si falla) se muestra el disponible real, que ya viene en el summary.
  const { data: funds, isSuccess } = useFunds();
  const hasFunds = !isSuccess || funds.length > 0 || committed.some((b) => Number(b.total) !== 0);

  // Moneda preferida primero (el backend ya ordena así); el resto, como filas secundarias.
  const primary =
    free_to_spend.find((b) => b.currency === preferredCurrency) ?? free_to_spend[0] ?? null;
  const others = free_to_spend.filter((b) => b !== primary);

  if (!hasFunds) {
    return (
      <div className="border-border bg-surface flex h-full flex-col justify-center gap-2 rounded-2xl border border-dashed p-4">
        <p className="text-text-muted text-xs sm:text-sm">Disponible real</p>
        <p className="text-text-muted text-sm">
          Aparta dinero para gastos futuros y verás aquí cuánto es realmente tuyo para gastar.
        </p>
        <Link
          href="/funds"
          className="text-primary hover:text-primary/80 inline-flex items-center gap-1 text-sm font-medium"
        >
          Crea tu primer sobre
          <ChevronRight size={14} aria-hidden="true" />
        </Link>
      </div>
    );
  }

  const currency = primary?.currency ?? preferredCurrency;
  const free = Number(primary?.total ?? 0);
  const isNegative = free < 0;
  const anyNegative = free_to_spend.some((b) => Number(b.total) < 0);

  return (
    <div className="border-border bg-surface h-full rounded-2xl border p-4">
      <div className="flex items-center justify-between gap-2">
        <p className="text-text-muted text-xs sm:text-sm">Disponible real</p>
        <Link
          href="/funds"
          className="text-primary hover:text-primary/80 inline-flex items-center gap-1 text-xs font-medium"
        >
          <Mail size={12} aria-hidden="true" />
          Ver sobres
        </Link>
      </div>

      {isStale ? (
        <Skeleton className="mt-2 h-8 w-40" />
      ) : (
        <p
          className={`mt-1 text-xl font-bold tabular-nums sm:text-2xl ${isNegative ? 'text-danger' : 'text-text'}`}
        >
          {formatCurrency(free, currency)}
        </p>
      )}

      <dl className="text-text-muted mt-3 space-y-1 text-xs">
        <div className="flex justify-between gap-2">
          <dt>Saldo en cuentas</dt>
          <dd className="text-text tabular-nums">
            {formatCurrency(totalOf(accounts_total, currency), currency)}
          </dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt>− Apartado en sobres</dt>
          <dd className="text-text tabular-nums">
            {formatCurrency(totalOf(committed, currency), currency)}
          </dd>
        </div>
      </dl>

      {isNegative && (
        <p role="status" className="bg-danger/10 text-text mt-3 rounded-xl p-2.5 text-xs">
          Estás usando plata apartada en tus sobres. No pasa nada: revisa si quieres reponerla o
          ajustar tus aportes.
        </p>
      )}

      {others.length > 0 && (
        <div className="border-border/50 mt-3 space-y-3 border-t pt-3">
          {others.map((b) => {
            const negative = Number(b.total) < 0;
            return (
              <div key={b.currency} className="space-y-1 text-xs">
                <div className="flex justify-between gap-2">
                  <span className="text-text-muted font-medium">{b.currency}</span>
                  <span
                    className={`font-medium tabular-nums ${negative ? 'text-danger' : 'text-text'}`}
                  >
                    {formatCurrency(Number(b.total), b.currency)}
                  </span>
                </div>
                <dl className="text-text-muted space-y-1">
                  <div className="flex justify-between gap-2">
                    <dt>Saldo en cuentas</dt>
                    <dd className="text-text tabular-nums">
                      {formatCurrency(totalOf(accounts_total, b.currency), b.currency)}
                    </dd>
                  </div>
                  <div className="flex justify-between gap-2">
                    <dt>− Apartado en sobres</dt>
                    <dd className="text-text tabular-nums">
                      {formatCurrency(totalOf(committed, b.currency), b.currency)}
                    </dd>
                  </div>
                </dl>
              </div>
            );
          })}
        </div>
      )}

      {!isNegative && anyNegative && (
        <p role="status" className="text-text-muted mt-2 text-xs">
          En otra moneda estás usando plata apartada en tus sobres.
        </p>
      )}
    </div>
  );
}
