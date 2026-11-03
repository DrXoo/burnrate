# 04 — An owner-initiated sync is an attended access

Status: ready-for-agent
Blocked by: 02

## Why

PSD2 caps *unattended* accesses at four per account per day. An access the account
holder asked for, while present, is exempt.

After ticket 02 the two scheduled runs spend exactly those four. There is no slack
left, which means **the manual sync button cannot succeed** — it competes for a
budget the schedule has already committed. That is not a regression introduced by 02;
it is the true cost of the schedule becoming visible once the waste is gone.

The client sends `psu_type` (`integrations/enable_banking/client.py:53,64`) but no
PSU-presence headers, so every request BurnRate makes is unattended whoever asked
for it.

## Behaviour wanted

A sync the owner triggers from the Web UI or Telegram is sent as an attended access
and does not draw on the unattended budget. A sync the scheduler triggers is sent as
unattended, honestly.

## Acceptance criteria

- A manual sync's requests carry the PSU-presence headers; a scheduled sync's do not.
- Presence is decided by **who asked**, carried explicitly from the API/bot entry
  point to the client. It must not be inferred from anything ambient — not the
  presence of a session cookie, not whether the call arrived over HTTP, not a
  thread-local. An unattended run that mislabels itself as attended is a compliance
  problem, not a bug, and the failure is silent.
- The scheduler cannot reach the attended path. Make this structurally true rather
  than true by convention, and write a test that fails if a scheduled sync ever
  sends a presence header.
- A manual sync still succeeds when the unattended budget is already spent. This is
  the acceptance test that matters, and it is the one the current fake bank client
  cannot express — it needs a double that enforces a budget and distinguishes
  attended from unattended requests.

## Before writing code

Three things found while checking the regulation on 2026-11-03, each of which would
have been walked into otherwise.

**The headers are per bank, and the list is served by the API.** `/aspsps` returns a
`required_psu_headers` field per ASPSP. Read it rather than hardcoding a pair of
header names — and note that the `/aspsps` payload is already fetched and could be
persisted alongside the connection.

**They are all-or-nothing.** Sending some but not all of a bank's required PSU headers
is rejected (`PSU_HEADER_NOT_PROVIDED`, reported as a 422), so a partial set is worse
than none: it turns a working unattended sync into a hard failure.

**At least one bank breaks if they are sent on data calls at all.** HypoVereinsbank is
reported to want PSU headers only at authorization, not on balance and transaction
requests. So this cannot be one global switch flipped by "the owner asked". It has to
be per bank, driven by what that bank declares, with a safe default — and the safe
default is to send nothing, because that is today's behaviour and it syncs.

Which also means **the acceptance criteria below cannot all be met for every bank**,
and that is not a bug in the ticket. For a bank that refuses PSU headers on data calls
there is no attended path, so the manual button cannot escape the budget there and the
honest outcome is ticket 03's message rather than a silent failure. Verify what ING and
Openbank each declare before designing the seam, because if neither of this owner's two
banks supports it, this ticket is research and not a feature.

Record what is found in `docs/technical/bank-integrations/enable-banking.md`. Getting
this wrong fails in the quiet direction: the headers are ignored, the budget is spent
anyway, and the only symptom is a 429 that looks like ticket 01 all over again.

## On the budget this ticket assumes

The premise "the schedule commits the entire unattended budget" rests on a scoping of
the four-per-day limit that this owner's own data **excludes** — see the spec's
measurement table. Under the scoping that does fit, two runs a day leave half the
budget free and a manual sync may simply work without any of this.

That weakens the urgency and not the ticket: competing for a shared budget fails
unpredictably, which is harder to live with than failing always. But it is a reason to
do `02` first, watch a week of real syncs, and let the measurement decide how much this
is worth.
