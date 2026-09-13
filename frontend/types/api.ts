export interface Account {
  id: number;
  name: string;
  type: 'cash' | 'debit' | 'credit';
  balance: number;
  /** Saldo de apertura, inmutable tras la creación (Fase 16 §16.4). Ancla para el
   *  endpoint de reconciliación. */
  opening_balance: number;
  currency: string;
  user_id: number;
  highlighted: boolean;
}

export interface Transaction {
  id: number;
  amount: number;
  currency: string;
  type: 'income' | 'expense';
  description: string | null;
  date: string;
  account_id: number;
  category_id: number;
  payment_method?: 'cash' | 'card' | 'transfer' | null;
  user_id: number;
}

export interface Category {
  id: number;
  name: string;
  type: 'income' | 'expense';
  user_id: number | null;
  icon?: string;
}

export interface Budget {
  id: number;
  category_id: number;
  amount_limit: number;
  currency: string;
  month: number;
  year: number;
  is_recurring: boolean;
  user_id: number;
}

export interface BudgetProgress {
  budget_id: number;
  category_name: string;
  category_icon?: string;
  amount_limit: number;
  spent: number;
  percentage: number;
  /** Moneda real del presupuesto (Fase 11 §11.1): gasto y límite viven en esta moneda. */
  currency: string;
}

export interface BalanceByCurrency {
  currency: string;
  total: number;
}

export interface DashboardSummary {
  balances: BalanceByCurrency[];
  monthly_income_by_currency: BalanceByCurrency[];
  monthly_expense_by_currency: BalanceByCurrency[];
  /**
   * Ingreso mensual declarado − gasto del mes (en la moneda preferida), calculado por el
   * backend (Fase 11 §11.3). `null` = el usuario no ha fijado monthly_income todavía;
   * distinguir de `undefined` (query en carga).
   */
  monthly_flow_balance: number | null;
}

export interface CashflowItem {
  date_label: string;
  expense: number;
  income: number;
}

export interface CategoryDistributionItem {
  category_id: number;
  category_name: string;
  total: number;
}

/** Balance del mes de una cuenta puntual (GET /accounts/{id}/monthly-summary, Fase 17 §17.1).
 *  Los montos Decimal pueden llegar serializados como `string` en JSON (Decisión 15.6) —
 *  normalizar con `Number(...)` al pintar. */
export interface AccountMonthlySummary {
  currency: string;
  monthly_income: number;
  monthly_expense: number;
  monthly_flow_balance: number;
}

export interface UserResponse {
  id: number;
  email: string;
  full_name: string;
  preferred_currency: string;
  preferred_locale: string;
  preferred_theme: string;
  monthly_income: number | null;
  /** Fase 19 §19.1 — true si el usuario tiene 2+ transacciones (usuario recurrente); solo se
   *  calcula en GET /users/me, nunca en los otros endpoints que devuelven UserResponse. */
  has_transaction_history: boolean;
}

export interface PreferencesUpdatePayload {
  preferred_currency?: string;
  preferred_locale?: string;
  preferred_theme?: string;
  weekly_summary_enabled?: boolean;
}

export interface UserPreferences {
  preferred_currency: string;
  preferred_locale: string;
  preferred_theme: string;
  weekly_summary_enabled: boolean;
}

export interface CreateTransactionPayload {
  description: string;
  amount: number;
  type: 'income' | 'expense';
  /** Opcional: si se omite, el backend la puebla con server_default=func.now(). */
  date?: string;
  account_id: number;
  category_id: number;
  payment_method?: 'cash' | 'card' | 'transfer' | null;
  currency?: string;
}

export interface UpdateTransactionPayload {
  id: number;
  description: string;
  amount: number;
  type: 'income' | 'expense';
  date: string;
  account_id: number;
  category_id: number;
  payment_method?: 'cash' | 'card' | 'transfer' | null;
}

export interface CreateAccountPayload {
  name: string;
  type: 'cash' | 'debit' | 'credit';
  balance: number;
  currency?: string;
  highlighted?: boolean;
}

export interface BudgetPayload {
  category_id: number;
  amount_limit: number;
  currency?: string;
  month: number;
  year: number;
  is_recurring?: boolean;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface AppNotification {
  id: number;
  /** `budget_threshold_80` | `budget_threshold_100` | `weekly_summary` (Fase 14). */
  type: string;
  title: string;
  body: string;
  /** Referencia opcional al presupuesto que originó el aviso; el frontend enlaza
   *  "Ver presupuesto" cuando no es null. */
  budget_id: number | null;
  /** Clave de período que originó el aviso (Fase 14, p. ej. "2026-W37" para el
   *  resumen semanal). Null para alertas de presupuesto (Fase 13). */
  period_key: string | null;
  read_at: string | null;
  created_at: string;
}

export interface UnreadCountResponse {
  count: number;
}
