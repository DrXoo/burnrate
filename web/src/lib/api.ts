import type {
  Account,
  Aspsp,
  Budget,
  SummaryDashboard,
  BudgetDraft,
  BudgetUpdateDraft,
  Category,
  Connection,
  FiltersState,
  ManualSyncResult,
  PagingState,
  Rule,
  RuleDraft,
  RuleUpdateDraft,
  StartAuthorizationResult,
  Transaction,
} from "../types";

export class ApiError extends Error {
  readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

// Registered by the app so any 401 (expired/absent session) can drop the user
// back to the login screen, no matter which call surfaced it.
let onUnauthorized: (() => void) | null = null;
export function setUnauthorizedHandler(handler: (() => void) | null): void {
  onUnauthorized = handler;
}

async function fetchJson<T>(url: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(url, {
    // Send the session cookie, including on the cross-origin dev setup
    // (web :3000 -> api :8000). The server must allow credentials in CORS.
    credentials: "include",
    headers: {
      Accept: "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  if (!response.ok) {
    if (response.status === 401) {
      onUnauthorized?.();
    }
    const body = await response.text();
    throw new ApiError(response.status, `Request failed (${response.status}): ${body}`);
  }

  return response.json() as Promise<T>;
}

function buildQuery(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") {
      search.set(key, String(value));
    }
  });
  const encoded = search.toString();
  return encoded ? `?${encoded}` : "";
}

function dedupe(values: string[]): string[] {
  return [...new Set(values.filter(Boolean))];
}

export async function detectApiBase(): Promise<string> {
  const candidates: string[] = [];

  if (window.BURNRATE_API_BASE) {
    candidates.push(window.BURNRATE_API_BASE);
  }

  // Same-origin first: in every deployed setup nginx proxies /api/v1 to the
  // backend, so this needs no knowledge of the host's IP or port and is never
  // subject to CORS. The :8000 candidates below are the `vite dev` fallback,
  // where nothing is proxying — they only work if the origin is listed in
  // APP_CORS_ORIGINS, so keep them last.
  //
  // There is deliberately no candidate for a non-local hostname on :8000. The
  // backend port is published on 127.0.0.1 only, so such a candidate could never
  // connect, and a firewall that drops rather than refuses would have stalled
  // startup on the browser's full TCP timeout: this loop awaits each candidate
  // with no deadline of its own.
  candidates.push(`${window.location.origin}/api/v1`);

  const hostname = window.location.hostname;
  const localHosts = new Set(["localhost", "127.0.0.1", "::1"]);
  if (localHosts.has(hostname)) {
    candidates.push(`http://${hostname}:8000/api/v1`);
    if (hostname === "localhost") {
      candidates.push("http://127.0.0.1:8000/api/v1");
    }
  }

  const errors: string[] = [];
  for (const candidate of dedupe(candidates)) {
    try {
      await fetchJson<{ status: string }>(`${candidate}/health`);
      return candidate;
    } catch (error) {
      errors.push(`${candidate} -> ${error instanceof Error ? error.message : String(error)}`);
    }
  }

  throw new Error(`Could not detect backend API base. Tried: ${errors.join(" | ")}`);
}

export async function getAuthStatus(apiBase: string): Promise<boolean> {
  const response = await fetch(`${apiBase}/auth/me`, {
    credentials: "include",
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    return false;
  }
  const body = (await response.json()) as { authenticated?: boolean };
  return Boolean(body.authenticated);
}

export async function login(apiBase: string, password: string): Promise<void> {
  // Deliberately bypasses fetchJson so a wrong-password 401 surfaces as a form
  // error here instead of tripping the global "session expired" handler.
  const response = await fetch(`${apiBase}/auth/login`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ password }),
  });
  if (response.ok) {
    return;
  }
  let detail = "";
  try {
    detail = ((await response.json()) as { detail?: string }).detail ?? "";
  } catch {
    // Non-JSON error body; fall back to a generic message below.
  }
  if (response.status === 401) {
    throw new ApiError(401, detail || "Incorrect password.");
  }
  if (response.status === 429) {
    throw new ApiError(429, detail || "Too many attempts. Please wait and try again.");
  }
  if (response.status === 503) {
    throw new ApiError(503, detail || "Login is not configured on the server yet.");
  }
  throw new ApiError(response.status, detail || `Login failed (${response.status}).`);
}

export async function logout(apiBase: string): Promise<void> {
  await fetch(`${apiBase}/auth/logout`, { method: "POST", credentials: "include" });
}

export async function getAspsps(apiBase: string, country: string): Promise<Aspsp[]> {
  const payload = await fetchJson<{ aspsps: Aspsp[] }>(
    `${apiBase}/integrations/enable-banking/aspsps${buildQuery({ country })}`,
  );
  return payload.aspsps ?? [];
}

