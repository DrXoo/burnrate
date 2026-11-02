import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { summaryFor } from "./fakeApi";
import { DashboardPage } from "../src/components/pages/DashboardPage";
import type { HeroMode } from "../src/lib/viewTypes";
import type { SummaryDashboard } from "../src/types";

function render(overrides: Partial<SummaryDashboard>, heroMode: HeroMode = "dial"): string {
  return renderToStaticMarkup(
    <DashboardPage
      summary={{ ...summaryFor("2026-10"), ...overrides }}
      loading={false}
      error={null}
      heroMode={heroMode}
      includedAccountCount={1}
    />,
  );
}

// The owner's live October, which is the month this whole split exists for. Food and
// Invoices between them spent 295 where 580 is usual; a one-off legal expense of 8400
// has no history and so cannot be compared to anything.
const OCTOBER: Partial<SummaryDashboard> = {
  monthly_spending_amount: "8695.00",
  comparable_spend_amount: "295.00",
  uncomparable_spend_amount: "8400.00",
  comparable_spend_baseline: {
    baseline_amount: "580.00",
    deviation_percent: -49.1,
    comparison_status: "below",
  },
  monthly_income_amount: "1400.00",
  monthly_income_baseline: {
    baseline_amount: "2000.00",
    deviation_percent: -30.0,
    comparison_status: "below",
  },
  net_cash_flow_amount: "-7295.00",
  net_cash_flow_baseline_amount: "1700.00",
};

describe("the dashboard's comparison against what is normal", () => {
  it("judges spending on the half it can compare, and discloses the rest", () => {
    const html = render(OCTOBER);

    expect(html).toContain("€295.00 comparable");
    expect(html).toContain("normally €580.00");
    expect(html).toContain("49% below usual");
    // Reported beside the comparison, never inside it. Folding it in would turn a
    // month where every ordinary category came in cheap into a report of
    // catastrophic overspending.
    expect(html).toContain("€8,400.00 cannot be compared");
  });

  it("shows what the owner normally earns beside what they earned", () => {
    const html = render(OCTOBER);

    expect(html).toContain("normally €2,000.00");
    expect(html).toContain("30% below usual");
  });

  it("gives net cash flow its usual figure and no verdict", () => {
    const html = render(OCTOBER);

    expect(html).toContain("normally €1,700.00");
  });

  it("claims nothing when there is too little trustworthy history", () => {
    const html = render({
      ...OCTOBER,
      baseline_status: "insufficient_history",
      baseline_months_count: 1,
      comparable_spend_baseline: {
        baseline_amount: null,
        deviation_percent: null,
        comparison_status: "no_baseline",
      },
      monthly_income_baseline: {
        baseline_amount: null,
        deviation_percent: null,
        comparison_status: "no_baseline",
      },
      net_cash_flow_baseline_amount: null,
    });

    expect(html).not.toContain("usual");
    expect(html).not.toContain("normally");
    expect(html).not.toContain("cannot be compared");
    // Silence would read as "nothing to say about your spending", which is a
    // different and wrong claim. The owner is told why there is no comparison, so
    // they can tell a product that has nothing to report from one that cannot
    // report yet -- and in their case the fix is theirs: classify the backlog.
    expect(html).toContain("not enough history to compare yet");
  });

  it("prints no figure for a baseline of zero, on any of the three cards", () => {
    // A zero baseline is an absent one: the backend does not divide by it, so the
    // band is already `no_baseline` while the amount beside it reads "0.00". The
    // string "0.00" is truthy, so a guard on the amount published "normally €0.00 ·
    // no baseline yet" -- a figure and a denial of it in one breath. The owner's own
    // case is a salary dated the 28th read on the 26th, where every Qualifying Month
    // contributes nothing up to the cutoff.
    const html = render({
      ...OCTOBER,
      monthly_income_baseline: {
        baseline_amount: "0.00",
        deviation_percent: null,
        comparison_status: "no_baseline",
      },
      comparable_spend_baseline: {
        baseline_amount: "0.00",
        deviation_percent: null,
        comparison_status: "no_baseline",
      },
    });

    expect(html).not.toContain("normally €0.00");
    expect(html).not.toContain("no baseline yet");
  });

  // Both hero modes carry the net baseline, and the owner picks the mode -- so both
  // are checked. They were two separate call sites of the same formatter.
  it.each(["dial", "bar"] as const)("signs a net cash flow baseline that is a deficit (%s)", (heroMode) => {
    // An owner whose usual month ends in the red is explicitly allowed to carry a
    // negative net baseline -- it is the one baseline published as an amount with no
    // band for exactly that reason. Rendered unsigned it read "normally €-450.00
    // kept", a minus sign smuggled in by the number formatter rather than stated.
    const html = render({ ...OCTOBER, net_cash_flow_baseline_amount: "-450.00" }, heroMode);

    expect(html).toContain("normally \u2212\u20ac450.00 kept");
    expect(html).not.toContain("\u20ac-450.00");
  });

  // Both hero modes carry it, for the same reason the net baseline above is checked
  // in both: the owner picks the mode, not the data.
  it.each(["dial", "bar"] as const)(
    "discloses the money moved in that funded the deficit (%s)",
    (heroMode) => {
      // The owner's live October: a net of -7295 paid for by 7841 moved in from an
      // account BurnRate cannot see. The deficit without its cause beside it is a
      // worse screen than the wrong figure it replaces.
      const html = render({ ...OCTOBER, inbound_transfer_amount: "7841.00" }, heroMode);

      expect(html).toContain("\u20ac7,841.00 moved in from an unsynced account");
    },
  );

  it("says nothing about money moved in when none was", () => {
    const html = render({ ...OCTOBER, inbound_transfer_amount: "0.00" });

    expect(html).not.toContain("moved in");
  });

  it("warns above the figures that bank data was never fetched and is gone", () => {
    // The owner's real 2026 outage: five days never asked about, and two months of
    // understated totals read without anything saying so.
    const html = render({
      ...OCTOBER,
      sync_gap: {
        status: "lost",
        oldest_missing_day: "2026-08-30",
        newest_missing_day: "2026-09-03",
        missing_days: 5,
        unrecoverable_days: 5,
        recoverable_until: null,
      },
    });

    expect(html).toContain("5 days of bank data were never fetched");
    expect(html).toContain("can no longer be recovered");
    // Above the figures it invalidates, not among them.
    expect(html.indexOf("never fetched")).toBeLessThan(html.indexOf("Saved this month"));
  });

  it("asks for a reconnection while the missing days can still be had", () => {
    const html = render({
      ...OCTOBER,
      sync_gap: {
        status: "expiring",
        oldest_missing_day: "2026-10-11",
        newest_missing_day: "2026-11-04",
        missing_days: 25,
        unrecoverable_days: 0,
        recoverable_until: "2026-11-10",
      },
    });

    expect(html).toContain("Reconnect the bank before 2026-11-10");
    expect(html).not.toContain("can no longer be recovered");
  });

  it("says nothing about sync when every day was fetched", () => {
    const html = render({ ...OCTOBER, sync_gap: null });

    expect(html).not.toContain("bank data");
  });

  it("does not disclose an uncomparable total when there is none", () => {
    const html = render({ ...OCTOBER, uncomparable_spend_amount: "0.00" });

    expect(html).toContain("49% below usual");
    expect(html).not.toContain("cannot be compared");
  });
});
