# Spending Baselines (Phase 9a)

Status: ready-for-agent

Phase 9 in `docs/technical/roadmap.md` is split in two. This spec covers **9a**:
trailing baselines, month-over-month comparison, and anomaly flagging on category
totals. **9b** — Recurring Charge detection, subscription inventory, price-change
detection — is a separate spec and is not designed here.

---

## Problem Statement

Every figure BurnRate reports describes the month on screen and nothing else. The
summary response carries two dozen fields and not one of them knows what any other
month looked like. The only field with "average" in its name divides this month's
variable spend by this month's elapsed days.

So the product can state a level and never a change, and for a salaried owner whose
levels are stable, the change is where all the information is. "420 EUR in Food, 84%
used" is the same sentence whether the owner normally spends 300, 430 or 480 — it
reads as a mild warning in all three cases, when it should read as an alarm, as
silence, and as praise respectively.

The failure has a shape worth naming, because it is what makes the problem worth
fixing rather than merely untidy: a subscription that rises from 12.99 to 15.99 is
invisible as a level and obvious as a change. No threshold on levels will ever catch
three euros. The owner finds it by reading a bank statement, which is the chore the
product exists to replace.

This is also the prerequisite for Phase 10. An alert needs a reason to fire, and
without a baseline the only thing it can say is what the dashboard already says.

## Solution

Every figure the owner acts on is shown against what that figure normally is for
them, and the product refuses to make the comparison when it cannot make it
honestly.

A **Baseline** is the mean of a figure over the recent months whose data can be
trusted, recomputed from transactions on every request and never stored. Where a
baseline exists, the figure is shown beside it with the deviation. Where one does
not — too little history, too little of the month classified, a category too new or
too rarely used — the product says so instead of printing a number it cannot stand
behind.

Two properties carry most of the design:

**The comparison excludes what it cannot compare, and discloses it.** A month
dominated by a one-off expense in a category with no history would otherwise report
catastrophic overspending while every ordinary category sat below its own baseline.
So spend splits into **Comparable Spend** — the categories that have a baseline —
and **Uncomparable Spend**, which is reported beside the comparison and never
inside it. This is the shape `Unbudgeted Spend` already has: invisible to the
figures it would corrupt, always disclosed next to them.

**The comparison carries a time term.** For the current month, each qualifying
month is summed only up to the same day of the month, so the statement is "by the
26th you would normally have spent X" rather than a part-month measured against a
whole-month total.

## User Stories

1. As the owner, I want each headline spending figure shown against what it
   normally is for me, so that I can tell a change from a level.
2. As the owner, I want my per-category spend shown against that category's own
   baseline, so that I can see which part of the month is unusual rather than only
   that the month is.
3. As the owner, I want to be told when my spend in a category is far above its
   baseline, so that I learn about it before I read a statement.
4. As the owner, I want to see that I am *below* my baseline, so that a quiet month
   is visible as good news rather than as the absence of a warning.
5. As the owner, I do not want an anomaly raised because I spent less than usual, so
   that the warnings I do get are worth reading.
6. As the owner, I want the number of months a baseline rests on shown next to it,
   so that I can judge how much to trust it.
7. As the owner, I want no baseline shown at all when there is too little history,
   so that I am never given a comparison the data cannot support.
8. As the owner, I want a month whose transactions are largely unclassified excluded
   from every baseline, so that my review backlog does not quietly bias my own
   history downwards.
9. As the owner, I want a month the bank was never asked about excluded from every
   baseline, so that a lapsed consent or a stopped worker cannot understate what I
   normally spend.
10. As the owner, I want the current month excluded from its own baseline, so that
    the comparison is against other months rather than partly against itself.
11. As the owner, I want a one-off expense in a category with no history kept out of
    the comparison and reported beside it, so that one unusual event does not make
    every ordinary category unreadable.
12. As the owner, I want to see the total of the spend that could not be compared,
    so that the excluded money is disclosed rather than hidden.
13. As the owner, I want a category I have only ever spent in once to have no
    baseline, so that the product does not invent a normal monthly cost for
    something that happened once.
14. As the owner, I want a category I have stopped spending in to lose its baseline
    as the window moves past it, so that the product stops telling me what I
    normally pay for something I no longer buy.
15. As the owner, I want my current month's spend compared against the same part of
    previous months, so that the comparison is not trivially favourable for most of
    the month.