export async function startBankAuthorization(
  apiBase: string,
  payload: { aspsp_name: string; aspsp_country: string; psu_type: "personal" | "business" },
): Promise<StartAuthorizationResult> {
  return fetchJson<StartAuthorizationResult>(`${apiBase}/integrations/enable-banking/auth/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function getConnections(apiBase: string): Promise<Connection[]> {
  const payload = await fetchJson<{ connections: Connection[] }>(`${apiBase}/integrations/enable-banking/connections`);
  return payload.connections ?? [];
}

export async function syncEnableBankingConnection(apiBase: string, connectionId: string): Promise<ManualSyncResult> {
  return fetchJson<ManualSyncResult>(`${apiBase}/integrations/enable-banking/connections/${connectionId}/sync`, {
    method: "POST",
  });
}

export async function getAccounts(apiBase: string): Promise<Account[]> {
  const payload = await fetchJson<{ accounts: Account[] }>(`${apiBase}/accounts`);
  return payload.accounts ?? [];
}

export async function updateAccountControls(
  apiBase: string,
  accountId: string,
  payload: {
    included_in_calculations: boolean;
  },
): Promise<Account> {
  return fetchJson<Account>(`${apiBase}/accounts/${accountId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function getCategories(apiBase: string): Promise<Category[]> {
  const payload = await fetchJson<{ categories: Category[] }>(`${apiBase}/categories`);
  return payload.categories ?? [];
}

export async function createCategory(
  apiBase: string,
  payload: { name: string; type: Category["type"] },
): Promise<Category> {
  return fetchJson<Category>(`${apiBase}/categories`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function getRules(apiBase: string): Promise<Rule[]> {
  const payload = await fetchJson<{ rules: Rule[] }>(`${apiBase}/rules`);
  return payload.rules ?? [];
}

export async function createRuleFromTransaction(
  apiBase: string,
  transactionId: string,
  draft: RuleDraft,
): Promise<Rule> {
  return fetchJson<Rule>(`${apiBase}/transactions/${transactionId}/rules`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      ...draft,
      name: draft.name.trim() || null,
    }),
  });
}

export async function updateRule(apiBase: string, ruleId: string, draft: RuleUpdateDraft): Promise<Rule> {
  return fetchJson<Rule>(`${apiBase}/rules/${ruleId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      ...draft,
      name: draft.name.trim() || null,
    }),
  });
}

export async function toggleRule(apiBase: string, ruleId: string, active: boolean): Promise<Rule> {
  return fetchJson<Rule>(`${apiBase}/rules/${ruleId}/status`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ active }),
  });
}

export async function deleteRule(apiBase: string, ruleId: string): Promise<void> {
  await fetchJson(`${apiBase}/rules/${ruleId}`, { method: "DELETE" });
}

export async function getBudgets(apiBase: string): Promise<Budget[]> {
  const payload = await fetchJson<{ budgets: Budget[] }>(`${apiBase}/budgets`);
  return payload.budgets ?? [];
}

export async function getSummary(apiBase: string, month: string): Promise<SummaryDashboard> {
  return fetchJson<SummaryDashboard>(`${apiBase}/summary${buildQuery({ month })}`);
}

export async function createBudgetForMonth(
  apiBase: string,
  draft: BudgetDraft,
  activeFrom: string,
): Promise<Budget> {
  return fetchJson<Budget>(`${apiBase}/budgets`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      category_id: draft.category_id,
      amount: draft.amount,
      currency: draft.currency.trim().toUpperCase(),
      active_from: activeFrom,
      is_fixed: draft.is_fixed,
    }),
  });
}

export async function updateBudget(apiBase: string, budgetId: string, draft: BudgetUpdateDraft): Promise<Budget> {
  return fetchJson<Budget>(`${apiBase}/budgets/${budgetId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      amount: draft.amount,
      currency: draft.currency.trim().toUpperCase(),
      is_fixed: draft.is_fixed,
    }),
  });
}

export async function deactivateBudget(apiBase: string, budgetId: string): Promise<Budget> {
  return fetchJson<Budget>(`${apiBase}/budgets/${budgetId}/deactivate`, {
    method: "POST",
  });
}

export async function getTransactions(
  apiBase: string,
  filters: FiltersState,
  paging: PagingState,
): Promise<{ transactions: Transaction[]; total_count: number; limit: number; offset: number }> {
  return fetchJson<{ transactions: Transaction[]; total_count: number; limit: number; offset: number }>(`${apiBase}/transactions${buildQuery({
    month: filters.month || undefined,
    account_id: filters.accountId || undefined,
    category_id: filters.categoryId || undefined,
    status: filters.status || undefined,
    categorized: filters.categorized || undefined,
    limit: paging.limit,
    offset: paging.offset,
  })}`);
}

export async function getUnknownQueue(
  apiBase: string,
  filters: FiltersState,
  paging: PagingState,
): Promise<{ transactions: Transaction[]; total_count: number; limit: number; offset: number }> {
  return fetchJson<{ transactions: Transaction[]; total_count: number; limit: number; offset: number }>(`${apiBase}/transactions/uncategorized${buildQuery({
    month: filters.month || undefined,
    account_id: filters.accountId || undefined,
    status: filters.status || undefined,
    limit: paging.limit,
    offset: paging.offset,
  })}`);
}

export async function getUncategorizedCount(apiBase: string, filters: FiltersState): Promise<number> {
  const payload = await fetchJson<{ count: number }>(`${apiBase}/transactions/uncategorized/count${buildQuery({
    month: filters.month || undefined,
    account_id: filters.accountId || undefined,
    status: filters.status || undefined,
  })}`);
  return payload.count ?? 0;
}

export async function categorizeTransaction(
  apiBase: string,
  transactionId: string,
  categoryId: string,
): Promise<void> {
  await fetchJson(`${apiBase}/transactions/${transactionId}/categorize`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ category_id: categoryId }),
  });
}

export async function uncategorizeTransaction(apiBase: string, transactionId: string): Promise<void> {
  await fetchJson(`${apiBase}/transactions/${transactionId}/uncategorize`, {
    method: "POST",
  });
}

export async function excludeTransaction(apiBase: string, transactionId: string): Promise<void> {
  await fetchJson(`${apiBase}/transactions/${transactionId}/exclude`, {
    method: "POST",
  });
}

export async function restoreTransaction(apiBase: string, transactionId: string): Promise<void> {
  await fetchJson(`${apiBase}/transactions/${transactionId}/restore`, {
    method: "POST",
  });
}
