/**
 * Fase 29 §F1 — criterio de bordes de período en UTC, compartido por el dashboard, Analítica y
 * la vista por cuenta.
 *
 * Todos los límites de este módulo se anclan con `Date.UTC` (o con setters UTC), nunca con getters
 * locales (`getFullYear()`/`getMonth()`/`getDate()`). El backend guarda y compara las fechas en UTC
 * (sesión de Postgres en UTC), así que un límite armado con la hora local del navegador llega
 * desplazado por el offset de la zona (UTC-5 en Bogotá) y deja afuera las transacciones del
 * borde del período. Ese era el bug que hacía que el dashboard perdiera **toda** transacción
 * fechada el día 1 del mes (H4): el `TransactionModal` manda la fecha como `YYYY-MM-DD` y el
 * backend la guarda a las 00:00 UTC, así que el día 1 caía fuera del rango local desplazado.
 *
 * Módulo puro (sin React ni hooks) para poder usarse desde páginas, componentes y tests.
 */

export type AnalyticsPeriod = 'week' | 'month' | 'year' | 'custom';

/** Agrupación que el backend de `cashflow-series` acepta ('week' no está soportada). */
export type DateRangeGranularity = 'day' | 'month';

export interface UtcMonth {
  year: number;
  /** 1..12, igual que `Date#getUTCMonth() + 1`. */
  month: number;
}

export interface DateRange {
  start_date: string;
  end_date: string;
  granularity: DateRangeGranularity;
}

/** Períodos de calendario que se pueden navegar con `◀ ▶` (el personalizado no lo tiene). */
export type CalendarPeriod = Exclude<AnalyticsPeriod, 'custom'>;

const MS_PER_DAY = 24 * 60 * 60 * 1000;

/** Locale del proyecto (`preferred_locale` = `es-CO`). Fijo acá porque el módulo es puro y no
 *  puede leer `useAppConfig()`; los rótulos de período no dependen de la preferencia del usuario. */
const LOCALE = 'es-CO';

const MONTH_PARAM_PATTERN = /^(\d{4})-(\d{2})$/;
const DATE_PARAM_PATTERN = /^\d{4}-\d{2}-\d{2}$/;

const toDateParam = (date: Date): string => date.toISOString().slice(0, 10);

/** `YYYY-MM-DD` → instante UTC de las 00:00, o `null` si no existe en el calendario. */
const parseDateParam = (raw: string): Date | null => {
  if (!DATE_PARAM_PATTERN.test(raw)) return null;
  const date = new Date(`${raw}T00:00:00Z`);
  // `new Date('2026-02-31T00:00:00Z')` no es `NaN`: normaliza a marzo 3. El round-trip descarta
  // esas fechas en vez de "corregirlas" en silencio y analizarlas en el período equivocado.
  return toDateParam(date) === raw ? date : null;
};

/** Inicio del período de calendario (00:00:00.000Z) que contiene `date`. */
const periodStartUtc = (period: CalendarPeriod, date: Date): Date => {
  const start = new Date(date);
  if (period === 'week') {
    // Semana calendario lunes–domingo (Q13), no los últimos 7 días móviles: `getUTCDay()` es
    // 0 para domingo, así que el lunes de la semana está (día + 6) % 7 días atrás.
    start.setUTCDate(date.getUTCDate() - ((date.getUTCDay() + 6) % 7));
  } else if (period === 'month') {
    start.setUTCDate(1);
  } else {
    start.setUTCMonth(0, 1);
  }
  start.setUTCHours(0, 0, 0, 0);
  return start;
};

/** Fin del período **exclusivo** (00:00 del período siguiente, en UTC). */
const periodEndUtc = (period: CalendarPeriod, start: Date): Date => {
  const end = new Date(start);
  if (period === 'week') end.setUTCDate(end.getUTCDate() + 7);
  else if (period === 'month') end.setUTCMonth(end.getUTCMonth() + 1);
  else end.setUTCFullYear(end.getUTCFullYear() + 1);
  return end;
};

