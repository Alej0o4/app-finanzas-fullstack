/**
 * Fase 34 §F2 — fechas en la zona horaria del usuario, solo con `Intl` (sin librería de fechas).
 *
 * El backend es el dueño de los límites de período (los interpreta en `User.timezone`); el
 * frontend solo necesita (a) saber "qué día es hoy" y "qué día es este instante" en esa zona para
 * armar días `YYYY-MM-DD`, y (b) formatear horas/fechas en esa zona. Nunca arma instantes UTC de
 * límite (H9).
 *
 * Módulo puro: sin React ni estado. `useTimezone` (lib/hooks) entrega la zona del usuario.
 */

/** Zona del dispositivo (para detectar en el registro y de respaldo mientras el usuario carga). */
export const deviceTimezone = (): string => {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
  } catch {
    return 'UTC';
  }
};

/** Zona usable por `Intl`: si el nombre no la reconoce (zona vieja/inventada) cae a la del
 *  dispositivo en vez de lanzar `RangeError` al renderizar. */
export const safeTimezone = (timezone: string | undefined | null): string => {
  if (!timezone) return deviceTimezone();
  try {
    new Intl.DateTimeFormat('en-CA', { timeZone: timezone });
    return timezone;
  } catch {
    return deviceTimezone();
  }
};

interface ZonedParts {
  year: number;
  month: number;
  day: number;
  hour: number;
}

const partsInZone = (instant: Date, timezone: string): ZonedParts => {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: safeTimezone(timezone),
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(instant);
  const pick = (type: string) => Number(parts.find((part) => part.type === type)?.value ?? 0);
  // `hourCycle: 'h23'` evita el "24" de medianoche que algunos motores devuelven con `hour12:false`.
  return { year: pick('year'), month: pick('month'), day: pick('day'), hour: pick('hour') % 24 };
};

const pad = (value: number, length = 2) => String(value).padStart(length, '0');

/** Día `YYYY-MM-DD` que contiene `instant` en `timezone`. */
export const dayInZone = (instant: Date | string, timezone: string): string => {
  const date = typeof instant === 'string' ? new Date(instant) : instant;
  if (Number.isNaN(date.getTime())) return '';
  const { year, month, day } = partsInZone(date, timezone);
  return `${pad(year, 4)}-${pad(month)}-${pad(day)}`;
};

/** "Hoy" (`YYYY-MM-DD`) en `timezone`. */
export const todayInZone = (timezone: string, now: Date = new Date()): string =>
  dayInZone(now, timezone);

/** Mes en curso en `timezone` (`month` 1..12). */
export const currentMonthInZone = (
  timezone: string,
  now: Date = new Date()
): { year: number; month: number } => {
  const { year, month } = partsInZone(now, timezone);
  return { year, month };
};

/** Hora del día (0..23) de `instant` en `timezone`. */
export const hourInZone = (timezone: string, instant: Date = new Date()): number =>
  partsInZone(instant, timezone).hour;
