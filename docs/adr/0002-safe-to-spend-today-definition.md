# Safe to Spend Today: remaining variable budget over days left, counting today

Safe to Spend Today is remaining variable budget, less any fixed overrun,
divided by the days left in the month counting today. `docs/product/metrics.md`
states what the metric is; this records why the four obvious alternatives are
not it.

## Considered Options

**Budgeted basis, not all-expense.** The numerator uses
`variable_budget_total - variable_budgeted_spend`, so it counts only spend in
categories that have a budget. Subtracting all expense spend would absorb spend
in unbudgeted categories too, which is more honest about money leaving the
account but mixes universes: the budget total only covers budgeted categories,
so unbudgeted spend could grind the headline to zero with no budget the owner
can point at to explain it. Unbudgeted spend is disclosed beside the headline
instead, via the existing `unbudgeted_spending_amount`.

**Day count includes today.** `days_in_month - days_elapsed + 1`. The last day
of the month then resolves to 1 — today's allowance is everything left — rather
than needing a zero-division special case. Bank data also lags, so today's spend
frequently has not booked when the number is read.

**Fixed overruns are deducted.** Summed per fixed category as
`max(0, spent - budget)`, so an underrun on one fixed category cannot fund an
overrun on another. Without this, a rent budget of 800 charged at 850 leaves the
allowance 50 too generous for the rest of the month — money already gone, and
the system already knows, because `_project_fixed` trusts the actual charge.

**Status is judged against on-plan remaining, not against the planned daily
pace.** This is the least obvious of the four. If spend tracks the budget
exactly, the ratio of the allowance to `expected_daily_spend` is
`(D-e)/(D-e+1)` — 0.94 by day 15, 0.83 by day 25, 0.50 by day 29 — so *any*
fixed threshold against planned pace fires in the last week of every month.
The pre-existing UI rule had exactly this bug: `budgetedSpend / budget >= 0.85`
is reached on day 26 of a perfectly on-plan 30-day month. Comparing against
`on_plan_remaining = B * (D-e) / D` gives a ratio that sits at 1.0 whenever
spend is on plan, at any point in the month, so the bands are time-stable.
`roadmap.md` is explicit that this product fails by crying wolf.

## Consequences

The metric is never negative, per `metrics.md`. `safe_to_spend_status` carries
`no_budget | not_current_month | on_track | watch | over`, with a null amount for
the first two, so a zero amount means exactly one thing: budgets exist, the
month is current, and they are used up.
