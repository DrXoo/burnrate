import type {
  BudgetUsageStatus,
  CategoryType,
  Connection,
  MatchField,
  MatchOperator,
  Transaction,
} from "../types";

/** Design status buckets used for category/budget coloring. */
export type Tone = "good" | "watch" | "over" | "neutral";

export const TONE_COLOR: Record<Tone, string> = {
  good: "var(--good)",
  watch: "var(--watch)",
  over: "var(--over)",
  neutral: "var(--text-2)",
};

export const TONE_DIM: Record<Tone, string> = {
  good: "var(--good-dim)",
  watch: "var(--watch-dim)",
  over: "var(--over-dim)",
  neutral: "var(--bg-4)",
};

export const TONE_LABEL: Record<Tone, string> = {
  good: "On track",
  watch: "Watch",
  over: "Over budget",
  neutral: "Neutral",
};

/** Map the backend budget-usage status to a design tone. */
export function usageTone(status: BudgetUsageStatus): Tone {
  if (status === "over") {
    return "over";
  }
  if (status === "watch") {
    return "watch";
  }
  return "good";
}

/** Category swatch color: expenses take their budget tone, income is positive, transfers are muted. */
export function categoryColor(type: CategoryType, tone: Tone): string {
  if (type === "income") {
    return "var(--good)";
  }
  if (type === "transfer") {
    return "var(--text-2)";
  }
  return TONE_COLOR[tone];
}

function toNumber(value: number | string): number {
  return typeof value === "string" ? Number(value) : value;
}

/** Signed euro amount with 2 decimals and the design's unicode minus (−€1,234.50 / €1,234.50). */
export function eur(value: number | string): string {
  const numeric = toNumber(value);
  if (!Number.isFinite(numeric)) {
    return String(value);
  }
  const body = Math.abs(numeric).toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return (numeric < 0 ? "−€" : "€") + body;
}

/** Unsigned euro amount with 2 decimals (€1,234.50) for budgeted figures. */
export function eurPlain(value: number | string): string {
  const numeric = toNumber(value);
  if (!Number.isFinite(numeric)) {
    return String(value);
  }
  return (
    "€" +
    numeric.toLocaleString("en-US", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })
  );
}

/** A bank connection needs re-authorizing if it's inactive or its consent is lapsing/lapsed. */
export function needsReconnect(connection: Connection): boolean {
  return (
    !connection.active ||
    connection.expiry_status === "expired" ||
    connection.expiry_status === "expiring_soon"
  );
}

/** Consent-expiry badge for a connection, or null when there's nothing to flag. */
export function expiryBadge(connection: Connection): { text: string; tone: Tone } | null {
  if (connection.expiry_status === "expired") {
    return { text: "Access expired", tone: "over" };
  }
  if (connection.expiry_status === "expiring_soon") {
    const days = connection.days_until_expiry;
    const when = days == null ? "soon" : days <= 0 ? "today" : `in ${days} day${days === 1 ? "" : "s"}`;
    return { text: `Expires ${when}`, tone: "watch" };
  }
  return null;
}

/** Compact relative time ("8 min ago") for last-sync labels. */
export function timeAgo(iso: string | null | undefined): string {
  if (!iso) {
    return "never";
  }
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) {
    return "unknown";
  }
  const seconds = Math.max(0, (Date.now() - then) / 1000);
  if (seconds < 60) {
    return "just now";
  }
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) {
    return `${minutes} min ago`;
  }
  const hours = Math.floor(minutes / 60);
  if (hours < 24) {
    return `${hours} h ago`;
  }
  const days = Math.floor(hours / 24);
  return `${days} d ago`;
}

/** Short account label ("Checking ···4021" → "Chk ···4021"). */
export function shortAccount(name: string): string {
  return name
    .replace("Checking ···", "Chk ···")
    .replace("Credit ···", "Cr ···")
    .replace("Savings ···", "Sav ···");
}

/** Capitalize a lowercase word ("expense" → "Expense"). */
export function capitalize(value: string): string {
  return value ? value.charAt(0).toUpperCase() + value.slice(1) : value;
}

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

