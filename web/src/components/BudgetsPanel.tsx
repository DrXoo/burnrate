import { useState, type FormEvent } from "react";

import type { Budget, BudgetDraft, BudgetUpdateDraft, Category } from "../types";
import { Card } from "./ui/Card";
import { BudgetCard } from "./BudgetCard";

interface BudgetsPanelProps {
  budgets: Budget[];
  categories: Category[];
  onCreateBudget: (draft: BudgetDraft) => Promise<void>;
  onUpdateBudget: (budgetId: string, draft: BudgetUpdateDraft) => Promise<void>;
  onDeactivateBudget: (budgetId: string) => Promise<void>;
}

export function BudgetsPanel({
  budgets,
  categories,
  onCreateBudget,
  onUpdateBudget,
  onDeactivateBudget,
}: BudgetsPanelProps) {
  const expenseCategories = categories.filter((category) => category.type === "expense" && category.active);
  const [draft, setDraft] = useState<BudgetDraft>({
    category_id: "",
    amount: "",
    currency: "EUR",
  });
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!draft.category_id || !draft.amount.trim()) {
      setError("Category and amount are required.");
      setFeedback(null);
      return;
    }

    try {
      setBusy(true);
      setError(null);
      setFeedback(null);
      await onCreateBudget(draft);
      setDraft({ category_id: "", amount: "", currency: "EUR" });
      setFeedback("Budget created.");
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : String(nextError));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title="Budgets" subtitle="Monthly spending targets per expense category.">
      <div className="stack">
        {budgets.length === 0 ? (
          <div className="empty-state">No budgets yet. Create a monthly target for an expense category.</div>
        ) : (
          budgets.map((budget) => (
            <BudgetCard
              key={budget.budget_id}
              budget={budget}
              onUpdateBudget={onUpdateBudget}
              onDeactivateBudget={onDeactivateBudget}
            />
          ))
        )}
      </div>

      <form className="form-stack" onSubmit={handleSubmit}>
        <label>
          Category
          <select
            value={draft.category_id}
            onChange={(event) => setDraft((current) => ({ ...current, category_id: event.target.value }))}
          >
            <option value="">Choose an expense category</option>
            {expenseCategories.map((category) => (
              <option key={category.category_id} value={category.category_id}>
                {category.name}
              </option>
            ))}
          </select>
        </label>
        <div className="dual-grid">
          <label>
            Monthly amount
            <input
              type="number"
              min="0.01"
              step="0.01"
              placeholder="300.00"
              value={draft.amount}
              onChange={(event) => setDraft((current) => ({ ...current, amount: event.target.value }))}
            />
          </label>
          <label>
            Currency
            <input
              maxLength={3}
              value={draft.currency}
              onChange={(event) => setDraft((current) => ({ ...current, currency: event.target.value }))}
            />
          </label>
        </div>
        <button type="submit" className="button" disabled={busy}>
          {busy ? "Creating..." : "Create budget"}
        </button>
      </form>

      {feedback ? <div className="success-banner">{feedback}</div> : null}
      {error ? <div className="error-banner">{error}</div> : null}
    </Card>
  );
}
