import { amountTone, prettyLabel, transactionMeta, transactionTitle } from "../lib/format";
import type { Transaction } from "../types";
import { StatusTag } from "./ui/StatusTag";

interface TransactionRowProps {
  transaction: Transaction;
  onSelect: (transaction: Transaction) => void;
}

export function TransactionRow({ transaction, onSelect }: TransactionRowProps) {
  return (
    <tr
      className="transaction-row"
      tabIndex={0}
      onClick={() => onSelect(transaction)}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onSelect(transaction);
        }
      }}
    >
      <td data-label="Date">{transaction.booking_date || "No booking date"}</td>
      <td className="transaction-primary-cell" data-label="Description">
        <strong>{transactionTitle(transaction)}</strong>
        <br />
        <span className="muted">{transactionMeta(transaction)}</span>
      </td>
      <td data-label="Account">{transaction.account_display_name}</td>
      <td data-label="Status">
        <StatusTag>{prettyLabel(transaction.status)}</StatusTag>
      </td>
      <td data-label="Category">
        <div className="transaction-cell">
          <span className={`tag ${transaction.category_id ? "tag-good" : "tag-warn"}`}>
            {transaction.category_name || (transaction.category_id ? "Assigned" : "Unknown")}
          </span>
          {transaction.matched_rule_name || transaction.matched_rule_id ? (
            <span className="hint-copy">Rule: {transaction.matched_rule_name || "Rule attached"}</span>
          ) : null}
        </div>
      </td>
      <td className={`amount amount-${amountTone(transaction.amount, transaction.direction)}`} data-label="Amount">
        {transaction.amount} {transaction.currency}
      </td>
    </tr>
  );
}
