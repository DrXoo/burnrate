import type { CSSProperties } from "react";

import { IconCheck } from "../icons";
import { eur, shortAccount, transactionMeta, transactionTitle } from "../../lib/format";
import type { Category, PagingState, Transaction } from "../../types";

interface ReviewPageProps {
  items: Transaction[];
  total: number;
  loading: boolean;
  error: string | null;
  paging: PagingState;
  /** Only an assignment picker here, so archived categories are excluded: the queue
      exists to file new spend, and a retired category must not receive any. */
  assignableCategories: Category[];
  onMovePage: (direction: "prev" | "next") => void;
  onCategorize: (transactionId: string, categoryId: string) => Promise<void>;
  onExclude: (transactionId: string) => Promise<void>;
}

const pagerButton: CSSProperties = {
  border: "1px solid var(--line-2)",
  background: "var(--bg-3)",
  color: "var(--text)",
  borderRadius: 7,
  padding: "5px 11px",
  font: "500 12px 'Hanken Grotesque', sans-serif",
  cursor: "pointer",
};

const ignoreButton: CSSProperties = {
  border: "1px solid var(--line-2)",
  background: "transparent",
  color: "var(--text-2)",
  borderRadius: 7,
  padding: "6px 12px",
  font: "500 12px 'Hanken Grotesque', sans-serif",
  cursor: "pointer",
  whiteSpace: "nowrap",
};

export function ReviewPage({ items, total, loading, error, paging, assignableCategories, onMovePage, onCategorize, onExclude }: ReviewPageProps) {
  if (error && items.length === 0) {
    return <div style={{ padding: "24px 4px", color: "var(--over)", fontSize: 13.5 }}>{error}</div>;
  }

  if (loading && items.length === 0) {
    return <div style={{ padding: "40px 4px", color: "var(--text-2)", fontSize: 14 }}>Loading the queue…</div>;
  }

  if (total === 0) {
    return (
      <div style={{ textAlign: "center", padding: "70px 20px", maxWidth: 420, margin: "0 auto" }}>
        <div
          style={{
            width: 72,
            height: 72,
            borderRadius: 20,
            margin: "0 auto 20px",
            background: "var(--good-dim)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <IconCheck size={34} color="var(--good)" />
        </div>
        <div className="num" style={{ fontSize: 22, fontWeight: 600, marginBottom: 8 }}>
          Queue's clear
        </div>
        <p style={{ fontSize: 14, color: "var(--text-2)", lineHeight: 1.6, margin: 0 }}>
          Every transaction this month is categorized. New unknowns will land here after the next sync — nothing to do
          right now.
        </p>
      </div>
    );
  }

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 18 }}>
        <div>
          <div style={{ fontSize: 16, fontWeight: 600 }}>Unknown queue</div>
          <div style={{ fontSize: 13, color: "var(--text-2)" }}>
            <span className="num">{total}</span> transaction{total === 1 ? "" : "s"} waiting to be categorized
          </div>
        </div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 12, maxWidth: 720 }}>
        {items.map((transaction) => {
          const positive = Number(transaction.amount) > 0;
          return (
            <div
              key={transaction.transaction_id}
              style={{
                background: "var(--bg-2)",
                border: "1px solid var(--line)",
                borderRadius: 14,
                padding: "16px 18px",
                boxShadow: "var(--card-shadow)",
                animation: "br-rise .3s ease both",
              }}
            >
              <div style={{ display: "flex", alignItems: "flex-start", gap: 14, flexWrap: "wrap" }}>
                <div style={{ flex: 1, minWidth: 180 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
                    <div style={{ fontSize: 15, fontWeight: 600 }}>{transactionTitle(transaction)}</div>
                    <div className="num" style={{ fontSize: 15, fontWeight: 600, color: positive ? "var(--good)" : "var(--text)" }}>
                      {eur(transaction.amount)}
                    </div>
                  </div>
                  <div className="num" style={{ fontSize: 12, color: "var(--text-3)", marginTop: 2 }}>
                    {transactionMeta(transaction)} · {shortAccount(transaction.account_display_name)}
                  </div>
                </div>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 14, flexWrap: "wrap" }}>
                <span style={{ fontSize: 12, color: "var(--text-3)" }}>Assign a category</span>
                <select
                  className="br-sel"
                  value="uncat"
                  onChange={(event) => {
                    if (event.target.value !== "uncat") {
                      void onCategorize(transaction.transaction_id, event.target.value);
                    }
                  }}
                >
                  <option value="uncat">Choose category…</option>
                  {assignableCategories.map((category) => (
                    <option key={category.category_id} value={category.category_id}>
                      {category.name}
                    </option>
                  ))}
                </select>
                <span style={{ fontSize: 12, color: "var(--text-3)" }}>or</span>
                <button
                  type="button"
                  style={ignoreButton}
                  title="Not a budget item (reimbursement, transfer, duplicate) — clears it from the queue without counting toward spend or income"
                  onClick={() => void onExclude(transaction.transaction_id)}
                >
                  Ignore
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {total > paging.limit ? (
        <div style={{ display: "flex", gap: 6, marginTop: 16, maxWidth: 720, justifyContent: "flex-end" }}>
          <button
            type="button"
            onClick={() => onMovePage("prev")}
            disabled={paging.offset === 0}
            style={{ ...pagerButton, opacity: paging.offset === 0 ? 0.5 : 1, cursor: paging.offset === 0 ? "default" : "pointer" }}
          >
            Prev
          </button>
          <button
            type="button"
            onClick={() => onMovePage("next")}
            disabled={paging.offset + paging.limit >= total}
            style={{
              ...pagerButton,
              opacity: paging.offset + paging.limit >= total ? 0.5 : 1,
              cursor: paging.offset + paging.limit >= total ? "default" : "pointer",
            }}
          >
            Next
          </button>
        </div>
      ) : null}
    </div>
  );
}
