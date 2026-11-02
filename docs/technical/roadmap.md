# BurnRate Implementation Roadmap

## Goal

This document is the implementation roadmap for BurnRate.

It answers:

* What has already shipped?
* What should be built next, and in what order?
* What is the exit criterion for each phase?

The roadmap is split into two acts. Act I (Phases 1-7) built the machine and is
essentially complete. Act II (Phases 8-13) makes the machine worth opening.

---

## Act I Status: Shipped

Act I was organized around **technical risk**: prove the Enable Banking
integration before building product on top of assumptions. That was the right
axis and it worked. Summary of the delivered state:

| Phase | Scope | Status |
|---|---|---|
| 1 | Foundations: FastAPI, PostgreSQL, Alembic, Docker Compose, core schema | Shipped |
| 2 | Enable Banking vertical slice: JWT signing, auth flow, callback, idempotent import | Shipped |
| 3 | Core product loop: transactions, unknown queue, rules, categories, budgets, summary | Shipped, with one gap (see below) |
| 4 | Sync automation: `sync-worker`, APScheduler cron, sync sessions, retry | Shipped |
| 5 | Product hardening: auth, encryption at rest, observability, test coverage | Shipped |
| 6 | Secondary interface: read-only Telegram bot | Shipped |
| 7 | Operational resilience: backup and restore | **Not started** — re-scoped as Phase 13 |

### The Phase 3 gap

Phase 3's Definition of Done required the summary to show *"money left, monthly
spending, burn rate, and runway"*. The first three shipped. **Runway never did** —
neither the calculation nor the data model it needs. `Account` has no way to mark
a balance as savings available for runway, which `docs/product/metrics.md`
requires.

Phase 3 is therefore recorded as **closed with a known gap**, not as done. The gap
is resolved in Phase 11, and the metric is redefined there because its original
definition does not apply to the product's actual user (see below).

The gap left a visible scar worth noting as a lesson: the Web UI grew its own
savings-rate metric, including the policy threshold for what counts as a thin
margin, in `web/src/components/pages/DashboardPage.tsx`. That is a product rule
living in the presentation layer, which the architecture forbids. When the domain
does not answer a question the user is asking, the answer gets invented in the
nearest layer. Phase 8 moves it back.

---

## The Act II Pivot

Act I's risk was *"will the integration work?"*. That risk is retired.

Act II's risk is different and entirely product-side:

> Will the owner still open this in three months?

A dashboard that reports levels is a dashboard you stop opening. The data is
already in the system and already correct; what is missing is that it never
tells you anything you did not already know, and it never speaks first.

So Act II changes the organizing principle. Phases are no longer named after
components to build. Each phase is **a question the owner asks**, and each exit
criterion is **behavioural** — something the owner can do, or learns without
asking — rather than technical.

### Who this is for

BurnRate targets **a salaried person who does not want to overspend**.

This is a deliberate narrowing from the six audiences listed in
`docs/product/overview.md`, and it is the single most important input to the
ordering below. It implies:

* The hero metric is **Safe to Spend Today**, not burn rate and not runway.
  A daily allowance changes a decision in the moment; a monthly rate does not.
* The second most valuable thing is **anomaly detection** — "this is unlike
  you" — because for a salaried user the levels are stable and only the
  *changes* carry information.
* **Runway, as originally defined, is degenerate for this user.** The definition
  in `docs/product/mvp.md` was savings divided by average monthly deficit; a user
  who saves has no deficit, so the result is infinite. Phase 11 redefines it as a
  cushion metric that is well-defined for a saver and still collapses to the
  original meaning for someone in deficit.

If the target user ever changes, re-order Act II before writing any code.

---

## Phase 8: "How much can I spend today?" — Shipped

### Objective

Replace the monthly abstraction with one number the owner can act on before
buying something.

### Scope

Scoped as a derivation and delivered as roughly two tickets more than that. The
original scope is kept below each item, because the gap between the two is the
useful part of the record.

* Domain calculation for **Safe to Spend Today** in a new pure domain module,
  `burnrate.domain.metrics`: `max(0, variable_budget_total −
  variable_budgeted_spend − fixed_overrun) / days_remaining`, where the day
  count includes today. The module holds every threshold the product judges a
  month by — the allowance's pace bands, the savings bands, the per-category
  budget band — as functions over primitives with no database session. See
  ADR-0001 and ADR-0002.
  *Originally scoped as "a derivation, not new accounting" computed in
  `SummaryService`.*
* **Pending spend became load-bearing**, which is the new accounting the
  original scope said this phase did not need. A card payment settles one to
  three days after it is made, so a daily allowance that counts only booked
  spend is optimistic by exactly the amount most likely to matter, and
  optimistic in the direction that causes overspending — the one failure the
  product exists to prevent. ADR-0003 carries the reasoning. It brought with it:
  * **Effective Date** — month membership resolves as booking date, then value
    date, then import date, behind one shared helper used by every
    month-windowed query. Required rather than optional: a pending row has no
    booking date, so it failed `>= month_start` in SQL and was invisible to the
    month window regardless of the status filter.
  * **A reconciliation sweep** — pending rows the bank stops reporting are
    deleted after a fully successful pending fetch, so a cancelled hold does not
    shrink the allowance forever. Gated on a complete fetch, and it skips rows
    the owner marked Ignored.
  * **An asymmetry between the slices** — pending counts in the variable slice
    only. The fixed step projection and the Fixed Overrun stay booked-only,
    because the projection trusts actual spend over its estimate as soon as any
    spend exists and a partial hold would wreck it. A pending charge in a fixed
    category must land in neither slice, which is why the variable slice cannot
    be computed as `monthly_spending − fixed_spent`.
* **Fixed Overrun** — `Σ max(0, booked − budgeted)` per fixed category, deducted
  from the allowance, so a rent increase does not quietly stay in the owner's
  daily spending money.
* Expose it through the summary API as a first-class field. Six fields added,
  none removed: `safe_to_spend_today_amount`, `safe_to_spend_status`,
  `pending_spend_amount`, `fixed_overrun_amount`, `savings_rate_percent`,
  `savings_status`.
* Make it the headline of the dashboard, above balance and budget, and the
  figure `/summary` opens with on Telegram, above the balance.
* Move the savings-rate threshold out of `DashboardPage.tsx` into the domain.
  The budget-pacing verdict moved with it: the UI's rule compared spend against
  85% of budget with no time term, so an on-plan month flipped to a warning
  around day 26. The replacement bands against **On-Plan Remaining**, which puts
  an on-plan month at a ratio of exactly 1.0 on every day of the month.
* **`APP_TIMEZONE`** (IANA name, default `UTC`) added to settings and used
  wherever a civil date is derived — the summary service, both call sites in the
  budget service, and the Telegram notifier. "Today" means today where the owner
  is, so the allowance does not jump back a day at 01:00 or report last month on
  the 1st.
