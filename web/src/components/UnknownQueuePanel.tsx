import { useState } from "react";

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
  const selectedTransaction = transactions.find((item) => item.transaction_id === selectedId) ?? null;

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
          <div className="stack">
            {transactions.map((transaction) => (
              <UnknownQueueItem
                key={transaction.transaction_id}
                transaction={transaction}
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
