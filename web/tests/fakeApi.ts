import type {
  Account,
  Budget,
  Category,
  Connection,
  FiltersState,
  PagingState,
  Rule,
  SummaryDashboard,
  Transaction,
} from "../src/types";

/** A stand-in for `lib/api`, the hook's only system boundary.
 *
 * It answers per month the way the backend does, including the asymmetry that
 * matters here: an omitted month means "the current month" on `/summary` and
 * "every month ever" on the three ledger views. Reads can also be held open or
 * made to fail for one month at a time, which is how a response that lands after
 * the owner has moved on gets staged. */

export const FAKE_API_BASE = "https://burnrate.test/api/v1";

interface MonthLedger {
  transactions: Transaction[];
  unknownQueue: Transaction[];
  summary: Partial<SummaryDashboard>;
  budgets: Budget[];
}

const ledgers = new Map<string, MonthLedger>();
const categoryStore = new Map<string, Category>();
const heldMonths = new Set<string>();
const resumers = new Map<string, (() => void)[]>();
const failures = new Map<string, string>();
let currentMonth = "2026-10";

function emptyLedger(): MonthLedger {
  return { transactions: [], unknownQueue: [], summary: {}, budgets: [] };
}

let unscopedLedgerReads = 0;

/** Controls the fake backend answers with. Drive it from the test, never from the hook.
 *
 *  Holds and failures are keyed on the month the caller *asked for*, so "" addresses the
 *  reads that omitted it -- the opening summary, and any ledger read that should never
 *  have been made. */
export const fakeApi = {
  reset(): void {
    ledgers.clear();
    categoryStore.clear();
    heldMonths.clear();
    resumers.clear();
    failures.clear();
    currentMonth = "2026-10";
    unscopedLedgerReads = 0;
  },
  /** The month the backend considers the owner to be in. */
  setCurrentMonth(month: string): void {
    currentMonth = month;
  },
  setMonth(month: string, ledger: Partial<MonthLedger>): void {
    ledgers.set(month, { ...emptyLedger(), ...ledger });
  },
  setCategories(categories: Category[]): void {
    categoryStore.clear();
    categories.forEach((category) => categoryStore.set(category.category_id, category));
  },
  /** Park every read that asks for this month until `resumeReads`. */
  holdReads(month: string): void {
    heldMonths.add(month);
  },
  resumeReads(month: string): void {
    heldMonths.delete(month);
    const parked = resumers.get(month) ?? [];
    resumers.delete(month);
    parked.forEach((resume) => resume());
  },
  failReads(month: string, message: string): void {
    failures.set(month, message);
  },
  healReads(month: string): void {
    failures.delete(month);
  },
  /** How many times the three month-windowed ledger views were asked for every month
      ever. The answer the backend gives such a read is correct and useless, so the only
      way to observe the mistake is that the question was asked at all. */
  unscopedLedgerReads(): number {
    return unscopedLedgerReads;
  },
};

async function awaitTurn(month: string): Promise<void> {
  if (!heldMonths.has(month)) {
    return;
  }
  await new Promise<void>((resolve) => {
    resumers.set(month, [...(resumers.get(month) ?? []), resolve]);
  });
}

async function read<T>(requestedMonth: string, answer: () => T): Promise<T> {
  await awaitTurn(requestedMonth);
  const failure = failures.get(requestedMonth);
  if (failure) {
    throw new Error(failure);
  }
  return answer();
}

async function readLedger<T>(requestedMonth: string, answer: () => T): Promise<T> {
  if (!requestedMonth) {
    unscopedLedgerReads += 1;
  }
  return read(requestedMonth, answer);
}

function ledgerFor(month: string): MonthLedger {
  return ledgers.get(month) ?? emptyLedger();
}

/** An omitted month on a ledger view means every month ever, oldest first. */
function rowsFor(month: string, pick: (ledger: MonthLedger) => Transaction[]): Transaction[] {
  if (month) {
    return pick(ledgerFor(month));
  }
  return [...ledgers.keys()].sort().flatMap((key) => pick(ledgerFor(key)));
}

function page(rows: Transaction[], paging: PagingState) {
  return {
    transactions: rows.slice(paging.offset, paging.offset + paging.limit),
    total_count: rows.length,
    limit: paging.limit,
    offset: paging.offset,
  };
}

