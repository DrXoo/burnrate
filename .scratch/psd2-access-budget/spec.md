# Living inside the PSD2 access budget

## The problem, as measured on 2026-11-03

Openbank started refusing syncs within an hour of being connected:

```
[HUB046] Allowed number of accesses exceeded for consent
error_name: RateLimitException   error: ASPSP_RATE_LIMIT_EXCEEDED
```

The owner read this as Openbank being stingy next to ING, which had served 37
syncs the same day. It is the opposite. ING is not more generous, it is simply not
enforcing the limit, and the day it starts we get the same wall. Openbank is the bank
behaving normally.

## What the limit actually is, and what is not known

**The number is solid.** RTS Article 36(5)(b) (Commission Delegated Regulation (EU)
2018/389), as confirmed in EBA Q&A 2019_4631: where the PSU "does not actively request
such information", an AISP may access it "no more than four times in a 24-hour period",
"unless a higher frequency is agreed between the AISP and the ASPSP, with the PSU's
consent". A PSU-present access is outside the budget by construction — that is the
clause the whole rule turns on, and it is what ticket 04 rests on.

**The scope of the counter is unsettled, and the first draft of this spec asserted it
as fact.** That claim — "four per account per day" — was wrong to state flatly. The EBA
Q&A does not say whether the four are counted per consent, per account, or per account
and request type. Published readings differ and ASPSPs implement it differently.

What this owner's own data says, which is better evidence than a reading:

| Scoping | Predicts | Observed |
|---|---|---|
| 4 per consent | the first sync fails (it cost 7 accesses) | first sync succeeded — **excluded** |
| 4 per account | the second sync fails (3 accesses each) | second sync succeeded — **excluded** |
| 4 per account per request type | the third sync fails (`/transactions` reaches 6) | third sync failed — **fits** |

Openbank on 2026-11-03: 17:25 succeeded, 17:30 succeeded, 18:00 failed, and by 19:30 it
was `/balances` being refused — which the third row also predicts, since `/balances`
reaches its own fifth access about then.

So the two strict readings are empirically excluded for this bank and the generous one
fits exactly. **One bank, one evening, n=1** — a hypothesis that happens to fit, not a
settled fact, and the next bank may count differently.

**Two caveats worth keeping.** The Q&A's final date is 2021-03-05 and the EBA states it
does not systematically review Q&As after legislative amendments, so this is the rule as
read in 2021. And whether Enable Banking treats PSU headers as exempting a request from
the background limit is so far community-reported, not found in their own reference.

**The conclusion that matters is robust to all of it.** Two scheduled runs a day is safe
under every scoping our own data has not already excluded, and under the one that fits
it leaves half the budget unused. Nothing below depends on resolving the question — and
the question is answerable by measurement rather than by reading, which is cheaper and
is what this repo prefers anyway.

The budget is being spent roughly three times over:

| Per account, per sync | Accesses | Earns its place? |
|---|---|---|
| `GET /accounts/{id}/balances` | 1 | yes |
| `GET /accounts/{id}/transactions` (booked) | 1 | yes |
| `GET /accounts/{id}/transactions?transaction_status=PDNG` | 1 | **no — has never returned a row** |

Three of four accesses in a single pass, on a schedule of `*/30 * * * *`, i.e. 48
passes a day against a budget of four.

And a 429 costs four accesses rather than one, because `RETRYABLE_STATUS_CODES`
in `integrations/enable_banking/client.py` includes it. A rate limit is retried
three times with 0.5s, 1s and 2s of backoff — against a budget measured in days.
It cannot succeed, and it quadruples the overspend that caused it.

## Evidence that the pending call returns nothing

Every one of the 649 transactions in the live database carries `status: BOOK` as
set by the bank:

```
  banco   | status_banco | nuestro | count
----------+--------------+---------+-------
 ING      | BOOK         | booked  |   624
 Openbank | BOOK         | booked  |    25
```

Five months of ING at a 30-minute cadence, and a hold lives one to three days, so
a pending row would have had hundreds of chances to be caught mid-flight.

**The honest limit of that evidence:** the fetch-scoped sweep deletes a pending row
once it books, so the table is a snapshot and not a history. Nothing recorded the
pending responses at the time. The claim is therefore "both of this owner's banks
behave as if they do not serve pending over open banking", which is strong but is
not the same as "no bank does" — which is why ADR-0003 is amended rather than
reversed, and why the pending *machinery* stays.

