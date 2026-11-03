# A Fixed Budget bounded to one month declares that month's spend an event

A **Fixed Budget whose window covers exactly one month** — `active_from` on the
1st, `active_to` on that month's last day — means the owner is saying that
month's spend in its category was an event and not a habit. Its spend is counted
in the actuals, steps the pace as any Fixed Budget does, and is **excluded from
every baseline**. Nothing else changes.

The declaration is the bounded window and there is no second thing to set.

## Why the window and not a flag

A flag was designed first and is recorded under *"Declined: the Exceptional
Charge"* in the roadmap: a third disposition on a charge, or on a category whose
charges are all events, beside `excluded_at`. The owner declined it twice, and the
reason is worth keeping because it is the whole argument for this shape.

**A flag asks for a new gesture.** The window asks for one the owner already
makes. On 2026-11-02, unprompted and for an unrelated reason, they bounded
`Divorce` and `Relocation` to `2026-10-31` using a primitive they already
understood. The rule reads that.

The proposal's own objection to a Budget as the carrier was that *a budget's
default is that it continues, and an event's default must be that it does not*.
That objection is sound and is exactly what the bounded window answers: an open
`active_to` is the default, and bounding it is the departure from the default. It
was raised against a *one-month window* as a substitute for the flag, which it is
not — but as a **signal** that the owner has declared an event, it is the cheapest
one available, because it requires no column, no migration and no new control.

## What the rule is not

Three neighbours answer the other way, and all three have tests whose mutations
were confirmed to fail:

* **An open window is not an event.** Rent at 500 a month keeps its baseline.
* **A window spanning two months is not an event.** A sublet, a course, a contract
  that ran and stopped is a commitment, not an event. ADR-0005 puts both edges of
  a window on month boundaries, so "exactly one month" is two equalities and no
  arithmetic over days, and two months is the nearest input that must be refused.
* **The month on screen is not excluded from its own figures.** This is the same
  figure-specific inclusion rule ADR-0003 established for Pending Spend, not a
  disposition. The exclusion is passed per month — empty for the month on screen,
  populated for the months behind it — rather than applied inside the queries.
  Applied to the month on screen too it would print a `Divorce` row reading 0.00
  beside a headline counting the 8,400, and would amount to a quieter
  `excluded_at`, which is a primitive the product already has.

## What it buys, and what it does not

The owner's October 2026 holds a €8,053.83 divorce. Without this rule it enters
the net cash flow baseline whole; the per-category baseline is protected only by
`BASELINE_PRESENCE_FLOOR`, and only as long as no second month carries divorce
spend, which an ongoing divorce makes a matter of time.

What it does **not** buy is a usable baseline on 2026-12-01, and that was measured
rather than assumed. With July classified, the window reaching {July, October,
November} and this rule applied, the baseline reads **+€395.41** — because the
rule removes the divorce and leaves July's €5,500.00 severance, which is an
exceptional *income* and has no budget to bound. That is why
`BASELINE_MINIMUM_MONTHS` was raised to 3 in the same change, and why protecting
the aggregate baselines is a separate open item. This rule makes January clean; it
does not make December honest.

## Consequences

**The signal depends on the owner bounding the window.** A one-off they never
budgeted is invisible to the rule and enters the baseline. That is acceptable and
was measured: July's €565.40 of `Car Maintenance` moves a three-month spend mean
by 7.5%, inside the 15% in-line band. A one-off small enough not to budget is
small enough not to move a mean; one large enough to move a mean is one the owner
would have budgeted. What the rule cannot reach at all is a one-off inside an
*ordinary* category — a boiler under `Home` — which no budget window can express
without inventing a budget for it. The declined flag was the only design that
covered that case, and it is unreached in the live data.

**`POST /budgets` accepts no `active_to`.** So an Event Budget can only be created
by bounding the window afterwards, from the following month, through
`deactivate_budget`. That asymmetry predates this rule and is recorded as its own
gap; closing it is what turns the declaration into one action instead of two.

**Both answers about a month's Fixed Budgets come off one fetch.**
`_budget_categories_by_month` returns which categories a month's budgets make
fixed and which make it an event, from the same rows, so no later change can move
one and leave the other behind. The window rule itself lives in
`burnrate.db.budget_windows` beside the others, for the reason that module exists:
a second spelling of a window rule is the defect it was created to prevent. The
transaction filter, by contrast, is private to `BaselineService` — the rule is
"excluded from every baseline", so the only callers that may have it are the two
queries that build one.
