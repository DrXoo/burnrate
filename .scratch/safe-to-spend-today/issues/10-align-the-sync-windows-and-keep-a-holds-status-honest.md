# 10: Align the sync windows, and keep a hold's status honest

**What to build:** Three defects in the pending machinery, found by `/code-review`
on ticket 05 and verified against the code. Each one quietly loses or invents
committed spend, and ticket 05 is what gave them teeth: before pending counted,
every one of them was invisible in the figures.

**Blocked by:** None (05 is done; this does not block 06-09)

**Status:** ready-for-agent

- [ ] The booked re-import window covers at least the pending sweep window, so a hold that books after a month boundary is re-imported instead of lost
- [ ] A pending row whose Effective Date is in the future can be swept once the bank stops reporting it
- [ ] A row that arrives in a response's `pending` array with no status of its own is stored as pending, not as booked
- [ ] Each case carries its own test at seam 3 (the sync entry point with a fake client), and each is mutation-checked
- [ ] `docs/technical/bank-integrations/enable-banking.md` records the window relationship as a constraint rather than two independent numbers

## The three defects

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
