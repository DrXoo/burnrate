# 10: Align the sync windows, and keep a hold's status honest

**What to build:** Four defects, three in the pending machinery and one in the
fixed figures, found by `/code-review` on tickets 05 and 06 and verified against
the code. The first three quietly lose or invent committed spend, and ticket 05
is what gave them teeth: before pending counted, every one of them was invisible
in the figures. The fourth is unreachable today and is defence in depth.

**Blocked by:** None (05 is done; this does not block 06-09)

**Status:** done

- [x] The booked re-import window covers at least the pending sweep window, so a hold that books after a month boundary is re-imported instead of lost
- [x] A pending row whose Effective Date is in the future can be swept once the bank stops reporting it
- [x] A row that arrives in a response's `pending` array with no status of its own is stored as pending, not as booked
- [x] Each case carries its own test at seam 3 (the sync entry point with a fake client), and each is mutation-checked
- [x] The fixed figures are derived per budget *category*, so a category with two budget rows in one month cannot have its commitment counted twice
- [x] `docs/technical/bank-integrations/enable-banking.md` records the window relationship as a constraint rather than two independent numbers

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

---

## Comments

**The existing fakes answered questions the service never asked, which is why
three passes could find defect 1 by reading and none by running.**
`PendingTransactionsClient` and its subclasses return their payloads whatever
window the service requested, so a fetch window too narrow to re-ask for a settled
charge was unobservable through them: the service could forget to ask and still be
handed the answer. `WindowedTransactionsClient` answers the window and nothing
else, and is what makes the January-to-February test fail against the old code.

**`EnableBankingService` now takes an injectable `clock`, matching
`SummaryService`.** The defect is only reachable when the sweep window reaches into
the previous month, which is every day except the 31st -- on the 31st the two
windows coincide exactly. A date-relative test would therefore have been a test
that quietly skips itself once a month, so the month boundary is pinned instead:
31 January and 1 February, as the ticket describes it.

**The three windows are one derived value, not two kept in step.** `_TRANSACTION_WINDOW`
is read by the booked fetch, the pending fetch and the sweep, so the covering
relationship cannot be broken by editing one number. The two existing tests that
asserted the booked window began on the first of the month were asserting the
defect; they now assert the relationship (`booked.date_from <= pending.date_from`,
`booked.date_to >= pending.date_to`), which survives the window length changing.

**Defect 2's upper bound was removed rather than extended.** Any finite upper bound
is a guess about how far ahead a bank will report a scheduled payment. The lower
bound is the one that carries meaning -- it marks the days the bank was actually
asked about.

**Defect 3 is carried as `ReportedTransaction(payload, default_status)`.** Copying a
defaulted status into the payload dict was the smaller diff but would have written
an invented status into `raw_payload`, which exists to record what the bank
actually said. The flat-`transactions`-list shape still defaults to booked: there
is no array there to imply anything.

**Defect 4's fold also fixes the same bug in the variable slice, and needed one
decision.** Folding in `_get_active_budgets` rather than at the three call sites
means `budget_usage` prints one row per category for variable categories too, which
had the same double-print. The decision the fold forces: a category with one fixed
row and one variable row in a month counts as fixed. Reading the flag off whichever
row sorts first would hand that to SQL ordering, and `any` matches what the spend
side has always done (`fixed_category_ids` was already `any`). Mutation-checking
caught that branch untested -- both rows in the ticket's scenario are fixed, so
last-row-wins survived -- and
`..._keeps_a_category_fixed_when_only_one_of_its_rows_says_so` now pins it.

**Six mutants, each caught by the test that should catch it:** booked window
narrowed back to the current month (the boundary test, plus both window-constraint
assertions); sweep lower bound dropped (the 45-day-old hold test); status default
back to `booked` (the array test); estimates not summed, no fold at all, and
`is_fixed` read off the last row (the three summary tests).

**Doc drift fixed in passing:** the sweep's safety list in
`docs/technical/bank-integrations/enable-banking.md` said "Three constraints" above
five bullets. ADR-0003's "self-healing on the next sync" now carries the constraint
it depends on, rather than the assumption that was false when written.

---

## What `/code-review` found afterwards

