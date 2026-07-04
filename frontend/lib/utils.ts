export function getApiError(error: unknown): string {
  const detail = (error as { response?: { data?: { detail?: string } } }).response?.data?.detail;
  return detail || "Ocurrió un error inesperado";
}

export const formatCurrency = (amount: number) => {
  return new Intl.NumberFormat('es-CO', {
    style: 'currency',
    currency: 'COP',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
};

export const formatDate = (isoString: string) => {
  const date = new Date(isoString);
  
  return new Intl.DateTimeFormat('es-CO', {
    day: '2-digit',
    month: 'short',   // Mostrará "jun" en lugar de "06"
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: true      // Formato AM/PM para mayor legibilidad
  }).format(date);
};