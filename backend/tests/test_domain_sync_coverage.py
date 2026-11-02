from __future__ import annotations

from datetime import date, timedelta

import pytest

from burnrate.domain.sync_coverage import (
    SYNC_GAP_GRACE_DAYS,
    gap_is_worth_alerting,
    sync_gap,
    uncovered_days,
)


# Worked examples for the day-level coverage sweep, which is the one spelling of this
# rule: ``month_sync_covered`` is this function asked whether its answer is empty.
#
# A sync run on day S asked the bank about ``[S - 30, S]``, so a day is covered when
# some successful run's window reaches it. ``until`` is exclusive, matching the month
# window convention everywhere else in the product.
#
# since, until, sync days, first missing day, how many missing
UNCOVERED_EXAMPLES = [
    # Nothing ever ran, so every day of the range is missing.
    (date(2026, 9, 1), date(2026, 10, 1), [], date(2026, 9, 1), 30),
    # One run on the last day reaches back thirty, which spans the whole month.
    (date(2026, 9, 1), date(2026, 10, 1), [date(2026, 9, 30)], None, 0),
    # One run on the 20th reaches back to 21 August, so it covers the month up to
    # itself and leaves the 21st to the 30th unasked.
    (date(2026, 9, 1), date(2026, 10, 1), [date(2026, 9, 20)], date(2026, 9, 21), 10),
    # Two runs 25 days apart cover a month neither covers alone.
    (date(2026, 9, 1), date(2026, 10, 1), [date(2026, 9, 5), date(2026, 9, 30)], None, 0),
    # The owner's real outage: runs stopped on 29 August and resumed on 4 October.
    # The October run reaches back to 4 September, so 30 August to 3 September is
    # what was never asked about -- the five days the roadmap accounts for.
    (
        date(2026, 8, 1),
        date(2026, 10, 1),
        [date(2026, 8, 29), date(2026, 10, 4)],
        date(2026, 8, 30),
        5,
    ),
]


@pytest.mark.parametrize(
    ("since", "until", "sync_days", "first_missing", "missing_count"), UNCOVERED_EXAMPLES
)
def test_uncovered_days_names_every_day_the_bank_was_never_asked_about(
    since: date,
    until: date,
    sync_days: list[date],
    first_missing: date | None,
    missing_count: int,
) -> None:
    missing = uncovered_days(
        since=since,
        until=until,
        successful_sync_days=sync_days,
        fetch_window_days=30,
    )

    assert len(missing) == missing_count
    assert (missing[0] if missing else None) == first_missing


def test_uncovered_days_reports_them_in_order_so_the_oldest_is_the_deadline() -> None:
    """The oldest missing day fixes the urgency, so the order is load-bearing."""
    missing = uncovered_days(
        since=date(2026, 9, 1),
        until=date(2026, 9, 11),
        successful_sync_days=[],
        fetch_window_days=30,
    )

    assert missing == [date(2026, 9, day) for day in range(1, 11)]


def test_a_gap_the_next_sync_will_close_is_not_a_gap_worth_reporting() -> None:
    """A two-hour restart leaves days the resumed syncs fetch in full.

    This is the over-firing the roadmap says the alerting phase fails by. A day is
    recoverable until it is thirty days old, so a run today still reaches a day
    missed yesterday and nothing has been lost that needs saying.
    """
    assert (
        sync_gap(
            today=date(2026, 11, 3),
            successful_sync_days=[date(2026, 11, 1), date(2026, 11, 3)],
            fetch_window_days=30,
            lookback_days=90,
        )
        is None
    )


