# 06: Measure again, and settle the snapshot-table question

**What to build:** The after-figure for the summary endpoint's request cost, taken by
ticket 01's method against the same month and scope, and a recorded decision about
whether a monthly snapshot table is warranted. The month window is already non-sargable
and plans as a sequential scan, and this feature reads several months where one was read
before, so the roadmap requires the question be answered on evidence.

**Blocked by:** 03, 04.

**Status:** ready-for-agent

- [ ] The request cost is measured again by ticket 01's method, against the same month and the same transaction scope
- [ ] The delta is recorded against ticket 01's figure
- [ ] A decision about snapshot tables is written down with its reasoning. If the cost is acceptable, that is recorded as the decision rather than left implicit
- [ ] If the decision is to introduce one, it is recorded as future work rather than built here; this ticket measures and decides, it does not optimise
- [ ] The relevant docs are updated in the same change, per the documentation rules
