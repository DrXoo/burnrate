import { useEffect, useMemo, useState, type CSSProperties } from "react";

import { IconPencil } from "../icons";

import {
  TONE_COLOR,
  TONE_DIM,
  TONE_LABEL,
  capitalize,
  categoryColor,
  eur,
  eurPlain,
  shortAccount,
  transactionTitle,
  usageTone,
} from "../../lib/format";
import type { Tone } from "../../lib/format";
import type { BudgetUsage, Category, CategoryType, SummaryDashboard, Transaction } from "../../types";

interface CategoriesPageProps {
  categories: Category[];
  summary: SummaryDashboard | null;
  loading: boolean;
  error: string | null;
  month: string;
  monthLabel: string;
  loadMonthTransactions: () => Promise<Transaction[]>;
  onCreateCategory: (name: string, type: CategoryType) => Promise<void>;
  /** Renames a category by id. The name is the label every other surface reads, so
      this panel edits it rather than keeping a display name of its own. */
  onRenameCategory: (categoryId: string, name: string) => Promise<void>;
  /** Removes the category outright. Refused by the backend unless nothing points at
      it, and the refusal names what does. */
  onDeleteCategory: (categoryId: string) => Promise<void>;
  /** Closes the category to new spend while keeping what it already recorded. */
  onArchiveCategory: (categoryId: string) => Promise<void>;
  onUnarchiveCategory: (categoryId: string) => Promise<void>;
}

interface CategoryStat {
  category: Category;
  /** The month's budget row from the backend, when this category has one. Every
      budget figure and the verdict are read off it, so this page and the dashboard
      cannot disagree about the same category. */
  usage: BudgetUsage | undefined;
  budget: number | null;
  spent: number;
  tone: Tone;
  color: string;
  count: number;
  total: number;
}

const FLOW: Record<CategoryType, string> = {
  expense: "spent",
  income: "received",
  transfer: "moved",
};

const GROUPS: Array<{ label: string; type: CategoryType }> = [
  { label: "Expenses", type: "expense" },
  { label: "Income", type: "income" },
  { label: "Transfers", type: "transfer" },
];

// Local like the other pages' copies of these. Extracting a shared set is a
// refactor of three pages, not part of renaming a category.
const accentButton: CSSProperties = {
  border: "none",
  background: "var(--accent)",
  color: "#0a0d10",
  borderRadius: 8,
  padding: "7px 16px",
  font: "600 12px 'Hanken Grotesque', sans-serif",
  cursor: "pointer",
};

const ghostButton: CSSProperties = {
  border: "1px solid var(--line-2)",
  background: "transparent",
  color: "var(--text-2)",
  borderRadius: 8,
  padding: "7px 14px",
  font: "500 12px 'Hanken Grotesque', sans-serif",
  cursor: "pointer",
};

const iconButton: CSSProperties = {
  flex: "none",
  width: 28,
  height: 28,
  borderRadius: 7,
  border: "1px solid var(--line-2)",
  background: "var(--bg-2)",
  color: "var(--text-2)",
  cursor: "pointer",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
};

const statCard: CSSProperties = {
  background: "var(--bg-3)",
  border: "1px solid var(--line)",
  borderRadius: 11,
  padding: "13px 14px",
};

interface BudgetNotice {
  text: string;
  /** "alert" when the figures on screen cannot be trusted; "info" when the page is
      merely reporting what it does not know yet. */
  severity: "alert" | "info";
}

/** The one line above the list that says what state the month's budget figures are in,
    or null when they need no explaining. */
function budgetNotice(budgetsKnown: boolean, loading: boolean, error: string | null, monthLabel: string): BudgetNotice | null {
  // The month's rows are on screen. A refresh that failed for this same month leaves
  // them in place, so they are the right month's figures and merely old -- marked
  // rather than withdrawn, because they are still the last figures the owner had and
  // the toast that reported the failure has faded by the time they are read.
  if (budgetsKnown) {
    return error ? { text: `These budget figures may be out of date \u2014 ${error}`, severity: "alert" } : null;
  }
  if (loading) {
    return { text: `Loading budgets for ${monthLabel}\u2026`, severity: "info" };
  }
  if (error) {
    return { text: `Budget figures unavailable: ${error}`, severity: "alert" };
  }
  return { text: "Budget figures are unavailable for this month.", severity: "info" };
}

