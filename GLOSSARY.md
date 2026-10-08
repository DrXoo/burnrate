# BurnRate

BurnRate answers one question for a salaried person who does not want to
overspend: how much is left, and how fast is it going. This glossary fixes the
language the product, API, domain and persistence layers all use for that.

## Language

### Money and movement

**Transaction**:
One financial movement on an account, imported from a bank provider.
_Avoid_: Entry, movement, payment, purchase

**Booked**:
The status of a transaction the bank has settled. Only booked transactions
feed the spending metrics.
_Avoid_: Cleared, settled, confirmed

**Pending**:
The status of a transaction the bank has committed to but not yet settled —
either a card authorization awaiting settlement, or a payment it has scheduled
for a date still to come. Real committed money: it counts as spend in the
variable slice, while the fixed slice is judged by its estimate until
settlement. A scheduled payment is Pending from the moment the bank reports it
and is filed by its Effective Date, so it can put spend in a month that has not
started.
_Avoid_: Held, unsettled, provisional, in-flight

**Effective Date**:
The date that places a transaction in a month: its booking date, or its value
date, or the date it was imported, in that order. Pending transactions often
have no booking date, so the month window cannot rely on that field alone.
_Avoid_: Transaction date, date, posting date

**Unknown Transaction**:
A transaction with no category assigned, awaiting review.
_Avoid_: Uncategorized, unclassified, orphan

**Ignored**:
The disposition of a transaction the owner has excluded from every metric. A
decision rather than a property of the data, so it survives a re-import and only
the owner lifts it.
_Avoid_: Hidden, deleted, archived

**Cancelled**:
The status of a transaction the bank cancelled or rejected. Not Ignored above and
not the owner's decision at all, although the import stores it in `status` under
that same word.
_Avoid_: Ignored, rejected, void, reversed

### Budgets

**Budget**:
A monthly spending target for one category. The monthly total is derived from
the sum of active category budgets, never stored as its own figure.
_Avoid_: Limit, cap, allocation, envelope

**Fixed Budget**:
A budget for a scheduled lump commitment such as rent or utilities. It is
charged as a step, so it is never paced day by day or rate-extrapolated.
_Avoid_: Recurring budget, bill, committed budget

**Variable Budget**:
A budget for spend that accrues day by day, and therefore the only slice a
daily allowance can draw on. The variable total is the monthly budget minus the
fixed total.
_Avoid_: Discretionary budget, flexible budget

**Fixed Overrun**:
The amount by which a charged fixed budget exceeded its budgeted estimate,
summed per category so an underrun on one cannot fund an overrun on another.
Money already gone, so it reduces the daily allowance.
_Avoid_: Fixed overspend, excess, variance

**Budgeted Spend**:
Spending that landed in a category that has an active budget.
_Avoid_: Planned spend, tracked spend

**Unbudgeted Spend**:
Spending that landed in an expense category with no active budget. Invisible to
every budget-basis figure, so it is always disclosed alongside them.
_Avoid_: Untracked spend, other spend, miscellaneous

### Derived metrics

**Month Tense**:
Which side of today a month falls on: current, closed, or not started. Decided
in the backend, because only it knows the owner's timezone, and named in the
figures it qualifies rather than left for each interface to work out — it is what
tells an outcome apart from a plan. A month that is not current has no daily
allowance, and one that has not started has no progress to report.
_Avoid_: Past month, future month, not current month

**Safe to Spend Today**:
BurnRate's headline metric: the amount the owner can spend today without
putting the month's variable budgets out of reach. Remaining variable budget,
less any fixed overrun, divided by the days left in the month counting today.
It is never negative and is undefined outside the current month.
_Avoid_: Daily allowance, daily budget, spendable, available today

**On-Plan Remaining**:
What would be left of the variable budget at this point in the month had spend
tracked the budget exactly. The comparator the headline's status is judged
against, because judging it against the planned daily pace reads as a warning
every month-end even when nothing is wrong.
_Avoid_: Expected remaining, target remaining

**Money Left**:
The monthly budget still unspent, on a budgeted basis.
_Avoid_: Budget left, remaining budget, headroom

**Burn Rate**:
The daily pace of variable spend so far this month. Fixed commitments are
excluded, so it measures controllable spend only.
_Avoid_: Spend rate, velocity, daily average

**Net Cash Flow**:
Income minus spending for the month, transfers excluded on both sides. This is
the same figure as money saved in the month; the product names it once.
_Avoid_: Saved, savings, surplus, net income, net

**Savings Rate**:
Net cash flow as a share of the month's income, carrying the same on-track /
watch / over verdict the budgets use. Decided in the backend, so any interface
that shows it shows the same verdict. A month with no income yet reads on-track,
not watch.
_Avoid_: Savings percentage, keep rate

**Cushion**:
How many months of normal expenses the owner's designated savings would cover.
The primary form of runway, and defined whether or not they are in deficit.
_Avoid_: Runway, buffer, emergency fund, months of runway

**Deficit Runway**:
How long the owner could sustain a negative cash flow before designated savings
run out. Only meaningful, and only shown, while cash flow is actually negative.
_Avoid_: Runway, time left, survival time