16. As the owner, I want a closed month compared whole against whole, so that
    reviewing a finished month gives me its real outcome.
17. As the owner, I want a month that has not started to make no comparison, so that
    a scheduled payment filed into a future month is not read as that month's
    outcome.
18. As the owner, I want my income shown against its baseline, so that a short
    payslip is visible immediately.
19. As the owner, I want my net cash flow shown against its baseline, so that I can
    see whether I am saving more or less than usual.
20. As the owner, I want my daily allowance left out of this, so that I am not shown
    a comparison between two months whose budgets, lengths and fixed commitments all
    differed.
21. As the owner, I want transfers between my own accounts kept out of every
    baseline, so that an automated round-up is not mistaken for spending.
22. As the owner, I want transactions I marked Ignored kept out of every baseline, so
    that a decision I already made is not undone by the comparison.
23. As the owner, I want an Archived Category left out of the comparison list, so
    that a category I retired does not report itself as below baseline every month
    for ever.
24. As the owner, I want the same comparison in my Telegram summary as on the
    dashboard, so that the two never disagree.
25. As the owner, I want the Telegram summary to omit the comparison when there is no
    baseline, so that it does not print a line with nothing in it.
26. As the owner, I want the comparison to appear beneath figures I already read,
    rather than on a new page, so that I do not have to go looking for it.
27. As the owner, I want the per-category comparison on the Categories page rows, so
    that it sits with the figures it qualifies.
28. As the owner, I want to page back to a closed month and see that month's
    comparison against the months before it, so that the baseline is not only ever
    about today.
29. As the owner, I want to change how many months a baseline reaches back over, so
    that I can widen it as my history grows.
30. As the owner, I want the product to keep working unchanged when I have only two
    qualifying months, so that the feature is usable now rather than next year.
31. As the owner, I want baselines recomputed from my transactions every time, so
    that classifying an old transaction or correcting a category immediately fixes
    every figure that depended on it.
32. As the owner, I want no new stored figures to go stale, so that there is nothing
    to repair when I edit my own past.
33. As the owner, I want a category with a budget and a category without one treated
    the same by the comparison, so that spend outside a budget is not invisible to it.
34. As the owner, I want the deviation expressed as a percentage, so that I can
    compare a large category and a small one at a glance.
35. As a maintainer, I want every threshold in this feature to live in the domain
    layer, so that no interface re-derives a financial rule.
36. As a maintainer, I want the request cost of the summary measured before and
    after, so that the decision about snapshot tables is taken on evidence.

## Implementation Decisions

### A Qualifying Month must pass two independent tests

A **Qualifying Month** is a closed month that can be trusted as baseline input. Two
things can make a month untrustworthy and they are invisible to each other, so both
are checked:

* **Classification coverage.** The share of the month's outgoing amount that is not
  classified must be at or below the coverage floor. **Measured by amount, never by
  rows.** This is not a preference: in the owner's live data, June 2026 reads 79%
  classified by row count and 33% by amount, because the unclassified rows are the
  large ones. A row-based measure would have admitted June as a clean baseline month
  while two thirds of its money was missing.
* **Sync coverage.** The month must be spanned by successful syncs with no gap wider
  than the provider fetch window. A month with a sync hole looks perfectly
  classified — every row it does have is filed — while missing transactions
  entirely, so classification coverage cannot see it. Derived from the existing sync
  session records; no new table.

The current month is never a Qualifying Month. Neither is a month that has not
started.

### Baselines are recomputed from source, never stored

No migration, no new table, no accumulator updated as months pass. This was
challenged directly during design and the reasoning is recorded because it will be
challenged again:

* `AGENTS.md` requires derived metrics to be computed from source rather than held
  as primary stored truth, and the roadmap's Phase 9 note opens the door to a
  snapshot table for **query cost only**, after measurement.
* In this product the past changes. Cancelling a budget from a past month is
  deliberately allowed (ADR-0005); the pending sweep deletes rows; classifying an
  Unknown Transaction rewrites a closed month's category totals; `Ignored` is a
  decision the owner can lift. An accumulated value cannot be verified against the
  current state of the data, and if it drifts there is no way to detect or repair it
  short of recomputing — at which point storing it bought nothing.
