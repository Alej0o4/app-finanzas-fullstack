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
};
