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
      valueDash: `${(spentFrac * GAUGE_ARC).toFixed(1)} ${GAUGE_CIRCUMFERENCE.toFixed(2)}`,
      projDeg: (projFrac * 270).toFixed(1),
      spentPct: `${(spentFrac * 100).toFixed(1)}%`,
      projPct: `${(projFrac * 100).toFixed(1)}%`,
      dayPct: `${(dayFrac * 100).toFixed(1)}%`,
    };
  }, [summary]);
}

function MetricCard({ label, value, valueColor, sub }: { label: string; value: string; valueColor?: string; sub: ReactNode }) {
  return (
    <div style={cardBase}>
      <div style={{ fontSize: 12, color: "var(--text-3)", fontWeight: 600, marginBottom: 7 }}>{label}</div>
      <div className="num" style={{ fontSize: 26, fontWeight: 600, color: valueColor }}>
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
  const net = num(summary.net_cash_flow_amount);

  // The dial's centered "money left" figure has to sit inside the ring's inner
  // opening (~150px of safe width once the arc's blur glow is accounted for). Now
  // that amounts carry cents they get wider, so size the type to fit that width:
  // ~0.62em per glyph in Space Grotesk, clamped to a sensible 24–44px range.
  const moneyLeftText = eur(summary.money_left_amount);
  const moneyLeftFontSize = Math.max(24, Math.min(44, Math.floor(150 / (moneyLeftText.length * 0.62))));

  return (
    <div>
      {/* HERO */}
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
        <div className="br-hero-row" style={{ position: "relative", display: "flex", gap: 38, flexWrap: "wrap", alignItems: "center" }}>
          <div style={{ flex: "none" }}>
            {heroMode === "dial" ? (
              <div style={{ position: "relative", width: 260, height: 210 }}>
                <svg width={260} height={210} viewBox="0 0 220 200" style={{ overflow: "visible" }}>
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
                      stroke={hero.statusColor}
                      strokeWidth="16"
                      strokeLinecap="round"
                      strokeDasharray={hero.valueDash}
                      style={{ filter: "blur(9px)", opacity: 0.55 }}
                    />
                    <circle
                      cx="110"
                      cy="110"
                      r={GAUGE_RADIUS}
                      fill="none"
                      stroke={hero.statusColor}
                      strokeWidth="16"
                      strokeLinecap="round"
                      strokeDasharray={hero.valueDash}
                    />
                    <line
                      x1="176"
                      y1="110"
                      x2="196"
                      y2="110"
                      stroke="var(--text)"
                      strokeWidth="2.5"
                      strokeLinecap="round"
                      transform={`rotate(${hero.projDeg} 110 110)`}
                    />
                  </g>
                </svg>
                <div style={{ position: "absolute", top: 78, left: 0, right: 0, textAlign: "center" }}>
                  <div
                    style={{
                      fontSize: 11.5,
                      textTransform: "uppercase",
                      letterSpacing: "0.08em",
                      color: "var(--text-3)",
                      fontWeight: 600,
                    }}
                  >
                    Money left
                  </div>
                  <div className="num" style={{ fontSize: moneyLeftFontSize, fontWeight: 600, lineHeight: 1.05, marginTop: 2, whiteSpace: "nowrap" }}>
                    {moneyLeftText}
                  </div>
                  <div style={{ fontSize: 12, color: "var(--text-3)" }}>of {eurPlain(hero.budget)} budget</div>
                </div>
                <div
                  style={{
                    position: "absolute",
                    bottom: 6,
                    left: 0,
                    right: 0,
                    display: "flex",
                    justifyContent: "space-between",
                    fontSize: 11,
                    color: "var(--text-3)",
                    padding: "0 8px",
                  }}
                >
                  <span>spent</span>
                  <span className="num">
                    day {summary.days_elapsed}/{summary.days_in_month}
                  </span>
                </div>
              </div>
            ) : (
              <div style={{ width: 300 }}>
                <div
                  style={{
                    fontSize: 11.5,
                    textTransform: "uppercase",
                    letterSpacing: "0.08em",
                    color: "var(--text-3)",
                    fontWeight: 600,
                  }}
                >
                  Money left this month
                </div>
                <div className="num" style={{ fontSize: 58, fontWeight: 600, lineHeight: 1, margin: "4px 0 2px" }}>
                  {eur(summary.money_left_amount)}
                </div>
                <div style={{ fontSize: 13, color: "var(--text-2)", marginBottom: 20 }}>
                  of {eurPlain(hero.budget)} budgeted · <span className="num">{summary.days_elapsed}</span> of{" "}
                  <span className="num">{summary.days_in_month}</span> days elapsed
                </div>
                <div style={{ position: "relative", height: 16, background: "var(--bg-4)", borderRadius: 8, overflow: "visible" }}>
                  <div
                    style={{
                      position: "absolute",
                      inset: 0,
                      width: hero.spentPct,
                      background: hero.statusColor,
                      borderRadius: 8,
                      boxShadow: `0 0 14px color-mix(in oklab, ${hero.statusColor} 55%, transparent)`,
                    }}
                  />
                  <div style={{ position: "absolute", top: -4, bottom: -4, left: hero.projPct, width: 2, background: "var(--text)" }} title="projected" />
                  <div style={{ position: "absolute", top: -4, bottom: -4, left: hero.dayPct, width: 2, background: "var(--text-3)" }} title="today's pace" />
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", marginTop: 8, fontSize: 11.5, color: "var(--text-3)" }}>
                  <span>
                    <span style={{ color: hero.statusColor }}>●</span> spent {eurPlain(summary.budgeted_spending_amount)}
                  </span>
                  <span>| projected {eurPlain(summary.projected_month_end_spend_amount)}</span>
                </div>
              </div>
            )}
          </div>

          {/* verdict + core numbers */}
          <div style={{ flex: 1, minWidth: 270 }}>
            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 7,
                padding: "5px 11px",
                borderRadius: 99,
                background: hero.statusDim,
                color: hero.statusColor,
                fontSize: 12.5,
                fontWeight: 600,
                marginBottom: 12,
              }}
            >
              <span style={{ width: 7, height: 7, borderRadius: "50%", background: hero.statusColor }} />
              {hero.statusLabel}
            </div>
            <div className="num" style={{ fontSize: 25, fontWeight: 600, letterSpacing: "-0.02em", lineHeight: 1.2, marginBottom: 6 }}>
              {hero.coach.title}
            </div>
            <div style={{ fontSize: 14.5, lineHeight: 1.55, color: "var(--text-2)", maxWidth: 400, marginBottom: 22 }}>
              {hero.coach.body}
            </div>

            <div style={{ display: "flex", gap: 26, flexWrap: "wrap" }}>
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
          label="Current balance"
          value={eur(summary.current_balance_amount)}
          sub={`across ${includedAccountCount} included account${includedAccountCount === 1 ? "" : "s"}`}
        />
        <MetricCard
          label="Monthly spending"
          value={eur(summary.monthly_spending_amount)}
          sub={`${eurPlain(summary.budgeted_spending_amount)} budgeted · ${eurPlain(summary.unbudgeted_spending_amount)} unbudgeted`}
        />
        <MetricCard
          label="Net this month"
          value={net >= 0 ? `+${eurPlain(net)}` : eur(net)}
          valueColor={net >= 0 ? "var(--good)" : "var(--over)"}
          sub="income minus spending"
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
