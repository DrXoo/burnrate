import { useMemo, useState, type CSSProperties } from "react";

import { IconSearch, IconSliders } from "../icons";
import { useMediaQuery } from "../../hooks/useMediaQuery";
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

function ruleButtonStyle(active: boolean, muted: boolean): CSSProperties {
  return {
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    alignSelf: "flex-start",
    maxWidth: "100%",
    border: `1px solid ${active ? "var(--accent)" : "var(--line-2)"}`,
    background: muted ? "var(--bg-3)" : "transparent",
    color: active && !muted ? "var(--accent)" : "var(--text-2)",
    borderRadius: 7,
    padding: "3px 8px",
    font: "500 11px 'Hanken Grotesque', sans-serif",
    cursor: "pointer",
  };
}

/** Inline rule editor shared by the desktop table panel and the mobile cards. */
function RuleForm({
  form,
  heading,
  categories,
  onChange,
  onSubmit,
  onDelete,
  onCancel,
}: {
  form: RuleFormState;
  heading: string;
  categories: Category[];
  onChange: (form: RuleFormState) => void;
  onSubmit: () => void;
  onDelete: () => void;
  onCancel: () => void;
}) {
  return (
    <div style={{ background: "var(--bg-2)", border: "1px solid var(--accent)", borderRadius: 11, padding: "13px 14px" }}>
      <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--text-3)", fontWeight: 700, marginBottom: 9 }}>
        {heading}
      </div>
      <input
        className="br-input"
        style={{ width: "100%" }}
        value={form.name}
        onChange={(event) => onChange({ ...form, name: event.target.value })}
        placeholder="Rule name (optional)"
      />
      <div style={{ display: "flex", gap: 6, marginTop: 8, flexWrap: "wrap" }}>
        <select
          className="br-sel"
          style={{ flex: 1, minWidth: 130 }}
          value={form.match_field}
          onChange={(event) => onChange({ ...form, match_field: event.target.value as MatchField })}
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
          value={form.match_operator}
          onChange={(event) => onChange({ ...form, match_operator: event.target.value as MatchOperator })}
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
        style={{ width: "100%", marginTop: 8 }}
        value={form.match_value}
        onChange={(event) => onChange({ ...form, match_value: event.target.value })}
        placeholder="Match value"
      />
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 8 }}>
        <span style={{ fontSize: 13, color: "var(--text-3)" }}>→ assign to</span>
        <select
          className="br-sel"
          style={{ flex: 1 }}
          value={form.category_id}
          onChange={(event) => onChange({ ...form, category_id: event.target.value })}
        >
          {categories.map((category) => (
            <option key={category.category_id} value={category.category_id}>
              {category.name}
            </option>
          ))}
        </select>
      </div>
      <div style={{ display: "flex", gap: 8, marginTop: 12, justifyContent: "space-between", alignItems: "center", flexWrap: "wrap" }}>
        {form.mode === "edit" ? (
          <button
            type="button"
            onClick={onDelete}
            style={{ border: "1px solid var(--over)", background: "transparent", color: "var(--over)", borderRadius: 8, padding: "7px 12px", font: "500 12px 'Hanken Grotesque', sans-serif", cursor: "pointer" }}
          >
            Delete rule
          </button>
        ) : (
          <span />
        )}
        <div style={{ display: "flex", gap: 8 }}>
          <button type="button" style={ghostButton} onClick={onCancel}>
            Cancel
          </button>
          <button type="button" style={accentButton} onClick={onSubmit}>
            {form.mode === "edit" ? "Save rule" : "Create rule"}
          </button>
        </div>
      </div>
    </div>
  );
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
  const isMobile = useMediaQuery("(max-width: 720px)");
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
  const activeTransaction = ruleTxnId ? items.find((transaction) => transaction.transaction_id === ruleTxnId) ?? null : null;

  function ruleAffordance(transaction: Transaction, fullWidth: boolean) {
    const matchedRule = transaction.matched_rule_id ? rulesById.get(transaction.matched_rule_id) : undefined;
    const isActive = ruleTxnId === transaction.transaction_id;
    if (matchedRule) {
      return (
        <button
          type="button"
          title="Edit the rule that categorized this transaction"
          onClick={() => openEdit(transaction, matchedRule)}
          style={{ ...ruleButtonStyle(isActive, true), width: fullWidth ? "100%" : undefined, justifyContent: fullWidth ? "center" : undefined }}
        >
          <IconSliders size={12} />
          <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>Rule: {matchedRule.name || "attached"}</span>
        </button>
      );
    }
    return (
      <button
        type="button"
        title="Create a categorization rule from this transaction"
        onClick={() => openCreate(transaction)}
        disabled={categories.length === 0}
        style={{
          ...ruleButtonStyle(isActive, false),
          width: fullWidth ? "100%" : undefined,
          justifyContent: fullWidth ? "center" : undefined,
          cursor: categories.length === 0 ? "not-allowed" : "pointer",
          opacity: categories.length === 0 ? 0.5 : 1,
        }}
      >
        <IconSliders size={12} />
        Create rule
      </button>
    );
  }

  function categorySelect(transaction: Transaction, fullWidth: boolean) {
    return (
      <select
        className="br-sel"
        style={{ maxWidth: "100%", width: fullWidth ? "100%" : undefined, borderColor: transaction.category_id ? "var(--line-2)" : "var(--watch)" }}
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
    );
  }

  const heading =
    activeTransaction && ruleForm
      ? ruleForm.mode === "edit"
        ? "Edit rule"
        : `New rule from “${transactionTitle(activeTransaction)}”`
      : "";

  const stateMessage = error
    ? { text: error, color: "var(--over)" }
    : loading && items.length === 0
      ? { text: "Loading transactions…", color: "var(--text-3)" }
      : visible.length === 0
        ? { text: "No transactions match these filters.", color: "var(--text-3)" }
        : null;

  return (
    <div>
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center", marginBottom: 16 }}>
        <div style={{ position: "relative", flex: 1, minWidth: 180 }}>
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

      {isMobile ? (
        /* ---------- MOBILE: stacked cards ---------- */
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {stateMessage ? (
            <div style={{ padding: "28px 16px", textAlign: "center", color: stateMessage.color, fontSize: 13, background: "var(--bg-2)", border: "1px solid var(--line)", borderRadius: 12 }}>
              {stateMessage.text}
            </div>
          ) : (
            visible.map((transaction) => {
              const positive = amountTone(transaction.amount, transaction.direction) === "positive";
              const isActive = ruleTxnId === transaction.transaction_id;
              return (
                <div
                  key={transaction.transaction_id}
                  style={{
                    background: "var(--bg-2)",
                    border: `1px solid ${isActive ? "var(--accent)" : "var(--line)"}`,
                    borderRadius: 12,
                    padding: 14,
                    boxShadow: "var(--card-shadow)",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 14, fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {transactionTitle(transaction)}
                      </div>
                      <div className="num" style={{ fontSize: 11.5, color: "var(--text-3)", marginTop: 2, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {shortDate(transaction.booking_date || transaction.value_date)} · {shortAccount(transaction.account_display_name)}
                      </div>
                    </div>
                    <div className="num" style={{ fontSize: 15, fontWeight: 600, color: positive ? "var(--good)" : "var(--text)", flex: "none" }}>
                      {eur(transaction.amount)}
                    </div>
                  </div>
                  <div style={{ marginTop: 11 }}>{categorySelect(transaction, true)}</div>
                  <div style={{ marginTop: 8 }}>{ruleAffordance(transaction, true)}</div>
                  {isActive && ruleForm ? (
                    <div style={{ marginTop: 11 }}>
                      <RuleForm
                        form={ruleForm}
                        heading={heading}
                        categories={categories}
                        onChange={setRuleForm}
                        onSubmit={() => void submitRule()}
                        onDelete={() => void removeRule()}
                        onCancel={closeForm}
                      />
                    </div>
                  ) : null}
                </div>
              );
            })
          )}

          <PagerFooter visible={visible.length} total={total} monthLabel={monthLabel} paging={paging} onMovePage={onMovePage} bordered />
        </div>
      ) : (
        /* ---------- DESKTOP: table ---------- */
        <div style={{ background: "var(--bg-2)", border: "1px solid var(--line)", borderRadius: 14, overflow: "hidden", boxShadow: "var(--card-shadow)" }}>
          <div className="br-hscroll">
            <div className="br-hmin">
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

              {stateMessage ? (
                <div style={{ padding: "28px 18px", textAlign: "center", color: stateMessage.color, fontSize: 13 }}>{stateMessage.text}</div>
              ) : (
                visible.map((transaction) => {
                  const positive = amountTone(transaction.amount, transaction.direction) === "positive";
                  const isActive = ruleTxnId === transaction.transaction_id;
                  return (
                    <div
                      key={transaction.transaction_id}
                      style={{
                        display: "grid",
                        gridTemplateColumns: GRID,
                        gap: 12,
                        padding: "12px 18px",
                        borderBottom: "1px solid var(--line)",
                        alignItems: "start",
                        background: isActive ? "var(--bg-3)" : undefined,
                      }}
                    >
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
                        {categorySelect(transaction, false)}
                        {ruleAffordance(transaction, false)}
                      </div>
                      <div className="num" style={{ textAlign: "right", fontSize: 14, fontWeight: 600, color: positive ? "var(--good)" : "var(--text)", paddingTop: 6 }}>
                        {eur(transaction.amount)}
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>

          {activeTransaction && ruleForm ? (
            <div style={{ padding: "14px 18px", borderBottom: "1px solid var(--line)", background: "var(--bg-3)" }}>
              <div style={{ maxWidth: 560 }}>
                <RuleForm
                  form={ruleForm}
                  heading={heading}
                  categories={categories}
                  onChange={setRuleForm}
                  onSubmit={() => void submitRule()}
                  onDelete={() => void removeRule()}
                  onCancel={closeForm}
                />
              </div>
            </div>
          ) : null}

          <PagerFooter visible={visible.length} total={total} monthLabel={monthLabel} paging={paging} onMovePage={onMovePage} />
        </div>
      )}
    </div>
  );
}

function PagerFooter({
  visible,
  total,
  monthLabel,
  paging,
  onMovePage,
  bordered = false,
}: {
  visible: number;
  total: number;
  monthLabel: string;
  paging: PagingState;
  onMovePage: (direction: "prev" | "next") => void;
  bordered?: boolean;
}) {
  const atStart = paging.offset === 0;
  const atEnd = paging.offset + paging.limit >= total;
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: bordered ? "12px 14px" : "12px 18px",
        fontSize: 12.5,
        color: "var(--text-3)",
        flexWrap: "wrap",
        gap: 8,
        ...(bordered ? { background: "var(--bg-2)", border: "1px solid var(--line)", borderRadius: 12 } : {}),
      }}
    >
      <span>
        Showing <span className="num">{visible}</span> of <span className="num">{total}</span> for {monthLabel}
      </span>
      <div style={{ display: "flex", gap: 6 }}>
        <button
          type="button"
          onClick={() => onMovePage("prev")}
          disabled={atStart}
          style={{ ...pagerButton, color: atStart ? "var(--text-3)" : "var(--text)", cursor: atStart ? "default" : "pointer" }}
        >
          Prev
        </button>
        <button
          type="button"
          onClick={() => onMovePage("next")}
          disabled={atEnd}
          style={{ ...pagerButton, color: atEnd ? "var(--text-3)" : "var(--text)", cursor: atEnd ? "default" : "pointer" }}
        >
          Next
        </button>
      </div>
    </div>
  );
}
