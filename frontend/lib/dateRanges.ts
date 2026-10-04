/**
 * Fase 34 §F2/F3 (reemplaza el criterio UTC de la Fase 29 §F1) — límites de período como **días
 * `YYYY-MM-DD`**, compartidos por el dashboard, Analítica, `/transactions` y la vista por cuenta.
 *
 * El frontend ya no arma instantes UTC de límite (H9): manda días y el backend los interpreta en
 * la zona horaria del usuario (`User.timezone`, B7). "Hoy" llega **inyectado** como `today`
 * (`YYYY-MM-DD` en la zona del usuario, de `todayInZone`/`useTimezone`), así este módulo sigue
 * siendo puro y testeable, y `today` es un string estable durante todo el día (sirve en query
 * keys y deps de memo).
 *
 * Aritmética de calendario puro (sumar días, primer/último día de mes, lunes de la semana): usa
 * `Date.UTC`/setters UTC **solo como motor de calendario** sobre `y/m/d` — un `Date` aquí
 * representa "ese día del calendario", no un instante del usuario, así que el offset de zona no
 * entra nunca (H9).
 */

export type AnalyticsPeriod = 'week' | 'month' | 'year' | 'custom';

/** Agrupación que el backend de `cashflow-series` acepta ('week' no está soportada). */
export type DateRangeGranularity = 'day' | 'month';

