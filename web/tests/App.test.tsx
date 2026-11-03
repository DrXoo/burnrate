import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { connection, fakeApi } from "./fakeApi";
import App from "../src/App";

vi.mock("../src/lib/api", () => import("./fakeApi"));

// A day and a half after the stale timestamp the fixture connection carries. Pinned
// because "Synced <n> ago" is read off the clock: against the real one these
// assertions would mean something different every day the suite runs.
const NOW = new Date("2026-10-30T10:30:14Z").getTime();

/** The app, settled far enough that the health strip *and* the summary behind it have
    arrived. Waiting on the strip alone is not enough: it renders from the connection,
    and the next-sync line comes from `/summary`, so an assertion made in between would
    read "no next sync" whether the rule works or not. */
async function openApp(): Promise<HTMLElement> {
  render(<App />);
  await screen.findByText("€40.00");
  return screen.findByText(/^Synced /);
}

beforeEach(() => {
  fakeApi.reset();
  vi.spyOn(Date, "now").mockReturnValue(NOW);
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("App — syncing is the worker's job alone", () => {
  it("offers nothing to press, anywhere", async () => {
    fakeApi.setConnection(connection());

    await openApp();

    // The button promised an immediacy no bank here delivers -- pending rows never
    // arrive and a booked one takes one to three days -- while spending accesses out
    // of the four-per-day budget the scheduled passes need. ADR-0015.
    expect(screen.queryByRole("button", { name: /Sync/ })).toBeNull();
    expect(fakeApi.syncRequests()).toEqual([]);
  });

  it("says when the next pass is due, in the hour the backend named", async () => {
    fakeApi.setConnection(connection());
    fakeApi.setNextSync("2026-10-30T21:00:00+01:00");

    const strip = await openApp();

    // With no button, the schedule is the only answer the owner has to "when does
    // this refresh?". The hour is the backend's, offset and all: a client that read
    // it as an instant and re-rendered it in its own zone would show an hour nobody
    // configured.
    expect(strip.textContent).toBe("Synced 1 d ago · next at 21:00");
  });

  it("promises no next pass while the connection needs attention", async () => {
    // The schedule and the state deliberately disagree: a sync is due in ten minutes
    // and the last one failed. Without the disagreement the rule has no test -- a
    // fixture with no next sync would pass whether the rule existed or not.
    fakeApi.setConnection(connection({ latest_sync_error_summary: "Bank session closed" }));
    fakeApi.setNextSync("2026-10-30T11:40:00+01:00");

    const strip = await openApp();

    // "Next at 11:40" during an outage is the product reassuring the owner at exactly
    // the moment it should not: a worker that is not running cannot contradict it,
    // which is ADR-0013's own premise. What they need here is the error.
    expect(strip.textContent).toBe("Synced 1 d ago");
    expect(screen.getByText(/Needs attention/)).toBeTruthy();
  });

  it("invents no schedule when the backend published none", async () => {
    fakeApi.setConnection(connection());
    fakeApi.setNextSync(null);

    expect((await openApp()).textContent).toBe("Synced 1 d ago");
  });
});
