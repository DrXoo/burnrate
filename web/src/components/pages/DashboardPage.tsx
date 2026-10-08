import { useMemo, type CSSProperties, type ReactNode } from "react";

import {
  TONE_COLOR,
  TONE_DIM,
  TONE_LABEL,
  eur,
  eurPlain,
  formatMonthLabel,
  safeToSpendTone,
  usageTone,
} from "../../lib/format";
import type { Tone } from "../../lib/format";
import type { HeroMode } from "../../lib/viewTypes";
import type { SafeToSpendStatus, SummaryDashboard } from "../../types";

interface DashboardPageProps {
  summary: SummaryDashboard | null;
  loading: boolean;
  error: string | null;
  heroMode: HeroMode;
  includedAccountCount: number;
}

const GAUGE_RADIUS = 84;
const GAUGE_CIRCUMFERENCE = 2 * Math.PI * GAUGE_RADIUS; // 527.79
const GAUGE_ARC = 0.75 * GAUGE_CIRCUMFERENCE; // 395.84 — the visible 270° sweep

const cardBase: CSSProperties = {
  background: "var(--bg-2)",
  border: "1px solid var(--line)",
  borderRadius: 14,
  padding: "16px 17px",
  boxShadow: "var(--card-shadow)",
};

function num(value: string | null | undefined): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function clampFraction(value: number): number {
  if (!Number.isFinite(value) || value < 0) {
    return 0;
  }
  return Math.min(1, value);
}

const ALLOWANCE_BADGE: Record<"on_track" | "watch" | "over", string> = {
  on_track: "On track",
  watch: "Watch",
  over: "Over plan",
};

interface Coach {
  title: string;
  body: string;
}

/** What a banded allowance means, in words. Keyed off the backend's verdict, so the
    dashboard and the bot cannot disagree about how the month is going. */
const ALLOWANCE_COACH: Record<"on_track" | "watch" | "over", Coach> = {
  on_track: {
    title: "On plan for this point in the month",
    body: "Your variable budgets have about as much left as the plan expects by now. Today's number is what you can spend without putting the rest of the month out of reach.",
  },
  watch: {
    title: "Spending ahead of plan",
    body: "Less is left of your variable budgets than the plan expects by now. Today's number already reflects it — staying under it brings the month back.",
  },
  over: {
    title: "Well past the plan for this point in the month",
    body: "Much less is left of your variable budgets than the plan expects by now. Today's number spreads what little remains over the days still to come.",
  },
};

/**
 * Hero model: the month's verdict, dressed for the gauge and the bar.
 *
 * No threshold and no money arithmetic live here. The tone is read off
 * safe_to_spend_status, and the only numbers this computes are fractions that
 * become an arc length or a bar width -- never a figure the owner reads.
 */
function useHeroModel(summary: SummaryDashboard) {
  return useMemo(() => {
    const budget = num(summary.monthly_budget_amount);
    const tone = safeToSpendTone(summary.safe_to_spend_status);

    const spentFrac = budget > 0 ? clampFraction(num(summary.budgeted_spending_amount) / budget) : 0;
    const projFrac = budget > 0 ? clampFraction(num(summary.projected_month_end_spend_amount) / budget) : 0;
    const dayFrac = summary.days_in_month > 0 ? clampFraction(summary.days_elapsed / summary.days_in_month) : 0;

    return {
      tone,
      statusColor: TONE_COLOR[tone],
      budget,
      spentFrac,
      projFrac,
      dayFrac,
      spentPct: `${(spentFrac * 100).toFixed(1)}%`,
      projPct: `${(projFrac * 100).toFixed(1)}%`,
      dayPct: `${(dayFrac * 100).toFixed(1)}%`,
    };
  }, [summary]);
}

interface Headline {
  eyebrow: string;
  value: string;
  /** A figure gets the full 52px; prose gets a size it can wrap at. */
  isFigure: boolean;
  badge: string;
  /** Standalone line under the balance. It cannot continue a sentence from the
      figure above it, because the balance line comes between the two. */
  note: string | null;
  coach: Coach;
}

