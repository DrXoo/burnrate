# 03: A month the bank never saw stops counting

**What to build:** The second, independent test a month must pass to be a Qualifying
Month. A month spanned by a gap in successful syncs wider than the provider fetch
window stops counting toward any baseline, so a lapsed consent or a stopped worker
cannot quietly understate what the owner normally spends.

This is invisible to ticket 02's coverage test and that is the whole point: a month
with a sync hole looks perfectly classified, because every row it does have is filed,
while transactions are missing outright.

**Blocked by:** 02.

**Status:** ready-for-agent

- [ ] A month not spanned by successful syncs, with no gap wider than the provider fetch window, is not a Qualifying Month
- [ ] A month with complete classification coverage but a sync hole is excluded — the case the coverage test in ticket 02 cannot observe
- [ ] Only successful syncs count as coverage; a failed or truncated sync does not
- [ ] The rule is decided in the domain over a series of sync instants, so it is exercised without a database fixture
- [ ] It is derived from the sync session records that already exist: no new table and no migration
- [ ] When excluding such a month drops the Qualifying Month count below the minimum, the status reports insufficient history rather than quietly showing a thinner baseline
- [ ] Checking only classification coverage and not sync coverage puts the sync-hole test red
