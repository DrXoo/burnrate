# A sync gap is reported at request time, and by the worker only at startup

Days the bank was never asked about are detected in **two** places, and neither is
the obvious one.

`/summary` computes the gap on **every request**, because the failure this exists
for is the sync worker not running, and **a process that is not running cannot
report itself**. The owner opening the app is the only path that catches it.

The worker reports it at **startup**, not on each sync pass. Starting up is the
first moment a returning worker can speak, and it is also what debounces the
alert — a permanent gap reported per pass would repeat for the ninety days of the
lookback, where startup reports it once per restart.

That argument was first written against a cadence of 48 passes a day, which made it
48 messages a day. ADR-0015 cut the cadence to two, so the number is now two a day and
the case is weaker than it was. It is not gone: two identical messages a day for three
months is still how a warning becomes furniture, and startup is still the first moment
a returning worker can speak. The arithmetic is recorded as changed rather than
quietly restated, because a reader checking this against `SYNC_CRON` would otherwise
find it wrong and distrust the rest.

## The cause recorded in the roadmap was wrong, and that is why

Phase 9a attributed the owner's 36-day hole to a lapsed consent writing a
`skipped` session per attempt, and designed the alert against that. Checked
against the database:

* there is exactly **one** `skipped` session in the entire history, dated
  2026-07-09;
* the active connection was authorized 2026-07-16 and expires 2027-01-12, and the
  consent alert demonstrably **works** — it fired on 2026-07-16 for the previous
  connection, three days before it lapsed;
* **there are no `sync_sessions` rows at all between 2026-08-29 and 2026-10-04.**
  The 29th cut off at 33 runs of 48; the 4th resumed at 27. (48 was the cadence
  at the time — see ADR-0015 for why it is now two.)

The worker was down. Had the alert been built where it was first proposed — inside
the sync pass — it would have been incapable of reporting the only failure that has
ever happened here. The wrong cause in the roadmap is corrected in place rather
than deleted, because the correction is the reason for this shape.

## The message is a deadline, not a fact

"There is a sync hole" is not actionable. A missing day is not lost: the provider
serves a trailing 30-day window, so a run today still reaches a day missed
yesterday and the next successful pass fetches it. A day is lost exactly when it
falls out of that window.

So the backend publishes a `status`, and the two values are two different things
to say:

* **`expiring`** — nothing lost yet, and the message is a date and an ask. About
  *today*, so it is reported whatever month the owner has open.
* **`lost`** — days are gone **and belong to the month being viewed**, whose
  figures are therefore understated. *No action is offered*, because none recovers
  them; offering a reconnection would be a lie.
* **`lost_elsewhere`** — gone, and belonging to some other month. **Silent.**

That third value was added after the first version shipped with only two, and the
owner found the defect in a sentence: *"are we going to show this all the time,
even in November?"* With a 90-day lookback that banner would have sat on top of
every month's figures until 2 December — a permanent notice about the days they
lost moving house in August, with nothing to do about it. **That is how a warning
becomes furniture.**

A loss is a fact about the months that lost the days, not about today, so it is
reported on them and nowhere else. The facts stay in the payload in all three
cases, so an interface that wants to surface it somewhere quieter need not
re-derive it.

**Permanent loss also stops being an alert.** A day hardens
`fetch_window_days` after itself, so `gap_is_worth_alerting` reports a loss only
while it hardened within the grace period. Without that rule the worker — which
reports at *startup* — would re-send the same August message on every redeploy for
three months.

A gap the next successful run will close earns **nothing**. That is the
over-firing the roadmap says the alerting phase fails by, and a restart is not
news. The threshold is `SYNC_GAP_GRACE_DAYS`, seven days.

The status is decided in the backend rather than derived by each interface, for the
reason ADR-0002 records: a state each client derives is a state each client can
derive differently.

## What is deliberately not built

**A dead-man's switch** — the only thing that warns *during* an outage. By
definition it cannot live inside the worker, and needs a host cron, an uptime
monitor or a healthcheck pinging something external. That is deployment, and it
belongs with Phase 13. Everything here is either at request time or after the
fact, and the limit is stated rather than papered over: **an owner who does not
open the app during an outage, and whose worker does not come back, is told
nothing.**

The gap the worker cannot see at all is the `expiring` one with the worker alive
and its syncs failing. That case already has `send_reconnect_alerts` and
`send_expiry_alerts` for its causes, and `/summary`'s own `sync_gap` for its
consequence.

## Consequences

**One spelling of the coverage sweep.** `baselines.month_sync_covered` is now
defined as `uncovered_days` being empty, rather than keeping its own copy. Two
spellings of one window rule is the defect `db.budget_windows` and
`db.counted_spend` both exist to prevent, and this product has already paid for it
once — the baselines and the summary each wrote their own pending-spend rule and
disagreed about a negative residual.

**One read of the sync history.** `sync_coverage_service.successful_sync_days` is
the only query, used by the gap and by the baselines' Qualifying Month test, for
the same reason.

**The lookback is bounded at both ends.** `SYNC_GAP_LOOKBACK_DAYS` (90) stops
permanent damage being re-reported for the life of the product, because an alert
that cannot stop is an alert that gets muted. And the range never begins before the
first day any sync *could* have covered, or a product with two months of history
reports its own first day as a hole — true, and useless. With no successful sync at
all there is nothing to report: that is onboarding, not a gap.