export function summaryFor(month: string): SummaryDashboard {
  const resolved = month || currentMonth;
  return {
    month: resolved,
    current_month: currentMonth,
    safe_to_spend_today_amount: "40.00",
    safe_to_spend_status: "on_track",
    fixed_overrun_amount: "0.00",
    pending_spend_amount: "0.00",
    current_balance_amount: "1000.00",
    current_balance_currency: "EUR",
    monthly_spending_amount: "0.00",
    monthly_income_amount: "0.00",
    net_cash_flow_amount: "0.00",
    savings_rate_percent: 0,
    savings_status: "on_track",
    monthly_budget_amount: "0.00",
    budgeted_spending_amount: "0.00",
    unbudgeted_spending_amount: "0.00",
    money_left_amount: "0.00",
    uncategorized_count: ledgerFor(resolved).unknownQueue.length,
    days_elapsed: 1,
    days_in_month: 30,
    average_daily_spend_amount: "0.00",
    expected_daily_spend_amount: "0.00",
    projected_month_end_spend_amount: "0.00",
    projected_overspend_amount: "0.00",
    budget_usage: [],
    ...ledgerFor(resolved).summary,
  };
}

export function budget(categoryName: string, overrides: Partial<Budget> = {}): Budget {
  return {
    budget_id: `budget-${categoryName.toLowerCase()}`,
    category_id: `cat-${categoryName.toLowerCase()}`,
    category_name: categoryName,
    category_type: "expense",
    amount: "800.00",
    currency: "EUR",
    period_type: "monthly",
    active_from: "2025-01-01",
    active_to: null,
    is_fixed: true,
    active: true,
    status: "active",
    can_reactivate: false,
    ...overrides,
  };
}

export function transaction(
  transactionId: string,
  description: string,
  overrides: Partial<Transaction> = {},
): Transaction {
  return {
    transaction_id: transactionId,
    account_id: "acc-1",
    account_display_name: "Checking ···4021",
    booking_date: "2026-10-02",
    value_date: null,
    amount: "-40.00",
    currency: "EUR",
    description,
    merchant_name: null,
    counterparty_name: null,
    direction: "debit",
    status: "booked",
    category_id: null,
    category_name: null,
    matched_rule_id: null,
    matched_rule_name: null,
    excluded: false,
    imported_at: "2026-10-02T09:00:00Z",
    ...overrides,
  };
}

// --- the `lib/api` surface -------------------------------------------------

export async function detectApiBase(): Promise<string> {
  return FAKE_API_BASE;
}

export async function getAuthStatus(): Promise<boolean> {
  return true;
}

export function setUnauthorizedHandler(): void {
  // The hook registers one on mount; nothing in these tests sends a 401.
}

export async function getConnections(): Promise<Connection[]> {
  return [];
}

export async function getAccounts(): Promise<Account[]> {
  return [];
}

export async function getCategories(): Promise<Category[]> {
  return [...categoryStore.values()];
}

export async function getRules(): Promise<Rule[]> {
  return [];
}

export async function getBudgets(_apiBase: string, month: string): Promise<Budget[]> {
  // Budgets are per month like the summary is, so this answers the month it was
  // asked for. A fake that returned one list whatever was requested would agree
  // with a caller that never passes the month -- the defect under test.
  //
  // An omitted month means the month the owner is in, as it does on `/summary`.
  return read(month, () => ledgerFor(month || currentMonth).budgets);
}

export async function getSummary(_apiBase: string, month: string): Promise<SummaryDashboard> {
  return read(month, () => summaryFor(month));
}

export async function getTransactions(_apiBase: string, filters: FiltersState, paging: PagingState) {
  return readLedger(filters.month, () =>
    page(rowsFor(filters.month, (ledger) => ledger.transactions), paging),
  );
}

export async function getUnknownQueue(_apiBase: string, filters: FiltersState, paging: PagingState) {
  return readLedger(filters.month, () =>
    page(rowsFor(filters.month, (ledger) => ledger.unknownQueue), paging),
  );
}

export async function getUncategorizedCount(_apiBase: string, filters: FiltersState): Promise<number> {
  return readLedger(
    filters.month,
    () => rowsFor(filters.month, (ledger) => ledger.unknownQueue).length,
  );
}

export async function categorizeTransaction(): Promise<void> {
  // Accepted immediately; the refresh it triggers is what these tests stage.
}

function notExercised(name: string) {
  return async (): Promise<never> => {
    throw new Error(`${name} is not exercised by these tests`);
  };
}

export const createBudgetForMonth = notExercised("createBudgetForMonth");
export const createCategory = notExercised("createCategory");

