import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { summaryFor } from "./fakeApi";
import { DashboardPage } from "../src/components/pages/DashboardPage";
import type { SummaryDashboard } from "../src/types";

function render(overrides: Partial<SummaryDashboard>): string {
  return renderToStaticMarkup(
    <DashboardPage
      summary={{ ...summaryFor("2026-10"), ...overrides }}
      loading={false}
      error={null}
      heroMode="dial"
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

  it("does not disclose an uncomparable total when there is none", () => {
    const html = render({ ...OCTOBER, uncomparable_spend_amount: "0.00" });

    expect(html).toContain("49% below usual");
    expect(html).not.toContain("cannot be compared");
  });
});
