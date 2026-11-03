import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { connection, fakeApi } from "./fakeApi";
import App from "../src/App";

vi.mock("../src/lib/api", () => import("./fakeApi"));

// Five seconds after the sync in fakeApi's SYNCED_AT, and a day and a half after the
// stale timestamp the fixture connection carries. Pinned because "Synced <n> ago" is
// read off the clock: against the real one these assertions would mean something
// different every day the suite runs.
const NOW = new Date("2026-10-30T10:30:14Z").getTime();

/** The app, settled far enough that the health strip's Sync button is on screen. */
async function openApp(): Promise<HTMLElement> {
  render(<App />);
  return screen.findByRole("button", { name: /Sync now/ });
}

beforeEach(() => {
  fakeApi.reset();
  vi.spyOn(Date, "now").mockReturnValue(NOW);
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("App — manual sync", () => {
  it("names the reason a manual sync failed, and leaves the timestamp as it was", async () => {
    fakeApi.setConnection(connection());
    fakeApi.failSync("conn-1", "Request failed (502): The bank service returned an error.");

    const button = await openApp();
    await act(async () => {
      fireEvent.click(button);
    });

    // The reason has to reach the owner: a sync that never left the browser looked
    // exactly like one that ran and found nothing.
    const toast = await screen.findByText(/Sync failed/);
    expect(toast.textContent).toContain("502");
    // And nothing may imply it worked. The strip keeps the timestamp it had.
    expect(screen.getByText("Synced 1 d ago")).toBeTruthy();
    expect(screen.queryByText(/Synced —/)).toBeNull();
  });

  it("does not call a spent bank allowance a broken bank", async () => {
    fakeApi.setConnection(connection());
    // What the backend sends for ASPSP_RATE_LIMIT_EXCEEDED: a structured detail, because
    // the status cannot carry it -- 429 is BurnRate's own click limiter and 503 is a
    // backend with no password set.
    fakeApi.failSync("conn-1", "Request failed (503): rate limited", {
      code: "bank_rate_limit",
      message:
        "This bank's daily allowance for automatic checks is used up. Syncing resumes " +
        "on its own, and nothing is lost -- the next successful sync still fetches " +
        "everything since.",
    });

    const button = await openApp();
    await act(async () => {
      fireEvent.click(button);
    });

    // The backend's own words reach the owner. "Sync failed -- Request failed (503)"
    // said the bank was broken when the truth was "wait", and those call for opposite
    // reactions.
    const toast = await screen.findByText(/daily allowance/);
    expect(toast.textContent).toContain("nothing is lost");
    expect(screen.queryByText(/Sync failed/)).toBeNull();
    expect(screen.queryByText(/503/)).toBeNull();
    // Still nothing may imply it worked: the strip keeps the timestamp it had.
    expect(screen.getByText("Synced 1 d ago")).toBeTruthy();
    expect(screen.queryByText(/Synced —/)).toBeNull();
  });

  it("says what a sync that landed brought in, and shows the new timestamp", async () => {
    fakeApi.setConnection(connection());

    const button = await openApp();
    await act(async () => {
      fireEvent.click(button);
    });

    expect((await screen.findByText(/Synced —/)).textContent).toContain("2 new transaction");
    // Only the fake's own store knows the new timestamp, so this fails unless the
    // connection was refetched after the sync.
    expect(screen.getByText("Synced just now")).toBeTruthy();
    // The row whose button was pressed is the one that was synced.
    expect(fakeApi.syncRequests()).toEqual(["conn-1"]);
  });

  it("distinguishes a sync that found nothing from one that did not run", async () => {
    fakeApi.setConnection(connection());
    fakeApi.setSyncImports(0);

    const button = await openApp();
    await act(async () => {
      fireEvent.click(button);
    });

    expect((await screen.findByText(/Synced —/)).textContent).toContain("nothing new");
  });
});
