import { useMemo, useState, type CSSProperties } from "react";

import { IconPencil, IconTrash } from "../icons";
import {
  categoryColor,
  eurPlain,
  prettyMatchField,
  prettyMatchOperator,
  usageTone,
} from "../../lib/format";
import type {
  Budget,
  BudgetDraft,
  BudgetUpdateDraft,
  Category,
  MatchField,
  MatchOperator,
  Rule,
  RuleUpdateDraft,
  SummaryDashboard,
} from "../../types";

interface RulesBudgetsPageProps {
  rules: Rule[];
  categories: Category[];
  budgets: Budget[];
  summary: SummaryDashboard | null;
  onToggleRule: (ruleId: string, active: boolean) => Promise<void>;
  onUpdateRule: (ruleId: string, draft: RuleUpdateDraft) => Promise<void>;
  onDeleteRule: (ruleId: string) => Promise<void>;
  onCreateBudget: (draft: BudgetDraft) => Promise<void>;
  onUpdateBudget: (budgetId: string, draft: BudgetUpdateDraft) => Promise<void>;
  onDeactivateBudget: (budgetId: string) => Promise<void>;
}

interface RuleDraftState {
  name: string;
  match_field: MatchField;
  match_operator: MatchOperator;
  match_value: string;
  category_id: string;
}

const cardStyle: CSSProperties = {
  background: "var(--bg-2)",
  border: "1px solid var(--line)",
  borderRadius: 16,
  padding: "20px 22px",
  boxShadow: "var(--card-shadow)",
};

const smallButton: CSSProperties = {
  border: "1px solid var(--line-2)",
  background: "var(--bg-3)",
  color: "var(--text)",
  borderRadius: 8,
  padding: "5px 11px",
  font: "500 12px 'Hanken Grotesque', sans-serif",
  cursor: "pointer",
};

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
  cursor: "pointer",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
};

const FIELD_OPTIONS: Array<{ value: MatchField; label: string }> = [
  { value: "merchant_name", label: "Merchant" },
  { value: "description", label: "Description" },
  { value: "counterparty_name", label: "Counterparty" },
];

const OPERATOR_OPTIONS: Array<{ value: MatchOperator; label: string }> = [
  { value: "contains", label: "contains" },
  { value: "starts_with", label: "starts with" },
  { value: "ends_with", label: "ends with" },
  { value: "equals", label: "equals" },
];

function num(value: string | null | undefined): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

