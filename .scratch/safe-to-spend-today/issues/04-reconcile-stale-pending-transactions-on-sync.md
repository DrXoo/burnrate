# 04: Reconcile stale Pending transactions on sync

**What to build:** Phantom Pending transactions stop accumulating. A hold that
disappears at the bank disappears here, and a Pending transaction that later
books does not leave a twin behind to be counted a second time. The owner sees a
transactions list and a review queue that shed clutter they never created.

This has to land before Pending spend counts toward anything, or the first
re-sync can double-count a single purchase.

**Blocked by:** 03

**Status:** done

- [x] After a fully successful Pending fetch for an account, Pending rows inside the fetched window whose provider identifier was absent from the response are deleted
- [x] A Pending row still present in the response survives untouched
- [x] A Pending transaction that books under a different provider identifier leaves no twin behind
- [x] A fetch that fails partway through any page sweeps nothing
- [x] A Pending row the owner marked Ignored is never swept
- [x] Both payload shapes are covered: a stable provider transaction identifier present, and absent so the fallback hash is used
- [x] The Ignored flag is not reused as a marker for swept rows

## Comments

**The sweep lives after the whole pending fetch, not per page.** `tdd` built this
in two steps: delete every pending row in the window (which passed the first
test), then compare against the identifiers the response actually reported (which
the second test forced). The placement is the load-bearing part. A per-page sweep
passes the vanished-hold and surviving-hold tests and still loses live data, so
`test_a_pending_fetch_that_fails_mid_pagination_sweeps_nothing` seeds two holds
and truncates the response after the first — a per-page implementation deletes
hold-2, which was on the page that never arrived.

**The partial-sweep risk is real because the scheduled run commits anyway.**
`SyncService._sync_one` catches a per-connection failure to isolate it, and
`worker.py` then commits the shared session, so anything a sweep deleted before
the failure would persist. The test mirrors that: it catches the error and
commits before asserting. A test that rolled back instead would have passed
against the broken implementation.

**`_fetch_and_upsert_transactions` now returns `FetchedTransactions` instead of an
int.** The sweep needs the set of identifiers the bank reported, and the fetch
loop is the only place that sees every page. The external id is derived once per
payload there and passed into `_upsert_transaction`, which previously derived it
itself — same hash, computed one fewer time, and the collection cannot drift from
what was stored.

**The window predicate is not decoration.**
`test_the_sweep_leaves_a_pending_hold_older_than_the_fetched_window` covers a hold
dated 45 days back: the pending fetch only asks about a trailing 30 days, so the
bank never mentions it either way and its absence proves nothing. Removing
`resolved >= date_from` fails that test.

**Both payload shapes carry their own test, and they fail for different reasons.**
With a stable `transaction_id` the sweep is belt-and-braces. Without one the
dedup key is a content hash over the booking date, so the booked copy of a
purchase hashes differently from its hold and the sweep is the only thing
preventing a double count — that is
`test_a_pending_hold_that_books_under_a_new_identifier_leaves_no_twin`. The
mirror case matters too: the hash has to be *stable across syncs* for a hold that
is still held, or a bank with no identifier would churn the row and lose its
category on every sync. `test_a_hold_with_no_identifier_survives_resync_on_its_content_hash`
asserts the primary key is unchanged, and it is the only test that fails if the
sweep matches on `transaction_id` alone.

**Three tests passed on arrival, and each was mutation-checked rather than
trusted.** The twin, mid-pagination and out-of-window tests all went green
without new production code, because the mechanism from the first two cycles
already covered them. Each was then re-run against a deliberately broken
implementation (sweep removed, sweep moved per-page, window predicate dropped,
identifier matching narrowed to `transaction_id`) to confirm it can actually
disagree with the code. A test that cannot fail is not coverage.

**`excluded_at` is only ever read here, never written.** The last acceptance
criterion is structural rather than behavioural, so it is worth stating where it
is enforced: the sweep's single reference to `excluded_at` is the
`.is_(None)` filter. A swept row is deleted outright, which is what
`test_sync_deletes_a_pending_hold_the_bank_stopped_reporting` asserts by checking
the row is gone rather than flagged.

