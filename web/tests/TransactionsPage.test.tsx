import { cleanup, fireEvent, render as renderDom } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { transaction } from "./fakeApi";
import { TransactionsPage } from "../src/components/pages/TransactionsPage";
import type { Category, FiltersState, Transaction } from "../src/types";

const FOOD: Category = { category_id: "cat-food", name: "Food", type: "expense", active: true };
const GYM_ARCHIVED: Category = { category_id: "cat-gym", name: "Gym", type: "expense", active: false };

const FILTERS: FiltersState = {
  month: "2026-10",
  accountId: "",
  categoryId: "",
  status: "",
  categorized: "",
};

interface PageOptions {
  items?: Transaction[];
  categories?: Category[];
  assignableCategories?: Category[];
}

/** The page as the owner reaches it, with one row and whatever categories exist. */
function page(options: PageOptions = {}) {
  return (
    <TransactionsPage
      accounts={[]}
      categories={options.categories ?? [FOOD, GYM_ARCHIVED]}
      assignableCategories={options.assignableCategories ?? [FOOD]}
      rules={[]}
      filters={FILTERS}
      applyFilters={() => {}}
      items={options.items ?? [transaction("t-1", "Supermarket")]}
      total={1}
      loading={false}
      error={null}
      paging={{ limit: 25, offset: 0, total: 1 }}
      monthLabel="October 2026"
      onMovePage={() => {}}
      onCategorize={() => Promise.resolve()}
      onUncategorize={() => Promise.resolve()}
      onExclude={() => Promise.resolve()}
      onRestore={() => Promise.resolve()}
      onCreateRule={() => Promise.resolve()}
      onUpdateRule={() => Promise.resolve()}
      onDeleteRule={() => Promise.resolve()}
    />
  );
}

function optionsOf(select: Element): (string | null)[] {
  return Array.from(select.querySelectorAll("option")).map((node) => node.textContent);
}

/** The month's category filter, which is the one select that is not an assignment. */
function filterSelect(dom: ReturnType<typeof renderDom>): Element {
  const selects = Array.from(dom.container.querySelectorAll("select"));
  const found = selects.find((select) => optionsOf(select).includes("All categories"));
  if (!found) {
    throw new Error("category filter not found");
  }
  return found;
}

function assignSelects(dom: ReturnType<typeof renderDom>): Element[] {
  return Array.from(dom.container.querySelectorAll("select")).filter((select) =>
    optionsOf(select).includes("— Assign —"),
  );
}

// jsdom ships no matchMedia, and this page switches between a desktop table and
// mobile cards on one. Reported as not matching, so the desktop layout renders.
beforeEach(() => {
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  }));
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("TransactionsPage and archived categories", () => {
  it("keeps an archived category in the filter but out of the assignment picker", () => {
    const dom = renderDom(page());

    // Filtering by a retired category is how the owner looks at what it used to cost,
    // so the filter keeps it...
    expect(optionsOf(filterSelect(dom))).toContain("Gym");
    // ...while nothing new may be filed against it.
    assignSelects(dom).forEach((select) => {
      expect(optionsOf(select)).toContain("Food");
      expect(optionsOf(select)).not.toContain("Gym");
    });
  });

  it("will not target a new rule at the archived category a transaction already sits in", () => {
    const dom = renderDom(
      page({
        items: [
          transaction("t-1", "Gym membership", { category_id: "cat-gym", category_name: "Gym" }),
        ],
      }),
    );

    fireEvent.click(dom.getAllByText("Create rule")[0]);

    // The rule form defaults to the transaction's own category. Archived, that is an
    // id absent from the picker: the select would render blank and the rule would be
    // refused by the backend on submit.
    const target = dom.getByLabelText("Rule target category") as HTMLSelectElement;
    expect(target.value).toBe("cat-food");
  });
});

describe("TransactionsPage rows in archived categories", () => {
  it("still shows the archived category a transaction is filed under", () => {
    const dom = renderDom(
      page({
        items: [
          transaction("t-1", "Gym membership", { category_id: "cat-gym", category_name: "Gym" }),
        ],
      }),
    );

    const [assign] = assignSelects(dom);
    // Archiving does not touch the transactions already filed under the category, so
    // the row is still categorized. A select whose value matches no option falls back
    // to index 0 and reads "— Assign —": a categorized row looking uncategorized, and
    // re-picking silently refiles it somewhere else.
    expect((assign as HTMLSelectElement).value).toBe("cat-gym");
    expect(optionsOf(assign).some((label) => label?.includes("Gym"))).toBe(true);
  });

  it("does not offer that archived category to a row filed elsewhere", () => {
    const dom = renderDom(
      page({
        items: [
          transaction("t-1", "Supermarket", { category_id: "cat-food", category_name: "Food" }),
        ],
      }),
    );

    // Carried only by the row that is already in it, never offered as a destination.
    // Matched as a substring: the archived label carries a suffix, so an exact
    // comparison would pass however many archived options were offered.
    expect(optionsOf(assignSelects(dom)[0]).some((label) => label?.includes("Gym"))).toBe(false);
  });
});
