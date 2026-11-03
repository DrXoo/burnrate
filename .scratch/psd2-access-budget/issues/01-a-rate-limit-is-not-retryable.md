# 01 — A rate limit is not a retryable error

Status: done
Blocked by: —

## The defect

`RETRYABLE_STATUS_CODES` in `backend/src/burnrate/integrations/enable_banking/client.py:16`
is `frozenset({429, 500, 502, 503, 504})`.

A 429 from Enable Banking is `ASPSP_RATE_LIMIT_EXCEEDED` — the daily unattended
access budget for a consent is spent. Retrying it three times at 0.5s, 1s and 2s
cannot succeed, because the quantity that must change is measured in days. What it
does instead is turn one over-budget access into four, deepening the overdraft that
caused the error and pushing recovery further into tomorrow.

Observed in `docker compose logs sync-worker` on 2026-11-03 at 19:30: three retries
of `GET /accounts/{id}/balances`, three further 429s, then the failure.

## Behaviour wanted

A 429 raises immediately. The other four codes keep their retries: a 500 or a 503
is a transient upstream fault and retrying it is correct.

## Acceptance criteria

- A 429 on any request results in exactly **one** HTTP request.
- A 503 followed by a 200 still succeeds, and takes two requests.
- The retry budget for the transient codes is unchanged, i.e. a persistent 503
  still makes `enable_banking_max_retries` + 1 requests.
- The 429 path logs enough for the owner to tell a rate limit from a bank outage,
  and logs no bank payload.

## Notes for the implementer

Write the counting double first and watch the first assertion **fail at four**. If
it passes on arrival you are not counting requests, you are counting something else
— and this is precisely the case AGENTS.md says to mutation-check, because the bug
being fixed is invisible to a double that does not count.

Do not express this as "retry unless 429" scattered at the call site. `_is_retryable`
already exists and is the one place that answers this question; the fix belongs
inside it, with the reason in a comment, because the next person will otherwise read
429 as an obvious member of a retryable set.

## Comments

**2026-11-03 — done.** Two vertical slices, both red first.

1. `429` out of `RETRYABLE_STATUS_CODES`. The first assertion failed at `assert 4 == 1`,
   which is the ticket's own tripwire.
2. A rate limit is logged by name. This one was worth having: with `429` no longer
   retried the client logged *nothing at all*, so the only trace was the caller's
   traceback — identical in shape to a `503` and differing by one number.

Three mutations, all killed:

| Mutation | Killed by |
|---|---|
| `429` back in `RETRYABLE_STATUS_CODES` | both rate-limit tests |
| log the bank's response body | the `secret` assertion in the logging test |
| drop the `429` guard in `_log_rate_limit` | **nothing — a real gap** |

That third one is the finding. Deleting the status check left all nine tests green
while a `503` outage would be announced to the owner as "rate limit reached for this
consent, no history is lost" — telling them to wait while the bank was down. The
guard was a rule with no test, exactly the shape AGENTS.md names. Closed by
`test_enable_banking_client_does_not_call_an_outage_a_rate_limit`, which passed on
arrival and was then mutation-checked until it failed.

Docs: `docs/technical/bank-integrations/enable-banking.md` had `429` written into its
retried list. Corrected, with the reason and the measurement. Also recorded there that
the Telegram bot *does* retry its own `429`s and that this is not an inconsistency to
tidy away — Telegram's limit is seconds and names a `retry_after`, a bank's is days
and names nothing. Without that note the next reader reconciles the two in the wrong
direction and reintroduces this bug.

Suite: 547 passed.

**2026-11-03, later — checked against the regulation, unchanged.** The owner asked how
sure the four-per-day figure was. It turned out the spec had overstated the *scope* of
the limit (see the spec's correction), but nothing in this ticket depends on the number:
a backoff of 0.5s, 1s and 2s cannot refill a budget measured in hours or days under any
scoping, and the retry is charged as an access under all of them. The fix stands as
shipped.
