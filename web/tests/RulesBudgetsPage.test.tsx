import { act, cleanup, fireEvent, render as renderDom } from "@testing-library/react";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it } from "vitest";

import { budget, summaryFor } from "./fakeApi";
import { RulesBudgetsPage } from "../src/components/pages/RulesBudgetsPage";
import type { Budget, BudgetDraft, BudgetUpdateDraft, Category } from "../src/types";

const RENT: Category = { category_id: "cat-rent", name: "Rent", type: "expense", active: true };
const FOOD: Category = { category_id: "cat-food", name: "Food", type: "expense", active: true };
const PHARMACY: Category = { category_id: "cat-pharmacy", name: "Pharmacy", type: "expense", active: true };

interface PageOptions {
  month?: string;
  categories?: Category[];
  assignableCategories?: Category[];
  onReactivateBudget?: (budgetId: string) => Promise<void>;
  onRenameCategory?: (categoryId: string, name: string) => Promise<void>;
  onUpdateBudget?: (budgetId: string, draft: BudgetUpdateDraft) => Promise<void>;
  onDeactivateBudget?: (budgetId: string) => Promise<void>;
  onCreateBudget?: (draft: BudgetDraft) => Promise<void>;
}

/** The page as the owner reaches it for a month, with whatever that month holds. */
function page(budgets: Budget[] | null, options: PageOptions = {}) {
  return (
    <RulesBudgetsPage
      rules={[]}
      categories={options.categories ?? [RENT, FOOD]}
      assignableCategories={options.assignableCategories ?? options.categories ?? [RENT, FOOD]}
      budgets={budgets}
      summary={summaryFor(options.month ?? "2026-10")}
      onToggleRule={() => Promise.resolve()}
      onUpdateRule={() => Promise.resolve()}
      onDeleteRule={() => Promise.resolve()}
      onCreateBudget={options.onCreateBudget ?? (() => Promise.resolve())}
      onUpdateBudget={options.onUpdateBudget ?? (() => Promise.resolve())}
      onDeactivateBudget={options.onDeactivateBudget ?? (() => Promise.resolve())}
      onReactivateBudget={options.onReactivateBudget ?? (() => Promise.resolve())}
      onRenameCategory={options.onRenameCategory ?? (() => Promise.resolve())}
    />
  );
}

/** Pharmacy as the owner left it after cancelling it by mistake in October: the
 *  window closed at the end of September, so October does not hold it.
 *
 *  Restorable, because nothing took its place -- which only the backend can say, so
 *  the row carries its answer. */
function cancelledPharmacy(): Budget {
  return budget("Pharmacy", {
    category_id: "cat-pharmacy",
    amount: "50.00",
    is_fixed: false,
    active_to: "2026-09-30",
    active: false,
    status: "inactive",
    can_reactivate: true,
  });
}

/** Rent as October holds it for the last time: the owner cancelled in November, so
 *  the window closed at the end of October.
 *
 *  Both edges of a window sit on month boundaries -- `active_from` is a 1st and
 *  `active_to` a month end -- so this is the only shape a final month comes in. A
 *  mid-month `active_to` is what the old rule wrote and what migration 0008 erases. */
function finalMonthRent(): Budget {
  return budget("Rent", {
    category_id: "cat-rent",
    active_to: "2026-10-31",
    active: true,
    status: "active",
  });
}

afterEach(() => {
  cleanup();
});

describe("RulesBudgetsPage", () => {
  it("marks the last month a budget covers", () => {
    // October is the last month Rent covers. The month's figures count it, so the row
    // has to appear -- but reading exactly like a running budget invites the owner to
    // cancel what is already cancelled. The day carries nothing, since a window
    // always closes on a month end; that this is the final month is the whole point.
    const markup = renderToStaticMarkup(page([finalMonthRent()]));

    expect(markup).toContain("Rent");
    expect(markup).toContain("Final month");
  });

  it("leaves a budget with months still ahead of it unmarked", () => {
    // Read from September, the same row has months left: it runs through September and
    // stops in a later one. Marking it there would report an end September has not
    // reached.
    const markup = renderToStaticMarkup(page([finalMonthRent()], { month: "2026-09" }));

    expect(markup).toContain("Rent");
    expect(markup).not.toContain("Final month");
  });

  it("does not offer a category its own budget for the month as unbudgeted", () => {
    // The choices come from the same rows, so a list read against the owner's day
    // offered Rent as though it had no budget -- and creating one for a month the old
    // row already covers is refused for overlapping, with a 400 the owner cannot act
    // on. Asserted through the form the owner actually opens, because that select is
    // the only place these choices are visible.
    const rendered = renderDom(page([finalMonthRent()]));

    fireEvent.click(rendered.getByText("+ New"));
    const choices = rendered
      .getAllByRole("option")
      .map((option) => option.textContent)
      .filter((label) => label !== "Choose category…");

    expect(choices).toEqual(["Food"]);
  });

  it("says the month's budgets are unavailable rather than claiming there are none", () => {
    // Null is a month whose list has not arrived. "No budgets yet" is a claim about
    // the month, and an unknown list is not entitled to make it.
    const markup = renderToStaticMarkup(page(null));

    expect(markup).toContain("Budgets unavailable");
    expect(markup).not.toContain("No budgets yet");
  });

  it("offers a cancelled budget a way back instead of a second cancel", () => {
    // Cancelling is one click and never deleted anything, so the row the owner
    // cancelled by mistake has to be reachable -- and offering them the same cancel
    // control again says nothing true about a budget that is already stopped.
    const reactivated: string[] = [];
    const rendered = renderDom(
      page([cancelledPharmacy()], {
        categories: [RENT, FOOD, PHARMACY],
        onReactivateBudget: (budgetId) => {
          reactivated.push(budgetId);
          return Promise.resolve();
        },
      }),
    );

    fireEvent.click(rendered.getByTitle("Reactivate this budget"));

    expect(reactivated).toEqual(["budget-pharmacy"]);
    expect(rendered.queryByTitle(/^Cancel this budget/)).toBeNull();
  });

  it("keeps a cancelled budget out of the month's own list", () => {
    // It belongs to the months it covered, and October is not one of them. Listing it
    // beside the month's budgets would put back the figure the cancellation removed.
    const rendered = renderDom(
      page([budget("Food", { category_id: "cat-food", amount: "300.00" }), cancelledPharmacy()], {
        categories: [RENT, FOOD, PHARMACY],
      }),
    );

    const monthList = rendered.getByText("Cancelled").parentElement?.previousElementSibling;
    expect(monthList?.textContent).toContain("Food");
    expect(monthList?.textContent).not.toContain("Pharmacy");
  });
});