def test_a_gap_is_reported_once_some_of_it_can_never_be_recovered() -> None:
    """The owner's real outage, told on the day the worker came back.

    Runs stopped on 29 August and resumed on 4 October. A day is fetchable while it
    is within thirty days, so by the 4th the days from 30 August onwards were already
    past saving -- and every figure BurnRate had reported for those months was wrong
    with nothing anywhere to say so.
    """
    gap = sync_gap(
        today=date(2026, 10, 4),
        successful_sync_days=[date(2026, 8, 29), date(2026, 10, 4)],
        fetch_window_days=30,
        lookback_days=90,
    )

    assert gap is not None
    assert gap.oldest_missing_day == date(2026, 8, 30)
    assert gap.newest_missing_day == date(2026, 9, 3)
    assert gap.missing_days == 5
    assert gap.unrecoverable_days == 5
    assert gap.recoverable_days == 0
    assert gap.recoverable_until is None
    assert gap_is_worth_alerting(gap=gap, today=date(2026, 10, 4)) is True


def test_a_gap_still_within_reach_is_reported_with_its_deadline() -> None:
    """Nothing lost yet, and the date is the whole message.

    "There is a sync hole" is not actionable; "the oldest missing day goes for good on
    the 10th" is. A missing day's deadline is thirty days after it, so the oldest
    missing day fixes the urgency.

    The fixture is the only shape that reaches this branch: the worker is **alive**
    and its syncs are failing, so successful days stop on 10 October while the clock
    runs to 5 November. A worker that is merely *down* cannot send anything, and when
    it returns it lands in the case above or in none at all.
    """
    gap = sync_gap(
        today=date(2026, 11, 5),
        successful_sync_days=[date(2026, 9, 15), date(2026, 10, 10)],
        fetch_window_days=30,
        lookback_days=90,
    )

    assert gap is not None
    assert gap.oldest_missing_day == date(2026, 10, 11)
    assert gap.unrecoverable_days == 0
    assert gap.recoverable_days == 25
    assert gap.recoverable_until == date(2026, 11, 10)
    assert gap.recoverable_until <= date(2026, 11, 5) + timedelta(days=SYNC_GAP_GRACE_DAYS)
    assert gap_is_worth_alerting(gap=gap, today=date(2026, 11, 5)) is True


def test_a_gap_outside_the_lookback_is_not_reported_for_ever() -> None:
    """Old damage is history, not news, and the alert must stop eventually.

    The owner's August gap is permanent and nothing will change that. Reported once
    when it was found, it must not be re-reported every run for the rest of the
    product's life, which is what makes the lookback a parameter rather than "all of
    time".
    """
    healthy_since_october = [date(2026, 8, 29)] + [
        date(2026, 10, 4) + timedelta(days=offset)
        for offset in range((date(2027, 6, 1) - date(2026, 10, 4)).days + 1)
    ]

    assert (
        sync_gap(
            today=date(2027, 6, 1),
            successful_sync_days=healthy_since_october,
            fetch_window_days=30,
            lookback_days=90,
        )
        is None
    )


def test_a_product_that_has_never_synced_has_no_gap_to_report() -> None:
    """No coverage history is not a hole in one. That is onboarding, not a gap.

    Without this the first run of a fresh install reports the whole lookback as
    missing, which is true and useless -- and it is the first thing a new owner would
    ever be told.
    """
    assert (
        sync_gap(
            today=date(2026, 11, 5),
            successful_sync_days=[],
            fetch_window_days=30,
            lookback_days=90,
        )
        is None
    )


def test_the_range_never_begins_before_any_sync_could_have_covered_it() -> None:
    """A product with two months of history must not report its first day as a hole.

    The first successful run reached back thirty days and no further, so nothing
    before that was ever askable. Without the clamp the lookback runs off the start
    of the owner's history and every day before it reads as missing.
    """
    first_run = date(2026, 10, 1)
    daily = [
        first_run + timedelta(days=offset)
        for offset in range((date(2026, 11, 5) - first_run).days)
    ]

    assert (
        sync_gap(
            today=date(2026, 11, 5),
            successful_sync_days=daily,
            fetch_window_days=30,
            lookback_days=365,
        )
        is None
    )
