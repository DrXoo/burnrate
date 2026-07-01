import { useEffect, useState, type FormEvent } from "react";

import { CURRENCY_OPTIONS, prettyLabel } from "../lib/format";
import type { Budget, BudgetUpdateDraft } from "../types";
import { StatusTag } from "./ui/StatusTag";

interface BudgetCardProps {
  budget: Budget;
  onUpdateBudget: (budgetId: string, draft: BudgetUpdateDraft) => Promise<void>;
  onDeactivateBudget: (budgetId: string) => Promise<void>;
}

export function BudgetCard({ budget, onUpdateBudget, onDeactivateBudget }: BudgetCardProps) {
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState<"save" | "deactivate" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState<BudgetUpdateDraft>({
    amount: budget.amount,
    currency: budget.currency,
  });

  useEffect(() => {
    setDraft({ amount: budget.amount, currency: budget.currency });
    setEditing(false);
    setBusy(null);
    setError(null);
  }, [budget]);

  async function handleSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!draft.amount.trim() || !draft.currency.trim()) {
      setError("Amount and currency are required.");
      return;
    }

    try {
      setBusy("save");
      setError(null);
      await onUpdateBudget(budget.budget_id, draft);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : String(nextError));
      setBusy(null);
    }
  }

  async function handleDeactivate() {
    if (!window.confirm(`Deactivate the ${budget.category_name} budget? It will stop counting toward your dashboard metrics.`)) {
      return;
    }
    try {
      setBusy("deactivate");
      setError(null);
      await onDeactivateBudget(budget.budget_id);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : String(nextError));
      setBusy(null);
    }
  }

  return (
    <article className="list-card list-card-muted">
      <div className="row">
        <strong>{budget.category_name}</strong>
        <StatusTag tone={budget.status === "active" ? "good" : budget.status === "scheduled" ? "warn" : "default"}>
          {prettyLabel(budget.status)}
        </StatusTag>
      </div>

      <p className="meta-copy">
        {budget.amount} {budget.currency} per month
      </p>

      <div className="inline-actions">
        <button type="button" className="button button-secondary" onClick={() => setEditing((current) => !current)}>
          {editing ? "Close editor" : "Edit budget"}
        </button>
        <button
          type="button"
          className="button button-secondary"
          disabled={budget.status === "inactive" || busy === "deactivate"}
          onClick={handleDeactivate}
        >
          {busy === "deactivate" ? "Updating..." : "Deactivate"}
        </button>
      </div>

      {editing ? (
        <form className="mini-form" onSubmit={handleSave}>
          <div className="dual-grid">
            <label>
              Monthly amount
              <input
                type="number"
                min="0.01"
                step="0.01"
                value={draft.amount}
                onChange={(event) => setDraft((current) => ({ ...current, amount: event.target.value }))}
              />
            </label>
            <label>
              Currency
              <select
                value={draft.currency}
                onChange={(event) => setDraft((current) => ({ ...current, currency: event.target.value }))}
              >
                {(CURRENCY_OPTIONS.includes(draft.currency)
                  ? CURRENCY_OPTIONS
                  : [draft.currency, ...CURRENCY_OPTIONS]
                ).map((code) => (
                  <option key={code} value={code}>
                    {code}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="inline-actions">
            <button type="submit" className="button" disabled={busy === "save"}>
              {busy === "save" ? "Saving..." : "Save budget"}
            </button>
            <button type="button" className="button button-secondary" onClick={() => setEditing(false)}>
              Cancel
            </button>
          </div>
        </form>
      ) : null}

      {error ? <div className="error-banner">{error}</div> : null}
    </article>
  );
}
