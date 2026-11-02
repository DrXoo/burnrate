# BurnRate Domain Model

## Goal

This document defines the main business concepts BurnRate should use internally so the product, API, and persistence layers speak the same language.

The domain model is intended to be stored in PostgreSQL for the first version.

---

## Core Entities

### Account

Represents a bank account included in BurnRate.

Suggested attributes:

* Internal account id
* Provider account id
* Provider name
* Display name
* Currency
* Included in calculations flag
* Included in runway flag
* Latest known balance
* Last synced at

`Provider account id` should be unique per provider.

---

### Transaction

Represents one financial movement imported from a provider or created internally for bookkeeping of import state.

Suggested attributes:

* Internal transaction id
* Provider transaction id
* Account id
* Booking date
* Value date
* Amount
* Currency
* Description
* Merchant or counterparty
* Direction
* Category id
* Status
* Rule id that assigned the category

`Amount` should be stored as a precise numeric value, not a float.

`Booking date` and `value date` should remain distinct when the provider supplies both.

`Effective date` is the date that places a transaction in a month: its booking
date, or its value date, or the day it was imported, in that order. It is
resolved in query rather than stored, so every month-windowed figure asks one
shared expression (`burnrate/db/effective_date.py`) instead of reading a date
column directly.

Booking date stays first in that chain so no figure already reported to the
owner is restated; the fallbacks only reach rows a window on booking date could
not see at all. Pending transactions are the reason the chain exists: the
provider has no booking date for them yet, and a null booking date satisfies no
month comparison in SQL, so such a row belonged to no month and reached no
review queue. The import date is a last resort for a row the provider dated not
at all, and it resolves on the *database session's* calendar day rather than the
owner's -- SQL has no portable timezone conversion, so a charge imported within
hours of a month boundary can land in the adjacent month until it books. That the
day is UTC is a deployment precondition, not a property of the expression:
PostgreSQL defaults the session to UTC, and setting `TZ` or `PGTZ` on the database
container would silently move undated charges between months with no test able to
catch it. See the docstring in `db/effective_date.py`.

`Provider transaction id` should be unique per provider when reliably available.

Suggested statuses:

* Pending
* Booked
* Unknown
* Ignored

Pending and booked transactions should be stored in the same transaction model, differentiated by status.

`Ignored` in that list is the *provider's* status, written from the Enable Banking
codes `CNCL` and `RJCT` for a payment the bank cancelled or rejected. The owner's
decision to exclude a transaction from every metric is a separate thing in a
separate column, `excluded_at`, and the two share a word by accident. `GLOSSARY.md`
resolves the clash in language -- the status is **Cancelled**, the disposition is
**Ignored** -- rather than in the schema, which would need a migration and a
backfill for no behavioural gain. Nothing should test one to get the other.

The owner's exclusion is a decision, so it outlives the sync that re-imports the
transaction. Two consequences, both stated in `burnrate/db/dispositions.py` rather
than at each call site:

* The categorization rules own a row only while it holds no category *and* carries
  no exclusion. An Ignored row holds no category either, so a bare "has no
  category" test reads the owner's decision as an absence of one and hands the
  category back -- returning the money to every figure while the row still reads as
  excluded.
* Every spend and income figure states the exclusion. It used to come for free,
  because excluding a row cleared its category too and rows with no category fell
  out of those queries anyway -- by a join on the category table in two of them and
  by an `IN` on category ids in the third. That made the definition a consequence of
  how three queries happened to be shaped.

Only the owner lifts it: by categorizing the transaction, by restoring it to the
review queue, or by making a categorization rule from it.

---

### Category

Represents a spending or income classification used by budgets and reporting.

Suggested attributes:

* Internal category id
* Name
* Type
* Active flag

Suggested types:

* Expense
* Income
* Transfer

---

### Categorization Rule

Represents a reusable rule that maps transactions into categories automatically.

Suggested attributes:

* Internal rule id
* Match field
* Match operator
* Match value
* Category id
* Priority
* Active flag
* Created from manual classification flag

For the first version, rules should match only against transaction naming fields such as description, merchant, or counterparty text.

Suggested match operators:

* Contains
* Equals
* Starts with
* Ends with
* Regex

Rules should not depend on transaction amount or account-level conditions in the first version.

Rules should be deterministic and evaluated in a stable order.

---

### Budget

Represents a monthly spending target for one category.

Suggested attributes:

* Internal budget id
* Category id
* Amount
* Period type
* Active from
* Active to

For the first version, monthly budgets are sufficient.

Budgets should be defined per category.

A category holds **at most one budget covering any given month**. It can hold many rows over time — one per amount change, each closing where the next begins — but their windows never overlap. Creating a window and reopening a cancelled one both refuse an overlap, through one predicate, because two rows covering a month are summed into a single inflated figure; see `docs/adr/0005-budget-windows-are-month-granular.md`.

