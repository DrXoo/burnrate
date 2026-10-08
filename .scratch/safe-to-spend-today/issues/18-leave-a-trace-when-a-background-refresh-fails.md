# 18: Leave a trace when a background refresh fails

**What to build:** A payload for the month already on screen that is known to be out
of date looks exactly like a fresh one on the Categories page. Found by `/code-review`
on ticket 11, when it was true of the dashboard too; ticket 14 closed that half.

**Blocked by:** None

**Status:** closed

- [x] On the Categories page, a payload for the month already on screen that is known to be out of date is distinguishable from a fresh one, or the decision to leave them alike is recorded

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

## The product call, and what was built

**The call went to parity: the Categories page marks it too.** The argument for leaving
it alone was that the page is a list the owner scans rather than a figure they act on.
What overrode it is that the page does not only list categories — it prints each one's
budget, spend and remaining, and the detail panel prints them again at 21px. Those are
figures the owner acts on, so the dashboard's reasoning does carry over: the toast that
reported the failure has faded by the time they are read.

Leaving the two pages unlike would also have meant the same failed refresh is announced
on one page and silent on the other, which is a worse story than either page's
treatment on its own.

**What changed.** `CategoriesPage`'s notice was rendered only when the month's budget
rows were unknown; the error was swallowed whenever a payload existed. The three states
are now decided in one place, `budgetNotice`, which returns the line to print and
whether it is an alert or an information notice:

* rows on screen, no error — no notice
* rows on screen, refresh failed — "These budget figures may be out of date — {error}"
* no rows, loading — "Loading budgets for {month}…"
* no rows, failed — "Budget figures unavailable: {error}"

The third and fourth were the existing behaviour and are unchanged. The distinction the
ticket turned on is kept explicit: a month with no rows at all is told apart from one
whose rows are a few minutes old, because there is nothing on screen that could be out
of date.

## Why this was originally recorded rather than scheduled

It is pre-existing and arguably not a defect at all: the figures are for the right month
and merely a few minutes old, which is a different claim from the wrong month's figures.
Deciding it needs a product call about what a few minutes of staleness is worth
announcing, not a bug fix. What remains after ticket 14 is narrower than what was
recorded — one page rather than two — and the question is now whether the Categories
page should match the dashboard, which is a parity call rather than an open defect.

## Testing

**A sixth seam was added: page rendering through `react-dom/server`.** Ticket 14 left
page tests off the seam list and said taking them should stay a decision rather than a
discovery; this ticket is that decision, recorded in the spec's Testing Decisions. It
was unavoidable here — the whole subject is one branch of one render, and nothing below
a render can observe whether a notice appears.

`web/tests/CategoriesPage.test.tsx`, three tests, all on owner-facing wording:

* `marks the budget figures when a background refresh fails for the month on screen` —
  the defect, red before the fix
* `leaves a fresh payload for the month on screen unmarked` — the other half of
  "distinguishable"; green on arrival, kept as the guard against a notice that is
  always on
* `calls the month's budgets unavailable rather than stale when no rows arrived at all` —
  green on arrival, guarding the two pre-existing states through the restructure

`vitest.config.ts` now collects `.tsx` as well, and `fakeApi.summaryFor` is exported so
both test files share one `SummaryDashboard` fixture.

### What was written before the decision above

Ticket 14 brought Vitest, scoped to the hook with `lib/api` faked, so the runner exists
by the time this is taken. Whether a staleness marker needs a test depends on where it
lives: a banner is a rendering and goes through `react-dom/server` like the rest, while
a "this payload is older than N" rule in the hook belongs at the new seam. The dashboard
banner ticket 14 added took the former route; its `summaryError` half is covered at the
seam, by `marks the figures and reports it when a background refresh fails`.
