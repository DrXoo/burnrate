# BurnRate Metric Definitions

To keep the product consistent, BurnRate should use clear definitions for the core metrics it exposes.

## Money Left

"Money left" means the amount of budget still available for the current month after subtracting categorized spending from the user-defined monthly budgets.

This is a budgeting metric, not simply the raw bank balance.

---

## Current Balance

"Current balance" means the latest known balance across the accounts the user has chosen to include in BurnRate.

This value should reflect imported account balances when available.

If balances are not available from the provider, BurnRate may estimate them from historical data, but the UI should make that clear.

---

## Monthly Spending

"Monthly spending" means the sum of all expense transactions during the current calendar month across included accounts.

Refunds, transfers, and income should not be counted as spending.

Both booked and pending expense transactions count. A pending card payment is
money already committed, and a figure that waits the one to three days the bank
takes to settle it is optimistic in exactly the direction that causes
overspending. The unsettled share is disclosed separately as pending spend, so
monthly spending less pending spend is what the bank has actually settled.

---

## Pending Spend

"Pending spend" means the share of the month's spending the bank has authorized
but not yet settled. It discloses the pending spend the figures actually counted,
so monthly spending less pending spend is what the bank has settled.

It counts in the variable slice only. The fixed slice -- the step projection for
a scheduled lump payment, and the fixed overrun -- is judged by the budgeted
estimate until a charge actually books, because the projection trusts actual
spend over its estimate as soon as any spend exists: a 1EUR pre-authorization on
a utility bill would otherwise project that bill at 1EUR.

A pending charge in a fixed budget's category therefore counts towards nothing
until it books -- not the fixed figures, which are booked-only, not the variable
slice a daily allowance draws on, and not monthly spending or the month's budget
either. The budgeted estimate already stands for the whole commitment, so
counting a partial authorization on top of it would charge the same bill twice,
and leaving it in the month total while every budget-basis figure excluded it
would make it resurface as unbudgeted spend, which it plainly is not.

One figure therefore counts the same money as the rows printed beside it:
budgeted spend is the sum of the per-category rows, each of which counts pending
in a variable category and booked only in a fixed one.

The asymmetry is deliberate and should not be tidied into consistency. See
`docs/adr/0003-pending-spend-is-load-bearing.md`.

---

## Burn Rate

"Burn rate" means the average rate at which money is being spent during the current month.

This should usually be expressed as:

* Daily average spending
* Projected month-end spending

It measures the variable slice only, pending spend included, so it tracks
controllable spend as the owner commits it rather than as the bank settles it.

---

## Net Cash Flow and the Savings Rate

"Net cash flow" means the month's income minus its spending, with transfers
excluded on both sides. It is the same figure as money saved in the month, and
the product names it once: there is no second "saved" figure computed anywhere
else.

Its spending side counts pending spend; its income side counts booked income
only. A credit the bank has not settled is not yet money kept, so both halves of
that asymmetry read in the cautious direction.

The "savings rate" is net cash flow as a percentage of the month's income. A
month with no income reports zero rather than dividing by nothing.

Its verdict reuses the budget-usage vocabulary, so the product has one status
language:

* `over` -- spending outran income, so nothing was banked
* `watch` -- under a tenth of income kept, a thin margin
* `on_track` -- a tenth of income or more kept, **or** no income yet

The last clause matters for a salaried user: before the month's salary books
there is no share of income to be thin, so the figure must not read as a warning.
Overspending with no income booked is still `over`.

The band is read off the rate rounded to one decimal, and interfaces display that
same rounded figure, so the number and the colour it is shown in cannot
disagree.

---

## Safe to Spend Today

"Safe to spend today" means the amount the user can spend today without putting
the month's variable budgets out of reach.

This is BurnRate's headline metric: it is the one figure that changes a decision
in the moment.

It is the remaining variable budget, less any fixed overrun, divided by the days
left in the month counting today:

* `remaining variable = variable budget - variable budgeted spend - fixed overrun`
* `days remaining = days in month - days elapsed + 1`

Fixed budgets (rent, utilities) are excluded from the budget it draws on, because
they are scheduled commitments rather than discretionary daily spend. What they
*overshot* by is not excluded -- see the fixed overrun below.

