/**
 * Claves de cache de TanStack Query. Lo que NO va en una key: nada que cambie sin que el
 * dato cambie (relojes, `new Date()`). El mes de la Fase 29 entra como `'YYYY-MM'`, un
 * segmento estable — no un ISO de instante, que generaría una key distinta por render.
 *
 * **Regla de los segmentos opcionales (Fase 29, H7):** un argumento opcional se OMITE del
 * array cuando no se pasa, nunca se deja como `undefined`. TanStack compara el prefijo
 * elemento a elemento, así que `['dashboardSummary', undefined]` dejaría de matchear las
 * ~17 invalidaciones que llaman `invalidateQueries({ queryKey: queryKeys.dashboard.summary() })`
 * desde 9 archivos, y capturar una transacción dejaría de refrescar el resumen. El mes
 * actual del dashboard se cachea con la key sin segmento — que es exactamente la de hoy.
 */

export const queryKeys = {
  currentUser: () => ['currentUser'] as const,
  userPreferences: () => ['userPreferences'] as const,
  accounts: {
    all: () => ['accounts'] as const,
    byId: (id: string | number) => ['account', id] as const,
    /** Saldo total por moneda de TODAS las cuentas (GET /accounts/summary, Fase 11 §11.5). */
    summary: () => ['accounts-summary'] as const,
    /** Balance del mes de una cuenta puntual (GET /accounts/{id}/monthly-summary, Fase 17 §17.1)
     *  — clave propia por cuenta, no reutiliza la del dashboard. */
    monthlySummary: (id: string | number) => ['account-monthly-summary', id] as const,
    /** Desglose de gastos del mes por categoría restringido a una cuenta (Fase 17 §17.1). */
    categoryBreakdown: (id: string | number) => ['account-category-breakdown', id] as const,
    /** Progreso de presupuestos filtrado a la moneda de una cuenta (Fase 17 §17.1, Decisión
     *  17.1.3/P4 — el prefijo también matchea la invalidación por prefix desde budgets). */
    budgetsProgress: (id: string | number) => ['account-budgets-progress', id] as const,
  },
  categories: {
    all: () => ['categories'] as const,
    byId: (id: string | number) => ['category', id] as const,
  },
  transactions: {
    all: () => ['transactions'] as const,
    byAccount: (id: string | number) => ['transactions', 'account', id] as const,
    byCategory: (id: string | number) => ['transactions', 'category', id] as const,
    filtered: (filters: Record<string, unknown>) => ['transactions', filters] as const,
    /** Fase 39: feed mixto (`GET /movements/`). Cuelga del prefijo `['transactions']`, así que
     *  toda invalidación de `transactions.all()` lo cubre sin tocar los 17 call sites. */
    movements: (filters: Record<string, unknown>) =>
      ['transactions', 'movements', filters] as const,
  },
  funds: {
    /** Lista de sobres (Fase 35). La variante con archivados cuelga de este prefijo. */
    all: () => ['funds'] as const,
    /** El id se normaliza a string: la página lo lee de la URL (string) y las mutaciones lo
     *  reciben como número; TanStack compara por hash JSON y `'5'` ≠ `5` (la invalidación
     *  no matcheaba y el detalle quedaba desactualizado tras aportar). */
    byId: (id: string | number) => ['fund', String(id)] as const,
    /** Prefijo de TODOS los detalles (`['fund', id]`). Fase 36: crear/editar/borrar un gasto
     *  cambia saldo y `linked_expenses` de algún sobre, así que se invalida por prefijo. */
    details: () => ['fund'] as const,
  },
  recurring: {
    /** Prefijo de todo lo recurrente (Fase 37): reglas, pendientes, calendario y sugerencias
     *  cuelgan de aquí, así que `invalidateQueries(recurring.all())` los cubre. */
    all: () => ['recurring'] as const,
    rules: () => ['recurring', 'rules'] as const,
    pending: () => ['recurring', 'pending'] as const,
    calendar: () => ['recurring', 'calendar'] as const,
    suggestions: () => ['recurring', 'suggestions'] as const,
  },
  cdts: {
    /** Fase 38: la lista (con sus `totals`) cuelga de aquí. Las mutaciones de CDT invalidan
     *  solo este prefijo y `dashboard.summary()`; no tocan cuentas, transacciones ni sobres. */
    all: () => ['cdts'] as const,
  },
  budgets: {
    all: () => ['budgets'] as const,
    /** Listado de `/budgets` de un mes (`'YYYY-MM'`). Cuelga del prefijo `['budgets']`, así que
     *  `invalidateQueries(budgets.all())` lo cubre. */
    byMonth: (month: string) => ['budgets', month] as const,
    /** Fase 29: `month` es el mes consultado del progreso del dashboard (`'YYYY-MM'`, o
     *  ausente en el mes actual). Lo que No depende del mes — `/budgets` — usa `all`. */
    progress: (month?: string) =>
      (month ? ['budgets-progress', month] : ['budgets-progress']) as
        readonly ['budgets-progress'] | readonly ['budgets-progress', string],
  },
  dashboard: {
    /** Fase 29: idem `budgets.progress` — el resumen del mes pedido, con el mes actual en la
     *  key sin segmento para que las invalidaciones por prefijo sigan matcheando. */
    summary: (month?: string) =>
      (month ? ['dashboardSummary', month] : ['dashboardSummary']) as
        readonly ['dashboardSummary'] | readonly ['dashboardSummary', string],
    /** Desglose de gastos del mes por categoría en el dashboard (Fase 11 §11.4).
     *  Clave propia: no reutiliza analytics.categories(), que exige período/tipo/neto.
     *  Fase 29: `month` y `currency` son los filtros de las barras; ambos se omiten si no
     *  se pasan, por el mismo motivo que arriba. */
    categoryBreakdown: (month?: string, currency?: string) =>
      (month || currency
        ? ['dashboard-category-breakdown', month, currency]
        : ['dashboard-category-breakdown']) as
        | readonly ['dashboard-category-breakdown']
        | readonly ['dashboard-category-breakdown', string | undefined, string | undefined],
  },
  analytics: {
    cashflow: (start: string, end: string, period: string, accountId?: string, currency?: string) =>
      ['analytics-cashflow', start, end, period, accountId, currency] as const,
    categories: (
      start: string,
      end: string,
      type: string,
      neto?: boolean,
      accountId?: string,
      currency?: string
    ) => ['analytics-categories', start, end, type, neto, accountId, currency] as const,
  },
  notifications: {
    /** Lista paginada de la bandeja in-app (GET /notifications, Fase 13 §13.5). */
    all: () => ['notifications'] as const,
    /** Conteo para el badge de la campana (GET /notifications/unread-count) — clave
     *  separada a propósito (Decisión 13.5.4): el poll corto del badge no dispara
     *  la query de lista completa. */
    unreadCount: () => ['notifications-unread-count'] as const,
  },
  /** API keys personales revocables (Fase 16 §16.1) — GET/POST /api-keys/, DELETE /api-keys/{id}. */
  apiKeys: () => ['apiKeys'] as const,
};
