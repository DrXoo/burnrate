import { useEffect, useState, type FormEvent } from "react";

import type { Account, Category, FiltersState, PagingState, RuleDraft, Transaction } from "../types";
import { Card } from "./ui/Card";
import { Pager } from "./ui/Pager";
import { TransactionDetailModal } from "./TransactionDetailModal";
import { TransactionRow } from "./TransactionRow";

interface TransactionsPanelProps {
  accounts: Account[];
  categories: Category[];
  filters: FiltersState;
  paging: PagingState;
  transactions: Transaction[];
  total: number;
  loading: boolean;
  error: string | null;
  onApplyFilters: (filters: FiltersState) => void;
  onMovePage: (direction: "prev" | "next") => void;
  onAssignCategory: (transactionId: string, categoryId: string) => Promise<void>;
  onClearCategory: (transactionId: string) => Promise<void>;
  onCreateRule: (transactionId: string, draft: RuleDraft) => Promise<void>;
}

export function TransactionsPanel({
  accounts,
  categories,
  filters,
  paging,
  transactions,
  total,
  loading,
  error,
  onApplyFilters,
  onMovePage,
  onAssignCategory,
  onClearCategory,
  onCreateRule,
}: TransactionsPanelProps) {
  const [draft, setDraft] = useState(filters);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    setDraft(filters);
  }, [filters]);

  const selectedTransaction = transactions.find((item) => item.transaction_id === selectedId) ?? null;

  return (
    <Card
      title="Transactions"
      subtitle="Live imported ledger entries with inline categorization and rule creation."
      actions={<span className="glass-pill">{total} matching</span>}
    >
      <form
        className="filter-grid"
        onSubmit={(event: FormEvent<HTMLFormElement>) => {
          event.preventDefault();
          onApplyFilters(draft);
        }}
      >
        <label>
          Month
          <input
            type="month"
            value={draft.month}
            onChange={(event) => setDraft((current) => ({ ...current, month: event.target.value }))}
          />
        </label>
        <label>
          Account
          <select
            value={draft.accountId}
            onChange={(event) => setDraft((current) => ({ ...current, accountId: event.target.value }))}
          >
            <option value="">All accounts</option>
            {accounts.map((account) => (
              <option key={account.account_id} value={account.account_id}>
                {account.display_name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Status
          <select
            value={draft.status}
            onChange={(event) => setDraft((current) => ({ ...current, status: event.target.value }))}
          >
            <option value="">Any status</option>
            <option value="booked">Booked</option>
            <option value="pending">Pending *</option>
            <option value="ignored">Ignored</option>
          </select>
        </label>
        <label>
          Categorization
          <select
            value={draft.categorized}
            onChange={(event) =>
              setDraft((current) => ({
                ...current,
                categorized: event.target.value as FiltersState["categorized"],
              }))
            }
          >
            <option value="">All transactions</option>
            <option value="false">Only unknown</option>
            <option value="true">Only categorized</option>
          </select>
        </label>
        <button type="submit" className="button filter-button">
          Apply filters
        </button>
      </form>

      {loading ? (
        <div className="empty-state">Loading transactions...</div>
      ) : error ? (
        <div className="error-banner">{error}</div>
      ) : transactions.length === 0 ? (
        <div className="empty-state">No transactions matched these filters. Try a different month or clear a filter.</div>
      ) : (
        <>
          <div className="table-shell">
            <table className="ledger-table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Description</th>
                  <th>Account</th>
                  <th>Status</th>
                  <th>Category</th>
                  <th>Amount</th>
                </tr>
              </thead>
              <tbody>
                {transactions.map((transaction) => (
                  <TransactionRow
                    key={transaction.transaction_id}
                    transaction={transaction}
                    onSelect={(item) => setSelectedId(item.transaction_id)}
                  />
                ))}
              </tbody>
            </table>
          </div>
          <Pager total={total} offset={paging.offset} limit={paging.limit} onMove={onMovePage} />
        </>
      )}

      <p className="hint-copy" role="note">
        * Held or pending transactions may not appear here. Many banks only share a transaction through open
        banking once it has fully posted, so BurnRate can display it only after your bank finalizes it —
        usually within a few days.
      </p>

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