* The owner has two months whose figures are about to move a great deal when the
  44 queued transactions in them are classified. A value accumulated before that
  review would be permanently wrong with no mechanism to notice.

The payoff is that the shape of the baseline stays cheap to change. The window is a
parameter over source data, so moving from a fixed window to a widening one or to
exponential decay is a change in one domain function with no migration and no
historical conversion.

### The baseline is a trailing mean, and it says how many months it rests on

The mean over the Qualifying Months the window reaches, with the count reported
alongside. Median and trimmed mean are rejected **for now, on arithmetic rather than
taste**: at two or three months a median is the middle value and buys no robustness,
which only appears around five. Revisit at four or more qualifying months, where it
becomes a change to one domain function.

The window is the maximum reach, not a requirement. Default three months,
configurable through settings in the manner of the existing expiry-warning setting.

### The divisor is the window, and a presence floor guards it

For a category above the floor, the mean divides by the **Qualifying Months in the
window**, not by the months the category appeared in. For a recurring expense an
absent month is a real zero and carries information.

That rule is only safe because a **presence floor** keeps one-off categories away
from it: a category with spend in fewer than the floor's number of Qualifying Months
gets **no baseline at all**. Without the floor, dividing a single holiday across
three months would invent a monthly travel cost that has never existed.

The floor also makes an owner-declared "circumstances changed" date unnecessary,
which is why no such concept is built. A category whose spend has stopped falls
below the floor as the window moves past it and loses its baseline on its own: in
the owner's data, a rent paid for three months and then ended is retired
automatically in every future window.

### Comparable and Uncomparable Spend

The aggregate comparison is computed over **only** the categories that have a
baseline. Everything else is **Uncomparable Spend**, reported beside the comparison
and never inside it.

This is load-bearing, not tidiness. In the owner's live October, one category with
no history holds 8403.83 of 9251.08 while Food, Invoices, Restaurant, Farmacy and
Shopping all sit *below* their own baselines. A comparison over all spend would
report +260% and catastrophic overspending; the truth is that every ordinary
category is quiet and one non-recurring event swamped the total. The aggregate
figure would not be merely unhelpful, it would be actively wrong about the only
thing the product exists to say.

`Unbudgeted Spend` is the precedent and the pattern is deliberately reused:
invisible to the figures it would corrupt, always disclosed alongside them.

The alternative term considered for the pair was Baselined / Unbaselined Spend,
rejected as awkward; the Comparable / Uncomparable pair states what the split is for.

### The current month's comparison carries a time term

For the current month, each Qualifying Month contributes only the spend up to the
**same day of the month**, clamped to that month's last day. The claim is "by the
26th you would normally have spent X".

Phase 8 already paid for the alternative: the Web UI compared spend against 85% of
budget with no time term, so an on-plan month flipped to a warning around day 26.
The fix there was `On-Plan Remaining`, a comparator with the time term built in.
Pro-rating the baseline by elapsed days was considered and rejected instead, because
it assumes spend accrues evenly, which is exactly what a `Fixed Budget` does not do
— a rent charged on the 1st would read as a month-long overrun. Summing each past
month to the same cutoff makes no pacing assumption and places a step charge
identically on both sides.

A closed month is compared whole against whole. A month that has not started makes
no comparison.

### Comparing and firing are different acts

The deviation is reported in both directions, always. An anomaly **fires only
upward**: spend at or above the baseline times the anomaly ratio. The product exists
to stop the owner overspending, and the roadmap is explicit that Phase 10 fails by
over-firing. Being 55% below a baseline is information, not an alarm — and the owner
has a live month in exactly that state.

One status names the whole judgement so no interface re-derives a band, following
ADR-0002's amendment: `no_baseline`, `below`, `in_line`, `above`, `anomalous`. The
`in_line` tolerance is set from the owner's own observed month-to-month variation in
clean months, which is roughly ±12%.

**Per-transaction anomaly flagging is out of 9a.** Stating "this charge is unusual
for this category" needs a per-transaction distribution, and two months with eleven
rows in a category is not one.

### Where the policy lives, and where the SQL lives

* A new pure domain module for baseline policy, a sibling of the existing metric
  policy module rather than an extension of it. The existing module judges one month
  against its budgets; this one judges a series of months against each other, and
  its inputs are a series rather than a month's figures. ADR-0001's own precedent is
  to scope such a module narrowly. It owns: the coverage floor, the minimum
  qualifying-month count, the presence floor, the divisor rule, the comparison
  bands, the anomaly ratio, and the Comparable / Uncomparable split. Primitives in,
  values out; no session, no ORM import.
