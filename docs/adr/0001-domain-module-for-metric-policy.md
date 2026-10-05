# A pure domain module for metric policy

Financial thresholds had drifted out of the backend: the savings-rate bands lived
in `web/src/components/pages/DashboardPage.tsx`, and `SummaryService` mixes SQL
with policy. Phase 8 both adds a rule and relocates one, so metric *policy* now
lives in `burnrate/domain/metrics.py` — pure functions over primitives, with no
`Session` and no ORM import. `SummaryService` queries and delegates.

The scope is deliberately narrow: only the rules Phase 8 touches move
(Safe to Spend Today, the budget-usage threshold, the savings-rate threshold).
The queries, the confidence-weighted projection blend and the fixed step
projection stay where they are. `AGENTS.md` forbids riding an architectural
rewrite along on a small feature, and this is a seam, not a restructuring.

## Considered Options

Another private method on `SummaryService` would have been consistent with the
code as it stands. Rejected: it leaves policy welded to SQL and untestable
without a database fixture, and the phase's second objective is precisely that
financial rules live in the domain rather than wherever the question got asked.

## Consequences

A reader will find one module with no ORM import while every other calculation
sits under `services/`. That is intentional — it is the seam, not an
inconsistency to be tidied away.
