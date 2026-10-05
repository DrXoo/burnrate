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
