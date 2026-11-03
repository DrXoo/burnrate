export type CategoryType = "expense" | "income" | "transfer";
export type MatchField = "description" | "merchant_name" | "counterparty_name";
export type MatchOperator = "contains" | "equals" | "starts_with" | "ends_with" | "regex";
export type BudgetStatus = "active" | "scheduled" | "inactive";
export type BudgetUsageStatus = "on_track" | "watch" | "over";
/** Why the allowance reads as it does. The amount is null for the first three.

    The two tenses are separate values because a caption needs to tell them apart, and
    with one value this client derived the comparison itself off a UTC-derived month --
    which read a month that had not started as a closed one. Read the tense off here. */
export type SafeToSpendStatus =
  | "no_budget"
  | "month_closed"
  | "month_not_started"
  | BudgetUsageStatus;

/** Whether a comparison against what is normal is offered, and if not, why not.

    A month that has not started has no outcome to compare however much history sits
    behind it, so the reason is a value here rather than something this client works
    out by cross-referencing `safe_to_spend_status`. */
export type BaselineStatus = "ok" | "insufficient_history" | "month_not_started";

/** Which side of normal a figure is, and whether it is worth raising.

    Only `anomalous` is a warning. `below` is reported in full because a quiet month
    is information, but it never raises anything: the product exists to stop the owner
    overspending. The bands are the backend's; this client renders the words. */
export type BaselineComparisonStatus =
  | "no_baseline"
  | "below"
  | "in_line"
  | "above"
  | "anomalous";

/** One whole-month figure against its own normal.

    Net cash flow has no entry of this shape on purpose: a ratio on a figure that can
    cross zero means nothing, so it carries an amount and no verdict.

    `comparison_status` is the field that says whether there is a baseline at all.
    The amount is not: it can read "0.00" where the band says `no_baseline`, because
    a baseline of zero or less is one the backend refuses to divide by. Read it
    through `baselineFigure`, never with a truthiness check on the amount. */
export interface FigureBaseline {
  baseline_amount: string | null;
  deviation_percent: number | null;
  comparison_status: BaselineComparisonStatus;
}

export interface CategoryBaseline {
  category_id: string;
  category_name: string;
  // The figure the comparison is about. For the current month both sides are measured
  // to the same day of the month, so this can differ from the category's spend in
  // `budget_usage` when a standing order falls later in the month.
  spend_amount: string;
  // Null when the category is below the presence floor, or when there is too little
  // history for any baseline. It can also be "0.00" -- two months whose movements
  // cancel out will do it -- in which case `comparison_status` is `no_baseline` and
  // this field must not be printed. See `baselineFigure`.
  baseline_amount: string | null;
  deviation_percent: number | null;
  comparison_status: BaselineComparisonStatus;
}

export type ConnectionExpiryStatus = "unknown" | "active" | "expiring_soon" | "expired";

export interface Connection {
  connection_id: string;
  aspsp_name: string;
  aspsp_country: string;
  psu_type: string;
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
  excluded: boolean;
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
  /** Whether reopening this row would be accepted. Decided in the backend with the
      same function the reactivate endpoint refuses with, so a restore this page
      offers is never one the endpoint rejects. */
  can_reactivate: boolean;
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
  // The month the owner is in, on the owner's own clock. Compared against `month` to
  // decide a month's tense, because a month derived here from UTC disagrees with the
  // backend's for part of every month-end.
  current_month: string;
  // Null when there is no allowance to report, which the status distinguishes from
  // an allowance of zero: budgets exist, the month is current, they are used up.
  safe_to_spend_today_amount: string | null;
  safe_to_spend_status: SafeToSpendStatus;
  fixed_overrun_amount: string;
  pending_spend_amount: string;
  current_balance_amount: string;
  current_balance_currency: string | null;
  monthly_spending_amount: string;
  monthly_income_amount: string;
  // Neither income nor spend: money the owner moved in from an account BurnRate
  // cannot see. Shown beside the net it funded, never folded into it.
  inbound_transfer_amount: string;
  net_cash_flow_amount: string;
  savings_rate_percent: number;
  savings_status: BudgetUsageStatus;
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
  baseline_status: BaselineStatus;
  // How many Qualifying Months the means rest on. Shown beside them, so the owner
  // can see how much to trust a comparison resting on as few as two.
  baseline_months_count: number;
  category_baselines: CategoryBaseline[];
  // The spend the comparison can speak to, and the rest. Uncomparable Spend is the
  // residual -- monthly spending less the comparable half -- so the two reconcile
  // against the headline above them. Every euro in it is one the comparison cannot
  // speak to: a category with no baseline, an archived category, or spend dated after
  // today's cutoff.
  comparable_spend_amount: string;
  uncomparable_spend_amount: string;
  comparable_spend_baseline: FigureBaseline;
  monthly_income_baseline: FigureBaseline;
  net_cash_flow_baseline_amount: string | null;
  // Null when every day of the recent past was fetched, which is the normal case and
  // earns silence rather than a reassurance nobody asked for.
  sync_gap: SyncGap | null;
  // When the next unattended sync is due, with the owner's offset, or null when the
  // backend has no schedule configured. Published rather than derived because it is
  // `SYNC_CRON` read through `APP_TIMEZONE`, and a browser knows neither. An
  // intention, not a promise -- see `nextSyncLabel`.
  next_sync_at: string | null;
}

/** Days the bank was never asked about, with whether they can still be had.
    `status` is the backend's call, so the dashboard and the bot cannot word the
    difference between money already lost and a hole worth acting on differently. */
export interface SyncGap {
  status: "lost" | "lost_elsewhere" | "expiring";
  oldest_missing_day: string;
  newest_missing_day: string;
  missing_days: number;
  unrecoverable_days: number;
  recoverable_until: string | null;
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
  /** Whether the month holds a budget for the transaction's category. "false" is the
      Unbudgeted Spend of `GLOSSARY.md`: spend in an expense category this month has
      no budget for. The backend decides it, and it needs `month` to mean anything. */
  budgeted: "" | "true" | "false";
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
