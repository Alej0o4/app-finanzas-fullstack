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
  // las monedas siempre muestra dos, salvo que se pida el modo entero para gráficos. Un
  // COP con centavos también va con dos ("$ 1.234,50", nunca "$ 1.234,5").
  const copSinCentavos = currency === 'COP' && Number.isInteger(Math.round(amount * 100) / 100);
  const minimumFractionDigits = options?.integer || copSinCentavos ? 0 : 2;
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

/**
 * Fase 33 F11 (QA-041): mayúscula solo en la primera letra. El `text-transform: capitalize` de
 * CSS que usaban los rótulos de fecha mayusculiza **cada palabra** — "03 De Oct De 2026, 05:55 P. M."
 * — así que el problema no era el CSS sino que no distingue "inicio de rótulo" de "palabra".
 */
export function capitalizeFirst(value: string): string {
  if (!value) return value;
  const trimmed = value.trim();
  if (!trimmed) return value;
  return trimmed.charAt(0).toUpperCase() + trimmed.slice(1);
}

/**
 * Fase 33 F11 (QA-041): `formatDate` + `capitalizeFirst`, para los rótulos que van en posición
 * de título. Es un helper aparte y no un `capitalize` dentro de `formatDate` a propósito: `formatDate`
 * es un formateador genérico de `Intl` con `options` opcional, y meterle una capitalización en el
 * default lo haría inconsistente (con `options` no se capitalizaría, sin ellos sí) y rompería la
 * expectativa de quien solo quiere la fecha cruda.
 */
export function formatDateLabel(isoString: string, locale = 'es-CO'): string {
  return capitalizeFirst(formatDate(isoString, locale));
}
