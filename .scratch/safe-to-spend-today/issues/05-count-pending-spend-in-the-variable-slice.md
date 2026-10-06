# 05: Count Pending spend in the Variable slice

**What to build:** Last night's card payment reduces this month's figures before
the bank settles it, so the owner is not invited to spend the same money twice.
Fixed commitments keep being judged by their estimate until they settle, because
a partial hold on a bill would otherwise convince the product the bill is tiny.

The derivation has one trap worth stating: the Variable slice cannot be reached
by subtracting Booked fixed spend from total spending once Pending counts, or a
Pending charge in a Fixed Budget category lands in the Variable slice — the one
place it must never go.

**Blocked by:** 03, 04

**Status:** done

- [x] Pending spend counts toward month-to-date spending, Budgeted Spend and the burn rate
- [x] Booked fixed spend alone feeds the Fixed Budget step projection and the Fixed Overrun
- [x] A Pending charge in a Fixed Budget category lands in neither the fixed nor the Variable slice
- [x] A Fixed Budget with only a Pending charge still projects at its budgeted estimate
- [x] Per-category Variable rows include Pending; Fixed rows stay Booked-only and keep their not-yet-paid presentation
- [x] The summary exposes the Pending spend total so a movement in the figures has a visible cause
- [x] The metric definitions and domain docs record that Pending counts in the Variable slice only, and that the asymmetry is deliberate

## Comments

**Seam.** Only the spec's seam 2 -- `SummaryService` through its `month`/`today`
parameters -- plus the route's existing response-shape assertion extended for the
new field. No test was written anywhere else. The fixed row's "not yet paid"
presentation is already pinned at seam 4 by
`test_format_budgets_marks_fixed_pending_as_estimate`, and what this ticket adds is
the service-side guarantee that makes it keep working: a fixed row carries booked
spend only, so a 1.00 hold does not flip the row to "1.00 of 900.00 used".

**Four cycles, each red for its own reason.** Pending counts (260.00 vs 285.00) ->
a fixed row stays booked-only (1.00 vs 0.00) -> the step projection reads booked
spend (528.50 vs 1427.50) -> the disclosure exists (`KeyError`). The third cycle is
the one that forced the booked/pending split to survive all the way from the query
to the figure rather than being collapsed at the edge.

**The trap has its own test, and it passed on arrival, so it was mutation-checked.**
`test_summary_service_keeps_a_hold_on_a_fixed_bill_out_of_the_variable_slice` went
green without new code, because the committed-total subtraction was already in place
from the previous cycle. Re-run against the obvious-but-wrong edit -- subtract
*booked* fixed spend from a total that now counts pending, which is what "the fixed
slice is booked-only" invites -- the burn rate reads 19.07 instead of 19.00 and the
test fails. That is the one edit the rest of the suite does not catch, which is why
the test earns its place.

**Eight existing tests shifted, and the figure pin shifted deliberately.**
`..._every_booked_figure_of_the_seeded_month_to_the_cent` is now
`..._every_figure_...`: ticket 03 used it to assert the seeded pending snack counted
toward nothing, and this ticket is exactly where that stops being true, so the name
lost a word it no longer earns. Every amount in all eight was re-worked by hand from
the seed -- 285.00 spent, 115.00 left, 527.50 projected, 85.8% kept -- rather than
pasted from the failure output, which is the only way the pin can still disagree with
the code.

**Income stays booked-only.** Of the three status filters in the service, two now
count committed spend and `_get_monthly_income` is untouched: a credit the bank has
not settled is not money kept. Both halves of that asymmetry read in the cautious
direction, which is the same argument ADR-0003 makes for counting pending spend.
Net cash flow and the savings rate therefore move with pending spend (1740.00 ->
1715.00 on the seeded month); that is a restatement of a figure the owner already
reads, and it is intended -- committed money is gone whether or not the bank agrees
yet.

**A hold on a fixed bill counts towards nothing until it books.** Not the step
projection, not the variable slice, and -- after the correction below -- not monthly
spending or the month's budget either. The budgeted estimate already stands for the
whole commitment, so a partial authorization on top of it charges the same rent
twice, and `test_..._out_of_the_variable_slice` and
`test_..._does_not_report_a_hold_on_a_fixed_bill_as_unbudgeted` pin each half.
One figure now counts the same money as the rows printed beside it: `_counted_spend`
is read by both the per-category row and the budgeted total, so the two cannot
drift.

**`pending_spend_amount` discloses the pending spend that counted.** One identity
holds either way -- monthly spending less pending spend is what the bank has settled
-- and after the correction below the figure also matches what actually moved: a hold
on a fixed bill is excluded from both sides rather than disclosed as a cause of a
movement it did not make. Uncategorized pending counts toward neither, exactly as
uncategorized booked spend does today: the `Category` join drops it.

