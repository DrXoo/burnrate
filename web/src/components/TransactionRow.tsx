import { useEffect, useState, type FormEvent } from "react";

import { amountTone, suggestRuleField, suggestRuleValue, transactionMeta, transactionTitle } from "../lib/format";
import type {
  Category,
  MatchField,
  MatchOperator,
  RuleDraft,
  Transaction,
} from "../types";
import { StatusTag } from "./ui/StatusTag";

interface TransactionRowProps {
  transaction: Transaction;
  categories: Category[];
  onAssignCategory: (transactionId: string, categoryId: string) => Promise<void>;
  onClearCategory: (transactionId: string) => Promise<void>;
  onCreateRule: (transactionId: string, draft: RuleDraft) => Promise<void>;
}

export function TransactionRow({
  transaction,
  categories,
  onAssignCategory,
  onClearCategory,
  onCreateRule,
}: TransactionRowProps) {
  const [categoryId, setCategoryId] = useState(transaction.category_id ?? "");
  const [busy, setBusy] = useState<"assign" | "clear" | "rule" | null>(null);
  const [showRuleForm, setShowRuleForm] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ruleDraft, setRuleDraft] = useState<RuleDraft>({
    name: "",
    category_id: transaction.category_id ?? "",
    match_field: suggestRuleField(transaction),
    match_operator: "contains",
    match_value: suggestRuleValue(transaction, suggestRuleField(transaction)),
    apply_to_existing_uncategorized: true,
  });

  useEffect(() => {
    const nextField = suggestRuleField(transaction);
    setCategoryId(transaction.category_id ?? "");
    setShowRuleForm(false);
    setBusy(null);
    setError(null);
    setRuleDraft({
      name: "",
      category_id: transaction.category_id ?? "",
      match_field: nextField,
      match_operator: "contains",
      match_value: suggestRuleValue(transaction, nextField),
      apply_to_existing_uncategorized: true,
    });
  }, [transaction]);

  async function handleAssign() {
    if (!categoryId) {
      return;
    }
    try {
      setBusy("assign");
      setError(null);
      await onAssignCategory(transaction.transaction_id, categoryId);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : String(nextError));
      setBusy(null);
    }
  }

  async function handleClear() {
    try {
      setBusy("clear");
      setError(null);
      await onClearCategory(transaction.transaction_id);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : String(nextError));
      setBusy(null);
    }
  }

  async function handleCreateRule(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!ruleDraft.category_id || !ruleDraft.match_value.trim()) {
      setError("Category and match value are required.");
      return;
    }

    try {
      setBusy("rule");
      setError(null);
      await onCreateRule(transaction.transaction_id, {
        ...ruleDraft,
        name: ruleDraft.name.trim(),
        match_value: ruleDraft.match_value.trim(),
      });
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : String(nextError));
      setBusy(null);
    }
  }

  return (
    <>
      <tr>
        <td>{transaction.booking_date || "No booking date"}</td>
        <td>
          <strong>{transactionTitle(transaction)}</strong>
          <br />
          <span className="muted">{transactionMeta(transaction)}</span>
        </td>
        <td>{transaction.account_display_name}</td>
        <td>
          <StatusTag>{transaction.status}</StatusTag>
        </td>
        <td>
          <div className="transaction-cell">
            <span className={`tag ${transaction.category_id ? "tag-good" : "tag-warn"}`}>
              {transaction.category_name || (transaction.category_id ? "Assigned" : "Unknown")}
            </span>
            {transaction.matched_rule_name || transaction.matched_rule_id ? (
              <span className="hint-copy">Rule: {transaction.matched_rule_name || "Rule attached"}</span>
            ) : null}
            <div className="inline-editor">
              <select value={categoryId} onChange={(event) => setCategoryId(event.target.value)} disabled={busy !== null}>
                <option value="">Choose a category</option>
                {categories.map((category) => (
                  <option key={category.category_id} value={category.category_id}>
                    {category.name} ({category.type})
                  </option>
                ))}
              </select>
              <button type="button" className="button" disabled={!categoryId || busy !== null} onClick={handleAssign}>
                {busy === "assign" ? "Saving..." : transaction.category_id ? "Update" : "Assign"}
              </button>
              <button
                type="button"
                className="button button-secondary"
                disabled={!transaction.category_id || busy !== null}
                onClick={() => {
                  setShowRuleForm((current) => !current);
                  setRuleDraft((current) => ({ ...current, category_id: categoryId || transaction.category_id || "" }));
                }}
              >
                Save rule
              </button>
              <button
                type="button"
                className="button button-secondary"
                disabled={!transaction.category_id || busy !== null}
                onClick={handleClear}
              >
                {busy === "clear" ? "Clearing..." : "Clear"}
              </button>
            </div>
          </div>
        </td>
        <td className={`amount amount-${amountTone(transaction.amount, transaction.direction)}`}>
          {transaction.amount} {transaction.currency}
        </td>
      </tr>
      {showRuleForm ? (
        <tr>
          <td colSpan={6}>
            <form className="transaction-rule-box" onSubmit={handleCreateRule}>
              <div className="dual-grid dual-grid-wide">
                <label>
                  Rule name
                  <input
                    value={ruleDraft.name}
                    onChange={(event) => setRuleDraft((current) => ({ ...current, name: event.target.value }))}
                    placeholder="Optional custom name"
                  />
                </label>
                <label>
                  Category
                  <select
                    value={ruleDraft.category_id}
                    onChange={(event) =>
                      setRuleDraft((current) => ({ ...current, category_id: event.target.value }))
                    }
                  >
                    <option value="">Choose a category</option>
                    {categories.map((category) => (
                      <option key={category.category_id} value={category.category_id}>
                        {category.name} ({category.type})
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Match field
                  <select
                    value={ruleDraft.match_field}
                    onChange={(event) =>
                      setRuleDraft((current) => ({ ...current, match_field: event.target.value as MatchField }))
                    }
                  >
                    <option value="description">Description</option>
                    <option value="merchant_name">Merchant name</option>
                    <option value="counterparty_name">Counterparty name</option>
                  </select>
                </label>
                <label>
                  Match type
                  <select
                    value={ruleDraft.match_operator}
                    onChange={(event) =>
                      setRuleDraft((current) => ({
                        ...current,
                        match_operator: event.target.value as MatchOperator,
                      }))
                    }
                  >
                    <option value="contains">Contains</option>
                    <option value="equals">Equals</option>
                    <option value="starts_with">Starts with</option>
                    <option value="ends_with">Ends with</option>
                    <option value="regex">Regex</option>
                  </select>
                </label>
                <label className="span-two">
                  Match value
                  <input
                    value={ruleDraft.match_value}
                    onChange={(event) =>
                      setRuleDraft((current) => ({ ...current, match_value: event.target.value }))
                    }
                    placeholder="Text or regex pattern"
                  />
                </label>
              </div>
              <label className="check-row">
                <input
                  type="checkbox"
                  checked={ruleDraft.apply_to_existing_uncategorized}
                  onChange={(event) =>
                    setRuleDraft((current) => ({
                      ...current,
                      apply_to_existing_uncategorized: event.target.checked,
                    }))
                  }
                />
                Apply to current unknown queue
              </label>
              <div className="inline-actions">
                <button type="submit" className="button" disabled={busy === "rule"}>
                  {busy === "rule" ? "Creating..." : "Create rule"}
                </button>
                <button type="button" className="button button-secondary" onClick={() => setShowRuleForm(false)}>
                  Cancel
                </button>
              </div>
              {error ? <div className="error-banner">{error}</div> : null}
            </form>
          </td>
        </tr>
      ) : null}
      {!showRuleForm && error ? (
        <tr>
          <td colSpan={6}>
            <div className="error-banner">{error}</div>
          </td>
        </tr>
      ) : null}
    </>
  );
}
