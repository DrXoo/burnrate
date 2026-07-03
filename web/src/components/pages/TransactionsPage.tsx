import { useState, type CSSProperties } from "react";

import { IconSearch } from "../icons";
import { amountTone, eur, shortAccount, transactionMeta, transactionTitle } from "../../lib/format";
import type { Account, Category, FiltersState, PagingState, Transaction } from "../../types";

interface TransactionsPageProps {
  accounts: Account[];
  categories: Category[];
  filters: FiltersState;
  applyFilters: (filters: FiltersState) => void;
  items: Transaction[];
  total: number;
  loading: boolean;
  error: string | null;
  paging: PagingState;
  monthLabel: string;
  onMovePage: (direction: "prev" | "next") => void;
  onCategorize: (transactionId: string, categoryId: string) => Promise<void>;
  onUncategorize: (transactionId: string) => Promise<void>;
}

const GRID = "78px 1fr 150px 190px 110px";

const pagerButton: CSSProperties = {
  border: "1px solid var(--line-2)",
  background: "var(--bg-3)",
  borderRadius: 7,
  padding: "5px 11px",
  font: "500 12px 'Hanken Grotesque', sans-serif",
};

function shortDate(value: string | null | undefined): string {
  if (!value) {
    return "—";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleDateString(undefined, { day: "2-digit", month: "short" });
}

export function TransactionsPage({
  accounts,
  categories,
  filters,
  applyFilters,
  items,
  total,
  loading,
  error,
  paging,
  monthLabel,
  onMovePage,
  onCategorize,
  onUncategorize,
}: TransactionsPageProps) {
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState<string>(filters.categorized === "false" ? "uncat" : "all");

  function handleAccount(value: string) {
    applyFilters({ ...filters, accountId: value === "all" ? "" : value });
  }

  function handleCategory(value: string) {
    setCategoryFilter(value);
    const categorized: FiltersState["categorized"] = value === "uncat" ? "false" : value === "all" ? "" : "true";
    applyFilters({ ...filters, categorized });
  }

  const visible = items.filter((transaction) => {
    if (search && !transactionTitle(transaction).toLowerCase().includes(search.toLowerCase())) {
      return false;
    }
    if (categoryFilter !== "all" && categoryFilter !== "uncat" && transaction.category_id !== categoryFilter) {
      return false;
    }
    return true;
  });

  return (
    <div>
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center", marginBottom: 16 }}>
        <div style={{ position: "relative", flex: 1, minWidth: 200 }}>
          <span style={{ position: "absolute", left: 11, top: "50%", transform: "translateY(-50%)", display: "flex" }}>
            <IconSearch color="var(--text-3)" />
          </span>
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search merchant…"
            style={{
              width: "100%",
              padding: "9px 12px 9px 33px",
              background: "var(--bg-2)",
              border: "1px solid var(--line-2)",
              borderRadius: 9,
              color: "var(--text)",
              font: "400 13px 'Hanken Grotesque', sans-serif",
              outline: "none",
            }}
          />
        </div>
        <select className="br-sel" value={filters.accountId || "all"} onChange={(event) => handleAccount(event.target.value)}>
          <option value="all">All accounts</option>
          {accounts.map((account) => (
            <option key={account.account_id} value={account.account_id}>
              {account.display_name}
            </option>
          ))}
        </select>
        <select className="br-sel" value={categoryFilter} onChange={(event) => handleCategory(event.target.value)}>
          <option value="all">All categories</option>
          <option value="uncat">Uncategorized</option>
          {categories.map((category) => (
            <option key={category.category_id} value={category.category_id}>
              {category.name}
            </option>
          ))}
        </select>
      </div>

      <div
        style={{
          background: "var(--bg-2)",
          border: "1px solid var(--line)",
          borderRadius: 14,
          overflow: "hidden",
          boxShadow: "var(--card-shadow)",
        }}
      >
        <div
          style={{
            display: "grid",
            gridTemplateColumns: GRID,
            gap: 12,
            padding: "11px 18px",
            borderBottom: "1px solid var(--line)",
            fontSize: 11,
            textTransform: "uppercase",
            letterSpacing: "0.05em",
            color: "var(--text-3)",
            fontWeight: 600,
          }}
        >
          <div>Date</div>
          <div>Merchant</div>
          <div>Account</div>
          <div>Category</div>
          <div style={{ textAlign: "right" }}>Amount</div>
        </div>

        {error ? (
          <div style={{ padding: "24px 18px", color: "var(--over)", fontSize: 13 }}>{error}</div>
        ) : loading && items.length === 0 ? (
          <div style={{ padding: "24px 18px", color: "var(--text-3)", fontSize: 13 }}>Loading transactions…</div>
        ) : visible.length === 0 ? (
          <div style={{ padding: "36px 18px", textAlign: "center", color: "var(--text-3)", fontSize: 13 }}>
            No transactions match these filters.
          </div>
        ) : (
          visible.map((transaction) => {
            const positive = amountTone(transaction.amount, transaction.direction) === "positive";
            return (
              <div
                key={transaction.transaction_id}
                style={{
                  display: "grid",
                  gridTemplateColumns: GRID,
                  gap: 12,
                  padding: "12px 18px",
                  borderBottom: "1px solid var(--line)",
                  alignItems: "center",
                }}
              >
                <div className="num" style={{ fontSize: 12.5, color: "var(--text-3)" }}>
                  {shortDate(transaction.booking_date || transaction.value_date)}
                </div>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 13.5, fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {transactionTitle(transaction)}
                  </div>
                  <div style={{ fontSize: 11, color: "var(--text-3)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {transactionMeta(transaction)}
                  </div>
                </div>
                <div className="num" style={{ fontSize: 12, color: "var(--text-2)" }}>
                  {shortAccount(transaction.account_display_name)}
                </div>
                <div>
                  <select
                    className="br-sel"
                    style={{ maxWidth: "100%", borderColor: transaction.category_id ? "var(--line-2)" : "var(--watch)" }}
                    value={transaction.category_id ?? "uncat"}
                    onChange={(event) => {
                      const value = event.target.value;
                      if (value === "uncat") {
                        void onUncategorize(transaction.transaction_id);
                      } else {
                        void onCategorize(transaction.transaction_id, value);
                      }
                    }}
                  >
                    <option value="uncat">— Assign —</option>
                    {categories.map((category) => (
                      <option key={category.category_id} value={category.category_id}>
                        {category.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div
                  className="num"
                  style={{ textAlign: "right", fontSize: 14, fontWeight: 600, color: positive ? "var(--good)" : "var(--text)" }}
                >
                  {eur(transaction.amount)}
                </div>
              </div>
            );
          })
        )}

        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 18px", fontSize: 12.5, color: "var(--text-3)" }}>
          <span>
            Showing <span className="num">{visible.length}</span> of <span className="num">{total}</span> for {monthLabel}
          </span>
          <div style={{ display: "flex", gap: 6 }}>
            <button
              type="button"
              onClick={() => onMovePage("prev")}
              disabled={paging.offset === 0}
              style={{ ...pagerButton, color: paging.offset === 0 ? "var(--text-3)" : "var(--text)", cursor: paging.offset === 0 ? "default" : "pointer" }}
            >
              Prev
            </button>
            <button
              type="button"
              onClick={() => onMovePage("next")}
              disabled={paging.offset + paging.limit >= total}
              style={{
                ...pagerButton,
                color: paging.offset + paging.limit >= total ? "var(--text-3)" : "var(--text)",
                cursor: paging.offset + paging.limit >= total ? "default" : "pointer",
              }}
            >
              Next
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
