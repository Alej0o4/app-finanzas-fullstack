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
  /** Fase 36 (D6): sobre al que está enlazado el gasto, o null. Si se pidió un sobre sin saldo
   *  vuelve null con `fund_applied_amount: "0.00"`. */
  fund_id?: number | null;
  /** Fase 36: lo que salió del sobre, `min(gasto, saldo)`, calculado por el backend (decimal
   *  como string). null si no hay enlace ni se pidió sobre. */
  fund_applied_amount?: string | null;
}

export interface Category {
  id: number;
  name: string;
  type: 'income' | 'expense';
  user_id: number | null;
  icon?: string;
  /** Oculta para mí (Fase 18 §18.3): computado por usuario en el backend; solo filtra el
   *  selector de captura, no históricos ni analítica. */
  is_hidden: boolean;
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
   * Ingresos reales del período menos gastos reales del período, en la moneda preferida
   * (Fase 11 §11.3, redefinido Fase 31 B9/Q9). Calculado por el backend, igual en el mes en
   * curso que en un mes cerrado; nunca `null` (sin transacciones vale `"0.00"`) y puede ser
   * negativo (a principio de mes, antes de cobrar, es un dato normal, no un error).
   * `monthly_income` (el ingreso declarado) ya NO participa de este cálculo — es solo una
   * referencia visual ("· esperado <monto>", Fase 31 F8).
   */
  monthly_flow_balance: number;
  /**
   * @deprecated Fase 31 (B9, Q9): siempre `"actual"` — el balance ya no tiene dos bases
   * (la base "declared" que usaba `monthly_income` desapareció). Se conserva sin default
   * por el mismo motivo que documentaba Fase 29 (B2/B6): no inventar un valor para un
   * contrato que un cliente viejo podría no enviar. El frontend ya no lo lee para decidir
   * el rótulo de la tarjeta (siempre "Balance de <mes>").
   */
  monthly_flow_basis: 'actual';
  /**
   * Mes UTC `"YYYY-MM"` de la transacción más antigua del usuario, o `null` si no tiene
   * ninguna (Fase 29, Q9). Es el límite inferior del `◀` del dashboard. Va sobre todas las
   * cuentas, no solo las destacadas, porque gobierna la página entera.
   */
  first_transaction_month: string | null;
  /**
   * Monedas distintas con gasto en el mes consultado, sobre TODAS las cuentas (Fase 29, B7).
   * Alimenta los chips de moneda de "Gastos por categoría" — que filtran las barras, y las
   * barras cuentan todas las cuentas, a diferencia de `monthly_expense_by_currency`, que solo
   * suma las destacadas. La preferida solo aparece si tiene gasto en el mes; el frontend la
   * suma igual a las opciones.
   */
  expense_currencies: string[];
  /**
   * Fase 35 (B11): foto de HOY sobre todas las cuentas (no depende del mes navegado), moneda
   * preferida primero. `free_to_spend = accounts_total - committed` lo calcula el backend y
   * puede ser negativo.
   */
  accounts_total: BalanceByCurrency[];
  committed: BalanceByCurrency[];
  free_to_spend: BalanceByCurrency[];
  /** Fase 36 (D9): parte de `monthly_expense_by_currency` que corresponde a gastos enlazados a
   *  un sobre ("planeado"). Es un desglose: no se resta ni cambia el total. */
  planned_expense: BalanceByCurrency[];
  /** Fase 38 (D5): capital + interés causado a hoy de los CDT vigentes, por moneda. Foto de HOY. */
  cdt_total: BalanceByCurrency[];
  /** Fase 38 (D5): `accounts_total + cdt_total`, por moneda. No altera `free_to_spend`. */
  net_worth: BalanceByCurrency[];
}

export type CdtStatus = 'active' | 'redeemed';
export type CdtAlert = 'ok' | 'due_soon' | 'matured';

/** CDT (Fase 38). Los Decimal llegan como string: normalizar con `Number(...)`. Fechas = días
 *  `YYYY-MM-DD` en la zona del usuario. Interés y valores los calcula el backend (E.A. bruto). */
export interface Cdt {
  id: number;
  name: string;
  currency: string;
  principal: string;
  /** Tasa E.A. en puntos porcentuales (`11.5` = 11,5 %). */
  rate_ea: string;
  opened_on: string;
  maturity_on: string;
  status: CdtStatus;
  redeemed_on?: string | null;
  final_amount?: string | null;
  /** `final_amount - principal`; solo en redimidos (puede ser negativo). */
  realized_interest?: string | null;
  term_days: number;
  elapsed_days: number;
  accrued_interest: string;
  current_value: string;
  maturity_interest: string;
  maturity_value: string;
  /** Negativo si ya venció; `null` si está redimido. */
  days_to_maturity?: number | null;
  alert: CdtAlert;
  created_at?: string | null;
}

