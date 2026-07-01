import type { MatchField, MatchOperator, RunwayStatus, Transaction } from "../types";

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

/** Title-cases a raw enum value ("not_available" -> "Not Available", "booked" -> "Booked"). */
export function prettyLabel(value: string): string {
  return value
    .split(/[_\s]+/)
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(" ");
}

export const CURRENCY_OPTIONS = ["EUR", "USD", "GBP", "CHF", "SEK", "NOK", "DKK", "PLN"];

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

export function formatMoney(amount: string, currency: string | null | undefined): string {
  const numericAmount = Number(amount);
  if (!Number.isFinite(numericAmount)) {
    return currency ? `${amount} ${currency}` : amount;
  }

  if (currency) {
    try {
      return new Intl.NumberFormat(undefined, {
        style: "currency",
        currency,
        maximumFractionDigits: 2,
      }).format(numericAmount);
    } catch (_error) {
      return `${amount} ${currency}`;
    }
  }

  return new Intl.NumberFormat(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(numericAmount);
}

export function formatMonthLabel(value: string): string {
  const date = new Date(`${value}-01T00:00:00`);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleDateString(undefined, {
    month: "long",
    year: "numeric",
  });
}

export function formatRunwayMonths(value: string | null, status: RunwayStatus): string {
  if (status === "not_available") {
    return "Not configured";
  }
  if (status === "stable" && !value) {
    return "On track";
  }
  if (!value) {
    return "At risk";
  }

  const numericValue = Number(value);
  if (!Number.isFinite(numericValue)) {
    return `${value} mo`;
  }
  return `${numericValue.toFixed(1)} mo`;
}
