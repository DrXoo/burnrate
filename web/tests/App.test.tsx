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
