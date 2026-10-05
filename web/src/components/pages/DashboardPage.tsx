import { useMemo, type CSSProperties, type ReactNode } from "react";

import {
  TONE_COLOR,
  TONE_DIM,
  TONE_LABEL,
  eur,
  eurPlain,
  usageTone,
} from "../../lib/format";
import type { Tone } from "../../lib/format";
import type { HeroMode } from "../../lib/viewTypes";
import type { SummaryDashboard } from "../../types";

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

/** Budget model: how the month is pacing against planned spend. */
function useHeroModel(summary: SummaryDashboard) {
  return useMemo(() => {
    const budget = num(summary.monthly_budget_amount);
    const budgetedSpend = num(summary.budgeted_spending_amount);
    const projected = num(summary.projected_month_end_spend_amount);
    const overspend = num(summary.projected_overspend_amount);

    const tone: Tone =
      overspend > 0 ? "over" : budget > 0 && budgetedSpend / budget >= 0.85 ? "watch" : "good";

    const spentFrac = budget > 0 ? clampFraction(budgetedSpend / budget) : 0;
    const projFrac = budget > 0 ? clampFraction(projected / budget) : 0;
    const dayFrac = summary.days_in_month > 0 ? clampFraction(summary.days_elapsed / summary.days_in_month) : 0;

    const underBudget = budget - projected;
    const coach =
      tone === "over"
        ? {
            title: `${eurPlain(overspend)} over budget, projected`,
            body: "At this pace you'll finish over plan. Trim discretionary spend to pull it back.",
          }
        : tone === "watch"
          ? {
              title: "Getting close to plan",
              body: `Spending is near your budget with ${summary.days_elapsed} of ${summary.days_in_month} days elapsed — ease off to stay under.`,
            }
          : {
              title: "Nice — plenty of headroom",
              body: `You're pacing under plan. On this trend you'll finish about ${eurPlain(Math.max(0, underBudget))} under budget.`,
            };

    return {
      tone,
      statusColor: TONE_COLOR[tone],
      statusDim: TONE_DIM[tone],
      statusLabel: TONE_LABEL[tone],
      coach,
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
        {error}
      </div>
    );
  }
  if (!summary) {
    return null;
  }

  return <DashboardContent summary={summary} heroMode={heroMode} includedAccountCount={includedAccountCount} />;
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
  const savings = useSavingsModel(summary);

  return (
    <div>
      {/* HERO — Current balance is the headline, twin gauges read the month. */}
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

        {/* Headline: current balance + overall status */}
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
              Current balance
            </div>
            <div className="num" style={{ fontSize: 52, fontWeight: 600, lineHeight: 1.05, letterSpacing: "-0.02em", margin: "3px 0 2px" }}>
              {eur(summary.current_balance_amount)}
            </div>
            <div style={{ fontSize: 13, color: "var(--text-3)" }}>
              across {includedAccountCount} included account{includedAccountCount === 1 ? "" : "s"}
            </div>
          </div>
          <StatusBadge tone={hero.tone} label={hero.statusLabel} />
        </div>

        {/* Twin visualizations: budget pacing + savings rate */}
        {heroMode === "dial" ? (
          <div
            className="br-hero-gauges"
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
            <div className="num" style={{ fontSize: 17, fontWeight: 600, letterSpacing: "-0.01em", lineHeight: 1.3, marginBottom: 5 }}>
              {hero.coach.title}
            </div>
            <div style={{ fontSize: 13.5, lineHeight: 1.55, color: "var(--text-2)", maxWidth: 440 }}>{hero.coach.body}</div>
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