function num(value: string | null | undefined): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

export function CategoriesPage({
  categories,
  summary,
  loading,
  error,
  month,
  monthLabel,
  loadMonthTransactions,
  onCreateCategory,
  onRenameCategory,
  onDeleteCategory,
  onArchiveCategory,
  onUnarchiveCategory,
}: CategoriesPageProps) {
  const [selectedId, setSelectedId] = useState<string>("");
  const [showNew, setShowNew] = useState(false);
  const [newName, setNewName] = useState("");
  const [newType, setNewType] = useState<CategoryType>("expense");
  const [monthTxns, setMonthTxns] = useState<Transaction[]>([]);

  // Pull the whole month once so per-category counts and lists are accurate,
  // not limited to the paginated ledger view.
  useEffect(() => {
    let cancelled = false;
    void loadMonthTransactions().then((transactions) => {
      if (!cancelled) {
        setMonthTxns(transactions);
      }
    });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [month]);

  // The month's budget rows only exist in a summary *for that month*, and
  // `useBurnRateData` withholds a payload fetched for any other month, so a null
  // summary here means the month's budgets are unknown -- loading or failed. That is a
  // third state, distinct from "this category has no budget this month", which is a
  // payload that carries no row for it.
  const budgetsKnown = summary !== null;

  const notice = budgetNotice(budgetsKnown, loading, error, monthLabel);

  const stats = useMemo<CategoryStat[]>(() => {
    const usageById = new Map((summary?.budget_usage ?? []).map((usage) => [usage.category_id, usage]));
    const ledgerCount: Record<string, number> = {};
    const ledgerTotal: Record<string, number> = {};
    for (const transaction of monthTxns) {
      if (!transaction.category_id) {
        continue;
      }
      ledgerCount[transaction.category_id] = (ledgerCount[transaction.category_id] ?? 0) + 1;
      ledgerTotal[transaction.category_id] = (ledgerTotal[transaction.category_id] ?? 0) + Math.abs(num(transaction.amount));
    }

    return categories.map((category) => {
      const usage = usageById.get(category.category_id);
      const ledgerSpent = ledgerTotal[category.category_id] ?? 0;
      // Every budget active in the month being viewed has a usage row, spend or no
      // spend, so no row means no budget for that month. A budget record that is
      // active *now* says nothing about the month on screen, which is why it is not
      // a fallback: it would print next month's amount beside this month's spend.
      const budget = usage ? num(usage.budget_amount) : null;
      const spent = usage ? num(usage.spent_amount) : ledgerSpent;

      // Only the backend bands a budget. With no budget row for the month being
      // viewed there is no verdict to show, so the category reads neutral rather
      // than this page inventing a threshold of its own.
      const tone: Tone = category.type === "expense" && usage ? usageTone(usage.status) : "neutral";

      return {
        category,
        usage,
        budget,
        spent,
        tone,
        color: categoryColor(category.type, tone),
        count: ledgerCount[category.category_id] ?? 0,
        total: ledgerTotal[category.category_id] ?? 0,
      };
    });
  }, [categories, summary, monthTxns]);

  const selected = stats.find((stat) => stat.category.category_id === selectedId) ?? stats[0];

  async function handleAdd() {
    const name = newName.trim() || "New category";
    await onCreateCategory(name, newType);
    setShowNew(false);
    setNewName("");
    setNewType("expense");
  }

  const selectedTxns = selected ? monthTxns.filter((transaction) => transaction.category_id === selected.category.category_id) : [];

  return (
    <div className="br-cols" style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1.5fr)", gap: 14 }}>
      {/* LIST */}
      <div
        style={{
          background: "var(--bg-2)",
          border: "1px solid var(--line)",
          borderRadius: 16,
          padding: 18,
          boxShadow: "var(--card-shadow)",
          alignSelf: "start",
          minWidth: 0,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
          <div style={{ fontSize: 15, fontWeight: 600 }}>Categories</div>
          <span style={{ fontSize: 12, color: "var(--text-3)" }}>
            <span className="num">{categories.length}</span> total
          </span>
        </div>

        {notice ? (
          <div
            style={{
              marginBottom: 12,
              padding: "9px 11px",
              borderRadius: 10,
              background: notice.severity === "alert" ? "var(--over-dim)" : "var(--bg-3)",
              border: `1px solid ${notice.severity === "alert" ? "color-mix(in oklab, var(--over) 30%, transparent)" : "var(--line)"}`,
              color: notice.severity === "alert" ? "var(--over)" : "var(--text-3)",
              fontSize: 11.5,
            }}
          >
            {notice.text}
          </div>
        ) : null}

        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {GROUPS.map((group) => {
            const groupStats = stats.filter((stat) => stat.category.type === group.type);
            if (groupStats.length === 0) {
              return null;
            }
            return (
              <div key={group.type}>
                <div
                  style={{
                    fontSize: 10.5,
                    textTransform: "uppercase",
                    letterSpacing: "0.07em",
                    color: "var(--text-3)",
                    fontWeight: 700,
                    padding: "2px 4px 6px",
                  }}
                >
                  {group.label}
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                  {groupStats.map((stat) => {
                    const isSelected = selected?.category.category_id === stat.category.category_id;
                    const isExpense = stat.category.type === "expense";
                    const barPct = stat.usage ? `${Math.min(100, Math.max(0, stat.usage.utilization_percent)).toFixed(0)}%` : "0%";
                    const pctStr = stat.usage ? `${Math.round(stat.usage.utilization_percent)}%` : "—";
                    return (
                      <button
                        key={stat.category.category_id}
                        type="button"
                        onClick={() => setSelectedId(stat.category.category_id)}
                        style={{
                          textAlign: "left",
                          border: `1px solid ${isSelected ? "var(--line-2)" : "transparent"}`,
                          background: isSelected ? "var(--bg-3)" : "transparent",
                          borderRadius: 11,
                          padding: "11px 12px",
                          cursor: "pointer",
                          fontFamily: "'Hanken Grotesque', sans-serif",
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
                          <span style={{ width: 9, height: 9, borderRadius: 2, background: stat.color, flex: "none" }} />
                          <span style={{ flex: 1, minWidth: 0, fontSize: 13.5, fontWeight: 500, color: stat.category.active ? "var(--text)" : "var(--text-3)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                            {stat.category.name}
                            {!stat.category.active ? (
                              <span style={{ fontSize: 11, color: "var(--text-3)", fontWeight: 500 }}> · archived</span>
                            ) : null}
                          </span>
                          <span className="num" style={{ fontSize: 11.5, color: "var(--text-3)" }}>
                            {stat.count} txns
                          </span>
                        </div>
                        {isExpense ? (
                          <>
                            <div style={{ position: "relative", height: 6, background: "var(--bg-4)", borderRadius: 4, overflow: "hidden", marginTop: 7 }}>
                              <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: barPct, background: stat.color, borderRadius: 4 }} />
                            </div>
                            <div style={{ display: "flex", justifyContent: "space-between", marginTop: 5 }}>
                              <span className="num" style={{ fontSize: 11, color: "var(--text-3)" }}>
                                {eurPlain(stat.spent)} / {stat.budget != null ? eurPlain(stat.budget) : budgetsKnown ? "no budget" : "—"}
                              </span>
                              <span style={{ fontSize: 11, fontWeight: 600, color: stat.color }}>{pctStr}</span>
                            </div>
                          </>
                        ) : (
                          <div className="num" style={{ fontSize: 11.5, color: "var(--text-3)", marginTop: 6 }}>
                            {eurPlain(stat.total)} {FLOW[stat.category.type]}
                          </div>
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>

        <div style={{ marginTop: 12, borderTop: "1px solid var(--line)", paddingTop: 12 }}>
          {showNew ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <input
                className="br-input"
                value={newName}
                onChange={(event) => setNewName(event.target.value)}
                placeholder="Category name"
              />
              <div style={{ display: "flex", gap: 8 }}>
                <select className="br-sel" style={{ flex: 1 }} value={newType} onChange={(event) => setNewType(event.target.value as CategoryType)}>
                  <option value="expense">Expense</option>
                  <option value="income">Income</option>
                  <option value="transfer">Transfer</option>
                </select>
                <button
                  type="button"
                  onClick={handleAdd}
                  style={{
                    border: "none",
                    background: "var(--accent)",
                    color: "#0a0d10",
                    borderRadius: 8,
                    padding: "8px 15px",
                    font: "600 12.5px 'Hanken Grotesque', sans-serif",
                    cursor: "pointer",
                  }}
                >
                  Add
                </button>
              </div>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setShowNew(true)}
              style={{
                width: "100%",
                padding: 9,
                border: "1px dashed var(--line-2)",
                background: "transparent",
                color: "var(--text-2)",
                borderRadius: 9,
                font: "500 12.5px 'Hanken Grotesque', sans-serif",
                cursor: "pointer",
              }}
            >
              + New category
            </button>
          )}
        </div>
      </div>

      {/* DETAIL */}
      <div
        style={{
          background: "var(--bg-2)",
          border: "1px solid var(--line)",
          borderRadius: 16,
          padding: 22,
          boxShadow: "var(--card-shadow)",
          minWidth: 0,
        }}
      >
        {selected ? (
          <CategoryDetail
            selected={selected}
            monthLabel={monthLabel}
            budgetsKnown={budgetsKnown}
            count={selectedTxns.length}
            txns={selectedTxns}
            onRenameCategory={onRenameCategory}
            onDeleteCategory={onDeleteCategory}
            onArchiveCategory={onArchiveCategory}
            onUnarchiveCategory={onUnarchiveCategory}
          />
        ) : (
          <div style={{ padding: 26, textAlign: "center", color: "var(--text-3)", fontSize: 13 }}>No categories yet.</div>
        )}
      </div>
    </div>
  );
}

function CategoryDetail({
  selected,
  monthLabel,
  budgetsKnown,
  count,
  txns,
  onRenameCategory,
  onDeleteCategory,
  onArchiveCategory,
  onUnarchiveCategory,
}: {
  selected: CategoryStat;
  monthLabel: string;
  /** False while the month's budget rows are loading or failed: the panel then says
      it does not know rather than reporting that no budget exists. */
  budgetsKnown: boolean;
  count: number;
  txns: Transaction[];
  onRenameCategory: (categoryId: string, name: string) => Promise<void>;
  onDeleteCategory: (categoryId: string) => Promise<void>;
  onArchiveCategory: (categoryId: string) => Promise<void>;
  onUnarchiveCategory: (categoryId: string) => Promise<void>;
}) {
  const { category, tone, color, usage } = selected;
  const [renaming, setRenaming] = useState(false);
  const [draftName, setDraftName] = useState(category.name);
  const [renameError, setRenameError] = useState<string | null>(null);

  // Selecting another category drops a rename left half-typed on the previous one:
  // the open field belongs to the row it was opened on, not to the panel.
  useEffect(() => {
    setRenaming(false);
    setDraftName(category.name);
    setRenameError(null);
  }, [category.category_id, category.name]);

  // Delete is armed by a first click. It is the only act on this panel with no way
  // back, and it sits beside Archive, which has one.
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [lifecycleError, setLifecycleError] = useState<string | null>(null);

  useEffect(() => {
    setConfirmingDelete(false);
    setLifecycleError(null);
  }, [category.category_id]);

  /** Runs one lifecycle act, keeping its refusal on screen.
   *
   *  The refusal is the useful part: it names the budgets, transactions or rules
   *  still pointing at the category, which is what the owner has to clear first. */
  async function runLifecycle(act: () => Promise<void>) {
    setLifecycleError(null);
    try {
      await act();
    } catch (error) {
      setLifecycleError(error instanceof Error ? error.message : String(error));
    }
  }

  async function saveName() {
    const name = draftName.trim();
    if (!name) {
      return;
    }
    if (name === category.name) {
      setRenaming(false);
      return;
    }
    setRenameError(null);
    try {
      await onRenameCategory(category.category_id, name);
    } catch (error) {
      setRenameError(error instanceof Error ? error.message : String(error));
      return;
    }
    setRenaming(false);
  }

  const isExpense = category.type === "expense";
  // A budget panel needs the month's budget row: that is where the figures come from.
  const hasBudget = isExpense && usage != null;
  const badgeLabel = hasBudget ? TONE_LABEL[tone] : capitalize(category.type);
  const badgeColor = hasBudget ? color : "var(--text-2)";
  const badgeDim = hasBudget ? TONE_DIM[tone] : "var(--bg-4)";
  const barPct = usage ? `${Math.min(100, Math.max(0, usage.utilization_percent)).toFixed(0)}%` : "0%";
  const pctStr = usage ? `${Math.round(usage.utilization_percent)}%` : "—";

  return (
    <>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
        <span style={{ width: 12, height: 12, borderRadius: 3, background: color, flex: "none" }} />
        {renaming ? (
          <>
            <input
              className="br-input"
              title="Category name"
              aria-label="Category name"
              style={{ flex: 1, minWidth: 0, fontSize: 17, fontWeight: 600 }}
              value={draftName}
              onChange={(event) => setDraftName(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  void saveName();
                }
                if (event.key === "Escape") {
                  setRenaming(false);
                  setDraftName(category.name);
                  setRenameError(null);
                }
              }}
            />
            <button type="button" style={accentButton} onClick={() => void saveName()}>
              Save
            </button>
            <button
              type="button"
              style={ghostButton}
              onClick={() => {
                setRenaming(false);
                setDraftName(category.name);
                setRenameError(null);
              }}
            >
              Cancel
            </button>
          </>
        ) : (
          <>
            <div style={{ fontSize: 19, fontWeight: 600 }}>{category.name}</div>
            <span style={{ fontSize: 11, fontWeight: 600, padding: "3px 9px", borderRadius: 99, background: badgeDim, color: badgeColor }}>
              {badgeLabel}
            </span>
            {!category.active ? (
              <span style={{ fontSize: 11, fontWeight: 600, padding: "3px 9px", borderRadius: 99, background: "var(--bg-4)", color: "var(--text-3)" }}>
                Archived
              </span>
            ) : null}
            <button
              type="button"
              title="Rename category"
              aria-label="Rename category"
              style={iconButton}
              onClick={() => {
                setDraftName(category.name);
                setRenaming(true);
              }}
            >
              <IconPencil />
            </button>
          </>
        )}
      </div>
      {renameError ? (
        <div role="alert" style={{ fontSize: 12, color: "var(--over)", marginBottom: 6 }}>
          {renameError}
        </div>
      ) : null}
      <div style={{ fontSize: 12.5, color: "var(--text-3)", marginBottom: 12 }}>
        {capitalize(category.type)} · {monthLabel} · <span className="num">{count}</span> transactions
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 18, flexWrap: "wrap" }}>
        {category.active ? (
          <button type="button" style={ghostButton} onClick={() => void runLifecycle(() => onArchiveCategory(category.category_id))}>
            Archive
          </button>
        ) : (
          <button type="button" style={ghostButton} onClick={() => void runLifecycle(() => onUnarchiveCategory(category.category_id))}>
            Unarchive
          </button>
        )}
        {confirmingDelete ? (
          <>
            <button
              type="button"
              style={{ ...ghostButton, borderColor: "var(--over)", color: "var(--over)" }}
              onClick={() => void runLifecycle(() => onDeleteCategory(category.category_id))}
            >
              Delete for good
            </button>
            <button type="button" style={ghostButton} onClick={() => setConfirmingDelete(false)}>
              Keep it
            </button>
          </>
        ) : (
          <button type="button" style={ghostButton} onClick={() => { setLifecycleError(null); setConfirmingDelete(true); }}>
            Delete
          </button>
        )}
        <span style={{ fontSize: 11.5, color: "var(--text-3)" }}>
          {confirmingDelete
            ? "This cannot be undone."
            : "Archiving keeps this category's history; deleting needs it to be unused."}
        </span>
      </div>
      {lifecycleError ? (
        <div role="alert" style={{ fontSize: 12, color: "var(--over)", lineHeight: 1.45, marginBottom: 16 }}>
          {lifecycleError}
        </div>
      ) : null}

      {hasBudget && usage ? (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 10 }}>
            <div style={statCard}>
              <div style={{ fontSize: 11, color: "var(--text-3)", fontWeight: 600 }}>Spent</div>
              <div className="num" style={{ fontSize: 21, fontWeight: 600, marginTop: 2 }}>{eurPlain(usage.spent_amount)}</div>
            </div>
            <div style={statCard}>
              <div style={{ fontSize: 11, color: "var(--text-3)", fontWeight: 600 }}>Budget</div>
              <div className="num" style={{ fontSize: 21, fontWeight: 600, marginTop: 2 }}>{eurPlain(usage.budget_amount)}</div>
            </div>
            <div style={statCard}>
              <div style={{ fontSize: 11, color: "var(--text-3)", fontWeight: 600 }}>Remaining</div>
              <div className="num" style={{ fontSize: 21, fontWeight: 600, marginTop: 2, color }}>
                {eur(usage.remaining_amount)}
              </div>
            </div>
          </div>
          <div style={{ position: "relative", height: 8, background: "var(--bg-4)", borderRadius: 5, overflow: "hidden", margin: "14px 0 6px" }}>
            <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: barPct, background: color, borderRadius: 5 }} />
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11.5, color: "var(--text-3)", marginBottom: 20 }}>
            <span className="num">{pctStr} used</span>
            <span>budget for {monthLabel}</span>
          </div>
        </>
      ) : (
        <div
          style={{
            background: "var(--bg-3)",
            border: "1px solid var(--line)",
            borderRadius: 11,
            padding: "15px 16px",
            marginBottom: 20,
            display: "flex",
            alignItems: "baseline",
            justifyContent: "space-between",
            gap: 12,
          }}
        >
          <div>
            <div style={{ fontSize: 11, color: "var(--text-3)", fontWeight: 600 }}>{capitalize(FLOW[category.type])} this month</div>
            <div className="num" style={{ fontSize: 24, fontWeight: 600, marginTop: 2 }}>{eurPlain(selected.total)}</div>
          </div>
          <div style={{ fontSize: 11.5, color: "var(--text-3)", textAlign: "right" }}>
            {!isExpense
              ? `${capitalize(category.type)} categories aren't budgeted`
              : budgetsKnown
                ? "No budget set yet"
                : "Budget status unavailable"}
          </div>
        </div>
      )}

      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 6, color: "var(--text-2)" }}>Transactions</div>
      {txns.length > 0 ? (
        <div style={{ display: "flex", flexDirection: "column" }}>
          {txns.map((transaction) => {
            const positive = Number(transaction.amount) > 0;
            return (
              <div
                key={transaction.transaction_id}
                style={{ display: "flex", alignItems: "center", gap: 10, padding: "11px 2px", borderBottom: "1px solid var(--line)" }}
              >
                <div className="num" style={{ fontSize: 12, color: "var(--text-3)", width: 46, flex: "none" }}>
                  {(transaction.booking_date || transaction.value_date || "").slice(5)}
                </div>
                <div style={{ flex: 1, minWidth: 0, fontSize: 13.5, fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {transactionTitle(transaction)}
                </div>
                <div
                  className="num"
                  style={{ fontSize: 12, color: "var(--text-3)", minWidth: 0, maxWidth: 96, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
                >
                  {shortAccount(transaction.account_display_name)}
                </div>
                <div className="num" style={{ fontSize: 13.5, fontWeight: 600, color: positive ? "var(--good)" : "var(--text)", flex: "none" }}>
                  {eur(transaction.amount)}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div style={{ padding: 26, textAlign: "center", color: "var(--text-3)", fontSize: 13, background: "var(--bg-3)", borderRadius: 11 }}>
          No transactions loaded for this category in the current view.
        </div>
      )}
    </>
  );
}
