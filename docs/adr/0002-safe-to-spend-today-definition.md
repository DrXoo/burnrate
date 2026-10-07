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

## Amendment: the status names the month's tense

Superseding the original five-value status, `safe_to_spend_status` carries
`no_budget | month_closed | month_not_started | on_track | watch | over`.

The original had one `not_current_month`, on the reasoning that a month the owner
is not in has no allowance and the reason is all the status owes them. That was
true of the allowance and false of everything beside it: a client cannot caption a
month, pick a tense for a sentence, or decide whether a figure is an outcome or a
plan without knowing which side of today the month falls on. So each client derived
it, and two of the three got it wrong. The dashboard compared the month on screen
against one it derived from UTC, which read a month that had not started as a closed
one for the hours of every month-end where the two clocks disagree. The Telegram
summary did not derive it at all and printed a used-budget bar, a daily pace over
zero elapsed days and a month-end projection for a month that had not begun.

Naming the tense in the status is what stops the next client being the third. The
comparison stays in `SummaryService`, which is the only side that knows
`APP_TIMEZONE`; what a tense *means* stays in `domain/metrics.py`.

**Tense now outranks `no_budget`.** The original order returned `no_budget` first,
on the reasoning that it is the more actionable of the two — it tells the owner what
they can do about it. About a month that closed before they ever set a budget they
can do nothing, and the dashboard printed "Set a budget / this becomes your daily
number" over a month weeks gone. A current month with nothing budgeted for
day-to-day spend still reads `no_budget`, including one budgeted entirely to fixed
commitments.

## Consequences

The metric is never negative, per `metrics.md`. The three statuses above with no
allowance to report pair with a null amount, so a zero amount means exactly one
thing: budgets exist, the month is current, and they are used up.
