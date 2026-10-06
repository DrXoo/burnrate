# 10: Align the sync windows, and keep a hold's status honest

**What to build:** Four defects, three in the pending machinery and one in the
fixed figures, found by `/code-review` on tickets 05 and 06 and verified against
the code. The first three quietly lose or invent committed spend, and ticket 05
is what gave them teeth: before pending counted, every one of them was invisible
in the figures. The fourth is unreachable today and is defence in depth.

**Blocked by:** None (05 is done; this does not block 06-09)

**Status:** ready-for-agent

- [ ] The booked re-import window covers at least the pending sweep window, so a hold that books after a month boundary is re-imported instead of lost
- [ ] A pending row whose Effective Date is in the future can be swept once the bank stops reporting it
- [ ] A row that arrives in a response's `pending` array with no status of its own is stored as pending, not as booked
- [ ] Each case carries its own test at seam 3 (the sync entry point with a fake client), and each is mutation-checked
- [ ] The fixed figures are derived per budget *category*, so a category with two budget rows in one month cannot have its commitment counted twice
- [ ] `docs/technical/bank-integrations/enable-banking.md` records the window relationship as a constraint rather than two independent numbers

## The four defects

**1 — The windows disagree, and the narrower one is the re-import.**
`_current_month_transaction_window` returns `[first of the current month, today]`;
`_pending_transaction_window` returns `[today - 30 days, today]`, and the sweep is
scoped to the pending window. A card charge that pends on 31 January and books
overnight is, on the 1st of February, (a) absent from the pending response, (b)
inside the sweep's window, and (c) outside the booked window, so the bank is never
asked for its booked copy. The hold is deleted and the charge exists in neither
status: January is permanently understated. ADR-0003 justifies deletion with "the
trailing window makes the loss self-healing on the next sync", which assumes the
booked window covers the sweep window. It does not.

Widening the booked fetch to the same trailing 30 days is the cheap fix: the upsert
is idempotent, the volume is one owner's, and the two windows then stop being
independent numbers that have to be kept in step by hand.

A second `/code-review` pass, on ticket 06, re-found this independently and reached
the same conclusion from the same evidence -- the docstring's "self-healing on the
next sync" claim holds only for rows still in pending state. A third pass, on ticket
07, found it again, with the sharper framing that the sweep window sits outside the
booked window for roughly the first 30 days of every month, and the observation that
the existing tests cover a 45-day-old hold -- outside the sweep window entirely --
but not one 1 to 30 days back in the previous month, which is the reachable case.
That test gap is the thing to add when this is fixed.

A fourth pass, the branch-wide one run after ticket 08, re-found it again with the
same January-to-February example and the same conclusion.

Nothing new to do before then; recorded because four independent passes landing on
it is the strongest signal in this ticket about which defect to fix first.

**2 — A future-dated pending row can never be swept.**
The sweep's window predicate is `resolved >= date_from, resolved <= date_to` with
`date_to = today`. `_normalize_transaction_status` maps `SCHD` to pending, so a
standing order the bank reports on the 10th for the 25th resolves an Effective Date
of the 25th, which `within_month` counts as this month's spend and the sweep can
never reach. Cancel it at the bank and the phantom sits in monthly spending for
ever. `test_the_sweep_leaves_a_scheduled_payment_the_booked_fetch_reported` dates
its standing order `owner_today()`, so this path is untested today.

The upper bound is what buys nothing here: the lower bound is what keeps the sweep
from judging rows the bank was never asked about, while a row dated past today is
inside the fetch's subject matter whatever date it carries.

**3 — A hold with no status of its own is stored as settled.**
`_extract_transactions` flattens a response to `[*booked, *pending]` and keeps no
record of which array a row came from; `_normalize_transaction_status` maps an
absent or unrecognised status to `"booked"`. A bank that marks status by array
rather than per transaction therefore gets its holds stored as booked spend, which
(a) under-reports `pending_spend_amount`, (b) feeds `_project_fixed` -- a 1.00
pre-authorization projecting 900.00 of rent as 1.00, the exact failure ADR-0003
exists to prevent -- and (c) is invisible to the sweep, which filters on
`status == "pending"`, so it is never cleaned up.