* Handle the degenerate cases explicitly: no budgets defined (the amount is
  null and the status says `no_budget`, because a zero would read as "you may
  spend nothing"), a month already overspent (the amount clamps to zero while
  the status bands the unclamped remainder, so an overspent month still reads
  `over`), the last day of the month (the day count includes today, so it
  resolves to 1 and needs no special case), and a month that is not the current
  one (`month_closed` or `month_not_started`, with the amount null -- the status
  names the tense so no interface has to work it out, per `ADR-0002`'s amendment).

No migration: the Effective Date is resolved in query rather than stored, and
the sweep deletes rows. The stored `effective_date` column is the better end
state and was deferred because it needs a backfill.

### Definition of Done

The owner can answer *"can I spend 40 EUR on dinner tonight?"* by glancing at one
number, without reading a chart or doing arithmetic. No financial rule or
threshold remains in the Web UI. A Pending charge reduces the allowance the day
it appears, and a Pending row that later books is not counted twice.

### Definition of Done: checked

Checked against the implementation rather than assumed, because Phase 3 was
recorded as complete while its headline metric was missing and the gap went
unnoticed for six phases.

| Clause | Result | Evidence |
|---|---|---|
| One number, glanceable, no arithmetic | Met | The allowance is the dashboard's 52px headline with the balance demoted to the line beneath it, and the figure `/summary` opens with. Seam 4 asserts it leads the output. |
| No financial rule or threshold in the Web UI | Met | Every threshold lives in `burnrate.domain.metrics`. `DashboardPage` reads `safe_to_spend_status` and `savings_status` and computes only fractions that become an arc length or a bar width. The sign tests that remain (`remaining >= 0` choosing "left" or "over", `amount > 0` choosing whether to show a disclosure) pick wording, not a number. |
| A Pending charge reduces the allowance the day it appears | Met | Seam 2: `test_summary_service_counts_a_pending_charge_as_spend_this_month`, and the worked example behind `safe_to_spend_today_amount == "7.19"` includes an unsettled 25.00. `test_summary_service_counts_an_undated_pending_charge_in_the_month_it_was_imported` covers the Effective Date fallback that makes a row with no booking date visible at all. |
| A Pending row that later books is not counted twice | Met | Seam 3: `test_a_pending_hold_that_books_under_a_new_identifier_leaves_no_twin` and `test_a_hold_with_no_identifier_survives_resync_on_its_content_hash`. Both payload shapes are covered, because which one the bank produces was not knowable before it ran. |
| Schema doc untouched | Met in substance, not literally | No migration and no table or column changed. The doc did gain two notes: that month placement reads the effective date rather than `booking_date`, and that this makes the window non-sargable so those queries plan as sequential scans. Both describe existing tables, which is why they belong there. |

266 backend tests passed at this check, 301 after the tickets that followed it.
`web/` had no test runner when this was checked, so the
dashboard was verified by rendering it through `react-dom/server` against fixtures and
reading the output — not by looking at the running app, which is what the spec assumed.
**Ticket 14 added Vitest**, scoped to one seam: `useBurnRateData` with `lib/api` faked.
It was added for concurrency rather than for coverage — a month selector makes a
background refresh racing a month change reachable, and which state survives two
responses landing out of order is not something a render can reach. Page rendering
stays on the `react-dom/server` route, so page tests remain a decision to take rather
than a gap to fill.

### A threshold deliberately left alone

The per-category budget band — `utilization_percent >= 85` reads `watch` —
still has the time-decay that was just removed from the hero: an on-plan
category flips to watch around day 26. Left alone knowingly, not overlooked.
"86% of Food used" is a different and legitimate claim from "off pace", and the
rows are a list the owner scans rather than the headline they act on. Redesigning
it is available work, not a defect.

### Known gaps

Recorded explicitly, so that none of them is rediscovered as a surprise. The list
grew twice after it was written: the five below the line were the gaps this phase's
Definition of Done check found, and the five under "Found later" came out of
per-ticket reviews afterwards. Anything checking Phase 8 against this section has to
read both halves — reading only the first would have called the phase closed with
four tickets open and two verified defects live.

**All of them are closed but one**, and that one — a manual categorization lost when
a hold books under a new identifier — is deliberately deferred to Phase 9, which is
where the identity matching that would actually fix it belongs. It is also
unreachable against the one bank restricted production has. The section is kept
rather than deleted because the reasoning for *not* taking its obvious fix is the
part worth having.

* ~~**The timezone work has almost no test coverage.**~~ **Closed by ticket 13.**
  `APP_TIMEZONE` was applied to four call sites and only the summary service was
  exercised off UTC. Every call site now takes the instant from an injectable
  `clock`, which `BudgetService` was missing, and `civil_date` requires the instant
  rather than defaulting to the wall clock, so the seam is enforced by the signature
  instead of by convention. Where the timezone comes from still varies —
  `EnableBankingService` reads it off the `Settings` it already holds, the other
  three take a `timezone_name` — and both forms are recorded. Four boundary tests,
  each over both offset directions: a budget starting on the 1st, the day a budget
  is cancelled on, the month a bare `/unknown` scopes to, and the month a sync
  notification counts, plus `civil_date` itself. The convention is in
  `burnrate/clock.py` and the two boundary instants in `tests/conftest.py`, so a
  fifth civil date has one shape to copy rather than a fourth to invent.
* ~~**The Web UI picks the month in UTC while the backend picks it in
  `APP_TIMEZONE`.**~~ **Closed by ticket 14.** `currentMonthValue()` was
  `new Date().toISOString().slice(0, 7)`, so for any non-UTC `APP_TIMEZONE` the two
  disagreed at every month boundary: in `Pacific/Auckland` at 00:30 on the 1st the UI
  requested last month, the backend called it not-current, and the owner's first screen
  of the month showed last month's label where their allowance should be. Of the two
  fixes offered, the first was taken: the client sends no month and the backend's answer
  decides it, rather than a settings payload the browser would have had to re-derive a
  month from. It costs a two-phase first load, because an omitted month means the
  current month on `/summary` and *every month ever* on the three ledger views — so the
  summary is fetched first, its `current_month` adopted, and the views then scoped to
  it. Both `currentMonthValue()` and `currentMonthStart()` are deleted, and the only
  clock left in `web/src` renders "8 min ago" on a sync label.
* ~~**Three month-label defects in the dashboard**~~ **Closed by ticket 11.** All of
  the same kind — the page stated something about a month it did not actually know.
  `monthHasPassed` read a future month as a closed one when `APP_TIMEZONE` is behind
  UTC; a stale summary paired with a failed refresh rendered with no banner; and the
  future-month caption asserted "Nothing is spent yet" while a scheduled payment
  filed into that month by the Effective Date already contradicted it. The backend
  now reports `current_month` so the comparison is exact in both offset directions,
  the hook withholds a payload for the wrong month, and the caption reads the figures
  beside it.
* ~~**There is no month selector in the Web UI.**~~ **Closed by ticket 14**, which
  settled that Phase 8 owed it: user stories 22 and 23 shipped as code no owner could
  run. Arrows plus a native `<input type="month">`, unbounded in both directions —
  bounding the past needs an API for the earliest month with data, and a future month is
  where standing orders land. The month stays in hook state rather than the URL, because
  `section` is not in the URL either and there is no router: a shared link would restore
  the month and always land on the dashboard. The top bar's month label became the way
  back to the current month, and both it and the selector are hidden on Settings, where a
  month means nothing. Fewer pages were touched than feared — the hook does every fetch,
  so the month reaches the UI in three places.
* ~~**An Ignored transaction does not stay Ignored across a re-import.**~~
  **Closed by ticket 12.** `RulesService` guarded on `category_id is None` and never
  read `excluded_at`, so a row the owner excluded that matched an active rule was
  handed its category back on the next sync — the ledger still showed it excluded
  and the unknown queue stayed quiet, while the money was back in monthly spending
  and therefore back out of the allowance. The rule engine now states which rows it
  may decide, and the spend and income queries state the exclusion rather than
  inheriting it from a null category.

All five are closed: the Ignored defect by ticket 12, the month-label defects by
ticket 11, the timezone coverage by ticket 13, and the last two by ticket 14. Those
last two were the same piece of work seen from two sides, which is why one ticket
owned both: neither could fire for an owner who could not navigate away from the
current month, and that is exactly what made them easy to leave and what Phase 3's
lesson says about leaving them.

#### Found later, by per-ticket reviews

These came out of `/code-review` after the Definition of Done check, so they are not
among the five above. Four were found by the per-ticket reviews and a fifth by the
review of ticket 14. Two are verified live defects in the backend, reproduced against
the current branch; the fifth is traced through the code rather than reproduced,
because it cannot fire against the one bank restricted production has:

* ~~**A month that has not started projects below the spend already committed in
  it**~~ **Closed by ticket 15.** `_days_elapsed_in_month` returns 0 before a month
  begins, and `_project_spend` then returned the budget reference unchanged — its "no
  signal yet, assume spending tracks the budget" branch, which was true when a future
  month could not hold spend. Effective Date and pending-spend counting made it false.
  Verified: a 500.00 standing order due in July, read in June against a 300.00 budget,
  reported `budgeted_spending_amount` 500.00 beside
  `projected_month_end_spend_amount` 300.00 and `projected_overspend_amount` 0.00 —
  the projection saying the month lands on budget while the headline already showed it
  blown. `_extrapolate_spend` had the same shape and returned 0.00 with no budget set,
  discarding the one figure such a month has. Both now carry a floor —
  `max(spend_to_date, budget_reference)` and `spend_to_date` — and both branches fire
  only when `days_elapsed <= 0`, so no current- or past-month figure moved.
* ~~**A month that closed before the owner budgeted anything is told to set a
  budget**~~ **Closed by ticket 16.** `safe_to_spend_today` decided `no_budget`
  before it considered whether the month is the current one. Verified: May 2026 read
  on 15 June returned `safe_to_spend_status: "no_budget"` with
  `current_month: "2026-06"`, and the dashboard then printed its set-a-budget
  invitation over a month that closed weeks ago. Same family as ticket 11 — the page
  stating something about a month it does not know — and both branches were
  individually right, only their order wrong. Tense now outranks `no_budget`, and
  `not_current_month` is split into `month_closed` and `month_not_started`, so that
  branch can no longer fire for a month the owner is not in: the backend never sends
  `no_budget` for one. A month with no budget also got its own wording in both
  tenses, because "what May finished with, of the €0.00 it had budgeted" is true and
  reads as noise.
* ~~**The Telegram summary has no tense**~~ **Closed by ticket 17.** `/summary <a future
  month>` printed a used-budget bar, a daily pace over zero elapsed days and a month-end
  projection for a month that had not begun, while the dashboard captioned the same
  payload "Not started yet". The header now names the tense in the dashboard's own badge
  words, read off `safe_to_spend_status`, and a month that has not started reports its
  budget and what is committed to it without the three lines that describe progress. A
  closed month keeps them, with a test so the suppression cannot widen.
* ~~**A failed background refresh leaves no trace**~~ **Closed by tickets 14 and 18.**
  `refreshLedgerViews` had no `catch` and no `cancelled` guard, so a
  rejection was silent and a response arriving after a month change clobbered the newer
  state. Both were recorded rather than scheduled because neither could fire until a
  month could change, so ticket 14 took them with the selector: the refresh now records
  the month it was started for and discards a payload for a month the owner has left,
  and a failure reports itself twice — a toast, because the edit it followed did land,
  and `summaryError`, because the figures on screen are no longer trustworthy. What is
  left in 18 was its third defect, narrowed to one page: the Categories panel showed a
  stale payload for the month on screen with no signal. Ticket 18 settled that parity
  call in favour of marking it — the page prints each category's budget, spend and
  remaining, and prints them again at hero size in the detail panel, so they are figures
  the owner acts on and the dashboard's reasoning carries over. A month with no rows at
  all still makes the stronger claim, because nothing on screen could be out of date.
  Ticket 18 also added the sixth testing seam, page rendering through `react-dom/server`,
  which ticket 14 had deliberately left as a decision for whoever needed it first.

* **A manual categorization on a hold is lost when the hold books under a new
  identifier**, for a bank that supplies no `transaction_id` or `entry_reference`.
  `_transaction_external_id` then hashes booking date, value date, direction, amount,
  currency and remittance; a pending row carries no booking date, so settling changes
  the hash, the booked row arrives as a new row, and the sweep deletes the pending one.
  Everything the owner decided about that row goes with it, and the booked twin lands
  back in the review queue uncategorized.

  **The obvious fix is wrong and should not be taken.** The sweep exempts Ignored rows
  and the suggestion is to exempt categorized ones the same way, on the reasoning that
  both record a decision the owner made. The reasoning does not carry, because the cost
  of the exemption is not the same: `excluded_at IS NULL` keeps an Ignored row out of
  every figure, so a surviving Ignored twin is clutter in the ledger and nothing more,
  while `COMMITTED_STATUSES` is `("booked", "pending")` — a surviving *categorized*
  pending twin counts, alongside its booked self, and the dinner is spent twice. That is
  the defect the sweep exists to prevent, and it is worse than losing a category. So the
  asymmetry is deliberate; `_sweep_stale_pending_transactions` should say so, since its
  docstring currently gives the Ignored exemption a rationale that reads as general.

  What would actually fix it is identity, not exemption: carrying a decision across the
  pending-to-booked transition needs the two rows recognised as one transaction, which
  the content hash cannot do by construction. That is a real piece of work — match on
  amount, counterparty and a date window — and it belongs with the recurring-payment
  matching in Phase 9 rather than bolted onto the sweep. Unreachable today in any case:
  restricted production has one bank, and whether it supplies stable pending
  identifiers is still unknown. If it does, this cannot fire at all.

**Tickets 16 and 17 were one defect in two interfaces, and the split was taken.**
Both files recorded the same alternative and both declined it for touching the status
enum `ADR-0002` fixed at five values. With two tense defects open rather than one, and
ticket 17 being exactly the "next client re-implements the comparison" that ticket 11's
review predicted, that trade was re-decided rather than inherited.
`safe_to_spend_status` now carries `month_closed` and `month_not_started` in place of
`not_current_month`, tense outranks `no_budget`, and `ADR-0002` records the amendment.
That closed ticket 16 and shrank ticket 17: the Telegram formatter reads the tense off
the status instead of needing one of its own, so all that was left there was the
rendering, which ticket 17 then took.

---

## Phase 9: "Is this normal?" — Split; 9a shipped, 9b not started

**The phase was split before any code was written**, during
`/grill-with-docs`. Its six scope bullets hold three independent machines, and two
of them are each larger than Phase 8's original scope was — which Phase 8 then
overran by sixteen tickets. The split falls on the natural seam:

* **9a — baselines.** Trailing per-category averages, month-over-month comparison,
  and anomaly flagging on category totals. All three hang off the same aggregation.
  **Shipped**; its Definition of Done is checked below.
* **9b — recurring charges.** Recurring-payment detection, the subscription
  inventory and price-change detection. All three hang off matching by counterparty
  and need no baseline at all. **Not started.** It also owes the last open Phase 8
  gap, because carrying a decision across the pending-to-booked transition needs the
  same identity matching.

The Definition of Done below is the *whole* phase's and is not satisfied: its
second clause is entirely 9b's. **Phase 9 is open.** The original clause was also
**rewritten on 2026-11-02** after it failed its own check; both versions are below,
and **Revised: what a baseline is for** is the argument that forced it.

### Objective

Give every number a baseline, so the product can distinguish a level from a
change. This is the prerequisite for anything proactive — an alert with nothing
to compare against is just the dashboard read aloud.

### Scope

* Trailing per-category averages over a configurable window (default 3 months).
* Month-over-month comparison on spending, income and per-category totals.
* **Recurring-payment detection**: same counterparty, stable cadence, similar
  amount. This is deterministic pattern matching, not a model.
* Subscription inventory derived from the recurring set, with total monthly cost.
* Price-change detection on recurring items ("this went up 2 EUR in March").
* Anomaly flagging on transactions and on category totals, relative to baseline.

### Notes

Prefer computing from source transactions. If query cost becomes a problem,
introduce a monthly snapshot table — but measure first, and keep derived metrics
derived, per the database rules in `AGENTS.md`.

### Definition of Done — superseded

> Every headline figure on the dashboard is shown against its own baseline, and the
> owner can see a list of their recurring commitments and total subscription cost
> without having gone looking for it manually.

Kept as written because what it got wrong is the lesson. Its first clause names no
enumerable set, so it could only be evaluated by inventing a denominator at close —
and when that was done it scored **3 of 8** and got the denominator wrong on the
first attempt. The replacement is below; the reasoning that forced it is under
**Revised: what a baseline is for**.

### Definition of Done — revised

Eight dashboard figures, named, each with its answer fixed in advance:

| Figure | Baseline? | Why |
|---|---|---|
| Monthly income | **yes** | the one figure no budget states, so history is the only possible source of normal |
| Monthly spending | **yes**, on the Comparable Spend basis | with its uncomparable residual disclosed beside it |
| Net cash flow | **yes** | met 2026-11-02: `figure_baseline_amount` is a median, which is the protection it had none of. Published as an amount with no band, because a ratio on a figure that crosses zero means nothing |
| Safe to Spend Today | no | comparing an allowance across months mixes a budget, a month length and a fixed overrun, all of which moved |
| Budget left | no | a budget the owner changed; the budget *is* the statement of normal |
| Projected spend | no | a plan, not an outcome |
| Burn rate | no | already compared against the plan, which is the comparison that acts on it |
| Current balance | no | a level with no month, so a monthly mean says nothing about it |

Every "no" renders **one line saying which kind of blank it is**, so that "no history
for this", "deliberately not compared" and "nobody asked" are not the same pixel.

And three rules, each of which must be the sole cause of a failing test:

* A month's spend declared an event by a **one-month Fixed Budget window** reaches no
  baseline. The test fails with `BASELINE_PRESENCE_FLOOR` neutralised, or the rule has
  no test — see the third failure mode in `AGENTS.md`.
* **No baseline is offered at all** while the qualifying months behind it are events
  rather than months. `BASELINE_MINIMUM_MONTHS` is what enforces this.
* The recurring half stays 9b's and is enumerated the same way: **the recurring
  commitments present in the live data at close, listed by name in the spec**, not
  "their recurring commitments".

### Definition of Done: checked (9a)

Checked against the implementation rather than assumed, and against the live
database rather than only the tests. Phase 8 learned that its own check was not
enough — the check found five gaps and per-ticket review found five more — so this
one reads the running product too.

| Clause | Result | Evidence |
|---|---|---|
| Every headline figure on the dashboard is shown against its own baseline | **Not met as written: three of eight** | Monthly spending, Monthly income and Saved this month each carry a comparison, asserted in `web/tests/DashboardPage.test.tsx`. Safe to Spend Today, Current balance, Budget left, Projected spend and Burn rate do not. This check first recorded the denominator as **seven**, having missed Burn rate — which is evidence for the wording gap below rather than a separate slip. See the gaps. |
| The owner can see their recurring commitments and total subscription cost | **Not met** | 9b, not started. Nothing in the codebase detects a Recurring Charge. |
| Trailing per-category averages over a configurable window, default 3 months | Met | `BASELINE_WINDOW_MONTHS`, default 3, read through the dependency the route uses and asserted by behaviour rather than by attribute. |
| Month-over-month comparison on spending, income and per-category totals | Met in substance, not on the stated surface | Spending, income and net cash flow are on the dashboard. The per-category comparison is on the **Categories** page, not the dashboard, and the dashboard's own per-category rows carry none. See the gaps. |
| Anomaly flagging on category totals, relative to baseline | Met | One status over five bands in `burnrate.domain.baselines`, fired one-sided at 1.5× the baseline, as a worked-example table. |
| Anomaly flagging **on transactions** | **Not met, deliberately** | Needs a per-transaction distribution. Two Qualifying Months with eleven rows in a category is not one. Recorded in the spec's Out of Scope rather than discovered later. |
| Derived metrics stay derived; measure before any snapshot table | Met | No migration, no table, nothing stored. Measured before and after: 6 statements to 13-15 live, 25 at the ceiling; the decision is no snapshot table, with widening the window named as the trigger to revisit. |

### Known gaps (9a)

Recorded explicitly, because Phase 3 was closed over a known gap and it stayed
closed for six phases.

* **Five of the dashboard's eight figures have no baseline, and only one of those is
  a decision.** Safe to Spend Today is excluded deliberately and has a test saying so
  — comparing an allowance across months mixes a budget, a month length and a fixed
  overrun, all of which moved. **Current balance, Budget left, Projected spend and
  Burn rate were never examined at all.** Two of them plausibly deserve the
  allowance's reasoning (Budget left is a budget the owner changed; Projected spend is
  a plan, not an outcome) and Current balance plausibly deserves a baseline, but none
  of that was decided — it was simply not asked, and the Definition of Done says
  "every".

  **Burn rate is the sharpest of the five**, and the one this check itself missed: it
  is the only figure that already carries a comparison — `vs €20.00/day planned` —
  against the *budget* rather than against the owner's *past*. That is precisely the
  distinction Phase 9 exists to add, on the one figure where it was never considered.
