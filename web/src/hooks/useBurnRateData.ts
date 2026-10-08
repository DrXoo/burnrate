import { startTransition, useEffect, useRef, useState } from "react";

import {
  categorizeTransaction,
  createBudgetForMonth,
  createCategory,
  createRuleFromTransaction,
  deactivateBudget,
  deleteRule,
  detectApiBase,
  excludeTransaction,
  getAccounts,
  getAuthStatus,
  getBudgets,
  getCategories,
  getConnections,
  getRules,
  getSummary,
  getTransactions,
  getUncategorizedCount,
  getUnknownQueue,
  login as loginRequest,
  logout as logoutRequest,
  restoreTransaction,
  setUnauthorizedHandler,
  syncEnableBankingConnection,
  toggleRule,
  uncategorizeTransaction,
  updateAccountControls,
  updateBudget,
  updateRule,
} from "../lib/api";
import type {
  Account,
  Budget,
  BudgetDraft,
  BudgetUpdateDraft,
  Category,
  Connection,
  FiltersState,
  PagingState,
  Rule,
  RuleDraft,
  RuleUpdateDraft,
  SummaryDashboard,
  Transaction,
} from "../types";

interface TransactionBucket {
  items: Transaction[];
  total: number;
  loading: boolean;
  error: string | null;
}

type AuthStatus = "checking" | "authenticated" | "unauthenticated";

interface BurnRateDataOptions {
  /** Reports a background refresh that failed after an edit of its own had already
      succeeded. Kept as an injected reporter so the hook decides nothing about how
      it is shown, and so the edit's own error path stays separate from it. */
  onRefreshFailed?: (message: string) => void;
}

