export const queryKeys = {
  currentUser: () => ["currentUser"] as const,
  accounts: {
    all: () => ["accounts"] as const,
    byId: (id: string | number) => ["account", id] as const,
  },
  categories: {
    all: () => ["categories"] as const,
    byId: (id: string | number) => ["category", id] as const,
  },
  transactions: {
    all: () => ["transactions"] as const,
    byAccount: (id: string | number) => ["transactions", "account", id] as const,
    byCategory: (id: string | number) => ["transactions", "category", id] as const,
    filtered: (filters: Record<string, unknown>) => ["transactions", filters] as const,
  },
  budgets: {
    all: () => ["budgets"] as const,
    progress: () => ["budgets-progress"] as const,
  },
  dashboard: {
    summary: () => ["dashboardSummary"] as const,
    recentTransactions: (limit: number = 5) => ["recent-transactions", limit] as const,
  },
  analytics: {
    cashflow: (start: string, end: string, period: string) => ["analytics-cashflow", start, end, period] as const,
    categories: (start: string, end: string, type: string, neto?: boolean) => ["analytics-categories", start, end, type, neto] as const,
  },
};