* A new service owns the queries: per-month classification coverage by amount,
  sync coverage from sync session records, and per-month per-category totals with
  the same-day cutoff. The summary service composes it and depends on a narrow
  contract — "the baselines for this month" — rather than on a broad repository API.
  The summary service is already 600 lines mixing SQL and policy, which ADR-0001
  names as a smell; this does not add to it.
* Every query reuses the existing Effective Date helper for month placement, the
  existing Ignored exclusion, and the existing category-type filters. Transfers stay
  out of spend because the spend query already restricts to expense categories.
* Archived Categories are excluded from the comparison list. They keep their
  historical figures per ADR-0007, but a retired category reporting itself below
  baseline every month for ever is noise, not information.

### API contract

Baselines ride on the existing summary endpoint as **new fields, none removed**,
following Phase 8's precedent. This is also what keeps the data-fetching hook
unchanged: a separate endpoint would add a second fetch, a second loading state and
a concurrency seam.

Month-level additions: a baseline status naming the state; the qualifying-month
count the baselines rest on; the comparable spend for the month with its baseline;
the uncomparable spend total; and baselines for income and net cash flow.

A **new per-category list**, separate from the existing budget-usage list. The
existing list is built from active budgets and would silently omit any category
with spend and no budget, which is precisely the spend `Unbudgeted Spend` exists to
disclose. Each entry carries the category, its spend for the month, its baseline
(absent below the presence floor), the months that baseline rests on, the deviation
percentage, and the comparison status.

Nullable amounts rather than zeros wherever a baseline is absent, for the reason
ADR-0002 already records for the allowance: a zero reads as a real figure.

### Presentation

A second line beneath figures the owner already reads — no new page. The dashboard
carries the comparison under monthly spending and income; the Categories page
carries it per row; the Telegram summary gains one line and omits it when there is
no baseline. The interfaces read the status and render words; they compute no bands
and no percentages beyond what the payload states.

### Measurement is part of the work

The month window is already non-sargable and plans as a sequential scan, and this
reads three months where one was read before. Request cost for the summary endpoint
is measured before and after, and the figure is recorded. The roadmap requires
measurement before any snapshot table is considered, and this is that measurement,
not a licence to build one. The before-figure is recorded below, under
**Recorded Measurement**.

## Testing Decisions

A good test here asserts what the owner would read or what the API states, never how
it was computed. The bands are asserted as worked examples, not as the expression
that produced them.

**Four seams, confirmed before writing this spec. No test is written anywhere else.**
Four of the six seams the repository already has are reused and no new seam is
created.

**1 — The pure domain functions.** A new module at the existing pure-domain seam.
Carries essentially all of this feature's risk, as a table of worked examples:
whether a month qualifies, against both coverage tests; the minimum qualifying-month
count and the `insufficient_history` state; the presence floor; the divisor over
window months rather than present months; the five comparison bands at their
boundaries; the anomaly ratio and that it is one-sided; and the Comparable /
Uncomparable split, including the October-shaped case where one uncomparable
category exceeds the whole comparable total. Primitives in, values out, no fixture,
so the combinatorial cases are cheap. Prior art: the existing domain metrics tests.

**2 — The summary service**, through the `month` and `today` parameters it already
accepts. Carries the SQL and the wiring: coverage computed by amount; only closed
months qualifying; the same-day cutoff for the current month; per-category presence
across months; the new fields populated; the new per-category list including a
category with spend and no budget; Archived Categories excluded; Ignored rows
excluded; and a regression that every pre-existing field is unchanged. This is not a
second copy of seam 1 — seam 1 asks whether the rule is right, seam 2 asks whether
it is wired to the right query. Prior art: the existing summary service tests.

**3 — The Telegram summary formatter**, dict in, string out. The comparison line,
and its absence under `insufficient_history`. Prior art: the existing formatter
tests.

**4 — Page rendering** through `renderToStaticMarkup` with props supplied directly,
asserting on the wording the owner would read. The second line under the dashboard
figures, the per-row comparison on the Categories page, the disclosed uncomparable
total, and that nothing is claimed when there is no baseline. Prior art: the
Categories page tests added by Phase 8's ticket 18.

