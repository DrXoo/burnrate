import { useMemo, useState, type CSSProperties } from "react";

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
import type { Budget, Category, CategoryType, SummaryDashboard, Transaction } from "../../types";

interface CategoriesPageProps {
  categories: Category[];
  budgets: Budget[];
  summary: SummaryDashboard | null;
  ledgerItems: Transaction[];
  monthLabel: string;
  onCreateCategory: (name: string, type: CategoryType) => Promise<void>;
}

interface CategoryStat {
  category: Category;
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

const statCard: CSSProperties = {
  background: "var(--bg-3)",
  border: "1px solid var(--line)",
  borderRadius: 11,
  padding: "13px 14px",
};

function num(value: string | null | undefined): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

export function CategoriesPage({ categories, budgets, summary, ledgerItems, monthLabel, onCreateCategory }: CategoriesPageProps) {
  const [selectedId, setSelectedId] = useState<string>("");
  const [showNew, setShowNew] = useState(false);
  const [newName, setNewName] = useState("");
  const [newType, setNewType] = useState<CategoryType>("expense");

  const stats = useMemo<CategoryStat[]>(() => {
    const usageById = new Map((summary?.budget_usage ?? []).map((usage) => [usage.category_id, usage]));
    const budgetById = new Map(budgets.filter((budget) => budget.active).map((budget) => [budget.category_id, budget]));
    const ledgerCount: Record<string, number> = {};
    const ledgerTotal: Record<string, number> = {};
    for (const transaction of ledgerItems) {
      if (!transaction.category_id) {
        continue;
      }
      ledgerCount[transaction.category_id] = (ledgerCount[transaction.category_id] ?? 0) + 1;
      ledgerTotal[transaction.category_id] = (ledgerTotal[transaction.category_id] ?? 0) + Math.abs(num(transaction.amount));
    }

    return categories.map((category) => {
      const usage = usageById.get(category.category_id);
      const budgetRecord = budgetById.get(category.category_id);
      const budget = usage ? num(usage.budget_amount) : budgetRecord ? num(budgetRecord.amount) : null;
      const ledgerSpent = ledgerTotal[category.category_id] ?? 0;
      const spent = usage ? num(usage.spent_amount) : ledgerSpent;

      let tone: Tone = "neutral";
      if (category.type === "expense") {
        if (usage) {
          tone = usageTone(usage.status);
        } else if (budget && budget > 0) {
          tone = spent / budget > 1 ? "over" : spent / budget >= 0.85 ? "watch" : "good";
        } else {
          tone = "good";
        }
      }

      return {
        category,
        budget,
        spent,
        tone,
        color: categoryColor(category.type, tone),
        count: ledgerCount[category.category_id] ?? 0,
        total: ledgerTotal[category.category_id] ?? 0,
      };
    });
  }, [categories, budgets, summary, ledgerItems]);

  const selected = stats.find((stat) => stat.category.category_id === selectedId) ?? stats[0];

  async function handleAdd() {
    const name = newName.trim() || "New category";
    await onCreateCategory(name, newType);
    setShowNew(false);
    setNewName("");
    setNewType("expense");
  }

  const selectedTxns = selected ? ledgerItems.filter((transaction) => transaction.category_id === selected.category.category_id) : [];

  return (
    <div className="br-cols" style={{ display: "grid", gridTemplateColumns: "1fr 1.5fr", gap: 14 }}>
      {/* LIST */}
      <div
        style={{
          background: "var(--bg-2)",
          border: "1px solid var(--line)",
          borderRadius: 16,
          padding: 18,
          boxShadow: "var(--card-shadow)",
          alignSelf: "start",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
          <div style={{ fontSize: 15, fontWeight: 600 }}>Categories</div>
          <span style={{ fontSize: 12, color: "var(--text-3)" }}>
            <span className="num">{categories.length}</span> total
          </span>
        </div>

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
                    const barPct = stat.budget && stat.budget > 0 ? `${Math.min(100, (stat.spent / stat.budget) * 100).toFixed(0)}%` : "0%";
                    const pctStr = stat.budget && stat.budget > 0 ? `${Math.round((stat.spent / stat.budget) * 100)}%` : "—";
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
                          <span style={{ width: 9, height: 9, borderRadius: 2, background: stat.color }} />
                          <span style={{ flex: 1, fontSize: 13.5, fontWeight: 500, color: "var(--text)" }}>{stat.category.name}</span>
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
                                {eurPlain(stat.spent)} / {stat.budget != null ? eurPlain(stat.budget) : "no budget"}
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
        }}
      >
        {selected ? (
          <CategoryDetail selected={selected} monthLabel={monthLabel} count={selectedTxns.length} txns={selectedTxns} />
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
  count,
  txns,
}: {
  selected: CategoryStat;
  monthLabel: string;
  count: number;
  txns: Transaction[];
}) {
  const { category, budget, spent, tone, color } = selected;
  const isExpense = category.type === "expense";
  const hasBudget = isExpense && budget != null && budget > 0;
  const remaining = budget != null ? budget - spent : 0;
  const badgeLabel = hasBudget ? TONE_LABEL[tone] : capitalize(category.type);
  const badgeColor = hasBudget ? color : "var(--text-2)";
  const badgeDim = hasBudget ? TONE_DIM[tone] : "var(--bg-4)";
  const barPct = hasBudget ? `${Math.min(100, (spent / (budget as number)) * 100).toFixed(0)}%` : "0%";
  const pctStr = hasBudget ? `${Math.round((spent / (budget as number)) * 100)}%` : "—";

  return (
    <>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
        <span style={{ width: 12, height: 12, borderRadius: 3, background: color }} />
        <div style={{ fontSize: 19, fontWeight: 600 }}>{category.name}</div>
        <span style={{ fontSize: 11, fontWeight: 600, padding: "3px 9px", borderRadius: 99, background: badgeDim, color: badgeColor }}>
          {badgeLabel}
        </span>
      </div>
      <div style={{ fontSize: 12.5, color: "var(--text-3)", marginBottom: 18 }}>
        {capitalize(category.type)} · {monthLabel} · <span className="num">{count}</span> transactions
      </div>

      {hasBudget ? (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10 }}>
            <div style={statCard}>
              <div style={{ fontSize: 11, color: "var(--text-3)", fontWeight: 600 }}>Spent</div>
              <div className="num" style={{ fontSize: 21, fontWeight: 600, marginTop: 2 }}>{eurPlain(spent)}</div>
            </div>
            <div style={statCard}>
              <div style={{ fontSize: 11, color: "var(--text-3)", fontWeight: 600 }}>Budget</div>
              <div className="num" style={{ fontSize: 21, fontWeight: 600, marginTop: 2 }}>{eurPlain(budget as number)}</div>
            </div>
            <div style={statCard}>
              <div style={{ fontSize: 11, color: "var(--text-3)", fontWeight: 600 }}>Remaining</div>
              <div className="num" style={{ fontSize: 21, fontWeight: 600, marginTop: 2, color }}>
                {remaining >= 0 ? eurPlain(remaining) : `−${eurPlain(-remaining)}`}
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
            {isExpense ? "No budget set yet" : `${capitalize(category.type)} categories aren't budgeted`}
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
                style={{ display: "flex", alignItems: "center", gap: 12, padding: "11px 2px", borderBottom: "1px solid var(--line)" }}
              >
                <div className="num" style={{ fontSize: 12, color: "var(--text-3)", width: 54, flex: "none" }}>
                  {(transaction.booking_date || transaction.value_date || "").slice(5)}
                </div>
                <div style={{ flex: 1, minWidth: 0, fontSize: 13.5, fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {transactionTitle(transaction)}
                </div>
                <div className="num" style={{ fontSize: 12, color: "var(--text-3)" }}>{shortAccount(transaction.account_display_name)}</div>
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
