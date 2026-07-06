export { formatCurrency, formatDate } from "./formatters";

export function getApiError(error: unknown): string {
  const detail = (error as { response?: { data?: { detail?: string } } }).response?.data?.detail;
  return detail || "Ocurrió un error inesperado";
}