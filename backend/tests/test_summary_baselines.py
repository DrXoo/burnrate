"""Baselines through the summary service: the wiring, not the policy.

``test_domain_baselines.py`` asks whether each rule is right. This module asks
whether the rules are wired to the right queries -- which months are fed in, over
which windows, and with which rows excluded. Those are the questions a pure
function cannot be asked, and the two most dangerous defects in this feature live
here rather than in the policy: measuring coverage by rows instead of by money, and
handing the baseline only the months a category appeared in.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from burnrate.db.base import Base
from burnrate.db.models import Account, Budget, Category, SyncSession, Transaction
from burnrate.services.summary_service import SummaryService

# Every fixture pins its own "today". Nothing here reads the wall clock: this whole
# feature is relative months, so a fixture dated against the real calendar would
# start reporting different windows the moment the month turned. Phase 8 lost a test
# to exactly that.
TODAY = date(2026, 10, 26)


def make_session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


class Fixture:
    """A database seeded month by month, so each test reads as its own example."""

    def __init__(self, db: Session, *, synced: bool = True) -> None:
        self.db = db
        # A healthy sync history by default, because every other test in this module
        # is about classification coverage and a sync hole would be an unrelated
        # confound. Tests about sync coverage opt out and seed their own runs.
        if synced:
            self.sync_daily(date(2026, 6, 1), date(2026, 12, 31))
        self.account = Account(
            display_name="Main account",
            currency="EUR",
            included_in_calculations=True,
            latest_balance_amount=Decimal("1000.00"),
            latest_balance_currency="EUR",
            last_synced_at=datetime(2026, 10, 26, 9, 0, tzinfo=timezone.utc),
        )
        db.add(self.account)
        db.flush()
        self.categories: dict[str, Category] = {}

    def category(self, name: str, *, type_: str = "expense", active: bool = True) -> Category:
        if name not in self.categories:
            category = Category(name=name, type=type_, active=active)
            self.db.add(category)
            self.db.flush()
            self.categories[name] = category
        return self.categories[name]

    def spend(
        self,
        *,
        category: str | None,
        on: date,
        amount: str,
        status: str = "booked",
        excluded: bool = False,
        type_: str = "expense",
    ) -> Transaction:
        """One outgoing row. ``category=None`` leaves it awaiting review."""
        transaction = Transaction(
            account_id=self.account.id,
            booking_date=on,
            value_date=on,
            amount=-Decimal(amount),
            currency="EUR",
            description=f"{category or 'unknown'} {on.isoformat()}",
            direction="debit",
            status=status,
            category_id=self.category(category, type_=type_).id if category else None,
            excluded_at=datetime(2026, 10, 1, tzinfo=timezone.utc) if excluded else None,
            imported_at=datetime(2026, 10, 26, 9, 0, tzinfo=timezone.utc),
        )
        self.db.add(transaction)
        self.db.flush()
        return transaction

    def income(self, *, category: str, on: date, amount: str) -> None:
        """One incoming row. Income is booked-only everywhere, so this is booked."""
        self.db.add(
            Transaction(
                account_id=self.account.id,
                booking_date=on,
                value_date=on,
                amount=Decimal(amount),
                currency="EUR",
                description=f"{category} {on.isoformat()}",
                direction="credit",
                status="booked",
                category_id=self.category(category, type_="income").id,
                imported_at=datetime(2026, 10, 26, 9, 0, tzinfo=timezone.utc),
            )
        )
        self.db.flush()

    def fixed_budget(self, *, category: str, amount: str, active_from: date) -> None:
        """An open-ended Fixed Budget, the kind a rent or a utility bill carries."""
        self.db.add(
            Budget(
                category_id=self.category(category).id,
                amount=Decimal(amount),
                currency="EUR",
                period_type="monthly",
                active_from=active_from,
                active_to=None,
                is_fixed=True,
            )
        )
        self.db.flush()

    def bounded_fixed_budget(
        self, *, category: str, amount: str, active_from: date, active_to: date
    ) -> None:
        """A Fixed Budget with both edges set, which an Event Budget is one case of.

        Takes the end date rather than deriving a month from it, so a test can bound a
        window to two months and show that the rule does not fire -- deriving it would
        make "exactly one month" unobservable from here.
        """
        self.db.add(
            Budget(
                category_id=self.category(category).id,
                amount=Decimal(amount),
                currency="EUR",
                period_type="monthly",
                active_from=active_from,
                active_to=active_to,
                is_fixed=True,
            )
        )
        self.db.flush()

    def sync_daily(self, first: date, last: date, *, status: str = "success") -> None:
        """One sync run per day across the range, as the cron would produce."""
        day = first
        while day <= last:
            self.sync_on(day, status=status)
            day += timedelta(days=1)

    def sync_on(self, day: date, *, status: str = "success") -> None:
        self.db.add(
            SyncSession(
                started_at=datetime(day.year, day.month, day.day, 9, 0, tzinfo=timezone.utc),
                finished_at=datetime(day.year, day.month, day.day, 9, 5, tzinfo=timezone.utc),
                status=status,
                imported_accounts_count=1,
                imported_transactions_count=0,
            )
        )
        self.db.flush()

    def summary(self, *, month: str = "2026-10", today: date = TODAY, window: int = 3) -> dict:
        return SummaryService(db=self.db, baseline_window_months=window).get_summary(
            month=month, today=today
        )


def row_for(summary: dict, name: str) -> dict:
    rows = [row for row in summary["category_baselines"] if row["category_name"] == name]
    assert len(rows) == 1, f"expected one {name} row, got {len(rows)}"
    return rows[0]


def test_a_category_with_spend_in_three_qualifying_months_gets_a_baseline() -> None:
    """The tracer bullet: three clean months behind the one on screen produce a mean.

    July, August and September are fully classified and so all qualify; October is
    the month on screen and is never its own baseline input. 450, 600 and 300 over
    the three of them is 450, and the 200 spent this month is well under it.

    Three and not two: ``BASELINE_MINIMUM_MONTHS`` was raised when the owner's first
    reachable pair turned out to be a divorce month and one ordinary month.
    """
    db = make_session()
    fixture = Fixture(db)
    fixture.spend(category="Food", on=date(2026, 7, 5), amount="450.00")
    fixture.spend(category="Food", on=date(2026, 8, 5), amount="600.00")
    fixture.spend(category="Food", on=date(2026, 9, 5), amount="300.00")
    fixture.spend(category="Food", on=date(2026, 10, 5), amount="200.00")

    summary = fixture.summary()

    assert summary["baseline_status"] == "ok"
    assert summary["baseline_months_count"] == 3
    food = row_for(summary, "Food")
    assert food["baseline_amount"] == "450.00"
    assert food["spend_amount"] == "200.00"
    assert food["comparison_status"] == "below"
    assert food["deviation_percent"] == -55.6


def test_coverage_is_the_share_of_money_unfiled_not_the_share_of_rows() -> None:
    """The defect the pure-domain seam structurally cannot catch.

    ``month_qualifies`` takes amounts, so its signature already encodes the decision
    and no test there can falsify it. Only the query can get this wrong, and getting
    it wrong is not hypothetical: the owner's June 2026 reads 79% classified counting
    rows and 33% counting money.

    Three months behind the one on screen, built so that the two measures qualify
    *different* months while agreeing on how many:

    * June is clean and qualifies either way. Food: 450.
    * July is clean and qualifies either way. Food: 300.
    * August hides 905 of its 1000 in a single unfiled row among twenty. By money it
      is 90.5% unfiled and disqualified; by rows it is 5% unfiled and admitted.
      Food: 95.
    * September has ten unfiled rows of 2.00 beside one Food charge of 600. By money
      it is 3.2% unfiled and admitted; by rows it is 90.9% unfiled and disqualified.

    So both measures find exactly three qualifying months and the count cannot tell
    them apart -- but by money the baseline is (450 + 300 + 600) / 3 = 450, and by
    rows it would be (450 + 300 + 95) / 3 = 281.67. The baseline is the
    discriminating assertion. The window is four so that a month can be disqualified
    by each measure and three still remain, which is the minimum.
    """
    db = make_session()
    fixture = Fixture(db)

    fixture.spend(category="Food", on=date(2026, 6, 5), amount="450.00")
    fixture.spend(category="Food", on=date(2026, 7, 5), amount="300.00")

    for _ in range(19):
        fixture.spend(category="Food", on=date(2026, 8, 5), amount="5.00")
    fixture.spend(category=None, on=date(2026, 8, 6), amount="905.00")

    fixture.spend(category="Food", on=date(2026, 9, 5), amount="600.00")
    for day in range(10, 20):
        fixture.spend(category=None, on=date(2026, 9, day), amount="2.00")

    fixture.spend(category="Food", on=date(2026, 10, 5), amount="450.00")

    summary = fixture.summary(window=4)

    assert summary["baseline_status"] == "ok"
    assert summary["baseline_months_count"] == 3
    assert row_for(summary, "Food")["baseline_amount"] == "450.00"


def test_a_qualifying_month_the_category_was_absent_from_still_divides() -> None:
    """The zeros the domain function cannot ask for.

    ``category_baseline`` divides by however many entries it is handed, so a caller
    that passes only the months a category appeared in gets a higher baseline and the
    domain seam cannot tell. This is where that is pinned.

    Three qualifying months. Food appears in two of them -- 600 in July, nothing in
    August, 300 in September -- which clears the presence floor. Dividing by the
    three qualifying months gives 300; dividing by the two Food appeared in would
    give 450. For a recurring expense an absent month is a real zero.

    August qualifies on Rent alone, which is what makes it a month Food was absent
    from rather than a month that was never counted.
    """
    db = make_session()
    fixture = Fixture(db)
    fixture.spend(category="Food", on=date(2026, 7, 5), amount="600.00")
    fixture.spend(category="Rent", on=date(2026, 8, 1), amount="500.00")
    fixture.spend(category="Food", on=date(2026, 9, 5), amount="300.00")
    fixture.spend(category="Food", on=date(2026, 10, 5), amount="300.00")

    summary = fixture.summary()

    assert summary["baseline_months_count"] == 3
    assert row_for(summary, "Food")["baseline_amount"] == "300.00"


def test_the_month_on_screen_is_never_its_own_baseline() -> None:
    """A comparison partly against itself is not a comparison.

    July, August and September each hold 300 of Food, so the baseline is 300. October
    holds 900. Were the month on screen folded into its own window the baseline would
    be 450, and a month three times the usual would report itself as merely above.
    """
    db = make_session()
    fixture = Fixture(db)
    fixture.spend(category="Food", on=date(2026, 7, 5), amount="300.00")
    fixture.spend(category="Food", on=date(2026, 8, 5), amount="300.00")
    fixture.spend(category="Food", on=date(2026, 9, 5), amount="300.00")
    fixture.spend(category="Food", on=date(2026, 10, 5), amount="900.00")

    summary = fixture.summary()

    food = row_for(summary, "Food")
    assert food["baseline_amount"] == "300.00"
    assert food["spend_amount"] == "900.00"
    assert food["comparison_status"] == "anomalous"


def test_the_current_month_is_compared_against_the_same_part_of_past_months() -> None:
    """A part-month measured against whole ones is favourable for most of the month.

    On the 26th, August contributes only what the owner had spent by *its* 26th: the
    100 on the 5th, not the 900 on the 30th. With July's and September's 100 the
    baseline is 100. Comparing against whole months instead would make it 366.67, and
    a month spending exactly its usual would read as far below.

    This is the defect Phase 8 fixed in the budget pacing, where a comparison with no
    time term flipped an on-plan month to a warning around day 26. Summing past
    months to the same cutoff makes no assumption about pacing, which is why it was
    preferred to pro-rating a whole-month baseline: a Fixed Budget is charged as a
    step, so pro-rating would read rent paid on the 1st as a month-long overrun.
    """
    db = make_session()
    fixture = Fixture(db)
    fixture.spend(category="Food", on=date(2026, 7, 5), amount="100.00")
    fixture.spend(category="Food", on=date(2026, 8, 5), amount="100.00")
    fixture.spend(category="Food", on=date(2026, 8, 30), amount="900.00")
    fixture.spend(category="Food", on=date(2026, 9, 5), amount="100.00")
    fixture.spend(category="Food", on=date(2026, 10, 5), amount="100.00")

    summary = fixture.summary(month="2026-10", today=date(2026, 10, 26))

    food = row_for(summary, "Food")
    assert food["baseline_amount"] == "100.00"
    assert food["comparison_status"] == "in_line"


def test_the_cutoff_clamps_to_a_shorter_months_own_length() -> None:
    """On the 31st, September contributes all of itself and nothing of October.

    September has thirty days, so a cutoff of "the first 31 days" has to clamp. Left
    unclamped the window would run to the 2nd of October and swallow the 100 the
    owner spent on the 1st, which belongs to the month on screen: September would
    contribute 300 and the baseline would be 233.33 rather than 200.
    """
    db = make_session()
    fixture = Fixture(db)
    fixture.spend(category="Food", on=date(2026, 7, 10), amount="200.00")
    fixture.spend(category="Food", on=date(2026, 8, 10), amount="200.00")
    fixture.spend(category="Food", on=date(2026, 9, 10), amount="200.00")
    fixture.spend(category="Food", on=date(2026, 10, 1), amount="100.00")

    summary = fixture.summary(month="2026-10", today=date(2026, 10, 31))

    food = row_for(summary, "Food")
    assert food["baseline_amount"] == "200.00"
    assert food["spend_amount"] == "100.00"


def test_a_closed_month_is_compared_whole_against_whole() -> None:
    """The cutoff is for the month in progress, not for a month with an outcome.

    September is closed, so July contributes all 1000 of itself rather than the 100
    it had reached by its 26th. Applying the cutoff here would make the baseline 700
    and understate every finished month the owner pages back to.
    """
    db = make_session()
    fixture = Fixture(db)
    fixture.spend(category="Food", on=date(2026, 6, 5), amount="1000.00")
    fixture.spend(category="Food", on=date(2026, 7, 5), amount="100.00")
    fixture.spend(category="Food", on=date(2026, 7, 30), amount="900.00")
    fixture.spend(category="Food", on=date(2026, 8, 5), amount="1000.00")
    fixture.spend(category="Food", on=date(2026, 9, 5), amount="500.00")

    summary = fixture.summary(month="2026-09", today=date(2026, 10, 26))

    food = row_for(summary, "Food")
    assert food["baseline_amount"] == "1000.00"
    assert food["spend_amount"] == "500.00"
    assert food["comparison_status"] == "below"


def test_a_month_that_has_not_started_makes_no_comparison() -> None:
    """There is no outcome to compare, only a standing order waiting to be charged.

    December holds a scheduled payment the bank has already reported, which the
    Effective Date files into it, so the month is not empty -- it just has nothing
    that can be read as a result. The status says which it is rather than leaving the
    reason to be inferred from an empty list, and rather than making each interface
    cross-reference the allowance's tense to find out whether a comparison exists.
    """
    db = make_session()
    fixture = Fixture(db)
    fixture.spend(category="Food", on=date(2026, 9, 5), amount="300.00")
    fixture.spend(category="Food", on=date(2026, 10, 5), amount="300.00")
    fixture.spend(category="Rent", on=date(2026, 12, 1), amount="880.00", status="pending")

    summary = fixture.summary(month="2026-12", today=date(2026, 10, 26))

    assert summary["baseline_status"] == "month_not_started"
    assert summary["category_baselines"] == []


def test_an_archived_category_is_absent_from_the_comparison() -> None:
    """It keeps its history and loses its commentary.

    ADR-0007 keeps an Archived Category named wherever past months are reported, and
    this does not take that away: the figures are still there when the owner pages
    back. What it takes away is the comparison, because a category closed to new
    spend reports itself below its own baseline every month from now until forever,
    which is noise rather than information.
    """
    db = make_session()
    fixture = Fixture(db)
    fixture.category("Gym", active=False)
    fixture.spend(category="Gym", on=date(2026, 8, 5), amount="40.00")
    fixture.spend(category="Gym", on=date(2026, 9, 5), amount="40.00")
    fixture.spend(category="Food", on=date(2026, 8, 6), amount="300.00")
    fixture.spend(category="Food", on=date(2026, 9, 6), amount="300.00")
    fixture.spend(category="Food", on=date(2026, 10, 6), amount="300.00")

    summary = fixture.summary()

    assert [row["category_name"] for row in summary["category_baselines"]] == ["Food"]


def test_an_ignored_transaction_reaches_neither_the_month_nor_the_baseline() -> None:
    """A decision the owner already made is not undone by the comparison.

    Food is 300 in each of July, August and September, so the baseline is 300. The
    900 reimbursement the owner excluded in August would make it 600 if it counted,
    and the 600 excluded this month would treble the figure on screen. GLOSSARY.md
    defines Ignored as excluded from every metric, and a baseline is a metric.
    """
    db = make_session()
    fixture = Fixture(db)
    fixture.spend(category="Food", on=date(2026, 7, 5), amount="300.00")
    fixture.spend(category="Food", on=date(2026, 8, 5), amount="300.00")
    fixture.spend(category="Food", on=date(2026, 8, 6), amount="900.00", excluded=True)
    fixture.spend(category="Food", on=date(2026, 9, 5), amount="300.00")
    fixture.spend(category="Food", on=date(2026, 10, 5), amount="300.00")
    fixture.spend(category="Food", on=date(2026, 10, 6), amount="600.00", excluded=True)

    summary = fixture.summary()

    food = row_for(summary, "Food")
    assert food["baseline_amount"] == "300.00"
    assert food["spend_amount"] == "300.00"
    assert food["comparison_status"] == "in_line"


def test_a_transfer_between_the_owners_own_accounts_is_not_spend() -> None:
    """An automated round-up is movement, not consumption.

    In the owner's live data a round-up saver is 232 near-identical rows across four
    months -- the densest category there is, and a transfer. It must not acquire a
    spending baseline, and the exclusion comes from the same category-type
    restriction every other spend figure already uses.
    """
    db = make_session()
    fixture = Fixture(db)
    fixture.spend(category="RoundUp Savings", on=date(2026, 8, 5), amount="50.00", type_="transfer")
    fixture.spend(category="RoundUp Savings", on=date(2026, 9, 5), amount="50.00", type_="transfer")
    fixture.spend(category="RoundUp Savings", on=date(2026, 10, 5), amount="50.00", type_="transfer")
    fixture.spend(category="Food", on=date(2026, 8, 6), amount="300.00")
    fixture.spend(category="Food", on=date(2026, 9, 6), amount="300.00")
    fixture.spend(category="Food", on=date(2026, 10, 6), amount="300.00")

    summary = fixture.summary()

    assert [row["category_name"] for row in summary["category_baselines"]] == ["Food"]


def test_a_category_with_spend_and_no_budget_still_gets_a_comparison() -> None:
    """The list is keyed by spend, not by budgets, and that is the whole point.

    ``budget_usage`` is built from active budgets, so a category the owner never
    budgeted would have been silently missing had the comparison ridden on that list
    -- and that is precisely the money Unbudgeted Spend exists to disclose. Nothing
    here is budgeted at all, so the budget rows are empty while the comparison is
    not.
    """
    db = make_session()
    fixture = Fixture(db)
    fixture.spend(category="Parking", on=date(2026, 7, 5), amount="20.00")
    fixture.spend(category="Parking", on=date(2026, 8, 5), amount="20.00")
    fixture.spend(category="Parking", on=date(2026, 9, 5), amount="20.00")
    fixture.spend(category="Parking", on=date(2026, 10, 5), amount="20.00")

    summary = fixture.summary()

    assert summary["budget_usage"] == []
    assert row_for(summary, "Parking")["baseline_amount"] == "20.00"


def test_one_qualifying_month_is_not_enough_to_claim_anything() -> None:
    """Below the floor the product says so, rather than comparing against one month.

    September is clean; August hides most of its money in an unfiled row and is
    disqualified; July is empty. That leaves one qualifying month, and a mean of one
    month is not a baseline -- it is last month, wearing a word that implies more.
    The rows still arrive, so the owner sees their spend; what they do not get is a
    comparison.
    """
    db = make_session()
    fixture = Fixture(db)
    fixture.spend(category="Food", on=date(2026, 8, 5), amount="50.00")
    fixture.spend(category=None, on=date(2026, 8, 6), amount="950.00")
    fixture.spend(category="Food", on=date(2026, 9, 5), amount="300.00")
    fixture.spend(category="Food", on=date(2026, 10, 5), amount="300.00")

    summary = fixture.summary()

    assert summary["baseline_status"] == "insufficient_history"
    assert summary["baseline_months_count"] == 1
    food = row_for(summary, "Food")
    assert food["spend_amount"] == "300.00"
    assert food["baseline_amount"] is None
    assert food["deviation_percent"] is None
    assert food["comparison_status"] == "no_baseline"


def test_the_window_bounds_how_far_back_a_baseline_reaches() -> None:
    """The reach is a setting, because the owner's history grows and the mean should.

    Food: 900 in June, then 300 in each of July, August and September. A four-month
    window reaches all four and averages 450; a three-month window leaves June out of
    reach and averages 300.

    The contrast used to be three against two. Two is now below
    ``BASELINE_MINIMUM_MONTHS``, so the narrower window would report no baseline at
    all rather than a narrower one -- which would have made this test about the
    minimum instead of about the reach.

    The window is a parameter over source data rather than anything stored, which is
    what keeps the *shape* cheap to change later: moving to a widening window or to
    exponential decay is a change in one domain function, with no accumulated history
    to convert and no migration. That was the point of refusing a stored accumulator.
    """
    db = make_session()
    fixture = Fixture(db)
    fixture.spend(category="Food", on=date(2026, 6, 5), amount="900.00")
    fixture.spend(category="Food", on=date(2026, 7, 5), amount="300.00")
    fixture.spend(category="Food", on=date(2026, 8, 5), amount="300.00")
    fixture.spend(category="Food", on=date(2026, 9, 5), amount="300.00")
    fixture.spend(category="Food", on=date(2026, 10, 5), amount="300.00")

    over_four = SummaryService(db=db, baseline_window_months=4).get_summary(
        month="2026-10", today=TODAY
    )
    over_three = SummaryService(db=db, baseline_window_months=3).get_summary(
        month="2026-10", today=TODAY
    )

    assert over_four["baseline_months_count"] == 4
    assert row_for(over_four, "Food")["baseline_amount"] == "450.00"
    assert over_three["baseline_months_count"] == 3
    assert row_for(over_three, "Food")["baseline_amount"] == "300.00"


def test_the_window_setting_reaches_the_service_through_the_dependency() -> None:
    """A setting nothing reads is the same as no setting.

    Neither test above would notice the wiring being absent, because both construct
    the service directly. This one goes through the dependency the route actually
    uses, and asserts the behaviour rather than the attribute: with the window set to
    four months, June's 900 comes into reach and the baseline is 450 rather than 300.
    """
    from burnrate.api.dependencies import get_summary_service
    from burnrate.config import Settings

    db = make_session()
    fixture = Fixture(db)
    fixture.spend(category="Food", on=date(2026, 6, 5), amount="900.00")
    fixture.spend(category="Food", on=date(2026, 7, 5), amount="300.00")
    fixture.spend(category="Food", on=date(2026, 8, 5), amount="300.00")
    fixture.spend(category="Food", on=date(2026, 9, 5), amount="300.00")
    fixture.spend(category="Food", on=date(2026, 10, 5), amount="300.00")

    settings = Settings(BANK_TOKEN_ENCRYPTION_KEY="x" * 44, BASELINE_WINDOW_MONTHS=4)
    assert Settings(BANK_TOKEN_ENCRYPTION_KEY="x" * 44).baseline_window_months == 3

    service = get_summary_service(db=db, settings=settings)
    summary = service.get_summary(month="2026-10", today=TODAY)

    assert summary["baseline_months_count"] == 4
    assert row_for(summary, "Food")["baseline_amount"] == "450.00"


def test_too_little_history_withholds_a_baseline_the_presence_floor_would_allow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The minimum-months rule, isolated from the presence floor that shadows it.

    Found by mutation rather than by reading. The test above looked like it covered
    this and did not: with one Qualifying Month a category can have spend in at most
    one of them, so the presence floor already refuses it and disabling the
    minimum-months rule changed nothing. The two rules masked each other and the
    mutation survived.

    They are separate constants precisely so either can move, and lowering the
    presence floor to one is what makes the other rule observable: September alone
    then clears the floor, and only the minimum-months rule stands between the owner
    and a "baseline" that is just last month wearing a word implying more.
    """
    monkeypatch.setattr("burnrate.domain.baselines.BASELINE_PRESENCE_FLOOR", 1)

    db = make_session()
    fixture = Fixture(db)
    fixture.spend(category="Food", on=date(2026, 8, 5), amount="50.00")
    fixture.spend(category=None, on=date(2026, 8, 6), amount="950.00")
    fixture.spend(category="Food", on=date(2026, 9, 5), amount="300.00")
    fixture.spend(category="Food", on=date(2026, 10, 5), amount="300.00")

    summary = fixture.summary()

    assert summary["baseline_status"] == "insufficient_history"
    assert summary["baseline_months_count"] == 1
    food = row_for(summary, "Food")
    assert food["baseline_amount"] is None
    assert food["comparison_status"] == "no_baseline"


