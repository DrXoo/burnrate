# Budget windows are month-granular, and a budget is counted in full

A budget's `[active_from, active_to]` window is read at month granularity: it
counts in full for any month the window touches at all. Both edges are therefore
month boundaries — `active_from` is required to be a 1st, and `active_to` is
always a month end or NULL — so neither edge can land mid-month and no figure has
to decide what a partial month is worth.
`docs/technical/database/schema.md` states the rule; this records what was
weighed, and why cancelling means what it does.

## Cancelling drops the month it happens in

Cancelling a budget records `active_to` as **the last day of the month before the
one it is cancelled from**. Saying "there is no more rent" is a statement about
what is still owed, the rest of that month included, so the month it is cancelled
in must not hold the budget — and because a month-granular window counts in full
for any month it touches, ending before the month is the only way to drop it.

The month cancelled *from* is the month on screen, which the endpoint takes as an
optional `?month=` exactly as the list endpoint does, defaulting to the one the
owner is in. It was read off the server's clock at first, so a click made while
paging through another month wrote a window for a month the owner was not looking
at: the refetched row came back unchanged while the toast said it was cancelled.

### Cancelling from a past month is allowed

It follows from the above that paging back to September and cancelling there
closes the window at the end of August, changing what September — and every month
since — reports. That was considered and **allowed deliberately**; there is no
guard against it.

BurnRate is single-owner. The only person who can rewrite these months is the one
whose spending they describe, so a backdated cancellation is the owner correcting
their own record, not falsifying a shared one. Refusing it would mean the product
knows better than the owner what their own past was, and the owner's way of fixing
a budget they forgot to cancel in March would be to leave it wrong for ever. The
risk being accepted is the owner misreading which month they are on and quietly
moving figures they were not looking at; the cancel control says "from this month
on" for that reason, and cancelling is undoable.

Note the asymmetry: reactivation is not month-relative. It clears `active_to`
outright, restoring the window as it originally stood, whichever month the click
is made from. The `?month=` it accepts only decides which month the response
reports the row's status against. Undo restores, it does not re-cut the window.

`active_to` was originally *yesterday*, which kept the cancellation month fully
budgeted on the grounds that the budget had genuinely run in it. That was the
wrong reading of the owner's intent: it left the dashboard quoting a target the
owner had just said would not be paid, and no later budget could cover that month
either, because a replacement overlapping it is refused. One rule now covers every
case, including a budget cancelled before it ever started: that lands with an
`active_to` before its own `active_from`, an empty window covering no month at
all.

The cost is paid in the opposite corner and is worth naming. If the charge for
this month had already landed before the owner cancelled — rent paid on the 1st,
cancelled on the 7th — the month loses the budget while keeping the spend, so that
spend is reported as **unbudgeted** and joins the variable burn rate, which is
meant to exclude lump commitments. Safe to Spend Today is unaffected: unbudgeted
spend is invisible to every budget-basis figure by design, and the variable total
loses the amount from both sides. Guarding that corner — keeping a month whose
category already holds spend — was considered and rejected as a rule whose answer
depends on data the owner cannot see from the button they are pressing.

Because cancelling destroys nothing, it is undoable: `reactivate_budget` clears
`active_to` on the same row, so the months it already covered keep their amount
and their identity. It is refused when reopening the window would overlap another
budget for the same category, naming that budget — two overlapping budgets are
summed into a single inflated figure.

Whether a given row could be reopened is reported on the row itself, as
`can_reactivate`, from the same function the endpoint refuses with. A row closed by
a later budget is indistinguishable from a cancelled one by its own fields, so an
interface deciding for itself offered a restore button that was refused every time
— and it grew one such dead row per amount change the category had ever had. The
rule is decided in the backend, like the budget verdicts, so every interface gets
the same answer.

That refusal is asked through the same predicate `create_budget` uses, because the
two are one question: does an open window from this start date hit anything? Asked
separately, they disagreed. Reactivation looked for a budget starting *later*,
which a replacement starting the same month is not, so cancelling a budget and
setting a different amount for the same month left the original reopenable — and
reopening it put two active rows in that month. An empty window is overlapped by
nothing, through the same rule that makes it inactive everywhere, which is what
lets the replacement be created in the first place.

Because both edges sit on month boundaries, a window that closes in the month on
screen always closes on that month's last day. So interfaces mark the row as the
budget's **final month** rather than dating the stop: a date there read as a
mid-month end, which this rule cannot write.

A budget whose window starts after the month on screen is `scheduled` there. It
covers no month yet, so the month's figures exclude it — but its category already
has a budget, and offering that category another is refused for overlapping. Such
rows are therefore listed apart and still count as budgeted.

Rows written under the old rule are normalised by
`0008_budget_active_to_month_end`, which moves a mid-month `active_to` to the last
day of the previous month: the date the current rule would have written for the
same cancellation. It changes what those past months report, which is the
correction being made. `budget_month_status` still reads a mid-month date
correctly — counting that month in full — so an un-migrated database is wrong
about the owner's intent but never inconsistent with itself.

## Considered Options

**Proration** — counting a budget for the fraction of the month its window
covers — is the obvious reading of a date-bounded window. It is rejected for now
as a product decision rather than a modelling one: a prorated budget changes what
Money Left, the fixed step projection, Safe to Spend Today and the per-category
rows all mean mid-month, and it asks the owner to accept that switching a budget
off on the 15th leaves them half a budget rather than none. The month-granular
rule is also what lets an open window (`active_to` NULL) be the normal state and
roll forward indefinitely, which is why nothing ever asks the owner to close a
month.

## Consequences

Anything deriving a month's budget reads whole rows, never partial amounts, and
`burnrate.db.budget_windows` is the single place that decides which rows a month
holds. It states the rule in the two forms its readers need — a SQL criterion for
the query and a status predicate for a row already loaded — because there are two
readers: the summary, which sums the amounts a month holds, and the budget list,
which says whether a row applies to the month being viewed.

Those two were written independently and disagreed. The list compared each window
against the owner's day while the total compared it against the month, so a rent
budget cancelled in October vanished from September's list while September's total
still counted it — one month, two screens, contradicting each other. A budget's
status is therefore read against the month being viewed and never against today.
A cancelled budget is `inactive` for the months it no longer covers, and the
budget list keeps those rows in a group of their own so the way back stays one
click, rather than hiding them or offering to cancel them again.

A change to proration is not a change to those two functions: it is a change to
every figure built on them, and to the overlap validation in `BudgetService`.
