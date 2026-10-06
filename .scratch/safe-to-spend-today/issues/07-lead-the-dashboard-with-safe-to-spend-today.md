# 07: Lead the dashboard with Safe to Spend Today

**What to build:** The owner opens the dashboard and the first thing they see is
what they can spend today, with the balance still visible beneath it for
reassurance. This is the ticket that satisfies the phase's Definition of Done:
the 40 EUR dinner question is answerable at a glance, and no financial rule is
left in the Web UI.

**Blocked by:** 06

**Status:** done

- [x] The allowance is the dashboard headline, with current balance on the line directly beneath it
- [x] Both existing gauges remain
- [x] Unbudgeted Spend, Pending spend and Fixed Overrun are disclosed beside the headline when non-zero
- [x] With no budgets set, the headline prompts the owner to set one rather than displaying zero
- [x] For a past month the headline shows how that month finished against plan; for a future month it reads as planned rather than achieved
- [x] No monetary arithmetic or threshold comparison remains in the Web UI: fractions driving an arc or a bar width stay, the pacing verdict and every threshold are gone
- [x] The owner can answer "can I spend 40 EUR on dinner tonight" from one number, without reading a chart or doing arithmetic
- [x] The type check passes with the allowance amount being nullable

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

---

## Implementation notes

**No red-green loop was available, and that was the spec's decision, not a shortcut.**
The spec's Testing Decisions name four seams and exclude this one: "not seams: ... the
dashboard, because `web/` has no test runner and installing one is not this phase's
work", with "the nullable amount is caught by the existing type check; the layout is
verified by looking at it". Installing a runner is also listed under Out of Scope. So
this ticket is presentation-only work behind an excluded seam. Three things were done
instead of writing tests at an unconfirmed seam.

**The type check was mutation-checked before being relied on.** Criterion 8 names it as
the gate, so it was given teeth rather than trusted. With
`safe_to_spend_today_amount: string | null` added to `SummaryDashboard`, passing it
unguarded to `eur()` was tried deliberately: `tsc` fails with
`error TS2345: Argument of type 'string | null' is not assignable to parameter of type
'string | number'`. `tsconfig.json` has `strict: true`, which is what makes it bite. The
guard in `useHeadline` is therefore load-bearing, and no `?? "0"` escape hatch was used
anywhere, because one would silently disarm the check.

The type check runs as `docker build --target build -f web/Dockerfile web/` — node is not
installed on this host, and `npm run build` is `tsc -b && vite build`.

**The six headline states were rendered and read, since "verified by looking at it" was
the instruction.** No browser or screenshot tool is available here, so `DashboardPage`
was rendered through `react-dom/server` against hand-written `SummaryDashboard`
fixtures and its hero's text printed in document order: on-track with nothing to
disclose, watch with all three disclosures, a used-up budget at 0.00, no-budget, a past
month, a future month. Three copy defects were found that way and fixed, none of which
the type check could have caught:

* `over` read "Well ahead of plan" and `watch` read "Running ahead of plan" — "ahead of
  plan" is what you would say about someone doing *well*. Now "Well past the plan for
  this point in the month" and "Spending ahead of plan".
* The past/future note was written to continue the sentence started by the figure
  ("...is how September finished against..."), but the balance line sits between the two
  by criterion 1, so it rendered as a fragment. The notes are standalone prose now.
* The future month's coach said "shows how this month stands against its budget" for a
  month in which nothing has happened. The coach moved onto the headline model, which
  already knows the tense, so a closed month and an unstarted one read differently.

The harness lived in the scratchpad and is gone; nothing was added to `package.json`, so
Out of Scope's "a web test runner. Not installed under cover of this phase" holds.

**The API contract was cross-checked field-for-field** between `SummaryResponse` and
`SummaryDashboard` — 24 fields each side, no difference in either direction. A misspelled
field would arrive as `undefined` and TypeScript could not catch it, since the response is
cast rather than validated at the boundary.

**No new backend test was added, deliberately.** The UI's narrowing leans on one
invariant: the amount is null exactly when the status is `no_budget` or
`not_current_month`. Seam 1 already pins it in both directions — every row of
`SAFE_TO_SPEND_BANDS` and `LAST_DAY_EXAMPLES` asserts a concrete amount, and
`UNDEFINED_EXAMPLES` asserts `amount is None` — so a test here would have been a second
copy of the policy table, which the spec explicitly warns against for seam 2.

## Decisions taken

**The status decides whether a month is current; the UI only picks the tense.** Criterion
5 needs past distinguished from future, but `safe_to_spend_status` conflates them into
`not_current_month`. The backend is the only side that knows `APP_TIMEZONE`, so it keeps
the current-versus-not question and `monthHasPassed` picks the tense only after the
backend has already said the month is not current. Equality reads as past, because the
only way the two disagree is a browser still on the 30th while `APP_TIMEZONE` has turned
the month — in which case the month being asked about is the one that just closed.

