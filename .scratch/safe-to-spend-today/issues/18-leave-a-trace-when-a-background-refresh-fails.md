# 18: Leave a trace when a background refresh fails

**What to build:** A payload for the month already on screen that is known to be out
of date looks exactly like a fresh one, on both the dashboard and the Categories page.
Found by `/code-review` on ticket 11.

**Blocked by:** None

**Status:** recorded — a known defect, not scheduled

- [ ] A payload for the month already on screen that is known to be out of date is distinguishable from a fresh one, or the decision to leave them alike is recorded

## Scope was cut by ticket 14's grilling

This file originally carried three defects. **The first two moved to ticket 14** and are
fixed there, because a month selector is what makes them reachable and shipping the
selector without them would have shipped a known defect: `refreshLedgerViews` had no
`catch` and no `cancelled` guard, so a rejection was silent and a response arriving
after a month change wrote the month the owner had left. Ticket 14 also settled how a
failed refresh reports itself — a toast for "your change saved, the refresh did not",
plus `summaryError` for "these figures are no longer trustworthy".

What is left is the third, below. It is the one that was always reachable and the one
that may not be a defect at all.

## The defect

**A stale payload for the month already on screen is invisible on both pages.** The
dashboard and the Categories page each render their banner only when there is no
payload at all, so a failed refresh for the month being viewed shows the previous
figures with no signal. Ticket 11's third criterion asked the dashboard to match the
Categories page here and it does; this is the parity itself being weak, in both places
at once. Whether that matters is a product call: the figures are for the right month
and merely a few minutes old, which is a different claim from the wrong month's figures.

## Why this is recorded rather than scheduled

It is pre-existing in both pages and arguably not a defect at all: the figures are for
the right month and merely a few minutes old, which is a different claim from the wrong
month's figures. Deciding it needs a product call about what a few minutes of staleness
is worth announcing, not a bug fix.

## Testing

Ticket 14 brings Vitest, scoped to the hook with `lib/api` faked, so the runner exists
by the time this is taken. Whether a staleness marker needs a test depends on where it
lives: a banner is a rendering and goes through `react-dom/server` like the rest, while
a "this payload is older than N" rule in the hook belongs at the new seam.