export const currentUtcMonth = (now: Date): UtcMonth => ({
  year: now.getUTCFullYear(),
  month: now.getUTCMonth() + 1,
});

/** Lee el query param `?month=YYYY-MM`. Devuelve `null` si no matchea el formato, si el mes está
 *  fuera de 1..12 o si el año es `< 1` — los 422 que responde el backend (H13), decididos acá
 *  para no pedir un mes que el servidor va a rechazar. */
export const parseMonthParam = (raw: string): UtcMonth | null => {
  const match = MONTH_PARAM_PATTERN.exec(raw);
  if (!match) return null;
  const year = Number(match[1]);
  const month = Number(match[2]);
  if (year < 1 || month < 1 || month > 12) return null;
  return { year, month };
};

/** Meses relativos con desborde de año (enero − 1 → diciembre del año anterior). */
export const shiftMonth = ({ year, month }: UtcMonth, delta: number): UtcMonth => {
  // Aritmética de índice absoluto de mes en vez de `Date.UTC`: `Date.UTC` mapea los años de dos
  // dígitos a 1900+año, así que un delta negativo sobre un año chico saldría del siglo XX.
  const absolute = year * 12 + (month - 1) + delta;
  return { year: Math.floor(absolute / 12), month: (((absolute % 12) + 12) % 12) + 1 };
};

/** Orden de períodos: negativo si `a` es anterior a `b`. */
export const compareMonth = (a: UtcMonth, b: UtcMonth): number =>
  a.year !== b.year ? a.year - b.year : a.month - b.month;

/**
 * Fin del día UTC que contiene `now` (23:59:59.999Z) — el techo del período en curso.
 *
 * No es "ahora" a propósito: las transacciones creadas sin `date` (el `/capture` de
 * `TransactionCaptureForm`, los atajos por API key) se guardan con el `now()` real del servidor,
 * no a las 00:00 UTC como las del `TransactionModal`. Un techo en el inicio del día las dejaba
 * afuera de las barras y de "Últimas 5" aunque la tarjeta del summary sí las contara, y un techo
 * en "ahora" congelado al montar las perdía después de un refetch. El fin del día las incluye y,
 * además, es estable durante todo el día: puede ir en una query key sin generar una key nueva
 * por render.
 */
export const endOfUtcDay = (now: Date): Date =>
  new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate(), 23, 59, 59, 999));

/** `YYYY-MM-DD` del día UTC que contiene `date`. Estable dentro del día: sirve de dependencia de
 *  memo para derivar un `now` que avanza al cambiar de día sin cambiar en cada render. */
export const utcDayKey = (date: Date): string => toDateParam(date);

/**
 * Rango ISO del mes pedido. El techo es el fin del día UTC de hoy (`endOfUtcDay`) en el mes en
 * curso y el último día del mes a las 23:59:59.999Z en un mes pasado. El backend corta el mes en
 * curso en "ahora" (`limites_mes_utc`, B1); la diferencia es solo lo fechado más tarde hoy, y a
 * cambio el rango no cambia en cada render ni deja afuera lo capturado hoy con hora real.
 */
export const utcMonthRange = (
  year: number,
  month: number,
  now: Date
): { start_date: string; end_date: string } => {
  // `Date.UTC` (no el constructor local `new Date(y, m, 1)`): un límite de calendario como
  // "inicio de mes" debe anclarse en UTC porque el backend guarda y compara fechas en UTC
  // (sesión de Postgres en UTC) — construirlo con getters locales lo desplaza por el offset de
  // la zona horaria del navegador y excluye transacciones del borde del período (H4).
  const start = new Date(Date.UTC(year, month - 1, 1));
  const isCurrentMonth = year === now.getUTCFullYear() && month === now.getUTCMonth() + 1;
  // `Date.UTC(y, month, 0)` es el día 0 del mes siguiente, o sea el último del pedido.
  const end = isCurrentMonth
    ? endOfUtcDay(now)
    : new Date(Date.UTC(year, month, 0, 23, 59, 59, 999));
  return { start_date: start.toISOString(), end_date: end.toISOString() };
};

