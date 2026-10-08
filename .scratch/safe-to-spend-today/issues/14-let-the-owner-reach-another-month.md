# 14: Let the owner reach another month

**What to build:** A month selector in the Web UI, so the past- and future-month
headlines this phase built are reachable by clicking rather than by editing a
default and rebuilding.

**Blocked by:** 11 (its month-label rules decide what a reached month is allowed to
claim, and this ticket is what makes those rules reachable)

**Status:** done

- [x] The owner can move to another month and stay there, and the selection survives a section change
- [x] The current month is reachable again in one action from any other month
- [x] No month is derived from a clock in the Web UI: the first load asks the backend which month is current, and `currentMonthValue()` is deleted
- [x] A refresh that resolves after the month has changed cannot write the month the owner has left
- [x] A background refresh that fails says so, where today it fails silently
- [x] Nothing financial is computed in the Web UI: the selector changes a query parameter
- [x] `web/` has a test runner, and the race above is its first test

## Why Phase 8 owes this

Decided at ticket 09's Definition of Done check. User stories 22 and 23 — the owner
"viewing a past month" and "viewing a future month" — are Phase 8 stories, and
ticket 07 implemented both headline states correctly. But no owner can reach either:
`filters.month` is initialised to `currentMonthValue()` in `useBurnRateData.ts` and
nothing ever assigns to it. All three `applyFilters` call sites are in
`TransactionsPage.tsx` and each spreads `...filters` while overriding only
`accountId`, `categoryId` or `categorized`. There is no `type="month"` input anywhere
in `web/src`. The month in `TopBar.tsx` is a read-only label, which is exactly what
makes the absence easy to miss.

So two of this phase's user stories shipped as code no user can run. That is the
argument for the ticket: a story nobody can reach is not delivered, and the backend
has supported `GET /api/v1/summary?month=` all along.

The reason it was not in the original ten tickets is that it reads as navigation
rather than as part of the metric, and it touches four pages. That makes it a ticket
of its own, not a correction on ticket 07.

## Settled by grilling

Thirteen decisions, taken before any code. Each is a branch somebody would otherwise
re-derive — and three of them correct this ticket's own text, which was written when
the month could not change.

### Where the month lives

**Hook state, not the URL.** The argument above for the query string was written
without the fact that **the section is not in the URL either**: `section` is
`useState<Section>("dashboard")` in `App.tsx`, and there is no router or router
dependency. The URL is used only transiently, for the bank-connect redirect, and wiped
with `replaceState`. So a shared link would restore the month and always land on the
dashboard, and the back button would step through months while the section stayed put.
Putting the month in the URL is half of a routing decision and the half with less
value. If deep links are ever wanted, that is a ticket that moves `section` there too.

**Arrows plus a native `<input type="month">`, unbounded.** Arrows cover the common
move, the input covers the long jump. No bounds: bounding needs a new API for the
earliest month with data, and a *future* month is worth visiting — that is where
standing orders land, which tickets 15 and 17 just made honest.

**The TopBar's month label becomes the reset to the current month**, which is the
third criterion. The selector and the label render on the five month-scoped sections
and are **hidden on Settings**, where a month means nothing — the label is already
noise there, and a control would be worse because it implies Settings responds to it.

**The review queue follows the selection**, which it already does since the hook
fetches it with `filters`. This diverges from the Telegram `/unknown`, which pins
itself to the current month on the reasoning that last month's leftovers are not
actionable. The divergence is deliberate: in a chat an inaccessible list is noise
pushed at the owner, on the web it is a table they asked to look at. Record it rather
than "fixing" either side.

### The client's clock goes away

**The first load sends no month, and the backend's answer decides it.** This is the
only option that removes the clock rather than correcting it afterwards.

**It has to be a two-phase load, and this is the fact the original plan missed:**
omitting the month only has a current-month default on `/summary`. On
`/transactions`, `/transactions/uncategorized` and `.../count` it means **every month
ever** — verified against the service, 3 rows against 1. So: fetch the summary, learn
`current_month`, then fetch the three ledger views with it. Those views already have a
loading state; this is that state for a moment longer, not a new blank screen.

**Empty means "the month the backend calls current", always.** One rule, not two: a
native month input can always be cleared from the keyboard, so the code answers `""`
regardless, and after the first load the fallback is `summary.current_month` rather
than a clock.

**The redundant `/summary` is accepted.** Phase two re-fetches it, so a page load
costs one extra GET. The alternative is a freshness rule in the one effect the whole
screen depends on, and "I hold a summary for this month" is not the same claim as
"this summary is current" — conflating those is the shape of ticket 18's third defect.

