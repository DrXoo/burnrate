import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { summaryFor } from "./fakeApi";
import { CategoriesPage } from "../src/components/pages/CategoriesPage";
import type { Category } from "../src/types";

const FOOD: Category = { category_id: "cat-food", name: "Food", type: "expense", active: true };

function render(props: { error?: string | null; loading?: boolean; withSummary?: boolean }): string {
  return renderToStaticMarkup(
    <CategoriesPage
      categories={[FOOD]}
      summary={props.withSummary === false ? null : summaryFor("2026-10")}
      loading={props.loading ?? false}
      error={props.error ?? null}
      month="2026-10"
      monthLabel="October 2026"
      loadMonthTransactions={() => Promise.resolve([])}
      onCreateCategory={() => Promise.resolve()}
    />,
  );
}

describe("CategoriesPage", () => {
  it("marks the budget figures when a background refresh fails for the month on screen", () => {
    const markup = render({ error: "Service unavailable" });

    expect(markup).toContain("may be out of date");
    expect(markup).toContain("Service unavailable");
  });

  it("leaves a fresh payload for the month on screen unmarked", () => {
    const markup = render({});

    expect(markup).not.toContain("out of date");
    expect(markup).not.toContain("unavailable");
  });

  it("calls the month's budgets unavailable rather than stale when no rows arrived at all", () => {
    const markup = render({ withSummary: false, error: "Service unavailable" });

    // A month with no rows is a different claim from one whose rows are a few minutes
    // old: there is nothing on screen that could be out of date.
    expect(markup).toContain("Budget figures unavailable");
    expect(markup).not.toContain("out of date");
  });
});
