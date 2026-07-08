import { startTransition, useEffect, useState } from "react";

import {
  categorizeTransaction,
  createBudgetForMonth,
  createCategory,
  createRuleFromTransaction,
  deactivateBudget,
  deleteRule,
  detectApiBase,
  getAccounts,
  getBudgets,
  getCategories,
  getConnections,
  getRules,
  getSummary,
  getTransactions,
  getUncategorizedCount,
  getUnknownQueue,
  syncEnableBankingConnection,
  toggleRule,
  uncategorizeTransaction,
  updateAccountControls,
  updateBudget,
  updateRule,
} from "../lib/api";
import { currentMonthValue } from "../lib/format";
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

export function useBurnRateData() {
  const [apiBase, setApiBase] = useState<string | null>(null);
  const [bootLoading, setBootLoading] = useState(true);
  const [bootError, setBootError] = useState<string | null>(null);

  const [connections, setConnections] = useState<Connection[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [rules, setRules] = useState<Rule[]>([]);
  const [budgets, setBudgets] = useState<Budget[]>([]);
  const [uncategorizedCount, setUncategorizedCount] = useState(0);
  const [summary, setSummary] = useState<SummaryDashboard | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(true);
  const [summaryError, setSummaryError] = useState<string | null>(null);

  const [filters, setFilters] = useState<FiltersState>({
    month: currentMonthValue(),
    accountId: "",
    categoryId: "",
    status: "",
    categorized: "",
  });
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

  useEffect(() => {
    let cancelled = false;

    async function boot() {
      try {
        const base = await detectApiBase();
        if (cancelled) {
          return;
        }
        setApiBase(base);

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

  useEffect(() => {
    if (!apiBase) {
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
    filters.accountId,
    filters.categoryId,
    filters.categorized,
    filters.month,
    filters.status,
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

  async function refreshLedgerViews() {
    if (!apiBase) {
      return;
    }
    const [transactionsPayload, countPayload, unknownPayload, summaryPayload] = await Promise.all([
      getTransactions(apiBase, filters, transactionsPaging),
      getUncategorizedCount(apiBase, filters),
      getUnknownQueue(apiBase, filters, unknownPaging),
      getSummary(apiBase, filters.month),
    ]);

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
  }

  // Fetch every transaction for the working month (ignoring account/category/status
  // filters) so the Categories view can aggregate accurate counts and per-category lists.
  async function listMonthTransactions() {
    if (!apiBase) {
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
    startTransition(() => {
      setFilters(nextFilters);
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

  return {
    apiBase,
    bootLoading,
    bootError,
    connections,
    accounts,
    categories,
    rules,
    budgets,
    summary,
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
    createRule: createRuleAction,
    updateRule: updateRuleAction,
    toggleRule: toggleRuleAction,
    deleteRule: deleteRuleAction,
    createBudget: createBudgetAction,
    updateBudget: updateBudgetAction,
    deactivateBudget: deactivateBudgetAction,
  };
}
