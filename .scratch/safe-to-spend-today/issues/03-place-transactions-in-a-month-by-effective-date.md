# 03: Place transactions in a month by Effective Date

**What to build:** A transaction with no booking date stops being invisible to
the month it belongs to. On its own this is a bug fix the owner can see: an
uncategorized Pending charge now reaches the review queue instead of vanishing.
It is also the prerequisite for Pending spend counting at all, because a null
booking date never satisfies a month-window comparison in SQL.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] One shared helper resolves a transaction's Effective Date as its booking date, then its value date, then its import date
- [ ] Every month-windowed summary query uses that helper rather than repeating the rule
- [ ] A transaction with no booking date but a value date inside the month is counted in that month
- [ ] An uncategorized Pending transaction with no booking date appears in the review queue
- [ ] Every pre-existing Booked figure is unchanged to the cent, asserted by a regression test over the existing seeded summary
- [ ] The domain doc records Effective Date
