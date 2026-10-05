# 02: Metric-policy domain module, and the savings verdict leaves the Web UI

**What to build:** The owner's savings rate and its verdict come from the
backend, so the Web UI and the bot cannot disagree about how the month is going,
and the dashboard's two differently-labelled copies of the same figure collapse
into one. This also creates and proves the pure domain module that the headline
metric will land in, by moving an existing threshold into it first without
changing any behaviour.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] A pure domain module holds metric policy, with no database session and no ORM import
- [ ] The existing budget-usage threshold moves into it with no behaviour change: the existing summary tests pass untouched
- [ ] The summary exposes the savings rate as a percentage and a savings status reusing the existing on-track / watch / over vocabulary
- [ ] Net Cash Flow is the single source for what the dashboard currently shows twice as "saved" and "net"; the duplicate tile is gone
- [ ] No monetary arithmetic or threshold comparison remains in the Web UI's savings path
- [ ] Domain tests cover the savings bands as a table of worked examples, with no database fixture
- [ ] Expected values come from worked examples, not recomputed the way the implementation computes them
