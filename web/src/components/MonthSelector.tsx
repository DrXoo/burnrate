import { IconChevronLeft, IconChevronRight } from "./icons";
import { shiftMonth } from "../lib/format";

interface MonthSelectorProps {
  /** `YYYY-MM`, or "" while the backend has not yet said which month is current. */
  month: string;
  /** Hands back the month to look at. "" means the month the backend calls current. */
  onSelectMonth: (month: string) => void;
}

const stepStyle = {
  flex: "none",
  width: 28,
  height: 28,
  borderRadius: 7,
  border: "1px solid var(--line)",
  background: "var(--bg-3)",
  color: "var(--text-2)",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
} as const;

/** Moves the owner between months. Unbounded in both directions on purpose: a future
    month is worth visiting, because that is where standing orders land, and bounding
    the past would need an API for the earliest month that has data. The arrows cover
    the common step and the native input covers the long jump.

    It computes nothing beyond which month is next: every figure for the month it
    selects comes from the backend. */
export function MonthSelector({ month, onSelectMonth }: MonthSelectorProps) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <button
        type="button"
        title="Previous month"
        aria-label="Previous month"
        disabled={!month}
        onClick={() => onSelectMonth(shiftMonth(month, -1))}
        style={{ ...stepStyle, cursor: month ? "pointer" : "default", opacity: month ? 1 : 0.5 }}
      >
        <IconChevronLeft />
      </button>

      <input
        type="month"
        className="br-month"
        aria-label="Month"
        value={month}
        onChange={(event) => onSelectMonth(event.target.value)}
      />

      <button
        type="button"
        title="Next month"
        aria-label="Next month"
        disabled={!month}
        onClick={() => onSelectMonth(shiftMonth(month, 1))}
        style={{ ...stepStyle, cursor: month ? "pointer" : "default", opacity: month ? 1 : 0.5 }}
      >
        <IconChevronRight />
      </button>
    </div>
  );
}
