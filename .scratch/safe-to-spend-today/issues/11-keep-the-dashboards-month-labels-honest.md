# 11: Keep the dashboard's month labels honest

**What to build:** Three Web UI defects, all in the same family: the page states
something about a month that it does not actually know. The first two were found by
the branch-wide `/code-review` after ticket 08 and are not reachable in the owner's
current configuration, which is why they are their own ticket rather than a
correction on ticket 07. The third was found by `/code-review` on ticket 10 and *is*
reachable, which is the one to fix first.

**Blocked by:** None (07 is done; this does not block 09)

**Status:** done

- [x] A month the backend has called "not current" is never labelled as finished when it has not started
- [x] No month label or tense is decided by comparing a UTC-derived month against the owner's timezone-resolved one
- [x] A stale summary paired with a failed refresh is visibly stale on the dashboard, as it now is on the Categories page
- [x] No caption claims a future month is unspent while the figure beside it says otherwise
- [x] Nothing new is computed in the Web UI: the fix adds a label rule or reads a backend field, not a financial one

## The three defects

**1 — `monthHasPassed` reads a future month as a closed one when `APP_TIMEZONE` is
behind UTC.**

`DashboardPage.monthHasPassed` is `month <= currentMonthValue()`, and
`currentMonthValue()` is `new Date().toISOString().slice(0, 7)` — UTC. It only runs
once the backend has said `not_current_month`, so the question it answers is purely
tense. Worked in both directions, the equality case is right in one and wrong in the
other:

* `APP_TIMEZONE` **ahead** of UTC, say Europe/Madrid. At `2026-06-30T23:00Z` the
  backend's civil date is 1 July, so its current month is July. UTC says June, which
  is also the month the switcher defaults to. The backend calls June not-current,
  equality reads past, and "Month closed · what June finished with" is **correct**.
  This is the configuration ticket 07's comment reasoned about.
* `APP_TIMEZONE` **behind** UTC, say Pacific/Honolulu. At `2026-07-01T02:00Z` the
  backend's civil date is still 30 June, so its current month is June. UTC says July,
  the switcher defaults to July, the backend calls July not-current, and equality
  reads past: the owner's first screen of the month says "Month closed · what July
  finished with, of the 1500.00 EUR it had budgeted", quoting the untouched budget as
  an outcome.

So the comment on `monthHasPassed` is not wrong, it is half the picture — it
considered only the UTC-ahead direction. The trap in fixing it: making the comparison
strict (`month < currentMonthValue()`) breaks the Madrid case to fix the Honolulu one,
because the equality case is genuinely ambiguous without knowing the offset.

Two honest fixes, in order of preference:

* Have the backend say which month is current. It is the only side that knows
  `APP_TIMEZONE`, and it already resolves the civil date; the UI then compares two
  figures from the same clock. The root cause is that `safe_to_spend_status` collapses
  past and future into one value, which ticket 07 recorded as a known compromise.
* Or render the ambiguous case without a tense at all — the money-left figure under a
  neutral "Not the current month" — which needs no API change and is never false.

Not urgent: the live configuration is EUR in a UTC-ahead timezone, where the defect
cannot fire. It becomes live the day `APP_TIMEZONE` is set to anything in the Americas.

**2 — A stale summary plus a failed refresh is invisible on the dashboard.**

`DashboardPage` renders its error banner only in the `error && !summary` branch, and
`useBurnRateData` does not clear `summary` on failure. So a failed refresh with a
payload already cached renders the previous month's figures with no banner: the
headline, both gauges and every disclosure describe a month the owner is not looking
at. The eyebrow does name the month in the non-current case, which is a weak signal,
and there is none at all when the cached month happens to be current.

Pre-existing, and found while probing the `CategoriesPage` finding that ticket 07's
second correction fixed. That page now treats a payload whose `month` is not the month
on screen as no payload at all; the dashboard should reach the same conclusion rather
than each page inventing its own staleness rule. The shared fix is for the hook to
expose the summary only for the month it was fetched for, which would make both pages
correct by construction.

**3 — The future-month caption asserts "Nothing is spent yet" while the figure above
it can already disagree.**

Found by `/code-review` on ticket 10. `DashboardPage`'s future-month branch captions
the money-left headline with "What <month> plans to have left of the <budget>
budgeted. Nothing is spent yet." — a hard-coded claim, not a reading of the payload.
It is already falsifiable: a standing order arrives as pending (`SCHD` normalizes to
pending) carrying a value date in a future month, so `effective_date()` files it in
*that* month, `budgeted_spending` for it is non-zero and `money_left_amount` is below
the budget before the month starts. The dashboard then prints the reduced figure and
captions it as untouched.