export interface CalendarMonth {
  year: number;
  /** 1..12. */
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

/** Día de calendario de un `Date` "de calendario" (ver cabecera) → `YYYY-MM-DD`. */
const toDateParam = (date: Date): string =>
  `${String(date.getUTCFullYear()).padStart(4, '0')}-${String(date.getUTCMonth() + 1).padStart(2, '0')}-${String(date.getUTCDate()).padStart(2, '0')}`;

/** `YYYY-MM-DD` → `Date` de calendario (00:00Z), o `null` si no existe en el calendario. */
const parseDateParam = (raw: string): Date | null => {
  if (!DATE_PARAM_PATTERN.test(raw)) return null;
  const date = new Date(`${raw}T00:00:00Z`);
  // `new Date('2026-02-31T00:00:00Z')` no es `NaN`: normaliza a marzo 3. El round-trip descarta
  // esas fechas en vez de "corregirlas" en silencio y analizarlas en el período equivocado.
  return toDateParam(date) === raw ? date : null;
};

/** Inicio del período de calendario que contiene el día `date` (calendario puro, ver cabecera). */
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

/** `{ year, month }` del día `today` (`YYYY-MM-DD`, ya en la zona del usuario). */
export const monthOfDay = (today: string): CalendarMonth => {
  const date = dayToDate(today);
  return { year: date.getUTCFullYear(), month: date.getUTCMonth() + 1 };
};

/** `today` (`YYYY-MM-DD`) como `Date` de calendario; si no parsea (no debería), el día UTC de hoy. */
const dayToDate = (today: string): Date =>
  parseDateParam(today) ?? parseDateParam(toDateParam(new Date()))!;

/** Lee el query param `?month=YYYY-MM`. Devuelve `null` si no matchea el formato, si el mes está
 *  fuera de 1..12 o si el año es `< 1` — los 422 que responde el backend (H13), decididos acá
 *  para no pedir un mes que el servidor va a rechazar. */
export const parseMonthParam = (raw: string): CalendarMonth | null => {
  const match = MONTH_PARAM_PATTERN.exec(raw);
  if (!match) return null;
  const year = Number(match[1]);
  const month = Number(match[2]);
  if (year < 1 || month < 1 || month > 12) return null;
  return { year, month };
};

/** Meses relativos con desborde de año (enero − 1 → diciembre del año anterior). */
export const shiftMonth = ({ year, month }: CalendarMonth, delta: number): CalendarMonth => {
  // Aritmética de índice absoluto de mes en vez de `Date.UTC`: `Date.UTC` mapea los años de dos
  // dígitos a 1900+año, así que un delta negativo sobre un año chico saldría del siglo XX.
  const absolute = year * 12 + (month - 1) + delta;
  return { year: Math.floor(absolute / 12), month: (((absolute % 12) + 12) % 12) + 1 };
};

/** Orden de períodos: negativo si `a` es anterior a `b`. */
export const compareMonth = (a: CalendarMonth, b: CalendarMonth): number =>
  a.year !== b.year ? a.year - b.year : a.month - b.month;

/**
 * Bordes del período de calendario en curso (semana/mes/año), como días `YYYY-MM-DD`, para
 * `/transactions` (Fase 30 F1, Fase 34 F3).
 *
 * Devuelve el inicio (lunes, día 1 o 1 de enero) y el fin (`today`) del período que contiene
 * `today`. Encapsula el criterio en este módulo en vez de exportar `periodStartUtc` suelto, para
 * que `/transactions` no arme fechas por su cuenta. El fin es hoy, no el domingo ni el último día
 * del mes: mismo corte que el período en curso de Analítica (Q1, supuesto 1 de la Fase 30). El
 * backend interpreta `end_date` como inclusivo de todo ese día en la zona del usuario.
 */
export const currentCalendarPeriodRange = (
  period: CalendarPeriod,
  today: string
): { start_date: string; end_date: string } => {
  const start = periodStartUtc(period, dayToDate(today));
  return { start_date: toDateParam(start), end_date: today };
};

/**
 * Rango del mes pedido, como días. El techo es `today` en el mes en curso y el último día del mes
 * en un mes pasado. El backend corta el mes en curso en "ahora" (B7); la diferencia es solo lo
 * fechado más tarde hoy, y a cambio el rango no cambia en cada render. Un mes futuro (no debería
 * pasar: los consumidores lo validan) se devuelve completo.
 */
export const monthRange = (
  year: number,
  month: number,
  today: string
): { start_date: string; end_date: string } => {
  const start = new Date(Date.UTC(year, month - 1, 1));
  const current = monthOfDay(today);
  const isCurrentMonth = year === current.year && month === current.month;
  // `Date.UTC(y, month, 0)` es el día 0 del mes siguiente, o sea el último del pedido.
  const end = isCurrentMonth ? dayToDate(today) : new Date(Date.UTC(year, month, 0));
  return { start_date: toDateParam(start), end_date: toDateParam(end) };
};

/** `{ year, month }` → query param `YYYY-MM` (inverso de `parseMonthParam`). */
export const formatMonthParam = ({ year, month }: CalendarMonth): string =>
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
export const normalizeRef = (period: AnalyticsPeriod, ref: string, today: string): string => {
  if (period === 'custom') return ref;
  const date = parseDateParam(ref);
  if (!date || toDateParam(date) > today) {
    return toDateParam(periodStartUtc(period, dayToDate(today)));
  }
  return toDateParam(periodStartUtc(period, date));
};

/**
 * Rango que consumen la tarjeta de KPIs, el gráfico de barras y la dona de Analítica — un solo
 * rango para las tres secciones (antes cada una tenía su preset y solo uno afectaba los números
 * de arriba, lo cual era confuso: Fase de discusión UX, 2026-09-06).
 *
 * `week` es la semana calendario lunes–domingo (Q13) y `month`/`year` arrancan en su límite de
 * calendario; los períodos pasados llegan completos y el actual termina hoy (Q34). Todo son días
 * `YYYY-MM-DD` (Fase 34 F3): el backend los resuelve en la zona del usuario. `ref` se normaliza
 * acá (y no en el caller) para que el rango nunca se construya sobre una fecha a mitad de período
 * ni futura.
 */
export const buildDateRange = (
  period: AnalyticsPeriod,
  ref: string,
  customStart: string,
  customEnd: string,
  today: string
): DateRange => {
  if (period === 'custom' && customStart && customEnd) {
    // Los inputs `type=date` ya entregan `YYYY-MM-DD`: pasan tal cual, sin convertir a instante.
    const spanDays =
      ((parseDateParam(customEnd)?.getTime() ?? 0) -
        (parseDateParam(customStart)?.getTime() ?? 0)) /
      MS_PER_DAY;
    // El backend de cashflow-series solo agrupa por 'day' o 'month' (sin 'week') — un rango
    // personalizado largo usa 'month' para no devolver cientos de barras diarias.
    return {
      start_date: customStart,
      end_date: customEnd,
      granularity: spanDays > 60 ? 'month' : 'day',
    };
  }

  // Fallback de 'custom' mientras el usuario no completa el rango: el mes en curso, igual que
  // antes de la Fase 29.
  const preset: CalendarPeriod = period === 'custom' ? 'month' : period;
  const anchor = parseDateParam(normalizeRef(preset, ref, today)) ?? dayToDate(today);

  if (preset === 'month') {
    // El mes delega en `monthRange` para no duplicar el criterio de techo (mismo helper que el
    // dashboard y la vista por cuenta).
    const range = monthRange(anchor.getUTCFullYear(), anchor.getUTCMonth() + 1, today);
    return { ...range, granularity: 'day' };
  }

  const start = periodStartUtc(preset, anchor);
  const isCurrentPeriod =
    toDateParam(start) === toDateParam(periodStartUtc(preset, dayToDate(today)));
  // Los períodos pasados van completos: último día del período (inicio del siguiente − 1 día).
  const lastDay = periodEndUtc(preset, start);
  lastDay.setUTCDate(lastDay.getUTCDate() - 1);
  const end = isCurrentPeriod ? today : toDateParam(lastDay);

  return {
    start_date: toDateParam(start),
    end_date: end,
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
 * es con setters UTC sobre días de calendario (ver cabecera): ningún offset de zona entra aquí.
 */
export const shiftPeriodRef = (
  period: CalendarPeriod,
  ref: string,
  delta: -1 | 1,
  today: string
): string => {
  // `periodStartUtc` primero y el desplazamiento después: así `◀`/`▶` saltan de período en
  // período aunque `ref` venga a mitad de uno (misma normalización que `normalizeRef`).
  const start = periodStartUtc(period, parseDateParam(ref) ?? dayToDate(today));
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
  today: string
): string => {
  const range = buildDateRange(period, ref, customStart, customEnd, today);
  const start = dayToDate(range.start_date);
  const startYear = start.getUTCFullYear();

  if (period === 'custom') {
    // Rango personalizado a medio llenar: `buildDateRange` cae al mes en curso y el rótulo también,
    // en vez de prometer un rango que no se está viendo.
    if (!customStart || !customEnd) return formatMonthLabel(startYear, start.getUTCMonth() + 1);
    const end = dayToDate(range.end_date);
    return `Desde el ${formatDayLabel(start, startYear)} hasta el ${formatDayLabel(end, startYear)}`;
  }

  if (period === 'year') return String(startYear);
  if (period === 'month') return formatMonthLabel(startYear, start.getUTCMonth() + 1);

  // Semana: siempre el lunes–domingo completo, incluso en la semana en curso, cuyos datos cortan
  // hoy (Q34). Tomar `end_date` diría "del 22 al 26" y parecería una semana recortada; con el
  // domingo, el rótulo no cambia al cruzar el `◀`/`▶`.
  const sunday = periodEndUtc('week', start);
  sunday.setUTCDate(sunday.getUTCDate() - 1);
  const sameMonth =
    start.getUTCMonth() === sunday.getUTCMonth() && startYear === sunday.getUTCFullYear();
  // "Semana del 18 al 24 de agosto" (Q40): el mes va una sola vez mientras no cambie; si la semana
  // cruza el mes o el año, se repite en cada extremo porque "del 31 de agosto al 6" no dice de
  // qué mes es el 6.
  return sameMonth
    ? `Semana del ${dayOf(start)} al ${dayOf(sunday)} de ${monthOf(start)}`
    : `Semana del ${formatDayLabel(start, startYear)} al ${formatDayLabel(sunday, startYear)}`;
};
