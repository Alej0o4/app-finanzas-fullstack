interface FormatCurrencyOptions {
  /**
   * Fase 31 F7 (Q8, QA-007): fuerza 0 decimales (mínimo y máximo), para ejes/etiquetas
   * compactas de gráficos — hoy solo el eje Y de `CashflowChart`, su cálculo de ancho y
   * las etiquetas sobre las barras (`LabelList`). El resto de la app (incluidos los
   * tooltips del mismo gráfico) sigue mostrando decimales.
   */
  integer?: boolean;
}

export function formatCurrency(
  amount: number,
  currency = 'COP',
  locale = 'es-CO',
  options?: FormatCurrencyOptions
): string {
  // Fase 31 F7 (QA-007): antes se fijaba siempre en 0 decimales, así que un gasto de
  // US$ 0,10 se mostraba como "US$ 0". COP se lista explícito (el default de `Intl` para
  // COP es 2 decimales por ISO 4217, no lo que el dueño espera ver a diario); el resto de
  // las monedas siempre muestra dos, salvo que se pida el modo entero para gráficos.
  const minimumFractionDigits = options?.integer ? 0 : currency === 'COP' ? 0 : 2;
  const maximumFractionDigits = options?.integer ? 0 : 2;

  return new Intl.NumberFormat(locale, {
    style: 'currency',
    currency,
    minimumFractionDigits,
    maximumFractionDigits,
  }).format(amount);
}

export function formatDate(
  isoString: string,
  locale = 'es-CO',
  options?: Intl.DateTimeFormatOptions
): string {
  const date = new Date(isoString);

  return new Intl.DateTimeFormat(
    locale,
    options ?? {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      hour12: true,
    }
  ).format(date);
}
