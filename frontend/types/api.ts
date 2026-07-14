export interface Account {
  id: number;
  name: string;
  type: 'cash' | 'debit' | 'credit';
  balance: number;
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
  user_id: number;
}

export interface BudgetProgress {
  budget_id: number;
  category_name: string;
  category_icon?: string;
  amount_limit: number;
  spent: number;
  percentage: number;
}

export interface BalanceByCurrency {
  currency: string;
  total: number;
}

export interface DashboardSummary {
  balances: BalanceByCurrency[];
  monthly_income_by_currency: BalanceByCurrency[];
  monthly_expense_by_currency: BalanceByCurrency[];
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

export interface UserResponse {
  id: number;
  email: string;
  full_name: string;
  preferred_currency: string;
  preferred_locale: string;
  preferred_theme: string;
}

export interface PreferencesUpdatePayload {
  preferred_currency?: string;
  preferred_locale?: string;
  preferred_theme?: string;
}

export interface UserPreferences {
  preferred_currency: string;
  preferred_locale: string;
  theme: string;
}

export interface CreateTransactionPayload {
  description: string;
  amount: number;
  type: 'income' | 'expense';
  date: string;
  account_id: number;
  category_id: number;
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
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}