* **The same cause produces a sentence on one card and silence on two others.** With
  `baseline_status == "insufficient_history"`, the spending card says "not enough
  history to compare yet" while Monthly income and Saved this month render nothing —
  because the spending card branches on `baseline_status` and the other two branch on
  their own null `baseline_amount`. Identical cause, three different surfaces. The
  product already decided that silence is a claim; that decision reached one card.
* **A blank beside a figure now means three different things and looks the same.**
  "No history for this" (income, saved), "deliberately not compared" (Safe to Spend
  Today) and "nobody ever asked" (the other four). The owner cannot tell them apart,
  which makes the cheap fix not four more baselines but **one line per figure saying
  which of the three it is**.
* **The clause could not be checked as written, and that is the reusable lesson.**
  "Every headline figure" names no enumerable set, so the clause was neither true nor
  false until someone invented the list at close — and the first attempt got the
  denominator wrong. Phase 8's DoD had the same shape (*"**No** financial rule or
  threshold remains in the Web UI"*) and resolved it by carving an exception into its
  own evidence row; it got away with it because the exception was defensible.
  **Phase 11's DoD has the same shape waiting** — *"no documented metric remains
  unimplemented"* — and it is the clause Phase 3 failed silently for six phases. A
  clause that can only be evaluated by inventing its denominator at close is an
  opinion issued when it is most expensive to act on. Enumerate the set in the
  clause.
