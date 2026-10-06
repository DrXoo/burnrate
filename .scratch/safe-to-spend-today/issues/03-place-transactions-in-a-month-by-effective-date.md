# 03: Place transactions in a month by Effective Date

**What to build:** A transaction with no booking date stops being invisible to
the month it belongs to. On its own this is a bug fix the owner can see: an
uncategorized Pending charge now reaches the review queue instead of vanishing.
It is also the prerequisite for Pending spend counting at all, because a null
booking date never satisfies a month-window comparison in SQL.

**Blocked by:** None (can start immediately)

**Status:** done

- [x] One shared helper resolves a transaction's Effective Date as its booking date, then its value date, then its import date
- [x] Every month-windowed summary query uses that helper rather than repeating the rule
- [x] A transaction with no booking date but a value date inside the month is counted in that month
- [x] An uncategorized Pending transaction with no booking date appears in the review queue
- [x] Every pre-existing Booked figure is unchanged to the cent, asserted by a regression test over the existing seeded summary
- [x] The domain doc records Effective Date

## Comments

**Seams (confirmed with the owner before the first test).** The spec's seam 2
(`SummaryService` through `month`/`today`) plus `LedgerService` as a fifth seam,
agreed explicitly. The review-queue criterion lands there and nowhere else: the
dashboard's badge and list read `/transactions/uncategorized` and its `/count`,
both of which are `LedgerService.list_transactions(categorized=False)`. There
was direct prior art for exactly this behaviour —
`test_ledger_service_lists_pending_transaction_without_booking_date_by_value_date`
already pinned the two-step fallback — so the rule was half-implemented there
before this ticket and the ticket's job was to finish and share it.

**The helper is a SQL expression, not a domain function.** `effective_date()`
lives in `burnrate/db/effective_date.py` and returns a SQLAlchemy
`coalesce(booking_date, value_date, date(imported_at))`. It resolves per row
inside the query, so there is nothing for the application layer to decide, and
`AGENTS.md` keeps SQL out of `domain/`. Six call sites: the four month-windowed
queries in `SummaryService`, and in `LedgerService` both the month filter and the
list ordering.

**The import date resolves on the UTC calendar day, chosen over a
timezone-correct form.** Phase 8 otherwise routes every civil date through
`APP_TIMEZONE` (tickets 01 and 02), so this is the deliberate exception. A
timezone-aware version is possible — compare `coalesce(booking, value)` against
the month dates, `OR` both-null-and-`imported_at` between the two UTC instants
the owner's month boundaries convert to — but SQLite carries no timezone
database, so the expression the tests exercise could not be the expression that
ships, and the one place the rule is hardest to get right would be the one place
untested. Weighed against that: the fallback only fires on a row the bank dated
not at all, where an import instant is already a proxy, and a misplacement
self-corrects the moment the charge books. Recorded in the helper's docstring
and the domain doc rather than as an ADR — it is a tradeoff inside one
expression, not a constraint on future work.

**`date(timestamptz)` was verified against the running Postgres 17, not just
SQLite.** The two dialects compile the expression identically, but a SQLite-only
check could not prove the function exists in production; it does, and returns a
`date`.

**Correction from code review: the fallback day is the database session's, not
UTC.** The first version of this ticket claimed a UTC calendar day. It is not
guaranteed: `date(timestamptz)` converts through the session `TimeZone`, and the
same instant yields 2026-06-30 under `UTC` and 2026-07-01 under `Europe/Madrid`
(verified against the live server). The claim held only because PostgreSQL
defaults the session to UTC. Setting `TZ` or `PGTZ` in the environment would move
undated charges between months silently, and SQLite cannot catch it because its
`date()` reads the stored naive UTC wall clock. The expression is unchanged --
`func.timezone('UTC', ...)` would break SQLite and reintroduce the portability
problem the UTC-day choice avoided -- so what changed is that the docstring now
states the real contract and the deployment requirement instead of a guarantee
the code does not make.

**Also from review, and not acted on.** The coalesce makes the month window
non-sargable, so the `booking_date` indexes no longer serve it (cost 38 to 84
over 487 rows). Recorded in `docs/technical/database/schema.md` with the two ways
out rather than fixed: single-owner volumes make it immeasurable, `AGENTS.md`
ranks performance last, and the real fix is the stored `effective_date` column
the spec deferred for needing a backfill. The window comparison `effective_date()
>= month_start, < month_end` is also still written out at five call sites; a
`within_month()` helper would bind it once and is left for `/simplify`.

**A dead ordering term went with the change.** `LedgerService.list_transactions`
sorted on `effective_date.is_(None)` first to push undated rows to the end. With
`imported_at` (NOT NULL) closing the chain the expression can never be null, so
the term was always false and was removed rather than left as noise.

**The regression test was renamed after review.** It was called
`..._when_the_month_window_falls_back`, but every seeded row carries a booking
date, so the chain always resolves on its first link and neither fallback leg is
ever evaluated -- the name promised coverage the test did not have, and breaking
the order of the coalesce arguments would not have failed it. It is now
`test_summary_service_reports_every_booked_figure_of_the_seeded_month_to_the_cent`,
which is what it does. The fallback legs keep their own tests.

**Not done here, by design.** Pending still counts toward no spend figure — the
`status == "booked"` filters are untouched, so this ticket makes pending rows
*visible to the month* and ticket 05 makes them *count*. The regression test
proves the separation holds: every seeded Booked figure is unchanged to the cent.
