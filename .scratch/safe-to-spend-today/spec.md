# Safe to Spend Today (Phase 8)

Status: ready-for-agent

Phase: 8 — "How much can I spend today?" (`docs/technical/roadmap.md`)
Design session: `/grill-with-docs`, 19 decisions, frontier closed
Decisions recorded: ADR-0001, ADR-0002, ADR-0003; vocabulary in `GLOSSARY.md`

---

## Problem Statement

The owner is a salaried person who does not want to overspend. They do not
struggle to afford their life; they drift past what they intended to spend and
only notice when the month is over.

BurnRate currently reports levels. It shows a current balance, a monthly budget,
money left, a burn rate and a projection — all correct, and none of them answer
the question actually being asked in the shop: *can I spend 40 EUR on dinner
tonight?* Answering it today means reading a gauge, finding the days elapsed,
and doing arithmetic in your head. So the owner does not do it, and the product
becomes something that reports the past rather than changes a decision.

Two further problems make the current answer worse than merely absent:

* Pending spend is invisible. Last night's card payment reduces nothing until
  the bank settles it, one to three days later. Any daily figure derived from
  today's data is therefore optimistic by exactly the amount most likely to
  matter, and optimistic in the direction that causes overspending.
* The Web UI invented its own financial rules where the domain had none — the
  savings-rate bands, the budget pacing verdict. One of them carries a bug that
  fires in the last week of every month.

## Solution

One number, as the headline of the dashboard: **Safe to Spend Today**. The
amount the owner can spend today without putting the month's Variable Budgets
out of reach.

It is remaining Variable Budget, less any Fixed Overrun, divided by the days
left in the month counting today. It is never negative. It counts Pending spend,
so it reflects what has actually been committed rather than only what the bank
has settled. It carries a status the owner can read as a colour without reading
the number, and that status is judged against On-Plan Remaining so it does not
warn every month-end for no reason.

It leads the dashboard above the balance, it leads `/summary` on Telegram, and
every threshold behind it lives in the backend.

## User Stories

1. As the owner, I want one number telling me what I can spend today, so that I can decide on a 40 EUR dinner without doing arithmetic.
2. As the owner, I want that number as the first thing on the dashboard, so that I do not have to go looking for the only figure that changes my behaviour.
3. As the owner, I want it to never go negative, so that an overspent month tells me to stop rather than offering me a meaningless minus figure.
4. As the owner, I want today counted among the days it has to cover, so that the figure on the last day of the month is the money actually left rather than a division by zero.
5. As the owner, I want Fixed Budgets left out of the allowance, so that rent being due does not make it look like I cannot buy lunch.
6. As the owner, I want a Fixed Budget that overshot its estimate to reduce my allowance, so that a 50 EUR rent increase does not quietly stay in my daily spending money.
7. As the owner, I want a Fixed Budget that has not been charged yet to keep using its estimate, so that a 1 EUR pre-authorization does not convince the product my utility bill will cost 1 EUR.
8. As the owner, I want last night's Pending card payment to reduce today's allowance, so that the number does not invite me to spend the same money twice.
9. As the owner, I want a Pending transaction that settles to be counted once, so that my allowance does not drop twice for one dinner.
10. As the owner, I want Pending transactions that silently vanish to stop affecting my figures, so that a cancelled hold does not shrink my allowance forever.
11. As the owner, I want my allowance coloured on track, watch or over, so that I can read my position at a glance without comparing two numbers.
12. As the owner, I want that colour to stay honest in the last week of the month, so that I do not learn to ignore a warning that appears every month regardless of my behaviour.
13. As the owner, I want to be told when I have no budgets set, so that I understand the number is missing rather than believing I can spend nothing.
14. As the owner, I want a clear prompt to set a budget when none exists, so that I know what to do to get the headline working.
15. As the owner, I want to see how much Unbudgeted Spend happened this month beside the allowance, so that I know the headline does not account for it.
16. As the owner, I want to see how much Pending spend is included, so that I understand why the allowance moved without a visible transaction.
17. As the owner, I want to see my Fixed Overrun when there is one, so that a sudden step down in my allowance has a visible cause.
18. As the owner, I want the balance still visible under the headline, so that I keep the reassurance of knowing what is actually in the account.
19. As the owner, I want the dashboard's budget and savings gauges kept, so that I can still see how the month as a whole is going.
20. As the owner, I want one figure for what I kept this month rather than two differently-labelled copies, so that I do not wonder which of them is right.
21. As the owner, I want my savings rate and its verdict computed by the backend, so that the web page and the bot cannot disagree about how I am doing.
22. As the owner viewing a past month, I want the headline to show how that month finished against plan, so that the slot says something true instead of showing today's allowance for September.
23. As the owner viewing a future month, I want the headline to show what is planned, so that an unstarted month does not read as an achievement.
24. As the owner on Telegram, I want `/summary` to open with my allowance, so that the fastest interface answers the most useful question first.
25. As the owner on Telegram, I want `/help` to describe `/summary` accurately, so that the listed commands match what they do.
26. As the owner near midnight, I want "today" to mean today in my own timezone, so that the allowance does not jump back a day at 01:00 and report last month on the 1st.
27. As the owner, I want every booked figure I already rely on to stay exactly as it was, so that adopting this change does not silently restate my history.
28. As the owner, I want an Unknown Transaction to stay out of my allowance until I categorize it, so that uncategorized noise does not move the headline.
29. As the owner, I want a transaction I marked Ignored to stay Ignored, so that a background sync does not return it to my review queue.
30. As a future maintainer, I want the financial rules in one place in the backend, so that I do not have to read a React component to learn how a metric is defined.
31. As a future maintainer, I want the deliberate asymmetries recorded, so that I do not "fix" the Pending rules into consistency and break the projection.
32. As a future maintainer, I want the metric's rejected alternatives written down, so that I do not re-propose the all-expense basis in six months.