* **The dashboard's Budget pulse rows are silent while the Categories page's rows
  are not.** Both render the same categories for the same month; one carries the
  comparison and the other does not. Cheap to close: the per-category payload already
  exists and joins by category id. Left open only because no ticket owned it.
  `budget_usage` is the wrong carrier on its own, though — it holds only budgeted
  categories, which is why the comparison travels in a list of its own.
* **Nothing yet is proactive**, by design. 9a makes the comparison visible; Phase 10
  is what makes the product speak first.
* **`as_utc` is a clock concern living in a consent module.** Baseline sync coverage
  imports it from `services/connection_expiry.py`, where its own docstring says it is
  for a datetime read back naive from SQLite. It was imported rather than duplicated
  or moved, because `AGENTS.md` forbids riding a refactor along on a feature; the
  review stage was where it should have been picked up and was not. Two readers now,
  so the next one is the trigger.

### The gap that is not in the code (9a)

**The live product shows no comparison at all today**, and the reason is the data
rather than the implementation. Both the current and a closed month report
`insufficient_history` with **zero** Qualifying Months, because the sync history has
a **36-day hole from 2026-08-29 to 2026-10-04** — wider than the 30-day fetch window.
The sync-coverage rule found it; nothing else in the system reports it.

August and September therefore **can never qualify**: no entry point can request a
window older than 30 days, so 30 August to 3 September will never be fetched. Their
spending totals are understated by whatever fell in those days, and every figure
BurnRate has ever reported for those two months is too.

Two consequences worth carrying into Phase 10 and beyond:

* **The feature becomes demonstrable in December 2026** without anyone touching it,
  once October and November are both closed and inside the window. It can instead be
  demonstrated today by classifying the June and July backlog — both months *are*
  sync-covered — and setting `BASELINE_WINDOW_MONTHS=5`. That this is an environment
  variable rather than a migration is the return on refusing a stored accumulator
  during design.
* **Nothing alerts the owner to a sync gap.** A lapsed consent writes a `skipped`
  session per attempt and the product carries on reporting figures for months it
  never fully fetched. That silence is now load-bearing for Phase 9's value and is a
  strong candidate for Phase 10's first alert — it is the one case where the product
  knows something the owner cannot see.

### The leak with a deadline (9a)

