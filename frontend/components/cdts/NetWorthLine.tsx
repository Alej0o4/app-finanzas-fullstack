'use client';

import Link from 'next/link';
import { formatCurrency } from '@/lib/utils';
import type { DashboardSummary } from '@/types/api';

interface NetWorthLineProps {
  summary: DashboardSummary;
  preferredCurrency: string;
}

/**
 * Fase 38 F4: línea secundaria "Patrimonio total" (cuentas + CDT vigentes). Todo viene del
 * servidor (`net_worth`, `cdt_total`); no suma nada aquí y nunca mezcla monedas.
 */
export default function NetWorthLine({ summary, preferredCurrency }: NetWorthLineProps) {
  const { net_worth, cdt_total } = summary;
  if (!net_worth || net_worth.length === 0) return null;

  const hasCdt = (cdt_total ?? []).some((b) => Number(b.total) !== 0);
  const primary = net_worth.find((b) => b.currency === preferredCurrency) ?? net_worth[0];
  const others = net_worth.filter((b) => b !== primary);
  const cdtOf = (currency: string) =>
    Number(cdt_total?.find((b) => b.currency === currency)?.total ?? 0);

  return (
    <div className="border-border bg-surface rounded-2xl border p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <p className="text-text-muted text-xs sm:text-sm">Patrimonio total</p>
        <p className="text-text text-lg font-bold tabular-nums">
          {formatCurrency(Number(primary.total), primary.currency)}
        </p>
      </div>
      <p className="text-text-muted mt-1 text-xs">
        {hasCdt ? (
          <>
            Cuentas + {formatCurrency(cdtOf(primary.currency), primary.currency)} en{' '}
            <Link href="/cdts" className="text-primary hover:text-primary/80 font-medium">
              CDT
            </Link>{' '}
            vigentes.
          </>
        ) : (
          'Saldo de tus cuentas; los CDT vigentes también suman aquí.'
        )}
      </p>
      {others.length > 0 && (
        <ul className="border-border/50 mt-2 space-y-1 border-t pt-2 text-xs">
          {others.map((b) => (
            <li key={b.currency} className="flex justify-between gap-2">
              <span className="text-text-muted font-medium">{b.currency}</span>
              <span className="text-text tabular-nums">
                {formatCurrency(Number(b.total), b.currency)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
