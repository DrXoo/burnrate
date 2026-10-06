# 11: Keep the dashboard's month labels honest

**What to build:** Three Web UI defects, all in the same family: the page states
something about a month that it does not actually know. The first two were found by
the branch-wide `/code-review` after ticket 08 and are not reachable in the owner's
current configuration, which is why they are their own ticket rather than a
correction on ticket 07. The third was found by `/code-review` on ticket 10 and *is*
reachable, which is the one to fix first.

**Blocked by:** None (07 is done; this does not block 09)

**Status:** ready-for-agent

- [ ] A month the backend has called "not current" is never labelled as finished when it has not started
- [ ] No month label or tense is decided by comparing a UTC-derived month against the owner's timezone-resolved one
- [ ] A stale summary paired with a failed refresh is visibly stale on the dashboard, as it now is on the Categories page
- [ ] No caption claims a future month is unspent while the figure beside it says otherwise
- [ ] Nothing new is computed in the Web UI: the fix adds a label rule or reads a backend field, not a financial one

## The three defects

**1 — `monthHasPassed` reads a future month as a closed one when `APP_TIMEZONE` is
behind UTC.**

`DashboardPage.monthHasPassed` is `month <= currentMonthValue()`, and
`currentMonthValue()` is `new Date().toISOString().slice(0, 7)` — UTC. It only runs
once the backend has said `not_current_month`, so the question it answers is purely
tense. Worked in both directions, the equality case is right in one and wrong in the
other:

* `APP_TIMEZONE` **ahead** of UTC, say Europe/Madrid. At `2026-06-30T23:00Z` the
  backend's civil date is 1 July, so its current month is July. UTC says June, which
  is also the month the switcher defaults to. The backend calls June not-current,
  equality reads past, and "Month closed · what June finished with" is **correct**.
  This is the configuration ticket 07's comment reasoned about.
* `APP_TIMEZONE` **behind** UTC, say Pacific/Honolulu. At `2026-07-01T02:00Z` the
  backend's civil date is still 30 June, so its current month is June. UTC says July,
  the switcher defaults to July, the backend calls July not-current, and equality
  reads past: the owner's first screen of the month says "Month closed · what July
  finished with, of the 1500.00 EUR it had budgeted", quoting the untouched budget as
  an outcome.

So the comment on `monthHasPassed` is not wrong, it is half the picture — it
considered only the UTC-ahead direction. The trap in fixing it: making the comparison
strict (`month < currentMonthValue()`) breaks the Madrid case to fix the Honolulu one,
because the equality case is genuinely ambiguous without knowing the offset.

Two honest fixes, in order of preference:

* Have the backend say which month is current. It is the only side that knows
  `APP_TIMEZONE`, and it already resolves the civil date; the UI then compares two
  figures from the same clock. The root cause is that `safe_to_spend_status` collapses
  past and future into one value, which ticket 07 recorded as a known compromise.
* Or render the ambiguous case without a tense at all — the money-left figure under a
  neutral "Not the current month" — which needs no API change and is never false.

Not urgent: the live configuration is EUR in a UTC-ahead timezone, where the defect
cannot fire. It becomes live the day `APP_TIMEZONE` is set to anything in the Americas.

**2 — A stale summary plus a failed refresh is invisible on the dashboard.**

`DashboardPage` renders its error banner only in the `error && !summary` branch, and
`useBurnRateData` does not clear `summary` on failure. So a failed refresh with a
payload already cached renders the previous month's figures with no banner: the
headline, both gauges and every disclosure describe a month the owner is not looking
at. The eyebrow does name the month in the non-current case, which is a weak signal,
and there is none at all when the cached month happens to be current.

Pre-existing, and found while probing the `CategoriesPage` finding that ticket 07's
second correction fixed. That page now treats a payload whose `month` is not the month
on screen as no payload at all; the dashboard should reach the same conclusion rather
than each page inventing its own staleness rule. The shared fix is for the hook to
expose the summary only for the month it was fetched for, which would make both pages
correct by construction.

**3 — The future-month caption asserts "Nothing is spent yet" while the figure above
it can already disagree.**

Found by `/code-review` on ticket 10. `DashboardPage`'s future-month branch captions
the money-left headline with "What <month> plans to have left of the <budget>
budgeted. Nothing is spent yet." — a hard-coded claim, not a reading of the payload.
It is already falsifiable: a standing order arrives as pending (`SCHD` normalizes to
pending) carrying a value date in a future month, so `effective_date()` files it in
*that* month, `budgeted_spending` for it is non-zero and `money_left_amount` is below
the budget before the month starts. The dashboard then prints the reduced figure and
captions it as untouched.

Unlike defects 1 and 2 this needs no unusual timezone or failed request: a scheduled
payment and a look at next month is enough, and ticket 10's sweep work means such
rows now persist correctly rather than being treated as phantoms. The fix is to
derive the sentence from the figures — say nothing about spend when there is spend,
or disclose it — rather than from which branch the code is in. No new financial
computation in the UI: the backend already reports the month's budgeted spending.

## Testing

`web/` has no test runner and installing one stays out of scope, so verification is
the type check (`docker build --target build -f web/Dockerfile web/`) plus rendering
the affected states through `react-dom/server` and reading them, which is how tickets
07 and its corrections were verified. Defect 1 needs both timezone directions
rendered, since the naive fix passes one and fails the other. If the fix moves the
current-month question into the backend, that part is seam 2 and carries a real test.
Defect 3 renders with a future-dated pending row in the payload, and the figure it
contradicts comes from seam 2, where a future month with a scheduled payment in it
can be asserted directly.
