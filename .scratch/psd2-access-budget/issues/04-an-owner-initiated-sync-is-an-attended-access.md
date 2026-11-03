# 04 — An owner-initiated sync is an attended access — REJECTED

Status: rejected, 2026-11-03
Blocked by: 02

**Superseded by `05`, which removes the manual sync instead.** Kept rather than deleted
because the reason is a measurement worth not repeating.

## What this ticket proposed

Send PSU-presence headers on owner-initiated syncs, so they count as *attended* access
and sit outside the four-per-day PSD2 budget rather than competing with the schedule
for it.

## Why it was rejected

The ticket's own "before writing code" section said to check what each bank declares
in `required_psu_headers` from `/aspsps`, and that if neither of this owner's banks
supported it the ticket was research rather than a feature. That check costs nothing —
`/aspsps` is a catalog call and is not scoped to a consent — and it was run:

| Bank | `required_psu_headers` | Enforces the limit? |
|---|---|---|
| **ING** | `['psu-ip-address']` | **no** — served 37 syncs on 2026-11-03 |
| **Openbank** | `None` | **yes** — refused the third sync of the day |

**It is crossed exactly the wrong way.** The bank that declares a PSU header is the one
that does not enforce the budget, and the bank that cuts us off declares none. Openbank
is also marked `beta: true`.

So the attended path would have worked only where it was not needed, and the manual
sync button at the bank that enforces the limit would still have failed — while adding
per-bank header plumbing, an all-or-nothing failure mode (`PSU_HEADER_NOT_PROVIDED`),
and a known hazard in at least one other bank that is reported to break if PSU headers
arrive on data calls.

## What survives from it

* **Sending `psu-ip-address` on ING** is cheap and would matter the day ING starts
  enforcing the limit, which is a question of when. Not urgent, and not worth a
  per-bank abstraction for one header at one bank — revisit if a second bank declares
  one.
* **Measuring the real budget** — see the spec's out-of-scope list. Still the only
  thing that settles how the four are counted, and still the right precondition for
  ever raising the cadence.