**Not seams:** the summary HTTP route, whose response-shape assertions are extended
but which would otherwise re-test seam 2 through HTTP; and the data-fetching hook,
which does not change because the fields ride on an existing response.

### The fixture trap this feature has, named in advance

`AGENTS.md` records that a test double which agrees with the code cannot disagree
with it. The analogue here is specific and it is the single most likely way this
feature ships broken:

**A fixture whose months are all cleanly classified cannot observe the coverage rule
at all.** If every fixture month is fully classified, the coverage floor is
unobservable, and so is the entire distinction between measuring coverage by amount
and by rows — the defect that would have admitted a two-thirds-empty month as clean.

So the fixtures must include a month shaped like the owner's June: a small number of
unclassified rows carrying most of the month's money. A second fixture month must
have the inverse shape — many unclassified rows carrying very little — so that the
two measures give opposite verdicts and only the amount-based one can pass both.

### Mutations to run, with the expected failure

Every test here is written after the behaviour it describes is specified, so none of
them has been shown to have teeth until it is broken deliberately. Each of these
must put something red:

* measure coverage by row count instead of by amount → the June-shaped month test
* divide by months present instead of window months → the one-off category test
* drop the presence floor → the single-month category test
* admit the current month as a qualifying month → the self-comparison test
* compare the current month against whole past months → the same-day cutoff test
* include uncomparable categories in the aggregate → the October-shaped test
* fire the anomaly downward as well → the below-baseline test
* check only classification coverage, not sync coverage → the sync-hole month test

### Fixtures pin the clock

Phase 8 lost a test to this: one passed under its own mutation because the fixture's
dates happened to work out against the month the suite ran in. This feature is
*entirely* about relative months, so every fixture fixes "today" through the
injectable clock the repository already has, and no fixture reads the real date. The
existing month-boundary instants in the shared test configuration are reused for the
timezone cases.

## Out of Scope

* **All of 9b**: Recurring Charge detection, the subscription inventory, and
  price-change detection on recurring items. Separate spec. The term `Recurring
  Charge` was settled during design and belongs to that spec. Note for whoever takes
  it: an automated round-up transfer in the owner's data is 232 near-identical rows
  across four months and will be the first thing any naive matcher detects, while
  being a transfer that must never appear in a subscription inventory.
* **The last open Phase 8 gap** — carrying a manual categorization across the
  pending-to-booked transition. It needs the identity matching that belongs with 9b.
* **Historical backfill.** Considered and dropped. The owner already has five months
  of history, so the question is moot; and it was the wrong idea anyway, because both
  the spend and income queries inner-join the category table, so an unclassified
  transaction counts toward nothing. A backfill would deliver zero baseline value
  plus a review backlog, and the value would only arrive as the owner cleared it.
* **An owner-declared "circumstances changed" date.** Designed, then dropped once the
  presence floor was shown to retire a stopped category automatically. The residual
  case it would address — a category that survives a change of circumstances at a new
  level — self-corrects as the window moves, in about as long as it would take the
  owner to trust a date they set by hand.
* **Median or trimmed-mean baselines.** Revisit at four or more qualifying months.
* **Per-transaction anomaly flagging.** Needs a per-transaction distribution the data
  cannot yet support.
* **A baseline on Safe to Spend Today.** Comparing the allowance across months mixes
  three things that all moved; the baseline belongs on spend.
* **Snapshot tables.** The roadmap requires measurement first, and this spec measures.
* **Proactive alerting.** Phase 10. 9a makes the comparison visible; it does not make
  the product speak first.

## Recorded Measurement

### Before (ticket 01, taken 2026-10-26, against commit `20592fe`)

Against the owner's live database, 623 transactions.

| Case | Month | SQL statements | Cold | Warm median |
|---|---|---|---|---|
| Current month | 2026-10 | 6 | 48.6 ms | 11.8 ms |
| Closed month | 2026-09 | 6 | 10.0 ms | 10.0 ms |

Taken twice. The statement count was 6 both times and the warm medians moved by
0.5 ms and 0.0 ms. Warm min/max across ten runs spanned 9.2 to 13.8 ms, so **wall
time carries roughly +/-15% of noise on a development machine, and the statement
count is the stable signal.** It is also the figure that predicts what this feature
costs, because the growth is in how many month windows get scanned, not in how fast
one scan runs. Ticket 06 should compare statement counts first and treat a wall-time
move inside that band as noise.

