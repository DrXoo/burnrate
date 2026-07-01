import { useEffect, useState, type FormEvent } from "react";

import { prettyMatchField, prettyMatchOperator } from "../lib/format";
import type { Rule, RuleUpdateDraft } from "../types";
import { RuleFields } from "./RuleFields";
import { StatusTag } from "./ui/StatusTag";

interface RuleCardProps {
  rule: Rule;
  onToggleRule: (ruleId: string, active: boolean) => Promise<void>;
  onUpdateRule: (ruleId: string, draft: RuleUpdateDraft) => Promise<void>;
}

export function RuleCard({ rule, onToggleRule, onUpdateRule }: RuleCardProps) {
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState<"toggle" | "save" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState<RuleUpdateDraft>({
    name: rule.name || "",
    match_field: rule.match_field,
    match_operator: rule.match_operator,
    match_value: rule.match_value,
    apply_to_existing_uncategorized: true,
  });

  useEffect(() => {
    setDraft({
      name: rule.name || "",
      match_field: rule.match_field,
      match_operator: rule.match_operator,
      match_value: rule.match_value,
      apply_to_existing_uncategorized: true,
    });
    setEditing(false);
    setBusy(null);
    setError(null);
  }, [rule]);

  async function handleToggle() {
    try {
      setBusy("toggle");
      setError(null);
      await onToggleRule(rule.rule_id, !rule.active);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : String(nextError));
      setBusy(null);
    }
  }

  async function handleSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!draft.match_value.trim()) {
      setError("Match value is required.");
      return;
    }

    try {
      setBusy("save");
      setError(null);
      await onUpdateRule(rule.rule_id, {
        ...draft,
        name: draft.name.trim(),
        match_value: draft.match_value.trim(),
      });
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : String(nextError));
      setBusy(null);
    }
  }

  return (
    <article className="list-card list-card-muted">
      <div className="row">
        <strong>{rule.name || `${rule.category_name} rule`}</strong>
        <StatusTag tone={rule.active ? "good" : "default"}>{rule.active ? "Active" : "Inactive"}</StatusTag>
      </div>

      <p className="meta-copy">
        {prettyMatchField(rule.match_field)} {prettyMatchOperator(rule.match_operator).toLowerCase()} "{rule.match_value}"
        <br />
        Category: {rule.category_name} · Priority: {rule.priority}
      </p>

      <div className="inline-actions">
        <button type="button" className="button button-secondary" onClick={() => setEditing((current) => !current)}>
          {editing ? "Close editor" : "Edit rule"}
        </button>
        <button type="button" className="button button-secondary" disabled={busy === "toggle"} onClick={handleToggle}>
          {busy === "toggle" ? "Updating..." : rule.active ? "Disable rule" : "Enable rule"}
        </button>
      </div>

      {editing ? (
        <form className="mini-form" onSubmit={handleSave}>
          <label>
            Rule name
            <input
              value={draft.name}
              onChange={(event) => setDraft((current) => ({ ...current, name: event.target.value }))}
              placeholder="Optional custom name"
            />
          </label>
          <RuleFields
            matchField={draft.match_field}
            matchOperator={draft.match_operator}
            matchValue={draft.match_value}
            disabled={busy === "save"}
            onChange={(patch) => setDraft((current) => ({ ...current, ...patch }))}
          />
          <label className="check-row">
            <input
              type="checkbox"
              checked={draft.apply_to_existing_uncategorized}
              onChange={(event) =>
                setDraft((current) => ({
                  ...current,
                  apply_to_existing_uncategorized: event.target.checked,
                }))
              }
            />
            Reapply to current unknown queue
          </label>
          <div className="inline-actions">
            <button type="submit" className="button" disabled={busy === "save"}>
              {busy === "save" ? "Saving..." : "Save changes"}
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
