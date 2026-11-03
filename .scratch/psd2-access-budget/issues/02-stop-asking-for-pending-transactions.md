# 02 — Stop asking for pending transactions

Status: done
Blocked by: 01

## Why

`_import_account_transactions` (`services/enable_banking_service.py:552`) makes two
transaction calls per account, booked and `transaction_status=PDNG`. The `PDNG` call
has never returned a row from either of this owner's banks: all 649 stored
transactions carry `status: BOOK` as set by the bank.

It costs a third of the per-account unattended access budget per sync. See the spec
for the arithmetic and for the honest limits of that evidence.

## Behaviour wanted

One transaction call per account, for booked. Everything downstream of the import —
the `pending` status, `counted_spend`, the effective-date chain, the stale-pending
sweep — stays exactly as ADR-0003 defines it, because a bank that volunteers a held
or scheduled row on the booked call must still be handled correctly.

## The subtlety that will bite

The sweep is currently gated on `booked.readable and pending.readable`, and fed
`booked.external_ids | pending.external_ids`.

With no pending fetch it gates on the booked fetch alone. **That is correct, and it
is not the narrowing the sweep's docstring warns against** — that warning is about
feeding the sweep *only* the pending response, which would delete a standing order
the booked call had just reported. Booked-only is safe for the opposite reason:
`_extract_transactions` merges a response's `pending` array whichever call produced
it, so any pending row the bank volunteers is inside `booked.external_ids`.

Read that docstring before touching the gate, and leave a note in it saying which
fetch now feeds it, or the next reader will re-add the call to "fix" the sweep.

## Acceptance criteria

- A sync of one account makes exactly one `GET /accounts/{id}/transactions` request,
  with no `transaction_status` parameter.
- A booked response that carries a `pending` array still produces a row with status
  `pending`, and that row still reaches `counted_spend`.
- The sweep still deletes a pending row the bank has stopped reporting, and still
  leaves an Ignored row alone.
- The sweep does **not** run when the booked fetch was incomplete or unreadable.
- `pending_spend_amount` is still computed and still serialized. It will read 0.00
  against these banks; the field is not removed.

## Docs

- Amend `docs/adr/0003-pending-spend-is-load-bearing.md`. It opens with "Pending
  transactions were already imported — a dedicated `PDNG` fetch" and that sentence
  stops being true. The amendment records the measurement, keeps the reasoning
  (a booking lag errs toward overspending, which is the failure the product exists
  to prevent), and states that the rules survive while the dedicated request does
  not. Do not mark it superseded: nothing about the metric changed.
- `docs/technical/bank-integrations/enable-banking.md` — the window section
  discusses both fetches sharing one window.

## Comments

**2026-11-03 — done.** Red first: `assert len(client.transaction_requests) == 1`
failed at 2, with the captured log showing the wasted call —
`status=PDNG ... imported=0`.

### The fakes were the work

Removing the call broke **18 tests**, and almost none of them were about the call.
They were fixtures that served pending rows *only* on the `PDNG` branch, which is the
hazard the spec predicted: a double that encodes the implementation's assumption
cannot observe the implementation changing.

Fixing one double — `PendingTransactionsClient`, to return both arrays in one response
the way a bank volunteering a hold actually does — cleared **12 of the 18** on its own.
The rest were the same defect in four more doubles plus two window assertions
expressed as a *relation between the two calls* (`booked.date_from <=
pending.date_from`), which has no meaning with one call and is now stated directly.

### Mutations

| Mutation | Killed by |
|---|---|
| sweep gate removed (`if booked.readable` → `if True`) | 2 tests |
| sweep fed no ids (`booked.external_ids` → `set()`) | 4 tests |

Both rules I touched have teeth.

### What it cost

One behaviour, asserted rather than left to be rediscovered. In the flat payload shape
an unmarked row used to fall back to the status the call had *asked* for; with no
`PDNG` request it falls back to settled. A bank using the flat shape **and** marking
status by response would have its holds read as money already spent.

Priced and accepted: no such bank is in play, and the budget the call spent was being
exhausted twice a day for real. `requested_status` is kept intact so restoring the call
restores the behaviour, and
`test_a_flat_unmarked_row_now_reads_as_settled_and_that_is_a_real_loss` names the cost
in its own title.

Docs: ADR-0003 amended (not superseded — nothing about the metric changed), ADR-0015
gained the consequence, and the integration doc's "One Fetch Window, Shared" became
"One Fetch Window, One Call".

Suite: 549 passed.
