# 04: Comparable Spend, Uncomparable Spend, and the dashboard's comparison

**What to build:** The dashboard shows monthly spending, income and net cash flow each
against its own baseline, as a second line beneath figures the owner already reads. The
spending comparison is computed over **only** the categories that have a baseline, and
the spend that could not be compared is reported beside it rather than inside it.

This is the ticket where the owner's October reads correctly: one category with no
history holding the great majority of the month must not turn a quiet month into a
report of catastrophic overspending.

**Blocked by:** 02.

**Status:** done

- [x] Monthly spending is shown against a baseline computed only over the categories that have one
- [x] The Uncomparable Spend total is reported beside the comparison and never counted inside it
- [x] A month in which one uncomparable category exceeds the entire comparable total does not move the comparison, and the comparison still reports the ordinary categories honestly
- [x] Income and net cash flow are each shown against their own baseline
- [x] Safe to Spend Today is given no baseline
- [x] The comparisons appear beneath the existing figures; no new page is added
- [x] An absent baseline is null in the payload rather than zero, and renders as no claim rather than as a figure
- [x] Paging back to a closed month shows that month's comparison against the months before it
- [x] Below the minimum Qualifying Month count, the dashboard states that there is not enough history rather than showing an empty comparison
- [x] Every pre-existing summary field is unchanged, asserted as a regression
- [x] Tests live only at the pure-domain seam, the summary service seam, and page rendering
- [x] Including uncomparable categories in the aggregate puts the October-shaped test red


## Comments

**Done.** 11 new backend tests and 6 new page tests (a new `DashboardPage.test.tsx`);
454 backend and 57 web pass, `tsc` is clean and `npm run build` succeeds.

Red first on five of six cycles. The closed-month and allowance tests went green on
arrival and were mutation-checked instead.

### A correction to ticket 02: it shipped a broken web build

Ticket 02's note that `tsc` was clean was **wrong, and the mistake was mine**: I
filtered the command's output with `tail -5`, which showed only npm's notices and cut
the five type errors above them. `CategoryStat` is an explicit interface and
`useMemo<CategoryStat[]>` annotates the return, so adding a `comparison` field to the
returned object without declaring it on the interface is an error.

Two things made it invisible. Vitest transforms through esbuild and **does not type
check**, so 52 tests were green over a broken build. And `npm run build` is
`tsc -b && vite build`, so the web image would have failed to build from that commit.
The interface now declares the field, and the real gate is the build rather than
`tsc --noEmit` read through a filter.

### The pin earned its keep

`test_summary_service_reports_every_figure_of_the_seeded_month_to_the_cent` asserts an
exact dict of every key ending in `_amount`, so three new fields broke it — exactly
what it exists for. No existing figure moved; the fix was to state the new amounts by
hand. The seeded month has nothing before it, so the comparable half is empty and the
residual covers the month's entire spending, which is the honest answer for a month
with no history behind it.

It also surfaced a process lapse of mine: I had been running only
`test_summary_baselines.py` through several cycles and so carried the failure for
three of them before the first full-suite run caught it.

### Decisions taken here

* **Uncomparable Spend is the residual**, monthly spending less the comparable half,
  rather than a sum over the categories without baselines. The two halves then
  reconcile against the headline the owner already has on screen instead of forming a
  third total they would have to tie back by hand, and every euro in it is genuinely
  something the comparison cannot speak to: a category below the presence floor, an
  Archived Category, or spend dated after today's cutoff. Defining it as a sum would
  have left those last two unaccounted for in either half.
* **Income and net cash flow take no comparable split.** The split exists because
  per-category baselines feed the spend aggregate and a category without one would
  poison it. Both of these are whole-month figures with no per-category decomposition
  in play, and "much worse than usual" about money kept is simply *true*, one-off
  included -- which is what makes it different from reporting that the owner
  overspent.
* **Net cash flow gets an amount and no verdict.** A ratio on a figure that can cross
  zero means nothing (1700 against -6700 is -3.94), and an owner whose usual month is
  a deficit would carry a negative baseline that the band logic reads as
  `no_baseline` -- a status denying what the amount beside it states. The two figures
  side by side already say it.
* **Aggregate figures take no presence floor.** `figure_baseline_amount` exists
  alongside `category_baseline` to state that: the floor is for a category spent in
  too rarely to have a normal monthly cost, while a month in which nothing came in is
  a fact about the owner's year. Skipping it would report a salary as normal to
  someone paid once in three months.
* **The income baseline does not exclude Archived Categories, while the per-category
  spend query does.** Each baseline matches the filters of the figure it is compared
  against: the month's income counts every income category, so excluding archived
  ones would compare a narrower total against a wider one. The per-category list
  excludes them because it is a list the owner reads.
