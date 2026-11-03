import type { BaselineComparisonStatus } from "../types";

import type {
  BudgetUsageStatus,
  CategoryType,
  Connection,
  MatchField,
  MatchOperator,
  SafeToSpendStatus,
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

/** Map the allowance's status to a design tone.

    A status-to-colour lookup, not a rule: the band behind on_track/watch/over is the
    backend's, and the three statuses with no allowance to report carry no verdict, so
    they read neutral rather than borrowing a colour they have not earned. */
export function safeToSpendTone(status: SafeToSpendStatus): Tone {
  if (status === "no_budget" || status === "month_closed" || status === "month_not_started") {
    return "neutral";
  }
  return usageTone(status);
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

/** The month `delta` months away from a `YYYY-MM` value, rolling over the year.
 *
 *  Navigation, not a clock: which month the owner is in is the backend's answer, and
 *  stepping away from it is plain calendar arithmetic on the month they are looking at.
 *  An unparseable value is returned unchanged, which is what an unresolved month is. */
export function shiftMonth(value: string, delta: number): string {
  const match = /^(\d{4})-(\d{2})$/.exec(value);
  if (!match) {
    return value;
  }
  const monthsFromYearZero = Number(match[1]) * 12 + (Number(match[2]) - 1) + delta;
  const year = Math.floor(monthsFromYearZero / 12);
  const month = monthsFromYearZero - year * 12 + 1;
  return `${String(year).padStart(4, "0")}-${String(month).padStart(2, "0")}`;
}

const SHORT_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** A plain `YYYY-MM-DD` as `12 Oct`.
 *
 *  Spelled out rather than locale-formatted: this reads inside a sentence about one
 *  budget, so it has to be the same words wherever the owner opens the page. */
export function dayAndMonth(value: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) {
    return value;
  }
  return `${Number(match[3])} ${SHORT_MONTHS[Number(match[2]) - 1]}`;
}

/** Whether `month` is the last month a budget covers.
 *
 *  Worth saying, because a row on its final month otherwise reads exactly like a
 *  running one and invites the owner to cancel what is already cancelled. An
 *  `active_to` in a later month has months still ahead of it from here, so it is left
 *  unsaid.
 *
 *  The day is not reported, because it carries nothing: both edges of a window sit on
 *  month boundaries, so a window that closes in this month always closes on its last
 *  day. Naming a date here read as a mid-month stop, which the rule cannot write and
 *  migration 0008 erased from the rows that had one. */
export function finalMonthFor(activeTo: string | null, month: string | undefined): string | null {
  if (!activeTo || !month || activeTo.slice(0, 7) !== month) {
    return null;
  }
  return "Final month";
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

/** The owner-facing message for a bank whose daily allowance is used up, or null when
    this is some other failure.

    The wording comes from the backend and is not written here. A client that composed
    it would be deciding what the state means and, worse, guessing when syncing
    resumes -- which the backend deliberately does not promise, because banks differ on
    whether the window rolls or resets at midnight.

    Matched on `detail.code` rather than on the status: 503 is also what the backend
    answers when no password is configured, and 429 is its own click limiter on the
    very same endpoint. Duck-typed rather than `instanceof ApiError` so the error can
    cross a module mock. */
export function bankRateLimitMessage(error: unknown): string | null {
  const detail = (error as { detail?: { code?: unknown; message?: unknown } } | null | undefined)?.detail;
  if (!detail || detail.code !== "bank_rate_limit") {
    return null;
  }
  return typeof detail.message === "string" ? detail.message : null;
}

/** The hour the next unattended sync is due, as `21:00`, or null when there is none.

    Read straight out of the backend's offset-bearing instant rather than through
    `Date`, on purpose: converting would re-render it in whatever zone the browser
    happens to sit in, and the hour that matters is the one configured in `SYNC_CRON`
    on the owner's own clock. A browser an hour away would otherwise be shown a time
    nobody ever set.

    Callers must show this only beside a healthy connection. It says what the schedule
    intends, and a worker that is not running cannot contradict it -- printing a
    confident hour during an outage is worse than printing nothing. See ADR-0013. */
export function nextSyncLabel(instant: string | null | undefined): string | null {
  if (!instant) {
    return null;
  }
  const hourAndMinute = /T(\d{2}:\d{2})/.exec(instant);
  return hourAndMinute ? hourAndMinute[1] : null;
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



/** The figure to print beside a comparison, or null when there is none to print.
 *
 * Read off the band and never off the amount, which is the trap this exists to
 * close: a baseline of zero or less is one the backend refuses to divide by, so it
 * publishes `no_baseline` with "0.00" still sitting in the amount. "0.00" is a
 * truthy string, so every card that guarded on the amount printed "normally €0.00 ·
 * no baseline yet" -- a figure and a denial of it in one breath. A salary dated the
 * 28th read on the 26th is all it takes, and a category can reach it too, with two
 * months whose movements cancel out.
 *
 * Stated once because three cards ask it: monthly income, comparable spending, and
 * each category row.
 */
export function baselineFigure(comparison: {
  baseline_amount: string | null;
  comparison_status: BaselineComparisonStatus;
}): string | null {
  if (comparison.comparison_status === "no_baseline") {
    return null;
  }
  return comparison.baseline_amount;
}

/** The phrase the owner reads beside a figure compared against its own normal.
 *
 * The bands are the backend's; this picks words for them. The magnitude is rounded
 * to a whole percent because the owner is deciding whether to care, not auditing.
 *
 * Only `anomalous` is worded as a warning. Being well under a baseline is reported
 * in full and flagged as nothing: the product exists to stop the owner overspending,
 * and in their own October every ordinary category sits below its baseline while one
 * one-off swamps the month.
 */
export function comparisonPhrase(comparison: {
  deviation_percent: number | null;
  comparison_status: BaselineComparisonStatus;
}): string {
  const deviation = comparison.deviation_percent;
  const magnitude = deviation == null ? "" : `${Math.abs(Math.round(deviation))}%`;
  switch (comparison.comparison_status) {
    case "no_baseline":
      return "no baseline yet";
    case "in_line":
      return "in line with usual";
    case "below":
      return `${magnitude} below usual`;
    case "above":
      return `${magnitude} above usual`;
    case "anomalous":
      return `unusually high · ${magnitude} above usual`;
  }
}