/** `{ year, month }` → query param `YYYY-MM` (inverso de `parseMonthParam`). */
export const formatMonthParam = ({ year, month }: UtcMonth): string =>
  `${String(year).padStart(4, '0')}-${String(month).padStart(2, '0')}`;

/**
 * Link a `/transactions` filtrado al mes completo, para el "Ver todas" del dashboard.
 *
 * El fin es el último día del mes y no "hoy" a propósito: el link tiene que seguir apuntando al
 * mismo período mañana. En el mes en curso la lista igual solo muestra lo que hay registrado.
 */
export const monthTransactionsHref = (year: number, month: number): string => {
  const firstDay = new Date(Date.UTC(year, month - 1, 1));
  const lastDay = new Date(Date.UTC(year, month, 0));
  // `preset=custom` explícito: sin él, `/transactions` valida el preset contra su whitelist y cae
  // en 'all', dejando el chip "Todo el histórico" resaltado con un rango activo (H5).
  return `/transactions?start=${toDateParam(firstDay)}&end=${toDateParam(lastDay)}&preset=custom`;
};

/** Rótulo legible del período: `"Agosto 2026"`. */
export const formatMonthLabel = (year: number, month: number): string => {
  // Se compone con `formatToParts` en vez de usar el string completo porque `es-CO` une mes y año
  // con "de" ("agosto de 2026") y el título del período va sin esa conjunción.
  const parts = new Intl.DateTimeFormat(LOCALE, {
    month: 'long',
    year: 'numeric',
    timeZone: 'UTC',
  }).formatToParts(new Date(Date.UTC(year, month - 1, 1)));
  const monthName = parts.find((part) => part.type === 'month')?.value ?? '';
  const yearLabel = parts.find((part) => part.type === 'year')?.value ?? '';
  const label = `${monthName} ${yearLabel}`.trim();
  return label.charAt(0).toUpperCase() + label.slice(1);
};

/** `Intl` en UTC, descompuesto en partes, para componer rótulos sin depender de cómo el locale
 *  une día, mes y año (mismo criterio que `formatMonthLabel`: `es-CO` mete "de" en el medio). */
const partValue = (
  date: Date,
  options: Intl.DateTimeFormatOptions,
  type: 'day' | 'month' | 'year'
): string => {
  const parts = new Intl.DateTimeFormat(LOCALE, { ...options, timeZone: 'UTC' }).formatToParts(
    date
  );
  return parts.find((part) => part.type === type)?.value ?? '';
};

const dayOf = (date: Date) => partValue(date, { day: 'numeric' }, 'day');
const monthOf = (date: Date) => partValue(date, { month: 'long' }, 'month');

/**
 * Nombre del mes en minúscula y sin año (`"agosto"`), para los rótulos que ya viven debajo del
 * `PeriodNavigator`, donde el año está a la vista (Fase 29 §F5.3): "Balance de agosto" y no
 * "Balance de agosto 2026". `formatMonthLabel` ("Agosto 2026") es el rótulo del navegador.
 */
export const formatMonthName = (year: number, month: number): string =>
  monthOf(new Date(Date.UTC(year, month - 1, 1))).toLowerCase();
const yearOf = (date: Date) => partValue(date, { year: 'numeric' }, 'year');

/**
 * Rótulo de un día suelto: `"18 de agosto"`, o `"18 de agosto de 2027"` si el año difiere del de
 * referencia. El año se omite cuando es el mismo del inicio del período: sobra en una semana que
 * no cruza enero y hace falta en una que sí cruza, porque si no los dos días del rótulo
 * parecerían del mismo año.
 */