def test_a_month_with_a_sync_hole_is_excluded_though_it_looks_fully_classified() -> None:
    """The test classification coverage is blind to, and that is the whole point.

    All four months behind the one on screen are fully classified -- every row they
    hold is filed, so coverage by amount reads 0% unfiled for each. August is
    nevertheless missing transactions, because syncs stopped on the 2nd and did not
    resume until the 20th of September, so the 3rd of August to the 20th was never
    asked about.

    Food is 450 in June, 600 in July, 100 in the gap-ridden August and 300 in
    September. Excluding August gives a baseline of 450; admitting it on its
    classification alone gives 362.50, understated by a month whose figures were
    never complete. An understated
    baseline is the one that makes ordinary spend look like an anomaly.
    """
    db = make_session()
    fixture = Fixture(db, synced=False)
    # Covers June and July in full: the windows reaching back from 2 August span them.
    fixture.sync_daily(date(2026, 6, 1), date(2026, 8, 2))
    # Then nothing until late September. [Jul 21, Aug 2] and [Aug 21, Sep 20] leave
    # the 3rd to the 20th of August unasked, while September is covered from here on.
    fixture.sync_daily(date(2026, 9, 20), date(2026, 10, 26))

    fixture.spend(category="Food", on=date(2026, 6, 5), amount="450.00")
    fixture.spend(category="Food", on=date(2026, 7, 5), amount="600.00")
    fixture.spend(category="Food", on=date(2026, 8, 5), amount="100.00")
    fixture.spend(category="Food", on=date(2026, 9, 5), amount="300.00")
    fixture.spend(category="Food", on=date(2026, 10, 5), amount="450.00")

    summary = fixture.summary(window=4)

    assert summary["baseline_months_count"] == 3
    assert row_for(summary, "Food")["baseline_amount"] == "450.00"


