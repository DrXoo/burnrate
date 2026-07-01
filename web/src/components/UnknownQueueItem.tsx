import { amountTone, transactionMeta, transactionTitle } from "../lib/format";
import type { Transaction } from "../types";

interface UnknownQueueItemProps {
  transaction: Transaction;
  onSelect: (transaction: Transaction) => void;
}

export function UnknownQueueItem({ transaction, onSelect }: UnknownQueueItemProps) {
  return (
    <article
      className="queue-card queue-card-clickable"
      tabIndex={0}
      onClick={() => onSelect(transaction)}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onSelect(transaction);
        }
      }}
    >
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

      <p className="hint-copy">Select to categorize or create a rule.</p>
    </article>
  );
}
