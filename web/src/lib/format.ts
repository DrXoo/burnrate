import type { MatchField, MatchOperator, Transaction } from "../types";

export function currentMonthValue(): string {
  return new Date().toISOString().slice(0, 7);
}

export function currentMonthStart(): string {
  return `${currentMonthValue()}-01`;
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return "Not available";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

export function summarizeApiError(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export function transactionTitle(transaction: Transaction): string {
  return transaction.description || transaction.merchant_name || transaction.counterparty_name || "No description";
}

export function transactionMeta(transaction: Transaction): string {
  return transaction.merchant_name || transaction.counterparty_name || "No merchant/counterparty";
}

export function suggestRuleField(transaction: Transaction): MatchField {
  if (transaction.merchant_name) {
    return "merchant_name";
  }
  if (transaction.description) {
    return "description";
  }
  if (transaction.counterparty_name) {
    return "counterparty_name";
  }
  return "description";
}

export function suggestRuleValue(transaction: Transaction, field: MatchField): string {
  const rawValue = transaction[field];
  return typeof rawValue === "string" ? rawValue.trim() : "";
}

export function prettyMatchField(field: MatchField): string {
  if (field === "merchant_name") {
    return "Merchant name";
  }
  if (field === "counterparty_name") {
    return "Counterparty name";
  }
  return "Description";
}

export function prettyMatchOperator(operator: MatchOperator): string {
  if (operator === "starts_with") {
    return "Starts with";
  }
  if (operator === "ends_with") {
    return "Ends with";
  }
  return operator.charAt(0).toUpperCase() + operator.slice(1);
}

export function amountTone(amount: string, direction: string): "positive" | "negative" {
  return direction === "credit" || Number(amount) > 0 ? "positive" : "negative";
}
