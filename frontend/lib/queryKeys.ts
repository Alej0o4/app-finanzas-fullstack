export const queryKeys = {
  currentUser: () => ['currentUser'] as const,
  userPreferences: () => ['userPreferences'] as const,
  accounts: {
    all: () => ['accounts'] as const,
    byId: (id: string | number) => ['account', id] as const,
    /** Saldo total por moneda de TODAS las cuentas (GET /accounts/summary, Fase 11 §11.5). */
    summary: () => ['accounts-summary'] as const,
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
  },
  budgets: {
    all: () => ['budgets'] as const,
    progress: () => ['budgets-progress'] as const,
  },
  dashboard: {
    summary: () => ['dashboardSummary'] as const,
    recentTransactions: (limit: number = 5) => ['recent-transactions', limit] as const,
    /** Desglose de gastos del mes por categoría en el dashboard (Fase 11 §11.4).
     *  Clave propia: no reutiliza analytics.categories(), que exige período/tipo/neto. */
    categoryBreakdown: () => ['dashboard-category-breakdown'] as const,
  },
  analytics: {
    cashflow: (start: string, end: string, period: string) =>
      ['analytics-cashflow', start, end, period] as const,
    categories: (start: string, end: string, type: string, neto?: boolean) =>
      ['analytics-categories', start, end, type, neto] as const,
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
