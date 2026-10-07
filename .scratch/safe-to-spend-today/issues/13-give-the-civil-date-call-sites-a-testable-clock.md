# 13: Give the civil-date call sites a testable clock

**What to build:** The three `APP_TIMEZONE` call sites that cannot currently be
tested get the seam that makes them testable, and the boundary that matters gets a
test. Ticket 01 applied the owner's timezone to four places and covered one of
them; the other three are untested because they have no clock to inject.

Recorded by ticket 09's Definition of Done check rather than bolted onto ticket 01,
because the fix is a seam decision and not a test to backfill.

**Blocked by:** None

**Status:** done

- [x] `BudgetService` resolves the owner's calendar day through an injectable clock, as `SummaryService` already does
- [x] A budget whose `active_from` is tomorrow UTC but today in the owner's timezone is active, asserted without freezing the system clock
- [x] `deactivate_budget` is covered at the same boundary
- [x] `TelegramCommandRouter._civil_month` is exercised off UTC
- [x] `send_sync_notification`'s `civil_date` call is exercised off UTC
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

## Comments

**Five criteria are met; the sixth is met in substance and left unticked.** The seam
is *not* the same shape in all four services, and saying it is was this ticket's own
first mistake. `EnableBankingService` takes the whole `Settings` object and reads
`settings.app_timezone`; the other three take a `timezone_name` beside the clock. The
part that was missing and untestable — the injectable clock — is now identical in all
four, and `burnrate/clock.py` documents both forms and says which to copy. Recorded
this way rather than ticked because a reader comparing the criterion against the diff
would otherwise find it false and not know which way to resolve it, which is how
ticket 09's Definition of Done check handled the same situation.

**The seam is enforced by the signature, not by the convention.** `civil_date` now
*requires* `instant`. That was not in the ticket and is the more durable half of the
work: a caller cannot fall back to the wall clock by omitting the argument, which is
exactly how three of the four call sites went uncovered through six phases. The
docstring convention alone would have let a fifth one do it again.

**Every test here was mutation-checked, and it mattered more than usual.** Four of
the seven new cases were green on first run, against code an earlier cycle in this
same ticket had already made correct. One row of the budget-status table passed
*under* the mutation: a budget starting 2026-07-01 reads `active` off any clock in
October, which is when the suite happened to run. It gained a second budget a month
further out so that both rows discriminate. Without that, the test the second
criterion asks for would have proved nothing and aged into false comfort.

## What the review found, and where it went

Eleven findings, all addressed. Nothing was routed to a new ticket.

**One was a real defect, and it is not clock work.** `deactivate_budget` recorded
`active_to` as *today*, and `_get_active_budgets` counts a budget in full for any
month its window touches at all. So cancelling a running budget on the 1st of a month
handed that month the entire amount: the budget list read the row `inactive` while
the dashboard kept quoting the figure, and the owner's daily allowance was derived
from a budget they had just switched off. Worked end to end at 01:00 on a Madrid
owner's 1 July, July reported a 300.00 budget and 9.68 of allowance with the row
cancelled, and creating July's own budget was refused for overlapping by one day.

The review attributed it to this ticket. It is not: run in plain UTC, with the server
and the owner agreeing on the day, it fires identically. The timezone error was
*masking* it — resolving in UTC gave `active_to` the 30th, which is what the owner
meant, by being wrong about what day it was. What is fair is that this ticket's test
was the first ever to reach that branch, and it pinned the bad value as correct.

Fixed as `active_to = today - 1`: the budget ran through yesterday. Cancelling on the
1st now leaves the new month unbudgeted, and cancelling on the 2nd or the 15th is
untouched, because the budget genuinely ran in that month and a refused overlap there
is the right answer. The root cause is recorded in `schema.md` rather than only in
the fix: the window is month-granular at both ends, and the counting rule is why.
Proration is the alternative and is a much larger product decision.

**Four were errors this ticket introduced into the documentation.** The worst is that
`clock.py` — the canonical record future work is told to copy — described a shape one
of its four named services does not have, and the same false claim had been copied
into `architecture.md`, the roadmap and a service docstring. The roadmap contradicted
itself: a struck-through gap sat directly above a paragraph still saying all five were
open, two of which tickets 11 and 12 had already closed and never marked. Renumbering
the next steps silently moved what "Steps 1 and 2 finish Phase 8 honestly" pointed at.
And `civil_date` had no test of its own while being declared the product's single
seam — the deleted gap text said "no test anywhere references `civil_date`", which was
still literally true.

**One asked for the test seam the production code got and the tests did not.** The two
boundary instants were retyped in four modules, two of them under the same constant
name, each with its own preamble restating the same arithmetic. They now live once in
`tests/conftest.py` as `AHEAD_OF_UTC` and `BEHIND_UTC`, deliberately the same pair
everywhere: a figure that breaks in only one direction is the failure mode they exist
to catch, and that is only visible if both sides are the same boundary.

**One overstated its evidence, as in ticket 12.** The missing allowance assertion was
called uncatchable; mutation shows the existing `monthly_spending_amount` assertion
catches the same change. Added anyway, because it is the figure the ticket names as
the harm. Its second half was a real gap.

**Two were proposals taken only in part.** Making `instant` required: taken, and it is
the best thing in this change. Dropping the `timezone_name="UTC"` defaults alongside
it: declined — it breaks six existing constructions for little gain, and `"UTC"` is
the same default `Settings` carries. `tzdata` is now declared, which makes explicit a
dependency that was being inherited from the base image rather than fixing a break.

**The remaining three were small and correct**: `deactivate_budget` covered in one
offset direction while the roadmap claimed both, an eight-line docstring restating
`clock.py` with a service list that was already wrong, and a negative assertion that
checked only for the absence of a substring and so would have held for an empty
message.
