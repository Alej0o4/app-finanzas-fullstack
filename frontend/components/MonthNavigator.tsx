'use client';

import PeriodNavigator from '@/components/PeriodNavigator';
import type { MonthParamState } from '@/hooks/useMonthParam';
import { compareMonth, parseMonthParam } from '@/lib/dateRanges';

interface MonthNavigatorProps {
  state: MonthParamState;
  /** Piso del `◀` (D18), de `summary.first_transaction_month`: `undefined` = aún desconocido
   *  (no deshabilita), `null` = sin movimientos (deshabilita). */
  firstTransactionMonth?: string | null;
}

/**
 * Selector de mes `◀ Agosto 2026 ▶` ligado a `useMonthParam` (Fase 40 D10), compartido por el
 * dashboard y el detalle de categoría. "Volver a este mes" solo fuera del mes en curso.
 */
export default function MonthNavigator({ state, firstTransactionMonth }: MonthNavigatorProps) {
  // Q9: `◀` no baja del mes de la primera transacción.
  const floorMonth = firstTransactionMonth ? parseMonthParam(firstTransactionMonth) : null;
  const prevDisabled =
    floorMonth === null
      ? firstTransactionMonth === null
      : compareMonth({ year: state.year, month: state.month }, floorMonth) <= 0;

  return (
    <PeriodNavigator
      label={state.monthLabel}
      onPrev={state.onPrev}
      onNext={state.onNext}
      prevDisabled={prevDisabled}
      nextDisabled={state.isCurrentMonth}
      onReset={state.isCurrentMonth ? undefined : state.onReset}
    />
  );
}
