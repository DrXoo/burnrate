# A month the bank was never asked about is not baseline input

A Qualifying Month — a closed month trusted as baseline input — must pass **two
independent coverage tests**, not one. The obvious test is classification
coverage: the share of the month's outgoing *money* that is still unclassified
must be under a floor. The second is sync coverage: the month must be spanned by
the trailing fetch windows of **successful** syncs, so that the bank was actually
asked about every one of its days.

Both are needed because each is blind to the other, and the blindness is not
hypothetical. **A month with a sync hole looks perfectly classified**: every row
it does have is filed, so classification coverage reports 0.0% unfiled while
transactions are missing outright. The resulting baseline is understated, and an
understated baseline makes ordinary spend read as an anomaly — the over-firing
the roadmap says Phase 10 fails by.

Measured against the owner's live database on 2026-10-26, the two tests disagree
about which months to trust, and the one-test version is wrong:

| Month | Sync covered | Unclassified share of outgoing | Qualifies |
|---|---|---|---|
| 2026-06 | yes | 66.6% | no — classification |
| 2026-07 | yes | 62.9% | no — classification |
| 2026-08 | **no** | 0.0% | no — never asked about |
| 2026-09 | **no** | 0.0% | no — never asked about |
| 2026-10 | not yet | 2.2% | not yet — month still open |

The two months that read cleanest in the entire dataset are the two straddling a
**36-day sync hole, 2026-08-29 to 2026-10-04**, which is wider than the 30-day
provider fetch window. The sync-coverage rule found it; nothing else in the
system reports it.

## Why this is hard to reverse

**Those two months can never qualify.** No entry point can request a window
older than 30 days, so 30 August to 3 September will never be fetched by
anything. August's and September's spending totals are understated by whatever
fell in those days, permanently, and so is every figure BurnRate has ever
reported for them. Relaxing this rule would not recover the data; it would only
stop the product saying so.

The consequence the owner lives with: the feature **ships reporting no comparison
at all**, `insufficient_history` with zero Qualifying Months, on a dashboard where
everything else looks healthy. Left alone it starts working in December 2026, when
October and November are both closed and inside the window. It can be made
demonstrable today by classifying the June and July backlog — both months *are*
sync-covered — and setting `BASELINE_WINDOW_MONTHS=5`, which is an environment
variable rather than a migration for the reason ADR-0008 records.

## Consequences

**Only `success` counts.** An expired consent writes a `skipped` session per
attempt and fetches nothing, so counting session rows rather than successes would
read the months the owner was disconnected as the best-covered months there are.
`started_at` is the field read, not `finished_at`: it is always set, and it is
far closer to the moment the sync read the owner's today to derive its window
from.

**Coverage is by chain, not by single window.** A run on day S asked about
`[S - fetch window, S]`, so a month is covered when those windows *union* to span
it: two runs 25 days apart cover a month between them although neither does
alone, and a cron that slows from daily to weekly produces exactly that. The
mutation that judged each window against the month's first day instead survived
all nine original domain examples, because every one of them was covered by a
single window or failed outright — it would have disqualified healthy months and
silently thinned every baseline.

**Widening the provider fetch window now makes more months qualify as baseline
input.** That was not previously one of its consequences; it has a fourth reader
and `enable-banking.md` says so.

**Nothing alerts the owner to a sync gap.** The product carries on reporting
figures for months it never fully fetched, and that silence is now load-bearing
for Phase 9's value. It is the one case where the product knows something the
owner cannot see, which makes it the strongest candidate for Phase 10's first
alert.

## Considered Options

**Classification coverage alone** was the planned design and is the cheaper one —
it needs no sync history and no window arithmetic. Rejected on the owner's own
data, where it calls the two holed months the cleanest in the dataset and admits
them as the baseline for everything that follows.

**Counting rows rather than money** for the classification half was rejected for
the same class of reason: the owner's June 2026 reads 79% classified by row count
and 33% by amount, because the rows not yet filed were the large ones. A
row-based test admits such a month and then biases every category's baseline
downwards with nothing anywhere to signal it. The rule is unfalsifiable at the
pure-domain seam — `month_qualifies` takes amounts, so its signature already
encodes the decision — which is why the discriminating test lives at the service
seam, over three months shaped so that the two measures find the same *count* of
qualifying months and different baselines.