Unlike defects 1 and 2 this needs no unusual timezone or failed request: a scheduled
payment and a look at next month is enough, and ticket 10's sweep work means such
rows now persist correctly rather than being treated as phantoms. The fix is to
derive the sentence from the figures — say nothing about spend when there is spend,
or disclose it — rather than from which branch the code is in. No new financial
computation in the UI: the backend already reports the month's budgeted spending.

## Testing

`web/` has no test runner and installing one stays out of scope, so verification is
the type check (`docker build --target build -f web/Dockerfile web/`) plus rendering
the affected states through `react-dom/server` and reading them, which is how tickets
07 and its corrections were verified. Defect 1 needs both timezone directions
rendered, since the naive fix passes one and fails the other. If the fix moves the
current-month question into the backend, that part is seam 2 and carries a real test.
Defect 3 renders with a future-dated pending row in the payload, and the figure it
contradicts comes from seam 2, where a future month with a scheduled payment in it
can be asserted directly.

## Comments

**Defect 1 was fixed the first way, so the two months being compared now come off one
clock.** `SummaryService` reports `current_month` -- the month `reference_day` falls in,
resolved through `APP_TIMEZONE` like every other civil date here -- and
`monthHasPassed` compares `summary.month` against it. That makes strict `<` correct in
both timezone directions rather than right in one and wrong in the other: equality now
means the month *is* the current one, which the backend would not have called
not-current, so the ambiguous case the naive fix tripped over no longer exists. The new
field is the seventh on the summary response rather than the six the spec's API contract
table listed, and that table now carries it; nothing is removed, so no client breaks, and
`safe_to_spend_status` still collapses past and future, which this makes survivable
instead of resolving.

**It carries a test at seam 2, parametrized over both directions**
(`test_summary_service_names_the_month_the_owner_is_in`): Pacific/Honolulu at
`2026-07-01T02:00Z` reports `current_month` June while July is asked for, and
Europe/Madrid at `2026-06-30T23:00Z` reports July while June is asked for. The first
case is the live defect; the second is the configuration ticket 07 reasoned about, and
it is in the table so the Madrid case cannot be broken to fix the Honolulu one.

**Defect 2 was fixed in the hook, not on the page.** `useBurnRateData` exposes the
summary only when `summary.month` matches `filters.month`, so a payload fetched for
another month never reaches a consumer. The dashboard's existing `error && !summary`
branch then fires on its own, and `CategoriesPage` stops re-deriving the rule it
invented -- a null prop now means the month's budgets are unknown, which is what it
already treated as a third state. One rule, at the door, instead of one per page.

**Defect 3's caption is read off `budgeted_spending_amount`**, which the backend already
serves: non-zero prints "€80.00 of it is already committed", zero keeps "Nothing is
spent yet". `test_summary_service_counts_a_scheduled_payment_in_the_month_it_falls_due`
pins the premise at seam 2 -- a hold with a July value date and no booking date puts
80.00 of spend in July while the owner is still in June, so money left is 1420.00 before
the month begins. That test passed on the first run: the backend behaviour was already
correct and the caption was contradicting it, so this one documents the figure the fix
depends on rather than driving it. It is the one part of this ticket with no red step.

**Verified the two ways available behind a seam with no test runner.** The type check
passes (`docker build --target build -f web/Dockerfile web/`). Then five states were
rendered through `react-dom/server` and read as text: both timezone directions, a failed
refresh for another month, and a future month with and without a standing order in it.

**All three were mutation-checked, and each mutant printed the reviewer's finding
verbatim.** The old `month <= currentMonthValue()` with the clock pinned at
`2026-07-01T02:00Z` prints "July 2026 · against plan | €1,500.00 | What July 2026
finished with, of the €1,500.00 it had budgeted | Month closed" -- the untouched budget
quoted as an outcome. Handing the page May's payload beside a failed June refresh prints
"Safe to spend today | €12.50 | On track" with no banner at all. Restoring the hard-coded
caption prints "€1,420.00 | ... Nothing is spent yet" directly above its own "€80.00
pending" disclosure. The harness lived in the scratchpad and is gone; nothing was added
to `package.json`.

