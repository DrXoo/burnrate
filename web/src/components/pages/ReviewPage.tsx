import { useMemo, type CSSProperties } from "react";

import { IconCheck, IconSliders } from "../icons";
import {
  categoryColor,
  eur,
  shortAccount,
  suggestRuleField,
  suggestRuleValue,
  transactionMeta,
  transactionTitle,
} from "../../lib/format";
import type { Category, PagingState, RuleDraft, Transaction } from "../../types";

interface ReviewPageProps {
  items: Transaction[];
  total: number;
  loading: boolean;
  error: string | null;
  paging: PagingState;
  categories: Category[];
  ledgerItems: Transaction[];
  onMovePage: (direction: "prev" | "next") => void;
  onCategorize: (transactionId: string, categoryId: string) => Promise<void>;
  onCreateRule: (transactionId: string, draft: RuleDraft) => Promise<void>;
}

interface Suggestion {
  categoryId: string;
  name: string;
  color: string;
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

function merchantKey(transaction: Transaction): string {
  return (transaction.merchant_name || transactionTitle(transaction)).toLowerCase().trim();
}

export function ReviewPage({
  items,
  total,
  loading,
  error,
  paging,
  categories,
  ledgerItems,
  onMovePage,
  onCategorize,
  onCreateRule,
}: ReviewPageProps) {
  // Suggest a category by looking at how the same merchant was categorized before.
  const suggestionByKey = useMemo(() => {
    const byId = new Map(categories.map((category) => [category.category_id, category]));
    const map = new Map<string, Suggestion>();
    for (const transaction of ledgerItems) {
      if (!transaction.category_id) {
        continue;
      }
      const key = merchantKey(transaction);
      if (map.has(key)) {
        continue;
      }
      const category = byId.get(transaction.category_id);
      map.set(key, {
        categoryId: transaction.category_id,
        name: transaction.category_name || category?.name || "Category",
        color: category ? categoryColor(category.type, "good") : "var(--good)",
      });
    }
    return map;
  }, [ledgerItems, categories]);

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
          const suggestion = suggestionByKey.get(merchantKey(transaction));
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
                {suggestion ? (
                  <>
                    <span style={{ fontSize: 12, color: "var(--text-3)" }}>Suggested</span>
                    <button
                      type="button"
                      onClick={() => void onCategorize(transaction.transaction_id, suggestion.categoryId)}
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: 7,
                        border: `1px solid color-mix(in oklab, ${suggestion.color} 45%, transparent)`,
                        background: `color-mix(in oklab, ${suggestion.color} 14%, transparent)`,
                        color: suggestion.color,
                        borderRadius: 8,
                        padding: "7px 12px",
                        font: "600 12.5px 'Hanken Grotesque', sans-serif",
                        cursor: "pointer",
                      }}
                    >
                      <span style={{ width: 7, height: 7, borderRadius: 2, background: suggestion.color }} />
                      {suggestion.name}
                      <IconCheck />
                    </button>
                  </>
                ) : null}

                <select
                  className="br-sel"
                  value="uncat"
                  onChange={(event) => {
                    if (event.target.value !== "uncat") {
                      void onCategorize(transaction.transaction_id, event.target.value);
                    }
                  }}
                >
                  <option value="uncat">{suggestion ? "Other category…" : "Assign category…"}</option>
                  {categories.map((category) => (
                    <option key={category.category_id} value={category.category_id}>
                      {category.name}
                    </option>
                  ))}
                </select>

                <button
                  type="button"
                  disabled={!suggestion}
                  title={suggestion ? "Create a rule from this merchant" : "No learned category yet — assign one first"}
                  onClick={() => {
                    if (!suggestion) {
                      return;
                    }
                    const field = suggestRuleField(transaction);
                    void onCreateRule(transaction.transaction_id, {
                      name: "",
                      category_id: suggestion.categoryId,
                      match_field: field,
                      match_operator: "contains",
                      match_value: suggestRuleValue(transaction, field),
                      apply_to_existing_uncategorized: true,
                    });
                  }}
                  style={{
                    marginLeft: "auto",
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 6,
                    border: "1px solid var(--line-2)",
                    background: "transparent",
                    color: "var(--text-2)",
                    borderRadius: 8,
                    padding: "7px 11px",
                    font: "500 12px 'Hanken Grotesque', sans-serif",
                    cursor: suggestion ? "pointer" : "not-allowed",
                    opacity: suggestion ? 1 : 0.5,
                  }}
                >
                  <IconSliders />
                  Create rule
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