describe("RulesBudgetsPage renaming", () => {
  /** The running Rent budget, as October holds it. */
  function rent(): Budget {
    return budget("Rent", { category_id: "cat-rent", amount: "800.00" });
  }

  function openEditor(dom: ReturnType<typeof renderDom>) {
    fireEvent.click(dom.getByTitle("Edit budget"));
    return dom.getByTitle("Budget name") as HTMLInputElement;
  }

  it("offers the budget's name for editing, prefilled with the category's", () => {
    const dom = renderDom(page([rent()]));

    const nameInput = openEditor(dom);

    expect(nameInput.value).toBe("Rent");
  });

  it("renames the category when the name in the editor changed", async () => {
    const renames: Array<[string, string]> = [];
    const updates: string[] = [];
    const dom = renderDom(
      page([rent()], {
        onRenameCategory: (categoryId, name) => {
          renames.push([categoryId, name]);
          return Promise.resolve();
        },
        onUpdateBudget: (budgetId) => {
          updates.push(budgetId);
          return Promise.resolve();
        },
      }),
    );

    const nameInput = openEditor(dom);
    fireEvent.change(nameInput, { target: { value: "Housing" } });
    await act(async () => {
      fireEvent.click(dom.getByText("Save"));
    });

    // The id, not the name: the category is identified by id everywhere, and a page
    // that looked the id up by the old name would break on the second rename.
    expect(renames).toEqual([["cat-rent", "Housing"]]);
    expect(updates).toEqual(["budget-rent"]);
  });

  it("does not rename when the name in the editor was left alone", async () => {
    let renamed = false;
    const dom = renderDom(
      page([rent()], {
        onRenameCategory: () => {
          renamed = true;
          return Promise.resolve();
        },
      }),
    );

    openEditor(dom);
    await act(async () => {
      fireEvent.click(dom.getByText("Save"));
    });

    // Editing only the amount must not write to the category: a no-op rename is a
    // pointless write, and against the row's own name the backend would allow it,
    // so nothing downstream would report the mistake.
    expect(renamed).toBe(false);
  });

  it("keeps the editor open with the reason when the new name is already taken", async () => {
    let amountSaved = false;
    const dom = renderDom(
      page([rent()], {
        onRenameCategory: () => Promise.reject(new Error("Category 'Food' already exists")),
        onUpdateBudget: () => {
          amountSaved = true;
          return Promise.resolve();
        },
      }),
    );

    const nameInput = openEditor(dom);
    fireEvent.change(nameInput, { target: { value: "Food" } });
    await act(async () => {
      fireEvent.click(dom.getByText("Save"));
    });

    expect(dom.queryByText(/already exists/)).not.toBeNull();
    // Still open, so the owner can correct the name rather than retype the edit.
    expect((dom.getByTitle("Budget name") as HTMLInputElement).value).toBe("Food");
    // The amount is not saved behind a failed rename: one Save is one outcome.
    expect(amountSaved).toBe(false);
  });
});

describe("RulesBudgetsPage and archived categories", () => {
  const GYM_ARCHIVED: Category = { category_id: "cat-gym", name: "Gym", type: "expense", active: false };

  it("will not offer an archived category a new budget", () => {
    const dom = renderDom(
      page([], {
        categories: [FOOD, GYM_ARCHIVED],
        assignableCategories: [FOOD],
      }),
    );

    fireEvent.click(dom.getByText("+ New"));

    const options = Array.from(dom.container.querySelectorAll("option")).map((node) => node.textContent);
    expect(options).toContain("Food");
    // Budgeting a category the owner retired is the mistake archiving exists to stop.
    expect(options).not.toContain("Gym");
  });

});

