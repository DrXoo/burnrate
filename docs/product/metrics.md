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

It is the remaining variable budget divided by the days remaining in the month.
Fixed budgets (rent, utilities) are excluded, because they are scheduled
commitments rather than discretionary daily spend.

This is BurnRate's headline metric: it is the one figure that changes a decision
in the moment.

It counts pending spend, so last night's card payment reduces today's allowance
rather than the allowance of whichever day the bank gets round to settling it.

It is never negative. A month that is already overspent shows zero, not a
negative allowance.

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