## Implementation Decisions

### The metric

* **Safe to Spend Today** = `max(0, remaining_variable) / days_remaining`, where
  `remaining_variable = variable_budget_total − variable_budgeted_spend − fixed_overrun`
  and `days_remaining = days_in_month − days_elapsed + 1`. Day count includes
  today, so the last day of the month resolves to 1 and needs no special case.
* **Budgeted basis.** The numerator counts only spend in categories that hold an
  active Budget. Unbudgeted Spend is disclosed alongside rather than subtracted,
  so the headline stays reconcilable against the per-category Budget rows. See
  ADR-0002 for why the all-expense basis lost.
* **Fixed Overrun** = `Σ max(0, booked_spend_in_category − budget_amount)` over
  Fixed Budgets, summed per category so an underrun on one cannot fund an
  overrun on another. Booked only.
* **Status** is a single five-value enum: `no_budget`, `not_current_month`,
  `on_track`, `watch`, `over`. The amount is null for the first two. A zero
  amount therefore means exactly one thing: budgets exist, the month is current,
  and they are used up.
* **Status is judged against On-Plan Remaining**, not against the planned daily
  pace: `on_plan_remaining = variable_budget_total × (days_in_month − days_elapsed) / days_in_month`,
  and `pace_ratio = remaining_variable / on_plan_remaining`. Bands: `≥ 0.85`
  on track, `0.5 ≤ r < 0.85` watch, `< 0.5` over. When `on_plan_remaining` is
  zero (the last day of the month), the status is `on_track` if anything remains
  and `over` otherwise. Comparing against the planned daily pace instead would
  fire in the last week of every month even when spend tracks budget exactly;
  ADR-0002 has the arithmetic.

### Pending becomes load-bearing

* Pending spend counts **in the Variable slice only**. The Fixed slice — the
  step projection and the Fixed Overrun — stays Booked-only, because the
  projection trusts actual spend over its estimate as soon as any spend exists,
  and a partial hold would wreck it.
* **The derivation trap to avoid:** the Variable slice cannot be computed as
  `monthly_spending − fixed_spent` once Pending is in play, because that would
  route a Pending charge in a Fixed category into the Variable slice. The Fixed
  figures must be split: Booked fixed spend feeds the overrun and the
  projection, while **both** Booked and Pending fixed spend are removed from the
  Variable slice. A Pending charge in a Fixed category must land in neither
  slice.
* **Effective Date** resolves month membership as booking date, then value date,
  then import date, behind one shared helper used by every month-windowed query.
  Booking date stays first in the chain, so every existing Booked figure is
  unchanged to the cent — the fallback only fires on rows invisible today. This
  is required, not optional: a null booking date fails `>= month_start` in SQL,
  so Pending rows were invisible to the month window regardless of the status
  filter.
* **Reconciliation sweep:** after a *fully successful* Pending fetch for an
  account — every page — Pending rows inside the fetched window whose provider
  identifier was absent from the response are deleted. Gating on a complete
  fetch prevents a mid-pagination failure sweeping live rows. Deletion is safe
  because the 30-day trailing window makes it self-healing on the next sync.
* **The sweep must skip rows the owner marked Ignored.** ADR-0003's reasoning is
  that a phantom is not a decision the owner made — the converse holds, so an
  Ignored row is a decision and deleting it would return the transaction to the
  Unknown queue on the next import. Ignored rows count toward no metric anyway,
  so leaving them costs nothing.