The day count includes today, because the owner is asking what they may spend
now. The last day of the month therefore has one day to cover and the allowance
is simply everything left, which falls out of the arithmetic rather than needing
a case of its own. Bank data also lags, so today's spend has usually not booked
when the figure is read.

It counts pending spend, so last night's card payment reduces today's allowance
rather than the allowance of whichever day the bank gets round to settling it.

It is measured on a **budgeted basis**: the spend it subtracts is spend in
categories that have an active budget. Spend in a category with no budget is
disclosed beside the headline as unbudgeted spend rather than subtracted from it,
so the figure stays reconcilable against the per-category budget rows the owner
can point at. See `docs/adr/0002-safe-to-spend-today-definition.md`.

It is never negative. A month that is already overspent shows zero, not a
negative allowance.

### Its status

The allowance carries a status so it can be read as a colour without reading the
number. One field, five values:

* `no_budget` -- nothing is budgeted for day-to-day spend, so there is no
  allowance. The amount is null, and the interface should prompt the owner to set
  a budget. A month budgeted entirely to fixed commitments reads this way too.
* `not_current_month` -- "today" is not in the month being reported, so the
  metric has no meaning. The amount is null.
* `on_track`, `watch`, `over` -- the bands below.

The amount is null for the first two cases and never for the others. A zero
amount therefore means exactly one thing: budgets exist, the month is current,
and they are used up.

The band is judged against **on-plan remaining**, not against the planned daily
pace:

* `on plan remaining = variable budget x (days in month - days elapsed) / days in month`
* `pace ratio = remaining variable / on plan remaining`
* `>= 0.85` is `on_track`, `0.5` up to `0.85` is `watch`, below `0.5` is `over`

Spend that tracks the budget exactly puts that ratio at 1.0 on every day of the
month, so the bands mean the same thing on the 29th as on the 1st. Judged against
the planned daily pace instead, an owner doing nothing wrong would be warned in
the last week of every month -- a warning they would learn to ignore. The
arithmetic is in `docs/adr/0002-safe-to-spend-today-definition.md`.

On the last day of the month on-plan remaining is zero, so there is no ratio to
band and the rule is read directly: anything still left is `on_track`, and
nothing left is `over`.

---

## Fixed Overrun

"Fixed overrun" means the amount by which the month's charged fixed budgets
exceeded their budgeted estimates.

It is summed per category -- `max(0, booked spend - budget)` for each fixed
budget, added together -- so an underrun on one fixed category cannot fund an
overrun on another. A rent budget of 800 charged at 850 is 50 already gone,
whatever the utility bill came in under.

It is booked only, like the rest of the fixed slice. A pending hold on a bill is
not the bill being paid, so it reaches the overrun only once it settles; see
pending spend above.

That overrun comes out of Safe to Spend Today, because the money is gone and the
system already knows it -- the fixed step projection trusts the actual charge
over its estimate for the same reason. Without the deduction, a 50 EUR rent
increase would quietly stay in the owner's daily spending money for the rest of
the month.

It is disclosed as its own figure, so a sudden step down in the allowance has a
visible cause.

---

## Runway

Runway has two forms, because a single definition does not serve both a saver and
someone drawing down savings.

Both forms use only savings accounts or balances the user has explicitly marked
as available for runway calculations.

### Cushion (primary)

"Cushion" means how many months of the user's normal expenses their designated
savings would cover.

It is savings divided by trailing average monthly expenses.

This form is always defined, whether or not the user is in deficit.

Example:

* Savings available for runway: 10,000EUR
* Trailing average monthly expenses: 2,000EUR
* Cushion: 5 months

### Deficit Runway (conditional)

"Deficit runway" means how long the user can sustain their current deficit before
their designated savings are exhausted.

It is savings divided by average monthly deficit.

This form is only shown when trailing net cash flow is actually negative. For a
user who saves, there is no deficit and the figure is meaningless, so the UI must
omit it rather than display an infinite or placeholder value.

Example:

* Savings available for runway: 10,000EUR
* Average monthly deficit: 500EUR
* Deficit runway: 20 months