def test_an_expired_consent_leaves_session_rows_that_are_not_coverage() -> None:
    """A row per attempt is not a row per answer.

    This is the shape the real failure takes. When the consent lapses the import
    writes a ``skipped`` session for every attempt and fetches nothing, so the gap is
    papered over with an unbroken chain of session rows. Counting rows rather than
    successes would read August as covered on the strength of runs that asked the
    bank nothing at all.

    Identical to the test above except that the gap is full of attempts, and the
    answer has to be identical too.
    """
    db = make_session()
    fixture = Fixture(db, synced=False)
    fixture.sync_daily(date(2026, 6, 1), date(2026, 8, 2))
    fixture.sync_daily(date(2026, 8, 3), date(2026, 9, 19), status="skipped")
    fixture.sync_daily(date(2026, 9, 20), date(2026, 10, 26))

    fixture.spend(category="Food", on=date(2026, 6, 5), amount="450.00")
    fixture.spend(category="Food", on=date(2026, 7, 5), amount="600.00")
    fixture.spend(category="Food", on=date(2026, 8, 5), amount="100.00")
    fixture.spend(category="Food", on=date(2026, 9, 5), amount="300.00")
    fixture.spend(category="Food", on=date(2026, 10, 5), amount="450.00")

    summary = fixture.summary(window=4)

    assert summary["baseline_months_count"] == 3
    assert row_for(summary, "Food")["baseline_amount"] == "450.00"


