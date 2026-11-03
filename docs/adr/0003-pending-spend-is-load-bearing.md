# Pending spend counts, in the variable slice only

Pending transactions were already imported — `enable_banking_service.py` runs a
dedicated `PDNG` fetch over a 30-day trailing window — but every spend query in
`SummaryService` filtered `status == "booked"`, so they reached no metric. For a
figure whose entire promise is *today*, a one-to-three-day booking lag errs in
the direction that causes overspending, which is the failure the product exists
to prevent. Pending spend therefore counts as spend in the variable slice.

Three supporting decisions make that safe, and each will look like a bug without
this note.

**Month membership resolves booking date, then value date, then import date.**
`booking_date` is nullable and a pending transaction often has none, and
`NULL >= month_start` is never true in SQL — so pending rows were invisible to
the month window *regardless* of the status filter. One shared helper resolves
the effective date for all four queries. `booking_date` stays first in the
chain, so every existing booked figure is unchanged to the cent; the fallback
only fires on rows that are invisible today. A non-nullable `effective_date`
column is the better end state, but it needs a migration and a backfill, which
is more than this phase should spend.

**A fetch-scoped sweep deletes stale pending rows.** After a fully successful
pending fetch for an account — all pages — pending rows inside the fetched
window whose external id was absent from the response are deleted. This is not
housekeeping: the dedup key falls back to a sha256 that includes `booking_date`,
which a pending row lacks, so a transaction that books under a different hash
would be counted twice. The sweep handles that for free, because once something
books it stops appearing in the pending response. Gating on a complete fetch
stops a mid-pagination failure sweeping live rows, and deletion is safe because
the 30-day trailing window makes the loss self-healing on the next sync.
`excluded_at` is deliberately not reused: it means the owner deliberately
excluded something (**Ignored** in `GLOSSARY.md`), and a phantom is not a
decision the owner made.

That self-healing clause is load-bearing, and it was not true when this was
written: the booked fetch was the narrower window, so a hold that booked across a
month boundary was deleted and never re-imported. Both fetches and the sweep now
share one trailing window. See
`docs/technical/bank-integrations/enable-banking.md` for the constraint and the
case that proved it.

**The fixed slice stays booked-only.** `_project_fixed` trusts actual spend over
the budgeted estimate as soon as `spent > 0`, so a 1 EUR pre-authorization on a
utility would make it project a 120 EUR bill as 1 EUR. The fixed overrun from
ADR-0002 has the same exposure: a partial hold would read as an overrun that
does not exist. So pending reaches the allowance and the burn rate, which are
variable by construction, and nothing else.

## Considered Options

Disclosing `pending_spend_amount` without subtracting it was cheaper and carried
no double-count risk, but it hands the owner a subtraction to do, and Phase 8's
Definition of Done requires an answer *without arithmetic*. Staying booked-only
and recording a known gap was rejected because the gap would sit in the headline
metric — the same shape of omission as the Phase 3 runway.

## Consequences

The asymmetry is deliberate and should not be tidied into consistency: a fixed
commitment is judged by its estimate until it settles, while everything else
counts pending. `AGENTS.md`'s rule that pending and booked cannot be treated
identically in all calculations is doing real work here.

The sweep also removes phantoms from the unknown queue, which
`_count_uncategorized_transactions` shows today because it never filtered on
status.

---

## Amendment, 2026-11-03: the dedicated `PDNG` fetch is gone; the rules are not

This ADR opens with "Pending transactions were already imported — a dedicated `PDNG`
fetch over a 30-day trailing window". **That request no longer exists.** Everything
else here stands unchanged: pending spend still counts in the variable slice, the
effective-date chain still resolves month membership, the sweep still runs, and the
fixed slice is still booked-only.

### What was measured

The `PDNG` call cost a third of the per-account access budget PSD2 grants for
unattended access, and it has never returned a row. All 649 transactions in the live
database carry `status: BOOK` as set by the bank:

```
  banco   | status_banco | nuestro | count
----------+--------------+---------+-------
 ING      | BOOK         | booked  |   624
 Openbank | BOOK         | booked  |    25
```

Five months of ING at a 30-minute cadence, and a hold lives one to three days, so a
pending row would have had hundreds of chances to be caught mid-flight.

**The honest limit of that evidence:** the fetch-scoped sweep deletes a pending row
once it books, so the table is a snapshot and not a history, and nothing recorded the
pending responses at the time. The claim is "both of this owner's banks behave as if
they do not serve pending over open banking", which is strong but is narrower than
"no bank does". That is why this is an amendment and not a reversal. ADR-0015 holds
the budget this was traded against.

### Why the machinery stays

`_extract_transactions` merges a response's `pending` array whichever call produced
it, and `SCHD` normalizes to pending. So a bank that volunteers a held or scheduled
row on the ordinary call still reaches `counted_spend` and the sweep with every rule
above intact. What was removed is one HTTP request that never contributed anything,
not the concept — and `pending_spend_amount` is still computed and still published.
It reads 0.00 against these banks, which is a true answer rather than a missing one.

### The sweep now judges the booked fetch alone

It was gated on both fetches being readable and fed the union of their ids. It is now
gated on the one fetch and fed its ids.

**That is not the narrowing this ADR's sweep docstring warns against.** That warning
is about feeding the sweep *only* the pending response, which would delete a standing
order the booked call had just reported — the row would oscillate, losing its category
every other sync. Booked-only is safe for the opposite reason: the pending array of
that same response is inside `booked.external_ids`.

### What this cost, stated rather than left implicit

In the flat payload shape there is no array to imply a status, so the fall-back was
whatever the call had asked for — and a `PDNG` request was the bank's own context for
its answer. With no such request, `requested_status` is always `None` and the fall-back
is "settled".

For a bank that uses the flat shape **and** marks status by response rather than per
row, every hold now reads as money already spent: it under-reports pending spend, feeds
the fixed-step projection a partial authorization, and stays invisible to the sweep for
ever. No such bank is in play — neither of the owner's two has ever reported a pending
row — while the budget the call spent was being exhausted twice a day for real. The
inference mechanism is kept intact behind `requested_status`, so restoring the call
restores the behaviour, and
`test_a_flat_unmarked_row_now_reads_as_settled_and_that_is_a_real_loss` asserts the
cost rather than leaving it to be rediscovered.

### What would bring the call back

A bank that reports holds only on a `PDNG` request. The way to find out is to make the
call once for a new bank and look, not to make it twice a day for every bank for ever.
