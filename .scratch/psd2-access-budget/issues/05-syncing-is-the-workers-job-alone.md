# 05 — Syncing is the worker's job alone

Status: done, 2026-11-03
Blocked by: 04 (rejected, which is what makes this the answer)

## Why

The manual sync button **cannot do what it implies**, and that is a measurement rather
than a judgement: neither of this owner's banks has ever returned a pending
transaction — all 649 stored rows carry `status: BOOK` as set by the bank — and a
booked row takes one to three days to appear. So "Sync now" can never show the owner
what they just spent. It promises an immediacy no bank here delivers.

It also loses the competition it is in. At Openbank, the one bank that enforces the
four-per-day budget, there is no attended path to escape it (ticket 04), so a manual
sync spends accesses the scheduled runs need and fails unpredictably once they are
gone.

Removing it makes syncing the sync worker's single responsibility, which is the shape
the rest of the system already assumes.

## What goes

* `POST /integrations/enable-banking/connections/{connection_id}/sync` and
  `ManualSyncResponse`
* the Sync buttons in `HealthStrip` and `SettingsPage`, and `App.syncConnection` /
  `syncOutcome`
* `syncEnableBankingConnection` in `web/src/lib/api.ts` and `syncConnectionAction` in
  `useBurnRateData`

## What stays, and must not be swept up with it

**`EnableBankingService.sync_connection`.** The scheduler calls it. This ticket removes
an entry point, not the capability.

**The initial import on connect.** `handle_callback` imports accounts and transactions,
so connecting a bank still produces data immediately without a button.

**Ticket 03's rate-limit carve-out in `_bank_error`.** It serves three routes, and the
callback is one of them — an initial import can be refused for rate limiting just as a
manual sync could, and the owner is standing right there when it happens.

> **Corrected while implementing.** The callback does *not* reach `_bank_error`: it
> catches `EnableBankingAPIError` itself and redirects to the Web UI with
> `connect=error`. The two routes that do reach it are `GET /aspsps` and
> `POST /auth/start` — still both attended, so the conclusion holds, but the
> client-side half of ticket 03 was about to become dead code. `bankRateLimitMessage`
> moved from the sync toast into `ConnectBankModal`, which is where those two calls
> are made.

## What arrives in its place

Nothing on screen currently says when data refreshes. `ReviewPage` even says "New
unknowns will land here after the next sync" without saying when that is. That is
survivable today only because the answer is "whenever you press the button" — remove
the button and the owner has lost the agency *and* has no information instead.

So the health strip gains the next scheduled sync beside the timestamp it already
shows: **`Synced 3 h ago · next at 21:00`**.

**It comes from the backend, computed, not from a cron the client parses.** The
schedule is `SYNC_CRON` plus `APP_TIMEZONE`, and a client that read either would be
deriving a system fact it has no business knowing — the rule ADR-0002 exists for. The
natural home is `/summary`, beside `sync_gap`: both are system health answered at
request time, which is ADR-0013's shape.

### The trap: it is a promise the backend cannot keep

**"Next at 21:00" is a lie if the worker is down** — and a worker that is not running
cannot say so, which is the whole premise of ADR-0013. Printing a confident next-sync
time during an outage is worse than printing nothing: it is the product reassuring the
owner at exactly the moment it should not.

The health strip already distinguishes `Healthy`, `Needs attention` (driven by
`latest_sync_error_summary`) and `Inactive`. **Show the next sync only in the `Healthy`
tone.** In the other two the line is suppressed, because what the owner needs then is
the reconnect or the error, not a schedule that is not being honoured.

That is cheap and it is honest, but it is not complete, and the gap should be stated
rather than discovered: a worker that died *between* successful syncs leaves the strip
`Healthy` with a next-sync time that will not arrive, until the sync-gap alert notices
days later. That is the dead-man's-switch hole ADR-0013 already records as deliberately
not built, and this ticket does not widen it — it just inherits it.

## Acceptance criteria

- No route, client function or button can trigger a sync; the only caller of
  `sync_connection` is the scheduler.
- Connecting a bank still imports accounts and transactions.
- The health strip shows the next scheduled sync in local time, read from a backend
  field, when the connection is healthy.
- It shows **no** next-sync time when the connection needs attention or is inactive.
- The backend field is derived from the configured schedule, so changing `SYNC_CRON`
  changes what the owner is told, with no second place to update.
- A test fails if the next-sync value is computed in the client.

## Testing notes

The last two criteria are the ones with teeth, and the rest will pass whatever happens.
Derive the field from the same settings the worker builds its trigger from and assert
the pairing — a test that hardcodes "21:00" would pass against a client-side constant
and prove nothing.

For the suppression rule, build the fixture so the schedule and the tone **disagree**:
a connection with an error whose next sync would otherwise be due shortly. If the two
cannot be made to disagree the rule has no test, which is the failure mode AGENTS.md
names.

## Comments

**2026-11-03, implemented.** Backend 561 pass, web 77, `tsc --noEmit` clean.

One pre-existing failure, unrelated and confirmed on `HEAD` before this ticket:
`test_auth.py::test_enable_banking_callback_stays_public` needs
`/run/secrets/enable-banking.pem`, which does not exist on this host. It passes
nowhere, not just here, and was not introduced by this change.

### What the schedule is derived from

`backend/src/burnrate/sync_schedule.py` is new and holds the only
`CronTrigger.from_crontab` in the codebase. `worker.build_scheduler` and
`SummaryService._serialize_next_sync_at` both go through it, so the hour the owner
reads and the hour the worker fires on cannot drift. The pairing is asserted directly
in `test_sync_schedule.py`: the published value is compared against the worker's own
trigger, for four cron/zone combinations, with no literal time anywhere in the test.

### The three mutations, and what each one proved

* **Dropped `sync_cron=settings.sync_cron` from `get_summary_service`** — one test
  failed. The field is optional on the service, so the wiring is exactly where it can
  go missing, and it would fail *silently*: the interface suppresses an absent schedule
  the same way it suppresses an unhealthy one.
* **Dropped the `tone === "good"` guard in `HealthStrip`** — the suppression test
  failed, because its fixture makes the schedule and the tone disagree (a sync due in
  ten minutes, on a connection whose last sync failed).
* **Rewrote `nextSyncLabel` to go through `new Date(...).toISOString()`** — the hour
  test failed. That is the mutation that matters most, because it is the plausible
  implementation: it reads the right field and produces a well-formed `HH:MM` that is
  simply an hour the owner never configured.

### Not done, and deliberately

No CLI entry point replaces the removed endpoint. Named in ADR-0016 rather than left
implicit: verifying a bank fix now means waiting for 12:00 or 21:00, because an access
is unattended whether it comes from a shell or a button, and the only person who would
run it can edit `SYNC_CRON`.