**`currentMonthValue()` and `currentMonthStart()` both get deleted.** They are the
frontend's last clock, and leaving either invites its reuse.

### Concurrency, absorbed from ticket 18

**This ticket fixes ticket 18's first two defects**, because the selector is what makes
them reachable. `refreshLedgerViews` has no `catch` and no `cancelled` guard, and it
closes over `filters` from the render that created it: categorize a transaction, change
month, and the stale response writes the previous month's summary, which ticket 11's
gate then withholds — "This month's figures are not available yet", with nothing to
retry. `loadViews` is already guarded and needs nothing.

**A failed background refresh reports itself twice, and both are needed.** A toast,
because the action it followed *did* succeed and the owner needs to know that; and
`summaryError`, because the figures on screen are no longer trustworthy. With only the
banner the owner cannot tell whether their change saved; with only the toast it fades
in 2.2 seconds and leaves stale figures unmarked.

Ticket 18 keeps only its third defect — a stale payload for the month already on
screen, invisible on both pages. Pre-existing, in two places, and that file itself
doubts it is a defect.

### What this corrects in the text above

* **The second criterion is gone.** It described pages each keeping their own idea of
  the month; they do not. The hook does every fetch, and the month reaches the UI in
  three places: the TopBar label twice and one prop to `CategoriesPage`.
* **`CategoriesPage`'s `month` prop is dormant, not dead.** It keys the effect at line
  96 that reloads the month's transactions, and `loadMonthTransactions()` reads
  `filters.month` internally. It becomes load-bearing the moment the month can change,
  so dropping it — as the note below suggested — would leave that page showing the
  previous month's per-category lists. **It stays.**
* **`applyFilters`' coercion stays but changes target**, from `currentMonthValue()` to
  `summary.current_month`. It also already resets both paging offsets, which a month
  change wants; the account, category and status filters are orthogonal and survive.

## Testing

**`web/` gains Vitest**, scoped as narrowly as it can be: the hook, with `lib/api`
faked. The race is what is actually at stake — which state survives when two responses
land out of order — and that is observable in the value the hook returns. Faking
`fetch` instead would buy coverage of `buildQuery` at the cost of tests that break when
a query parameter is renamed, which is the coupling `tdd` warns about.

This is a **fifth seam**, and the spec says four with "no test is written anywhere
else". Recorded in the spec's Testing Decisions rather than added quietly, and it is
material for `/distill-decisions`.

Page rendering stays ad-hoc for this ticket — type check plus `react-dom/server`, as
tickets 07, 11 and 16 did. Page tests are the obvious next use of the runner, written
down here so that next time it is a decision and not a discovery.

## Absorbed from `/code-review`

Two defects in this ticket's own code, both found after the first green run and both
fixed here rather than handed on. Each has a test at the fifth seam.

**A refresh with no month resolved asked for every month ever.** `refreshLedgerViews`
did not get the `!filters.month` guard its two siblings did, so an edit landing inside
the two-phase load's window fetched the three ledger views unscoped — every transaction
ever, plus the all-time uncategorized count — and committed them. The stale-month gate
waved it through, because `""` was both the month requested and the month still
selected. Sync sits in the health strip on every section, so the window is reachable
after boot and again after every reset of the month. Now it declines to ask: the
loader's second phase is about to fetch the month's views, so nothing is lost.
Covered by `will not ask the ledger views for every month ever while no month is
resolved`, which counts the unscoped reads at the faked boundary — the answer such a
read gets is correct and useless, so the only observable mistake is the question.

**A first load whose opening summary failed could not be retried.** The catch recorded
the error and left the month `""`, and no dep of the loader changed again, so the month
was never resolved: the label read "Loading month…" for ever, the arrows were disabled
for want of a month to step from, and on Settings the selector is not rendered at all.
Recovery meant the native month input or a reload. The loader now takes a
`reloadToken` that every `applyFilters` bumps, so asking for the same month again
re-runs it — and the one month that could not be re-asked for was exactly `""`. The
label is the control that asks, so when the month is unresolved *and* errored it reads
"Month unavailable — retry" instead of claiming to be loading. Covered by `can be asked
again for the current month after the opening summary failed`.

The side effect of the token is that re-selecting an unchanged filter now refetches
rather than doing nothing. That is wanted: "ask again" is the only thing the owner can
mean by re-picking the month they are already on.
