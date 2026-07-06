export type CategoryType = "expense" | "income" | "transfer";
export type MatchField = "description" | "merchant_name" | "counterparty_name";
export type MatchOperator = "contains" | "equals" | "starts_with" | "ends_with" | "regex";
export type BudgetStatus = "active" | "scheduled" | "inactive";
export type BudgetUsageStatus = "on_track" | "watch" | "over";

export type ConnectionExpiryStatus = "unknown" | "active" | "expiring_soon" | "expired";

export interface Connection {
  connection_id: string;
  aspsp_name: string;
  aspsp_country: string;
  psu_type: string;
  session_id: string | null;
  session_status: string | null;
  active: boolean;
  authorized_at: string | null;
  last_synced_at: string | null;
  expires_at: string | null;
  days_until_expiry: number | null;
  expiry_status: ConnectionExpiryStatus;
  linked_account_count: number;
  latest_sync_status: string | null;
  latest_sync_started_at: string | null;
  latest_sync_finished_at: string | null;
  latest_sync_accounts_count: number | null;
  latest_sync_transactions_count: number | null;
  latest_sync_error_summary: string | null;
}

export interface Aspsp {
  name: string;
  country: string;
  [key: string]: unknown;
}

export interface StartAuthorizationResult {
  authorization_id: string | null;
  psu_id_hash: string | null;
  state: string;
  url: string;
  valid_until: string;
}

export interface ManualSyncResult {
  connection_id: string;
  sync_session_id: string;
  session_id: string | null;
  session_status: string;
  accounts_synced: number;
  transactions_imported: number;
  message: string | null;
}

export interface Account {
  account_id: string;
  display_name: string;
  currency: string;
  latest_balance_amount: string | null;
  latest_balance_currency: string | null;
  included_in_calculations: boolean;
  last_synced_at: string | null;
  source_connection_id: string | null;
  source_aspsp_name: string | null;
  source_aspsp_country: string | null;
  external_account_id: string | null;
}

export interface Transaction {
  transaction_id: string;
  account_id: string;
  account_display_name: string;
  booking_date: string | null;
  value_date: string | null;
  amount: string;
  currency: string;
  description: string | null;
  merchant_name: string | null;
  counterparty_name: string | null;
  direction: string;
  status: string;
  category_id: string | null;
  category_name: string | null;
  matched_rule_id: string | null;
  matched_rule_name: string | null;
  imported_at: string;
}

export interface Category {
  category_id: string;
  name: string;
  type: CategoryType;
  active: boolean;
}

export interface Rule {
  rule_id: string;
  name: string | null;
  match_field: MatchField;
  match_operator: MatchOperator;
  match_value: string;
  category_id: string;
  category_name: string;
  priority: number;
  active: boolean;
  created_from_manual_classification: boolean;
}

export interface Budget {
  budget_id: string;
  category_id: string;
  category_name: string;
  category_type: CategoryType;
  amount: string;
  currency: string;
  period_type: "monthly";
  active_from: string;
  active_to: string | null;
  is_fixed: boolean;
  active: boolean;
  status: BudgetStatus;
}

export interface BudgetUsage {
  category_id: string;
  category_name: string;
  budget_amount: string;
  spent_amount: string;
  remaining_amount: string;
  currency: string;
  utilization_percent: number;
  status: BudgetUsageStatus;
  is_fixed: boolean;
}

export interface SummaryDashboard {
  month: string;
  current_balance_amount: string;
  current_balance_currency: string | null;
  monthly_spending_amount: string;
  monthly_income_amount: string;
  net_cash_flow_amount: string;
  monthly_budget_amount: string;
  budgeted_spending_amount: string;
  unbudgeted_spending_amount: string;
  money_left_amount: string;
  uncategorized_count: number;
  days_elapsed: number;
  days_in_month: number;
  average_daily_spend_amount: string;
  expected_daily_spend_amount: string;
  projected_month_end_spend_amount: string;
  projected_overspend_amount: string;
  budget_usage: BudgetUsage[];
}

export interface TransactionsResponse {
  transactions: Transaction[];
  total_count: number;
  limit: number;
  offset: number;
}

export interface FiltersState {
  month: string;
  accountId: string;
  categoryId: string;
  status: string;
  categorized: "" | "true" | "false";
}

export interface PagingState {
  limit: number;
  offset: number;
  total: number;
}

export interface RuleDraft {
  name: string;
  category_id: string;
  match_field: MatchField;
  match_operator: MatchOperator;
  match_value: string;
  apply_to_existing_uncategorized: boolean;
}

export interface RuleUpdateDraft {
  name: string;
  match_field: MatchField;
  match_operator: MatchOperator;
  match_value: string;
  apply_to_existing_uncategorized: boolean;
}

export interface BudgetDraft {
  category_id: string;
  amount: string;
  currency: string;
  is_fixed: boolean;
}

export interface BudgetUpdateDraft {
  amount: string;
  currency: string;
  is_fixed: boolean;
}