**The UTC-derived default month is still there, and is ticket 14's.** `filters.month`
is initialised from `currentMonthValue()`, so on the Honolulu configuration the owner's
first screen still *asks for* the wrong month -- it is now labelled truthfully as a month
that has not started, rather than as one that closed. Ticket 14's fourth criterion owns
the default and can read the `current_month` field this ticket adds.

## What the review found, and where it went

`/code-review` raised twelve findings. Four were corrected here, two were already
answered, and the rest became tickets 15-18 or notes on ticket 14. The three that
changed the code are worth keeping, because each one says something this ticket got
wrong on its first pass.

**The caption was still falsifiable, and the fix for it was half a fix.** It read
`budgeted_spending_amount`, so a future hold in a category *with no budget* put the
caption back where it started: verified at seam 2, an 80.00 standing order due in July
in an unbudgeted category reports `budgeted_spending_amount` 0.00 against
`unbudgeted_spending_amount` 80.00 and `monthly_spending_amount` 80.00. The headline
figure does not move — money left is on a budgeted basis — but the disclosure chips do,
so the page printed "Nothing is spent yet" a few pixels from "€80.00 unbudgeted". It now
reads `monthly_spending_amount`, the figure that reconciles both slices, and the sentence
no longer claims the spend came out of the budget. `test_summary_service_discloses_a_
scheduled_payment_no_budget_covers` pins that figure at seam 2, and the mutant prints the
contradiction verbatim.

**The hook's gate made a dead branch live without giving it a rendering.** Before it,
`DashboardPage`'s `if (!summary) return null` could only fire while loading or after a
failure, both of which have their own branch; after it, a payload withheld for the wrong
month lands there and paints an empty page. Latent today, because nothing writes
`filters.month` until ticket 14 — which is exactly why it is fixed now rather than left
for 14 to discover. The state reads "This month's figures are not available yet", and the
mutant renders nothing at all.

**The doc comment on `monthHasPassed` was wrong in the same way as the one it
replaced.** It claimed both months come from the backend's clock. They do not:
`current_month` is resolved through `APP_TIMEZONE`, while `month` is the month the
browser asked for, echoed back — and that request still originates in
`currentMonthValue()`, one hop upstream. The comparison is sound and the comment was
not, which is precisely the failure mode of the half-picture comment this ticket set out
to fix. Rewritten to say which month comes from where, and to name the UTC default as a
separate question that decides which month the owner lands on rather than whether the
label is true of it.

Two smaller corrections: `applyFilters` now coerces an empty month to the current one,
because `buildQuery` drops an empty query value and the gate would then withhold every
payload with no error to explain it; and `reference_day.strftime("%Y-%m")` is resolved
once into `current_month` and fed to both `_resolve_month` and the payload, so the month
that is reported and the month that is served cannot drift apart.
`_is_current_month` keeps its own date comparison, which cannot drift from either
because `month_start` is derived from the same `month_value`.

**Two findings were already answered.** The dashboard's staleness parity was called
unmet: it is not, because `CategoriesPage` renders its banner only when there is no
payload either, so a failed same-month refresh is invisible on both pages. That shared
weakness is real and is ticket 18's third defect; the criterion asked for parity with
that page and got it. And removing the page's own month check was called an unenforced
cross-module assumption: true, but the useful half of that finding is that the `month`
prop it checked against no longer selects anything, which is now a note on ticket 14.

**Four became tickets.** 15, the projection discarding spend already committed in a
month that has not started — the sharpest of the twelve, and verified: 500.00 committed
against a 400.00 budget still projects 400.00 and zero overspend. 16, `no_budget`
winning over tense, so a month that closed before the owner budgeted anything is told to
set a budget — the same family as this ticket, missed because the status is decided
before tense is considered. 17, the Telegram formatter reading a future month as if it
were in progress. 18, a background refresh that fails leaving no trace anywhere. 17 and
18 are recorded rather than scheduled, for reasons in their own files.

**One was a design argument, not a defect.** `/code-review` makes the case for
splitting `not_current_month` into a closed/not-started pair, so tense lives in the
domain, equality becomes unrepresentable rather than merely unreachable, and every
client stops re-implementing the comparison — with ticket 17 as evidence that the next
client does exactly that. It is a better end state and it is not this ticket's to take:
it changes the status enum that `ADR-0002` fixes at five values and both interfaces
read. Recorded as the alternative in ticket 16, which it would absorb.