Both cases cost the same today, and that is the thing to watch rather than a
curiosity: nothing in the current summary reads a month other than the one
requested, so a closed month and the current one scan the same number of windows.
After this feature they will not, and the current month should become the more
expensive of the two because of the same-day cutoff.

### After (ticket 06, taken 2026-10-26, against commit `a965f76`)

Same 623 transactions and the same pinned inputs. The harness was read out of the
block below and run in a one-off container from a rebuilt image, so that the
branch's code met the live database without restarting the owner's stack.

| Case | Month | SQL statements | Warm median | Before |
|---|---|---|---|---|
| Current month | 2026-10 | 13 | 37.1 ms | 6 / 11.8 ms |
| Closed month | 2026-09 | 15 | 35.6 ms | 6 / 10.0 ms |

**Ticket 01's prediction was wrong, and in the opposite direction.** It said the
current month should become the more expensive of the two, and that finding them
still equal would mean something was broken. They are not equal — but the *closed*
month costs more. The cutoff is not what drives the cost: `_month_qualifies` tests
sync coverage first and returns before running the two classification queries, so
what a candidate month costs depends on **which test it fails**, not on how many
months end up qualifying. Viewing September, two of its three candidate months pass
the sync test and go on to the classification queries; viewing October, only one
does. Four queries against two, and 15 − 13 = 2 accounts for the difference exactly.

That makes the measurement **data-dependent**, which is the more useful finding: the
same code over the same month costs 13 statements or 16 depending on whether the sync
history has a hole in it.

### These figures are a lower bound, because the owner's data is holed

Both cases report `baseline_status: insufficient_history` with **zero** Qualifying
Months, so most of the per-qualifying-month work never ran at all. The live figures
measure the cheap path.

The ceiling is measured separately, over an in-memory fixture at the default
three-month window. The queries are the same, so the statement counts carry over; the
timings would not and are not quoted.

| Qualifying Months | SQL statements |
|---|---|
| 0 | 16 |
| 2 | 22 |
| 3 | 25 |

Each Qualifying Month costs three more statements — its per-category spend and its
two aggregate totals — and each candidate month that passes the sync test costs two
more for classification coverage. The count is therefore bounded by the **window**,
and does not move with how much history accumulates behind it.

### The snapshot-table decision: no, with a named trigger for revisiting it

**No snapshot table.** Recorded as the decision rather than left implicit.

25 statements and roughly 37 ms, over one owner's 623 transactions, for a screen they
open a few times a day. `AGENTS.md` ranks performance last of five, and `schema.md`
already records that single-owner volumes make the non-sargable month window
immeasurable in practice. Transactions accrue at roughly 80 to 190 a month, so five
years of history is some 8,000 rows: still a trivial sequential scan, and the
statement *count* does not move with it at all.

What would change the answer is **widening the baseline window**, which is the one
thing this design actively invites — `BASELINE_WINDOW_MONTHS` exists so the reach can
grow as history does. At twelve months the same arithmetic gives roughly seventy
statements per summary request. So the trigger to revisit this is a window change
rather than the passage of time, and the cheap mitigation then is the one `schema.md`
already names for these same queries: an expression index on the coalesce, or the
stored `effective_date` column Phase 8 deferred. A snapshot table stays the last
resort rather than the next step.

---

### The harness

Pinned inputs, so that ticket 06 repeats this measurement rather than taking a
different one. Both the requested month and `today` are fixed: `today` is injectable
on the service, and leaving it to the wall clock would silently change which case is
"the current month" as soon as the calendar moves past October.

Run from the repository root, against the running stack:

