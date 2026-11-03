import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getTransactions } from "../src/lib/api";
import type { FiltersState } from "../src/types";

const API_BASE = "https://burnrate.test/api/v1";

const FILTERS: FiltersState = {
  month: "2026-10",
  accountId: "",
  categoryId: "",
  status: "",
  categorized: "",
  budgeted: "",
};

const PAGING = { limit: 25, offset: 0, total: 0 };

/** The URLs the module asked for, which is the only thing these tests look at. */
const urls: string[] = [];

beforeEach(() => {
  urls.length = 0;
  vi.stubGlobal("fetch", async (url: string) => {
    urls.push(url);
    return {
      ok: true,
      status: 200,
      json: async () => ({ transactions: [], total_count: 0, limit: 25, offset: 0 }),
    } as unknown as Response;
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function queryOf(url: string): URLSearchParams {
  return new URL(url).searchParams;
}

describe("getTransactions and the budget filter", () => {
  it("asks the backend for the month's spend that no budget covers", async () => {
    // The filter is decided in the backend, so the request is the whole of it: a
    // parameter that never leaves the browser leaves the owner looking at an
    // unfiltered page that looks perfectly correct.
    await getTransactions(API_BASE, { ...FILTERS, budgeted: "false" }, PAGING);

    expect(queryOf(urls[0]).get("budgeted")).toBe("false");
    expect(queryOf(urls[0]).get("month")).toBe("2026-10");
  });

  it("leaves the parameter off entirely when no budget filter is set", async () => {
    // `budgeted=` would reach the endpoint as an unparseable boolean, not as "no
    // filter", so an unset filter has to be absent rather than empty.
    await getTransactions(API_BASE, FILTERS, PAGING);

    expect(queryOf(urls[0]).has("budgeted")).toBe(false);
  });
});
