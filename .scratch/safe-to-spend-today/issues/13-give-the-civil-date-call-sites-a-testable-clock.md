# 13: Give the civil-date call sites a testable clock

**What to build:** The three `APP_TIMEZONE` call sites that cannot currently be
tested get the seam that makes them testable, and the boundary that matters gets a
test. Ticket 01 applied the owner's timezone to four places and covered one of
them; the other three are untested because they have no clock to inject.

Recorded by ticket 09's Definition of Done check rather than bolted onto ticket 01,
because the fix is a seam decision and not a test to backfill.

**Blocked by:** None

**Status:** ready-for-agent

- [ ] `BudgetService` resolves the owner's calendar day through an injectable clock, as `SummaryService` already does
- [ ] A budget whose `active_from` is tomorrow UTC but today in the owner's timezone is active, asserted without freezing the system clock
- [ ] `deactivate_budget` is covered at the same boundary
- [ ] `TelegramCommandRouter._civil_month` is exercised off UTC
- [ ] `send_sync_notification`'s `civil_date` call is exercised off UTC
- [ ] The seam is the same shape in every service that needs it, so the next civil date added has somewhere obvious to go

## Why it is its own ticket

`SummaryService` took an injectable `clock` in ticket 10 and is the one call site
with coverage. `BudgetService` took only `timezone_name`, so `_budget_status` and
`deactivate_budget` read the real wall clock: the only way to test the boundary
today is to freeze the process clock, which is the kind of test `AGENTS.md` warns
about. Giving it the same seam is a small change, but it is a decision about the
shape of the dependency rather than a correction, and three services should not
each invent their own.

Nothing here is a known defect. The code is believed correct in all four places and
the three uncovered ones are the three that would fail silently — a budget starting
"tomorrow" that the owner sees as today, a Telegram summary for the wrong month near
midnight, a sync notification dated a day out. The cost of the gap is that no later
phase can trust a civil date off UTC without re-deriving it by hand.

## Testing

Seam 2's existing fixture pattern, extended to `test_budget_service.py` and
`test_telegram_router.py`. The boundary case to assert in both directions: an
`APP_TIMEZONE` ahead of UTC where the owner's day has already turned, and one
behind where it has not yet. Neither test module currently contains the string
`timezone_name`, so both start from zero.