The sync hole above is why no comparison shows **today**. This is what happens when
one does. Measured against the live database on 2026-10-26, not reasoned about:

```
month    sync covered   unclassified share of outgoing   qualifies
2026-06       yes               66.6%  (4,661.72)           no
2026-07       yes               62.9%  (4,952.77)           no
2026-08       no                 0.0%                       no, permanently
2026-09       no                 0.0%                       no, permanently
2026-10        —                 2.2%    (212.99)           yes, once it closes
```

August and September are perfectly classified and permanently disqualified; June and
July are fully fetched and disqualified only by the backlog. So a window of three
from **December 2026** reaches September, October and November, September is gone,
and what is left is **October and November — exactly the two-month minimum**.

> **The first baseline this product ever shows its owner will be a two-month mean,
> and one of the two months is October 2026.**

October 2026 holds **€8,403.83** in a category named `Divorce` — five booked
transfers, the largest €5,000.00, dated the 1st and the 9th — against a monthly spend
of €9,251.08. It is 90.8% of the month and 97.2% of all unbudgeted spend. Three of the
four aggregate baselines survive that; one does not.

| Baseline | Survives October? | Why |
|---|---|---|
| Per-category | **yes** | `Divorce` has spend in one of the two months, and `BASELINE_PRESENCE_FLOOR` is 2, so it is denied a baseline |
| Comparable spend | **yes** | built from the per-category baselines, so a category without one cannot enter it |
| Monthly income | yes | the charge is spend |
| **Net cash flow** | **no** | `figure_baseline_amount` is a plain mean with **no presence floor and no outlier handling** |

The exemption is deliberate and documented — *"a month in which nothing came in is a
fact about the owner's year, and skipping it would report a salary as normal to
someone who was paid once in three months"* — and it is exactly what lets the charge
through. October's net of **−€354.88** enters whole and carries **half** the weight of
the owner's first-ever "normal".

> **Correction, 2026-11-02.** That −€354.88 was itself wrong, and wrong by a factor of
> twenty-three. `From Savings` was typed `income`, so five credits from the owner's own
> savings totalling €7,841.00 counted as money earned; the figure was measuring how
> much the *current account* drained. October's real net is **−€8,208.87**. Retyped by
> `0009_from_savings_is_a_transfer`; see `docs/adr/0010-a-savings-draw-is-a-transfer.md`.
> The leak this section describes is worse than it says, not better.

The consequence is not a wrong pixel. From December 2026 the product begins telling
the owner that a monthly deficit is normal for them, the divorce is laundered into
their baseline, and **nothing anywhere says so**. Every remedy below has to land
before then, and the per-category protection that does work is the reason this is one
figure rather than all of them.

Two things that do **not** fix it, recorded so they are not re-proposed:

* **A Fixed Budget on the category.** It fixes the pace figures (see the proposal
  below) and has no effect here. *Corrected 2026-11-02:* this said `_category_spend`
  has "no budget awareness at all", which is wrong in letter — `_fixed_categories_by_month`
  does read `Budget.is_fixed`, month by month. But it reads it only to decide whether
  **pending** spend counts, and all seven divorce rows are booked, so they enter every
  baseline in full. Right in substance, and the correction matters because a reader
  checking the claim would have found the budget join and concluded the opposite.
* **A median or a trimmed mean.** At the two Qualifying Months the minimum allows, a
  median *is* the mean. Robust statistics need a distribution, and per-transaction
  distributions are out of scope by decision, not by omission.

The cheap mitigation that does work is already named above: classifying the June and
July backlog (**€9,614.49** of unclassified outgoing money across the two) and
widening `BASELINE_WINDOW_MONTHS` to 5. From October that window reaches May to
September and **excludes the divorce entirely**, because October is the month on
screen rather than a candidate. It buys a clean baseline now and dilutes October to a
third of the weight later.

> **Outcome, 2026-11-02.** July was classified: 62.9% of outgoing money unclassified
> down to **0.0%**, so it qualifies. The mitigation did not work, and the reason is the
> one thing nobody checked — **July is an outlier too.** It holds a €5,500.00
> severance, €4,821.00 of it moved to savings the same week, giving a **+€2,909.73**
> month. Diluting a divorce with a severance is not a baseline. The three answers it
> produces are measured under **Revised: what a baseline is for**, and all three are
> false. June is still 66.6% unclassified and a 5-month window from December does not
> reach it anyway.

---

## Revised: what a baseline is for

Written on 2026-11-02, after the owner's own objection: *an unforeseen expense wrecks
the baseline, unforeseen expenses happen easily — a mortgage, a car, a car repair, a
trip — and having to wait months for it to be clean again is bad design.* The
objection is right about something specific and wrong about something specific, and
the difference is what this section exists to fix.

### Four examples, four different things

**A mortgage is not an outlier.** It is a new recurring commitment, the owner enters
it as a Fixed Budget, and the baseline should rise at once. A baseline that takes
three months to notice a mortgage is wrong for being *slow*, not for being fragile.
Nothing here needs changing for it.

**A car or a trip is an event**, and the owner already declares it without being
asked. On 2026-11-02 they bounded `Divorce` and `Relocation` to `2026-10-31`
themselves, using a primitive they already understood, for an unrelated reason. That
is the whole argument for reading the *window* rather than asking for a flag: the
Exceptional Charge was declined twice because it asked for a new gesture, and a
one-month Fixed Budget window asks for none.

**A car repair is the case the objection was really about, and it was measured.** July
2026 holds €565.40 of `Car Maintenance` over 6 rows, against €3,015.02 of spend.
Removing it moves a three-month spend mean from €2,713.59 to €2,525.13 — **7.5%**,
inside the 15% in-line band. It is absorbed and never reported. That generalises: a
one-off small enough not to budget is small enough not to move a mean, and one large
enough to move a mean is one the owner would have budgeted. The gap between the two is
narrower than it looks from outside.

### What actually breaks it is two numbers and a hole

Not the idea. `BASELINE_WINDOW_MONTHS` is 3 and `BASELINE_MINIMUM_MONTHS` is 2, so **a
single event is half of "normal"** — and two of the owner's five months are
permanently dead from a 36-day sync hole. At a twelve-month window a divorce is one
month of twelve and none of this conversation exists.

So the fragility is a property of starting up, made acute by a data accident. It is
still a real defect, because every product starts up.

### The defect that is narrower and worse

Per-category baselines **are** protected: `BASELINE_PRESENCE_FLOOR` denies a mean to a
category with spend in fewer than two Qualifying Months, so an event in a new category
never becomes a normal.

The aggregates had **no protection at all**. `figure_baseline_amount` was a plain
mean — no presence floor, no outlier handling — and the exemption was deliberate and
documented. That exemption is the hole October walks through, and no budget and no
window rule closes all of it, because an exceptional *income* has no budget to bound.
The owner's July is the proof: a €5,500.00 severance, €4,821.00 of it moved straight
to savings, giving a **+€2,909.73** month.

> **Closed 2026-11-02, by a median.** 9a rejected a median and was right to on the
> floor it had: *"at the two Qualifying Months the minimum allows, a median is the
> mean."* A median of **three** is not the mean — it rejects exactly one outlier — so
> raising `BASELINE_MINIMUM_MONTHS` to 3 is what made it available, and the two
> changes only work together. The function had **no test of its own at all** until
> then; it was exercised only through the service, which is how a plain mean survived
> in the one figure that needed robustness most. Over {July, October, November} it now
> reads **−€1,568.45** where the mean read −€2,289.20, and income reads **€1,055.20**
> where the mean read €2,653.38. "Normally" now means typical rather than average,
> which is the claim the product was making in words all along. ADR-0012 records it,
> including why a category keeps its mean and the trap that **lowering the minimum
> back to 2 silently turns this median back into a mean** with nothing to say so.

**Half the system is protected and the half that is not is the half that is lying.**

### Measured: every answer available on 2026-12-01 is false

Corrected months, after `From Savings` was retyped and July classified:

