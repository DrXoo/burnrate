# 05: Count Pending spend in the Variable slice

**What to build:** Last night's card payment reduces this month's figures before
the bank settles it, so the owner is not invited to spend the same money twice.
Fixed commitments keep being judged by their estimate until they settle, because
a partial hold on a bill would otherwise convince the product the bill is tiny.

The derivation has one trap worth stating: the Variable slice cannot be reached
by subtracting Booked fixed spend from total spending once Pending counts, or a
Pending charge in a Fixed Budget category lands in the Variable slice — the one
place it must never go.

**Blocked by:** 03, 04

**Status:** ready-for-agent

- [ ] Pending spend counts toward month-to-date spending, Budgeted Spend and the burn rate
- [ ] Booked fixed spend alone feeds the Fixed Budget step projection and the Fixed Overrun
- [ ] A Pending charge in a Fixed Budget category lands in neither the fixed nor the Variable slice
- [ ] A Fixed Budget with only a Pending charge still projects at its budgeted estimate
- [ ] Per-category Variable rows include Pending; Fixed rows stay Booked-only and keep their not-yet-paid presentation
- [ ] The summary exposes the Pending spend total so a movement in the figures has a visible cause
- [ ] The metric definitions and domain docs record that Pending counts in the Variable slice only, and that the asymmetry is deliberate
