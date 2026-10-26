# 01: Record the summary endpoint's current request cost

**What to build:** A recorded measurement of what the summary endpoint costs today,
against the owner's real data, before any baseline query exists. The roadmap requires
measurement before a snapshot table is even considered, and this is the half of that
measurement that can only be taken now — once the first baseline query lands, the
before-figure is gone for good.

**Blocked by:** None (can start immediately).

**Status:** done

- [x] The summary endpoint's request cost is measured against the owner's live data and the figure recorded in the spec
- [x] The measurement states which month was requested and how many transactions were in scope, so the after-figure can be compared like for like
- [x] The method is written down precisely enough that ticket 06 can repeat it identically rather than inventing a second one
- [x] No production code is changed by this ticket

## Comments

**Done.** Recorded in the spec under **Recorded Measurement**: 6 SQL statements for
both the current month and a closed month, warm medians of 11.8 ms and 10.0 ms,
against 623 transactions.

**No red → green loop, and no test was written.** This ticket changes no behaviour,
and its own last criterion forbids touching production code, so there was nothing to
drive out. `AGENTS.md` asks for that to be said in the summary rather than papered
over with a test that would assert a measurement against itself. The highest-value
thing available instead was making the measurement *verifiably* repeatable, which is
what was done: the harness was extracted from the spec's fenced block and executed
verbatim, and that run reproduced the recorded figures.

Three findings worth carrying into ticket 06:

* **The statement count is the signal; wall time is noise.** Warm runs spanned 9.2 to
  17.5 ms across four measurement sessions — roughly ±15% — while the statement count
  was 6 every single time. The growth this feature introduces is in how many month
  windows get scanned, not in how fast one scan runs, so statement count is also the
  figure that actually predicts the cost. Ticket 06 compares counts first.
* **Both months cost the same today, and that is the baseline to beat.** Nothing in
  the current summary reads a month other than the one requested, so the current month
  and a closed one scan the same number of windows. After this feature they should
  not, and the current month should become the more expensive of the two because of
  the same-day cutoff. If ticket 06 finds them still equal, something is wrong.
* **Both the month and `today` are pinned in the harness.** `today` is injectable on
  the service, and leaving it to the wall clock would silently change which case is
  "the current month" the moment the calendar moves past October — which it will have
  done by the time ticket 06 runs. This is the same class of trap as the fixture-clock
  rule in ticket 02.

The harness measures the service rather than the HTTP route on purpose: the route adds
authentication and response validation that this feature does not touch, and only the
service accepts `today`, which is what makes the measurement repeatable at all.
