# 02: A category's spend shown against its own baseline

**What to build:** On the Categories page, each category row shows its spend for the
month on screen beside what that category normally costs the owner, with a verdict —
or states plainly that it has no baseline. This is the tracer bullet for the whole
feature: it carries the Qualifying Month rules, the baseline arithmetic, the bands,
and the first interface, end to end.

It comes first because the aggregate comparison in ticket 04 is *defined* in terms of
which categories have a baseline, so it cannot be built before this.

**Blocked by:** 01.

**Status:** ready-for-agent

- [ ] A category with spend in at least the presence floor's number of Qualifying Months shows its spend beside its baseline and the deviation as a percentage
- [ ] A category below the presence floor shows no baseline and says so; no monthly figure is invented for a category the owner spent in once
- [ ] A month whose unclassified outgoing amount exceeds the coverage floor is not a Qualifying Month, and coverage is measured **by amount**: a month with few unclassified rows carrying most of its money is excluded, while a month with many unclassified rows carrying very little is admitted
- [ ] The current month is never a Qualifying Month for its own baseline
- [ ] Below the minimum Qualifying Month count the baseline status says so and no baseline is shown anywhere
- [ ] The baseline divides by the Qualifying Months the window reaches, not by the months the category happened to appear in
- [ ] For the current month, each Qualifying Month contributes only spend up to the same day of the month, clamped to that month's last day, so a part-month is never measured against a whole one
- [ ] A closed month is compared whole against whole
- [ ] A month that has not started makes no comparison
- [ ] One status names the whole judgement across its five states; the page renders words and computes no band and no percentage the payload does not state
- [ ] An anomaly is raised only when spend is at or above the baseline times the anomaly ratio; spend below the baseline reports the deviation and raises nothing
- [ ] The number of Qualifying Months the baseline rests on is in the payload and on screen
- [ ] Archived Categories are absent from the comparison list
- [ ] Ignored transactions count toward neither the month's figure nor any baseline
- [ ] Transfers count toward neither, by the existing category-type restriction
- [ ] The per-category list includes a category with spend and no active budget, which the existing budget-usage list would omit
- [ ] The baseline window is read from settings with a default of three months
- [ ] Every pre-existing summary field is unchanged, asserted as a regression
- [ ] No migration, no new table, and nothing stored: every figure is recomputed from transactions on each request
- [ ] Tests live only at the pure-domain seam, the summary service seam, and page rendering. Nothing is tested elsewhere
- [ ] Fixtures include a month shaped like the owner's June — a few unclassified rows carrying most of the money — and a month of the inverse shape, so that a row-based coverage measure cannot pass both
- [ ] Every fixture pins "today" through the injectable clock; no fixture reads the real date
- [ ] Each of these mutations puts something red: measuring coverage by row count; dividing by months present; dropping the presence floor; admitting the current month as a Qualifying Month; comparing the current month against whole past months; firing the anomaly downward
