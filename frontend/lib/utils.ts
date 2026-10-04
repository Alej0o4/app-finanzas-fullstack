export { formatCurrency, formatDate, capitalizeFirst, formatDateLabel } from './formatters';

interface PydanticErrorDetail {
  msg: string;
}

type ApiErrorDetail =
  | string
  | PydanticErrorDetail[]
  | { mensaje?: string; message?: string; msg?: string }
  | null
  | undefined;

const VALUE_ERROR_PREFIX = 'Value error, ';

/**
 * Fase 31 F1 (QA-004): aplana cualquier forma de `detail` que devuelva el backend a un
 * string legible. Nunca devuelve algo que no sea `string` — es lo que evita el "Objects
 * are not valid as a React child" cuando un 422 de Pydantic trae `detail` en lista.
 */
export function getApiError(error: unknown, fallback = 'Ocurrió un error inesperado'): string {
  const detail = (error as { response?: { data?: { detail?: ApiErrorDetail } } }).response?.data
    ?.detail;

  if (typeof detail === 'string' && detail) return detail;

  if (Array.isArray(detail) && detail.length > 0) {
    const joined = detail
      .map((d) =>
        d.msg.startsWith(VALUE_ERROR_PREFIX) ? d.msg.slice(VALUE_ERROR_PREFIX.length) : d.msg
      )
      .join(' ');
    if (joined) return joined;
  }

  if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
    const message = detail.mensaje || detail.message || detail.msg;
    if (message) return message;
  }

  return fallback;
}
