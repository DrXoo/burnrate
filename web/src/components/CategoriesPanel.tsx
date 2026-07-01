import { useState, type FormEvent } from "react";

import { prettyLabel } from "../lib/format";
import type { Category } from "../types";
import { Card } from "./ui/Card";
import { StatusTag } from "./ui/StatusTag";

interface CategoriesPanelProps {
  categories: Category[];
  onCreateCategory: (name: string, type: Category["type"]) => Promise<void>;
}

export function CategoriesPanel({ categories, onCreateCategory }: CategoriesPanelProps) {
  const [name, setName] = useState("");
  const [type, setType] = useState<Category["type"]>("expense");
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!name.trim()) {
      setError("Category name is required.");
      setFeedback(null);
      return;
    }

    try {
      setBusy(true);
      setError(null);
      setFeedback(null);
      await onCreateCategory(name.trim(), type);
      setName("");
      setType("expense");
      setFeedback("Category created.");
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : String(nextError));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title="Categories" subtitle="Stable buckets for spending, income, and transfers." actions={<span className="glass-pill">{categories.length} defined</span>}>
      <div className="stack">
        {categories.length === 0 ? (
          <div className="empty-state">No categories yet. Create your first one to start shaping the queue.</div>
        ) : (
          categories.map((category) => (
            <article key={category.category_id} className="list-card">
              <div className="row">
                <strong>{category.name}</strong>
                <StatusTag>{prettyLabel(category.type)}</StatusTag>
              </div>
              <p className="meta-copy">{category.active ? "Active" : "Inactive"}</p>
            </article>
          ))
        )}
      </div>

      <form className="form-stack" onSubmit={handleSubmit}>
        <label>
          Category name
          <input value={name} onChange={(event) => setName(event.target.value)} placeholder="Food, Rent, Transport..." />
        </label>
        <label>
          Type
          <select value={type} onChange={(event) => setType(event.target.value as Category["type"])}>
            <option value="expense">Expense</option>
            <option value="income">Income</option>
            <option value="transfer">Transfer</option>
          </select>
        </label>
        <button type="submit" className="button" disabled={busy}>
          {busy ? "Creating..." : "Create category"}
        </button>
      </form>

      {feedback ? <div className="success-banner">{feedback}</div> : null}
      {error ? <div className="error-banner">{error}</div> : null}
    </Card>
  );
}
