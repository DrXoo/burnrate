import { useMemo, useState, type CSSProperties } from "react";

import { IconSearch, IconSliders } from "../icons";
import {
  amountTone,
  eur,
  shortAccount,
  suggestRuleField,
  suggestRuleValue,
  transactionMeta,
  transactionTitle,
} from "../../lib/format";
import type {
  Account,
  Category,
  FiltersState,
  MatchField,
  MatchOperator,
  PagingState,
  Rule,
  RuleDraft,
  RuleUpdateDraft,
  Transaction,
} from "../../types";

interface TransactionsPageProps {
  accounts: Account[];
  categories: Category[];
  rules: Rule[];
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
  onCreateRule: (transactionId: string, draft: RuleDraft) => Promise<void>;
  onUpdateRule: (ruleId: string, draft: RuleUpdateDraft) => Promise<void>;
  onDeleteRule: (ruleId: string) => Promise<void>;
}

interface RuleFormState {
  mode: "create" | "edit";
  editRuleId: string | null;
  name: string;
  match_field: MatchField;
  match_operator: MatchOperator;
  match_value: string;
  category_id: string;
}

const GRID = "76px 1fr 138px 204px 96px";

const FIELD_OPTIONS: Array<{ value: MatchField; label: string }> = [
  { value: "merchant_name", label: "Merchant" },
  { value: "description", label: "Description" },
  { value: "counterparty_name", label: "Counterparty" },
];

const OPERATOR_OPTIONS: Array<{ value: MatchOperator; label: string }> = [
  { value: "contains", label: "contains" },
  { value: "starts_with", label: "starts with" },
  { value: "ends_with", label: "ends with" },
  { value: "equals", label: "equals" },
];

const pagerButton: CSSProperties = {
  border: "1px solid var(--line-2)",
  background: "var(--bg-3)",
  borderRadius: 7,
  padding: "5px 11px",
  font: "500 12px 'Hanken Grotesque', sans-serif",
};

const accentButton: CSSProperties = {
  border: "none",
  background: "var(--accent)",
  color: "#0a0d10",
  borderRadius: 8,
  padding: "7px 16px",
  font: "600 12px 'Hanken Grotesque', sans-serif",
  cursor: "pointer",
};