| Month | Net | What it is |
|---|---|---|
| 2026-07 | **+€2,909.73** | a severance |
| 2026-08 | −€1,596.91 | ordinary — **permanently disqualified** |
| 2026-09 | −€1,568.45 | ordinary — **permanently disqualified** |
| 2026-10 | **−€8,208.87** | a divorce |
| 2026-11 | in progress | — |

With November landing near September, the three reachable answers are:

| Scenario | Qualifying | Baseline |
|---|---|---|
| Window 3, as shipped | Oct, Nov | **−€4,888.66** |
| Window 5, July classified | Jul, Oct, Nov | −€2,289.20 |
| Window 5 + the event rule | Jul, Oct, Nov | **+€395.41** |

The third is the worst: the rule removes the divorce and leaves the severance, so the
product tells an unemployed owner burning €1,600 a month that they normally save €395.
The second looks defensible and is an accident — a severance cancelling a divorce.

**The owner's only two ordinary months are the two the bank was never asked about.**
Everything that qualifies is an event. The baseline is not missing a rule; there is
nothing normal to average.

### The claim shrinks

The original Definition of Done promised a baseline beside every figure and scored 3
of 8. That was read as eight gaps to close. It is better read as the goal being wrong.

The owner has already told the product what normal is: **it is the budget.** A
baseline is a second, derived, fragile answer to a question already answered. Where it
is not a second answer is narrow, and that narrow set is what the revised Definition
of Done keeps:

* **Income**, which nobody budgets, so history is the only source.
* **Telling the owner their budget is unrealistic** — budget €450 of food against
  €600 spent every month and the budget says "over" forever and teaches nothing, while
  the baseline says "this month is like your months". There the baseline does not
  compete with the budget; it corrects it.

Outside those, *"is this normal?"* competes with *"am I on plan?"*, and the second is
the hero metric — which uses no baseline at all.

### The structural answer, named as such

**Widen the window.** At twelve months with a median instead of a mean, outliers stop
mattering and the robust statistics that are out of scope today become available,
because a median needs a distribution and twelve months is one. It cannot be done now:
there are five months of history, two of them dead.

9a measured the cost of the window before deciding against a snapshot table — 6
statements to 13-15 live, 25 at the ceiling — and named *widening the window* as the
trigger to revisit that decision. **This is that trigger being claimed in advance.**
Twelve months and a median is the target shape; every parameter change before then is
a patch on N=2 and should be recorded as one.

### What this costs, in order

1. **`BASELINE_MINIMUM_MONTHS` to 3**, before 2026-12-01. One line. Not a delaying
   tactic: any number the product could publish that day is false, and it already
   knows how to say *"not enough history to compare yet"*. Saying it is the correct
   output.
2. **The event rule.** A predicate beside `budget_covers_month` — `is_fixed` and both
   edges on the same month's boundaries, which ADR-0005 makes an exact comparison —
   applied in `_month_spending` and `_category_spend` and nowhere else. It does not
   rescue December, and it makes every month after it clean with no new gesture from
   the owner. Owes an ADR at implementation.
3. ~~**Protect the aggregates**~~, which is the defect this section exists to name.
   **Done 2026-11-02**: a median, which needed the minimum of three above it and
   nothing else. The guess that it "needs the window first" was wrong — the window
   would have helped a median, but three months were already enough for one.
4. **Then the window**, with the snapshot-table decision reopened against measurement
   rather than against the estimate 9a made.

---

## Declined: the Exceptional Charge

**Declined by the owner on 2026-11-02, twice over, and the reasoning is kept because
what replaced it is weaker in one place and stronger in another.**

The pace half was solved instead by a **Fixed Budget** on `Divorce`, bounded to
`2026-10-01`-`2026-10-31`: `_project_fixed` steps it and `fixed_booked_spend` lifts it
out of the variable slice, so October's burn rate reads €22.71/day against €20.00
planned instead of €302.84. That is the figure set this proposal argued a Budget could
not be trusted with, and over one month it can — the objection was never mechanical,
it was that a Budget's default is to continue. Bounding the window is what answers it,
and the owner bounded it unprompted.

The baseline half is taken by the **event rule** above, which reads that same bounded
window instead of asking for a declaration. The proposal's own argument is why: a
category-level flag is a new gesture, and the window is one the owner already makes.

What the Budget does **not** cover, and this proposal would have: a one-off inside an
*ordinary* category — a boiler repair filed under `Home` — which no budget window can
express without inventing a budget for it. That case is unreached in the live data and
is the reason this section is kept rather than deleted.

The original reasoning follows unchanged.

### Why it was proposed

One primitive, which closes a live Phase 8 defect and the Phase 9 leak above with the
same rule, and which the owner's October is the worked example for.

### The product models two kinds of spend and there are three

1. **Budgeted recurring** — rent, food. Has a budget; paced, or stepped if fixed.
2. **Unbudgeted ordinary** — the small unplanned stuff. *Must* pace, and must erode
   the allowance.
3. **Exceptional** — the divorce, a boiler, a car written off. Real money, but neither
   a rate nor a budget overrun. An event.

**2 and 3 are collapsed into "unbudgeted", and that collapse is the defect.** An
exceptional charge has no budget, so it is not `is_fixed`, so it lands in the variable
slice and is extrapolated as a daily rate.

### What that does to the live dashboard

October 2026, day 26 of 31, with the €8,403.83 charge in the variable slice:

| Figure | Live value | What the charge does |
|---|---|---|
| Burn rate | €349.04/day vs €20.00 planned | **swallowed whole** — 17× the plan |
| Projected spend | €10,730.94 | **extrapolated forward**, as though the divorce continued at €349/day |
| Monthly spending | €9,251.08 | counted. Correct. |
| Saved this month | −€354.88 | counted. Correct. |
| Safe to Spend Today | **€32.13, `on_track`** | **invisible to it** |
| Budget left | €313.83 | invisible to it |

These are two opposite failures. The pace figures treat the charge as **recurring**;
the budget figures **cannot see it**. Only the actuals are right.

Removing the charge from the variable slice gives a burn rate of **€25.82/day**
against €20.00 planned — 29% over, a number that can be read and acted on.

The allowance's blindness is a **third, separate** matter and should not be folded in
here. It draws on `variable_budgeted_spend`, so spend with no budget cannot reduce it;
that is internally consistent. But the live consequence is that with **€164.51** in
the account the product says spend €32.13 today and calls it on track, and five
remaining days at that allowance is €160.65 — the balance, near enough. Nothing in
that figure is computed from what is actually in the bank. **That belongs to
Phase 11's cushion**, and it is listed here only because it is live.

### Why a Budget is the wrong carrier

A one-month Fixed Budget window looks like it should work, and mechanically it does:
`_project_fixed` steps it rather than extrapolating, and `fixed_booked_spend` lifts it
out of the variable slice. Two things make it the wrong answer.

**A budget's default is that it continues.** A one-off's default must be that it does
not. The create endpoint takes `active_from` and **not `active_to`** — a budget can be
scheduled to *start* and can only be ended afterwards, from a later month, by
`deactivate_budget`, which sets `active_to = month_start - 1 day`. So the owner cannot
express "October only": cancelling **in** October ends the window before October
begins, and only cancelling **in November** produces the intended window. A primitive
whose null state is recurrence cannot represent an event; it can only be simulated by
a human remembering, in one specific month, to correct it.

**Forgetting does not merely clutter the page, it invents money.** Cancelled a month
late, the window covers October and November, and in November the category has a
€8,403.83 fixed budget with nothing booked against it. `_project_fixed` falls back to
the budgeted estimate when nothing has booked, so November's Projected spend carries a
phantom €8,403.83, Budget left reads ~€8,717 instead of €313.83, and Budget pulse
renders a neutral `Divorce` row that reads as a fixed bill not yet paid.

The right carrier is therefore **the charge, not a window of time**. A charge is
singular by construction — it happened once, on one date. Nothing to cancel, nothing
to roll forward, no November. The codebase has already made this exact choice once:
`excluded_at` lives on the transaction rather than on a budget window.

