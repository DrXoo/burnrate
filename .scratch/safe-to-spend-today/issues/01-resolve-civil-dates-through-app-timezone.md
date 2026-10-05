# 01: Resolve civil dates through APP_TIMEZONE

**What to build:** "Today" and "the current month" mean today in the owner's own
timezone rather than UTC. Near midnight the dashboard stops reporting yesterday,
and on the first of the month it stops reporting the whole previous month. The
same latent bug exists in four places, so all four are fixed together.

**Blocked by:** None (can start immediately)

**Status:** done

- [x] A setting names an IANA timezone and defaults to UTC, documented in the example environment file
- [x] The summary resolves today and the current month through that setting
- [x] Both civil-date call sites in the budget service and the one in the Telegram notifier resolve the same way
- [x] A test proves that with the timezone set ahead of UTC, a reading taken just after local midnight reports the new local day
- [x] A test proves the first of the month is not reported as the previous month
- [x] The architecture doc records the setting

## Comments

**Seams (confirmed with the owner before the first test).** Tested at the
spec's seam 2 only — `SummaryService`, which gained a `clock` constructor
argument mirroring `TelegramCommandRouter`'s existing one, so a reading can be
taken at a fixed instant. One test covers both date criteria at once: 12:30 UTC
on 30 June is 00:30 on 1 July in Auckland, so a single assertion on `month` and
`days_elapsed` proves the new local day *and* that the 1st is not reported as
the previous month. The owner also chose fail-at-boot over fall-back-to-UTC for
an unknown zone, which added one test at the existing config seam
(`test_config.py`) — outside the spec's four seams, agreed explicitly.

No tests at the budget service or the Telegram notifier: not agreed seams, and
both now route through the same helper, so there is one behaviour to get wrong
rather than three.

**A fifth call site.** The ticket enumerates four; `TelegramCommandRouter._unknown`
derives `%Y-%m` from a UTC instant for the same reason and had the same bug.
Fixed in the same pass, since the router had to be touched anyway to hand the
timezone to `SummaryService`.

**Two more sites, deferred and then not.** The first pass left
`EnableBankingService._current_month_transaction_window` and
`_pending_transaction_window` on UTC, on the grounds that they are provider
*fetch* windows rather than figures shown to the owner. `/code-review` rejected
that and was right: the window decides which rows exist in the database, so it
does move the shown figures. In `Pacific/Auckland` at local 1 July 00:30 the
dashboard resolves July while the fetch asks the bank for 1-30 June, so July
reads 0.00 until UTC catches up some hours later. Both windows now resolve
through the helper, which also makes the architecture doc's "single helper"
claim true rather than aspirational. Issue 04 still owns the pending window's
sweep semantics.

**Defaults chosen so no existing figure moves.** `timezone_name` defaults to
`"UTC"` on `SummaryService`, `BudgetService` and the router, matching the
setting's default. Every pre-existing test passes untouched (168 → 170), which
is the regression evidence for the spec's "every booked figure stays exactly as
it was".

**Shape.** `burnrate/clock.py::civil_date(timezone_name, instant=None)` takes the
IANA name rather than `Settings`, so it stays pure and depends on one string
instead of the whole config object. It sits at the package root beside
`crypto.py` and `security.py` rather than in `domain/`, which ADR-0001 reserves
for metric policy.

**Review fixes (`/code-review`, after the first commit).**

* `civil_date` raises on a naive instant instead of letting `astimezone` read it
  as the host's local time. Verified it mattered: the same naive reading
  resolved to 1 July on a UTC host and 30 June under `TZ=Europe/Madrid`. Pinned
  by a test at seam 2 rather than against the helper, which is not an agreed
  seam.
* `BudgetService` resolves the day once per call. `deactivate_budget` was
  reading the clock twice -- writing `active_to` from one day and reporting a
  status judged against another if the call straddled local midnight -- and
  `list_budgets` re-read it per row. Pre-existing, cheap to fix while here.
* The config validator's accept-and-normalize path is now pinned. It was
  already correct, so this closes a coverage gap rather than a defect.

Three review findings were downgraded after checking them: `ZoneInfo` is
name-cached, so the per-row lookups cost nothing; a required `timezone_name`
would *not* have caught the Enable Banking windows, which construct neither
service; and the `%Y-%m` duplication is two sites, not three, since
`summary_service` formats an already-resolved date.
