# 16: Tell a closed month apart from a month with no budget

**What to build:** `safe_to_spend_today` decides `no_budget` before it considers
whether the month is the current one, so a month that closed before the owner ever set
a budget is captioned as an invitation to set one. Found by `/code-review` on ticket
11, in the same family that ticket closed: the page states something about a month it
does not know.

**Blocked by:** None

**Status:** ready-for-agent

- [ ] A month that is not the current one never asks the owner to set a budget for it
- [ ] A current month with no variable budget still reads `no_budget`
- [ ] A current month budgeted entirely to fixed commitments still reads `no_budget`
- [ ] The precedence is stated at seam 1 as its own case, both orders covered
- [ ] `docs/product/metrics.md` and `docs/adr/0002-safe-to-spend-today-definition.md` describe the precedence that ships

## The defect

Verified: May 2026 read on 15 June, with budgets that start on 1 June, returns
`safe_to_spend_status: "no_budget"` and `current_month: "2026-06"`. The dashboard
takes its `no_budget` branch before any tense is considered and prints "Safe to spend
today / Set a budget / Add a monthly budget under Rules & Budgets and this becomes
your daily number" over a month that closed weeks ago.

The ordering is in `domain/metrics.py`: `variable_budget_total <= 0` returns
`no_budget` ahead of the `is_current_month` check. Both branches are individually
right; only their order is wrong, and only for a month the owner is not in.

## The decision to make

**Preferred: let `not_current_month` win.** One line moved in the domain, and the
dashboard's existing past and future captions then cover the case with no UI change at
all. The thing to look at before shipping it: that caption quotes the month's budget,
so a closed month with no budget would read "What May 2026 finished with, of the €0.00
it had budgeted" — true, but worth a look to decide whether a zero budget deserves its
own wording.

**Alternative: leave the domain alone and have the UI consult `current_month` before
its `no_budget` branch.** Keeps the status meaning "nothing is budgeted" regardless of
tense, at the cost of the tense decision living in two places on the page — which is
the shape ticket 11 spent its effort removing.

`/code-review` argued a third way on ticket 11: split `not_current_month` into a
closed/not-started pair and let the domain own tense outright. It would cover this
case, ticket 17's, and any future client in one move. It is out of this ticket's scope
because it changes the status enum, which `ADR-0002` fixes at five values and both
interfaces read — but if it is ever done, this ticket disappears into it.

## Testing

Seam 1, the pure domain functions. The case is a table row, not a fixture: no budget
and not the current month, both orders of the two conditions, plus the two cases that
must not move (a current month with no variable budget, and one budgeted entirely to
fixed commitments).
