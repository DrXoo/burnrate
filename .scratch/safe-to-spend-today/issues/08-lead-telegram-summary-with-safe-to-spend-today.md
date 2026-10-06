# 08: Lead Telegram /summary with Safe to Spend Today

**What to build:** The fastest interface answers the most useful question first.
The owner messages the bot and the opening line of the summary is what they can
spend today.

**Blocked by:** 06

**Status:** done

- [x] The summary command opens with the allowance
- [x] The no-budget and not-current-month cases render as readable text rather than a bare zero or a null
- [x] The help text describes the summary command accurately
- [x] No new command is added
- [x] The bot computes no financial value of its own
- [x] The README's command list matches the behaviour

## Comments

**Seam.** The spec's seam 4 only: `format_summary` in `test_telegram_formatters.py`,
pure dict in / string out. `HELP_TEXT` lives in the same module and is read at the
same boundary, so the help-text criterion is pinned there too. Nothing was written at
`test_telegram_router.py`, which is an existing seam but not one this feature agreed.

**Five cycles.** The allowance leading the output -> `no_budget` -> `not_current_month`
-> the three banded colours -> the help line. Each was red first; cycles 2 and 3 went
red as a `KeyError` on the status, which is the honest failure for a branch that does
not exist yet.

**The colour cycle passed on arrival and was mutation-checked rather than trusted.**
Cycle 1 read the icon from the existing `_BUDGET_STATUS_ICONS` map instead of hardcoding
a green circle, so the watch and over rows were already satisfied when their test
arrived. Replacing the lookup with a literal `🟢` fails
`..._colours_the_allowance_by_its_status`, so the test has teeth. Reuse was the right
call over a literal-then-replace: the spec puts the bot on one status vocabulary with
the budget rows, and that map already is it.

**What "opens with" was taken to mean.** The month header (`📊 Summary for 2026-06`)
stays first and the allowance is the line under it, before the balance. `/summary` takes
a month argument, so the header is the message's title rather than a figure -- dropping
it would leave the owner unable to tell which month a bare number belongs to. The test
asserts the allowance is the *first line carrying a figure*, which pins the ordering
that matters without freezing the header's wording.

**The two undefined cases say why the number is absent, and nothing more.** `no_budget`
reads "set a monthly budget to get a daily number" -- the prompt, not a zero, because
0.00 is the "you may spend nothing" claim ticket 06 rejected. `not_current_month` reads
"only for the current month"; unlike the dashboard it does not borrow `money_left_amount`
into the slot, because the bot already prints that figure eight lines down as "Budget
left" and printing it twice under two labels is the duplication user story 20 objects to.
Both lines are tested for the absence of a literal `None` anywhere in the output, since a
null leaking into an f-string is the realistic failure.

**The neutral icon is `⚪`, matching the "not yet paid" fixed-budget row.** One neutral
in the bot, not two.

**No test at the router seam, but the router tests prove the wiring anyway.**
`_allowance_line` indexes `payload["safe_to_spend_status"]` with no default, so a payload
missing the field raises rather than printing a plausible blank.
`test_summary_reports_month_and_balance` drives a real `SummaryService` payload through
`format_summary`, so it would fail with a `KeyError` if the service and the formatter
disagreed about the field name. It passes, which is the integration check this ticket
needed without adding a test outside the agreed seams.

**One financial value the bot still computes, left in place deliberately.** Criterion 5
is satisfied for everything this ticket touches, but the sweep it implies found one
pre-existing case: `_budget_bar` computes `(budget - money_left) / budget * 100` and
prints "87% used" -- a figure with a unit, which is the wrong side of the line the
architecture doc states. It is not fixed here for two reasons. The backend serves
`utilization_percent` per budget row but has no month-level equivalent, so removing the
division needs a seventh field on the summary response, and the spec's API contract is
fixed at six with "nothing is removed, so no client breaks". And the bar predates this
phase. Recorded so ticket 09's Definition of Done check reads it as a choice: the figure
is reconcilable from two fields the backend already serves, and the fix is one API field
plus one formatter line whenever it is wanted.

Everything else the formatters compare is a zero-or-sign test choosing whether to print a
line or which arrow to use, which ticket 07 already recorded as presentation.

**Docs.** The README's command list said `/summary` reported "money left, spending, burn
rate, and runway" -- runway has never been in that output, so the line was wrong before
this ticket and is now accurate. `docs/technical/architecture.md`'s Telegram paragraph
gains one clause naming the allowance as the lead and `safe_to_spend_status` as the
source of its colour, which makes the claim in the paragraph above it ("the dashboard and
the bot cannot disagree") literally true of the bot as well. No new command, so
`docs/product/mvp.md`'s command list is untouched.
