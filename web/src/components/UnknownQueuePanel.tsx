import { useEffect, useState } from "react";

import type { Category, PagingState, RuleDraft, Transaction } from "../types";
import { Card } from "./ui/Card";
import { Pager } from "./ui/Pager";
import { TransactionDetailModal } from "./TransactionDetailModal";
import { UnknownQueueItem } from "./UnknownQueueItem";

interface UnknownQueuePanelProps {
  transactions: Transaction[];
  total: number;
  loading: boolean;
  error: string | null;
  paging: PagingState;
  categories: Category[];
  onMovePage: (direction: "prev" | "next") => void;
  onAssignCategory: (transactionId: string, categoryId: string) => Promise<void>;
  onClearCategory: (transactionId: string) => Promise<void>;
  onCreateRule: (transactionId: string, draft: RuleDraft) => Promise<void>;
}

export function UnknownQueuePanel({
  transactions,
  total,
  loading,
  error,
  paging,
  categories,
  onMovePage,
  onAssignCategory,
  onClearCategory,
  onCreateRule,
}: UnknownQueuePanelProps) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [bulkCategoryId, setBulkCategoryId] = useState("");
  const [bulkBusy, setBulkBusy] = useState(false);

  // Selection applies to the current view; reset it whenever the list changes.
  useEffect(() => {
    setSelectedIds(new Set());
  }, [transactions]);

  const selectedTransaction = transactions.find((item) => item.transaction_id === selectedId) ?? null;
  const allSelected = transactions.length > 0 && transactions.every((item) => selectedIds.has(item.transaction_id));

  function toggleSelect(transactionId: string) {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (next.has(transactionId)) {
        next.delete(transactionId);
      } else {
        next.add(transactionId);
      }
      return next;
    });
  }

  function toggleSelectAll() {
    setSelectedIds(allSelected ? new Set() : new Set(transactions.map((item) => item.transaction_id)));
  }

  async function handleBulkAssign() {
    if (!bulkCategoryId || selectedIds.size === 0) {
      return;
    }
    setBulkBusy(true);
    try {
      for (const transactionId of Array.from(selectedIds)) {
        try {
          await onAssignCategory(transactionId, bulkCategoryId);
        } catch {
          // Best-effort: keep assigning the rest even if one fails.
        }
      }
      setBulkCategoryId("");
    } finally {
      setBulkBusy(false);
    }
  }

  return (
    <Card
      title="Unknown queue"
      subtitle="Uncategorized transactions land here first. Clear them quickly so rules and budgets start telling the truth."
      actions={<span className="glass-pill glass-pill-warn">{total} waiting</span>}
    >
      {loading ? (
        <div className="empty-state">Loading uncategorized transactions...</div>
      ) : error ? (
        <div className="error-banner">{error}</div>
      ) : transactions.length === 0 ? (
        <div className="success-banner">The unknown queue is empty for the current filters.</div>
      ) : (
        <>
          <div className="queue-toolbar">
            <label className="check-row">
              <input type="checkbox" checked={allSelected} onChange={toggleSelectAll} />
              Select all on this page
            </label>
          </div>

          {selectedIds.size > 0 ? (
            <div className="bulk-bar">
              <span>{selectedIds.size} selected</span>
              <select value={bulkCategoryId} onChange={(event) => setBulkCategoryId(event.target.value)} disabled={bulkBusy}>
                <option value="">Choose a category</option>
                {categories.map((category) => (
                  <option key={category.category_id} value={category.category_id}>
                    {category.name} ({category.type})
                  </option>
                ))}
              </select>
              <button type="button" className="button" disabled={!bulkCategoryId || bulkBusy} onClick={handleBulkAssign}>
                {bulkBusy ? "Assigning..." : "Assign to selected"}
              </button>
              <button
                type="button"
                className="button button-secondary"
                disabled={bulkBusy}
                onClick={() => setSelectedIds(new Set())}
              >
                Clear
              </button>
            </div>
          ) : null}

          <div className="stack">
            {transactions.map((transaction) => (
              <UnknownQueueItem
                key={transaction.transaction_id}
                transaction={transaction}
                selected={selectedIds.has(transaction.transaction_id)}
                onToggleSelect={toggleSelect}
                onSelect={(item) => setSelectedId(item.transaction_id)}
              />
            ))}
          </div>
          <Pager total={total} offset={paging.offset} limit={paging.limit} onMove={onMovePage} />
        </>
      )}

      {selectedTransaction ? (
        <TransactionDetailModal
          key={selectedTransaction.transaction_id}
          transaction={selectedTransaction}
          categories={categories}
          onAssignCategory={onAssignCategory}
          onClearCategory={onClearCategory}
          onCreateRule={onCreateRule}
          onClose={() => setSelectedId(null)}
        />
      ) : null}
    </Card>
  );
}
