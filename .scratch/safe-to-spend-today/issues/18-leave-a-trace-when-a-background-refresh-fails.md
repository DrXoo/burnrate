# 18: Leave a trace when a background refresh fails

**What to build:** A payload for the month already on screen that is known to be out
of date looks exactly like a fresh one on the Categories page. Found by `/code-review`
on ticket 11, when it was true of the dashboard too; ticket 14 closed that half.

**Blocked by:** None

**Status:** recorded — a known defect, not scheduled

- [ ] On the Categories page, a payload for the month already on screen that is known to be out of date is distinguishable from a fresh one, or the decision to leave them alike is recorded

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

**A stale payload for the month already on screen is invisible.** The dashboard and the
Categories page each rendered their banner only when there was no payload at all, so a
failed refresh for the month being viewed showed the previous figures with no signal.
Ticket 11's third criterion asked the dashboard to match the Categories page here and it
did; this is the parity itself being weak, in both places at once. Whether that matters
is a product call: the figures are for the right month and merely a few minutes old,
which is a different claim from the wrong month's figures.

**The dashboard half is closed by ticket 14**, and not by choice: that ticket's own
decision requires a failed refresh to be reported twice, and `summaryError` marks
nothing while the page swallows it whenever a payload exists. `DashboardPage` now keeps
the figures and puts "These figures may be out of date" above them. So the product call
was forced for the one page where the toast alone would have faded and left an unmarked
number, and nowhere else.

**The Categories page is what is left.** Its notice still appears only when the month's
budget rows are unknown, so a failed refresh for the month on screen is silent there.
That page is a list the owner scans rather than a figure they act on, which is why
ticket 14's argument does not carry over to it on its own.

## Why this is recorded rather than scheduled

It is pre-existing and arguably not a defect at all: the figures are for the right month
and merely a few minutes old, which is a different claim from the wrong month's figures.
Deciding it needs a product call about what a few minutes of staleness is worth
announcing, not a bug fix. What remains after ticket 14 is narrower than what was
recorded — one page rather than two — and the question is now whether the Categories
page should match the dashboard, which is a parity call rather than an open defect.

## Testing

Ticket 14 brought Vitest, scoped to the hook with `lib/api` faked, so the runner exists
by the time this is taken. Whether a staleness marker needs a test depends on where it
lives: a banner is a rendering and goes through `react-dom/server` like the rest, while
a "this payload is older than N" rule in the hook belongs at the new seam. The dashboard
banner ticket 14 added took the former route; its `summaryError` half is covered at the
seam, by `marks the figures and reports it when a background refresh fails`.
