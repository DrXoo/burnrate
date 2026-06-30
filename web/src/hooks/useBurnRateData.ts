import { startTransition, useEffect, useState } from "react";

import {
  categorizeTransaction,
  createBudgetForMonth,
  createCategory,
  createRuleFromTransaction,
  deactivateBudget,
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
  toggleRule,
  uncategorizeTransaction,
  updateBudget,
  updateRule,
} from "../lib/api";
import { currentMonthStart, currentMonthValue } from "../lib/format";
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
    await createCategory(apiBase, { name, type });
    const nextCategories = await getCategories(apiBase);
    setCategories(nextCategories);
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
    await createRuleFromTransaction(apiBase, transactionId, draft);
    const nextRules = await getRules(apiBase);
    setRules(nextRules);
    await refreshLedgerViews();
  }

  async function updateRuleAction(ruleId: string, draft: RuleUpdateDraft) {
    if (!apiBase) {
      throw new Error("API base not loaded");
    }
    await updateRule(apiBase, ruleId, draft);
    const nextRules = await getRules(apiBase);
    setRules(nextRules);
    await refreshLedgerViews();
  }

  async function toggleRuleAction(ruleId: string, active: boolean) {
    if (!apiBase) {
      throw new Error("API base not loaded");
    }
    await toggleRule(apiBase, ruleId, active);
    const nextRules = await getRules(apiBase);
    setRules(nextRules);
  }

  async function createBudgetAction(draft: BudgetDraft) {
    if (!apiBase) {
      throw new Error("API base not loaded");
    }
    await createBudgetForMonth(apiBase, draft, currentMonthStart());
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
    refreshReferenceData,
    createCategory: createCategoryAction,
    categorizeTransaction: categorizeTransactionAction,
    uncategorizeTransaction: uncategorizeTransactionAction,
    createRule: createRuleAction,
    updateRule: updateRuleAction,
    toggleRule: toggleRuleAction,
    createBudget: createBudgetAction,
    updateBudget: updateBudgetAction,
    deactivateBudget: deactivateBudgetAction,
  };
}