* The existing `excluded_at` flag is **not** reused as a soft-delete marker for
  swept rows; it means Ignored, and overloading it would corrupt the term.
* Per-category Budget rows follow the same slice rule: Variable rows include
  Pending, Fixed rows stay Booked-only, which preserves their existing "not yet
  paid" presentation.

### Where the code lives

* A new pure domain module holds metric **policy** — the allowance, its status,
  the savings-rate bands and the budget-usage bands — as functions over
  primitives with no database session and no ORM import. The summary service
  queries and delegates. Scope is narrow by design: the queries, the
  confidence-weighted projection blend and the fixed step projection stay where
  they are. See ADR-0001.
* **Nothing financial remains in the Web UI.** The line, stated so the
  Definition of Done is checkable: if a result is compared against a constant,
  or displayed as a figure with a unit, it belongs in the domain; if it only
  ever becomes a pixel width or an arc length, it is presentation. The gauge's
  270° sweep and the amount-to-fraction conversions stay in the UI; the 85%
  threshold, the savings rate and the pacing verdict move out.
* **`APP_TIMEZONE`** (IANA name, default `UTC`) is added to settings and used
  wherever a civil date is derived — the summary service, both call sites in the
  budget service, and the Telegram notifier. This fixes the same latent bug in
  all four. It is too small to warrant an ADR; one line in the architecture doc
  and an `.env.example` entry.

### API contract

Seven new fields on the summary response. Nothing is removed, so no client breaks.

| Field | Type |
|---|---|
| `current_month` | `YYYY-MM` |
| `safe_to_spend_today_amount` | 2dp decimal string, nullable |
| `safe_to_spend_status` | `no_budget \| not_current_month \| on_track \| watch \| over` |
| `pending_spend_amount` | 2dp decimal string |
| `fixed_overrun_amount` | 2dp decimal string |
| `savings_rate_percent` | float |
| `savings_status` | `on_track \| watch \| over` |

`current_month` is the month the owner is in, resolved through `APP_TIMEZONE`. It was
added during ticket 11 rather than designed here: a client comparing the reported
`month` against a month of its own disagrees with the backend for part of every
month-end, and so labels a month that has not started as one that closed.

`savings_status` reuses the existing budget-usage status vocabulary so the
codebase has one status language. `unbudgeted_spending_amount` and
`net_cash_flow_amount` already exist and become load-bearing: the first backs
the headline's disclosure, the second becomes the sole source for what the UI
currently computes twice as "saved" and "net".

### Presentation

* The allowance becomes the dashboard's 52px headline. The current balance
  demotes to the small line directly beneath it. Both gauges stay.
* The hero carries up to three disclosures when non-zero: Unbudgeted Spend,
  Pending spend, Fixed Overrun.
* For a month that is not the current one, the headline slot shows that month's
  outcome against plan, which is the existing money-left figure — no new
  calculation. The presentation chooses the wording by comparing the response's
  month to the `current_month` the same response reports; that is a label, not a
  financial rule.
* The duplicate "saved / net" tile collapses to one, reading the backend field.
* Telegram: the allowance becomes the first line of the `/summary` output, and
  the `/help` text is corrected to match. No new command — the MVP doc fixes the
  command set.

### Documentation, in the same change

Per the Documentation Rules in `AGENTS.md`: the metric definitions doc (Pending,
Fixed Overrun, status, Net Cash Flow naming), the domain doc (Effective Date,
Pending in the derived concepts, the slice asymmetry), the architecture doc (the
domain module and `APP_TIMEZONE`), `.env.example`, and the `/summary` line in
the README.

The roadmap's Phase 8 entry is amended rather than left to understate what
shipped, and its Definition of Done gains a clause so the new behaviour is
checkable: *a Pending charge reduces the allowance the day it appears, and a
Pending row that later books is not counted twice.* The schema doc is
**untouched** — the Effective Date is resolved in query, not stored, and the
sweep deletes rows, so this phase carries no migration.

## Testing Decisions

A good test here states a behaviour the owner would recognise and survives the
code being rearranged underneath it. It observes through a public boundary,
never a private method or a side-channel database read. Expected values come
from a worked example or a known-good literal, never recomputed the way the
implementation computes them — a test that divides the same two numbers the same
way cannot ever disagree with the code.

Four seams, confirmed before writing this spec. No test is written anywhere else.

