# 03 — A rate limit reaches the owner as itself, not as a 502

Status: ready-for-agent
Blocked by: 01

## Why

`_bank_error` in `api/routes/enable_banking.py:23` maps every
`EnableBankingAPIError` to a 502 with "The bank service returned an error (upstream
status 429)."

That reasoning is sound and must be preserved: the upstream status is deliberately
not passed through, because a bank 401 reused as a 401 would look like BurnRate's
own session expiring and log the owner out. But the result is that the owner's
screen says the bank is broken when the truth is "you have used today's allowance,
it refills tomorrow". Those call for opposite reactions — one is "something is
wrong, go look", the other is "nothing is wrong, wait" — and the owner spent an
evening on the wrong one.

## Behaviour wanted

A rate limit is its own answer, distinguishable at the API boundary and shown as
what it is: the allowance for this bank is spent, syncing resumes on its own, no
data is lost because the next successful run still reaches back 30 days.

The last clause is the one that makes it calm rather than alarming, and it is true
— it is the same self-healing property `domain/sync_coverage.py` is built on. A
rate-limited sync is only worth worrying about if it persists long enough for a day
to fall out of the fetch window, and the existing sync-gap alert already says that.

## Acceptance criteria

- A 429 from the bank during a manual sync produces a distinct, documented status
  and body, not the generic 502.
- No upstream status code is reused as BurnRate's own, and no bank payload is
  echoed to the client. Both of the reasons in `_bank_error`'s docstring still hold
  for every other code.
- The Web UI renders it as information rather than an error, and says when syncing
  resumes.
- Every other `EnableBankingAPIError` still maps to the 502 it maps to today.

## Notes

Decide the status code deliberately and write the reason down. A 429 passed through
is honest about the cause but invites a client to retry, which ticket 01 establishes
is the wrong thing to do. The presentation layer must not derive "when it resumes"
on its own — per AGENTS.md the client reads it from a backend field.