export function RulesBudgetsPage({
  rules,
  categories,
  budgets,
  summary,
  onToggleRule,
  onUpdateRule,
  onDeleteRule,
  onCreateBudget,
  onUpdateBudget,
  onDeactivateBudget,
}: RulesBudgetsPageProps) {
  const categoryById = useMemo(() => new Map(categories.map((category) => [category.category_id, category])), [categories]);
  const toneById = useMemo(
    () => new Map((summary?.budget_usage ?? []).map((usage) => [usage.category_id, usageTone(usage.status)])),
    [summary],
  );

  const [editRuleId, setEditRuleId] = useState<string | null>(null);
  const [ruleDraft, setRuleDraft] = useState<RuleDraftState | null>(null);

  const expenseCategories = categories.filter((category) => category.type === "expense");
  const activeBudgets = budgets.filter((budget) => budget.active);
  const budgetedIds = new Set(activeBudgets.map((budget) => budget.category_id));

  const [showNewBudget, setShowNewBudget] = useState(false);
  const [newBudgetCat, setNewBudgetCat] = useState("");
  const [newBudgetAmount, setNewBudgetAmount] = useState("");
  const [editBudgetId, setEditBudgetId] = useState<string | null>(null);
  const [editBudgetAmount, setEditBudgetAmount] = useState("");

  function startEditRule(rule: Rule) {
    setEditRuleId(rule.rule_id);
    setRuleDraft({
      name: rule.name ?? "",
      match_field: rule.match_field,
      match_operator: rule.match_operator,
      match_value: rule.match_value,
      category_id: rule.category_id,
    });
  }

  async function saveRule() {
    if (!editRuleId || !ruleDraft) {
      return;
    }
    await onUpdateRule(editRuleId, {
      name: ruleDraft.name,
      match_field: ruleDraft.match_field,
      match_operator: ruleDraft.match_operator,
      match_value: ruleDraft.match_value,
      apply_to_existing_uncategorized: true,
    });
    setEditRuleId(null);
    setRuleDraft(null);
  }

  async function addBudget() {
    const categoryId = newBudgetCat || expenseCategories.find((category) => !budgetedIds.has(category.category_id))?.category_id;
    if (!categoryId || !newBudgetAmount.trim()) {
      return;
    }
    await onCreateBudget({ category_id: categoryId, amount: newBudgetAmount.trim(), currency: "EUR" });
    setShowNewBudget(false);
    setNewBudgetCat("");
    setNewBudgetAmount("");
  }

  async function saveBudget(budget: Budget) {
    if (!editBudgetAmount.trim()) {
      return;
    }
    await onUpdateBudget(budget.budget_id, { amount: editBudgetAmount.trim(), currency: budget.currency });
    setEditBudgetId(null);
    setEditBudgetAmount("");
  }

  const unbudgetedExpense = expenseCategories.filter((category) => !budgetedIds.has(category.category_id));

  return (
    <div className="br-cols" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
      {/* RULES */}
      <div style={cardStyle}>
        <div style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 15, fontWeight: 600 }}>Rules</div>
          <span style={{ fontSize: 12, color: "var(--text-3)" }}>
            Auto-categorize on sync · create new ones from a transaction in Review
          </span>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {rules.length === 0 ? (
            <div style={{ padding: 22, textAlign: "center", color: "var(--text-3)", fontSize: 13, background: "var(--bg-3)", borderRadius: 11 }}>
              No rules yet. Assign a category in Review, then use “Create rule”.
            </div>
          ) : null}

          {rules.map((rule) => {
            const category = categoryById.get(rule.category_id);
            const color = category ? categoryColor(category.type, toneById.get(rule.category_id) ?? "good") : "var(--text-2)";
            if (editRuleId === rule.rule_id && ruleDraft) {
              return (
                <div key={rule.rule_id} style={{ background: "var(--bg-3)", border: "1px solid var(--accent)", borderRadius: 11, padding: "13px 14px" }}>
                  <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--text-3)", fontWeight: 700, marginBottom: 9 }}>
                    Edit rule
                  </div>
                  <input
                    className="br-input"
                    style={{ width: "100%", background: "var(--bg-2)" }}
                    value={ruleDraft.name}
                    onChange={(event) => setRuleDraft({ ...ruleDraft, name: event.target.value })}
                    placeholder="Rule name"
                  />
                  <div style={{ display: "flex", gap: 6, marginTop: 8 }}>
                    <select
                      className="br-sel"
                      style={{ flex: 1 }}
                      value={ruleDraft.match_field}
                      onChange={(event) => setRuleDraft({ ...ruleDraft, match_field: event.target.value as MatchField })}
                    >
                      {FIELD_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                    <select
                      className="br-sel"
                      style={{ flex: 1 }}
                      value={ruleDraft.match_operator}
                      onChange={(event) => setRuleDraft({ ...ruleDraft, match_operator: event.target.value as MatchOperator })}
                    >
                      {OPERATOR_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </div>
                  <input
                    className="br-input"
                    style={{ width: "100%", background: "var(--bg-2)", marginTop: 8 }}
                    value={ruleDraft.match_value}
                    onChange={(event) => setRuleDraft({ ...ruleDraft, match_value: event.target.value })}
                    placeholder="Match value (e.g. Rewe)"
                  />
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 8 }}>
                    <span style={{ fontSize: 13, color: "var(--text-3)" }}>→ assign to</span>
                    <select
                      className="br-sel"
                      style={{ flex: 1 }}
                      value={ruleDraft.category_id}
                      onChange={(event) => setRuleDraft({ ...ruleDraft, category_id: event.target.value })}
                    >
                      {categories.map((option) => (
                        <option key={option.category_id} value={option.category_id}>
                          {option.name}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div style={{ display: "flex", gap: 8, marginTop: 12, justifyContent: "space-between", alignItems: "center" }}>
                    <button
                      type="button"
                      onClick={() => void onDeleteRule(rule.rule_id)}
                      style={{ border: "1px solid var(--over)", background: "transparent", color: "var(--over)", borderRadius: 8, padding: "7px 12px", font: "500 12px 'Hanken Grotesque', sans-serif", cursor: "pointer" }}
                    >
                      Delete
                    </button>
                    <div style={{ display: "flex", gap: 8 }}>
                      <button type="button" style={ghostButton} onClick={() => { setEditRuleId(null); setRuleDraft(null); }}>
                        Cancel
                      </button>
                      <button type="button" style={accentButton} onClick={() => void saveRule()}>
                        Save rule
                      </button>
                    </div>
                  </div>
                </div>
              );
            }
            return (
              <div key={rule.rule_id} style={{ display: "flex", alignItems: "center", gap: 10, padding: "12px 14px", background: "var(--bg-3)", border: "1px solid var(--line)", borderRadius: 11 }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 600 }}>{rule.name || "Untitled rule"}</div>
                  <div style={{ fontSize: 12, color: "var(--text-3)", marginTop: 2 }}>
                    {prettyMatchField(rule.match_field)} {prettyMatchOperator(rule.match_operator).toLowerCase()} "
                    <span style={{ color: "var(--text-2)" }}>{rule.match_value}</span>" →{" "}
                    <span style={{ color, fontWeight: 600 }}>{rule.category_name}</span>
                  </div>
                </div>
                <div
                  role="switch"
                  aria-checked={rule.active}
                  onClick={() => void onToggleRule(rule.rule_id, !rule.active)}
                  style={{ flex: "none", width: 36, height: 20, borderRadius: 11, background: rule.active ? "var(--good)" : "var(--bg-4)", position: "relative", cursor: "pointer", transition: "background .15s" }}
                >
                  <div style={{ position: "absolute", top: 2, left: rule.active ? 18 : 2, width: 16, height: 16, borderRadius: "50%", background: "#fff", transition: "left .15s" }} />
                </div>
                <button type="button" title="Edit" style={{ ...iconButton, color: "var(--text-2)" }} onClick={() => startEditRule(rule)}>
                  <IconPencil />
                </button>
                <button type="button" title="Delete" style={{ ...iconButton, color: "var(--text-3)" }} onClick={() => void onDeleteRule(rule.rule_id)}>
                  <IconTrash />
                </button>
              </div>
            );
          })}
        </div>
      </div>

      {/* BUDGETS */}
      <div style={cardStyle}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
          <div style={{ fontSize: 15, fontWeight: 600 }}>Monthly budgets</div>
          <button type="button" style={smallButton} onClick={() => setShowNewBudget((value) => !value)} disabled={unbudgetedExpense.length === 0}>
            + New
          </button>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {showNewBudget && unbudgetedExpense.length > 0 ? (
            <div style={{ background: "var(--bg-3)", border: "1px solid var(--accent)", borderRadius: 11, padding: "13px 14px", display: "flex", flexDirection: "column", gap: 8 }}>
              <select className="br-sel" value={newBudgetCat} onChange={(event) => setNewBudgetCat(event.target.value)}>
                <option value="">Choose category…</option>
                {unbudgetedExpense.map((category) => (
                  <option key={category.category_id} value={category.category_id}>
                    {category.name}
                  </option>
                ))}
              </select>
              <div style={{ display: "flex", gap: 8 }}>
                <input
                  className="br-input"
                  style={{ flex: 1, background: "var(--bg-2)" }}
                  value={newBudgetAmount}
                  onChange={(event) => setNewBudgetAmount(event.target.value)}
                  placeholder="Amount (€/mo)"
                  inputMode="decimal"
                />
                <button type="button" style={accentButton} onClick={() => void addBudget()}>
                  Add
                </button>
              </div>
            </div>
          ) : null}

          {activeBudgets.length === 0 && !showNewBudget ? (
            <div style={{ padding: 22, textAlign: "center", color: "var(--text-3)", fontSize: 13, background: "var(--bg-3)", borderRadius: 11 }}>
              No budgets yet. Add one to start tracking spend against a plan.
            </div>
          ) : null}

          {activeBudgets.map((budget) => {
            const color = categoryColor(budget.category_type, toneById.get(budget.category_id) ?? "good");
            if (editBudgetId === budget.budget_id) {
              return (
                <div key={budget.budget_id} style={{ display: "flex", alignItems: "center", gap: 10, padding: "11px 14px", background: "var(--bg-3)", border: "1px solid var(--accent)", borderRadius: 11 }}>
                  <span style={{ width: 9, height: 9, borderRadius: 2, background: color, flex: "none" }} />
                  <span style={{ flex: 1, fontSize: 13.5, fontWeight: 500 }}>{budget.category_name}</span>
                  <input
                    className="br-input"
                    style={{ width: 96, background: "var(--bg-2)" }}
                    value={editBudgetAmount}
                    onChange={(event) => setEditBudgetAmount(event.target.value)}
                    inputMode="decimal"
                  />
                  <button type="button" style={accentButton} onClick={() => void saveBudget(budget)}>
                    Save
                  </button>
                  <button type="button" style={ghostButton} onClick={() => setEditBudgetId(null)}>
                    Cancel
                  </button>
                </div>
              );
            }
            return (
              <div key={budget.budget_id} style={{ display: "flex", alignItems: "center", gap: 12, padding: "11px 14px", background: "var(--bg-3)", border: "1px solid var(--line)", borderRadius: 11 }}>
                <span style={{ width: 9, height: 9, borderRadius: 2, background: color, flex: "none" }} />
                <span style={{ flex: 1, fontSize: 13.5, fontWeight: 500 }}>{budget.category_name}</span>
                <span className="num" style={{ fontSize: 13.5, fontWeight: 600 }}>
                  {eurPlain(num(budget.amount))}
                  <span style={{ color: "var(--text-3)", fontWeight: 400, fontSize: 12 }}>/mo</span>
                </span>
                <button
                  type="button"
                  title="Edit budget"
                  style={{ ...iconButton, color: "var(--text-2)" }}
                  onClick={() => { setEditBudgetId(budget.budget_id); setEditBudgetAmount(String(num(budget.amount))); }}
                >
                  <IconPencil />
                </button>
                <button type="button" title="Remove budget" style={{ ...iconButton, color: "var(--text-3)" }} onClick={() => void onDeactivateBudget(budget.budget_id)}>
                  <IconTrash />
                </button>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
