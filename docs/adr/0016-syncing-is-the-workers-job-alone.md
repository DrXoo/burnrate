# Syncing is the worker's job alone

There is no way for a person to ask BurnRate to sync. The `POST
/integrations/enable-banking/connections/{id}/sync` endpoint, both Sync buttons and the
client code behind them are gone. In their place `/summary` publishes `next_sync_at`,
and the health strip reads **`Synced 3 h ago · next at 21:00`**.

## Why: the button could not do what it implied

Not a judgement about clutter — a measurement. **Neither of this owner's banks has ever
returned a pending transaction**: all 649 stored rows carry `status: BOOK` as the bank
set it. A booked row takes one to three days to appear. So "Sync now" could never show
the owner what they had just spent, which is the only thing a person presses that button
hoping for.

It also lost the competition it was in. BurnRate does not send the PSU-presence headers
that would mark a request as attended, so **every call it makes is unattended whoever
triggered it** — a manual sync spent accesses out of the four-per-day budget
(ADR-0015) that the scheduled passes need, and then failed unpredictably once they were
gone. At Openbank, the one bank here that enforces the budget, there is no attended path
to escape it: the headers are declared by ING, which does not enforce, and not declared
by Openbank, which does. Crossed exactly the wrong way, which is why that option was
rejected before this one was taken.

## Why the backend publishes the schedule

Removing the button removes an answer as well as an action. Nothing else on screen said
when data refreshes — `ReviewPage` still says "after the next sync" without saying when
that is — and that was survivable only while the answer was "whenever you press the
button".

So the next pass is published as a field, computed from `SYNC_CRON` resolved through
`APP_TIMEZONE`. A client parsing the cron would be deriving a system fact, which is
ADR-0002's rule, and it could not resolve the zone anyway. `sync_schedule.py` builds the
trigger for both readers — the worker fires on it, `/summary` reports it — so the hour
on screen and the hour the worker intends cannot drift apart. The instant carries its
offset and the interface reads the hour straight out of it rather than through `Date`,
because converting would re-render it in whatever zone the browser sits in and show an
hour nobody configured.

## The trap: it is an intention, not a promise

**"Next at 21:00" is a lie if the worker is down**, and a worker that is not running
cannot say so — the whole premise of ADR-0013. Printing a confident hour during an
outage is worse than printing nothing: it is the product reassuring the owner at exactly
the moment it should not.

So the line is shown **only in the `Healthy` tone**. In `Needs attention` and `Inactive`
it is suppressed, because what the owner needs then is the error or the reconnection,
not a schedule that is not being honoured.

That is cheap and honest and **not complete**. A worker that dies *between* successful
passes leaves the strip `Healthy` with a next-sync hour that will not arrive, until the
sync-gap alert notices days later. That is the dead-man's switch ADR-0013 records as
deliberately not built; this decision inherits the hole rather than widening it.

## What this costs

**The owner loses the agency**, and nothing replaces it. After reconnecting a bank the
initial import in `handle_callback` still runs, so connecting produces data immediately
— that is the one case where pressing something used to matter and still works.

**The operator loses the escape hatch.** There is no longer any way to force a fetch:
restarting the worker reports a sync gap at startup but does not sync, so verifying a
fix means waiting for 12:00 or 21:00. No CLI entry point was added, because the only
person who would use it can also edit `SYNC_CRON`, and an unattended-by-definition
access is just as expensive from a shell as from a button.

## Consequences

**`_bank_error`'s rate-limit carve-out survives and changed audience.** It now serves
listing a country's banks and starting an authorization — both attended, the owner
reading the message as it happens — so the client-side `bankRateLimitMessage` moved
from the sync toast into `ConnectBankModal`. Without that move ticket 03's work would
have been half dead code.

**The fake is strict rather than absent.** `web/tests/fakeApi.ts` still exports
`syncEnableBankingConnection`, and it records the attempt and throws. A re-added client
call therefore shows up in `syncRequests()` instead of quietly working against a
tolerant double.

**`/sync` is dropped from the planned Telegram commands** in `docs/product/mvp.md`. It
was never implemented, and it is now a command that must not exist.

## What would change this decision

* **Measuring the PSU-presence headers on the bank that enforces.** If an attended
  request is genuinely outside the budget at Openbank, a manual sync costs nothing that
  the scheduled passes need, and the agency can come back — see the rejected ticket 04
  for why the declared headers do not currently support that.
* **A bank that actually returns pending transactions.** The premise here is that
  nothing a sync could fetch reflects today's spending. A bank that reported holds would
  make the button able to do what it implies.