Carrying the array a row came from through the flattening, and defaulting a row from
the `pending` array to pending status, is the whole fix. Which shape the real bank
sends is still unknown, which is the same reason ticket 04 covered both payload
shapes.

**4 — The fixed figures are derived per budget row, while spend is aggregated per
category.** Found by `/code-review` on ticket 06. `_get_active_budgets` returns one
row per `Budget` record overlapping the month, and three figures then pair each row
with `fixed_spend_by_category[row.category_id]` -- the category's *whole-month*
booked spend. A category holding two budget rows in one month therefore has its
commitment counted once per row:

* `fixed_overrun` reads 1100.00 instead of 0.00 for a Rent category budgeted
  500.00 then 600.00 with 1100.00 booked -- which zeroes Safe to Spend Today and
  flags it `over` for an owner who is exactly on budget.
* `fixed_projected` adds 1100.00 twice, so the month-end projection overstates by
  the whole commitment. Pre-existing, from before ticket 05.
* `budget_usage` prints two Rent rows, each showing 1100.00 spent against its own
  estimate. Also pre-existing.

**It is not reachable through the product API today, which is why it is here rather
than fixed in ticket 06.** `BudgetService._validate_month_start` forces
`active_from` to the first of a month, `_ensure_no_overlap` rejects a second budget
whose period touches an existing one, and `create_budget` auto-closes the previous
open row at `active_from - 1 day`. Probed directly: a second same-month budget is
refused with "Budget periods must not overlap for the same category", and one
starting the next month falls outside the window's `active_from < month_end`. The
figures above were produced by seeding the two rows straight into the session,
bypassing the service.

So the defect is a missing invariant in `SummaryService`, not a live miscalculation,
and the fix belongs here for two reasons. First, it is one bug with three symptoms:
patching `fixed_overrun` alone would leave the projection and the rows lying in the
same scenario, and ticket 06's overrun deliberately reads the same
`fixed_spend_by_category[...].booked` the step projection does so the two cannot
disagree -- splitting them now would undo that. Second, the right shape is to fold
the fixed budgets to one commitment per category before deriving anything from
them, which touches all three call sites and is exactly the kind of change
`AGENTS.md` forbids riding along on a feature ticket.

Worth deciding while here: what a category's commitment *means* when it has two
estimates in one month. Summing them, as `monthly_budget` already does, is the
reading consistent with the existing total.

---

## Quality items from the same review, deliberately not bundled here

None changes behaviour; they are recorded so they are not rediscovered.

* **One status vocabulary, shared.** The sweep matches `Transaction.status ==
  "pending"` exactly, every spend query wraps the column in `func.lower`, and
  `_normalize_transaction_status` owns the mapping. The three agree today only
  because that mapping is the single writer and always emits lowercase. A shared
  status module beside `db/effective_date.py` -- the pattern this phase already
  established for a rule that needs one definition -- would bind the vocabulary and
  the predicate the sweep and `COMMITTED_STATUSES` both read. Note the review's
  other suggestion, moving `COMMITTED_STATUSES` into `domain/`, was rejected:
  ADR-0001 scopes that module to bands over primitives with no ORM, and these are
  stored status strings used inside SQL.
* **Dropping `func.lower` would restore the `transactions.status` index** and remove
  the case discrepancy above. Pre-existing, and `AGENTS.md` ranks performance last.
* **One fold, one scan.** `_get_monthly_spend` and `_get_budget_category_spend`
  each turn status-grouped rows into a `SpendByStatus` in their own way, and run two
  aggregate scans over the same table and window. `/simplify` territory.
