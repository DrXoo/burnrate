# Two unattended syncs a day, because the bank grants four accesses

`SYNC_CRON` is `0 11,20 * * *` — twice a day. It was `*/30 * * * *`, forty-eight
times a day, from Phase 1 until 2026-11-03.

The cadence is not a performance choice and not a politeness convention. It is a
**regulated budget**, and the old value was outside it by an order of magnitude. This
records what the budget is, what is genuinely known about it, and what would justify
changing the number — because the obvious instinct on reading `0 11,20` is that it is
too conservative.

## The rule

PSD2's RTS, [Article 36(5)(b) of Commission Delegated Regulation (EU) 2018/389][rts],
limits an AIS provider's access to account information **where the payment service
user is not actively requesting it**. [EBA Q&A 2019_4631][qa] states it operatively:
such access is permitted

> no more than four times in a 24-hour period

> unless a higher frequency is agreed between the AISP and the ASPSP, with the PSU's
> consent.

Two clauses in there carry all the weight.

**"Where the PSU does not actively request"** — an access the owner asked for, while
present, is outside the budget entirely. That is not a loophole, it is the distinction
the rule is built on, and it is why sending PSU-presence headers on owner-initiated
syncs is the real fix rather than a trick. Enable Banking exposes those headers, and
the set each bank requires is served per-ASPSP as `required_psu_headers`; BurnRate
sends none today, so **every** request it makes is unattended whoever asked for it.

**"Unless a higher frequency is agreed"** — the ceiling is contractual, between the
AISP (Enable Banking) and the bank. BurnRate is downstream of that agreement and
cannot raise it.

## What is not known, and must not be written down as if it were

**The scope of the counter.** The Q&A does not say whether the four accesses are
counted per consent, per account, or per account and request type. Published readings
differ and banks implement it differently. An earlier draft of this work asserted "four
per account per day" as fact; it was one of three plausible readings.

This owner's own data discriminates between them better than any reading does. Openbank
on 2026-11-03, at a sync cost of 7 accesses — one session check, plus `/balances` and
two `/transactions` calls for each of two accounts:

| Scoping | Predicts | Observed |
|---|---|---|
| four per consent | the **first** sync fails | 17:25 succeeded — excluded |
| four per account | the **second** sync fails | 17:30 succeeded — excluded |
| four per account per request type | the **third** sync fails, `/transactions` reaching 6 | 18:00 failed — fits |

The third row also predicts the detail: by 19:30 it was `/balances` being refused,
which is about when that call reaches its own fifth access.

So the two strict readings are excluded **for this bank** and the generous one fits
exactly. That is one bank on one evening. It is a hypothesis that happens to fit, not a
settled fact, and the next bank may count differently.

**Whether PSU headers exempt a request from the limit in Enable Banking's own
implementation.** The regulation is clear that attended access is outside the budget.
That Enable Banking treats the presence of the headers as the signal for it is, so far,
reported by other integrators rather than found in Enable Banking's own reference.

**How current the reading is.** The Q&A's final date is 2021-03-05, and the EBA states
it does not systematically review Q&As after legislative amendments.

## Why two, specifically

Two is **the largest cadence that is safe under every reading still standing**, and that
is the whole justification. It is deliberately not "exactly the budget": the first draft
of this reasoning claimed that, and it was arithmetic resting on the scoping that the
measurements above exclude.

Under the strict per-account reading, a sync costs 2 accesses per account — one
`/balances`, one `/transactions` — so two runs spend the four exactly. Under the reading
that actually fits, it is one access per counter per run and two runs spend half the
budget. Either way two runs is inside.

A third run would buy nothing to offset the risk, because **every figure this product
reports is daily**. Safe to Spend Today, the month's spending, the budgets, the
baselines: none of them have sub-daily resolution, so a sync at 12:00 and 21:00 Madrid
time leaves no number less correct than a sync every half hour did. What the old cadence
bought was not accuracy. It was 48 chances a day to be refused.

## ING is not a counter-example

ING served 37 syncs on the same day without complaint. That is ING choosing not to
enforce a limit it is entitled to enforce, and it can start at any time without notice.
The old cadence was not working at ING; it was unbilled. Moving both banks inside the
rule closes that exposure as a side effect.

## Consequences

**A 429 is not retried.** `RETRYABLE_STATUS_CODES` in the Enable Banking client
excluded 429 as part of this change. A backoff measured in seconds cannot refill a
budget measured in hours or days, the retry is itself charged as an access, and so
three retries turned one over-budget call into four. This consequence is independent
of every open question above: it holds under all three scopings.

**The dedicated pending fetch was removed.** A sync spent three accesses per account
— balances, booked, pending — and the pending one has never returned a row from either
of this owner's banks. Dropping it takes a sync to two accesses per account, which is
what makes two runs a day fit with room rather than exactly. The pending *rules* are
untouched; see the 2026-11-03 amendment to ADR-0003 for the measurement, for why the
machinery stays, and for the one behaviour it did cost.

**A spent allowance is reported as itself.** It used to reach the owner as a `502`
saying "The bank service returned an error (upstream status 429)" — so "the bank is
broken, go and look" and "today's allowance is spent, wait" differed by one number in
a message that had to be interpreted, and the owner spent an evening on the wrong one.
It is now a `503` carrying `code: "bank_rate_limit"` and a message from the backend.
The integration doc holds the shape and why the status cannot be the discriminator.

**The schedule is expressed in UTC and drifts an hour across DST.** `APP_TIMEZONE` is
unset and therefore UTC, so `0 11,20` lands at 12:00 and 21:00 Europe/Madrid in winter
and an hour later under CEST. At this cadence that is immaterial. Setting
`APP_TIMEZONE=Europe/Madrid` would fix the drift but also move every civil date the
product derives — the month boundary, and what "today" means in Safe to Spend Today —
so it is a product decision and not a scheduling convenience.

**The sync-gap alert needed no recalibration**, because coverage is measured per day
against a 30-day fetch window, not per sync. See ADR-0013. Its own reasoning about
debouncing still holds, though its arithmetic no longer does: a permanent gap reported
per pass would now be 2 messages a day rather than 48.

**A manual sync still competes for the unattended budget.** Until PSU-presence headers
are sent, an owner-initiated sync is indistinguishable from a scheduled one and draws
from the same four. Under the strict reading it cannot succeed at all once the schedule
has run; under the generous one it works until it does not. That is the open work, and
it is per bank rather than one global switch: the headers are all-or-nothing (a partial
set is rejected outright), and at least one bank is reported to want them only at
authorization and to fail if they arrive on data calls.

## What would change this decision

* **Measuring the real budget.** Counting accesses per sync and recording where the
  wall falls would settle the scoping question per bank by observation. That is cheaper
  than reading it and stays correct when a bank changes its mind. It is the thing to do
  before raising the number.
* **PSU-presence headers shipping.** They do not raise the unattended ceiling, but they
  take owner-initiated syncs out from under it, which is what makes the cadence feel
  low rather than be low.
* **More accounts on one consent.** The cost of a run scales with the number of
  accounts. The ING savings account and the second Openbank account both arriving would
  change the arithmetic, not the rule.

Raising the cadence on the grounds that ING tolerates it would be reading the one bank
that is not enforcing the rule as evidence about the rule.

[rts]: https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32018R0389
[qa]: https://www.eba.europa.eu/single-rule-book-qa/qna/view/publicId/2019_4631