/** Totales por moneda, solo de los CDT vigentes. */
export interface CdtTotals {
  currency: string;
  principal: string;
  accrued_interest: string;
  current_value: string;
  maturity_value: string;
}

export interface CdtListResponse {
  items: Cdt[];
  totals: CdtTotals[];
}

export interface CreateCdtPayload {
  name: string;
  currency: string;
  principal: number;
  rate_ea: number;
  opened_on: string;
  maturity_on: string;
}

/** Parcial: solo se mandan los campos que cambiaron (`null` explícito da 422). */
export type UpdateCdtPayload = Partial<CreateCdtPayload>;

export interface RedeemCdtPayload {
  redeemed_on?: string;
  final_amount?: number;
}

export type FundKind = 'annual_expense' | 'emergency' | 'goal';
export type FundPace = 'completed' | 'on_track' | 'behind';

/** Sobre virtual (Fase 35). Los Decimal pueden llegar como string: normalizar con `Number(...)`. */
export interface Fund {
  id: number;
  name: string;
  kind: FundKind;
  status: 'active' | 'archived';
  account_id: number;
  currency: string;
  balance: number | string;
  target_amount: number | string | null;
  target_months: number | null;
  target_date: string | null;
  progress_pct: number | null;
  remaining: number | string | null;
  months_remaining: number | null;
  required_contribution: number | string | null;
  /** Cuota sugerida del mes siguiente con el saldo actual; null sin fecha, en el último mes o sin nada por aportar. */
  next_month_contribution: number | string | null;
  pace: FundPace | null;
  monthly_expense_avg: number | string | null;
  runway_months: number | string | null;
  backing_shortfall: number | string;
  created_at: string | null;
  /** Fase 36 (D12): gastos enlazados vivos a este sobre y su monto total (decimal como string). */
  linked_expenses_count: number;
  linked_expenses_total: number | string;
}

export interface FundEntry {
  id: number;
  fund_id: number;
  /** Con signo: aporte > 0, retiro < 0. */
  amount: number | string;
  type: 'contribution' | 'withdrawal' | 'adjustment';
  occurred_at: string;
  period: string;
  note: string | null;
  /** Fase 36: transacción de gasto que originó el movimiento, o null. */
  transaction_id: number | null;
}

/** Gasto enlazado a un sobre (Fase 36, los 50 más recientes). */
export interface FundLinkedExpense {
  transaction_id: number;
  amount: number | string;
  /** Lo que salió del sobre; si es menor que `amount`, el resto fue gasto normal. */
  applied_amount: number | string;
  date: string;
  description: string | null;
  category_name: string | null;
}

export interface FundDetail extends Fund {
  entries: FundEntry[];
  linked_expenses: FundLinkedExpense[];
}

export interface CreateFundPayload {
  name: string;
  kind: FundKind;
  account_id: number;
  target_amount?: number;
  target_months?: number;
  target_date?: string;
}

export interface UpdateFundPayload {
  name?: string;
  account_id?: number;
  target_amount?: number;
  target_months?: number;
  target_date?: string | null;
}

export type RecurringFrequency = 'weekly' | 'monthly' | 'yearly';
export type RecurringStatus = 'active' | 'paused';

/** Regla recurrente (Fase 37). Los Decimal llegan como string: normalizar con `Number(...)`.
 *  Fechas = días de calendario `YYYY-MM-DD` en la zona del usuario, no instantes. */
export interface RecurringRule {
  id: number;
  name: string;
  type: 'income' | 'expense';
  amount: number | string;
  /** Moneda de su cuenta; null si la cuenta se borró (`account_missing`). */
  currency: string | null;
  account_id: number;
  category_id: number;
  frequency: RecurringFrequency;
  start_date: string;
  /** Próxima ocurrencia no resuelta. */
  next_date: string;
  status: RecurringStatus;
  /** Costo mensualizado calculado por el backend (semanal x52/12, anual /12). */
  monthly_equivalent: number | string;
  is_annual: boolean;
  /** Activa y `next_date <= hoy`. */
  is_due: boolean;
  account_missing: boolean;
  category_missing: boolean;
  created_at: string | null;
}

export interface CreateRecurringPayload {
  name: string;
  type: 'income' | 'expense';
  amount: number;
  account_id: number;
  category_id: number;
  frequency: RecurringFrequency;
  start_date: string;
}

/** `frequency`, `start_date` y `type` NO se editan: enviarlos es 422. */
export interface UpdateRecurringPayload {
  name?: string;
  amount?: number;
  account_id?: number;
  category_id?: number;
  status?: RecurringStatus;
}