def test_a_sync_hole_can_leave_too_little_history_to_compare_at_all() -> None:
    """And when it does, the product says so rather than thinning the mean quietly.

    Two clean months behind October, one of them never fully asked about. That leaves
    one Qualifying Month, which is not a baseline.
    """
    db = make_session()
    fixture = Fixture(db, synced=False)
    fixture.sync_daily(date(2026, 9, 20), date(2026, 10, 26))

    fixture.spend(category="Food", on=date(2026, 8, 5), amount="100.00")
    fixture.spend(category="Food", on=date(2026, 9, 5), amount="300.00")
    fixture.spend(category="Food", on=date(2026, 10, 5), amount="300.00")

    summary = fixture.summary()

    assert summary["baseline_status"] == "insufficient_history"
    assert summary["baseline_months_count"] == 1
    assert row_for(summary, "Food")["baseline_amount"] is None


def test_the_aggregate_comparison_leaves_out_what_it_cannot_compare() -> None:
    """The month this whole split exists for.

    Shaped after the owner's live October. Food and Invoices both have three clean
    months behind them -- 400 and 180 usual, respectively -- and both come in under
    that: 250 and 45, so 295 spent where 580 is normal, a notably quiet month. A
    one-off legal expense of 8400 has no history and so no baseline.

    The comparison speaks only to the 295 against the 580 and reads 49% below. Were
    the uncomparable 8400 folded in, the same month would report 8695 against 580 --
    fifteen times normal -- and the product would cry catastrophic overspending in a
    month where every category the owner controls came in cheap.

    The 8400 is disclosed rather than dropped, and the three figures reconcile
    against the month's spending: Uncomparable Spend is defined as the residual, so
    comparable plus uncomparable is exactly the headline above them.
    """
    db = make_session()
    fixture = Fixture(db)
    fixture.spend(category="Food", on=date(2026, 7, 5), amount="400.00")
    fixture.spend(category="Invoices", on=date(2026, 7, 5), amount="180.00")
    fixture.spend(category="Food", on=date(2026, 8, 5), amount="500.00")
    fixture.spend(category="Invoices", on=date(2026, 8, 5), amount="200.00")
    fixture.spend(category="Food", on=date(2026, 9, 5), amount="300.00")
    fixture.spend(category="Invoices", on=date(2026, 9, 5), amount="160.00")
    fixture.spend(category="Food", on=date(2026, 10, 5), amount="250.00")
    fixture.spend(category="Invoices", on=date(2026, 10, 5), amount="45.00")
    fixture.spend(category="Divorce", on=date(2026, 10, 5), amount="8400.00")

    summary = fixture.summary()

    assert summary["comparable_spend_amount"] == "295.00"
    assert summary["uncomparable_spend_amount"] == "8400.00"
    assert summary["comparable_spend_baseline"]["baseline_amount"] == "580.00"
    assert summary["comparable_spend_baseline"]["comparison_status"] == "below"
    assert summary["comparable_spend_baseline"]["deviation_percent"] == -49.1
    # The headline is untouched and the split reconciles against it.
    assert summary["monthly_spending_amount"] == "8695.00"