### The primitive

A third disposition, in the gap between `excluded_at` (out of *everything*) and
nothing — the figure-specific inclusion rule ADR-0003 already established for Pending
Spend:

> **Exceptional Charge** — counted in the actuals. A step in the pace and the
> projection, never a rate. Excluded from every baseline.

The term was fixed in `GLOSSARY.md` beside `Ignored` and has been **removed from it**,
because a declined concept is not the product's language. `Event Budget` stands in its
place, in the Budgets section rather than among the dispositions, which is the whole
difference between the two: this was a disposition the owner set on a charge, that is a
budget window they bound. Both are kept distinct from the `anomalous` comparison status
on purpose: that is a verdict the product computes against a baseline.

One concept, three rules. It fixes the burn rate and the projection for the month in
progress, and it is the only thing above that also stops October 2026 from becoming
the owner's normal in December.

**Where the flag goes has two answers, and the live data picks the cheaper one.** The
€8,403.83 is not one charge but **five** booked transfers dated the 1st and the 9th,
so a purely per-transaction disposition means the owner marks five rows and keeps
marking them as more arrive. Both exceptional clusters in the live data sit in
categories of their own — `Divorce`, and arguably `Relocation` — which makes a
**category-level flag the cheap 80%**: one mark, permanent, every charge in that
category exceptional in every month. It also has none of the Budget's problem, because
a category carries no time window at all, so there is nothing to cancel in November.

The per-transaction disposition remains the general case and should follow rather than
lead: it is the only one that reaches a one-off inside an *ordinary* category — a
boiler repair filed under `Home` — which no category flag can express. Taken in that
order, the first step is a boolean on `Category` and the second is a nullable column
on `Transaction`, and neither invalidates the other. A categorization rule setting the
flag is a third option worth weighing, since three of the five rows share a
counterparty.

### Known gap it exposes

`POST /budgets` accepts no `active_to`. A commitment can be given a start date, even a
future one, but can only be given an end retroactively from a later month. That
asymmetry is independent of this proposal and worth closing on its own.

---

## Phase 10: "Tell me, don't make me look"

### Objective

Invert the interaction model. Today Telegram is a pull interface for a dashboard
the owner has to remember to check; this phase makes BurnRate speak first.

### Scope

* Weekly digest pushed over Telegram: what changed against baseline, where the
  month is heading, one suggested action.
* Event-triggered alerts, deterministic and rate-limited:
  * projected overspend crosses the monthly budget
  * a category crosses its threshold
  * an anomalous transaction lands
  * a recurring payment changes price or fails to appear
  * the unknown queue grows past a threshold
* Alert preferences and quiet hours, so the channel does not get muted.
* Reuse existing backend services. The bot stays free of financial logic.

### Notes

The `telegram-bot` worker and `notifier` module already exist, so the
infrastructure cost here is low. The real design work is **restraint**: an alert
that fires too often gets muted, and a muted channel is worse than no channel.
Every alert must be defensible as something the owner would act on.

### Definition of Done

Over a full month, the owner learns something actionable they did not already
know, without having opened the Web UI — and has not muted the bot.

---

## Phase 11: "How long would I last?" (Runway, redefined)

### Objective

Close the Phase 3 gap and make the product's own name mean something, with a
definition that is valid for a salaried saver.

### Scope

* Schema: account purpose, so a balance can be explicitly marked as savings
  available for runway. Migration required; `included_in_calculations` is not a
  substitute.
* **Cushion**: savings balance divided by trailing average monthly *expenses* —
  "my savings cover N months of my life". Well-defined whether or not the owner
  is in deficit.
* **Deficit runway**: retained as a conditional view, shown only when trailing
  net cash flow is actually negative. This is the original definition, correctly
  scoped to the case where it applies.
* Expose both through the summary API, the dashboard, and the `/runway` Telegram
  command already promised in `docs/product/mvp.md`.
* Update `docs/product/metrics.md` in the same change.

### Notes

Deliberately placed after the retention work, because for the target user this
is a reassurance metric checked occasionally, not a daily driver. It is small and
well-understood, so pull it forward freely if the dashboard's missing runway
starts to grate — it has no dependency on Phases 8 to 10.

### Definition of Done

The dashboard states how many months the owner's explicitly-marked savings would
cover, and no documented metric remains unimplemented.

**Enumerate "documented metric" before starting.** This clause has the shape 9a's
first clause failed on — a universal over a set named nowhere — and it is the clause
Phase 3 failed silently for six phases. The set is small and knowable from
`docs/product/metrics.md` and `docs/technical/domain.md`; listing it here turns the
check into arithmetic instead of judgement. Phase 11 also inherits the live case
recorded under the Exceptional Charge proposal: the allowance is computed from budgets
and knows nothing about the balance, which on 2026-10-26 meant €32.13/day and
`on_track` against €164.51 in the account.

---

## Phase 12: AI Assistance

### Objective

Use a model where deterministic rules genuinely cannot reach, without making the
product dependent on one.

### Scope

* **Categorization copilot** — the primary deliverable. Rules stay the fast path;
  anything the rule engine misses goes to a model, which proposes both a category
  *and* a generalized rule. The owner confirms with one action, and the
  confirmation writes the rule. The system becomes **more** deterministic with
  use, not more model-dependent. `created_from_manual_classification` and
  `apply_to_existing_uncategorized` in `RulesService` already support this shape.
* **Merchant normalization** for the recurring detection in Phase 9, where dirty
  counterparty strings defeat exact matching.
* **Digest narration** in Phase 10: the numbers and the trigger logic stay
  deterministic; the model only selects what deserves mention and writes the
  prose.
* Optional natural-language queries over existing APIs via tool use. Lowest
  priority — it demos well and gets used least.

### Architecture constraints

* Define a domain-level interface (e.g. `CategorySuggester`). Application logic
  depends on that, never on a provider SDK or response shape, per the dependency
  inversion rules in `AGENTS.md`.
* One implementation only, until a second real use case exists. No
  multi-provider abstraction.
* **Opt-in and degradable.** `docs/product/overview.md` promises no required
  cloud dependency, and sending transaction data to a hosted model is in tension
  with that. With the feature disabled, every Act II phase above must still work.
  A local implementation can land behind the same interface later.
* Never let a suggestion write a category without confirmation. Suggestions are
  proposals; rules are truth.

### Notes

This phase has **no dependencies** and can be pulled forward at any time. It sits
here only because the rule engine already handles the common case, so the value
is in the tail. If the unknown queue is the daily friction, promote it.

### Definition of Done

The unknown queue can be cleared in a fraction of the taps it takes today, every
confirmation leaves a reusable rule behind, and turning the feature off degrades
the product without breaking it.

---

## Phase 13: Operational Resilience

### Objective

Protect the data now that a real financial history lives in the system. This was
Act I's Phase 7; it was correctly deferred, and it is now genuinely owed.

### Scope

* `pg_dump`-based backup and restore scripts wired for Docker Compose.
* Documented restore procedure.
* Explicit handling of `BANK_TOKEN_ENCRYPTION_KEY` in the backup story — a
  restore without the key yields a database whose bank tokens cannot be
  decrypted.

### Definition of Done

A restore has been exercised at least once and reproduces the owner's data on a
clean stack, including working bank connections.

---

## Milestone View

Act I, complete:

* **Data In** — connect to Enable Banking, import real balances and transactions.
* **Data Understood** — show transactions, classify unknowns, store rules.
* **Data Becomes Insight** — budgets, money left, burn rate.
* **Data Stays Fresh** — automatic refresh through the sync worker.
* **Access Anywhere** — summaries over Telegram.

Act II, under way:

* **Data Becomes a Decision** (Phase 8) — one number that changes what the owner
  does today. Shipped, with the gaps listed under that phase still open.
* **Data Gets a Memory** (Phase 9) — every figure has a baseline. 9a shipped: the
  comparison exists and refuses to speak when it cannot speak honestly. 9b, the
  recurring charges, is not started.