```
docker compose exec -T backend python - <<'PY'
import statistics, time
from datetime import date
from sqlalchemy import event, text
from burnrate.db.session import SessionLocal, engine
from burnrate.services.summary_service import SummaryService

RUNS = 11
CASES = [("2026-10", date(2026, 10, 26), "current month"),
         ("2026-09", date(2026, 10, 26), "closed month")]

statements = []
@event.listens_for(engine, "before_cursor_execute")
def _count(conn, cursor, stmt, params, context, executemany):
    statements.append(stmt)

with SessionLocal() as db:
    scope = db.execute(text("SELECT count(*) FROM transactions")).scalar()
    print(f"transactions in database: {scope}")
    for month, today, label in CASES:
        svc = SummaryService(db=db, timezone_name="Europe/Madrid")
        times = []
        for i in range(RUNS):
            statements.clear()
            t0 = time.perf_counter()
            svc.get_summary(month=month, today=today)
            times.append((time.perf_counter() - t0) * 1000)
            if i == 0:
                n_stmts = len(statements)
        cold, warm = times[0], times[1:]
        print(f"\n{month} ({label}), today={today}")
        print(f"  SQL statements : {n_stmts}")
        print(f"  cold           : {cold:.1f} ms")
        print(f"  warm median    : {statistics.median(warm):.1f} ms  (n={len(warm)})")
        print(f"  warm min/max   : {min(warm):.1f} / {max(warm):.1f} ms")
PY
```

The first run of each case is reported separately rather than averaged in, because
it carries cold cache and connection setup; the median of the remaining ten is the
comparable figure. It measures the service rather than the HTTP route deliberately:
the route adds authentication and response validation this feature does not touch,
and the service takes `today` as a parameter, which is what makes the measurement
repeatable at all.

---

## Further Notes

The design came out of a grilling session whose record is worth keeping in one
respect: **three of its decisions were reversed by querying the owner's live
database rather than by argument.** A historical backfill was recommended and
dropped; a coverage measure by rows was assumed and replaced by amount; and an
owner-declared break date was recommended, accepted, and then removed once the
presence floor was shown to cover it. Each reversal came from a measurement, not
from a second opinion.

The live figures that drove the design, as of 2026-10-26, so that a future reader
can tell whether the ground has moved:

| Month | Outgoing | Unclassified by amount | Qualifies |
|---|---|---|---|
| 2026-06 | 7002.82 | 66.6% | no |
| 2026-07 | 8602.36 | 57.6% | no |
| 2026-08 | 2858.00 | 0.0% | no — see below |
| 2026-09 | 2566.53 | 0.0% | no — see below |
| 2026-10 | 9479.13 | 2.2% | current month |

Expense-only spend for June through September is 2278.96, 2883.25, 2577.11 and
2548.65 — the roadmap's premise that a salaried owner's levels are stable holds, and
holds to within about ±12%, which is where the `in_line` tolerance comes from. The
apparent volatility in the outgoing column is an artefact of transfers.

**The claim this section originally made was wrong, and ticket 06 corrected it.** It
read: "the feature ships with exactly two qualifying months, which is exactly the
minimum — baselines work from day one, by one month's margin." It ships with
**zero**. That claim was computed from classification coverage alone, before the
sync-coverage rule existed to disagree with it, and the table above is exactly the
measurement that could not see the problem — which is why its verdict column now
defers.

**Ticket 03's rule found a real 36-day hole in the owner's live data**, from
2026-08-29 to 2026-10-04, wider than the 30-day fetch window, which nothing else in
the system reported. Running both coverage tests over the live database, month by
month:

| Month | Sync covered | Unclassified | Qualifies |
|---|---|---|---|
| 2026-06 | yes | 66.6% | no — classification |
| 2026-07 | yes | 57.6% | no — classification |
| 2026-08 | **no** | 0.0% | no — never asked about |
| 2026-09 | **no** | 0.0% | no — never asked about |
| 2026-10 | not yet | 2.2% | not yet — the month is still open |
| 2026-11 | not yet | — | not yet |

So the two months that looked cleanest are the two straddling the gap, and **they can
never qualify**: no entry point can request a window older than 30 days, so the days
from 30 August to 3 September will never be fetched. The expense totals quoted above
for August and September are understated by whatever fell in them.

Two things follow, and the second is the useful one:

* **Left alone, the feature starts working in December 2026.** Viewing December, the
  window reaches September, October and November; October and November will both
  qualify once closed, given continuous syncs and classification above the floor.
  Every earlier view has at most one Qualifying Month within reach.
* **Or it works today, for the price of one setting and some classification.** June
  and July *are* sync-covered; only the backlog disqualifies them. Classifying it and
  setting `BASELINE_WINDOW_MONTHS=5` puts both inside October's window, which is two
  Qualifying Months and a working comparison. That this is an environment variable
  rather than a migration is the whole return on refusing a stored accumulator.
