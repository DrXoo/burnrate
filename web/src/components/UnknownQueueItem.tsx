import { useEffect, useState } from "react";

import { amountTone, transactionMeta, transactionTitle } from "../lib/format";
import type { Category, Transaction } from "../types";

interface UnknownQueueItemProps {
  transaction: Transaction;
  categories: Category[];
  onAssign: (transactionId: string, categoryId: string) => Promise<void>;
}

export function UnknownQueueItem({ transaction, categories, onAssign }: UnknownQueueItemProps) {
  const [categoryId, setCategoryId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setCategoryId("");
    setError(null);
    setBusy(false);
  }, [transaction.transaction_id]);

  async function handleAssign() {
    if (!categoryId) {
      return;
    }
    try {
      setBusy(true);
      setError(null);
      await onAssign(transaction.transaction_id, categoryId);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : String(nextError));
      setBusy(false);
    }
  }

  return (
    <article className="queue-card">
      <div className="queue-head">
        <div>
          <h3>{transactionTitle(transaction)}</h3>
          <p className="meta-copy">
            {transaction.account_display_name} · {transaction.booking_date || "No booking date"}
            <br />
            {transactionMeta(transaction)} ·{" "}
            <span className={`amount amount-${amountTone(transaction.amount, transaction.direction)}`}>
              {transaction.amount} {transaction.currency}
            </span>
          </p>
        </div>
        <span className="queue-badge">Unknown</span>
      </div>

      <div className="queue-actions">
        <select value={categoryId} disabled={!categories.length || busy} onChange={(event) => setCategoryId(event.target.value)}>
          <option value="">Choose a category</option>
          {categories.map((category) => (
            <option key={category.category_id} value={category.category_id}>
              {category.name} ({category.type})
            </option>
          ))}
        </select>
        <button type="button" className="button" disabled={!categoryId || busy} onClick={handleAssign}>
          {busy ? "Assigning..." : "Assign"}
        </button>
      </div>

      {error ? <div className="error-banner">{error}</div> : null}
    </article>
  );
}