const formatDayLabel = (date: Date, referenceYear: number): string => {
  const year = yearOf(date);
  return `${dayOf(date)} de ${monthOf(date)}${Number(year) === referenceYear ? '' : ` de ${year}`}`;
};

/**
 * Normaliza el query param `?ref=YYYY-MM-DD` al inicio del período que contiene (supuesto 3,
 * Q37). Un `ref` a mitad de período se corrige a su inicio para que las flechas `◀ ▶` pelen
 * período contra período, y un `ref` inválido o futuro devuelve el inicio del período actual en
 * vez de romper la vista. `custom` no tiene período que normalizar: se devuelve tal cual.
 */
export const normalizeRef = (period: AnalyticsPeriod, ref: string, now: Date): string => {
  if (period === 'custom') return ref;
  const date = parseDateParam(ref);
  if (!date || date.getTime() > now.getTime()) {
    return toDateParam(periodStartUtc(period, now));
  }
  return toDateParam(periodStartUtc(period, date));
};

/**
 * Rango que consumen la tarjeta de KPIs, el gráfico de barras y la dona de Analítica — un solo
 * rango para las tres secciones (antes cada una tenía su preset y solo uno afectaba los números
 * de arriba, lo cual era confuso: Fase de discusión UX, 2026-09-06).
 *
 * `week` es la semana calendario lunes–domingo (Q13) y `month`/`year` arrancan en su límite de
 * calendario; los períodos pasados llegan completos y el actual termina hoy (Q34) — al final del
 * día UTC (`endOfUtcDay`), no en "ahora", por lo mismo que `utcMonthRange`. `ref` se
 * normaliza acá (y no en el caller) para que el rango nunca se construya sobre una fecha a mitad
 * de período ni futura.
 */
export const buildDateRange = (
  period: AnalyticsPeriod,
  ref: string,
  customStart: string,
  customEnd: string,
  now: Date
): DateRange => {
  if (period === 'custom' && customStart && customEnd) {
    // 'Z' explícito: el input type=date entrega "YYYY-MM-DD" sin zona horaria — sin el
    // sufijo, `new Date(...)` lo interpreta en hora local y desplaza el límite (mismo
    // problema que el de los límites de calendario).
    const start = new Date(`${customStart}T00:00:00Z`);
    const end = new Date(`${customEnd}T23:59:59Z`);
    const spanDays = (end.getTime() - start.getTime()) / MS_PER_DAY;
    // El backend de cashflow-series solo agrupa por 'day' o 'month' (sin 'week') — un rango
    // personalizado largo usa 'month' para no devolver cientos de barras diarias.
    return {
      start_date: start.toISOString(),
      end_date: end.toISOString(),
      granularity: spanDays > 60 ? 'month' : 'day',
    };
  }

  // Fallback de 'custom' mientras el usuario no completa el rango: el mes en curso, igual que
  // antes de la Fase 29.
  const preset: CalendarPeriod = period === 'custom' ? 'month' : period;
  const anchor = parseDateParam(normalizeRef(preset, ref, now)) ?? now;

  if (preset === 'month') {
    // El mes delega en `utcMonthRange` para no duplicar el criterio de techo (mismo helper que
    // el dashboard y que `limites_mes_utc` del backend).
    const range = utcMonthRange(anchor.getUTCFullYear(), anchor.getUTCMonth() + 1, now);
    return { ...range, granularity: 'day' };
  }

  const start = periodStartUtc(preset, anchor);
  const isCurrentPeriod = start.getTime() === periodStartUtc(preset, now).getTime();
  const end = isCurrentPeriod
    ? endOfUtcDay(now)
    : // Los períodos pasados van completos: fin de período menos 1 ms (23:59:59.999Z).
      new Date(periodEndUtc(preset, start).getTime() - 1);

  return {
    start_date: start.toISOString(),
    end_date: end.toISOString(),
    // El año se agrupa por mes: un rango de 365 días con granularidad 'day' son 365 barras.
    granularity: preset === 'year' ? 'month' : 'day',
  };
};