**1 — The pure domain functions.** New seam, created by ADR-0001. Carries the
policy table: the pace bands at day 1, 15, 25, 29 and the last day; the
allowance clamped at zero; the Fixed Overrun deduction; `no_budget`;
`not_current_month`; the `on_plan_remaining == 0` guard. Primitives in, values
out, no fixture, so the combinatorial cases are cheap. Prior art: none directly
— this is the repo's first pure-domain test module, and it should read as a
table of worked examples.

**2 — The summary service, through its existing `month` and `today`
parameters.** Existing seam with an in-memory SQLite fixture; `today` is already
injectable, so no new affordance is needed. Carries the wiring and the SQL
behaviour: the new fields populated correctly; Pending counted in the Variable
slice; Pending in a Fixed category landing in neither slice; the Fixed Overrun
and step projection ignoring Pending; the Effective Date fallback pulling in a
row with a null booking date; and a regression test that every pre-existing
Booked figure is unchanged. This is deliberately **not** a second copy of seam
1 — seam 1 asks whether the rule is right, seam 2 asks whether the rule is wired
to the right query. Prior art: `test_summary_service.py`.

**3 — The Enable Banking sync entry point, with a fake client.** Existing seam;
the test module already defines a fake client and subclasses it to vary
payloads. Carries the sweep: a Pending row that reappears survives; one that
vanishes is deleted; one that books under a *different* provider identifier is
not counted twice; a failed page sweeps nothing; and an Ignored Pending row is
never swept. Both payload shapes are covered — with and without a provider
transaction identifier — because which one the real bank produces is unknown
until it runs, and the sweep is load-bearing only in the second case. Prior art:
`test_enable_banking_service.py`.

**4 — The Telegram summary formatter.** Existing seam, pure dict in / string
out. Carries the allowance leading the output, and the `not_current_month` and
`no_budget` renderings. Prior art: `test_telegram_formatters.py`.

Not seams: the summary HTTP route, whose existing response-shape assertions are
extended but which would otherwise re-test seam 2 through HTTP; and the
dashboard, because `web/` has no test runner and installing one is not this
phase's work. The nullable amount is caught by the existing type check; the
layout is verified by looking at it.

## Out of Scope

* **Runway and Cushion.** Phase 11, and it needs the account-purpose migration.
* **Baselines, trailing averages, recurring-payment detection, anomalies.**
  Phase 9. The allowance is judged against the owner's own budget, not against
  their history.
* **Proactive alerts and the weekly digest.** Phase 10. This phase makes the
  number worth pushing; it does not push it.
* **AI categorization.** Phase 12. The allowance's accuracy depends on rule
  coverage, since an Unknown Transaction holds no category and therefore moves
  nothing — but improving that coverage is Phase 12's job.
* **A stored `effective_date` column.** The better end state, deliberately
  deferred: it needs a migration and a backfill.
* **Redesigning the per-category Budget status.** The 85% band has the same
  time-decay as the rule being replaced in the hero — an on-plan category flips
  to watch around day 26. Knowingly left alone: "86% of Food used" is a
  different and legitimate claim from "off pace", and the rows are a list rather
  than the headline. Recorded here so it reads as a choice, not an oversight.
* **A web test runner.** Not installed under cover of this phase.
* **New Telegram commands.** `/summary` leads with the allowance; no `/today`.
* **Multi-currency handling of the allowance.** Inherits the existing
  single-currency assumption.

## Further Notes

The phase grew. The roadmap scoped it as *"a derivation, not new accounting"*,
and the Pending work is new accounting — roughly two tickets beyond the original
shape, for the reason recorded in ADR-0003: a daily metric blind to a
three-day booking lag errs toward overspending, which is the exact failure the
product exists to prevent. The roadmap entry and its Definition of Done are
amended to match rather than left to describe a narrower change than shipped.

The sweep carries the only residual unknown in the design, and it is not
resolvable from the code: whether the bank supplies a stable provider identifier
across the Pending-to-Booked transition. If it does, the dedup hash never fires
and duplicates cannot occur, making the sweep belt-and-braces. If it does not,
the sweep is the only thing standing between the owner and a double-counted
dinner. Hence both payload shapes at seam 3.

One adjacent pre-existing risk, noted and not fixed here: re-importing a
transaction re-applies the rule engine, which can reassign a category to a row
the owner marked Ignored. The sweep's skip rule keeps this phase from making it
worse, but the underlying interaction predates this work.

A thing worth watching after this ships: the allowance only counts *categorized*
Pending spend in budgeted categories. A Pending charge that no rule matches sits
in the Unknown queue and moves the headline by nothing, exactly as an
uncategorized Booked charge does today. That is correct and consistent, but it
means the headline's accuracy is a function of rule coverage — which is the
argument for promoting Phase 12 if the Unknown queue turns out to be the daily
friction.