## What has already been done

`SYNC_CRON` moved from `*/30 * * * *` to `0 11,20 * * *` in `.env` and the worker
was restarted, confirmed at 19:53 UTC. Expressed in UTC because `APP_TIMEZONE` is
unset and therefore UTC; these land at 12:00 and 21:00 Europe/Madrid in winter and
an hour later under CEST, which does not matter at this cadence.

Not bundled here, deliberately: setting `APP_TIMEZONE=Europe/Madrid` would make the
cron mean local time year-round, but it also moves every civil date the product
derives — the month boundary and what "today" means in Safe to Spend Today. That is
a product decision, not a scheduling convenience, and belongs in its own change.

## Where that leaves the arithmetic

With the `PDNG` call gone, a sync costs **2 accesses per account**: one `/balances`
and one `/transactions`.

Under the scoping that fits the measurements that is one access per counter per run, so
four runs a day would fit and the two we schedule leave half the budget unused. Under
the stricter per-account reading — which this owner's data excludes but another bank
may not — it is two per run, and two runs spend the lot exactly.

Two runs a day is therefore right for a different reason than the first draft of this
spec claimed: not because it is exactly the budget, but because it is the largest
cadence that is safe under **every** reading still standing. The product's figures are
all daily, so a third run would buy nothing to offset the risk.

The manual sync button is the genuinely tight part, and it is why ticket 04 is not a
nice-to-have. Under the strict reading the schedule commits the whole budget and the
button cannot succeed at all; under the generous one it competes for whatever is left
and fails unpredictably, which is harder to diagnose. An owner-initiated sync is an
*attended* access and sits outside the budget — but only if the request says so, and
the client currently sends `psu_type` without any PSU-presence headers.

## Scope

1. `01` — a rate limit is not a retryable error
2. `02` — stop asking for pending transactions, and amend ADR-0003
3. `03` — a rate limit reaches the owner as itself, not as a 502
4. `04` — an owner-initiated sync is an attended access

## Out of scope

- Measuring the real budget. Worth doing, deliberately not blocking this work:
  counting accesses per sync and recording where the wall actually falls would settle
  the scoping question per bank by observation. Cheaper than reading it, and the only
  method that stays correct when a bank changes its mind.
- Per-bank sync coverage reporting (the gap alert is day-granular and needs no
  recalibration for this cadence — `SYNC_GAP_GRACE_DAYS` is 7 days, the fetch
  window is 30)
- `APP_TIMEZONE`
- Excluding the second Openbank account. It reads €0.00 with 0 transactions today,
  but the owner states it is about to become the new savings account, so excluding
  it would have to be undone within the week.

## Implementation Decisions

**The pending machinery stays; only the dedicated call goes.** `_extract_transactions`
merges a response's `pending` array whichever call produced it, and `SCHD` normalizes
to pending, so a bank that volunteers a held or scheduled transaction on the booked
call still reaches `counted_spend` and the sweep with ADR-0003's rules intact. What
is removed is one HTTP request that has never contributed a row — not the concept.

**No `ENABLE_BANKING_FETCH_PENDING` flag.** A boolean that changes how much of a
regulated budget each sync spends is exactly the "unclear boolean flag" AGENTS.md
warns about, and with two banks there is no second use case to justify the seam.
Re-adding the call is a handful of lines guarded by the amended ADR.

## Testing Decisions

The fake bank client is the hazard here, and AGENTS.md names this failure mode
directly: a double that answers a question the code never asked cannot disagree
with it. The current fake returns its payload whatever was requested, so it cannot
observe *which* calls a sync makes — and "which calls a sync makes" is the entire
subject of this feature.

So the first test to write is a **strict recording double**: one that records every
`(method, path, params)` it is asked for, and whose assertion is the access count
and the absence of a `transaction_status=PDNG` request. A test that only checks the
imported rows would pass before and after ticket 02 and prove nothing.

For ticket 01, the double must be strict about *sequence*: it has to be able to say
"this path was requested four times" and fail. A double that returns an error
without counting makes a retry loop unobservable, which is how this bug survived.