* **Data Speaks First** (Phase 10) — BurnRate reaches out instead of waiting.
* **Data Gets a Horizon** (Phase 11) — how long the cushion lasts.
* **Data Gets Help** (Phase 12) — the model handles the tail the rules cannot.
* **Data Survives** (Phase 13) — backup and restore, proven.

---

## What Not To Do

Still off the table, and now for firmer reasons:

* **Multi-provider banking abstraction.** One provider works; a second is not on
  the roadmap.
* **Multi-tenant or multi-user models.** The product is single-owner by design,
  and the narrowed target user makes this less relevant, not more.
* **Net-worth or investment tracking.** Explicitly a non-goal in
  `docs/product/overview.md`, and nothing in Act II changes that.
* **Making the AI load-bearing.** If a disabled model breaks a core flow, the
  design is wrong.
* **More alerts than the owner will tolerate.** Phase 10 fails by over-firing,
  not by under-firing.
* **Charts for their own sake.** The product competes with a fuel gauge, not with
  a BI tool. A new visualization needs to change a decision.

---

## Between Phase 8 and 9a: the category lifecycle

Not a phase, and recorded here because it shipped between the two and the roadmap
would otherwise read as though Phase 8 were the last thing that happened.

Categories could only ever be created: their name was fixed and nothing could retire
one, although `Category.active` existed and three guards already refused an inactive
category. Renaming now lives on the category rather than on a per-surface label, so
one rename reaches budget rows, rules, the dashboard and Telegram through joins that
already existed. Retiring is two operations, because deleting and archiving are not
the same act — delete only while nothing references it, archive otherwise, and both
refuse rather than cascade, because a category's budget rows are what past months
reported. ADR-0005 settled the month-granular budget window rules alongside it, and
ADR-0006 and ADR-0007 record the two decisions a future reader will question.

---

## Recommended Immediate Next Steps

Rewritten on 2026-11-02. The previous list put the Exceptional Charge third with a
December deadline; it was declined, the pace half is solved by a bounded Fixed Budget,
and the baseline half turned out not to be solvable in time by anything. Two items
below are new and two are gone.

Done since the last revision, recorded so the list reads honestly: **July is
classified** (0.0% of outgoing unclassified, down from 62.9%), **`From Savings` is
retyped** to `transfer` by `0009`, and **`0008` has finally been applied** — the live
database sat on `0007` for an entire phase, so every mid-month `active_to` the old
cancellation rule wrote was still being read as a budget the month held in full.

In rough order of value:

1. ~~**`BASELINE_MINIMUM_MONTHS` to 3, before 2026-12-01.**~~ **Shipped 2026-11-02.**
   Not one line, as this list first called it: it is a domain constant in
   `burnrate.domain.baselines`, and only `BASELINE_WINDOW_MONTHS` is configuration.
   On 2026-12-01 the window would have reached two Qualifying Months — a divorce and
   one ordinary month — and published **−€4,888.66** as the owner's normal. Every
   other reachable answer that day was also false, including the event rule's. The
   product now says *"not enough history to compare yet"*, which is the honest
   output. See **Revised: what a baseline is for**.

   It cost twenty-one fixtures across two files, because the floor of two was baked
   into every one of them. And it exposed a test passing for the wrong reason:
   `test_a_qualifying_months_own_hold_on_a_fixed_bill_is_excluded_too` claimed to
   cover the presence floor at the service seam, but with two Qualifying Months the
   window itself was below the minimum, so nothing earned a baseline and lowering
   `BASELINE_PRESENCE_FLOOR` to 1 changed nothing. Two rules masking each other,
   visible only to the mutation.

   **One consequence to carry**: a 3-month window with a 3-month minimum means all
   three months must be clean, so a single sync hole anywhere in the window silences
   the comparison entirely. Widening the window is not the fix — window 5 reaches
   July's severance. Item 2 is the fix.
2. **Close the sync gap, and alert on the next one.** Unchanged in substance and now
   the most valuable item on the list rather than the first of several. The 36-day hole
   killed **August and September** — the owner's only two ordinary months — so the
   baseline has nothing normal to average, and nothing in the product reports a gap.
   This is both the cheapest Phase 10 alert and the one protecting every figure
   Phase 9 produces.
3. ~~**The event rule.**~~ **Shipped 2026-11-02**, with item 1. A one-month Fixed
   Budget window — an **Event Budget** in `GLOSSARY.md` — declares that month's
   spend in its category an event, excluded from every baseline and from nothing
   else. `is_event_budget` lives beside `budget_covers_month`; the transaction filter
   is private to `BaselineService`, because the rule is "excluded from every
   baseline" and a shared predicate would sooner or later be added to a figure.
   ADR-0011 records it, with the three neighbours that must answer the other way: an
   open window, a two-month window, and the month on screen's own figures. Five
   mutations confirmed, one per rule. It does **not** rescue December — that is
   item 1, and the reason is July's severance, which is an exceptional *income* and
   has no budget to bound. Which makes item 5 the one that is left.
4. **Close 9a's cheap gaps**, now narrower than they were: the dashboard's Budget pulse
   rows, and one line per figure saying which kind of blank it is. The fourth part of
   this item — "a decision, either way, on Current balance, Budget left, Projected
   spend and Burn rate" — **is decided**, in the revised Definition of Done: all four
   carry no baseline, with the reason named per figure.
5. ~~**Protect the aggregate baselines.**~~ **Shipped 2026-11-02.**
   `figure_baseline_amount` is a **median**, which is the hole October walked through
   closed, and the one no budget could close — an exceptional *income* has no window
   to bound, and the owner's €5,500.00 severance in July was the worked example. It
   needed the minimum of three and nothing more; the note that it "needs the window
   first" was a wrong guess. It also gained the first tests it has ever had, including
   one at the service seam, because every other fixture in that module seeds identical
   months — where a median and a mean agree, which is how the mean survived.
6. **Widen the window, and reopen the snapshot-table decision.** Twelve months with a
   median is the target shape, and 9a named widening as the trigger to revisit the
   no-snapshot-table decision. Blocked on history: five months exist and two are dead.
   Everything above it is a patch on N=2 and should be recorded as one.
7. **Then 9b**: recurring-charge detection, the subscription inventory and
   price-change detection, which also owes the last open Phase 8 gap. Two notes from
   the 2026-11-02 grilling, which was cancelled before reaching a spec but not before
   reaching the data. **There is no counterparty**: `counterparty_name` is NULL in 610
   of 623 rows, `merchant_name` is NULL in 305 and is the *owner's own name* in 261,
   `bank_transaction_code` reads `"Banca online"` on all 623 and
   `merchant_category_code` is always NULL — so the only signal in the entire payload
   is a Spanish free-text `description`, and 9b's scope line "same counterparty,
   stable cadence, similar amount" names a field that does not exist. And **exact
   description matching splits three of the eight real subscriptions in half**: Claude,
   Google One and ChatGPT each arrive under two strings, leaving each half below any
   cadence threshold. Merchant normalization is not an improvement to 9b, it is 9b.
   The round-up saver is now **259** near-identical rows across five months, every day
   of the month, €0.01-€1.94.
8. **Decide whether to promote Phase 12's categorization copilot.** Sharpened a third
   time: classifying July took one afternoon and changed what three months report, and
   the backlog is what disqualifies months from being baseline input.

Phase 3's lesson was that a phase closed over a known gap stays closed for six
phases. Phase 8's gap list growing twice *after* its own check was that lesson
arriving again. 9a's version was narrower: **its check passed on the tests and failed
on the data**, and only reading the running product showed the difference.

The 2026-11-02 version is narrower still and is about the goal rather than the check.
9a scored 3 of 8 against "every headline figure", and that was read as five gaps to
close. It was the goal that was wrong: the owner had already stated what normal is —
it is the budget — and a baseline beside every figure is a second, derived, fragile
answer to a question already answered. **A Definition of Done can fail its own check
by being met too little or by being worth meeting too little, and the second takes
longer to notice.**
