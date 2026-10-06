# 06: Safe to Spend Today, in the domain and the API

**What to build:** The number itself. The owner can ask the API how much they can
spend today without putting the month's Variable Budgets out of reach, and get an
answer that is never negative, that accounts for a Fixed Budget that overshot,
and that carries a status they could read as a colour without reading the number.

The status is judged against On-Plan Remaining rather than the planned daily
pace, because the obvious comparator warns in the last week of every month even
when spend tracks budget exactly.

**Blocked by:** 02, 05

**Status:** done

- [x] The allowance is remaining Variable Budget, less Fixed Overrun, over the days left in the month counting today
- [x] The allowance is never negative
- [x] Fixed Overrun is summed per Fixed Budget category from Booked spend, so an underrun on one cannot fund an overrun on another
- [x] Status is a single five-value field, and the amount is null for the no-budget and not-current-month cases
- [x] A zero amount can only mean budgets exist, the month is current, and they are used up
- [x] A month that is exactly on plan reads on-track on every day of that month, including the last week — holds for the last week; **not** for the last day, where the spec's zero guard overrides it. See the note below
- [x] The last day of the month resolves without a special case, and the zero On-Plan Remaining case is guarded
- [x] The API exposes the allowance, its status and the Fixed Overrun total
- [x] Domain tests cover the bands at day 1, 15, 25, 29 and the last day, the zero clamp, and both undefined cases, as worked examples with no database fixture
- [x] The metric definitions doc matches what was implemented

## Comments

**Seams.** The spec's seam 1 (`test_domain_metrics.py`, no fixture) and seam 2
(`test_summary_service.py` through `month`/`today`), plus the route's existing
response-shape assertion extended for the three new fields. No test written
anywhere else. Seam 1 carries the policy table; seam 2 asks only whether the rule
is wired to the right query.

**Twelve cycles.** `fixed_overrun` -> the division -> the overrun deduction -> the
zero clamp -> the bands -> the last-day guard -> both undefined cases -> the fields
on the seeded month -> the overshoot -> booked-only -> the undefined cases at the
service -> the API contract. The band cycle is the one that paid: all fourteen
hand-worked amounts passed against a stub that returned `on_track` for everything,
which is what confirmed the two divisions before any status logic existed.

**Three tests passed on arrival and were mutation-checked rather than trusted.**

* The overrun deduction. I wrote `- fixed_overrun` during the division cycle
  without a test driving it -- a horizontal-slicing slip. Removing the subtraction
  makes `..._charges_the_owner_for_a_fixed_budget_that_overshot` read 9.38 instead
  of 6.25, so the test has teeth even though it arrived after the code.
* The seam-2 overshoot test, which the previous cycle's wiring already satisfied.
  Passing `Decimal("0.00")` as the overrun fails it.
* **The one that found a real gap.** Mutating the service to read
  `fixed_spend_by_category[...].total` instead of `.booked` broke *nothing* in the
  whole suite. The obvious test for it does not catch it either: a 1.00 hold on a
  900.00 rent budget is below the estimate, so `max(0, 1 - 900)` is zero whichever
  figure is read. It takes a fixed category that is *already* over on booked spend
  and has a hold on top -- Utilities booked at 120.00 of 100.00 with a 30.00 hold,
  where booked-only says 20.00 and committed says 50.00, costing the owner another
  1.88 a day for money the bank has not moved.
  `..._does_not_deepen_a_fixed_overrun_with_a_hold` covers it and fails against
  that mutation. This is the same blind spot ticket 05 recorded in a different
  shape: the natural fixture agrees with the code.

**A criterion and the spec disagree about the last day, and I followed the spec.**
"A month that is exactly on plan reads on-track on every day of that month,
including the last week" cannot hold on the last *day* under the spec's own guard:
a month exactly on plan has spent its budget by the 30th, so nothing remains, and
"on_track if anything remains and over otherwise" makes that `over` with a 0.00
amount. Implemented as the spec and ADR-0002 state it. The criterion's content is
the last *week*, which is where the replaced rule actually misfired -- the day-29
on-plan row reads 0.5 against the planned daily pace, i.e. `over` for an owner
doing nothing wrong, and it is in the table reading `on_track`. The pairing is also
the coherent one: `over` beside 0.00 says the same thing the zero amount already
says, where green beside 0.00 would contradict the number next to it. Flagging it
because it is a visible difference on one day a month and the alternative is a
one-character change (`>= 0`).

**No-budget wins over not-current-month when both hold.** Not stated in the spec.
It is the more useful of the two: it tells the owner what to do, where saying a
budgetless month finished against a plan it never had says nothing. Pinned as a
row in the undefined-cases table, and it matters for the common case of a fresh
install where every month is budgetless.

**A month budgeted entirely to fixed commitments reads `no_budget`.** It falls out
of `variable_budget_total <= 0`, and it is the right reading: user story 13 asks to
be told the number is missing rather than believing they can spend nothing, and
0.00 is exactly the "you may spend nothing" claim. Recorded because it is a
behaviour nobody asked for by name.

**The overrun reads the same figure the step projection trusts.**
`fixed_spend_by_category[...].booked`, which ticket 05 left in place for exactly
this. The overrun inherits the booked-only rule rather than restating it, so the
two cannot disagree about what a fixed commitment has cost.