Even so, every budget-basis figure is derived from a **fold per category** — a month's commitment is the sum of that category's active rows, and the category counts as fixed if any of them is — rather than from the rows themselves. That fold is a defensive invariant of `SummaryService`, not a consequence of the model: it protects figures from a row pair the service refuses to write but that a database predating the guard could still hold, since `0008_budget_active_to_month_end` normalises window edges without de-duplicating overlaps.

It is kept because the spend each figure is compared against is grouped per category, so pairing each row with that spend would count the commitment once per row — inventing a fixed overrun for an owner who is exactly on budget, adding the step projection twice, and printing the same category twice with each row claiming all of its spend. A single pathological row pair would therefore corrupt several figures at once, which is more than the fold costs.

There is no need for a separate global monthly budget entity in the first version, because the overall budget can be derived as the sum of all active category budgets.

---

### Sync Session

Represents one synchronization attempt with a bank provider.

Suggested attributes:

* Internal sync session id
* Provider name
* Started at
* Finished at
* Status
* Imported transaction count
* Error summary

This entity helps with traceability and troubleshooting.

Timestamps should be stored in UTC.

---

## Derived Concepts

### Current Balance

The latest known sum of balances across included accounts.

---

### Monthly Spending

The sum of expense transactions within the current calendar month.

Income transactions should not be mixed into this metric.

Both booked and pending transactions count, because a pending charge is money
already committed. The pending share is reported alongside as its own figure, so
a movement in the metrics has a cause the owner can point at even before the
charge appears as a settled transaction.

---

### Pending Spend

The share of the month's spending the provider has authorized but not settled.

It counts in the variable slice only: the daily pace, the variable projection,
and the allowance that draws on them. A fixed category is judged by its budgeted
estimate until a charge books, so a partial hold on a scheduled bill counts
towards no figure at all -- not the step projection, not the fixed overrun, not
monthly spending, and not the month's budget -- and the category's row keeps
reading as not yet paid.

The derivation order is what makes that hold stay out, and the obvious order gets
it wrong: a hold on a fixed bill has to leave the month total *before* the
variable slice is taken out of it, because the variable slice removes only booked
fixed spend. Subtracting booked fixed spend from a total that still counted the
hold would route it straight into the variable slice -- the one place it must
never land. Each budget-basis figure then counts what the per-category rows
count, so the total and the rows beside it cannot disagree.

The asymmetry is deliberate and should not be reconciled into consistency. See
`docs/adr/0003-pending-spend-is-load-bearing.md`.

---

### Money Left

The remaining monthly budget after subtracting categorized spending from configured budgets.

The total monthly budget is derived from the sum of all active category budgets.

---

### Burn Rate

The current pace of spending, typically represented as daily average spending and projected month-end spending.

---

### Inbound Transfer

Money that arrived in the month from an account BurnRate cannot see: the booked credit legs of transfer categories. It is neither income nor spend, so it reaches neither side of net cash flow -- it is **disclosed beside** that figure as the funding the deficit came from, and never added to it. The loss is counted once, in the net; this says which pocket paid.

The category carrying such credits was once typed `income`, which made a month that drained the owner's savings report as very nearly break-even: October 2026 read a net of -354.88 where the real figure was -8,195.88, the difference being 7,841.00 moved in from savings. The product's rule was already right -- both income queries select on `Category.type == "income"` -- so the correction was a retype, not a code change.

The sign is filtered in SQL rather than netted afterwards, because the same categories carry money going the other way and summing them whole reports an outgoing month as *negative* money arriving. Booked only, matching the income figure it is read against.

It **assumes every transfer in came from outside**, which holds while one account is linked and stops at the second: a transfer between two linked accounts lands as a credit on one and a debit on the other, and the credit leg would be reported as money from outside when nothing entered the owner's world at all. The trigger for pairing the two legs is the second linked account. See `docs/adr/0010-a-savings-draw-is-a-transfer.md`.

---

### Runway

The estimated time remaining before designated savings are exhausted, based on the current monthly deficit.

### Baseline

What a figure normally is for the owner: its mean over the Qualifying Months a window reaches, recomputed from transactions on each request and never stored.

A **Qualifying Month** is a closed month whose data can be trusted. Two independent tests decide it, because each is blind to the other:

