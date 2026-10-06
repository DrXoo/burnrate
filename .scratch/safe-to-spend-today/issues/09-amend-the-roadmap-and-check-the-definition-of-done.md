# 09: Amend the roadmap and check the Definition of Done

**What to build:** The roadmap describes the phase that actually shipped, and
every item of its Definition of Done is checked rather than assumed. This exists
as its own gate because Phase 3 was recorded as complete while its headline
metric was missing, and the gap went unnoticed for six phases.

**Blocked by:** 01, 07, 08

**Status:** ready-for-agent

- [ ] Phase 8's scope in the roadmap matches what shipped, with a line on why it grew beyond "a derivation, not new accounting"
- [ ] The Definition of Done gains the clause: a Pending charge reduces the allowance the day it appears, and a Pending row that later books is not counted twice
- [ ] Every Definition of Done item is checked against the implementation, and the result recorded
- [ ] The deliberately unchanged per-category budget threshold is recorded as a choice, not left as an oversight
- [ ] The schema doc is confirmed untouched, since this phase carries no migration
- [ ] Any gap found is recorded explicitly in the roadmap rather than left implicit

## Comments

**A coverage gap for the Definition of Done check to account for, found in code
review.** Tickets 01 and 02 added timezone-dependent behaviour to three places with
no test for any of them, against `AGENTS.md`'s TDD rule. `git diff main...HEAD --stat
-- backend/tests` touches only `test_config`, `test_domain_metrics`,
`test_ledger_service`, `test_summary_routes` and `test_summary_service`:

* `BudgetService._budget_status` and `deactivate_budget` now compare
  `budget.active_from >= today` against the owner's calendar day.
  `test_budget_service.py` is unchanged and contains no `timezone_name`, so the
  boundary that matters — a budget starting tomorrow UTC but today in Auckland — is
  uncovered.
* `TelegramCommandRouter._civil_month` is never exercised off UTC;
  `test_telegram_router.py` still constructs the router without `timezone_name`.
* `send_sync_notification`'s `civil_date` call is untested.

This is not a one-line fix, which is why it is recorded here rather than bolted onto
a closed ticket: `SummaryService` got an injectable `clock` seam for exactly this
purpose and `BudgetService` got only `timezone_name`, so it cannot be tested without
freezing the system clock. Closing the gap means either giving `BudgetService` the
same clock seam or agreeing a different one — a seam decision, so it belongs in a
ticket of its own rather than being smuggled into the DoD check.

Related and already handled: the hardcoded `0.85` in the dashboard hero is ticket
07's sixth criterion, with a breadcrumb on that ticket. It is not a gap for this one.

**Also from the review, fixed rather than recorded** (listed so the DoD check does
not re-find them): the sync worker's cron was pinned to UTC while every other civil
date moved to `APP_TIMEZONE`; `docs/technical/domain.md` claimed the Effective Date
import fallback "resolves on the UTC calendar day" when the code's own docstring
says it resolves on the database session's; the pending sweep compared against the
pending fetch's identifiers only, deleting `SCHD` rows the booked fetch reported; and
nginx appended to a client-supplied `X-Forwarded-For`, letting anyone defeat the
login lockout and the bank rate limiter.
