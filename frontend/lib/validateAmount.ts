// Fase 31 F2 (Q6, QA-013): límites del rango real de `Numeric(14,2)` — los mismos que
// valida el backend (B3 de la spec de Fase 31: 12 dígitos enteros, 2 decimales). Vive acá
// para que el mensaje aparezca ANTES de enviar, no solo cuando el 422 del servidor vuelve.
export const MAX_INTEGER_DIGITS = 12;
export const MAX_DECIMAL_PLACES = 2;

interface ValidateAmountOptions {
  /** `true` = el campo acepta 0 (ingreso esperado, saldo inicial); por default exige > 0
   *  (monto de transacción, límite de presupuesto). */
  allowZero?: boolean;
  /** `true` = un campo vacío no es un error (queda como "sin definir", ej. saldo inicial
   *  de una cuenta nueva, que por default vale 0 si se deja en blanco). Por default un
   *  campo vacío es un error, igual que hoy en los formularios que ya lo exigían. */
  allowEmpty?: boolean;
}

/**
 * Valida el TEXTO de un input de monto (no el `Number(...)`, para poder contar los
 * decimales exactos que escribió el usuario — `Number('1.234')` no distingue de
 * `Number('1.2340')`). Devuelve el mensaje de error en español, o `null` si el texto es
 * válido. Mismo criterio para vacío / no numérico / negativo (o cero) / más de 2
 * decimales / más de 12 dígitos enteros en todos los formularios que envían dinero.
 */
export function validateAmountText(value: string, options?: ValidateAmountOptions): string | null {
  const trimmed = value.trim();

  if (!trimmed) {
    return options?.allowEmpty ? null : 'Ingresa un monto.';
  }

  if (!/^-?\d+(\.\d+)?$/.test(trimmed)) {
    return 'Ingresa un monto válido.';
  }

  const isNegative = trimmed.startsWith('-');
  const unsigned = isNegative ? trimmed.slice(1) : trimmed;
  const [integerPart, decimalPart = ''] = unsigned.split('.');

  if (decimalPart.length > MAX_DECIMAL_PLACES) {
    return `El monto no puede tener más de ${MAX_DECIMAL_PLACES} decimales.`;
  }

  if (integerPart.length > MAX_INTEGER_DIGITS) {
    return `El monto no puede tener más de ${MAX_INTEGER_DIGITS} dígitos enteros.`;
  }

  const numeric = Number(trimmed);
  const minMessage = options?.allowZero
    ? 'El monto no puede ser negativo.'
    : 'Ingresa un monto mayor a cero.';

  if (options?.allowZero ? numeric < 0 : numeric <= 0) {
    return minMessage;
  }

  return null;
}
