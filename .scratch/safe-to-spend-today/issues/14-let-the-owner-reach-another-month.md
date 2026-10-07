# 14: Let the owner reach another month

**What to build:** A month selector in the Web UI, so the past- and future-month
headlines this phase built are reachable by clicking rather than by editing a
default and rebuilding.

**Blocked by:** 11 (its month-label rules decide what a reached month is allowed to
claim, and this ticket is what makes those rules reachable)

**Status:** ready-for-agent

- [ ] The owner can move to another month from the dashboard and stay there
- [ ] Every page that reads `filters.month` follows the selection, rather than each page keeping its own idea of the month
- [ ] The current month is reachable again in one action from any other month
- [ ] The month the UI asks for is the one the backend calls current, with no UTC-derived default (shares its root with ticket 11's second criterion)
- [ ] Nothing financial is computed in the Web UI: the selector changes a query parameter

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

## Worth settling while here

Whether the selection belongs in the URL. Four pages share one month and the owner
will want to send themselves a link or use the back button; putting it in the query
string answers both and removes the question of what resets it. Not a requirement
above, because it is a routing decision the rest of the app has not had to make yet.

## Testing

`web/` has no test runner and installing one stays out of scope for this phase, so
verification is the type check plus rendering the affected states through
`react-dom/server`, as tickets 07 and 11 do. If the current-month default moves to
the backend, that part is seam 2 and carries a real test there.
