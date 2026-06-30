import type { Category, PagingState, Transaction } from "../types";
import { Card } from "./ui/Card";
import { Pager } from "./ui/Pager";
import { UnknownQueueItem } from "./UnknownQueueItem";

interface UnknownQueuePanelProps {
  transactions: Transaction[];
  total: number;
  loading: boolean;
  error: string | null;
  paging: PagingState;
  categories: Category[];
  onMovePage: (direction: "prev" | "next") => void;
  onAssign: (transactionId: string, categoryId: string) => Promise<void>;
}

export function UnknownQueuePanel({
  transactions,
  total,
  loading,
  error,
  paging,
  categories,
  onMovePage,
  onAssign,
}: UnknownQueuePanelProps) {
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
                categories={categories}
                onAssign={onAssign}
              />
            ))}
          </div>
          <Pager total={total} offset={paging.offset} limit={paging.limit} onMove={onMovePage} />
        </>
      )}
    </Card>
  );
}