Thirteen findings. Three were real gaps in this ticket's own work and were fixed
here, red test first and each mutation-checked; one was a serious pre-existing bug
this ticket's window change widens, and is now **ticket 12**; one belongs to
**ticket 11**; two do not survive checking. The reviewer could not execute anything
in its environment, so every finding was re-checked by running it.

**Fixed here — the flat shape bypassed defect 3's fix.** A `PDNG` call answering with
one flat `transactions` list has no array to imply a status, and the extractor
defaulted those rows to booked even though the *request* had just said PDNG. Same
failure as defect 3, left open by the same change that fixed it. The requested status
now flows into `_extract_transactions` and through the same vocabulary mapping, so a
bank using the flat shape *and* marking status by response stores its holds as
pending. The array branches deliberately ignore it: an explicit array is better
evidence than the request.

**Fixed here — status codes were matched case-sensitively.** Pre-existing, but this
ticket changed what a miss costs: a lower-case `pdng` in the booked array reads as
settled money. Matched with `.upper()` now. Note the review's severity reasoning on
this one is backwards — before defect 3's fix a `cncl` fell back to `booked`
(a permanent phantom, invisible to the sweep); afterwards it falls back to the array,
so `pending` and sweepable. The fix got better, not worse.

**Fixed here — the clock seam was only half wired.** `imported_at` still read the wall
clock, and that is the last leg of the Effective Date chain: for a row the bank dated
not at all it is the whole of its month membership. It now comes from the injected
clock. The sync and expiry instants deliberately stay on the real clock, because
"when did this process run" has to be true even under a pinned one.

**Fixed here — the window rationale was written out three times.** `AGENTS.md` says
to prefer changing existing docs over duplicating explanations. The constraint stays
stated in all three places that need it; the narrative (the 31 January case, the
idempotence argument) now lives once, in `enable-banking.md`.

**Became ticket 12 — an Ignored transaction gets its category back on the next sync.**
Reproduced end to end: `spend=15.99` → Ignored → `spend=0.00` → re-sync →
`spend=15.99`, with `excluded_at` still set, so the ledger and the unknown queue show
nothing while the money is back in the allowance. `apply_rule_to_transaction` guards
on `category_id is None` and never reads `excluded_at`, and the spend queries rely on
a NULL category dropping the row from a join rather than stating the exclusion. The
review frames this as widened by the window change; it is, by about a month of
history, but it already fired on the next sync for anything excluded in the current
month. Pre-existing and reachable, so its own ticket rather than a ride-along.

**Became defect 3 of ticket 11 — the future-month caption.** "Nothing is spent yet" is
hard-coded for the future-month branch, and a `SCHD` row dated in a future month puts
spend in that month, so the caption can contradict the figure above it. Same family as
that ticket's other two, and the only one of the three reachable in the live config.

**Rejected — the sweep's missing upper bound is not the same defect mirrored.** The
review argues a future-dated hold can be deleted outside the window the bank was
asked about and never recover. The row only exists because the bank reported it
outside that window in the first place, so the pending call is exactly what brings it
back: the failure mode is oscillation (a lost category, a re-announced row), not the
permanent loss the finding claims, and the alternative it implies leaves a phantom
counting as spend for ever. The trade-off stands as the ticket argued it. The residual
oscillation risk is worth writing down if a real bank ever shows the behaviour.

**Rejected — mixed currencies in the per-category fold.** True, and pre-existing in
kind: `monthly_budget` has summed amounts across categories without checking currency
since long before this change, so the fold introduces nothing new. Summing the
estimates is this ticket's documented decision, in a state `BudgetService` cannot
produce.

**Left as backlog.** A single `_response_arrays` decoder to replace the three
hand-mirrored shape branches is the best quality idea in the review and would have
subsumed the flat-shape fix properly — but it touches the sweep's safety gate, so it
is a deliberate refactor, not a ride-along. `get_summary`'s length and the per-row
`SELECT` + `RulesService` churn are both pre-existing and already named in this
ticket's quality section. The Telegram `None` rendering is defensive only: both
null-amount statuses are handled before the icon lookup. One small confirmed
cosmetic: `_summarize_transactions_payload` logs `booked_count: 0, pending_count: 0`
for the flat shape, where `transactions_count` carries the real number.