export interface PendingOccurrence {
  rule_id: number;
  name: string;
  type: 'income' | 'expense';
  amount: number | string;
  currency: string;
  account_id: number;
  category_id: number;
  frequency: RecurringFrequency;
  occurrence_date: string;
  /** Solo la primera ocurrencia de cada regla se puede confirmar o saltar. */
  is_next: boolean;
}

export interface RecurringCalendarItem {
  rule_id: number;
  name: string;
  type: 'income' | 'expense';
  amount: number | string;
  currency: string;
  date: string;
  is_annual: boolean;
  is_overdue: boolean;
}

export interface RecurringCalendarTotals {
  currency: string;
  income: number | string;
  expense: number | string;
  net: number | string;
}

export interface RecurringCalendarMonth {
  /** `YYYY-MM`. */
  month: string;
  items: RecurringCalendarItem[];
  totals: RecurringCalendarTotals[];
}

export interface RecurringCalendar {
  months: RecurringCalendarMonth[];
  /** Suma de `monthly_equivalent` de las reglas de gasto por moneda; informativo. */
  monthly_commitment: { currency: string; amount: number | string }[];
}

export interface RecurringSuggestion {
  name: string;
  account_id: number;
  category_id: number;
  currency: string;
  amount: number | string;
  last_date: string;
  suggested_start_date: string;
  occurrences: number;
}

export interface CashflowItem {
  date_label: string;
  expense: number;
  income: number;
}

/** Nueva forma de respuesta de GET /dashboard/cashflow-series a partir de Fase 30 (B1).
 *  Antes era `CashflowItem[]`. Ahora es un objeto con buckets + totales, para que el
 *  frontend no sume en cliente (Q6). Los `Decimal` llegan como string o number; se
 *  normalizan con `Number(...)` igual que los buckets. */
export interface CashflowSeries {
  buckets: CashflowItem[];
  total_income: number;
  total_expense: number;
  net: number;
  /** Fase 36 (D9): parte de `total_expense` enlazada a sobres; decimal como string. */
  planned_expense: number | string;
}

export interface CategoryDistributionItem {
  category_id: number;
  category_name: string;
  category_icon?: string; // Fase 24 §24.4 — ícono real de la categoría (mismo campo que BudgetProgress)
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
  /** Fase 22 §22.4 — true si el usuario tiene contraseña (cuenta híbrida o por password);
   *  false para cuentas creadas solo con Google. Computado server-side desde
   *  `password_hash is not None` (Decisión D4), sin migración. */
  has_password: boolean;
  /** Fase 34 §B3 — zona IANA del usuario (default `America/Bogota`); única fuente de día/semana/
   *  mes del backend. Leer con `useTimezone()`. */
  timezone: string;
}

export interface PreferencesUpdatePayload {
  preferred_currency?: string;
  preferred_locale?: string;
  preferred_theme?: string;
  weekly_summary_enabled?: boolean;
  /** Fase 34 §B4 — nombre IANA válido; inválida → 422. No toca movimientos, solo reagrupa. */
  timezone?: string;
  /** Fase 22 §22.1 (Decisiones A2/A5) — instrucción por-request: además de actualizar la
   *  preferencia, cascadear la moneda a la cuenta por defecto si sigue virgen (nombre
   *  "Cuenta principal", balance 0, sin transacciones). No persiste en el usuario. */
  apply_to_default_account?: boolean;
}

export interface UserPreferences {
  preferred_currency: string;
  preferred_locale: string;
  preferred_theme: string;
  weekly_summary_enabled: boolean;
}

export interface CreateTransactionPayload {
  description: string | null;
  amount: number;
  type: 'income' | 'expense';
  /** Opcional: si se omite, el backend la puebla con server_default=func.now(). */
  date?: string;
  account_id: number;
  category_id: number;
  payment_method?: 'cash' | 'card' | 'transfer' | null;
  currency?: string;
  /** Fase 36 (D6): solo gastos, y la cuenta debe ser la del sobre. Se omite si no hay sobre. */
  fund_id?: number;
}

export interface UpdateTransactionPayload {
  id: number;
  description: string | null;
  amount: number;
  type: 'income' | 'expense';
  /** Fase 34 §B9: `YYYY-MM-DD` del `<input type="date">`, sin convertir. Se manda **solo si el
   *  usuario cambió la fecha** (así editar el monto no re-estampa la hora de un gasto de hoy). */
  date?: string;
  account_id: number;
  category_id: number;
  payment_method?: 'cash' | 'card' | 'transfer' | null;
  /** Fase 36 (D6): ausente conserva el enlace, `null` lo quita, otro id cambia de sobre. */
  fund_id?: number | null;
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
