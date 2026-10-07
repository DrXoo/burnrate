# 15: Keep a month's projection honest before it starts

**What to build:** The spend projection discards money already committed in a month
that has not started, so it reports the month landing exactly on budget while the
headline beside it already shows the budget blown. Found by `/code-review` on ticket
11 and verified against the service.

**Blocked by:** None

**Status:** ready-for-agent

- [ ] A month that has not started projects at least the spend already committed in it
- [ ] `projected_overspend_amount` is non-zero when committed spend already exceeds the budget, whichever month it is
- [ ] The same holds with no budget set, where the extrapolation currently returns 0.00
- [ ] Every projection figure for a current or past month is unchanged to the cent
- [ ] The behaviour is stated at seam 2 as a worked example, not as a restatement of the formula

## The defect

A pending standing order of 500.00 carrying a 3 July value date, against a Food
budget of 300.00 in a 400.00 month, read on 15 June for July:

| field | value |
|---|---|
| `budgeted_spending_amount` | 500.00 |
| `money_left_amount` | -100.00 |
| `projected_month_end_spend_amount` | 400.00 |
| `projected_overspend_amount` | 0.00 |

`_days_elapsed_in_month` returns 0 for a month that has not started, and
`_project_spend` then returns `budget_reference` unchanged: its "no signal yet, assume
spending tracks the budget" branch. That assumption was true when a future month could
not hold spend. Effective Date (ticket 03) and pending spend counting (ticket 05) made
it false, because a hold carrying a future value date is filed in the month it is due.
`_extrapolate_spend` has the same shape and returns 0.00, dropping committed future
spend entirely when no budget exists.

On screen the dashboard prints "spent €500.00" and "projected €400.00" on the same
`MeterBar`, and the projection needle claims the month lands on budget while the
headline above it reads -€100.00. It also contradicts the paragraph ticket 11 added to
`docs/product/metrics.md`: *"A month that has not started is not necessarily
untouched."*

## A floor, not a new model

A month that has not started has no pace to extrapolate from, so there is nothing
cleverer available than refusing to project below what is already committed:
`max(spend_to_date, budget_reference)` on the budget-anchored path, and
`spend_to_date` on the extrapolation. Both keep every current- and past-month figure
untouched, because both branches only fire when `days_elapsed <= 0`.

Worth checking while here: whether the confidence blend wants the same floor on day 1
of a live month, where `days_elapsed` is 1 and a single large hold dominates a pace
computed over one day. Probably not — that is the blend doing its job — but it is the
nearest neighbour of this defect.

## Testing

Seam 2, the summary service through its `month` and `today` parameters, which is where
the figures above were taken from. The worked example is the table at the top. The
existing `test_summary_service_reports_every_figure_of_the_seeded_month_to_the_cent`
is the regression that the live month is unchanged.
