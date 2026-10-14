import { act, cleanup, fireEvent, render as renderDom } from "@testing-library/react";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it } from "vitest";

import { summaryFor } from "./fakeApi";
import { CategoriesPage } from "../src/components/pages/CategoriesPage";
import type { Category } from "../src/types";

const FOOD: Category = { category_id: "cat-food", name: "Food", type: "expense", active: true };
const GYM_ARCHIVED: Category = { category_id: "cat-gym", name: "Gym", type: "expense", active: false };

interface PageProps {
  error?: string | null;
  loading?: boolean;
  withSummary?: boolean;
  categories?: Category[];
  onRenameCategory?: (categoryId: string, name: string) => Promise<void>;
  onDeleteCategory?: (categoryId: string) => Promise<void>;
  onArchiveCategory?: (categoryId: string) => Promise<void>;
  onUnarchiveCategory?: (categoryId: string) => Promise<void>;
}

function page(props: PageProps) {
  return (
    <CategoriesPage
      categories={props.categories ?? [FOOD]}
      summary={props.withSummary === false ? null : summaryFor("2026-10")}
      loading={props.loading ?? false}
      error={props.error ?? null}
      month="2026-10"
      monthLabel="October 2026"
      loadMonthTransactions={() => Promise.resolve([])}
      onCreateCategory={() => Promise.resolve()}
      onRenameCategory={props.onRenameCategory ?? (() => Promise.resolve())}
      onDeleteCategory={props.onDeleteCategory ?? (() => Promise.resolve())}
      onArchiveCategory={props.onArchiveCategory ?? (() => Promise.resolve())}
      onUnarchiveCategory={props.onUnarchiveCategory ?? (() => Promise.resolve())}
    />
  );
}

function render(props: PageProps): string {
  return renderToStaticMarkup(page(props));
}

afterEach(() => {
  cleanup();
});

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

describe("CategoriesPage renaming", () => {
  function openRename(dom: ReturnType<typeof renderDom>) {
    fireEvent.click(dom.getByTitle("Rename category"));
    return dom.getByTitle("Category name") as HTMLInputElement;
  }

  it("renames the selected category from its own panel", async () => {
    const renames: Array<[string, string]> = [];
    const dom = renderDom(
      page({
        onRenameCategory: (categoryId, name) => {
          renames.push([categoryId, name]);
          return Promise.resolve();
        },
      }),
    );

    const nameInput = openRename(dom);
    expect(nameInput.value).toBe("Food");
    fireEvent.change(nameInput, { target: { value: "  Groceries  " } });
    await act(async () => {
      fireEvent.click(dom.getByText("Save"));
    });

    // Trimmed before it leaves the page: the backend normalizes too, but a name sent
    // with its padding makes the two disagree about what was asked for.
    expect(renames).toEqual([["cat-food", "Groceries"]]);
  });

  it("keeps the rename open with the reason when the name is already taken", async () => {
    const dom = renderDom(
      page({ onRenameCategory: () => Promise.reject(new Error("Category 'Rent' already exists")) }),
    );

    const nameInput = openRename(dom);
    fireEvent.change(nameInput, { target: { value: "Rent" } });
    await act(async () => {
      fireEvent.click(dom.getByText("Save"));
    });

    expect(dom.queryByText(/already exists/)).not.toBeNull();
    expect((dom.getByTitle("Category name") as HTMLInputElement).value).toBe("Rent");
  });

  it("will not send a blank name", async () => {
    let renamed = false;
    const dom = renderDom(
      page({
        onRenameCategory: () => {
          renamed = true;
          return Promise.resolve();
        },
      }),
    );

    const nameInput = openRename(dom);
    fireEvent.change(nameInput, { target: { value: "   " } });
    await act(async () => {
      fireEvent.click(dom.getByText("Save"));
    });

    expect(renamed).toBe(false);
  });
});

describe("CategoriesPage archiving and deleting", () => {
  it("archives the selected category", async () => {
    const archived: string[] = [];
    const dom = renderDom(
      page({
        onArchiveCategory: (categoryId) => {
          archived.push(categoryId);
          return Promise.resolve();
        },
      }),
    );

    await act(async () => {
      fireEvent.click(dom.getByText("Archive"));
    });

    expect(archived).toEqual(["cat-food"]);
  });

  it("offers the way back on an archived category, and says it is archived", async () => {
    const restored: string[] = [];
    const dom = renderDom(
      page({
        categories: [GYM_ARCHIVED],
        onUnarchiveCategory: (categoryId) => {
          restored.push(categoryId);
          return Promise.resolve();
        },
      }),
    );

    // Marked, or an archived category reads exactly like a live one and the owner
    // files spend against something they thought they had retired.
    expect(dom.queryByText("Archived")).not.toBeNull();
    // And no Archive button, which would be a no-op on a row already archived.
    expect(dom.queryByText("Archive")).toBeNull();

    await act(async () => {
      fireEvent.click(dom.getByText("Unarchive"));
    });

    expect(restored).toEqual(["cat-gym"]);
  });

  it("asks before deleting, and does not delete until the second click", async () => {
    const deleted: string[] = [];
    const dom = renderDom(
      page({
        onDeleteCategory: (categoryId) => {
          deleted.push(categoryId);
          return Promise.resolve();
        },
      }),
    );

    await act(async () => {
      fireEvent.click(dom.getByText("Delete"));
    });
    // One click arms it. Deleting is the one act on this page with no way back, and
    // it sits next to Archive, which has one.
    expect(deleted).toEqual([]);

    await act(async () => {
      fireEvent.click(dom.getByText("Delete for good"));
    });
    expect(deleted).toEqual(["cat-food"]);
  });

  it("reports why a category could not be deleted", async () => {
    const dom = renderDom(
      page({
        onDeleteCategory: () =>
          Promise.reject(new Error("Category 'Food' is still used by 31 transactions and 1 budget")),
      }),
    );

    await act(async () => {
      fireEvent.click(dom.getByText("Delete"));
    });
    await act(async () => {
      fireEvent.click(dom.getByText("Delete for good"));
    });

    // The reason names what to clear first, so it has to reach the screen intact.
    expect(dom.queryByText(/still used by 31 transactions and 1 budget/)).not.toBeNull();
  });

  it("reports why a category could not be archived", async () => {
    const dom = renderDom(
      page({
        onArchiveCategory: () =>
          Promise.reject(
            new Error("Category 'Gym' cannot be archived yet: it has a budget for this month or later"),
          ),
      }),
    );

    await act(async () => {
      fireEvent.click(dom.getByText("Archive"));
    });

    expect(dom.queryByText(/budget for this month or later/)).not.toBeNull();
  });
});

describe("CategoriesPage list", () => {
  it("marks an archived category in the list, not only in its panel", () => {
    const markup = renderToStaticMarkup(page({ categories: [FOOD, GYM_ARCHIVED] }));

    // The list is what the owner scans. A row that reads like a live category invites
    // them to pick it and wonder why it offers no budget.
    expect(markup).toContain("archived");
  });
});