/** The headline slot: the allowance, or why there is no allowance to show. */
function useHeadline(summary: SummaryDashboard): Headline {
  return useMemo(() => {
    if (summary.safe_to_spend_status === "no_budget") {
      return {
        eyebrow: "Safe to spend today",
        value: "Set a budget",
        isFigure: false,
        badge: "No budget",
        note: "Add a monthly budget under Rules & Budgets and this becomes your daily number.",
        coach: {
          title: "No variable budget to spend from",
          body: 'A daily allowance needs a monthly budget to draw on. Add one under Rules & Budgets and the headline starts answering "can I spend this?".',
        },
      };
    }

    if (
      summary.safe_to_spend_status === "month_closed" ||
      summary.safe_to_spend_status === "month_not_started"
    ) {
      // That month's outcome against plan is the money-left figure the gauge already
      // shows -- the slot borrows it rather than deriving anything new. Only the
      // wording changes, so a finished month reads as achieved and a future one as
      // planned.
      const monthName = formatMonthLabel(summary.month);
      const budgeted = eurPlain(summary.monthly_budget_amount);
      const unavailable = "A daily allowance only means something inside the month you are in.";
      // What a month that has not started has already had filed in it. A standing
      // order arrives as a hold carrying a future value date, so a month can hold
      // committed spend before it begins. Read off the payload rather than asserted
      // from the branch, which is what printed "Nothing is spent yet" above a figure
      // already reduced by a scheduled payment.
      //
      // The month's whole spend, not its budgeted slice: a charge in a category with no
      // budget leaves the figure above untouched, but it still arrives as a disclosure
      // a few pixels to the right, and "nothing is spent" beside an "unbudgeted" chip
      // is the same contradiction in a quieter form. So the sentence does not claim the
      // spend came out of the budget either.
      const committed = num(summary.monthly_spending_amount);
      const spendNote =
        committed > 0
          ? `${eurPlain(summary.monthly_spending_amount)} is already committed.`
          : "Nothing is spent yet.";
      // A month the owner never budgeted for has no plan to be judged against, so the
      // note says that instead of quoting a zero as if it were the plan. Reachable
      // because tense now outranks no_budget: before, such a month was captioned with
      // the set-a-budget invitation, which is the defect this replaced.
      const hadNoBudget = num(summary.monthly_budget_amount) <= 0;
      return summary.safe_to_spend_status === "month_closed"
        ? {
            eyebrow: `${monthName} · against plan`,
            value: eur(summary.money_left_amount),
            isFigure: true,
            badge: "Month closed",
            note: hadNoBudget
              ? `${monthName} closed with no budget set, so there is no plan to compare it against.`
              : `What ${monthName} finished with, of the ${budgeted} it had budgeted.`,
            coach: {
              title: `${monthName} is closed`,
              body: `${unavailable} The headline shows how that month finished against its budget instead.`,
            },
          }
        : {
            eyebrow: `${monthName} · planned`,
            value: eur(summary.money_left_amount),
            isFigure: true,
            badge: "Not started yet",
            note: hadNoBudget
              ? `${monthName} has no budget set yet. ${spendNote}`
              : `What ${monthName} plans to have left of the ${budgeted} budgeted. ${spendNote}`,
            coach: {
              title: `${monthName} has not started`,
              body: `${unavailable} The headline shows what that month plans, not what it achieved.`,
            },
          };
    }

    // The domain pairs a null amount with exactly the two statuses above. Restated
    // here because nothing in the type system ties the two fields together, so this
    // is what turns a change to that pairing into a visible state rather than a
    // crash on the headline.
    if (summary.safe_to_spend_today_amount == null) {
      return {
        eyebrow: "Safe to spend today",
        value: "Not available",
        isFigure: false,
        badge: "Unavailable",
        note: "The backend reported a status but no amount.",
        coach: {
          title: "No allowance to show",
          body: "The month has a status but no amount to go with it. Nothing is wrong with your data; the dashboard simply has nothing to print here.",
        },
      };
    }

    return {
      eyebrow: "Safe to spend today",
      value: eur(summary.safe_to_spend_today_amount),
      isFigure: true,
      // "Over plan", not TONE_LABEL's "Over budget": the allowance is banded against
      // On-Plan Remaining, so the budget total is not what it has overshot.
      badge: ALLOWANCE_BADGE[summary.safe_to_spend_status],
      note: null,
      coach: ALLOWANCE_COACH[summary.safe_to_spend_status],
    };
  }, [summary]);
}

interface Disclosure {
  amount: string;
  label: string;
  title: string;
}

/**
 * What the headline does not account for, shown beside it when there is any.
 *
 * Each is a backend figure printed as it arrives; the only test applied is whether
 * there is anything to disclose.
 */
