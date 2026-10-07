# 18: Leave a trace when a background refresh fails

**What to build:** A background refresh that fails changes nothing on screen and
reports nothing anywhere. Found by `/code-review` on ticket 11.

**Blocked by:** None

**Status:** recorded — a known defect, not scheduled

- [ ] A failed background refresh reports itself, as the initial load already does
- [ ] A refresh that resolves after the month has changed does not overwrite the newer month's state
- [ ] A month left with no payload and no error has a way back that does not require a reload
- [ ] A payload for the month already on screen that is known to be out of date is distinguishable from a fresh one, or the decision to leave them alike is recorded

## The defects, which are three in one family

**`refreshLedgerViews` has no `catch`.** It awaits four requests, and on a rejection
leaves `summaryLoading` false, `summaryError` null and the previous payload in place,
with the rejection unhandled. The owner categorizes a transaction, the refresh fails,
and nothing on the page acknowledges it. The initial `loadViews` effect does have the
catch; this path was written without one.

**Neither it nor the three budget actions guard on `cancelled`.** The main load effect
does. These do not, so a response that arrives after the month has changed calls
`setSummary` with the month the owner has left, plus `setSummaryLoading(false)` and
`setSummaryError(null)` — clobbering the newer load's state. Ticket 11's month gate then
withholds that payload, so the dashboard shows "This month's figures are not available
yet" with nothing to retry. Before ticket 11 the same race showed the wrong month's
figures instead, which is worse but quieter.

**A stale payload for the month already on screen is invisible on both pages.** The
dashboard and the Categories page each render their banner only when there is no
payload at all, so a failed refresh for the month being viewed shows the previous
figures with no signal. Ticket 11's third criterion asked the dashboard to match the
Categories page here and it does; this is the parity itself being weak, in both places
at once. Whether that matters is a product call: the figures are for the right month
and merely a few minutes old, which is a different claim from the wrong month's figures.

## Why this is recorded rather than scheduled

The first two are only reachable once the month can change, and nothing writes
`filters.month` until ticket 14 adds a selector. The third is pre-existing in both
pages and arguably not a defect at all. So the honest order is ticket 14 first — and
whoever takes 14 should read this file, because a month selector is exactly what makes
the first two live.

## Testing

`web/` has no test runner, so verification is the type check plus rendering the
affected states through `react-dom/server`, as tickets 07 and 11 did. The race is the
part that rendering cannot reach; if it needs a real test, that is the argument for a
runner, which is its own decision and not this ticket's to make.
