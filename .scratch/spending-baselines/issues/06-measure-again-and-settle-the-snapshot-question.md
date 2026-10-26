# 06: Measure again, and settle the snapshot-table question

**What to build:** The after-figure for the summary endpoint's request cost, taken by
ticket 01's method against the same month and scope, and a recorded decision about
whether a monthly snapshot table is warranted. The month window is already non-sargable
and plans as a sequential scan, and this feature reads several months where one was read
before, so the roadmap requires the question be answered on evidence.

**Blocked by:** 03, 04.

**Status:** done

- [x] The request cost is measured again by ticket 01's method, against the same month and the same transaction scope
- [x] The delta is recorded against ticket 01's figure
- [x] A decision about snapshot tables is written down with its reasoning. If the cost is acceptable, that is recorded as the decision rather than left implicit
- [x] If the decision is to introduce one, it is recorded as future work rather than built here; this ticket measures and decides, it does not optimise
- [x] The relevant docs are updated in the same change, per the documentation rules


## Comments

**Done.** No red → green loop and no test, for the same reason as ticket 01: this
changes no behaviour. The backend image was rebuilt from the branch and the harness
run in a one-off container, so the branch's code met the live database without
restarting the owner's stack.

### The decision

**No snapshot table.** 13 and 15 statements live, 25 at the ceiling, roughly 37ms,
over one owner's 623 transactions. The statement count is bounded by the window
rather than by accumulated history, so five years of rows does not move it.

The trigger for revisiting is named rather than left open: **widening
`BASELINE_WINDOW_MONTHS`**, which this design actively invites. Twelve months comes
to about seventy statements a request, and the cheap mitigation at that point is the
expression index or the stored `effective_date` column `schema.md` already names for
these same queries. A snapshot table is the last resort, not the next step.

### My prediction was wrong, in the opposite direction

I wrote in tickets 01, 02, 03 and 04 that the current month should become the more
expensive of the two, and that finding them equal would mean something was broken.
They are not equal, and the **closed** month costs more: 15 against 13.

The cutoff is not what drives the cost. `_month_qualifies` tests sync coverage first
and returns before running the two classification queries, so what a candidate month
costs depends on *which test it fails*, not on how many months qualify. Viewing
September, two of its three candidates pass the sync test and reach the
classification queries; viewing October, one does. 15 − 13 = 2 accounts for it
exactly.

Which makes the measurement **data-dependent** — the same code over the same month
costs 13 statements or 16 depending on whether the sync history is holed. That is the
part worth carrying forward, and it is why the live figure needed a synthetic ceiling
beside it.

### What the measurement actually found, which was not a performance problem

**Ticket 03's rule has found a real 36-day hole in the owner's live data**, 2026-08-29
to 2026-10-04, wider than the 30-day fetch window, which nothing else in the system
reported. Both months report `insufficient_history` with **zero** Qualifying Months.

This falsifies a claim the spec made and that I repeated at the end of ticket 02: that
the feature "ships with exactly two qualifying months, which is exactly the minimum".
It ships with zero. The claim came from classification coverage alone, measured before
ticket 03's rule existed to disagree with it.

| Month | Sync covered | Unclassified | Qualifies |
|---|---|---|---|
| 2026-06 | yes | 66.6% | no — classification |
| 2026-07 | yes | 57.6% | no — classification |
| 2026-08 | **no** | 0.0% | no — never asked about |
| 2026-09 | **no** | 0.0% | no — never asked about |
| 2026-10 | not yet | 2.2% | not yet — month still open |

The two months that looked cleanest are the two straddling the gap, and **they can
never qualify**: nothing can request a window older than 30 days, so 30 August to 3
September will never be fetched. August's and September's expense totals, which the
spec quotes, are understated by whatever fell in those days.

### What the owner can do about it

* **Left alone, the feature starts working in December 2026.** Viewing December, the
  window reaches September, October and November; the last two qualify once closed,
  given continuous syncs. Every earlier view has at most one Qualifying Month in
  reach.
* **Or it works today for the price of one setting.** June and July *are* sync
  covered — only the backlog disqualifies them. Classifying it and setting
  `BASELINE_WINDOW_MONTHS=5` brings both inside October's window: two Qualifying
  Months and a working comparison. That this is an environment variable rather than a
  migration is the entire return on refusing a stored accumulator during design.

### Not done here

The Definition of Done check belongs to the next pipeline stage, not to this ticket,
and it now has something real to weigh: the phase's clause about every headline figure
being shown against its own baseline is not demonstrable against live data today. The
reason is the owner's data rather than the code, which is a distinction that check
should make explicitly rather than inherit from here.