**`is_current_month` is passed in rather than derived.** The domain cannot tell a
current month's last day from a past month -- `days_elapsed == days_in_month` in
both -- so the civil-date comparison stays in the service, which is where the
timezone-resolved reference day already lives.

**Mild duplication left for review.** `_is_current_month` and
`_days_elapsed_in_month` both build `(year, month)` tuples. The latter needs a
three-way comparison, so sharing would only remove the equality branch. Left
alone: the two answer different questions, and refactoring is not part of the loop.

**The figure pin shifted by two entries, worked by hand.**
`..._reports_every_figure_of_the_seeded_month_to_the_cent` gains
`safe_to_spend_today_amount: "7.19"` (115.00 of the 400.00 budget left, over the
15th and the fifteen days after it) and `fixed_overrun_amount: "0.00"` (nothing in
the seeded month is fixed). Neither was pasted from the failure output.

**The route gained one test beyond the extended assertion, and it earns its place.**
The spec says the nullable amount is caught by the existing type check, but the
service returns `dict[str, Any]`, so nothing would have caught
`safe_to_spend_today_amount: str` in the schema -- a 500 on every no-budget month.
`..._serves_an_allowance_the_owner_does_not_have` pins the null round-tripping.

**Docs.** `docs/product/metrics.md`: the Safe to Spend Today section now carries
the day count including today, the budgeted basis, the overrun deduction, the
five-value status with its null-versus-zero rule, and the on-plan-remaining
comparator with the last-day guard; a new Fixed Overrun section states the
per-category sum and the booked-only rule. `GLOSSARY.md` already defined all three
terms, and the domain doc's assigned items shipped with tickets 03 and 05, so
neither changed. No migration, as the spec said.

**Nothing in `web/` or the Telegram formatter changed.** The three fields are
exposed and left undisplayed; tickets 07 and 08 consume them. `SummaryDashboard`
does not know about them yet, which is ticket 07's work and why that ticket carries
the nullable-type criterion.

## Correction from code review

`/code-review` returned three findings. One was a defect in this ticket's own
module, one was already recorded, and one was fixed here rather than deferred.

**The finding against this ticket's code was real but unreachable, and is now
ticket 10's fourth defect.** `fixed_overrun` pairs one `FixedCommitment` per fixed
*budget row* with the category's whole-month booked spend, so a category holding
two budget rows in one month counts its commitment twice -- 1100.00 of overrun for
a Rent budgeted 500.00 then 600.00 with 1100.00 booked, which zeroes the headline
and flags it `over` for an owner exactly on budget.

Probed before acting rather than taken at face value, and two things came back.
It is not reachable through the product API: `_validate_month_start` forces
`active_from` to the first of a month and `_ensure_no_overlap` refuses the second
budget outright ("Budget periods must not overlap for the same category"), while
one starting the next month falls outside `active_from < month_end`. And when the
invariant is broken by seeding rows directly, `fixed_projected` double-counts
identically (2727.50 projected) and `budget_usage` prints two Rent rows -- both
preexisting, because the overrun inherited the per-row pattern from
`_project_fixed`, which is precisely what ticket 05 left in place so the two
figures could not disagree. One bug, three symptoms, and patching only the newest
would leave the projection lying and undo that shared derivation. Ticket 10.

**The window finding was already defect 1 of ticket 10**, re-found independently
with the same month-boundary example. Noted there, because two passes landing on
it is a signal about which to fix first.

**The legibility finding was fixed here, because it deletes live spend.** The same
test ticket 05 applied to its own finding 2.
`_is_readable_transactions_payload` promised in its docstring to recognise shapes
"by their keys", and did so for the top-level branch while returning `True` for
*any* dict under `transactions`. A bank nesting its rows under another key --
`{"transactions": {"entries": [...]}}` -- reads as a legible empty fetch, the
identifier set comes back empty, and every un-ignored pending row in the 30-day
window is swept. Not self-healing either: every later sync reads the same
unreadable shape. The failure log makes the diagnosis plain --
`transactions_type: 'dict', transactions_count: 0, booked_count: 0` beside a sweep
that ran.

The gate's three branches now mirror `_extract_transactions` one for one.
`..._in_an_unrecognised_shape_sweeps_nothing` covers it with the sharp version of
the case: the payload *does* still report the hold, so the row is deleted against
the bank's own evidence that it is live.

**Mutation-checking the fix found a second gap, which is also closed.** With all
three branches made explicit, removing the `transactions`-list branch broke
*nothing*: no test drove a bare `{"transactions": [...]}` payload through a sweep,
so a third of the gate was unpinned -- and read as illegible, such a bank would
never have a sweep run at all, the mirror of the failure
`..._arrays_arrive_at_the_top_level_still_sweeps` exists to prevent.
`..._as_one_flat_list_still_sweeps` closes it and fails against that mutation. All
three branches are now individually pinned.

One process note: the first mutation run was worthless and nearly reported as
evidence. The backup it restored from was the pre-fix file, so two of the three
mutants were applied on top of the original bug and their failures meant nothing.
Redone from a backup taken after the fix, with a `cmp` guard that shouts when a
mutation edit silently matches nothing.

`docs/technical/bank-integrations/enable-banking.md` carried the same imprecision
the code did -- "a `transactions` list or object" -- and now states the key
requirement and why an object alone is not enough.
