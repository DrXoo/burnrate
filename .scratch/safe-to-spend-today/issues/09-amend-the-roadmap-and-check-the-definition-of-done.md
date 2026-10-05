# 09: Amend the roadmap and check the Definition of Done

**What to build:** The roadmap describes the phase that actually shipped, and
every item of its Definition of Done is checked rather than assumed. This exists
as its own gate because Phase 3 was recorded as complete while its headline
metric was missing, and the gap went unnoticed for six phases.

**Blocked by:** 01, 07, 08

**Status:** ready-for-agent

- [ ] Phase 8's scope in the roadmap matches what shipped, with a line on why it grew beyond "a derivation, not new accounting"
- [ ] The Definition of Done gains the clause: a Pending charge reduces the allowance the day it appears, and a Pending row that later books is not counted twice
- [ ] Every Definition of Done item is checked against the implementation, and the result recorded
- [ ] The deliberately unchanged per-category budget threshold is recorded as a choice, not left as an oversight
- [ ] The schema doc is confirmed untouched, since this phase carries no migration
- [ ] Any gap found is recorded explicitly in the roadmap rather than left implicit
