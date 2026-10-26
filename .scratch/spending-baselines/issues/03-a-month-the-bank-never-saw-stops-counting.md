# 03: A month the bank never saw stops counting

**What to build:** The second, independent test a month must pass to be a Qualifying
Month. A month spanned by a gap in successful syncs wider than the provider fetch
window stops counting toward any baseline, so a lapsed consent or a stopped worker
cannot quietly understate what the owner normally spends.

This is invisible to ticket 02's coverage test and that is the whole point: a month
with a sync hole looks perfectly classified, because every row it does have is filed,
while transactions are missing outright.

**Blocked by:** 02.

**Status:** done

- [x] A month not spanned by successful syncs, with no gap wider than the provider fetch window, is not a Qualifying Month
- [x] A month with complete classification coverage but a sync hole is excluded — the case the coverage test in ticket 02 cannot observe
- [x] Only successful syncs count as coverage; a failed or truncated sync does not
- [x] The rule is decided in the domain over a series of sync instants, so it is exercised without a database fixture
- [x] It is derived from the sync session records that already exist: no new table and no migration
- [x] When excluding such a month drops the Qualifying Month count below the minimum, the status reports insufficient history rather than quietly showing a thinner baseline
- [x] Checking only classification coverage and not sync coverage puts the sync-hole test red


## Comments

**Done.** 13 new tests; 441 backend and 52 web pass. A month is now a Qualifying
Month only if it passes both coverage tests, and the second one is decided in the
domain over a series of civil sync days with no database in sight.

Red first on both cycles: the domain rule by its absent import, then all three
service tests at once.

### The mutation that survived, and the case it was hiding

Judging each window against **the month's first day** instead of against what is
still unaccounted for passed all nine of the original examples. The two rules are
not equivalent — the mutant rejects months the real rule accepts — and none of the
examples could tell, because every one of them was covered by a *single* window or
failed outright.

What separates them is coverage by **chain**: two runs 25 days apart, neither of
whose windows spans the month, that overlap and so reach every day of it between
them. `[Aug 21, Sep 20]` and `[Sep 15, Oct 15]` cover September; the mutant sees
the second window opening after the month did and rejects it. A cron that slows
from daily to weekly produces exactly this, so the mutant would have disqualified
healthy months and silently thinned every baseline.

Three cases added — a two-window chain, a three-window chain, and a chain broken by
one day — and the mutation now dies on the first two. This is the second surviving
mutation in this feature and the second time the gap was invisible to reading.

### The fixture consequence nobody would have noticed in review

Turning this rule on would have broken **all sixteen** of ticket 02's service tests
at once, because that fixture seeds no sync sessions at all, so no month would have
qualified. The fix is not a per-test patch: `Fixture` now seeds a daily successful
history by default and sync-coverage tests opt out with `synced=False`. Every other
test in the module is about classification coverage, and a sync hole in those would
be an unrelated confound rather than a stricter assertion.

### Decisions taken here

* **`started_at`, not `finished_at`.** It is the field that is always set --
  `finished_at` is nullable, and a crashed run has none -- and it is far closer to
  the moment the sync read the owner's today to derive its window from.
* **Only `success` counts, and `skipped` is the status that matters.** An expired
  consent writes a `skipped` session per attempt and fetches nothing, so the gap it
  opens is papered over with an unbroken chain of session rows. Anything counting
  rows rather than successes would read the months the owner was disconnected as the
  best-covered months there are. That case has its own test, identical to the
  sync-hole test except for the attempts filling the gap, and the mutation that
  admits every status kills exactly that one test.
* **`_TRANSACTION_WINDOW` is now public `TRANSACTION_WINDOW`.** Baseline coverage is
  a fourth reader of it, and `enable-banking.md` is explicit that all readers derive
  from one value rather than restating 30 -- restating it is how a hold that booked
  across a month boundary came to be deleted and never re-imported. The doc now says
  four readers, and says that widening this window makes more months qualify as
  baseline input, which was not previously one of its consequences.
* **Sync days are fetched once per request, not per candidate month.** The rule needs
  runs from *after* a month as well as during it, since a window reaches backwards,
  so there is one query bounded below by the oldest candidate month less a day for
  the timezone conversion.
* **Coverage is judged in civil days, not UTC instants**, because the window the sync
  actually used was derived from the owner's own today.

### Noted, not fixed

`as_utc` lives in `services/connection_expiry.py`, and its own docstring says it is
for a datetime read back naive from SQLite -- a clock concern in a consent-window
module. It is imported from there rather than duplicated, and rather than moved:
`AGENTS.md` forbids riding a refactor along on a feature. A candidate for the review
stage.

### Mutations run

| Mutation | Result |
|---|---|
| Gap measured against the month's first day | **survived**, then fixed; now 2 chain examples |
| Gap check removed entirely | 2 domain examples |
| Off-by-one on the month's end | 1 domain example |
| Sync coverage not consulted at all | all 3 service tests |
| Every session status counts as coverage | the expired-consent test, exactly |
| Fetch window not read from the one constant | all 3 service tests |

### For ticket 06

One more query per request, plus the coverage pair per candidate month that ticket
02 already added. The sync query is bounded by date but unbounded in rows within
that bound, so a frequent cron makes it grow; it returns instants and dedupes to
civil days in Python, which is the part to look at if the measurement surprises.