describe("RulesBudgetsPage save failures", () => {
  function rent(): Budget {
    return budget("Rent", { category_id: "cat-rent", amount: "800.00" });
  }

  it("keeps the editor open with the reason when saving the amount fails", async () => {
    const dom = renderDom(
      page([rent()], {
        onUpdateBudget: () => Promise.reject(new Error("Amount must be greater than zero")),
      }),
    );

    fireEvent.click(dom.getByTitle("Edit budget"));
    fireEvent.change(dom.getByTitle("Budget amount"), { target: { value: "0" } });
    await act(async () => {
      fireEvent.click(dom.getByText("Save"));
    });

    // The rename half is guarded; this is the other half. Unhandled, the editor closes
    // on a Save that did not happen -- or stays open showing the new amount as though
    // it had, with nothing on screen saying otherwise.
    expect(dom.queryByText(/greater than zero/)).not.toBeNull();
    expect(dom.queryByTitle("Budget amount")).not.toBeNull();
  });
});

describe("RulesBudgetsPage cancelled and scheduled rows", () => {
  /** Rent as the owner cancelled it: closed, and nothing has taken its place. */
  function cancelledRent(): Budget {
    return budget("Rent", {
      category_id: "cat-rent",
      active_to: "2026-09-30",
      active: false,
      status: "inactive",
      can_reactivate: true,
    });
  }

  /** Rent's previous amount, closed by a later budget rather than by the owner. The
   *  two read identically from the row alone, which is why the backend decides. */
  function supersededRent(): Budget {
    return budget("Rent", {
      budget_id: "budget-rent-old",
      category_id: "cat-rent",
      amount: "500.00",
      active_to: "2026-05-31",
      active: false,
      status: "inactive",
      can_reactivate: false,
    });
  }

  it("offers a restore on a budget the owner cancelled", () => {
    const dom = renderDom(page([cancelledRent()]));

    expect(dom.queryByTitle("Reactivate this budget")).not.toBeNull();
  });

  it("does not offer a restore the backend would always refuse", () => {
    const dom = renderDom(page([supersededRent()]));

    // Replaced by a later budget, so reopening is refused every time. Offered anyway,
    // the button looked like a no-op and the section grew one dead row per amount
    // change the category had ever had.
    expect(dom.queryByTitle("Reactivate this budget")).toBeNull();
  });

  it("shows a budget scheduled to start later and does not offer its category another", () => {
    // Created in October, read from September: the row covers no month yet, so it was
    // in neither list and invisible -- while its category was offered as unbudgeted,
    // and creating one is refused for overlapping.
    const scheduled = budget("Rent", {
      category_id: "cat-rent",
      active_from: "2026-10-01",
      active_to: null,
      active: false,
      status: "scheduled",
    });
    const dom = renderDom(page([scheduled], { month: "2026-09" }));

    expect(dom.queryByText(/Starting later/i)).not.toBeNull();
    fireEvent.click(dom.getByText("+ New"));
    const options = Array.from(dom.container.querySelectorAll("option")).map((node) => node.textContent);
    expect(options).not.toContain("Rent");
  });
});

describe("RulesBudgetsPage refusals", () => {
  function rent(): Budget {
    return budget("Rent", { category_id: "cat-rent" });
  }

  it("reports why a restore was refused", async () => {
    const cancelled = budget("Rent", {
      category_id: "cat-rent",
      active_to: "2026-09-30",
      active: false,
      status: "inactive",
      can_reactivate: true,
    });
    const dom = renderDom(
      page([cancelled], {
        onReactivateBudget: () =>
          Promise.reject(new Error("'Rent' has another budget starting 2026-11-01")),
      }),
    );

    await act(async () => {
      fireEvent.click(dom.getByTitle("Reactivate this budget"));
    });

    // The message names the budget in the way, which is the owner's way out. Dropped,
    // the click was indistinguishable from a no-op and they pressed it again.
    expect(dom.queryByText(/another budget starting 2026-11-01/)).not.toBeNull();
  });

  it("reports why a cancellation was refused", async () => {
    const dom = renderDom(
      page([rent()], { onDeactivateBudget: () => Promise.reject(new Error("Budget not found for id x")) }),
    );

    await act(async () => {
      fireEvent.click(dom.getByTitle(/Cancel this budget/));
    });

    expect(dom.queryByText(/Budget not found/)).not.toBeNull();
  });

  it("reports why a new budget was refused", async () => {
    const dom = renderDom(
      page([], {
        onCreateBudget: () =>
          Promise.reject(new Error("Budget periods must not overlap for the same category")),
      }),
    );

    fireEvent.click(dom.getByText("+ New"));
    fireEvent.change(dom.getByPlaceholderText("Amount (€/mo)"), { target: { value: "100" } });
    await act(async () => {
      fireEvent.click(dom.getByText("Add"));
    });

    expect(dom.queryByText(/must not overlap/)).not.toBeNull();
  });
});
