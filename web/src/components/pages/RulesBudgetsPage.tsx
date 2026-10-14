import { useMemo, useState, type CSSProperties } from "react";

import { IconPencil, IconRestore, IconTrash } from "../icons";
import {
  categoryColor,
  dayAndMonth,
  finalMonthFor,
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
  /** Every category, archived ones included. Only the per-rule colour is read off
      this: a rule's own label comes from its payload. Archived ones belong here so a
      rule left over on one still draws in its type's colour rather than grey. */
  categories: Category[];
  /** The categories new spend may be filed against: archived ones are excluded.
      Every picker on this page reads this one, never `categories`. */
  assignableCategories: Category[];
  // Null is a month whose budget list has not arrived, which is a different claim
  // from a month with no budgets. The page has to tell them apart.
  budgets: Budget[] | null;
  summary: SummaryDashboard | null;
  onToggleRule: (ruleId: string, active: boolean) => Promise<void>;
  onUpdateRule: (ruleId: string, draft: RuleUpdateDraft) => Promise<void>;
  onDeleteRule: (ruleId: string) => Promise<void>;
  onCreateBudget: (draft: BudgetDraft) => Promise<void>;
  onUpdateBudget: (budgetId: string, draft: BudgetUpdateDraft) => Promise<void>;
  onDeactivateBudget: (budgetId: string) => Promise<void>;
  onReactivateBudget: (budgetId: string) => Promise<void>;
  /** Renames the budget's category, which is where its label lives. Takes the id,
      because the name being replaced is not a stable handle on the row. */
  onRenameCategory: (categoryId: string, name: string) => Promise<void>;
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
  assignableCategories,
  budgets,
  summary,
  onToggleRule,
  onUpdateRule,
  onDeleteRule,
  onCreateBudget,
  onUpdateBudget,
  onDeactivateBudget,
  onReactivateBudget,
  onRenameCategory,
}: RulesBudgetsPageProps) {
  const categoryById = useMemo(() => new Map(categories.map((category) => [category.category_id, category])), [categories]);
  const toneById = useMemo(
    () => new Map((summary?.budget_usage ?? []).map((usage) => [usage.category_id, usageTone(usage.status)])),
    [summary],
  );

  const [editRuleId, setEditRuleId] = useState<string | null>(null);
  const [ruleDraft, setRuleDraft] = useState<RuleDraftState | null>(null);

  const expenseCategories = assignableCategories.filter((category) => category.type === "expense");
  // `active` is read against the month on screen, so these are the budgets that
  // month holds -- including one the owner has since cancelled, which still counts
  // towards the month's figures and so has to appear beside them.
  const activeBudgets = (budgets ?? []).filter((budget) => budget.active);
  const budgetedIds = new Set(
    [...activeBudgets, ...(budgets ?? []).filter((budget) => budget.status === "scheduled")].map(
      (budget) => budget.category_id,
    ),
  );
  // Budgets the owner stopped. They belong to the months they covered and not to this
  // one, so they sit apart from the month's list -- but they stay reachable, because
  // cancelling is one click and the way back has to be one too.
  // Rows the owner can put back. `can_reactivate` is the backend's answer, from the
  // same function the endpoint refuses with -- a row closed by a later budget reads
  // identically to a cancelled one here, so deciding it on this side offered a
  // restore that was refused every time.
  const restorableBudgets = (budgets ?? []).filter((budget) => budget.can_reactivate);
  // Budgets that start after the month on screen. They cover no month yet, so they
  // belong to neither list above -- but they are real, and their categories must not
  // be offered a second budget that would overlap them.
  const scheduledBudgets = (budgets ?? []).filter((budget) => budget.status === "scheduled");

  const [showNewBudget, setShowNewBudget] = useState(false);
  const [newBudgetCat, setNewBudgetCat] = useState("");
  const [newBudgetAmount, setNewBudgetAmount] = useState("");
  const [newBudgetFixed, setNewBudgetFixed] = useState(false);
  const [editBudgetId, setEditBudgetId] = useState<string | null>(null);
  const [editBudgetAmount, setEditBudgetAmount] = useState("");
  const [editBudgetFixed, setEditBudgetFixed] = useState(false);
  const [editBudgetName, setEditBudgetName] = useState("");
  // Why the last cancel, restore or create did not go through. Each was fired with
  // `void`, so a refusal the backend had written for the owner -- naming the budget in
  // the way -- was dropped as an unhandled rejection and the click read as a no-op.
  const [budgetActionError, setBudgetActionError] = useState<string | null>(null);
  // Why the last Save did not go through, shown in the editor. A rename can fail for
  // a reason the owner can fix -- the name is taken -- so it has to be said next to
  // the field rather than swallowed.
  const [editBudgetError, setEditBudgetError] = useState<string | null>(null);

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

  async function runBudgetAction(act: () => Promise<void>) {
    setBudgetActionError(null);
    try {
      await act();
    } catch (error) {
      setBudgetActionError(error instanceof Error ? error.message : String(error));
    }
  }

  async function addBudget() {
    const categoryId = newBudgetCat || expenseCategories.find((category) => !budgetedIds.has(category.category_id))?.category_id;
    if (!categoryId || !newBudgetAmount.trim()) {
      return;
    }
    await onCreateBudget({ category_id: categoryId, amount: newBudgetAmount.trim(), currency: "EUR", is_fixed: newBudgetFixed });
    setShowNewBudget(false);
    setNewBudgetCat("");
    setNewBudgetAmount("");
    setNewBudgetFixed(false);
  }

  function startEditBudget(budget: Budget) {
    setEditBudgetId(budget.budget_id);
    setEditBudgetAmount(String(num(budget.amount)));
    setEditBudgetFixed(budget.is_fixed);
    setEditBudgetName(budget.category_name);
    setEditBudgetError(null);
  }

  function closeEditBudget() {
    setEditBudgetId(null);
    setEditBudgetAmount("");
    setEditBudgetName("");
    setEditBudgetError(null);
  }

  async function saveBudget(budget: Budget) {
    const name = editBudgetName.trim();
    if (!editBudgetAmount.trim() || !name) {
      return;
    }
    setEditBudgetError(null);
    // Both halves can be refused, and either refusal has to stay on screen: dropped,
    // the editor closes on a Save that did not happen.
    //
    // The rename goes first because it is the half that is refused for a reason the
    // owner can act on, and a refused rename then leaves the amount as it was rather
    // than half-applying the edit. The reverse order cannot be protected the same way
    // -- a rename already through cannot be taken back -- so the error says which
    // half failed and the editor stays open on it.
    try {
      if (name !== budget.category_name) {
        await onRenameCategory(budget.category_id, name);
      }
      await onUpdateBudget(budget.budget_id, { amount: editBudgetAmount.trim(), currency: budget.currency, is_fixed: editBudgetFixed });
    } catch (error) {
      setEditBudgetError(error instanceof Error ? error.message : String(error));
      return;
    }
    closeEditBudget();
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
                      {assignableCategories.map((option) => (
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

        {budgetActionError ? (
          <div role="alert" style={{ fontSize: 12, color: "var(--over)", lineHeight: 1.45, marginBottom: 12 }}>
            {budgetActionError}
          </div>
        ) : null}

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
                <button type="button" style={accentButton} onClick={() => void runBudgetAction(addBudget)}>
                  Add
                </button>
              </div>
              <label style={{ display: "flex", gap: 9, alignItems: "flex-start", cursor: "pointer" }}>
                <input
                  type="checkbox"
                  checked={newBudgetFixed}
                  onChange={(event) => setNewBudgetFixed(event.target.checked)}
                  style={{ marginTop: 2, accentColor: "var(--accent)", cursor: "pointer" }}
                />
                <span style={{ fontSize: 12, color: "var(--text-2)", lineHeight: 1.45 }}>
                  <span style={{ fontWeight: 600, color: "var(--text)" }}>Fixed payment</span> — a single charge like rent
                  or utilities. Tracked against its budget, but not spread across the month or paced day-by-day.
                </span>
              </label>
            </div>
          ) : null}

          {budgets === null ? (
            <div style={{ padding: 22, textAlign: "center", color: "var(--text-3)", fontSize: 13, background: "var(--bg-3)", borderRadius: 11 }}>
              Budgets unavailable for this month.
            </div>
          ) : null}

          {budgets !== null && activeBudgets.length === 0 && !showNewBudget ? (
            <div style={{ padding: 22, textAlign: "center", color: "var(--text-3)", fontSize: 13, background: "var(--bg-3)", borderRadius: 11 }}>
              No budgets yet. Add one to start tracking spend against a plan.
            </div>
          ) : null}

          {activeBudgets.map((budget) => {
            const color = categoryColor(budget.category_type, toneById.get(budget.category_id) ?? "good");
            if (editBudgetId === budget.budget_id) {
              return (
                <div key={budget.budget_id} style={{ display: "flex", flexDirection: "column", gap: 10, padding: "11px 14px", background: "var(--bg-3)", border: "1px solid var(--accent)", borderRadius: 11 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <span style={{ width: 9, height: 9, borderRadius: 2, background: color, flex: "none" }} />
                    <input
                      className="br-input"
                      title="Budget name"
                      aria-label="Budget name"
                      style={{ flex: 1, minWidth: 0, background: "var(--bg-2)", fontSize: 13.5, fontWeight: 500 }}
                      value={editBudgetName}
                      onChange={(event) => setEditBudgetName(event.target.value)}
                    />
                    <input
                      className="br-input"
                      title="Budget amount"
                      aria-label="Budget amount"
                      style={{ width: 96, background: "var(--bg-2)" }}
                      value={editBudgetAmount}
                      onChange={(event) => setEditBudgetAmount(event.target.value)}
                      inputMode="decimal"
                    />
                    <button type="button" style={accentButton} onClick={() => void saveBudget(budget)}>
                      Save
                    </button>
                    <button type="button" style={ghostButton} onClick={closeEditBudget}>
                      Cancel
                    </button>
                  </div>
                  <label style={{ display: "flex", gap: 9, alignItems: "flex-start", cursor: "pointer" }}>
                    <input
                      type="checkbox"
                      checked={editBudgetFixed}
                      onChange={(event) => setEditBudgetFixed(event.target.checked)}
                      style={{ marginTop: 2, accentColor: "var(--accent)", cursor: "pointer" }}
                    />
                    <span style={{ fontSize: 12, color: "var(--text-2)", lineHeight: 1.45 }}>
                      <span style={{ fontWeight: 600, color: "var(--text)" }}>Fixed payment</span> — a single charge like
                      rent or utilities. Not paced day-by-day.
                    </span>
                  </label>
                  {editBudgetError ? (
                    <div role="alert" style={{ fontSize: 12, color: "var(--over)", lineHeight: 1.45 }}>
                      {editBudgetError}
                    </div>
                  ) : null}
                </div>
              );
            }
            const finalMonth = finalMonthFor(budget.active_to, summary?.month);
            return (
              <div key={budget.budget_id} style={{ display: "flex", alignItems: "center", gap: 12, padding: "11px 14px", background: "var(--bg-3)", border: "1px solid var(--line)", borderRadius: 11 }}>
                <span style={{ width: 9, height: 9, borderRadius: 2, background: color, flex: "none" }} />
                <span style={{ flex: 1, fontSize: 13.5, fontWeight: 500, display: "flex", alignItems: "center", gap: 8, minWidth: 0 }}>
                  <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{budget.category_name}</span>
                  {budget.is_fixed ? (
                    <span
                      title="Fixed payment — not paced day-by-day"
                      style={{ flex: "none", fontSize: 10.5, fontWeight: 600, letterSpacing: "0.04em", textTransform: "uppercase", color: "var(--text-2)", background: "var(--bg-4)", border: "1px solid var(--line-2)", borderRadius: 6, padding: "1px 6px" }}
                    >
                      Fixed
                    </span>
                  ) : null}
                  {finalMonth ? (
                    <span
                      title="The last month this budget covered. The month counts it in full; the months after it hold no budget for this category."
                      style={{ flex: "none", fontSize: 10.5, fontWeight: 600, letterSpacing: "0.04em", textTransform: "uppercase", color: "var(--text-3)", background: "var(--bg-4)", border: "1px solid var(--line-2)", borderRadius: 6, padding: "1px 6px" }}
                    >
                      {finalMonth}
                    </span>
                  ) : null}
                </span>
                <span className="num" style={{ fontSize: 13.5, fontWeight: 600 }}>
                  {eurPlain(num(budget.amount))}
                  <span style={{ color: "var(--text-3)", fontWeight: 400, fontSize: 12 }}>/mo</span>
                </span>
                <button
                  type="button"
                  title="Edit budget"
                  style={{ ...iconButton, color: "var(--text-2)" }}
                  onClick={() => startEditBudget(budget)}
                >
                  <IconPencil />
                </button>
                <button type="button" title="Cancel this budget from this month on. Earlier months keep it, and this can be undone." style={{ ...iconButton, color: "var(--text-3)" }} onClick={() => void runBudgetAction(() => onDeactivateBudget(budget.budget_id))}>
                  <IconTrash />
                </button>
              </div>
            );
          })}
        </div>

        {scheduledBudgets.length > 0 ? (
          <div style={{ marginTop: 18 }}>
            <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase", color: "var(--text-3)", marginBottom: 9 }}>
              Starting later
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {scheduledBudgets.map((budget) => (
                <div
                  key={budget.budget_id}
                  style={{ display: "flex", alignItems: "center", gap: 12, padding: "9px 14px", background: "var(--bg-3)", border: "1px dashed var(--line-2)", borderRadius: 11, color: "var(--text-2)" }}
                >
                  <span style={{ width: 9, height: 9, borderRadius: 2, border: "1.5px solid var(--text-3)", flex: "none" }} />
                  <span style={{ flex: 1, fontSize: 13, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {budget.category_name}
                  </span>
                  <span className="num" style={{ fontSize: 12.5 }}>
                    {eurPlain(num(budget.amount))}
                    <span style={{ color: "var(--text-3)", fontSize: 11.5 }}>/mo</span>
                  </span>
                  <span
                    title="This budget starts in a later month. The month on screen holds no budget for this category, so its figures do not count it."
                    style={{ flex: "none", fontSize: 11.5, color: "var(--text-3)" }}
                  >
                    from {dayAndMonth(budget.active_from)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        ) : null}

        {restorableBudgets.length > 0 ? (
          <div style={{ marginTop: 18 }}>
            <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase", color: "var(--text-3)", marginBottom: 9 }}>
              Cancelled
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {restorableBudgets.map((budget) => (
                <div
                  key={budget.budget_id}
                  style={{ display: "flex", alignItems: "center", gap: 12, padding: "9px 14px", background: "var(--bg-3)", border: "1px dashed var(--line-2)", borderRadius: 11, color: "var(--text-2)" }}
                >
                  <span style={{ width: 9, height: 9, borderRadius: 2, border: "1.5px solid var(--text-3)", flex: "none" }} />
                  <span style={{ flex: 1, fontSize: 13, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {budget.category_name}
                  </span>
                  <span className="num" style={{ fontSize: 12.5 }}>
                    {eurPlain(num(budget.amount))}
                    <span style={{ color: "var(--text-3)", fontSize: 11.5 }}>/mo</span>
                  </span>
                  {budget.active_to ? (
                    <span style={{ flex: "none", fontSize: 11.5, color: "var(--text-3)" }}>
                      until {dayAndMonth(budget.active_to)}
                    </span>
                  ) : null}
                  <button
                    type="button"
                    title="Reactivate this budget"
                    style={{ ...iconButton, color: "var(--text-2)" }}
                    onClick={() => void runBudgetAction(() => onReactivateBudget(budget.budget_id))}
                  >
                    <IconRestore />
                  </button>
                </div>
              ))}
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
