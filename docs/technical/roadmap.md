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

## Phase 8: "How much can I spend today?" — Shipped, with known gaps

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
grew after it was written: the five below the line were the gaps this phase's
Definition of Done check found, and the four under "Found later" came out of
per-ticket reviews afterwards. Anything checking Phase 8 against this section has to
read both halves — reading only the first would have called the phase closed with
four tickets open and two verified defects live.

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

* **A month that has not started projects below the spend already committed in it**
  (ticket 15). `_days_elapsed_in_month` returns 0 before a month begins and
  `_project_spend` then returns the budget reference unchanged — its "no signal yet,
  assume spending tracks the budget" branch, which was true when a future month could
  not hold spend. Effective Date and pending-spend counting made it false. Verified: a
  500.00 standing order due in July, read in June against a 300.00 budget, reports
  `budgeted_spending_amount` 500.00 beside `projected_month_end_spend_amount` 300.00
  and `projected_overspend_amount` 0.00 — the projection says the month lands on
  budget while the headline already shows it blown. `_extrapolate_spend` has the same
  shape and
  returns 0.00 with no budget set.
* **A month that closed before the owner budgeted anything is told to set a budget**
  (ticket 16). `safe_to_spend_today` decides `no_budget` before it considers whether
  the month is the current one. Verified: May 2026 read on 15 June returns
  `safe_to_spend_status: "no_budget"` with `current_month: "2026-06"`, and the
  dashboard then prints its set-a-budget invitation over a month that closed weeks
  ago. Same family as ticket 11 — the page stating something about a month it does
  not know — and both branches are individually right, only their order is wrong.
* ~~**The Telegram summary has no tense**~~ **Closed by ticket 17.** `/summary <a future
  month>` printed a used-budget bar, a daily pace over zero elapsed days and a month-end
  projection for a month that had not begun, while the dashboard captioned the same
  payload "Not started yet". The header now names the tense in the dashboard's own badge
  words, read off `safe_to_spend_status`, and a month that has not started reports its
  budget and what is committed to it without the three lines that describe progress. A
  closed month keeps them, with a test so the suppression cannot widen.
* **A failed background refresh leaves no trace** (ticket 18) — **two thirds closed by
  ticket 14.** `refreshLedgerViews` had no `catch` and no `cancelled` guard, so a
  rejection was silent and a response arriving after a month change clobbered the newer
  state. Both were recorded rather than scheduled because neither could fire until a
  month could change, so ticket 14 took them with the selector: the refresh now records
  the month it was started for and discards a payload for a month the owner has left,
  and a failure reports itself twice — a toast, because the edit it followed did land,
  and `summaryError`, because the figures on screen are no longer trustworthy. What is
  left in 18 is its third defect, now narrowed to one page: the Categories panel still
  shows a stale payload for the month on screen with no signal, which is a parity call
  about what a few minutes of staleness is worth announcing rather than an open defect.

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
the status instead of needing one of its own, so what is left there is the rendering —
a used-budget bar, a pace over zero elapsed days and a projection, all still printed
for a month that has not begun.

---

## Phase 9: "Is this normal?"

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

### Definition of Done

Every headline figure on the dashboard is shown against its own baseline, and the
owner can see a list of their recurring commitments and total subscription cost
without having gone looking for it manually.

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
* **Data Gets a Memory** (Phase 9) — every figure has a baseline.
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

## Recommended Immediate Next Steps

Phase 8's original first three steps — the domain calculation, moving the
savings-rate threshold out of `DashboardPage.tsx`, and re-leading the dashboard
with the allowance — are done. What is left:

1. Give the Web UI a month selector and stop it choosing the month in UTC — one piece
   of work, not two, and ticket 14 owns it. Read ticket 18 alongside it: its first two
   defects become reachable the moment a month can change, and nothing writes the month
   until this ships.
2. Add trailing per-category baselines, as the foundation for Phase 9.
3. Decide whether to promote Phase 12's categorization copilot, based on whether
   the unknown queue is actually the daily friction.

Step 1 is the last thing Phase 8 owes. Tickets 15, 16 and 17 are done, so what remains
is the two user stories that shipped as code no owner can reach. Phase 3's
lesson was that a phase closed over a known gap stays closed for six phases — and this
section having grown twice after its own Definition of Done check is the same lesson
arriving a second time.