* **`comparisonPhrase` moved to `lib/format.ts`.** The second real use case arrived,
  which is when `AGENTS.md` says to extract; duplicating it across two pages would
  have been the alternative.
* **The insufficient-history statement goes on the spending card only.** One
  statement of the reason, beside the figure the owner acts on, rather than the same
  sentence under all three.

### A criterion I had missed, and the owner should know about

The last acceptance criterion asks the dashboard to **state** that there is not
enough history rather than show an empty comparison. My first implementation was
silent, and I only caught it re-reading the criteria before closing. Silence reads as
"nothing to say about your spending", which is a different and wrong claim. It now
says "not enough history to compare yet", so the owner can tell a product that has
nothing to report from one that cannot report yet -- and in their case the fix is
theirs rather than the code's.

### Mutations run

| Mutation | Result |
|---|---|
| Uncomparable categories folded into the aggregate | `8705.62` vs `301.79` |
| Income baseline not gated on the status | `'0.00'` where `None` is owed |
| Net cash flow baseline not gated on the status | `'-300.00'` where `None` is owed |
| Residual computed backwards | `-8400.00` vs `8400.00`, 2 tests |
| Dashboard silent instead of stating the reason | its own test |

### Review findings, absorbed here

Verified after the fixes: **471 backend** and **61 web** pass, `tsc -b` exits 0 and
`npm run build` succeeds. The web suite runs in a `node:22` container -- there is no
node on the host, since the web app only ever builds in Docker, and the repo's
`node_modules` lacks the platform-specific rollup binary, so it takes a clean
`npm ci` in a copy of `web/` rather than a mount of the existing tree.

| Mutation | Result |
|---|---|
| `spend_counts` drops every pending row | the variable-category test |
| The month on screen's budgets used across the window | the per-month test |
| `counted_spend` counts a fixed hold | 5 pre-existing summary tests |
| `fires_anomalies` ignored | 2 domain examples and the bonus-month test |
| `baselineFigure` keyed on the amount | both zero-baseline page tests |
| Net baseline rendered unsigned | both hero modes, separately |


Three of five `/code-review` findings on the feature branch landed in this ticket,
all of them in the acceptance criterion about an absent baseline being null rather
than zero. The criterion was right; it was read too narrowly.

**The two spend bases were not the same base.** Uncomparable Spend is defined as the
residual -- monthly spending less the comparable half -- and that only reconciles
while both count the same money. The headline excludes a hold on a Fixed Budget's
category (ADR-0003: the budgeted estimate already stands for the whole commitment);
`BaselineService` counted holds everywhere. A fixed Rent with 500 booked in each of
two Qualifying Months and 500 held on the 1st published 0.00 spent, 500.00 comparable
and **minus 500.00** that cannot be compared. The dashboard hid it (`> 0`) and the bot
printed it (`!= 0`), which is the disclosure working exactly backwards.

Fixed by giving the rule one home, `burnrate/db/counted_spend.py`, in the two forms
its callers need -- the same arrangement as `budget_windows.py`, for the same reason:
three readers, and the two that were written independently disagreed. The baselines
now apply it per month, because a budget window is month-granular and a category the
owner made fixed in September was not fixed in August. That costs **one** extra query
for the whole window, not one per month: the Fixed Budget windows are read once and
`budget_month_status` -- `budget_covers_month`'s own pure twin, which is why the two
live together -- decides each month in Python. Ticket 06 should see one statement
more, not `window + 1`.

The per-month lookup passed every test on arrival and was mutation-checked: reading
the month on screen's budgets across the whole window survived the suite, so
`test_each_month_is_asked_whether_the_category_was_fixed_in_that_month` was written
for it and kills both that mutation and the refactor to one query getting the month
wrong.

**"0.00" is a truthy string.** A baseline of zero or less is one the backend refuses
to divide by, so it publishes `no_baseline` with 0.00 still in the amount -- and every
card keyed its guard on the amount. The income card rendered "normally €0.00 · no
baseline yet", a figure and a denial of it in one breath. A salary dated the 28th read
on the 26th is all it takes; a category can reach it too, with two months whose
movements cancel out. Now read off the band, through one helper (`baselineFigure`)
because three cards ask the same question, and the Telegram formatter's own
`baseline is None` guard had the same hole.

**The net cash flow baseline was rendered unsigned.** It is the one baseline published
as an amount with no band precisely because it can be a deficit, and `eurPlain` let
the formatter smuggle the minus in as "€-450.00" where every other signed figure uses
`eur`.

### For ticket 06

The month on screen and every Qualifying Month now each cost two more aggregate
queries -- income and total spending -- on top of ticket 02's per-category spend and
coverage pair and ticket 03's single sync query. With a three-month window and two
qualifying months that is a lot more than the six statements ticket 01 recorded, and
the current month should now cost strictly more than a closed one.