**One latent interaction, noted and not fixed.** The sweep's
`enable_banking_transaction_id.not_in(...)` filter cannot match a row whose
identifier is NULL, since `NULL NOT IN (...)` is never true. Nothing creates such
a row today — the bank import is the only writer of `transactions` — so this
changes no behaviour now. If manual transaction entry ever lands, NULL-id rows
will be excluded from the sweep, which is the right default: a row the owner typed
is not the bank's to delete.

**Not done here, by design.** Pending still counts toward no spend figure. Ticket
03 made pending rows visible to the month window, this ticket stops them
accumulating as phantoms, and ticket 05 makes them count. The ordering is the
point: counting pending spend before the sweep existed would let the first
re-sync double-count a single purchase.

**Correction from code review: the sweep compared against the wrong set.** The first
version passed `pending.external_ids` only, which deleted any row the *booked* fetch
had stored with pending status. Confirmed by probe before fixing: a bank returning
`{"status": "SCHD", ...}` in the default call produced `row=present → MISSING →
present → MISSING` across three syncs, with imported counts `[0, 1, 0]`. Every other
scheduled run therefore fired a false "1 new transaction" Telegram alert and reset the
row's `category_id`, `matched_rule_id` and `imported_at`.

Two things in existing code make a pending row arrive outside the `PDNG` call, and
both were visible in the code this ticket read: `_normalize_transaction_status` maps
`SCHD` to pending, and `_extract_transactions` merges a response's `pending` array
whichever call produced it. The fix passes `booked.external_ids | pending.external_ids`,
because the real invariant is *the bank did not mention this row anywhere in this sync*,
not *the pending call did not list it*. The union does not weaken the twin case: a hold
that books is reported under its new identifier, so the stale row's old hash is still in
neither set — `test_a_pending_hold_that_books_under_a_new_identifier_leaves_no_twin`
still passes. It also strengthens the failure gating, since both fetches must now
complete before anything is swept.

**Why the original seven tests missed it.** `PendingTransactionsClient` only ever put
pending payloads in the `PDNG` response, so the test double encoded the same assumption
as the implementation — the fake agreed with the code about where pending rows come
from, and no amount of mutation testing finds a case the double cannot express. The
regression test uses a client whose *booked* call carries the pending array
(`test_the_sweep_leaves_a_scheduled_payment_the_booked_fetch_reported`) and asserts the
row's primary key is unchanged across two syncs, which catches the oscillation rather
than just the deletion.

**Lower-priority review items closed in the same pass.** None changes this ticket's
behaviour; they are recorded here because this is where the review ran.

* The sweep's `not_in` now sits beside an explicit
  `enable_banking_transaction_id.is_not(None)`. Behaviourally a no-op — `NULL NOT IN
  (...)` already never matched — but the exclusion was happening by accident of
  three-valued logic rather than by a stated predicate.
* `month_window()` moved next to `within_month` in `db/effective_date.py`, replacing
  `SummaryService._parse_month` + `_resolve_month`'s inline rollover and
  `LedgerService._parse_month`. The module existed so "the boundary convention is
  decided here once", and the December rollover was still written twice. It was also
  tested **zero** times: `test_summary_service_closes_december_on_the_first_of_january`
  now covers it at the agreed summary-service seam rather than opening a new seam for
  the helper, and it fails if the rollover drops the `year + 1`.
* `TransactionFilters` carries one `month: tuple[date, date] | None` instead of two
  independent bounds, so a half-specified window is unrepresentable rather than
  silently dropping the filter and scanning all history.
* `send_sync_notification`'s docstring claimed "It never raises" while
  `civil_date` rejects a naive `now`. Fixed as a contract statement, not a
  normalisation: assuming UTC for a naive instant is exactly the bug `civil_date`'s
  guard exists to prevent, and no production caller passes `now` at all — the worker
  passes nothing and only tests set it. The other two `now`-taking functions in that
  module never reach `civil_date`, so the review's claim that they share the exposure
  does not hold.
* The `effective_date` import-date leg is now documented as the one civil date not
  resolved through `APP_TIMEZONE`, with the concrete divergence spelled out. Not
  fixed: the real fix is the stored `effective_date` column the spec deferred for
  needing a migration and a backfill.
