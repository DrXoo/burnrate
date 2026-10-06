# 07: Lead the dashboard with Safe to Spend Today

**What to build:** The owner opens the dashboard and the first thing they see is
what they can spend today, with the balance still visible beneath it for
reassurance. This is the ticket that satisfies the phase's Definition of Done:
the 40 EUR dinner question is answerable at a glance, and no financial rule is
left in the Web UI.

**Blocked by:** 06

**Status:** ready-for-agent

- [ ] The allowance is the dashboard headline, with current balance on the line directly beneath it
- [ ] Both existing gauges remain
- [ ] Unbudgeted Spend, Pending spend and Fixed Overrun are disclosed beside the headline when non-zero
- [ ] With no budgets set, the headline prompts the owner to set one rather than displaying zero
- [ ] For a past month the headline shows how that month finished against plan; for a future month it reads as planned rather than achieved
- [ ] No monetary arithmetic or threshold comparison remains in the Web UI: fractions driving an arc or a bar width stay, the pacing verdict and every threshold are gone
- [ ] The owner can answer "can I spend 40 EUR on dinner tonight" from one number, without reading a chart or doing arithmetic
- [ ] The type check passes with the allowance amount being nullable

## Comments

**Code review found the exact line this ticket's sixth criterion is about.**
`useHeroModel` in `web/src/components/pages/DashboardPage.tsx` computes
`budgetedSpend / budget >= 0.85` in TypeScript and derives its coach copy from the
result, while `BUDGET_USAGE_WATCH_PERCENT = Decimal("85.0")` lives in
`backend/src/burnrate/domain/metrics.py`. Change the band in the domain and the
per-category badges, the API `status` field and the Telegram output all move while
the hero gauge's colour and its wording stay behind.

The contrast is already in the file: `useSavingsModel`, forty lines below, carries
the comment "the page neither recomputes them nor sets a threshold of its own, so
the dashboard and the bot cannot disagree" — which is exactly what `useHeroModel`
does do. Ticket 02 moved the savings verdict out and left this one.

Nothing to fix ahead of time: ticket 06 delivers `safe_to_spend_status`, so the
hero's tone reads a backend field instead of comparing against a constant, and
this ticket rewrites that block anyway. Recorded so it is not rediscovered.
