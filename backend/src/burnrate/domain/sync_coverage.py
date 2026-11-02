"""Which days the bank was actually asked about, and what a hole in them costs.

A sync run on day ``S`` fetches the trailing window ``[S - fetch_window_days, S]``,
so a day is covered when some *successful* run's window reaches it. That rule already
had one reader -- ``baselines.month_sync_covered``, which asks whether a whole month
is covered -- and this module is the same sweep answered a day at a time, because a
second reader needs to know *which* days and *for how much longer*.

``month_sync_covered`` is defined in terms of ``uncovered_days`` rather than keeping
its own copy of the sweep. Two spellings of one window rule is the defect
``burnrate.db.budget_windows`` and ``burnrate.db.counted_spend`` both exist to
prevent, and this one has already been paid for once: the baselines and the summary
each wrote their own pending-spend rule and disagreed about a negative residual.

**The deadline is the whole point.** A missing day is not lost: a run today still
reaches back thirty days, so a day missed yesterday will be fetched by the next
successful run and nothing needs saying. A day is lost exactly when it falls out of
the fetch window, which is ``fetch_window_days`` after it. So the useful statement is
never "there is a sync hole" but "these days are already gone, and these go on this
date" -- and the owner's own history is why: a 36-day outage in 2026 lost 30 August
to 3 September permanently, and no figure anywhere said so.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta

SYNC_GAP_GRACE_DAYS = 7
"""How close to expiring a still-recoverable day must be before it is worth saying.

A gap the next run will close is not news, and reporting it is the over-firing the
roadmap says the alerting phase fails by. Seven days is enough notice to reconnect a
bank or restart a worker without the product nagging about every restart.
"""


def uncovered_days(
    *,
    since: date,
    until: date,
    successful_sync_days: Sequence[date],
    fetch_window_days: int,
) -> list[date]:
    """The days in ``[since, until)`` no successful sync ever asked the bank about.

    Half-open at the end, matching the month window convention everywhere else, so a
    caller passing ``today`` as ``until`` does not report today as missing before the
    day's run has had its chance.

    Returned oldest first, because the oldest missing day is the one whose deadline
    falls first and therefore the one that fixes the urgency.

    Only days on which a sync *succeeded* may be passed. That matters most for the
    case this exists to catch: a lapsed consent writes a session row per attempt, so
    counting rows rather than successes would see an unbroken chain running straight
    through the hole it is meant to find.
    """
    covered_through: date | None = None
    missing: list[date] = []
    day = since
    windows = sorted(successful_sync_days)
    index = 0
    while day < until:
        # Admit every run whose window has started by this day; each one extends the
        # covered frontier to its own day, since its window runs forward to it.
        while index < len(windows) and windows[index] - timedelta(days=fetch_window_days) <= day:
            covered_through = max(covered_through or windows[index], windows[index])
            index += 1
        if covered_through is None or covered_through < day:
            missing.append(day)
        day += timedelta(days=1)
    return missing


@dataclass(frozen=True)
class SyncGap:
    """Days the bank was never asked about, split by whether they can still be had.

    Facts and no verdict: whether a gap is worth interrupting the owner over is a
    different question from what the gap is, and the two consumers of this ask it
    differently. The dashboard reports any gap, because the owner is already looking;
    the worker only speaks when something is lost or about to be.
    """

    oldest_missing_day: date
    newest_missing_day: date
    missing_days: int
    unrecoverable_days: int
    recoverable_days: int
    recoverable_until: date | None
    """The last day a run can still fetch the oldest recoverable day. ``None`` when
    every missing day is already past saving."""


def sync_gap(
    *,
    today: date,
    successful_sync_days: Sequence[date],
    fetch_window_days: int,
    lookback_days: int,
) -> SyncGap | None:
    """The gap in the recent past, or ``None`` when the bank was asked about all of it.

    Two bounds keep this from reporting things that are not the owner's problem.

    ``lookback_days`` stops permanent damage being re-reported for the life of the
    product: the owner's August 2026 loss is history, not news, and an alert that
    cannot stop is an alert that gets muted.

    The range also never begins before the earliest day any sync *could* have
    covered, which is the first successful run less the fetch window. Without that
    clamp a product with two months of history reports its first day as a hole, which
    is true and useless. With **no** successful sync at all there is no coverage
    history to have a hole in, so there is nothing to say here -- that is onboarding,
    not a gap.
    """
    if not successful_sync_days:
        return None

    earliest_coverable = min(successful_sync_days) - timedelta(days=fetch_window_days)
    since = max(today - timedelta(days=lookback_days), earliest_coverable)
    if since >= today:
        return None

    missing = uncovered_days(
        since=since,
        until=today,
        successful_sync_days=successful_sync_days,
        fetch_window_days=fetch_window_days,
    )
    if not missing:
        return None

    # A day is still reachable while a run made today would cover it, which is for
    # ``fetch_window_days`` after it. Equality is reachable: the window is inclusive
    # at both ends, so a day exactly that old is the last day it can be had.
    recoverable = [day for day in missing if day + timedelta(days=fetch_window_days) >= today]
    return SyncGap(
        oldest_missing_day=missing[0],
        newest_missing_day=missing[-1],
        missing_days=len(missing),
        unrecoverable_days=len(missing) - len(recoverable),
        recoverable_days=len(recoverable),
        recoverable_until=(
            recoverable[0] + timedelta(days=fetch_window_days) if recoverable else None
        ),
    )


def gap_is_worth_alerting(*, gap: SyncGap, today: date, fetch_window_days: int) -> bool:
    """Whether a gap earns an **unprompted** message, as the backend's single answer.

    Two cases earn one, and two deliberately do not.

    Something is **about to be lost**, within ``SYNC_GAP_GRACE_DAYS``. There is no
    freshness rule on this side: it is an ask rather than a fact, and it cannot nag
    for long by construction, because a recoverable day either gets fetched or turns
    into a lost one. Reachable only while the worker is alive and its syncs are
    failing, since a worker that is down cannot send anything.

    Something has **just become** lost. No action recovers it, but the owner has been
    reading understated figures for those months and that is worth knowing even
    though it is too late. A day hardens ``fetch_window_days`` after itself, so the
    most recent loss hardened at ``newest_missing_day + fetch_window_days`` -- for the
    owner's real outage, the day before the worker came back.

    **Old loss earns nothing**, and that is the rule this function gained after the
    first version shipped without it. The August days are gone and repeating it is
    nagging about a fact; worse, the worker reports at *startup*, so every redeploy
    for three months would have re-sent the same August message. The persistent place
    for that fact is the affected months' own figures, not an alert.

    And a gap the next successful run will close earns nothing at all, which is the
    over-firing the roadmap says the alerting phase fails by.
    """
    grace = timedelta(days=SYNC_GAP_GRACE_DAYS)
    if gap.recoverable_until is not None and gap.recoverable_until <= today + grace:
        return True
    if gap.unrecoverable_days == 0:
        return False
    hardened_on = gap.newest_missing_day + timedelta(days=fetch_window_days)
    return hardened_on >= today - grace
