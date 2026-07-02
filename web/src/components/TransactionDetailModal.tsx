import { useState, type FormEvent } from "react";

import {
  amountTone,
  prettyLabel,
  suggestRuleField,
  suggestRuleValue,
  transactionMeta,
  transactionTitle,
} from "../lib/format";
import type { Category, RuleDraft, Transaction } from "../types";
import { RuleFields } from "./RuleFields";
import { Modal } from "./ui/Modal";
import { StatusTag } from "./ui/StatusTag";

interface TransactionDetailModalProps {
  transaction: Transaction;
  categories: Category[];
  onAssignCategory: (transactionId: string, categoryId: string) => Promise<void>;
  onClearCategory: (transactionId: string) => Promise<void>;
  onCreateRule: (transactionId: string, draft: RuleDraft) => Promise<void>;
  onClose: () => void;
}

export function TransactionDetailModal({
  transaction,
  categories,
  onAssignCategory,
  onClearCategory,
  onCreateRule,
  onClose,
}: TransactionDetailModalProps) {
  const initialField = suggestRuleField(transaction);
  const hasRule = Boolean(transaction.matched_rule_id || transaction.matched_rule_name);
  const [categoryId, setCategoryId] = useState(transaction.category_id ?? "");
  const [busy, setBusy] = useState<"assign" | "clear" | "rule" | null>(null);
  const [showRuleForm, setShowRuleForm] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ruleDraft, setRuleDraft] = useState<RuleDraft>({
    name: "",
    category_id: transaction.category_id ?? "",
    match_field: initialField,
    match_operator: "contains",
    match_value: suggestRuleValue(transaction, initialField),
    apply_to_existing_uncategorized: true,
  });

  async function handleAssign() {
    if (!categoryId) {
      return;
    }
    try {
      setBusy("assign");
      setError(null);
      await onAssignCategory(transaction.transaction_id, categoryId);
      setBusy(null);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : String(nextError));
      setBusy(null);
    }
  }

  async function handleClear() {
    if (!window.confirm("Remove this transaction's category? It will return to the unknown queue.")) {
      return;
    }
    try {
      setBusy("clear");
      setError(null);
      await onClearCategory(transaction.transaction_id);
      setBusy(null);
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
      setShowRuleForm(false);
      setBusy(null);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : String(nextError));
      setBusy(null);
    }
  }

  return (
    <Modal title="Transaction detail" onClose={onClose}>
      <div className="stack">
        <div className="row">
          <div>
            <strong>{transactionTitle(transaction)}</strong>
            <p className="meta-copy">{transactionMeta(transaction)}</p>
          </div>
          <span className={`amount amount-${amountTone(transaction.amount, transaction.direction)}`}>
            {transaction.amount} {transaction.currency}
          </span>
        </div>

        <p className="meta-copy">
          {transaction.booking_date || "No booking date"} · {transaction.account_display_name} ·{" "}
          <StatusTag>{prettyLabel(transaction.status)}</StatusTag>
        </p>

        <div className="transaction-cell">
          <span className={`tag ${transaction.category_id ? "tag-good" : "tag-warn"}`}>
            {transaction.category_name || (transaction.category_id ? "Assigned" : "Unknown")}
          </span>
          {transaction.matched_rule_name || transaction.matched_rule_id ? (
            <span className="hint-copy">Rule: {transaction.matched_rule_name || "Rule attached"}</span>
          ) : null}
          <div className="inline-editor">
            <select
              value={categoryId}
              onChange={(event) => setCategoryId(event.target.value)}
              disabled={busy !== null}
            >
              <option value="">Choose a category</option>
              {categories.map((category) => (
                <option key={category.category_id} value={category.category_id}>
                  {category.name} ({category.type})
                </option>
              ))}
            </select>
            <button
              type="button"
              className="button"
              disabled={!categoryId || busy !== null}
              onClick={handleAssign}
            >
              {busy === "assign" ? "Saving..." : transaction.category_id ? "Update" : "Assign"}
            </button>
            {hasRule ? null : (
              <button
                type="button"
                className="button button-secondary"
                disabled={(!categoryId && !transaction.category_id) || busy !== null}
                onClick={() => {
                  setShowRuleForm((current) => !current);
                  setRuleDraft((current) => ({ ...current, category_id: categoryId || transaction.category_id || "" }));
                }}
              >
                Add rule
              </button>
            )}
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

        {showRuleForm ? (
          <form className="transaction-rule-box" onSubmit={handleCreateRule}>
            <div className="dual-grid">
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
                  onChange={(event) => setRuleDraft((current) => ({ ...current, category_id: event.target.value }))}
                >
                  <option value="">Choose a category</option>
                  {categories.map((category) => (
                    <option key={category.category_id} value={category.category_id}>
                      {category.name} ({category.type})
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <RuleFields
              matchField={ruleDraft.match_field}
              matchOperator={ruleDraft.match_operator}
              matchValue={ruleDraft.match_value}
              disabled={busy === "rule"}
              onChange={(patch) => setRuleDraft((current) => ({ ...current, ...patch }))}
            />
            <label className="check-row">
              <input
                type="checkbox"
                checked={ruleDraft.apply_to_existing_uncategorized}
                onChange={(event) =>
                  setRuleDraft((current) => ({ ...current, apply_to_existing_uncategorized: event.target.checked }))
                }
              />
              Apply to current unknown queue
            </label>
            <div className="inline-actions">
              <button type="submit" className="button" disabled={busy === "rule"}>
                {busy === "rule" ? "Saving..." : "Save rule"}
              </button>
              <button type="button" className="button button-secondary" onClick={() => setShowRuleForm(false)}>
                Cancel
              </button>
            </div>
          </form>
        ) : null}

        {error ? <div className="error-banner">{error}</div> : null}
      </div>
    </Modal>
  );
}