* **Classification coverage** — the share of the month's *outgoing money* that is still unclassified must be under a floor. Measured by amount and never by rows: a month can read almost fully classified by row count while most of its money sits in the few large rows the owner has not got to, and admitting such a month biases every baseline downwards with nothing to signal it.
* **Sync coverage** — the month must be spanned by the trailing fetch windows of *successful* syncs. A run on day S asked the bank about `[S - fetch window, S]`, so a month is covered only when those windows union to span every one of its days: two runs 25 days apart cover a month between them although neither does alone, and a single run a day short of the month's end leaves its last day never asked about. A month with a hole looks perfectly classified, because every row it does have is filed, while transactions are missing outright — and the resulting baseline is understated, which is the direction that makes ordinary spend read as an anomaly. Only `success` counts: an expired consent writes a `skipped` session per attempt and fetches nothing, so counting session rows rather than successes would read the months the owner was disconnected as the best-covered ones there are.

Two rules keep a mean from being computed where it would mislead. A **presence floor** denies a baseline to a category the owner spends in too rarely, which is what makes the divisor safe: for a category above the floor the mean divides by every Qualifying Month in the window, treating an absent month as a real zero, because for a recurring expense that absence is information. The floor also retires a category whose spend has stopped, without anyone declaring anything — it falls below the floor as the window moves past it.

For the month in progress, both sides are summed only to the **same day of the month**, clamped to each past month's own length. A part-month measured against whole ones is favourable for most of the month, which is the defect Phase 8 fixed in the budget pacing; summing past months to the same cutoff makes no assumption about pacing, so a Fixed Budget charged as a step lands identically on both sides. A closed month is compared whole against whole, and a month that has not started is not compared at all.

Comparing and firing are different acts. The deviation is reported in both directions, since a quiet month is information. An anomaly fires **only upward**, and **only on spend**: the product exists to stop the owner overspending, and income is not spend. A bonus month bands *above* and stops there, because "unusually high" is the wording both interfaces give an anomaly and there is nothing wrong with being paid more than usual. Every other band applies to income unchanged, so a month well below the usual income still reads *below*.

The spend comparison is computed over **Comparable Spend** only — the categories that have a baseline — and the rest is disclosed beside it as **Uncomparable Spend**, which is the shape Unbudgeted Spend already has. This is load-bearing rather than tidy: a month dominated by a one-off in a category with no history would otherwise report catastrophic overspending while every ordinary category sat under its own usual figure. Uncomparable Spend is defined as the residual, monthly spending less the comparable half, so the two reconcile against the headline rather than against a third total; the three things that land in it are a category with no baseline, an Archived Category, and spend dated after today's cutoff.

Because it is a residual, both halves have to count the same money, which means the baselines read spend on the **same basis the headline does**: a hold on a Fixed Budget's category counts towards nothing until it books, in every month, the ones behind the window included. The rule is month-by-month, since a budget's window is month-granular and a category the owner made fixed in September was not fixed in August. Counting such a hold on the comparison side alone made the residual *negative* — 0.00 spent, 500.00 comparable and minus 500.00 that cannot be compared — and measuring a baseline on a wider basis than the figure it is compared against is the same defect in the other direction.

Income and net cash flow take no such split. It exists because per-category baselines feed the spend aggregate and a category without one would poison it; both of these are whole-month figures with no per-category decomposition in play, and "this month was much worse than usual" about money kept is simply true, one-off included. Their means also take **no presence floor**, unlike a category's: a month in which nothing came in is a fact about the owner's year, and skipping it would report a salary as normal to someone paid once in three months. Net cash flow carries a baseline **amount and no verdict**, because a ratio on a figure that can cross zero means nothing and an owner whose usual month is a deficit would carry a negative baseline that the bands read as no baseline at all.

---

## Important Invariants

BurnRate should preserve the following invariants:

* A transaction must belong to exactly one account
* A transaction may have zero or one assigned category
* Unknown transactions are uncategorized transactions that require review
* Every transaction belongs to exactly one month, resolved by its effective date
* Transfer categories should not inflate spending metrics
* Budget-basis figures are derived per category, never per budget row: a category's monthly commitment is the sum of its active budget rows
* Pending transactions count as spend in the variable slice only, while the fixed slice is judged by its budgeted estimate until a charge books
* Income should remain a minimal classification concern and should not drive budget reporting in the first version
* Runway should only use balances from accounts explicitly included for runway calculations
* Imported provider identifiers should support idempotent re-sync behavior
* Monetary values should be stored with exact precision

---

## Current Modeling Decisions

The following decisions are currently assumed for implementation:

* Pending and booked transactions should share one transaction model with a status field
* Rules should support text-based matching only, using operators such as contains, equals, starts with, ends with, and regex
* Rules should not depend on transaction amount or account conditions in the first version
* Budgets should exist only per category, with the general monthly budget derived from their sum
* Income should remain secondary to expense visibility and can be grouped under a minimal income classification model
* PostgreSQL should be the default persistence target for the first version
