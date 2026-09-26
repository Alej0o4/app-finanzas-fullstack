'use client';

import { useMemo, useState } from 'react';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { Tags } from 'lucide-react';
import { api } from '@/lib/api';
import { queryKeys } from '@/lib/queryKeys';
import type { DateRange } from '@/lib/dateRanges';
import type { CategoryDistributionItem } from '@/types/api';
import CategoryBreakdownBars from '@/components/charts/CategoryBreakdownBars';
import SegmentedControl from '@/components/ui/SegmentedControl';

interface CategoryBreakdownSectionProps {
  /** Segmento de mes de la key de caché. `undefined` en el mes en curso (Fase 29 H7/H10). */
  monthKey?: string;
  /** Rango ISO del mes visible, ya anclado en UTC por `utcMonthRange` (Fase 29 §F1). */
  range: Pick<DateRange, 'start_date' | 'end_date'>;
  /** Monedas con gasto en el mes + la preferida, ya deduplicadas y con la preferida primera. */
  currencyOptions: string[];
  preferredCurrency: string;
  /** Mensaje de "sin gastos" que nombra el mes. `undefined` deja el texto genérico. */
  emptyMessage?: string;
}

/**
 * Sección "Gastos por Categoría" del dashboard (Fase 11 §11.4 + Fase 29 §F5.4): encabezado
 * con los chips de moneda y las barras del mes visible.
 *
 * Vive en su propio componente (riesgo R2 de la spec) porque arrastra su propia query, su
 * propio estado de selección de moneda y sus tres estados — el `CategoryBreakdownBars` de
 * hoy, que no sabe de meses, no puede hacerlo. El rango y las opciones de moneda los arma el
 * padre: la sección no sabe de dónde salen, solo los consume.
 */
export default function CategoryBreakdownSection({
  monthKey,
  range,
  currencyOptions,
  preferredCurrency,
  emptyMessage,
}: CategoryBreakdownSectionProps) {
  // `null` = "la preferida", no una copia de ella: el padre pasa `config.currency` mientras
  // `/users/me` no resolvió y la preferida real llega después (o cambia desde Ajustes). Un
  // `useState(preferredCurrency)` capturaría solo el primer valor y quedaría pegado a él.
  const [selectedCurrency, setSelectedCurrency] = useState<string | null>(null);
  // Supuesto 2: si la moneda elegida no tiene gastos en el mes visible, se vuelve a la
  // preferida — resuelto en el render, sin `useEffect` ni estado espejo. La selección sigue
  // guardada, así que volver al mes anterior la restaura sola.
  const currency =
    selectedCurrency && currencyOptions.includes(selectedCurrency)
      ? selectedCurrency
      : preferredCurrency;

  // `useMemo` para que el objeto de params no cambie de identidad en cada render: forma
  // parte de la query key a través de `queryKeys.dashboard.categoryBreakdown`.
  const params = useMemo(
    () => ({
      start_date: range.start_date,
      end_date: range.end_date,
      type: 'expense',
      currency,
    }),
    [range.start_date, range.end_date, currency]
  );

  const { data, isLoading, isError, refetch } = useQuery<CategoryDistributionItem[]>({
    queryKey: queryKeys.dashboard.categoryBreakdown(monthKey, currency),
    queryFn: async () => (await api.get('dashboard/category-distribution', { params })).data,
    // Fase 29 §F5.1 (User Story 9): al cambiar de mes las barras no vuelven al skeleton,
    // muestran las del mes anterior hasta que llegan las del nuevo.
    placeholderData: keepPreviousData,
  });

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Tags className="text-primary" size={20} />
          <h2 className="text-text font-sans text-xl font-bold">Gastos por Categoría</h2>
        </div>
        {/* Q4 / User Story 22: con una sola moneda los chips no se renderizan — un control
            con una única opción es ruido, y el mensaje de "sin gastos" alcanza para explicar
            por qué no hay nada que cambiar. */}
        {currencyOptions.length > 1 && (
          <SegmentedControl
            options={currencyOptions.map((value) => ({ value, label: value }))}
            value={currency}
            // Elegir la preferida vuelve a `null` en vez de fijar su código: así la selección
            // sigue a la preferida si esta cambia después.
            onChange={(next) => setSelectedCurrency(next === preferredCurrency ? null : next)}
            ariaLabel="Moneda de los gastos por categoría"
          />
        )}
      </div>

      <CategoryBreakdownBars
        data={data}
        isLoading={isLoading}
        isError={isError}
        onRetry={() => refetch()}
        currency={currency}
        emptyMessage={emptyMessage}
      />
    </div>
  );
}
