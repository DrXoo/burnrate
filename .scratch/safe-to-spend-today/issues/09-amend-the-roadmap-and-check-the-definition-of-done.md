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

**The dashboard answers a question the Web UI cannot ask: there is no month selector.**
Found while verifying ticket 07, which implements user stories 22 and 23 — the owner
"viewing a past month" and "viewing a future month". Those states work, and ticket 07's
fifth criterion is met, but no owner can reach them by clicking.

Verified exhaustively rather than assumed. `filters.month` is initialised to
`currentMonthValue()` at `web/src/hooks/useBurnRateData.ts:76` and nothing ever changes
it: all three `applyFilters` call sites are in `TransactionsPage.tsx:263-272` and each
spreads `...filters` while overriding only `accountId`, `categoryId` or `categorized`.
There is no `type="month"` input anywhere in `web/src`. The TopBar shows the month at
`TopBar.tsx:57`, but it is a read-only label, which is what makes the absence easy to
miss. The backend has supported the parameter all along — `GET /api/v1/summary?month=`,
via `getSummary` in `web/src/lib/api.ts:274`.

So the past/future headline is reachable today only by editing the default and
rebuilding. It is not in any of the ten tickets of this phase, and it is not obviously
another phase's work either — worth deciding here whether Phase 8 owes a month picker,
or whether stories 22 and 23 are deliberately groundwork for a later phase. Flagging
rather than fixing: a month selector changes navigation across four pages that all read
`filters.month`, which is a ticket, not a DoD footnote.

**A consequence for this ticket's own check:** ticket 07's criterion 5 cannot be verified
by looking at the running app. It was verified by rendering `DashboardPage` through
`react-dom/server` against fixtures, which the spec's "the layout is verified by looking
at it" did not anticipate. The criterion is met; the verification route is not the one
the spec assumed.

**The Web UI picks the month in UTC while the backend picks it in `APP_TIMEZONE`, and
ticket 07 makes the mismatch visible.** A fourth timezone defect, in the same family as
the three above but on the client side, so `grep timezone_name` over `backend/` does not
find it.

`currentMonthValue()` is `new Date().toISOString().slice(0, 7)` — `toISOString` is UTC by
definition. `SummaryService` resolves its reference day as
`civil_date(timezone_name=self._timezone_name, instant=self._clock())`, and
`_is_current_month` compares the requested month against *that*. The two disagree at every
month boundary for any `APP_TIMEZONE` that is not UTC.

Worked through for an owner in `Pacific/Auckland` (UTC+13) at 00:30 on 1 November 2026:
the browser's UTC instant is 2026-10-31 11:30, so the UI requests `month=2026-10`, while
the backend's civil day is 2026-11-01 and its civil month is 2026-11. `_is_current_month`
returns False, the domain returns `not_current_month` with a null amount, and the owner
opens the app on the morning of the 1st to "October 2026 · against plan" where their
allowance should be. Story 26 names exactly this — "so that the allowance does not jump
back a day at 01:00 and report last month on the 1st" — and Phase 8 fixed the four
backend call sites while the client kept its own UTC clock. Before ticket 07 the symptom
was a quietly stale dashboard; now it is a headline that visibly reports the wrong month.

Westward timezones have the mirror case at the end of the month rather than the start.

Two notes for whoever takes it. The fix is not simply swapping the function: the browser
cannot know `APP_TIMEZONE`, so either the backend exposes it (it already defaults the
month when the parameter is omitted, which is the smaller change — drop the client-side
default and let the server choose) or it is added to a settings payload the client reads.
And `monthHasPassed`, added in ticket 07, calls the same UTC `currentMonthValue()`; its
docstring records why equality reads as past, which keeps the *tense* right when the two
clocks disagree, but it cannot repair a request for the wrong month.