function useDisclosures(summary: SummaryDashboard): Disclosure[] {
  return useMemo(
    () =>
      [
        {
          amount: summary.unbudgeted_spending_amount,
          label: "unbudgeted",
          title:
            "Spent this month in expense categories with no active budget. The allowance is on a budgeted basis, so it does not count this — hence showing it here.",
        },
        {
          amount: summary.pending_spend_amount,
          label: "pending",
          title:
            "Authorized by the bank but not yet settled. Already deducted from the allowance, so the number does not invite you to spend the same money twice.",
        },
        {
          amount: summary.fixed_overrun_amount,
          label: "fixed overrun",
          title:
            "Fixed commitments that came in above their estimate. Money already gone, so it comes out of the allowance.",
        },
      ].filter((disclosure) => num(disclosure.amount) > 0),
    [summary],
  );
}

/** Savings model: the backend's share-of-income verdict, dressed for the gauge. */
function useSavingsModel(summary: SummaryDashboard) {
  return useMemo(() => {
    // Net cash flow is what the owner kept, and the rate and its band are the
    // backend's call -- the page neither recomputes them nor sets a threshold of
    // its own, so the dashboard and the bot cannot disagree.
    const saved = num(summary.net_cash_flow_amount);
    const tone = usageTone(summary.savings_status);

    return {
      income: num(summary.monthly_income_amount),
      spending: num(summary.monthly_spending_amount),
      saved,
      // Percent to arc length: presentation, not policy.
      savedFrac: clampFraction(summary.savings_rate_percent / 100),
      tone,
      statusColor: TONE_COLOR[tone],
      // One decimal, because the backend bands on exactly this rounded figure: print
      // fewer and a 9.8% month would read "10%" while still coloured as a warning.
      ratePct: `${summary.savings_rate_percent.toFixed(1)}%`,
    };
  }, [summary]);
}

function StatusBadge({ tone, label }: { tone: Tone; label: string }) {
  return (
    <div
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 7,
        padding: "5px 11px",
        borderRadius: 99,
        background: TONE_DIM[tone],
        color: TONE_COLOR[tone],
        fontSize: 12.5,
        fontWeight: 600,
        whiteSpace: "nowrap",
      }}
    >
      <span style={{ width: 7, height: 7, borderRadius: "50%", background: TONE_COLOR[tone] }} />
      {label}
    </div>
  );
}

function DisclosureChip({ amount, label, title }: Disclosure) {
  return (
    <div
      title={title}
      style={{
        display: "inline-flex",
        alignItems: "baseline",
        gap: 5,
        padding: "3px 9px",
        borderRadius: 7,
        background: "var(--bg-4)",
        border: "1px solid var(--line-2)",
        fontSize: 11.5,
        color: "var(--text-2)",
        whiteSpace: "nowrap",
        cursor: "help",
      }}
    >
      <span className="num" style={{ fontWeight: 600, color: "var(--text)" }}>
        {eurPlain(amount)}
      </span>
      {label}
    </div>
  );
}

interface GaugeProps {
  fillFraction: number;
  color: string;
  label: string;
  centerText: string;
  subtitle: string;
  footLeft: string;
  footRight: string;
  /** Optional projection tick, as a 0–1 fraction of the 270° sweep. */
  needleFraction?: number;
  size?: number;
}