const ghostButton: CSSProperties = {
  border: "1px solid var(--line-2)",
  background: "transparent",
  color: "var(--text-2)",
  borderRadius: 8,
  padding: "7px 14px",
  font: "500 12px 'Hanken Grotesque', sans-serif",
  cursor: "pointer",
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
  rules,
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
  onCreateRule,
  onUpdateRule,
  onDeleteRule,
}: TransactionsPageProps) {
  const [search, setSearch] = useState("");
  const [ruleTxnId, setRuleTxnId] = useState<string | null>(null);
  const [ruleForm, setRuleForm] = useState<RuleFormState | null>(null);

  const rulesById = useMemo(() => new Map(rules.map((rule) => [rule.rule_id, rule])), [rules]);
  const categoryValue = filters.categoryId ? filters.categoryId : filters.categorized === "false" ? "uncat" : "all";

  function handleAccount(value: string) {
    applyFilters({ ...filters, accountId: value === "all" ? "" : value });
  }

  function handleCategory(value: string) {
    if (value === "all") {
      applyFilters({ ...filters, categoryId: "", categorized: "" });
    } else if (value === "uncat") {
      applyFilters({ ...filters, categoryId: "", categorized: "false" });
    } else {
      applyFilters({ ...filters, categoryId: value, categorized: "" });
    }
  }

  function closeForm() {
    setRuleTxnId(null);
    setRuleForm(null);
  }

  function openCreate(transaction: Transaction) {
    if (ruleTxnId === transaction.transaction_id && ruleForm?.mode === "create") {
      closeForm();
      return;
    }
    const field = suggestRuleField(transaction);
    setRuleTxnId(transaction.transaction_id);
    setRuleForm({
      mode: "create",
      editRuleId: null,
      name: "",
      match_field: field,
      match_operator: "contains",
      match_value: suggestRuleValue(transaction, field),
      category_id: transaction.category_id ?? categories[0]?.category_id ?? "",
    });
  }

  function openEdit(transaction: Transaction, rule: Rule) {
    if (ruleTxnId === transaction.transaction_id && ruleForm?.mode === "edit") {
      closeForm();
      return;
    }
    setRuleTxnId(transaction.transaction_id);
    setRuleForm({
      mode: "edit",
      editRuleId: rule.rule_id,
      name: rule.name ?? "",
      match_field: rule.match_field,
      match_operator: rule.match_operator,
      match_value: rule.match_value,
      category_id: rule.category_id,
    });
  }

  async function submitRule() {
    if (!ruleTxnId || !ruleForm || !ruleForm.category_id) {
      return;
    }
    if (ruleForm.mode === "edit" && ruleForm.editRuleId) {
      await onUpdateRule(ruleForm.editRuleId, {
        name: ruleForm.name,
        match_field: ruleForm.match_field,
        match_operator: ruleForm.match_operator,
        match_value: ruleForm.match_value,
        apply_to_existing_uncategorized: true,
      });
    } else {
      await onCreateRule(ruleTxnId, {
        name: ruleForm.name,
        category_id: ruleForm.category_id,
        match_field: ruleForm.match_field,
        match_operator: ruleForm.match_operator,
        match_value: ruleForm.match_value,
        apply_to_existing_uncategorized: true,
      });
    }
    closeForm();
  }

  async function removeRule() {
    if (ruleForm?.editRuleId) {
      await onDeleteRule(ruleForm.editRuleId);
    }
    closeForm();
  }

  const visible = items.filter(
    (transaction) => !search || transactionTitle(transaction).toLowerCase().includes(search.toLowerCase()),
  );

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
        <select className="br-sel" value={categoryValue} onChange={(event) => handleCategory(event.target.value)}>
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
          <div>Category &amp; rule</div>
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
            const matchedRule = transaction.matched_rule_id ? rulesById.get(transaction.matched_rule_id) : undefined;
            const formOpen = ruleTxnId === transaction.transaction_id && ruleForm !== null;
            return (
              <div key={transaction.transaction_id} style={{ borderBottom: "1px solid var(--line)" }}>
                <div style={{ display: "grid", gridTemplateColumns: GRID, gap: 12, padding: "12px 18px", alignItems: "start" }}>
                  <div className="num" style={{ fontSize: 12.5, color: "var(--text-3)", paddingTop: 7 }}>
                    {shortDate(transaction.booking_date || transaction.value_date)}
                  </div>
                  <div style={{ minWidth: 0, paddingTop: 4 }}>
                    <div style={{ fontSize: 13.5, fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {transactionTitle(transaction)}
                    </div>
                    <div style={{ fontSize: 11, color: "var(--text-3)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {transactionMeta(transaction)}
                    </div>
                  </div>
                  <div className="num" style={{ fontSize: 12, color: "var(--text-2)", paddingTop: 7 }}>
                    {shortAccount(transaction.account_display_name)}
                  </div>
                  <div style={{ minWidth: 0, display: "flex", flexDirection: "column", gap: 6 }}>
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
                    {matchedRule ? (
                      <button
                        type="button"
                        title="Edit the rule that categorized this transaction"
                        onClick={() => openEdit(transaction, matchedRule)}
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: 6,
                          alignSelf: "flex-start",
                          maxWidth: "100%",
                          border: `1px solid ${formOpen && ruleForm?.mode === "edit" ? "var(--accent)" : "var(--line-2)"}`,
                          background: "var(--bg-3)",
                          color: "var(--text-2)",
                          borderRadius: 7,
                          padding: "3px 8px",
                          font: "500 11px 'Hanken Grotesque', sans-serif",
                          cursor: "pointer",
                        }}
                      >
                        <IconSliders size={12} />
                        <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          Rule: {matchedRule.name || "attached"}
                        </span>
                      </button>
                    ) : (
                      <button
                        type="button"
                        title="Create a categorization rule from this transaction"
                        onClick={() => openCreate(transaction)}
                        disabled={categories.length === 0}
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: 6,
                          alignSelf: "flex-start",
                          border: `1px solid ${formOpen && ruleForm?.mode === "create" ? "var(--accent)" : "var(--line-2)"}`,
                          background: "transparent",
                          color: formOpen && ruleForm?.mode === "create" ? "var(--accent)" : "var(--text-2)",
                          borderRadius: 7,
                          padding: "3px 8px",
                          font: "500 11px 'Hanken Grotesque', sans-serif",
                          cursor: categories.length === 0 ? "not-allowed" : "pointer",
                          opacity: categories.length === 0 ? 0.5 : 1,
                        }}
                      >
                        <IconSliders size={12} />
                        Create rule
                      </button>
                    )}
                  </div>
                  <div
                    className="num"
                    style={{ textAlign: "right", fontSize: 14, fontWeight: 600, color: positive ? "var(--good)" : "var(--text)", paddingTop: 6 }}
                  >
                    {eur(transaction.amount)}
                  </div>
                </div>

                {formOpen && ruleForm ? (
                  <div style={{ padding: "0 18px 16px" }}>
                    <div style={{ background: "var(--bg-3)", border: "1px solid var(--accent)", borderRadius: 11, padding: "13px 14px" }}>
                      <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--text-3)", fontWeight: 700, marginBottom: 9 }}>
                        {ruleForm.mode === "edit" ? "Edit rule" : `New rule from “${transactionTitle(transaction)}”`}
                      </div>
                      <input
                        className="br-input"
                        style={{ width: "100%", background: "var(--bg-2)" }}
                        value={ruleForm.name}
                        onChange={(event) => setRuleForm({ ...ruleForm, name: event.target.value })}
                        placeholder="Rule name (optional)"
                      />
                      <div style={{ display: "flex", gap: 6, marginTop: 8, flexWrap: "wrap" }}>
                        <select
                          className="br-sel"
                          style={{ flex: 1, minWidth: 130 }}
                          value={ruleForm.match_field}
                          onChange={(event) => setRuleForm({ ...ruleForm, match_field: event.target.value as MatchField })}
                        >
                          {FIELD_OPTIONS.map((option) => (
                            <option key={option.value} value={option.value}>
                              {option.label}
                            </option>
                          ))}
                        </select>
                        <select
                          className="br-sel"
                          style={{ flex: 1, minWidth: 130 }}
                          value={ruleForm.match_operator}
                          onChange={(event) => setRuleForm({ ...ruleForm, match_operator: event.target.value as MatchOperator })}
                        >
                          {OPERATOR_OPTIONS.map((option) => (
                            <option key={option.value} value={option.value}>
                              {option.label}
                            </option>
                          ))}
                        </select>
                      </div>
                      <input
                        className="br-input"
                        style={{ width: "100%", background: "var(--bg-2)", marginTop: 8 }}
                        value={ruleForm.match_value}
                        onChange={(event) => setRuleForm({ ...ruleForm, match_value: event.target.value })}
                        placeholder="Match value"
                      />
                      <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 8 }}>
                        <span style={{ fontSize: 13, color: "var(--text-3)" }}>→ assign to</span>
                        <select
                          className="br-sel"
                          style={{ flex: 1 }}
                          value={ruleForm.category_id}
                          onChange={(event) => setRuleForm({ ...ruleForm, category_id: event.target.value })}
                        >
                          {categories.map((category) => (
                            <option key={category.category_id} value={category.category_id}>
                              {category.name}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div style={{ display: "flex", gap: 8, marginTop: 12, justifyContent: "space-between", alignItems: "center" }}>
                        {ruleForm.mode === "edit" ? (
                          <button
                            type="button"
                            onClick={() => void removeRule()}
                            style={{ border: "1px solid var(--over)", background: "transparent", color: "var(--over)", borderRadius: 8, padding: "7px 12px", font: "500 12px 'Hanken Grotesque', sans-serif", cursor: "pointer" }}
                          >
                            Delete rule
                          </button>
                        ) : (
                          <span />
                        )}
                        <div style={{ display: "flex", gap: 8 }}>
                          <button type="button" style={ghostButton} onClick={closeForm}>
                            Cancel
                          </button>
                          <button type="button" style={accentButton} onClick={() => void submitRule()}>
                            {ruleForm.mode === "edit" ? "Save rule" : "Create rule"}
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                ) : null}
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
