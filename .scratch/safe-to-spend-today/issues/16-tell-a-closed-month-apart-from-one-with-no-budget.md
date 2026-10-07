# 16: Tell a closed month apart from a month with no budget

**What to build:** `safe_to_spend_today` decides `no_budget` before it considers
whether the month is the current one, so a month that closed before the owner ever set
a budget is captioned as an invitation to set one. Found by `/code-review` on ticket
11, in the same family that ticket closed: the page states something about a month it
does not know.

**Blocked by:** None

**Status:** done

- [x] A month that is not the current one never asks the owner to set a budget for it
- [x] A current month with no variable budget still reads `no_budget`
- [x] A current month budgeted entirely to fixed commitments still reads `no_budget`
- [x] The precedence is stated at seam 1 as its own case, both orders covered
- [x] `docs/product/metrics.md` and `docs/adr/0002-safe-to-spend-today-definition.md` describe the precedence that ships

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

## Comments

**The third way was taken, not the preferred one.** `safe_to_spend_status` now carries
`month_closed` and `month_not_started` in place of `not_current_month`, so the domain
owns tense and no client derives it. The ticket scoped this out for touching the enum
`ADR-0002` fixes at five values; the decision was re-made because by then there were
*two* tense defects open rather than one, and ticket 17 is precisely the "next client
re-implements the comparison" that `/code-review` predicted on ticket 11. `ADR-0002`
carries the amendment with the reasoning for the original five values and why they did
not survive.

**`is_current_month: bool` became `month_tense: MonthTense`.** The calendar comparison
stays in `SummaryService._month_tense`, because `reference_day` is resolved through
`APP_TIMEZONE` and only that side knows it; what a tense *means* stays in the domain.
Comparing two dates is not policy.

**Tense now outranks `no_budget`, which is the ticket's actual subject.** Verified: May
2026 read on 15 June returns `month_closed` where it returned `no_budget`. The
dashboard's set-a-budget branch can no longer fire for a month the owner is not in,
because the backend never sends `no_budget` for one — so the fix is in the domain and
the UI inherits it. Mutation-checked: swapping the two branches back fails the two
table rows that cover it.

**The caption question the ticket flagged was real, and is answered.** "What May 2026
finished with, of the €0.00 it had budgeted" is true and reads as noise, so a month with
no budget gets its own wording: "May 2026 closed with no budget set, so there is no plan
to compare it against", and "July 2026 has no budget set yet" ahead of the committed-spend
sentence. Rendered through `react-dom/server` across four states — closed with no budget,
not started with no budget, not started with 500.00 committed, and the current month with
no budget — confirming the first three no longer ask the owner to set a budget and the
fourth still does.

**`monthHasPassed` is gone.** It existed to compare `month` against `current_month`,
which is the comparison the split removes from every client. `web/` type-checks through
`docker build --target build`.

**What this left for ticket 17.** The Telegram formatter now reads the tense off the
status — the two tenses are rendered alike in the allowance line on purpose, and the
lines beneath it still describe a month that has not begun as if it were in progress.
That rendering is 17's, and it no longer has a "where does tense come from" question in
front of it.
