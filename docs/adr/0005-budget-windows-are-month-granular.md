# Budget windows are month-granular, and a budget is counted in full

A budget's `[active_from, active_to]` window is read at month granularity: it
counts in full for any month the window touches at all. So `active_from` is
required to be the 1st, and cancelling a budget records `active_to` as
*yesterday* rather than today — otherwise cancelling on the 1st hands the new
month the whole amount of a budget the owner has just switched off, and the
dashboard quotes a figure the budget list is simultaneously calling inactive.
`docs/technical/database/schema.md` states the rule; this records that the
alternative was weighed.

## Considered Options

**Proration** — counting a budget for the fraction of the month its window
covers — is the obvious reading of a date-bounded window, and it is what someone
will propose on finding `active_to = today - 1`. It is rejected for now as a
product decision rather than a modelling one: a prorated budget changes what
Money Left, the fixed step projection, Safe to Spend Today and the per-category
rows all mean mid-month, and it asks the owner to accept that switching a budget
off on the 15th leaves them half a budget rather than none. The month-granular
rule is also what lets an open window (`active_to` NULL) be the normal state and
roll forward indefinitely, which is why nothing ever asks the owner to close a
month.

The cost of the rule is paid at the edges and is visible: cancelling on the 1st
leaves the new month unbudgeted, which reads as `no_budget` rather than as a
budget of zero, and cancelling on the 2nd or the 15th leaves the month fully
budgeted because the budget genuinely ran in it. A subsequent budget for that
same month is then refused for overlapping, correctly.

## Consequences

Anything deriving a month's budget reads whole rows, never partial amounts, and
`_get_active_budgets` is the single place that decides which rows a month holds.
A change to proration is not a change to that function: it is a change to every
figure built on it, and to the overlap validation in `BudgetService`.
