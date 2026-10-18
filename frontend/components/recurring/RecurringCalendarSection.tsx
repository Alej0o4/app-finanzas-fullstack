'use client';

import QueryErrorState from '@/components/ui/QueryErrorState';
import Skeleton from '@/components/ui/Skeleton';
import {
  Chip,
  formatDay,
  formatMonthLabel,
  money,
} from '@/components/recurring/recurringPresentation';
import { useRecurringCalendar } from '@/lib/hooks/useRecurring';

/** Calendario de 12 meses. Todo (ocurrencias, totales por moneda, `monthly_commitment`) lo
 *  proyecta el backend; el frontend no calcula fechas ni suma montos. */
export default function RecurringCalendarSection() {
  const { data: calendar, isLoading, isError, refetch } = useRecurringCalendar();
  const hasItems = calendar?.months.some((m) => m.items.length > 0) ?? false;

  return (
    <section aria-labelledby="recurring-calendar-title" className="space-y-3">
      <h2 id="recurring-calendar-title" className="text-text text-lg font-bold">
        Calendario de 12 meses
      </h2>

      {isLoading ? (
        <Skeleton className="h-40" />
      ) : isError ? (
        <QueryErrorState message="No se pudo cargar el calendario." onRetry={() => refetch()} />
      ) : !calendar || !hasItems ? (
        <p className="text-text-muted text-sm">
          Cuando tengas reglas activas verás aquí lo que viene en los próximos 12 meses.
        </p>
      ) : (
        <>
          {calendar.monthly_commitment.length > 0 && (
            <div className="border-border bg-surface rounded-2xl border p-4">
              <p className="text-text-muted text-xs sm:text-sm">
                Compromiso mensual en gastos recurrentes
              </p>
              <ul className="mt-1 space-y-0.5">
                {calendar.monthly_commitment.map((c) => (
                  <li key={c.currency} className="text-text text-xl font-bold tabular-nums">
                    {money(c.amount, c.currency)}{' '}
                    <span className="text-text-muted text-xs font-normal">{c.currency} al mes</span>
                  </li>
                ))}
              </ul>
              <p className="text-text-muted mt-1 text-xs">
                Es informativo: los cargos anuales se reparten en 12 y no cambian tu disponible.
              </p>
            </div>
          )}

          <ol className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
            {calendar.months.map((month) => (
              <li key={month.month} className="border-border bg-surface rounded-2xl border p-4">
                <h3 className="text-text font-semibold">{formatMonthLabel(month.month)}</h3>
                {month.items.length === 0 ? (
                  <p className="text-text-muted mt-2 text-xs">Sin cargos ni ingresos.</p>
                ) : (
                  <>
                    <ul className="mt-2 space-y-2">
                      {month.items.map((item, index) => (
                        <li
                          key={`${item.rule_id}-${item.date}-${index}`}
                          className="flex items-start justify-between gap-2 text-sm"
                        >
                          <div className="min-w-0">
                            <p className="text-text truncate">{item.name}</p>
                            <div className="mt-0.5 flex flex-wrap items-center gap-1.5">
                              <span className="text-text-muted text-xs">
                                {formatDay(item.date)}
                              </span>
                              {item.is_annual && <Chip tone="primary">Anual</Chip>}
                              {item.is_overdue && <Chip tone="danger">Vencida</Chip>}
                            </div>
                          </div>
                          <span
                            className={`shrink-0 tabular-nums ${item.type === 'income' ? 'text-success' : 'text-text'}`}
                          >
                            {item.type === 'income' ? '+' : '−'}
                            {money(item.amount, item.currency)}
                          </span>
                        </li>
                      ))}
                    </ul>
                    <dl className="border-border/50 mt-3 space-y-1 border-t pt-2 text-xs">
                      {month.totals.map((t) => (
                        <div key={t.currency} className="flex flex-wrap justify-between gap-x-2">
                          <dt className="text-text-muted">{t.currency}</dt>
                          <dd className="text-text-muted tabular-nums">
                            {Number(t.income) !== 0 && (
                              <span className="text-success">+{money(t.income, t.currency)} </span>
                            )}
                            {Number(t.expense) !== 0 && (
                              <span>−{money(t.expense, t.currency)} </span>
                            )}
                            <span className="text-text font-medium">
                              = {money(t.net, t.currency)}
                            </span>
                          </dd>
                        </div>
                      ))}
                    </dl>
                  </>
                )}
              </li>
            ))}
          </ol>
        </>
      )}
    </section>
  );
}