export function useBurnRateData({ onRefreshFailed }: BurnRateDataOptions = {}) {
  const [apiBase, setApiBase] = useState<string | null>(null);
  const [bootLoading, setBootLoading] = useState(true);
  const [bootError, setBootError] = useState<string | null>(null);
  const [authStatus, setAuthStatus] = useState<AuthStatus>("checking");

  const [connections, setConnections] = useState<Connection[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [rules, setRules] = useState<Rule[]>([]);
  const [budgets, setBudgets] = useState<Budget[]>([]);
  const [uncategorizedCount, setUncategorizedCount] = useState(0);
  const [summary, setSummary] = useState<SummaryDashboard | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(true);
  const [summaryError, setSummaryError] = useState<string | null>(null);

  // An empty month means "the month the backend calls current". The loader below
  // resolves it; nothing here reads a clock, because a month derived in the browser
  // disagrees with the backend's for part of every month-end.
  const [filters, setFilters] = useState<FiltersState>({
    month: "",
    accountId: "",
    categoryId: "",
    status: "",
    categorized: "",
  });
  // Bumped by every applyFilters, so asking for the same month again re-runs the loader.
  // Without it the one month that cannot be re-asked for is "" -- an opening summary that
  // failed leaves the month unresolved, and the deps below would never change again.
  const [reloadToken, setReloadToken] = useState(0);
  const [transactionsPaging, setTransactionsPaging] = useState<PagingState>({
    limit: 25,
    offset: 0,
    total: 0,
  });
  const [unknownPaging, setUnknownPaging] = useState<PagingState>({
    limit: 12,
    offset: 0,
    total: 0,
  });

  const [transactions, setTransactions] = useState<TransactionBucket>({
    items: [],
    total: 0,
    loading: true,
    error: null,
  });
  const [unknownQueue, setUnknownQueue] = useState<TransactionBucket>({
    items: [],
    total: 0,
    loading: true,
    error: null,
  });

  // The month a background refresh must still find selected when it resolves.
  // Such a refresh closes over the filters of the render that started it, so
  // without this a slow response can write the month the owner has already left.
  // Synced from an effect rather than during render, so it only ever holds a month
  // that was actually committed.
  const selectedMonth = useRef(filters.month);
  useEffect(() => {
    selectedMonth.current = filters.month;
  }, [filters.month]);

  useEffect(() => {
    let cancelled = false;

    async function boot() {
      try {
        const base = await detectApiBase();
        if (cancelled) {
          return;
        }
        setApiBase(base);

        const authenticated = await getAuthStatus(base);
        if (cancelled) {
          return;
        }
        if (!authenticated) {
          // Stop before touching any protected endpoint; App renders the login gate.
          startTransition(() => {
            setAuthStatus("unauthenticated");
            setBootError(null);
            setBootLoading(false);
          });
          return;
        }

        const [initialConnections, initialAccounts, initialCategories, initialRules, initialBudgets] =
          await Promise.all([
            getConnections(base),
            getAccounts(base),
            getCategories(base),
            getRules(base),
            getBudgets(base),
          ]);

        if (cancelled) {
          return;
        }

        startTransition(() => {
          setConnections(initialConnections);
          setAccounts(initialAccounts);
          setCategories(initialCategories);
          setRules(initialRules);
          setBudgets(initialBudgets);
          setAuthStatus("authenticated");
          setBootError(null);
          setBootLoading(false);
        });
      } catch (error) {
        if (cancelled) {
          return;
        }
        setBootError(error instanceof Error ? error.message : String(error));
        setBootLoading(false);
      }
    }

    void boot();
    return () => {
      cancelled = true;
    };
  }, []);

  // Any 401 from any call (expired or missing session) drops back to the login gate.
  useEffect(() => {
    setUnauthorizedHandler(() => setAuthStatus("unauthenticated"));
    return () => setUnauthorizedHandler(null);
  }, []);

  useEffect(() => {
    if (!apiBase || authStatus !== "authenticated") {
      return;
    }
    const base = apiBase;

    let cancelled = false;

    async function loadViews() {
      setTransactions((current) => ({ ...current, loading: true, error: null }));
      setUnknownQueue((current) => ({ ...current, loading: true, error: null }));
      setSummaryLoading(true);
      setSummaryError(null);

      try {
        // An omitted month means the current month only on /summary; on the three
        // ledger views it means every month ever. So the first load asks the summary
        // which month is current, adopts it, and lets this effect re-run with a month
        // to scope the views to. Everything stays in the loading state it is already in.
        if (!filters.month) {
          const openingSummary = await getSummary(base, "");
          if (cancelled) {
            return;
          }
          setFilters((current) => ({ ...current, month: openingSummary.current_month }));
          return;
        }

        const [transactionsPayload, countPayload, unknownPayload, summaryPayload] = await Promise.all([
          getTransactions(base, filters, transactionsPaging),
          getUncategorizedCount(base, filters),
          getUnknownQueue(base, filters, unknownPaging),
          getSummary(base, filters.month),
        ]);

        if (cancelled) {
          return;
        }

        startTransition(() => {
          setSummary(summaryPayload);
          setSummaryLoading(false);
          setSummaryError(null);
          setUncategorizedCount(countPayload);
        });

        let adjusted = false;
        if (transactionsPaging.offset > 0 && transactionsPaging.offset >= transactionsPayload.total_count) {
          adjusted = true;
          setTransactionsPaging((current) => ({
            ...current,
            offset: Math.max(0, current.offset - current.limit),
          }));
        }
        if (unknownPaging.offset > 0 && unknownPaging.offset >= unknownPayload.total_count) {
          adjusted = true;
          setUnknownPaging((current) => ({
            ...current,
            offset: Math.max(0, current.offset - current.limit),
          }));
        }
        if (adjusted) {
          return;
        }

        startTransition(() => {
          setTransactions({
            items: transactionsPayload.transactions,
            total: transactionsPayload.total_count,
            loading: false,
            error: null,
          });
          setTransactionsPaging((current) => ({ ...current, total: transactionsPayload.total_count }));
          setUnknownQueue({
            items: unknownPayload.transactions,
            total: unknownPayload.total_count,
            loading: false,
            error: null,
          });
          setUnknownPaging((current) => ({ ...current, total: unknownPayload.total_count }));
        });
      } catch (error) {
        if (cancelled) {
          return;
        }
        const message = error instanceof Error ? error.message : String(error);
        setTransactions((current) => ({ ...current, loading: false, error: message }));
        setUnknownQueue((current) => ({ ...current, loading: false, error: message }));
        setSummaryLoading(false);
        setSummaryError(message);
      }
    }

    void loadViews();
    return () => {
      cancelled = true;
    };
  }, [
    apiBase,
    authStatus,
    filters.accountId,
    filters.categoryId,
    filters.categorized,
    filters.month,
    filters.status,
    reloadToken,
    transactionsPaging.limit,
    transactionsPaging.offset,
    unknownPaging.limit,
    unknownPaging.offset,
  ]);

  async function refreshReferenceData() {
    if (!apiBase) {
      return;
    }
    const [nextConnections, nextAccounts, nextCategories, nextRules, nextBudgets] = await Promise.all([
      getConnections(apiBase),
      getAccounts(apiBase),
      getCategories(apiBase),
      getRules(apiBase),
      getBudgets(apiBase),
    ]);
    startTransition(() => {
      setConnections(nextConnections);
      setAccounts(nextAccounts);
      setCategories(nextCategories);
      setRules(nextRules);
      setBudgets(nextBudgets);
    });
  }

  async function loginAction(password: string) {
    if (!apiBase) {
      throw new Error("API base not loaded");
    }
    await loginRequest(apiBase, password);
    // Load reference data before flipping to authenticated so the app never
    // renders the empty "first run" state during the transition.
    await refreshReferenceData();
    setAuthStatus("authenticated");
  }

  async function logoutAction() {
    if (apiBase) {
      await logoutRequest(apiBase);
    }
    startTransition(() => {
      setAuthStatus("unauthenticated");
      setConnections([]);
      setAccounts([]);
    });
  }

  async function refreshLedgerViews() {
    if (!apiBase) {
      return;
    }
    if (!filters.month) {
      // No month has been resolved yet, which an edit can still reach: Sync sits in the
      // health strip on every section. Asking the three ledger views without a month
      // gets every transaction ever, and the gate below would wave it through because
      // the month it was requested for is the month still selected. The loader's second
      // phase is already about to fetch this month's views, so declining is not a loss.
      return;
    }
    const requestedMonth = filters.month;
    try {
      const [transactionsPayload, countPayload, unknownPayload, summaryPayload] = await Promise.all([
        getTransactions(apiBase, filters, transactionsPaging),
        getUncategorizedCount(apiBase, filters),
        getUnknownQueue(apiBase, filters, unknownPaging),
        getSummary(apiBase, filters.month),
      ]);

      // The owner reached another month while this was in flight. These payloads
      // describe the month they left, and the loader keyed on the new month is already
      // fetching its own, so writing them would put one month's rows and counts under
      // another month's heading.
      if (selectedMonth.current !== requestedMonth) {
        return;
      }

      startTransition(() => {
        setSummary(summaryPayload);
        setSummaryLoading(false);
        setSummaryError(null);
        setUncategorizedCount(countPayload);
      });

      let adjusted = false;
      if (transactionsPaging.offset > 0 && transactionsPaging.offset >= transactionsPayload.total_count) {
        adjusted = true;
        setTransactionsPaging((current) => ({
          ...current,
          offset: Math.max(0, current.offset - current.limit),
        }));
      }
      if (unknownPaging.offset > 0 && unknownPaging.offset >= unknownPayload.total_count) {
        adjusted = true;
        setUnknownPaging((current) => ({
          ...current,
          offset: Math.max(0, current.offset - current.limit),
        }));
      }
      if (adjusted) {
        return;
      }

      startTransition(() => {
        setTransactions({
          items: transactionsPayload.transactions,
          total: transactionsPayload.total_count,
          loading: false,
          error: null,
        });
        setTransactionsPaging((current) => ({ ...current, total: transactionsPayload.total_count }));
        setUnknownQueue({
          items: unknownPayload.transactions,
          total: unknownPayload.total_count,
          loading: false,
          error: null,
        });
        setUnknownPaging((current) => ({ ...current, total: unknownPayload.total_count }));
      });
    } catch (error) {
      // The edit this followed did land, so rethrowing would tell the owner their
      // change had failed when it had not. It is reported twice instead: the reporter
      // says the refresh failed, and summaryError marks the figures still on screen as
      // no longer trustworthy once that message has faded.
      if (selectedMonth.current !== requestedMonth) {
        return;
      }
      const message = error instanceof Error ? error.message : String(error);
      startTransition(() => {
        setSummaryLoading(false);
        setSummaryError(message);
      });
      onRefreshFailed?.(message);
    }
  }

  // Fetch every transaction for the working month (ignoring account/category/status
  // filters) so the Categories view can aggregate accurate counts and per-category lists.
  // An unresolved month is not "no month filter" here either: it would answer with every
  // transaction ever, which is what the two-phase load above exists to avoid.
  async function listMonthTransactions() {
    if (!apiBase || !filters.month) {
      return [];
    }
    const payload = await getTransactions(
      apiBase,
      { month: filters.month, accountId: "", categoryId: "", status: "", categorized: "" },
      { limit: 200, offset: 0, total: 0 },
    );
    return payload.transactions;
  }

  function applyFilters(nextFilters: FiltersState) {
    // A cleared month is not "no month filter" the way a cleared account is "no account
    // filter": the loader reads it as "the month the backend calls current" and resolves
    // it over the wire. A native month input can always be emptied from the keyboard, so
    // that is the one rule rather than two.
    startTransition(() => {
      setFilters(nextFilters);
      setReloadToken((current) => current + 1);
      setTransactionsPaging((current) => ({ ...current, offset: 0 }));
      setUnknownPaging((current) => ({ ...current, offset: 0 }));
    });
  }

  function moveTransactionsPage(direction: "prev" | "next") {
    setTransactionsPaging((current) => ({
      ...current,
      offset: direction === "prev" ? Math.max(0, current.offset - current.limit) : current.offset + current.limit,
    }));
  }

  function moveUnknownPage(direction: "prev" | "next") {
    setUnknownPaging((current) => ({
      ...current,
      offset: direction === "prev" ? Math.max(0, current.offset - current.limit) : current.offset + current.limit,
    }));
  }

  async function createCategoryAction(name: string, type: Category["type"]) {
    if (!apiBase) {
      throw new Error("API base not loaded");
    }
    const createdCategory = await createCategory(apiBase, { name, type });
    startTransition(() => {
      setCategories((current) => {
        const nextCategories = [...current.filter((category) => category.category_id !== createdCategory.category_id), createdCategory];
        nextCategories.sort((left, right) => {
          const typeOrder = ["expense", "income", "transfer"];
          const typeDelta = typeOrder.indexOf(left.type) - typeOrder.indexOf(right.type);
          if (typeDelta !== 0) {
            return typeDelta;
          }
          return left.name.localeCompare(right.name);
        });
        return nextCategories;
      });
    });

    const canonicalCategories = await getCategories(apiBase);
    setCategories(canonicalCategories);
  }

  async function updateAccountAction(
    accountId: string,
    draft: Pick<Account, "included_in_calculations">,
  ) {
    if (!apiBase) {
      throw new Error("API base not loaded");
    }

    await updateAccountControls(apiBase, accountId, {
      included_in_calculations: draft.included_in_calculations,
    });

    const nextAccounts = await getAccounts(apiBase);
    startTransition(() => {
      setAccounts(nextAccounts);
    });
    await refreshLedgerViews();
  }

  async function syncConnectionAction(connectionId: string) {
    if (!apiBase) {
      throw new Error("API base not loaded");
    }

    const result = await syncEnableBankingConnection(apiBase, connectionId);
    const nextConnections = await getConnections(apiBase);
    const nextAccounts = await getAccounts(apiBase);

    startTransition(() => {
      setConnections(nextConnections);
      setAccounts(nextAccounts);
    });
    await refreshLedgerViews();
    return result;
  }

  async function categorizeTransactionAction(transactionId: string, categoryId: string) {
    if (!apiBase) {
      throw new Error("API base not loaded");
    }
    await categorizeTransaction(apiBase, transactionId, categoryId);
    await refreshLedgerViews();
  }

  async function uncategorizeTransactionAction(transactionId: string) {
    if (!apiBase) {
      throw new Error("API base not loaded");
    }
    await uncategorizeTransaction(apiBase, transactionId);
    await refreshLedgerViews();
  }

  async function excludeTransactionAction(transactionId: string) {
    if (!apiBase) {
      throw new Error("API base not loaded");
    }
    await excludeTransaction(apiBase, transactionId);
    await refreshLedgerViews();
  }

  async function restoreTransactionAction(transactionId: string) {
    if (!apiBase) {
      throw new Error("API base not loaded");
    }
    await restoreTransaction(apiBase, transactionId);
    await refreshLedgerViews();
  }

  async function createRuleAction(transactionId: string, draft: RuleDraft) {
    if (!apiBase) {
      throw new Error("API base not loaded");
    }
    const createdRule = await createRuleFromTransaction(apiBase, transactionId, draft);
    const nextRules = await getRules(apiBase);
    setRules(nextRules);
    await refreshLedgerViews();
    // The backend may not have applied the new rule to existing transactions by
    // the time refreshLedgerViews() refetches, so optimistically attach the rule
    // (and its category) to the transaction it was created from. Applied after
    // the refetch so it wins over any stale row still lacking the match.
    setTransactions((current) => ({
      ...current,
      items: current.items.map((txn) =>
        txn.transaction_id === transactionId
          ? {
              ...txn,
              matched_rule_id: createdRule.rule_id,
              matched_rule_name: createdRule.name,
              category_id: createdRule.category_id,
              category_name: createdRule.category_name,
            }
          : txn,
      ),
    }));
  }

  async function updateRuleAction(ruleId: string, draft: RuleUpdateDraft) {
    if (!apiBase) {
      throw new Error("API base not loaded");
    }
    const updated = await updateRule(apiBase, ruleId, draft);
    setRules((current) => current.map((rule) => (rule.rule_id === updated.rule_id ? updated : rule)));
    await refreshLedgerViews();
  }

  async function toggleRuleAction(ruleId: string, active: boolean) {
    if (!apiBase) {
      throw new Error("API base not loaded");
    }
    const updated = await toggleRule(apiBase, ruleId, active);
    setRules((current) => current.map((rule) => (rule.rule_id === updated.rule_id ? updated : rule)));
  }

  async function deleteRuleAction(ruleId: string) {
    if (!apiBase) {
      throw new Error("API base not loaded");
    }
    await deleteRule(apiBase, ruleId);
    setRules((current) => current.filter((rule) => rule.rule_id !== ruleId));
    await refreshLedgerViews();
  }

  async function createBudgetAction(draft: BudgetDraft) {
    if (!apiBase) {
      throw new Error("API base not loaded");
    }
    if (!filters.month) {
      // The month the budget starts in is the month on screen, and there is no month on
      // screen until the backend has named one.
      throw new Error("The month is still loading");
    }
    // Create the budget for the month the user is currently viewing, not always
    // the real current month, so a new budget shows up in the summary they see.
    await createBudgetForMonth(apiBase, draft, `${filters.month}-01`);
    const [nextBudgets, nextSummary] = await Promise.all([getBudgets(apiBase), getSummary(apiBase, filters.month)]);
    setBudgets(nextBudgets);
    setSummary(nextSummary);
  }

  async function updateBudgetAction(budgetId: string, draft: BudgetUpdateDraft) {
    if (!apiBase) {
      throw new Error("API base not loaded");
    }
    await updateBudget(apiBase, budgetId, draft);
    const [nextBudgets, nextSummary] = await Promise.all([getBudgets(apiBase), getSummary(apiBase, filters.month)]);
    setBudgets(nextBudgets);
    setSummary(nextSummary);
  }

  async function deactivateBudgetAction(budgetId: string) {
    if (!apiBase) {
      throw new Error("API base not loaded");
    }
    await deactivateBudget(apiBase, budgetId);
    const [nextBudgets, nextSummary] = await Promise.all([getBudgets(apiBase), getSummary(apiBase, filters.month)]);
    setBudgets(nextBudgets);
    setSummary(nextSummary);
  }

  // A payload describes the month it was fetched for and no other. A failed refresh
  // leaves the previous month's payload in state while every consumer reads the month
  // now selected, so handing it over prints one month's figures under another month's
  // heading -- silently, because a page cannot tell a current payload from a stale
  // one. Withholding it puts those pages in the loading or error state they already
  // have for a month whose figures are unknown. The Categories page reached this
  // conclusion for its budget rows; this is that rule applied once, at the door.
  const summaryForSelectedMonth = summary && summary.month === filters.month ? summary : null;

  return {
    apiBase,
    bootLoading,
    bootError,
    authStatus,
    login: loginAction,
    logout: logoutAction,
    connections,
    accounts,
    categories,
    rules,
    budgets,
    summary: summaryForSelectedMonth,
    summaryLoading,
    summaryError,
    uncategorizedCount,
    filters,
    transactionsPaging,
    unknownPaging,
    transactions,
    unknownQueue,
    applyFilters,
    moveTransactionsPage,
    moveUnknownPage,
    listMonthTransactions,
    refreshReferenceData,
    createCategory: createCategoryAction,
    updateAccount: updateAccountAction,
    syncConnection: syncConnectionAction,
    categorizeTransaction: categorizeTransactionAction,
    uncategorizeTransaction: uncategorizeTransactionAction,
    excludeTransaction: excludeTransactionAction,
    restoreTransaction: restoreTransactionAction,
    createRule: createRuleAction,
    updateRule: updateRuleAction,
    toggleRule: toggleRuleAction,
    deleteRule: deleteRuleAction,
    createBudget: createBudgetAction,
    updateBudget: updateBudgetAction,
    deactivateBudget: deactivateBudgetAction,
  };
}