function Gauge({ fillFraction, color, label, centerText, subtitle, footLeft, footRight, needleFraction, size = 210 }: GaugeProps) {
  const height = size * 0.8;
  const valueDash = `${(clampFraction(fillFraction) * GAUGE_ARC).toFixed(1)} ${GAUGE_CIRCUMFERENCE.toFixed(2)}`;
  // Center number has to fit inside the ring's inner opening (~0.56 of the box).
  const innerWidth = size * 0.56;
  const centerFont = Math.max(19, Math.min(36, Math.floor(innerWidth / (centerText.length * 0.62))));
  return (
    <div style={{ position: "relative", width: size, height }}>
      <svg width={size} height={height} viewBox="0 0 220 200" style={{ overflow: "visible" }}>
        <g transform="rotate(135 110 110)">
          <circle
            cx="110"
            cy="110"
            r={GAUGE_RADIUS}
            fill="none"
            stroke="var(--bg-4)"
            strokeWidth="16"
            strokeLinecap="round"
            strokeDasharray={`${GAUGE_ARC.toFixed(2)} ${GAUGE_CIRCUMFERENCE.toFixed(2)}`}
          />
          <circle
            cx="110"
            cy="110"
            r={GAUGE_RADIUS}
            fill="none"
            stroke={color}
            strokeWidth="16"
            strokeLinecap="round"
            strokeDasharray={valueDash}
            style={{ filter: "blur(9px)", opacity: 0.55 }}
          />
          <circle
            cx="110"
            cy="110"
            r={GAUGE_RADIUS}
            fill="none"
            stroke={color}
            strokeWidth="16"
            strokeLinecap="round"
            strokeDasharray={valueDash}
          />
          {needleFraction != null ? (
            <line
              x1="176"
              y1="110"
              x2="196"
              y2="110"
              stroke="var(--text)"
              strokeWidth="2.5"
              strokeLinecap="round"
              transform={`rotate(${(clampFraction(needleFraction) * 270).toFixed(1)} 110 110)`}
            />
          ) : null}
        </g>
      </svg>
      <div style={{ position: "absolute", top: "35%", left: 0, right: 0, textAlign: "center" }}>
        <div
          style={{
            fontSize: 11,
            textTransform: "uppercase",
            letterSpacing: "0.08em",
            color: "var(--text-3)",
            fontWeight: 600,
          }}
        >
          {label}
        </div>
        <div className="num" style={{ fontSize: centerFont, fontWeight: 600, lineHeight: 1.05, marginTop: 2, whiteSpace: "nowrap" }}>
          {centerText}
        </div>
        <div style={{ fontSize: 11.5, color: "var(--text-3)" }}>{subtitle}</div>
      </div>
      <div
        style={{
          position: "absolute",
          bottom: "2%",
          left: 0,
          right: 0,
          display: "flex",
          justifyContent: "space-between",
          fontSize: 11,
          color: "var(--text-3)",
          padding: "0 8px",
        }}
      >
        <span>{footLeft}</span>
        <span className="num">{footRight}</span>
      </div>
    </div>
  );
}

interface MeterBarProps {
  label: string;
  value: string;
  subtitle: ReactNode;
  fillPct: string;
  color: string;
  markers?: { pct: string; color: string; title: string }[];
  footLeft: ReactNode;
  footRight: ReactNode;
}

function MeterBar({ label, value, subtitle, fillPct, color, markers = [], footLeft, footRight }: MeterBarProps) {
  return (
    <div>
      <div
        style={{
          fontSize: 11.5,
          textTransform: "uppercase",
          letterSpacing: "0.08em",
          color: "var(--text-3)",
          fontWeight: 600,
        }}
      >
        {label}
      </div>
      <div className="num" style={{ fontSize: 34, fontWeight: 600, lineHeight: 1, margin: "4px 0 2px" }}>
        {value}
      </div>
      <div style={{ fontSize: 12.5, color: "var(--text-2)", marginBottom: 14 }}>{subtitle}</div>
      <div style={{ position: "relative", height: 14, background: "var(--bg-4)", borderRadius: 7, overflow: "visible" }}>
        <div
          style={{
            position: "absolute",
            inset: 0,
            width: fillPct,
            background: color,
            borderRadius: 7,
            boxShadow: `0 0 14px color-mix(in oklab, ${color} 55%, transparent)`,
          }}
        />
        {markers.map((marker, index) => (
          <div
            key={index}
            style={{ position: "absolute", top: -4, bottom: -4, left: marker.pct, width: 2, background: marker.color }}
            title={marker.title}
          />
        ))}
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", marginTop: 8, fontSize: 11.5, color: "var(--text-3)" }}>
        <span>{footLeft}</span>
        <span>{footRight}</span>
      </div>
    </div>
  );
}

function MetricCard({ label, value, sub }: { label: string; value: string; sub: ReactNode }) {
  return (
    <div style={cardBase}>
      <div style={{ fontSize: 12, color: "var(--text-3)", fontWeight: 600, marginBottom: 7 }}>{label}</div>
      <div className="num" style={{ fontSize: 26, fontWeight: 600 }}>
        {value}
      </div>
      <div style={{ fontSize: 11.5, color: "var(--text-3)", marginTop: 3 }}>{sub}</div>
    </div>
  );
}

