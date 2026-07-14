export function formatCurrency(amount: number, currency = 'COP', locale = 'es-CO'): string {
  return new Intl.NumberFormat(locale, {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
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
