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

## Phase 8: "How much can I spend today?"

### Objective

Replace the monthly abstraction with one number the owner can act on before
buying something.

### Scope

* Domain calculation for **Safe to Spend Today**: remaining variable budget
  divided by days remaining in the month. The inputs already exist in
  `SummaryService` — `variable_budget_total`, `variable_budgeted_spend` and the
  fixed/variable split — so this is a derivation, not new accounting. Fixed
  commitments are already carved out of the variable slice and must not be
  subtracted twice.
* Expose it through the summary API as a first-class field.
* Make it the headline of the dashboard, above balance and budget.
* Move the savings-rate threshold out of `DashboardPage.tsx` into the domain,
  alongside the existing budget-status thresholds in `SummaryService`.
* Handle the degenerate cases explicitly: no budgets defined, month already
  overspent (allowance is zero, not negative), and last day of the month.

### Definition of Done

The owner can answer *"can I spend 40 EUR on dinner tonight?"* by glancing at one
number, without reading a chart or doing arithmetic. No financial rule or
threshold remains in the Web UI.

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

Act II, ahead:

* **Data Becomes a Decision** (Phase 8) — one number that changes what the owner
  does today.
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

1. Implement Safe to Spend Today in the domain, test-first, deriving from the
   existing fixed/variable split in `SummaryService`.
2. Move the savings-rate threshold out of `DashboardPage.tsx` into the domain.
3. Re-lead the dashboard with the daily allowance.
4. Add trailing per-category baselines, as the foundation for Phase 9.
5. Decide whether to promote Phase 12's categorization copilot, based on whether
   the unknown queue is actually the daily friction.

Steps 1 to 3 are a single coherent change and the fastest route to the product
feeling different to use.