/**
 * Inicio del período que está `delta` períodos antes/después del que contiene `ref` — el `◀ ▶` de
 * Analítica (Fase 29 §F6.1).
 *
 * El resultado es siempre el **inicio** del período destino, así que el link sigue apuntando al
 * mismo período mañana (Q36) y `buildDateRange` no lo tiene que volver a normalizar. La aritmética
 * es con setters UTC (no getters locales) por el mismo motivo que el resto del módulo: un
 * desplazamiento de zona aquí movería el período un día y metería o sacaría las transacciones del
 * borde.
 */
export const shiftPeriodRef = (
  period: CalendarPeriod,
  ref: string,
  delta: -1 | 1,
  now: Date
): string => {
  // `periodStartUtc` primero y el desplazamiento después: así `◀`/`▶` saltan de período en
  // período aunque `ref` venga a mitad de uno (misma normalización que `normalizeRef`).
  const start = periodStartUtc(period, parseDateParam(ref) ?? now);
  if (period === 'week') start.setUTCDate(start.getUTCDate() + delta * 7);
  else if (period === 'month') start.setUTCMonth(start.getUTCMonth() + delta);
  else start.setUTCFullYear(start.getUTCFullYear() + delta);
  return toDateParam(start);
};

/**
 * Rótulo legible del período que se está mirando, para el título de `PeriodNavigator` (Fase 29
 * §F6.1, User Story 40): `"Semana del 18 al 24 de agosto"`, `"Julio 2026"`, `"2025"`,
 * `"Desde el 1 de marzo hasta el 15 de marzo"`.
 *
 * Los límites salen de `buildDateRange` en vez de recalcularlos: el rótulo describe el mismo
 * rango que la query pide, y duplicar el cálculo es la forma más corta de que el título termine
 * desalineado del rango que se está mirando.
 */
export const formatPeriodLabel = (
  period: AnalyticsPeriod,
  ref: string,
  customStart: string,
  customEnd: string,
  now: Date
): string => {
  const range = buildDateRange(period, ref, customStart, customEnd, now);
  const start = new Date(range.start_date);
  const startYear = start.getUTCFullYear();

  if (period === 'custom') {
    // Rango personalizado a medio llenar: `buildDateRange` cae al mes en curso y el rótulo también,
    // en vez de prometer un rango que no se está viendo.
    if (!customStart || !customEnd) return formatMonthLabel(startYear, start.getUTCMonth() + 1);
    const end = new Date(range.end_date);
    return `Desde el ${formatDayLabel(start, startYear)} hasta el ${formatDayLabel(end, startYear)}`;
  }

  if (period === 'year') return String(startYear);
  if (period === 'month') return formatMonthLabel(startYear, start.getUTCMonth() + 1);

  // Semana: siempre el lunes–domingo completo, incluso en la semana en curso, cuyos datos cortan
  // hoy (Q34). Tomar `end_date` diría "del 22 al 26" y parecería una semana recortada; con el
  // domingo, el rótulo no cambia al cruzar el `◀`/`▶`.
  const sunday = new Date(periodEndUtc('week', start).getTime() - 1);
  const sameMonth =
    start.getUTCMonth() === sunday.getUTCMonth() && startYear === sunday.getUTCFullYear();
  // "Semana del 18 al 24 de agosto" (Q40): el mes va una sola vez mientras no cambie; si la semana
  // cruza el mes o el año, se repite en cada extremo porque "del 31 de agosto al 6" no dice de
  // qué mes es el 6.
  return sameMonth
    ? `Semana del ${dayOf(start)} al ${dayOf(sunday)} de ${monthOf(start)}`
    : `Semana del ${formatDayLabel(start, startYear)} al ${formatDayLabel(sunday, startYear)}`;
};
