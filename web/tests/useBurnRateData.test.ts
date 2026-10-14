import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { budget, fakeApi, transaction } from "./fakeApi";
import { useBurnRateData } from "../src/hooks/useBurnRateData";

vi.mock("../src/lib/api", () => import("./fakeApi"));

type BurnRateData = ReturnType<typeof useBurnRateData>;
type Rendered = { current: BurnRateData };

async function settled(result: Rendered): Promise<void> {
  await waitFor(() => {
    expect(result.current.summaryLoading).toBe(false);
    expect(result.current.transactions.loading).toBe(false);
  });
}

function descriptions(data: BurnRateData): (string | null)[] {
  return data.transactions.items.map((row) => row.description);
}

function budgetedCategories(data: BurnRateData): string[] {
  // Null means the month's list has not arrived. Every caller here expects it to
  // have, and asserts against the rows it should hold.
  return (data.budgets ?? []).map((row) => row.category_name);
}

beforeEach(() => {
  fakeApi.reset();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("useBurnRateData", () => {
  it("opens on the month the backend calls current, not on one read off a clock", async () => {
    fakeApi.setCurrentMonth("2031-03");
    fakeApi.setMonth("2031-03", { transactions: [transaction("t-mar", "March dinner")] });
    fakeApi.setMonth("2030-12", { transactions: [transaction("t-dec", "December dinner")] });

    const { result } = renderHook(() => useBurnRateData());
    await settled(result);

    expect(result.current.filters.month).toBe("2031-03");
    expect(result.current.summary?.month).toBe("2031-03");
    // An unscoped ledger read would answer with every month ever, March and December both.
    expect(descriptions(result.current)).toEqual(["March dinner"]);
  });

  it("will not let a refresh for the month the owner left overwrite the one they reached", async () => {
    fakeApi.setMonth("2026-10", {
      transactions: [transaction("t-oct", "October dinner")],
      unknownQueue: [transaction("t-oct", "October dinner")],
    });
    fakeApi.setMonth("2026-09", { transactions: [transaction("t-sep", "September dinner")] });

    const { result } = renderHook(() => useBurnRateData());
    await settled(result);
    expect(descriptions(result.current)).toEqual(["October dinner"]);

    // Categorizing refreshes the ledger views in the background. Hold October's
    // answers open so that refresh is still in flight when the month changes.
    fakeApi.holdReads("2026-10");
    const refreshForOctober = result.current.categorizeTransaction("t-oct", "cat-1");

    await act(async () => {
      result.current.applyFilters({ ...result.current.filters, month: "2026-09" });
    });
    await settled(result);

    fakeApi.resumeReads("2026-10");
    await act(async () => {
      await refreshForOctober;
    });

    expect(result.current.filters.month).toBe("2026-09");
    expect(descriptions(result.current)).toEqual(["September dinner"]);
    expect(result.current.summary?.month).toBe("2026-09");
    expect(result.current.uncategorizedCount).toBe(0);
  });

  it("marks the figures and reports it when a background refresh fails", async () => {
    fakeApi.setMonth("2026-10", { transactions: [transaction("t-oct", "October dinner")] });
    const reported: string[] = [];

    const { result } = renderHook(() =>
      useBurnRateData({ onRefreshFailed: (message) => reported.push(message) }),
    );
    await settled(result);

    fakeApi.failReads("2026-10", "Request failed (503): upstream unavailable");
    // The edit itself landed, so it must not surface as a failed edit.
    await act(async () => {
      await result.current.categorizeTransaction("t-oct", "cat-1");
    });

    expect(result.current.summaryError).toContain("503");
    expect(reported).toEqual([expect.stringContaining("503")]);
    // The figures the owner was looking at stay on screen, marked rather than blanked.
    expect(descriptions(result.current)).toEqual(["October dinner"]);
  });

  it("returns to the month the backend calls current when the selection is cleared", async () => {
    fakeApi.setMonth("2026-10", { transactions: [transaction("t-oct", "October dinner")] });
    fakeApi.setMonth("2026-09", { transactions: [transaction("t-sep", "September dinner")] });

    const { result } = renderHook(() => useBurnRateData());
    await settled(result);

    await act(async () => {
      result.current.applyFilters({ ...result.current.filters, month: "2026-09" });
    });
    await settled(result);
    expect(descriptions(result.current)).toEqual(["September dinner"]);

    // What the month label's reset does, and what a native month input emptied from
    // the keyboard sends: one rule, resolved over the wire rather than off a clock.
    await act(async () => {
      result.current.applyFilters({ ...result.current.filters, month: "" });
    });
    await waitFor(() => expect(result.current.filters.month).toBe("2026-10"));
    await settled(result);
    expect(descriptions(result.current)).toEqual(["October dinner"]);
  });

  it("will not ask the ledger views for every month ever while no month is resolved", async () => {
    fakeApi.setMonth("2026-10", { transactions: [transaction("t-oct", "October dinner")] });
    fakeApi.setMonth("2026-09", { transactions: [transaction("t-sep", "September dinner")] });

    // Park the opening summary, which is the window a Sync or an account toggle sits in
    // right after boot and again after a reset: no month is resolved yet.
    fakeApi.holdReads("");
    const { result } = renderHook(() => useBurnRateData());
    await waitFor(() => expect(result.current.bootLoading).toBe(false));

    let refreshWithNoMonth!: Promise<void>;
    await act(async () => {
      refreshWithNoMonth = result.current.categorizeTransaction("t-oct", "cat-1");
    });

    fakeApi.resumeReads("");
    await act(async () => {
      await refreshWithNoMonth;
    });
    await settled(result);

    // An omitted month means every month ever on these three views, so the refresh has
    // to decline to ask rather than ask and throw the answer away.
    expect(fakeApi.unscopedLedgerReads()).toBe(0);
    expect(descriptions(result.current)).toEqual(["October dinner"]);
    expect(result.current.transactions.total).toBe(1);
  });

  it("can be asked again for the current month after the opening summary failed", async () => {
    fakeApi.setMonth("2026-10", { transactions: [transaction("t-oct", "October dinner")] });
    fakeApi.failReads("", "Request failed (503): upstream unavailable");

    const { result } = renderHook(() => useBurnRateData());
    await waitFor(() => expect(result.current.summaryError).toContain("503"));
    expect(result.current.filters.month).toBe("");

    // What the top bar's month label asks for. It is the only thing that can ask while
    // no month is resolved -- the arrows are disabled until one is -- so a first load
    // that failed has to be retryable through exactly this call.
    fakeApi.healReads("");
    await act(async () => {
      result.current.applyFilters({ ...result.current.filters, month: "" });
    });

    await waitFor(() => expect(result.current.filters.month).toBe("2026-10"));
    await settled(result);
    expect(descriptions(result.current)).toEqual(["October dinner"]);
    expect(result.current.summaryError).toBeNull();
  });

  it("reads the budget list for the month on screen, not for the month the owner is in", async () => {
    // The owner stopped renting during October, so Rent covers September and not
    // October. The list was fetched once at boot and never again on a month change,
    // so September showed October's budgets while September's summary counted Rent --
    // two readings of one month, contradicting each other.
    fakeApi.setMonth("2026-10", { budgets: [budget("Gym")] });
    fakeApi.setMonth("2026-09", { budgets: [budget("Rent"), budget("Gym")] });

    const { result } = renderHook(() => useBurnRateData());
    await settled(result);
    expect(budgetedCategories(result.current)).toEqual(["Gym"]);

    await act(async () => {
      result.current.applyFilters({ ...result.current.filters, month: "2026-09" });
    });
    await settled(result);

    expect(budgetedCategories(result.current)).toEqual(["Rent", "Gym"]);
  });

  it("cancels a budget in the month on screen, not the month the owner is in", async () => {
    fakeApi.setMonth("2026-10", { budgets: [budget("Rent")] });
    fakeApi.setMonth("2026-09", { budgets: [budget("Rent")] });

    const { result } = renderHook(() => useBurnRateData());
    await settled(result);
    await act(async () => {
      result.current.applyFilters({ ...result.current.filters, month: "2026-09" });
    });
    await settled(result);

    await act(async () => {
      await result.current.deactivateBudget("budget-rent");
    });

    // September is where the click was made, so September is what changed. The row
    // stays listed -- cancelling never deletes it -- so what moved is its status.
    expect((result.current.budgets ?? []).map((row) => row.status)).toEqual(["inactive"]);

    // And October is untouched, which a cancel sent with the owner's own month
    // would have hit instead.
    await act(async () => {
      result.current.applyFilters({ ...result.current.filters, month: "2026-10" });
    });
    await settled(result);
    expect((result.current.budgets ?? []).map((row) => row.status)).toEqual(["active"]);
  });

  it("shows a renamed category on its budget row without a reload", async () => {
    fakeApi.setCategories([
      { category_id: "cat-rent", name: "Rent", type: "expense", active: true },
    ]);
    fakeApi.setMonth("2026-10", { budgets: [budget("Rent", { category_id: "cat-rent" })] });

    const { result } = renderHook(() => useBurnRateData());
    await settled(result);
    expect(budgetedCategories(result.current)).toEqual(["Rent"]);

    await act(async () => {
      await result.current.renameCategory("cat-rent", "Housing");
    });

    // Both surfaces, because the name lives in one place: the budget row reads it
    // through the join, and the category list is where it was edited.
    expect(budgetedCategories(result.current)).toEqual(["Housing"]);
    expect(result.current.categories.map((category) => category.name)).toEqual(["Housing"]);
  });

  it("drops a deleted category from the list without a reload", async () => {
    fakeApi.setCategories([
      { category_id: "cat-typo", name: "Fodo", type: "expense", active: true },
      { category_id: "cat-food", name: "Food", type: "expense", active: true },
    ]);

    const { result } = renderHook(() => useBurnRateData());
    await settled(result);

    await act(async () => {
      await result.current.deleteCategory("cat-typo");
    });

    expect(result.current.categories.map((category) => category.name)).toEqual(["Food"]);
  });

  it("keeps an archived category listed, marked inactive, and out of the assignable set", async () => {
    fakeApi.setCategories([
      { category_id: "cat-gym", name: "Gym", type: "expense", active: true },
      { category_id: "cat-food", name: "Food", type: "expense", active: true },
    ]);

    const { result } = renderHook(() => useBurnRateData());
    await settled(result);

    await act(async () => {
      await result.current.archiveCategory("cat-gym");
    });

    // Still listed: archiving is not deleting, and there has to be a way back.
    expect(result.current.categories.map((category) => category.name)).toEqual(["Gym", "Food"]);
    // But closed to new spend, which is the only reason to archive it.
    expect(result.current.assignableCategories.map((category) => category.name)).toEqual(["Food"]);

    await act(async () => {
      await result.current.unarchiveCategory("cat-gym");
    });

    expect(result.current.assignableCategories.map((category) => category.name)).toEqual(["Gym", "Food"]);
  });

  it("puts a reactivated budget back in the month on screen", async () => {
    // The owner cancelled Pharmacy by mistake, so October dropped it. Undoing that
    // has to show up in the month they are looking at, not only in the row the
    // endpoint answered with -- the list is what they are reading.
    fakeApi.setMonth("2026-10", {
      budgets: [budget("Pharmacy", { active_to: "2026-09-30", active: false, status: "inactive" })],
    });

    const { result } = renderHook(() => useBurnRateData());
    await settled(result);
    expect(result.current.budgets?.map((row) => row.status)).toEqual(["inactive"]);

    await act(async () => {
      await result.current.reactivateBudget("budget-pharmacy");
    });

    expect(result.current.budgets?.map((row) => row.status)).toEqual(["active"]);
  });
});