def test_income_is_shown_against_what_the_owner_normally_earns() -> None:
    """A short payslip should be visible the month it happens, not at year end.

    Two thousand in each of July, August and September, fourteen hundred this month:
    30% down, which for a salaried owner is the single most consequential thing that can
    change about their month.

    Income needs no comparable split. That split exists because per-category spend
    baselines feed the spend aggregate and a category without one would poison it;
    income is one whole-month figure with no per-category decomposition in play.

    The Food rows are not decoration -- a month qualifies on the share of its
    *outgoing* money that is classified, so a month holding only income has nothing
    to measure coverage over and would not qualify at all.
    """
    db = make_session()
    fixture = Fixture(db)
    fixture.income(category="Salary", on=date(2026, 7, 25), amount="2000.00")
    fixture.income(category="Salary", on=date(2026, 8, 25), amount="2000.00")
    fixture.income(category="Salary", on=date(2026, 9, 25), amount="2000.00")
    fixture.income(category="Salary", on=date(2026, 10, 25), amount="1400.00")
    fixture.spend(category="Food", on=date(2026, 7, 5), amount="300.00")
    fixture.spend(category="Food", on=date(2026, 8, 5), amount="300.00")
    fixture.spend(category="Food", on=date(2026, 9, 5), amount="300.00")
    fixture.spend(category="Food", on=date(2026, 10, 5), amount="300.00")

    summary = fixture.summary()

    assert summary["monthly_income_amount"] == "1400.00"
    assert summary["monthly_income_baseline"]["baseline_amount"] == "2000.00"
    assert summary["monthly_income_baseline"]["deviation_percent"] == -30.0
    assert summary["monthly_income_baseline"]["comparison_status"] == "below"


def test_an_aggregate_figure_has_no_presence_floor() -> None:
    """A month with no income at all is a real zero, not a month to leave out.

    The presence floor exists for a category the owner spends in too rarely to have
    a normal monthly cost. An aggregate figure has no such notion: a month in which
    nothing came in is a fact about the owner's year, and dropping it would report a
    salary as normal to someone who was paid once in three months.

    July, August and September each saw 2000 and October nothing, so the usual figure
    is 2000 and this month is 100% down.
    """
    db = make_session()
    fixture = Fixture(db)
    fixture.income(category="Salary", on=date(2026, 7, 25), amount="2000.00")
    fixture.income(category="Salary", on=date(2026, 8, 25), amount="2000.00")
    fixture.income(category="Salary", on=date(2026, 9, 25), amount="2000.00")
    fixture.spend(category="Food", on=date(2026, 7, 5), amount="300.00")
    fixture.spend(category="Food", on=date(2026, 8, 5), amount="300.00")
    fixture.spend(category="Food", on=date(2026, 9, 5), amount="300.00")
    fixture.spend(category="Food", on=date(2026, 10, 5), amount="300.00")

    summary = fixture.summary()

    assert summary["monthly_income_amount"] == "0.00"
    assert summary["monthly_income_baseline"]["baseline_amount"] == "2000.00"
    assert summary["monthly_income_baseline"]["deviation_percent"] == -100.0


def test_net_cash_flow_gets_a_baseline_amount_and_deliberately_no_verdict() -> None:
    """The owner normally keeps 1700 a month. This month they are 6700 down.

    The amount is published and the band is not, because a ratio on a figure that
    can cross zero means nothing: 1700 against -6700 is a ratio of -3.94, which no
    band reads sensibly, and an owner whose usual month is a deficit would have a
    negative baseline that the band logic treats as no baseline at all -- a status
    saying there is none beside an amount saying there is. The two figures side by
    side already say it: normally this much kept, this month this much.

    Net cash flow also takes no comparable split. The split is for per-category
    spend baselines feeding an aggregate; "this month was much worse than usual"
    about money kept is simply true, one-off included, which is exactly what makes
    it different from reporting the owner overspent.
    """
    db = make_session()
    fixture = Fixture(db)
    for month in (7, 8, 9, 10):
        fixture.income(category="Salary", on=date(2026, month, 25), amount="2000.00")
        fixture.spend(category="Food", on=date(2026, month, 5), amount="300.00")
    fixture.spend(category="Divorce", on=date(2026, 10, 6), amount="8400.00")

    summary = fixture.summary()

    assert summary["net_cash_flow_amount"] == "-6700.00"
    assert summary["net_cash_flow_baseline_amount"] == "1700.00"
    assert "net_cash_flow_baseline" not in summary


def test_the_daily_allowance_is_given_no_baseline() -> None:
    """Comparing an allowance across months compares three things that all moved.

    The budget, the month's length and the fixed overrun all differ between any two
    months, so a change in the allowance says nothing the owner can act on. The
    baseline belongs on spend, which is what the allowance is derived from.
    """
    db = make_session()
    fixture = Fixture(db)
    fixture.spend(category="Food", on=date(2026, 8, 5), amount="300.00")
    fixture.spend(category="Food", on=date(2026, 9, 5), amount="300.00")
    fixture.spend(category="Food", on=date(2026, 10, 5), amount="300.00")

    summary = fixture.summary()

    assert not [key for key in summary if key.startswith("safe_to_spend") and "baseline" in key]


