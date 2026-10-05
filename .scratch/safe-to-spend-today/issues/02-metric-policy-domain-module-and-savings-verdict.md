# 02: Metric-policy domain module, and the savings verdict leaves the Web UI

**What to build:** The owner's savings rate and its verdict come from the
backend, so the Web UI and the bot cannot disagree about how the month is going,
and the dashboard's two differently-labelled copies of the same figure collapse
into one. This also creates and proves the pure domain module that the headline
metric will land in, by moving an existing threshold into it first without
changing any behaviour.

**Blocked by:** None (can start immediately)

**Status:** done

- [x] A pure domain module holds metric policy, with no database session and no ORM import
- [x] The existing budget-usage threshold moves into it with no behaviour change: the existing summary tests pass untouched
- [x] The summary exposes the savings rate as a percentage and a savings status reusing the existing on-track / watch / over vocabulary
- [x] Net Cash Flow is the single source for what the dashboard currently shows twice as "saved" and "net"; the duplicate tile is gone
- [x] No monetary arithmetic or threshold comparison remains in the Web UI's savings path
- [x] Domain tests cover the savings bands as a table of worked examples, with no database fixture
- [x] Expected values come from worked examples, not recomputed the way the implementation computes them

## Comments

Implemented test-first at the spec's seams 1 and 2. Seam 1 is new:
`backend/tests/test_domain_metrics.py`, two parametrized tables of worked
examples, no fixture. Seam 2 gained two cases in `test_summary_service.py`: the
new fields off the existing June fixture (2000.00 income, 260.00 spend, so
1740.00 kept = 87.0%), and the budget-row ordering that the sort cleanup below
rewrote. Deliberately not a second copy of seam 1 -- seam 1 asks whether the band
is right, seam 2 whether it is wired to the right query. The pre-existing summary
tests were not edited, which is the protection the threshold move relied on.

Three notes for the distill step, as settled after `/code-review`:

* **A month with no income reads `on_track`, not `watch`.** My first pass
  preserved the old UI rule (`rate < 0.1` with the rate pinned to 0 when income
  was 0), which put the gauge in amber on the 1st of every month until a salaried
  owner's pay books -- a warning that fires every month regardless of behaviour,
  which is the exact failure mode ADR-0002 rejects for the headline. The band is
  now: overspent is `over` whether or not anything came in; no income yet is
  `on_track`; a real income with under a tenth kept is `watch`. Both the
  no-income rows and the `income 2000, net 0 -> watch` row are in the table, so
  the distinction is pinned.
* **The band is read off the rate rounded to one decimal, and the UI prints that
  same figure.** The first pass banded at 0.1 precision while the dashboard
  printed a whole percent, so a 9.8% month rendered "10%" in amber -- the exact
  thing I had claimed was impossible, asserted in three places. The owner now
  reads "87.0%", and the invariant holds because the figure shown and the figure
  banded are one value.
* **`useHeroModel`'s 85% pacing threshold is still in the Web UI.** Out of scope
  here -- this ticket's line is the savings path -- and ticket 07 replaces that
  verdict with `safe_to_spend_status`, which does not exist yet. Moving it now
  would be work ticket 07 then undoes.

Shape changes the review prompted, all behaviour-neutral and covered:

* `savings_rate_percent` and `savings_status` collapsed into one
  `savings_verdict()` returning a frozen `SavingsVerdict`. The rate was otherwise
  derived twice per request -- once for the payload, once inside the status -- and
  the pair makes "the band judges the figure you publish" structural rather than a
  convention someone has to keep.
* `MetricStatus = Literal["on_track", "watch", "over"]` is declared in the domain
  module and imported by the API schema, so the policy and the contract share one
  source. Previously the domain returned a bare `str` while the schema pinned the
  three values, and a fourth band would have surfaced as a request-time `KeyError`
  in the sort or a 500 from Pydantic.
* `budget_usage` rows are now sorted by the status and utilization already on the
  serialized row, which deletes the second derivation of both. The two had already
  drifted -- the serializer quantized `remaining_amount`, the sort key did not --
  so the badge and the ordering could in principle have disagreed. The badge is
  now authoritative, and a new seam-2 test pins "worst row leads".
* `MetricCard`'s `valueColor` prop went with the duplicate tile that was its only
  caller.

The Web UI change could not be typechecked in this environment: there is no node
toolchain and no `web/node_modules`, so `tsc -b` runs only in the build. The edit
is confined to `useSavingsModel`, the `SummaryDashboard` type and the removal of
the duplicate `Net this month` tile; nothing referenced the removed `net` local
or the dropped `rate` field.