**`no_budget` beats `not_current_month` in the headline too, so a budgetless past month
prompts for a budget rather than reporting an outcome.** This follows ticket 06's
recorded precedence rather than re-deciding it in the UI; checking the month first would
have put a rule back in the page. The consequence is worth naming: a budgetless
September shows "Set a budget" instead of how September finished. That is the honest
reading — it finished against no plan — and the prompt is the more useful of the two for
the fresh-install case ticket 06 called out.

**A fourth headline branch exists for an amount that is null under a banded status.** It
cannot happen: the domain pairs null with exactly the two undefined statuses. It is there
because nothing in the type system ties the two fields together, so without it `tsc`
could only be satisfied by a defensive default that would have hidden the breakage. This
way a broken pairing surfaces as "Not available" instead of a crash or a fake zero.

**The badge says "Over plan", not `TONE_LABEL`'s "Over budget".** The allowance is banded
against On-Plan Remaining, so the budget total is not what it has overshot — an owner can
be `over` with budget still left. `TONE_LABEL` stays as it is for the per-category rows,
where "Over budget" is exactly right.

**Both gauges keep the headline's tone, which greys them outside the current month.**
There is one hero tone, read from `safe_to_spend_status`, and `no_budget` and
`not_current_month` map to neutral. So a past month's "Budget left" gauge is grey where it
used to be coloured. The colour it used to have came from the UI rule this ticket deleted,
and the backend exposes no overall verdict for a non-current month, so neutral is the only
reading available that nothing in the page invents.

## Criterion 6 went wider than the hero, and here is the whole account

The breadcrumb on this ticket pointed at `useHeroModel`, and that was the main event: the
`budgetedSpend / budget >= 0.85` band and the `budget - projected` coach arithmetic are
both gone, the tone reads `safe_to_spend_status`, and the only numbers the model still
computes are `spentFrac`, `projFrac` and `dayFrac`, which become an arc length, a needle
angle and a bar width and are never printed.

But the criterion says "the Web UI", and a sweep found a **second, independent copy of
the same threshold** in `CategoriesPage.tsx`:
`spent / budget > 1 ? "over" : spent / budget >= 0.85 ? "watch" : "good"`, plus
`remaining = budget - spent` printed in euros and `Math.round(spent / budget * 100)`
printed as a percentage. Three figures the backend already serves on every budget row as
`status`, `remaining_amount` and `utilization_percent`. Left alone, the dashboard and the
Categories page could print different remainings for the same category — the exact failure
user stories 21 and 30 name — and ticket 09's Definition of Done check would have
re-found it.

Fixed, in the narrowest way that removes the duplication: the page reads those three
backend fields, and where the month has no budget row for a category there is no verdict
to show, so it reads neutral instead of inventing one. This does **not** touch the 85%
band itself, which stays in `domain/metrics.py` where Out of Scope leaves it — only the
UI's private copy of it is gone.

It has a visible consequence worth flagging, because it is a page this ticket was not
otherwise about: a category with an active budget record but no budget row for the month
being viewed used to show an invented percentage and band, and now shows "—" and no
budget panel. A budgetless expense category used to be tinted green ("good"); it is now
neutral. Both are more honest, but if that is judged out of scope, it is one
self-contained commit and reverts cleanly.

**Two things in the UI do arithmetic on money and were deliberately kept.** Recorded so
ticket 09's check reads them as choices:

* `CategoriesPage`'s per-category ledger total, `Σ |amount|` over the month's
  transactions. It is an aggregation of the very rows the page is listing on screen, not a
  derived metric with a policy in it, and no backend field supplies it outside
  `budget_usage`. Replacing it needs a new endpoint, which is well past this ticket.
* The Budget pulse's `remaining >= 0 ? "left" : "over"` and the matching sign flip. This
  is the sign of a backend figure choosing a word, not a comparison against a policy
  constant, and it is part of the per-category presentation Out of Scope protects.
  `eur()` already encodes the same sign convention one layer down.

## Incidental

`DashboardPage` set `className="br-hero-gauges"` on the gauge row while `styles.css`
defines `.br-hero-row` — so the responsive rule that centres the gauges once the hero's
columns wrap has never applied on a phone. Renamed to the class the stylesheet actually
targets, since the hero was being rewritten anyway.

`docs/technical/architecture.md` said "The Web UI should remain a presentation client over
the backend APIs", one aspirational line, while the paragraph below it spelled out that
the Telegram bot carries "no financial logic of its own". As of this ticket the same is
true of the Web UI, so that line now states the spec's checkable test and names the three
status fields the dashboard reads its verdicts from.

Not renamed: `web/src/types.ts` still calls the shared three-value status
`BudgetUsageStatus` while the backend has renamed it `MetricStatus`. It is used for
`savings_status` too, so the name is already wrong on both sides of the wire. A
cross-file rename is refactoring, which is not part of the loop.