def test_paging_back_to_a_closed_month_compares_it_against_the_months_before_it() -> None:
    """The baseline is not only ever about today.

    Viewed from the 26th of October, September is closed: its window reaches June,
    July and August, all three of which hold spend and qualify. Food's usual figure
    there is 500, September spent 300, so the month that has already happened reads
    40% below -- compared whole against whole, since the cutoff is for a month
    still in progress.
    """
    db = make_session()
    fixture = Fixture(db)
    fixture.spend(category="Food", on=date(2026, 6, 5), amount="500.00")
    fixture.spend(category="Food", on=date(2026, 7, 5), amount="600.00")
    fixture.spend(category="Food", on=date(2026, 8, 5), amount="400.00")
    fixture.spend(category="Food", on=date(2026, 9, 5), amount="300.00")

    summary = fixture.summary(month="2026-09", today=date(2026, 10, 26))

    assert summary["baseline_months_count"] == 3
    assert summary["comparable_spend_amount"] == "300.00"
    assert summary["comparable_spend_baseline"]["baseline_amount"] == "500.00"
    assert summary["comparable_spend_baseline"]["deviation_percent"] == -40.0
    assert summary["uncomparable_spend_amount"] == "0.00"


def test_with_too_little_history_the_whole_month_is_reported_as_uncomparable() -> None:
    """Which is the honest answer: nothing in it can be compared to anything.

    One Qualifying Month, so no category earns a baseline and the comparable half is
    empty. The residual then covers the month's entire spending, every amount the
    comparison would have spoken to is null rather than zero, and no verdict is
    offered on any of the three figures.
    """
    db = make_session()
    fixture = Fixture(db)
    fixture.spend(category="Food", on=date(2026, 8, 5), amount="50.00")
    fixture.spend(category=None, on=date(2026, 8, 6), amount="950.00")
    fixture.spend(category="Food", on=date(2026, 9, 5), amount="300.00")
    fixture.spend(category="Food", on=date(2026, 10, 5), amount="300.00")
    fixture.income(category="Salary", on=date(2026, 10, 25), amount="2000.00")

    summary = fixture.summary()

    assert summary["baseline_status"] == "insufficient_history"
    assert summary["comparable_spend_amount"] == "0.00"
    assert summary["uncomparable_spend_amount"] == "300.00"
    assert summary["monthly_spending_amount"] == "300.00"
    assert summary["comparable_spend_baseline"]["baseline_amount"] is None
    assert summary["comparable_spend_baseline"]["comparison_status"] == "no_baseline"
    assert summary["monthly_income_baseline"]["baseline_amount"] is None
    assert summary["net_cash_flow_baseline_amount"] is None


def test_a_hold_on_a_fixed_bill_counts_towards_the_comparison_as_little_as_elsewhere() -> None:
    """The two bases have to be the same one, or the residual goes negative.

    Uncomparable Spend is defined as the month's spending less the comparable half,
    so the two halves reconcile against the headline rather than against a third
    total of their own. That only holds while both count the same money -- and a
    hold on a Fixed Budget's category is money the headline does not count, per
    ADR-0003: the budgeted estimate already stands for the whole commitment.

    Rent is 500 in each of the three Qualifying Months and held, not booked, on the
    1st of the month on screen. Counting that hold on the comparison side alone
    gave 0.00 spent, 500.00 comparable and *minus* 500.00 that cannot be compared --
    a figure the dashboard hid and the bot published.
    """
    db = make_session()
    fixture = Fixture(db)
    fixture.fixed_budget(category="Rent", amount="500.00", active_from=date(2026, 7, 1))
    fixture.spend(category="Rent", on=date(2026, 7, 1), amount="500.00")
    fixture.spend(category="Rent", on=date(2026, 8, 1), amount="500.00")
    fixture.spend(category="Rent", on=date(2026, 9, 1), amount="500.00")
    fixture.spend(category="Rent", on=date(2026, 10, 1), amount="500.00", status="pending")

    summary = fixture.summary()

    assert summary["monthly_spending_amount"] == "0.00"
    assert summary["comparable_spend_amount"] == "0.00"
    assert summary["uncomparable_spend_amount"] == "0.00"
    rent = row_for(summary, "Rent")
    assert rent["spend_amount"] == "0.00"
    assert rent["baseline_amount"] == "500.00"


def test_a_qualifying_months_own_hold_on_a_fixed_bill_is_excluded_too() -> None:
    """The rule is the same rule in every month, which is the point of fixing it.

    A baseline measured on a wider basis than the figure it is compared against is
    the defect above wearing a different hat: the month on screen would be judged
    against history that counted holds it does not count itself.

    Rent held in July, booked in August, held again in September, booked in the month
    on screen. July and September therefore contribute nothing, which leaves Rent
    present in one Qualifying Month out of three -- below the presence floor, so
    there is no normal monthly cost to report. Counting those holds would have
    published a 500.00 baseline instead.

    One of three and not one of two, and the difference is the point: with two
    Qualifying Months the window itself was below ``BASELINE_MINIMUM_MONTHS``, so
    *nothing* got a baseline and this test passed without the presence floor being
    consulted at all. Lowering the floor to 1 changed nothing and the mutation
    survived -- the two rules masked each other, which is the shape ``AGENTS.md``
    names. With three months the window is satisfied and the floor is the only thing
    left standing between the hold and a baseline.
    """
    db = make_session()
    fixture = Fixture(db)
    fixture.fixed_budget(category="Rent", amount="500.00", active_from=date(2026, 7, 1))
    fixture.spend(category="Rent", on=date(2026, 7, 1), amount="500.00", status="pending")
    fixture.spend(category="Rent", on=date(2026, 8, 1), amount="500.00")
    fixture.spend(category="Rent", on=date(2026, 9, 1), amount="500.00", status="pending")
    fixture.spend(category="Rent", on=date(2026, 10, 1), amount="500.00")

    summary = fixture.summary()

    assert summary["baseline_status"] == "ok"
    assert summary["baseline_months_count"] == 3
    rent = row_for(summary, "Rent")
    assert rent["spend_amount"] == "500.00"
    assert rent["baseline_amount"] is None
    assert rent["comparison_status"] == "no_baseline"
    # Disclosed rather than dropped: the headline still counts the rent.
    assert summary["monthly_spending_amount"] == "500.00"
    assert summary["uncomparable_spend_amount"] == "500.00"


def test_each_month_is_asked_whether_the_category_was_fixed_in_that_month() -> None:
    """A budget window is month-granular, so "fixed" is a fact about a month.

    Rent became a Fixed Budget in October. July, August and September were not
    covered by it, so a hold in any of them was ordinary committed spend and counted
    -- which is what their own figures said at the time. Reading the month on
    screen's budgets across the whole window would retroactively disqualify all three
    holds and leave Rent present in no Qualifying Month at all, publishing no
    baseline where there is one.
    """
    db = make_session()
    fixture = Fixture(db)
    fixture.fixed_budget(category="Rent", amount="500.00", active_from=date(2026, 10, 1))
    fixture.spend(category="Rent", on=date(2026, 7, 1), amount="500.00", status="pending")
    fixture.spend(category="Rent", on=date(2026, 8, 1), amount="500.00", status="pending")
    fixture.spend(category="Rent", on=date(2026, 9, 1), amount="500.00", status="pending")
    fixture.spend(category="Rent", on=date(2026, 10, 1), amount="500.00", status="pending")

    summary = fixture.summary()

    rent = row_for(summary, "Rent")
    assert rent["baseline_amount"] == "500.00"
    # October's own hold is excluded, because October is the month Rent is fixed in.
    assert rent["spend_amount"] == "0.00"
    assert summary["monthly_spending_amount"] == "0.00"
    assert summary["uncomparable_spend_amount"] == "0.00"


