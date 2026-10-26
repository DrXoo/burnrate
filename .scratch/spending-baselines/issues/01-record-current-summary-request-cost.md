# 01: Record the summary endpoint's current request cost

**What to build:** A recorded measurement of what the summary endpoint costs today,
against the owner's real data, before any baseline query exists. The roadmap requires
measurement before a snapshot table is even considered, and this is the half of that
measurement that can only be taken now — once the first baseline query lands, the
before-figure is gone for good.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] The summary endpoint's request cost is measured against the owner's live data and the figure recorded in the spec
- [ ] The measurement states which month was requested and how many transactions were in scope, so the after-figure can be compared like for like
- [ ] The method is written down precisely enough that ticket 06 can repeat it identically rather than inventing a second one
- [ ] No production code is changed by this ticket