export async function deleteCategory(_apiBase: string, categoryId: string): Promise<void> {
  // Strict about what the backend allows: a category anything points at is refused
  // there, so a fake that deleted it regardless would let a caller look correct while
  // asking for something the real endpoint rejects.
  if (!categoryStore.has(categoryId)) {
    throw new Error(`Category not found for id ${categoryId}`);
  }
  for (const ledger of ledgers.values()) {
    if (ledger.budgets.some((row) => row.category_id === categoryId)) {
      throw new Error("Category 'X' is still used by 1 budget");
    }
  }
  categoryStore.delete(categoryId);
}

export async function archiveCategory(_apiBase: string, categoryId: string): Promise<Category> {
  return setCategoryActive(categoryId, false);
}

export async function unarchiveCategory(_apiBase: string, categoryId: string): Promise<Category> {
  return setCategoryActive(categoryId, true);
}

function setCategoryActive(categoryId: string, active: boolean): Category {
  const category = categoryStore.get(categoryId);
  if (category === undefined) {
    throw new Error(`Category not found for id ${categoryId}`);
  }
  const updated = { ...category, active };
  categoryStore.set(categoryId, updated);
  return updated;
}

export async function renameCategory(
  _apiBase: string,
  categoryId: string,
  name: string,
): Promise<Category> {
  // Strict about the id: a caller that renames the wrong category, or passes an id
  // it never had, fails here rather than getting a payload back that agrees with it.
  const category = categoryStore.get(categoryId);
  if (category === undefined) {
    throw new Error(`Category not found for id ${categoryId}`);
  }
  const renamed = { ...category, name };
  categoryStore.set(categoryId, renamed);
  // Budget rows and rules label themselves with the category's name through a join,
  // so the rename lands on them too -- which is what makes a missing refresh in the
  // caller observable instead of invisible.
  for (const ledger of ledgers.values()) {
    ledger.budgets = ledger.budgets.map((row) =>
      row.category_id === categoryId ? { ...row, category_name: name } : row,
    );
  }
  return renamed;
}
export const createRuleFromTransaction = notExercised("createRuleFromTransaction");
export async function deactivateBudget(
  _apiBase: string,
  budgetId: string,
  month: string,
): Promise<Budget> {
  // Applies the cancellation to the month it was told about, which is the whole
  // question here: the backend closes the window relative to that month, so a caller
  // that sends its own idea of "now" changes a month the owner was not looking at.
  // A fake that cancelled everywhere would agree with either caller.
  if (!month) {
    throw new Error("deactivateBudget was given no month");
  }
  const ledger = ledgerFor(month);
  let cancelled: Budget | null = null;
  ledger.budgets = ledger.budgets.map((row) => {
    if (row.budget_id !== budgetId) {
      return row;
    }
    cancelled = { ...row, active: false, status: "inactive", active_to: `${month}-01` };
    return cancelled;
  });
  if (cancelled === null) {
    throw new Error(`Budget not found for id ${budgetId} in ${month}`);
  }
  return cancelled;
}

export async function reactivateBudget(_apiBase: string, budgetId: string): Promise<Budget> {
  // The backend reopens the window on the same row, so a month that had dropped the
  // budget holds it again. Ledgers here are per month, so the row is restored
  // wherever this fake was told it exists -- which is what makes the refresh the
  // hook does afterwards observable, rather than agreeing with it by returning a
  // fixed payload.
  let restored: Budget | null = null;
  for (const ledger of ledgers.values()) {
    ledger.budgets = ledger.budgets.map((row) => {
      if (row.budget_id !== budgetId) {
        return row;
      }
      restored = { ...row, active_to: null, active: true, status: "active" };
      return restored;
    });
  }
  if (restored === null) {
    throw new Error(`Budget not found for id ${budgetId}`);
  }
  return restored;
}
export const deleteRule = notExercised("deleteRule");
export const excludeTransaction = notExercised("excludeTransaction");
export const login = notExercised("login");
export const logout = notExercised("logout");
export const restoreTransaction = notExercised("restoreTransaction");
export const syncEnableBankingConnection = notExercised("syncEnableBankingConnection");
export const toggleRule = notExercised("toggleRule");
export const uncategorizeTransaction = notExercised("uncategorizeTransaction");
export const updateAccountControls = notExercised("updateAccountControls");
export const updateBudget = notExercised("updateBudget");
export const updateRule = notExercised("updateRule");