def test_a_hold_on_a_variable_category_still_counts_on_both_sides() -> None:
    """The exclusion is about Fixed Budgets, not about pending spend.

    Pending spend is load-bearing in the variable slice -- it is money the owner has
    committed -- so a hold on a category with no Fixed Budget counts in the headline
    and in the comparison alike. Without this, the fix above would quietly become
    "the comparison ignores pending".
    """
    db = make_session()
    fixture = Fixture(db)
    fixture.spend(category="Food", on=date(2026, 7, 5), amount="300.00")
    fixture.spend(category="Food", on=date(2026, 8, 5), amount="300.00")
    fixture.spend(category="Food", on=date(2026, 9, 5), amount="300.00")
    fixture.spend(category="Food", on=date(2026, 10, 5), amount="200.00", status="pending")

    summary = fixture.summary()

    assert summary["monthly_spending_amount"] == "200.00"
    assert summary["comparable_spend_amount"] == "200.00"
    assert summary["uncomparable_spend_amount"] == "0.00"
    assert row_for(summary, "Food")["spend_amount"] == "200.00"


def test_a_bonus_month_is_not_an_anomaly() -> None:
    """Income is banded, and never fired on.

    ``comparison_status`` is given the flag here, not a figure it can judge for
    itself, so this is the seam where the income path could silently start firing
    again. 3000 against a 2000 normal is twice the anomaly ratio's distance past
    the in_line band; both clients word an anomaly "unusually high", and there is
    nothing wrong with being paid more than usual.
    """
    db = make_session()
    fixture = Fixture(db)
    for month in (7, 8, 9):
        fixture.income(category="Salary", on=date(2026, month, 5), amount="2000.00")
        fixture.spend(category="Food", on=date(2026, month, 5), amount="300.00")
    fixture.income(category="Salary", on=date(2026, 10, 5), amount="3000.00")
    fixture.spend(category="Food", on=date(2026, 10, 5), amount="300.00")

    summary = fixture.summary()

    income = summary["monthly_income_baseline"]
    assert income["baseline_amount"] == "2000.00"
    assert income["deviation_percent"] == 50.0
    assert income["comparison_status"] == "above"


def test_an_event_budgets_spend_reaches_no_baseline() -> None:
    """A Fixed Budget bounded to one month says that month's spend was an event.

    Shaped so the event rule is the only thing that can produce the answer. Divorce
    has spend in **two** Qualifying Months -- 8400 in August and 1200 in September,
    each under a budget bounded to its own month -- so it clears
    ``BASELINE_PRESENCE_FLOOR`` on its own and the floor cannot be what refuses it.
    Without the rule the owner would be told a divorce normally costs them 3200 a
    month.

    The aggregate is the discriminating half. Net cash flow over the three months is
    1700, 1700 and 1700 with the rule and 1700, -6700 and 500 without it, so the
    baseline is 1700 against -1500: the product either reports the owner normally
    keeps 1700 a month or that they normally run a deficit, from the same data.
    """
    db = make_session()
    fixture = Fixture(db)
    for month in (7, 8, 9, 10):
        fixture.income(category="Salary", on=date(2026, month, 25), amount="2000.00")
        fixture.spend(category="Food", on=date(2026, month, 5), amount="300.00")
    fixture.bounded_fixed_budget(
        category="Divorce",
        amount="8400.00",
        active_from=date(2026, 8, 1),
        active_to=date(2026, 8, 31),
    )
    fixture.spend(category="Divorce", on=date(2026, 8, 9), amount="8400.00")
    fixture.bounded_fixed_budget(
        category="Divorce",
        amount="1200.00",
        active_from=date(2026, 9, 1),
        active_to=date(2026, 9, 30),
    )
    fixture.spend(category="Divorce", on=date(2026, 9, 9), amount="1200.00")
    # And once more in the month on screen, so the row exists to be asserted on. Its
    # spend is a figure and counts; only the months behind it are baseline input.
    fixture.bounded_fixed_budget(
        category="Divorce",
        amount="500.00",
        active_from=date(2026, 10, 1),
        active_to=date(2026, 10, 31),
    )
    fixture.spend(category="Divorce", on=date(2026, 10, 9), amount="500.00")

    summary = fixture.summary()

    assert summary["baseline_status"] == "ok"
    assert summary["baseline_months_count"] == 3
    divorce = row_for(summary, "Divorce")
    assert divorce["spend_amount"] == "500.00"
    assert divorce["baseline_amount"] is None
    assert divorce["comparison_status"] == "no_baseline"
    assert row_for(summary, "Food")["baseline_amount"] == "300.00"
    assert summary["net_cash_flow_baseline_amount"] == "1700.00"


def test_an_event_budget_still_counts_in_the_month_it_happened() -> None:
    """Counted in the actuals, excluded from every baseline -- and only the baseline.

    The same phrase ADR-0003 established for Pending Spend: a figure-specific
    inclusion rule, not a disposition that removes a row from everything. An Event
    Budget in the month on screen is money that left, so monthly spending and net
    cash flow carry it whole. Applying the exclusion to ``_get_monthly_spend`` as
    well would make it a quieter ``excluded_at``, which is a different primitive and
    one the product already has.
    """
    db = make_session()
    fixture = Fixture(db)
    for month in (7, 8, 9, 10):
        fixture.income(category="Salary", on=date(2026, month, 25), amount="2000.00")
        fixture.spend(category="Food", on=date(2026, month, 5), amount="300.00")
    fixture.bounded_fixed_budget(
        category="Divorce",
        amount="8400.00",
        active_from=date(2026, 10, 1),
        active_to=date(2026, 10, 31),
    )
    fixture.spend(category="Divorce", on=date(2026, 10, 9), amount="8400.00")

    summary = fixture.summary()

    assert summary["monthly_spending_amount"] == "8700.00"
    assert summary["net_cash_flow_amount"] == "-6700.00"
    # Nothing to compare it against, so it is disclosed as the residual rather than
    # folded into a comparison that would read the month as catastrophic.
    assert summary["comparable_spend_amount"] == "300.00"
    assert summary["uncomparable_spend_amount"] == "8400.00"


def test_an_open_ended_fixed_budget_is_not_an_event() -> None:
    """Rent is a habit, and the rule must not read every Fixed Budget as an event.

    The one thing that separates them is the bounded window: an open ``active_to``
    means the commitment continues, which is the whole argument the roadmap makes for
    reading the window instead of asking the owner to flag a charge. Rent at 500 a
    month has to keep its baseline.
    """
    db = make_session()
    fixture = Fixture(db)
    fixture.fixed_budget(category="Rent", amount="500.00", active_from=date(2026, 7, 1))
    for month in (7, 8, 9, 10):
        fixture.spend(category="Rent", on=date(2026, month, 1), amount="500.00")

    summary = fixture.summary()

    assert row_for(summary, "Rent")["baseline_amount"] == "500.00"
    assert row_for(summary, "Rent")["comparison_status"] == "in_line"


