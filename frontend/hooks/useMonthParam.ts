'use client';

import { useMemo } from 'react';
import { useQueryParamState } from '@/hooks/useQueryParamState';
import {
  compareMonth,
  formatMonthLabel,
  formatMonthName,
  formatMonthParam,
  monthOfDay,
  monthRange as buildMonthRange,
  parseMonthParam,
  shiftMonth,
} from '@/lib/dateRanges';
import type { CalendarMonth, DateRange } from '@/lib/dateRanges';
import { todayInZone } from '@/lib/dates';
import { useTimezone } from '@/lib/hooks/useTimezone';

/**
 * Fase 29 §F5.1 (Q6, H10, supuesto 3): validador read-time de `?month=YYYY-MM`, mismo patrón
 * que `validateDateParam` de transactions/page.tsx (Fase 13 §13.6). Un link con `?month=basura`,
 * `?month=2026-13` o con un mes futuro devuelve el mes actual en vez de dejar la vista rota
 * (User Story 8); la URL no se reescribe con el valor corregido, el re-normalizado por render
 * alcanza. Cubre los 422 de `core/periods.resolver_mes` (H13) antes de pedirle el mes al server.
 */
const validateMonthParam = (raw: string, current: CalendarMonth): string => {
  const parsed = parseMonthParam(raw);
  if (!parsed || compareMonth(parsed, current) > 0) {
    return formatMonthParam(current);
  }
  return raw;
};

export interface MonthParamState {
  year: number;
  month: number;
  isCurrentMonth: boolean;
  /** Fase 29 H10: `undefined` en el mes en curso (el reloj del navegador puede ir atrasado en
   *  el cambio de mes y daría un 422 falso); `'YYYY-MM'` en cualquier otro. Segmento de key. */
  apiMonth: string | undefined;
  /** Params `{ year, month }` para el API; `undefined` en el mes en curso (H10). */
  periodParams: { year: number; month: number } | undefined;
  /** Rango del mes visible como días `YYYY-MM-DD` (Fase 34 F3). */
  monthRange: Pick<DateRange, 'start_date' | 'end_date'>;
  monthLabel: string;
  monthNameLower: string;
  /** Día de hoy en la zona del usuario. */
  today: string;
  displayTimezone: string;
  /** `false` hasta que se conoce la zona del usuario (Fase 34 F1). */
  ready: boolean;
  onPrev: () => void;
  onNext: () => void;
  /** Vuelve al mes en curso (borra `?month=`). */
  onReset: () => void;
}

/**
 * Fase 40 D10: mes visible en `?month=YYYY-MM`, compartido por el dashboard y el detalle de
 * categoría. El default (mes en curso) nunca se escribe en la URL (User Story 7).
 *
 * El piso del `◀` (D18, `summary.first_transaction_month`) se pasa a `MonthNavigator`: depende de
 * una query que a su vez necesita `apiMonth`/`periodParams` de este hook, así que no puede
 * entrar aquí sin una dependencia circular.
 */
export function useMonthParam(): MonthParamState {
  const { displayTimezone, ready } = useTimezone();
  const today = todayInZone(displayTimezone);
  const { year: currentYear, month: currentMonth } = monthOfDay(today);

  const [monthParam, setMonthParam] = useQueryParamState('month', '', (raw) =>
    validateMonthParam(raw, { year: currentYear, month: currentMonth })
  );

  // `?? {...}` defensivo: `validateMonthParam` ya garantiza un valor parseable.
  const selectedMonth = parseMonthParam(monthParam) ?? { year: currentYear, month: currentMonth };
  const { year, month } = selectedMonth;
  const isCurrentMonth = year === currentYear && month === currentMonth;

  const apiMonth = isCurrentMonth ? undefined : monthParam;
  const periodParams = isCurrentMonth ? undefined : { year, month };

  const monthRange = useMemo(() => buildMonthRange(year, month, today), [year, month, today]);

  // User Story 7: si `▶` aterriza en el mes actual se borra `?month=` en vez de escribirlo.
  const onNext = () => {
    const target = shiftMonth(selectedMonth, 1);
    const isTargetCurrent = compareMonth(target, { year: currentYear, month: currentMonth }) >= 0;
    setMonthParam(isTargetCurrent ? '' : formatMonthParam(target));
  };

  return {
    year,
    month,
    isCurrentMonth,
    apiMonth,
    periodParams,
    monthRange,
    monthLabel: formatMonthLabel(year, month),
    monthNameLower: formatMonthName(year, month),
    today,
    displayTimezone,
    ready,
    onPrev: () => setMonthParam(formatMonthParam(shiftMonth(selectedMonth, -1))),
    onNext,
    onReset: () => setMonthParam(''),
  };
}