export function DashboardPage({ summary, loading, error, heroMode, includedAccountCount }: DashboardPageProps) {
  if (loading && !summary) {
    return <div style={{ padding: "40px 4px", color: "var(--text-2)", fontSize: 14 }}>Calculating your month…</div>;
  }
  if (error && !summary) {
    return <FailureBanner>{error}</FailureBanner>;
  }
  // No payload for the month on screen, and neither loading nor failed. `useBurnRateData`
  // withholds a payload fetched for any other month, so this is what a month whose
  // figures have not arrived looks like: briefly while a month change is in flight, and
  // durably if a background refresh resolved for the month the owner has just left.
  // Rendering the state rather than nothing keeps that from reading as a blank page.
  if (!summary) {
    return (
      <div style={{ padding: "40px 4px", color: "var(--text-2)", fontSize: 14 }}>
        This month&rsquo;s figures are not available yet.
      </div>
    );
  }

  // A failed background refresh leaves the previous payload on screen. It is still the
  // last figures the owner had, so it is marked rather than withdrawn -- the toast that
  // reported the failure has faded by the time they read the number.
  return (
    <div>
      {error ? (
        <div style={{ marginBottom: 18 }}>
          <FailureBanner>These figures may be out of date — {error}</FailureBanner>
        </div>
      ) : null}
      <DashboardContent summary={summary} heroMode={heroMode} includedAccountCount={includedAccountCount} />
    </div>
  );
}

function FailureBanner({ children }: { children: ReactNode }) {
  return (
    <div
      style={{
        padding: "16px 18px",
        background: "var(--over-dim)",
        border: "1px solid color-mix(in oklab, var(--over) 30%, transparent)",
        borderRadius: 12,
        color: "var(--over)",
        fontSize: 13.5,
      }}
    >
      {children}
    </div>
  );
}