def test_a_fixed_budget_spanning_two_months_is_not_an_event() -> None:
    """"Exactly one month" is the rule, and two is the boundary that proves it.

    A window bounded to August and September is a commitment that ran for two months
    and stopped -- a sublet, a course, a contract -- not an event. ADR-0005 puts both
    edges of a window on month boundaries, so the question is exact and this is the
    nearest input that must answer it the other way.

    Rent is present in both Qualifying Months at 500, so it clears the presence floor
    and earns a 333.33 baseline across the three months the window reaches. Were the
    rule reading "bounded" rather than "bounded to one month", it would read None.
    """
    db = make_session()
    fixture = Fixture(db)
    fixture.bounded_fixed_budget(
        category="Rent",
        amount="500.00",
        active_from=date(2026, 8, 1),
        active_to=date(2026, 9, 30),
    )
    fixture.spend(category="Rent", on=date(2026, 8, 1), amount="500.00")
    fixture.spend(category="Rent", on=date(2026, 9, 1), amount="500.00")
    fixture.spend(category="Food", on=date(2026, 7, 5), amount="300.00")
    fixture.spend(category="Food", on=date(2026, 10, 5), amount="300.00")

    summary = fixture.summary()

    assert summary["baseline_months_count"] == 3
    assert row_for(summary, "Rent")["baseline_amount"] == "333.33"


def test_one_exceptional_month_does_not_become_the_owners_normal() -> None:
    """The aggregate baselines are medians, observed where the product serves them.

    Every other fixture in this module seeds months with identical figures, where a
    median and a mean agree -- which is why a plain mean survived in the one place it
    did the most damage. This one puts an outlier in the window.

    Shaped after the owner's real July: a 5500 severance among two ordinary months of
    1000. The median says a typical month brings in 1000, so October's 1000 is in
    line. The mean would say 2500, and the month their income returned to normal
    would be published as 60% down -- a product telling someone out of work that
    their income had collapsed.

    An exceptional *income* is the case no budget and no Event Budget can reach,
    because there is no window to bound. This is what covers it.
    """
    db = make_session()
    fixture = Fixture(db)
    fixture.income(category="Salary", on=date(2026, 7, 25), amount="5500.00")
    for month in (8, 9, 10):
        fixture.income(category="Salary", on=date(2026, month, 25), amount="1000.00")
    for month in (7, 8, 9, 10):
        fixture.spend(category="Food", on=date(2026, month, 5), amount="300.00")

    summary = fixture.summary()

    assert summary["baseline_months_count"] == 3
    income = summary["monthly_income_baseline"]
    assert income["baseline_amount"] == "1000.00"
    assert income["deviation_percent"] == 0.0
    assert income["comparison_status"] == "in_line"
    # Net cash flow over the same three months: 5200, 700, 700. The mean is 2200.
    assert summary["net_cash_flow_baseline_amount"] == "700.00"


def test_the_summary_reports_a_sync_hole_the_product_already_knew_about() -> None:
    """The one case the product knows something the owner cannot see.

    This is the failure that actually happened: the worker was not running from 29
    August to 4 October 2026, so 30 August to 3 September was never fetched. A worker
    that is down cannot report itself, which is why this is read at **request** time
    -- the owner opening the app is the only path that catches it.

    The status is decided here rather than derived by each interface, following the
    amendment ADR-0002 records: a state each client derives is a state each client can
    derive differently.
    """
    db = make_session()
    fixture = Fixture(db, synced=False)
    fixture.sync_daily(date(2026, 8, 1), date(2026, 8, 29))
    fixture.sync_daily(date(2026, 10, 4), date(2026, 10, 26))
    fixture.spend(category="Food", on=date(2026, 9, 10), amount="300.00")

    # Viewed on September, which is one of the months that lost the days. October's
    # own view reports the same facts as ``lost_elsewhere``; that scoping has its own
    # test below.
    summary = fixture.summary(month="2026-09")

    gap = summary["sync_gap"]
    assert gap is not None
    assert gap["status"] == "lost"
    assert gap["oldest_missing_day"] == "2026-08-30"
    assert gap["missing_days"] == 5
    assert gap["unrecoverable_days"] == 5
    assert gap["recoverable_until"] is None


def test_the_summary_says_nothing_about_sync_when_every_day_was_asked_about() -> None:
    """A healthy history earns silence, not a reassurance nobody asked for."""
    db = make_session()
    fixture = Fixture(db)
    fixture.spend(category="Food", on=date(2026, 10, 5), amount="300.00")

    assert fixture.summary()["sync_gap"] is None


def test_the_summary_reports_a_hole_still_within_reach_with_its_deadline() -> None:
    """The worker is alive and its syncs are failing, which is the recoverable case.

    Nothing is lost yet, so the message is a date rather than an apology: the owner
    can reconnect the bank and the days come back. Distinguished from the lost case by
    a status, so the dashboard and the bot cannot word it differently.
    """
    db = make_session()
    fixture = Fixture(db, synced=False)
    fixture.sync_daily(date(2026, 9, 1), date(2026, 10, 10))
    fixture.spend(category="Food", on=date(2026, 10, 5), amount="300.00")

    summary = fixture.summary(month="2026-11", today=date(2026, 11, 5))

    gap = summary["sync_gap"]
    assert gap is not None
    assert gap["status"] == "expiring"
    assert gap["oldest_missing_day"] == "2026-10-11"
    assert gap["unrecoverable_days"] == 0
    assert gap["recoverable_until"] == "2026-11-10"


def test_a_months_own_loss_is_reported_on_that_month_and_not_on_a_later_one() -> None:
    """Days lost in August are a fact about August, not about the November screen.

    The first version of this put one banner above every month's figures for as long
    as the lookback reached, which on the owner's data meant a permanent notice about
    the move they made in August sitting on top of November. Nothing to do, every
    time they opened the app -- which is how a warning becomes furniture.

    So the status is scoped here: ``lost`` when the month being viewed holds the
    missing days, ``lost_elsewhere`` when the loss is real and belongs to another
    month. The fact stays in the payload either way, because an interface that wants
    to surface it somewhere quieter should not have to re-derive it.
    """
    db = make_session()
    fixture = Fixture(db, synced=False)
    fixture.sync_daily(date(2026, 8, 1), date(2026, 8, 29))
    fixture.sync_daily(date(2026, 10, 4), date(2026, 11, 30))
    fixture.spend(category="Food", on=date(2026, 9, 10), amount="300.00")
    fixture.spend(category="Food", on=date(2026, 11, 5), amount="300.00")

    viewing_november = fixture.summary(month="2026-11", today=date(2026, 11, 20))
    viewing_september = fixture.summary(month="2026-09", today=date(2026, 11, 20))

    assert viewing_november["sync_gap"]["status"] == "lost_elsewhere"
    assert viewing_september["sync_gap"]["status"] == "lost"
    # The same five days in both: one fact, two views of it.
    assert viewing_november["sync_gap"]["unrecoverable_days"] == 5
    assert viewing_september["sync_gap"]["unrecoverable_days"] == 5


def test_a_hole_still_worth_acting_on_is_reported_whatever_month_is_open() -> None:
    """``expiring`` is about today, so paging back does not silence it.

    Unlike a loss, this is an ask with a deadline, and the deadline does not care
    which month the owner happens to be looking at.
    """
    db = make_session()
    fixture = Fixture(db, synced=False)
    fixture.sync_daily(date(2026, 9, 1), date(2026, 10, 10))
    fixture.spend(category="Food", on=date(2026, 9, 10), amount="300.00")

    viewing_september = fixture.summary(month="2026-09", today=date(2026, 11, 5))

    assert viewing_september["sync_gap"]["status"] == "expiring"
