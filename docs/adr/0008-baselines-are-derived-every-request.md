# Baselines are recomputed on every request, with no snapshot table

Phase 9a added a comparison of every figure the owner acts on against what that
figure normally is for them. A baseline reads *other* months, so one summary
request went from scanning one month window to scanning several. The roadmap's
own Phase 9 note opens the door to a monthly snapshot table for query cost —
after measurement. This is that measurement, and the answer is **no snapshot
table, no accumulator, no column**. Every baseline is computed from transactions
on each request.

The reason is not performance, which `AGENTS.md` ranks last of five. It is that
**in this product the past changes**, deliberately and in four separate ways: a
budget can be cancelled from a month already closed (ADR-0005), the pending
sweep deletes rows (ADR-0003), classifying an Unknown Transaction rewrites a
closed month's category totals, and `Ignored` is a decision the owner can lift.
A stored figure could not be verified against the current state of the data, and
if it drifted there would be no way to detect or repair it short of recomputing —
at which point storing it bought nothing. The owner had two months whose figures
were about to move a great deal once a 44-transaction backlog was classified; a
value accumulated before that review would have been permanently wrong with
nothing anywhere to say so.

The payoff is that the *shape* of the baseline stays cheap to change. The window
is a parameter over source data, so moving from a fixed window to a widening one,
or to exponential decay, is a change to one domain function with no migration and
no historical conversion. The owner's live data cashed that cheque immediately:
making the comparison demonstrable today is `BASELINE_WINDOW_MONTHS=5`, an
environment variable, where a stored accumulator would have made it a backfill.

## The measurement

Against the owner's live database, 623 transactions, both the requested month and
`today` pinned. Measured before the feature at commit `20592fe` and after at
`a965f76`.

| Case | Month | SQL statements | Warm median | Before |
|---|---|---|---|---|
| Current month | 2026-10 | 13 | 37.1 ms | 6 / 11.8 ms |
| Closed month | 2026-09 | 15 | 35.6 ms | 6 / 10.0 ms |

The live figures are a **lower bound**: both cases report zero Qualifying Months
(see ADR-0009), so most of the per-qualifying-month work never ran. The ceiling
was measured separately over an in-memory fixture at the default three-month
window — the queries are identical, so the counts carry over and the timings do
not.

| Qualifying Months | SQL statements |
|---|---|
| 0 | 16 |
| 2 | 22 |
| 3 | 25 |

Each Qualifying Month costs three more statements — its per-category spend and
its two aggregate totals — and each candidate month that passes the sync test
costs two more for classification coverage. **The count is bounded by the window,
not by accumulated history**, so five years of rows (some 8,000, at the owner's 80
to 190 a month) does not move it at all.

Three findings about the method, because the next person to measure this should
not re-derive them:

* **The statement count is the signal; wall time is noise.** Warm runs spanned
  9.2 to 17.5 ms across four sessions, roughly ±15% on a development machine,
  while the count was identical every time. The growth this feature introduces is
  in how many month windows get scanned, not in how fast one scan runs, so the
  count is also the figure that predicts the cost. Compare counts first and treat
  a wall-time move inside that band as noise.
* **Pin both the month and `today`.** `today` is injectable on the service, and
  leaving it to the wall clock silently changes which case is "the current month"
  the moment the calendar turns.
* **The cost is data-dependent, which was the surprising part.** The prediction
  was that the current month would become the more expensive of the two because
  of the same-day cutoff. It is the *closed* month that costs more, 15 against 13:
  `_month_qualifies` tests sync coverage first and returns before running the two
  classification queries, so what a candidate month costs depends on **which test
  it fails**. Viewing September, two of its three candidates pass the sync test
  and reach the classification queries; viewing October, one does. The same code
  over the same month costs 13 statements or 16 depending on whether the sync
  history has a hole in it.

## Consequences

**The trigger for revisiting this is a window change, not the passage of time.**
Twelve months of reach comes to roughly seventy statements per request, and
`BASELINE_WINDOW_MONTHS` exists precisely so the reach can grow as history does.
The cheap mitigation at that point is the one `schema.md` already names for these
same non-sargable queries — an expression index on the coalesce, or the stored
`effective_date` column Phase 8 deferred. A snapshot table stays the last resort
rather than the next step.

## Considered Options

A **monthly snapshot table** was the roadmap's own suggestion and is the obvious
shape: one row per month per category, written when a month closes. Rejected
because a closed month is not final in this product, so the table would need
invalidation on four unrelated events, and a missed invalidation is a wrong
baseline that looks exactly like a right one.

An **incremental accumulator** was rejected for the same reason plus one more: it
cannot be audited. A snapshot can at least be compared against a recomputation; a
running total carries no record of what went into it.