function DashboardContent({
  summary,
  heroMode,
  includedAccountCount,
}: {
  summary: SummaryDashboard;
  heroMode: HeroMode;
  includedAccountCount: number;
}) {
  const hero = useHeroModel(summary);
  const headline = useHeadline(summary);
  const disclosures = useDisclosures(summary);
  const savings = useSavingsModel(summary);

  return (
    <div>
      {/* HERO — Safe to Spend Today is the headline, the balance sits under it, twin
          gauges read the month as a whole. */}
      <div
        className="br-hero"
        style={{
          position: "relative",
          background: "var(--bg-2)",
          border: "1px solid var(--line)",
          borderRadius: 18,
          padding: 30,
          overflow: "hidden",
          boxShadow: "var(--card-shadow)",
        }}
      >
        <div
          style={{
            position: "absolute",
            inset: 0,
            background: `radial-gradient(90% 120% at 22% 0%, color-mix(in oklab, ${hero.statusColor} 13%, transparent) 0%, transparent 55%)`,
            pointerEvents: "none",
          }}
        />

        {/* Headline: what you can spend today, with the balance kept directly beneath it */}
        <div
          style={{
            position: "relative",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
            gap: 16,
            flexWrap: "wrap",
          }}
        >
          <div style={{ minWidth: 0 }}>
            <div
              style={{
                fontSize: 11.5,
                textTransform: "uppercase",
                letterSpacing: "0.08em",
                color: "var(--text-3)",
                fontWeight: 600,
              }}
            >
              {headline.eyebrow}
            </div>
            <div
              className={headline.isFigure ? "num" : undefined}
              style={{
                fontSize: headline.isFigure ? 52 : 30,
                fontWeight: 600,
                lineHeight: 1.05,
                letterSpacing: "-0.02em",
                margin: "3px 0 4px",
                color: headline.isFigure ? undefined : "var(--text-2)",
              }}
            >
              {headline.value}
            </div>
            <div style={{ fontSize: 13, color: "var(--text-3)" }}>
              <span className="num" style={{ color: "var(--text-2)", fontWeight: 600 }}>
                {eur(summary.current_balance_amount)}
              </span>{" "}
              in {includedAccountCount} included account{includedAccountCount === 1 ? "" : "s"}
            </div>
            {headline.note ? (
              <div style={{ fontSize: 12.5, color: "var(--text-3)", marginTop: 5, maxWidth: 420, lineHeight: 1.5 }}>
                {headline.note}
              </div>
            ) : null}
          </div>

          <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 8 }}>
            <StatusBadge tone={hero.tone} label={headline.badge} />
            {disclosures.length > 0 ? (
              <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "flex-end", gap: 6, maxWidth: 320 }}>
                {disclosures.map((disclosure) => (
                  <DisclosureChip key={disclosure.label} {...disclosure} />
                ))}
              </div>
            ) : null}
          </div>
        </div>

        {/* Twin visualizations: budget pacing + savings rate */}
        {heroMode === "dial" ? (
          <div
            className="br-hero-row"
            style={{ position: "relative", display: "flex", gap: 30, flexWrap: "wrap", justifyContent: "center", marginTop: 20 }}
          >
            <Gauge
              fillFraction={hero.spentFrac}
              needleFraction={hero.projFrac}
              color={hero.statusColor}
              label="Budget left"
              centerText={eur(summary.money_left_amount)}
              subtitle={`of ${eurPlain(hero.budget)} budget`}
              footLeft="spent"
              footRight={`day ${summary.days_elapsed}/${summary.days_in_month}`}
            />
            <Gauge
              fillFraction={savings.savedFrac}
              color={savings.statusColor}
              label="Saved this month"
              centerText={eur(savings.saved)}
              subtitle={`of ${eurPlain(savings.income)} income`}
              footLeft="saved"
              footRight={`${savings.ratePct} rate`}
            />
          </div>
        ) : (
          <div style={{ position: "relative", display: "flex", flexDirection: "column", gap: 22, marginTop: 22, maxWidth: 560 }}>
            <MeterBar
              label="Budget left this month"
              value={eur(summary.money_left_amount)}
              subtitle={
                <>
                  of {eurPlain(hero.budget)} budgeted · <span className="num">{summary.days_elapsed}</span> of{" "}
                  <span className="num">{summary.days_in_month}</span> days elapsed
                </>
              }
              fillPct={hero.spentPct}
              color={hero.statusColor}
              markers={[
                { pct: hero.projPct, color: "var(--text)", title: "projected" },
                { pct: hero.dayPct, color: "var(--text-3)", title: "today's pace" },
              ]}
              footLeft={
                <>
                  <span style={{ color: hero.statusColor }}>●</span> spent {eurPlain(summary.budgeted_spending_amount)}
                </>
              }
              footRight={<>projected {eurPlain(summary.projected_month_end_spend_amount)}</>}
            />
            <MeterBar
              label="Saved this month"
              value={eur(savings.saved)}
              subtitle={<>of {eurPlain(savings.income)} income this month</>}
              fillPct={`${(savings.savedFrac * 100).toFixed(1)}%`}
              color={savings.statusColor}
              footLeft={
                <>
                  <span style={{ color: savings.statusColor }}>●</span> {savings.ratePct} of income kept
                </>
              }
              footRight={<>spent {eurPlain(savings.spending)}</>}
            />
          </div>
        )}

        {/* Coach verdict + burn rate */}
        <div
          style={{
            position: "relative",
            display: "flex",
            gap: 26,
            flexWrap: "wrap",
            marginTop: 26,
            paddingTop: 22,
            borderTop: "1px solid var(--line)",
          }}
        >
          <div style={{ flex: 1, minWidth: 260 }}>
            <div style={{ fontSize: 17, fontWeight: 600, letterSpacing: "-0.01em", lineHeight: 1.3, marginBottom: 5 }}>
              {headline.coach.title}
            </div>
            <div style={{ fontSize: 13.5, lineHeight: 1.55, color: "var(--text-2)", maxWidth: 440 }}>{headline.coach.body}</div>
          </div>

          <div style={{ borderLeft: `2px solid ${hero.statusColor}`, paddingLeft: 13 }}>
            <div
              title="Daily pace of variable spend — fixed payments (rent, utilities) are excluded."
              style={{ fontSize: 11.5, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--text-3)", fontWeight: 600 }}
            >
              Burn rate
            </div>
            <div className="num" style={{ fontSize: 23, fontWeight: 600, marginTop: 1 }}>
              {eur(summary.average_daily_spend_amount)}
              <span style={{ fontSize: 13, color: "var(--text-3)", fontWeight: 500 }}>/day</span>
            </div>
            <div style={{ fontSize: 11.5, color: "var(--text-3)" }}>
              {num(summary.expected_daily_spend_amount) > 0 ? (
                <>
                  vs {eurPlain(summary.expected_daily_spend_amount)}/day planned
                  <br />
                </>
              ) : null}
              proj. {eurPlain(summary.projected_month_end_spend_amount)} month-end
            </div>
          </div>
        </div>
      </div>

      {/* SECONDARY METRICS */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))",
          gap: 14,
          marginTop: 14,
        }}
      >
        <MetricCard
          label="Monthly income"
          value={eur(summary.monthly_income_amount)}
          sub="booked income this month"
        />
        <MetricCard
          label="Monthly spending"
          value={eur(summary.monthly_spending_amount)}
          sub={`${eurPlain(summary.budgeted_spending_amount)} budgeted · ${eurPlain(summary.unbudgeted_spending_amount)} unbudgeted`}
        />
        <MetricCard
          label="Projected spend"
          value={eur(summary.projected_month_end_spend_amount)}
          sub={`of ${eurPlain(hero.budget)} · ${summary.days_elapsed} of ${summary.days_in_month} days`}
        />
      </div>

      {/* BUDGET PULSE */}
      <div style={{ marginTop: 14 }}>
        <div
          style={{
            background: "var(--bg-2)",
            border: "1px solid var(--line)",
            borderRadius: 16,
            padding: "20px 22px",
            boxShadow: "var(--card-shadow)",
          }}
        >
          <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 16 }}>
            <div style={{ fontSize: 15, fontWeight: 600 }}>Budget pulse</div>
            <div style={{ fontSize: 12, color: "var(--text-3)" }}>
              {summary.days_elapsed} of {summary.days_in_month} days · {hero.dayPct} through the month
            </div>
          </div>
          {summary.budget_usage.length > 0 ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 15 }}>
              {summary.budget_usage.map((usage) => {
                const remaining = num(usage.remaining_amount);
                // A fixed budget that hasn't been charged yet is neither "on track" nor
                // "over" — it's just pending. Show it neutral until the payment lands.
                const isPendingFixed = usage.is_fixed && num(usage.spent_amount) <= 0;
                const tone = isPendingFixed ? "neutral" : usageTone(usage.status);
                const color = TONE_COLOR[tone];
                const barPct = `${Math.min(100, Math.max(0, usage.utilization_percent)).toFixed(0)}%`;
                return (
                  <div key={usage.category_id}>
                    <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 6 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13.5, fontWeight: 500 }}>
                        <span style={{ width: 8, height: 8, borderRadius: 2, background: color }} />
                        {usage.category_name}
                        {usage.is_fixed ? (
                          <span
                            title="Fixed payment — not paced day-by-day"
                            style={{ fontSize: 9.5, fontWeight: 600, letterSpacing: "0.04em", textTransform: "uppercase", color: "var(--text-3)", background: "var(--bg-4)", border: "1px solid var(--line-2)", borderRadius: 5, padding: "1px 5px" }}
                          >
                            Fixed
                          </span>
                        ) : null}
                      </div>
                      <div className="num" style={{ fontSize: 12.5, color: "var(--text-2)" }}>
                        {eurPlain(usage.spent_amount)} <span style={{ color: "var(--text-3)" }}>/ {eurPlain(usage.budget_amount)}</span>
                      </div>
                    </div>
                    <div style={{ position: "relative", height: 8, background: "var(--bg-4)", borderRadius: 5, overflow: "hidden" }}>
                      <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: barPct, background: color, borderRadius: 5 }} />
                      {/* The "today's pace" marker only makes sense for spend that accrues
                          daily — a fixed lump has no meaningful pace, so we hide it. */}
                      {usage.is_fixed ? null : (
                        <div style={{ position: "absolute", top: -1, bottom: -1, left: hero.dayPct, width: 1.5, background: "var(--text-3)", opacity: 0.6 }} />
                      )}
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", marginTop: 5, fontSize: 11 }}>
                      <span style={{ color, fontWeight: 600 }}>{isPendingFixed ? "Not yet paid" : TONE_LABEL[tone]}</span>
                      <span className="num" style={{ color: "var(--text-3)" }}>
                        {isPendingFixed
                          ? `${eurPlain(usage.budget_amount)} est.`
                          : `${Math.round(usage.utilization_percent)}% used · ${
                              remaining >= 0 ? `${eurPlain(remaining)} left` : `${eurPlain(-remaining)} over`
                            }`}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div style={{ padding: "26px", textAlign: "center", color: "var(--text-3)", fontSize: 13, background: "var(--bg-3)", borderRadius: 11 }}>
              No active budgets this month. Add one under Rules &amp; Budgets.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