**Standing orders now count, upstream of this ticket.**
`_normalize_transaction_status` maps `SCHD` to pending -- found by ticket 04's review
arriving in the *booked* fetch -- so a scheduled payment the bank reports for later
this month counts as spend from the moment it appears. That is consistent with
counting committed money, and in a fixed category, which is where a standing order
usually lives, it lands in neither slice. Recorded as a thing to watch rather than
acted on: nothing here treats it specially, and the alternative is a status filter
that disagrees with the one the sweep uses.

**The Fixed Overrun does not exist yet.** Ticket 06 builds it. What this ticket
delivers for that criterion is the booked-only per-category figure it will read:
`fixed_spend_by_category[category_id].booked`. The step projection reads the same
figure now, so the overrun inherits the rule rather than restating it.

**Nothing in `web/` or the Telegram formatter changed.** Both read
`spent_amount` and `monthly_spending_amount` and so follow the service without
knowing pending exists. `pending_spend_amount` is exposed on the API and left
undisplayed; ticket 07 puts it on the dashboard and ticket 08 on `/summary`.

**No migration.** Status was already stored per transaction and the split is resolved
in query, so the schema doc stays untouched, as the spec said it would.

## Correction from code review

`/code-review` returned nine findings. Four were real defects in ticket 04's sync
code, which this ticket is what gives teeth: before pending counted, deleting or
misclassifying a pending row moved no figure. They are now ticket 10, except the one
that could not wait. Two of the three quality items were recorded there as well; the
third was rejected, with the reason.

**Finding 5 changed the shape of this ticket, and it was right to.** The first
version followed the spec's derivation literally: monthly spending counted a hold on
a fixed bill, and the variable slice removed committed fixed spend. That satisfies
every acceptance criterion and still leaves three things wrong, two of which the
original notes recorded as acceptable and one of which they missed:

* `budgeted_spending_amount` counted the hold while the per-category rows did not, so
  the dashboard's "Monthly spending" sub-line read 286.00 budgeted beside rows
  summing to 285.00.
* The invariant this same change added to `docs/technical/domain.md` -- pending counts
  in the variable slice only -- was contradicted by the `money_left` path.
* The missed one: a fixed category's budget *is* the commitment, so adding a hold on
  top counted 901.00 committed against a 900.00 estimate. Double counting, not
  disclosure.

So a hold on a fixed bill now counts towards nothing until it books, and the
derivation order carries the rule: the hold leaves the month total *before* the
variable slice is taken out of it, which is why the slice removes only booked fixed
spend. Three more cycles: the budgeted total and the rows reconcile through one
shared `_counted_spend`, a hold does not resurface as unbudgeted spend, and the
disclosure drops it too. Both edits were mutation-checked -- keeping the hold in the
month total, and subtracting it twice -- and each fails a different test. The figures
the owner sees changed by one cent of nothing in the seeded month, which has no fixed
budget; what changed is the holds case, where `money_left` went from 1014.00 to
1015.00.

One claim in that finding was wrong: it said nothing pinned which of the two figures
to trust, while `test_..._out_of_the_variable_slice` already asserted
`money_left_amount` explicitly. The disagreement it described was real regardless.

**Finding 2 was fixed here rather than deferred, because it deletes live spend.**
`not_in(set())` compiles to `... OR (1 = 1)` -- verified by compiling the predicate --
so a sync that reported no identifiers at all deleted every un-ignored pending row in
the 30-day window. Reachable without any bank misbehaviour: `_extract_transactions`
returns an empty list for a payload shape it does not recognise, and `AGENTS.md`
names restricted production returning empty results a valid product state.

The first attempt guarded on the identifier set being empty, and ticket 04's
`test_sync_deletes_a_pending_hold_the_bank_stopped_reporting` immediately failed --
correctly. A bank that reports zero rows *legibly* has made a real claim about every
hold in the window, and sweeping on it is the behaviour that test exists to protect.
So the gate is legibility, not emptiness: every page must arrive in a shape the
extractor recognises -- a `transactions` list or object, or top-level
`booked`/`pending` arrays -- before the sweep runs. The two tests now pull in
opposite directions, which is what makes the gate's placement checkable.

That fix also needed a second test. Mutating the legibility check to reject the
top-level-arrays shape broke nothing, because every fake client in the module wraps
its payload in `transactions` -- the same blind spot ticket 04 recorded, where the
double agrees with the code about the shape of the world.
`test_a_sync_whose_arrays_arrive_at_the_top_level_still_sweeps` covers it, and fails
against that mutation.

**The quality item that was rejected.** Moving `COMMITTED_STATUSES` and
`SpendByStatus` into `domain/metrics.py` would cut against ADR-0001, which scopes
that module to bands and thresholds over primitives with no ORM and no session.
These are stored status strings used inside SQL and the shape of a query result,
not policy. The defensible version of the same instinct -- one shared status
vocabulary beside `db/effective_date.py`, read by both the sweep and the spend
queries -- is in ticket 10, where it also closes the case discrepancy between the
sweep's exact match and the queries' `func.lower`.
