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
from burnrate.db.models import Account, Category, SyncSession, Transaction
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

    def summary(self, *, month: str = "2026-10", today: date = TODAY) -> dict:
        return SummaryService(db=self.db).get_summary(month=month, today=today)


def row_for(summary: dict, name: str) -> dict:
    rows = [row for row in summary["category_baselines"] if row["category_name"] == name]
    assert len(rows) == 1, f"expected one {name} row, got {len(rows)}"
    return rows[0]


def test_a_category_with_spend_in_two_qualifying_months_gets_a_baseline() -> None:
    """The tracer bullet: two clean months behind the one on screen produce a mean.

    August and September are fully classified and so both qualify; October is the
    month on screen and is never its own baseline input. 600 and 300 over the two of
    them is 450, and the 200 spent this month is well under it.
    """
    db = make_session()
    fixture = Fixture(db)
    fixture.spend(category="Food", on=date(2026, 8, 5), amount="600.00")
    fixture.spend(category="Food", on=date(2026, 9, 5), amount="300.00")
    fixture.spend(category="Food", on=date(2026, 10, 5), amount="200.00")

    summary = fixture.summary()

    assert summary["baseline_status"] == "ok"
    assert summary["baseline_months_count"] == 2
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

    * July is clean and qualifies either way. Food: 300.
    * August hides 905 of its 1000 in a single unfiled row among twenty. By money it
      is 90.5% unfiled and disqualified; by rows it is 5% unfiled and admitted.
      Food: 95.
    * September has ten unfiled rows of 2.00 beside one Food charge of 600. By money
      it is 3.2% unfiled and admitted; by rows it is 90.9% unfiled and disqualified.

    So both measures find exactly two qualifying months and the count cannot tell
    them apart -- but by money the baseline is (300 + 600) / 2 = 450, and by rows it
    would be (300 + 95) / 2 = 197.50. The baseline is the discriminating assertion.
    """
    db = make_session()
    fixture = Fixture(db)

    fixture.spend(category="Food", on=date(2026, 7, 5), amount="300.00")

    for _ in range(19):
        fixture.spend(category="Food", on=date(2026, 8, 5), amount="5.00")
    fixture.spend(category=None, on=date(2026, 8, 6), amount="905.00")

    fixture.spend(category="Food", on=date(2026, 9, 5), amount="600.00")
    for day in range(10, 20):
        fixture.spend(category=None, on=date(2026, 9, day), amount="2.00")

    fixture.spend(category="Food", on=date(2026, 10, 5), amount="450.00")

    summary = fixture.summary()

    assert summary["baseline_status"] == "ok"
    assert summary["baseline_months_count"] == 2
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

    August and September both hold 300 of Food, so the baseline is 300. October holds
    900. Were the month on screen folded into its own window the baseline would be
    500, and a month three times the usual would report itself as merely above.
    """
    db = make_session()
    fixture = Fixture(db)
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
    100 on the 5th, not the 900 on the 30th. With September's 100 the baseline is
    100. Comparing against whole months instead would make it 550, and a month
    spending exactly its usual would read as far below.

    This is the defect Phase 8 fixed in the budget pacing, where a comparison with no
    time term flipped an on-plan month to a warning around day 26. Summing past
    months to the same cutoff makes no assumption about pacing, which is why it was
    preferred to pro-rating a whole-month baseline: a Fixed Budget is charged as a
    step, so pro-rating would read rent paid on the 1st as a month-long overrun.
    """
    db = make_session()
    fixture = Fixture(db)
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
    contribute 300 and the baseline would be 250 rather than 200.
    """
    db = make_session()
    fixture = Fixture(db)
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
    it had reached by its 26th. Applying the cutoff here would make the baseline 550
    and understate every finished month the owner pages back to.
    """
    db = make_session()
    fixture = Fixture(db)
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

    Food is 300 in each of August and September, so the baseline is 300. The 900
    reimbursement the owner excluded in August would make it 750 if it counted, and
    the 600 excluded this month would treble the figure on screen. GLOSSARY.md
    defines Ignored as excluded from every metric, and a baseline is a metric.
    """
    db = make_session()
    fixture = Fixture(db)
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

    Four months of Food: 900 in July, then 300 in each of August and September. A
    three-month window reaches all three and averages 500; a two-month window reaches
    only August and September and averages 300.

    The window is a parameter over source data rather than anything stored, which is
    what keeps the *shape* cheap to change later: moving to a widening window or to
    exponential decay is a change in one domain function, with no accumulated history
    to convert and no migration. That was the point of refusing a stored accumulator.
    """
    db = make_session()
    fixture = Fixture(db)
    fixture.spend(category="Food", on=date(2026, 7, 5), amount="900.00")
    fixture.spend(category="Food", on=date(2026, 8, 5), amount="300.00")
    fixture.spend(category="Food", on=date(2026, 9, 5), amount="300.00")
    fixture.spend(category="Food", on=date(2026, 10, 5), amount="300.00")

    over_three = SummaryService(db=db, baseline_window_months=3).get_summary(
        month="2026-10", today=TODAY
    )
    over_two = SummaryService(db=db, baseline_window_months=2).get_summary(
        month="2026-10", today=TODAY
    )

    assert over_three["baseline_months_count"] == 3
    assert row_for(over_three, "Food")["baseline_amount"] == "500.00"
    assert over_two["baseline_months_count"] == 2
    assert row_for(over_two, "Food")["baseline_amount"] == "300.00"


def test_the_window_setting_reaches_the_service_through_the_dependency() -> None:
    """A setting nothing reads is the same as no setting.

    Neither test above would notice the wiring being absent, because both construct
    the service directly. This one goes through the dependency the route actually
    uses, and asserts the behaviour rather than the attribute: with the window set to
    two months, July's 900 is out of reach and the baseline is 300 rather than 500.
    """
    from burnrate.api.dependencies import get_summary_service
    from burnrate.config import Settings

    db = make_session()
    fixture = Fixture(db)
    fixture.spend(category="Food", on=date(2026, 7, 5), amount="900.00")
    fixture.spend(category="Food", on=date(2026, 8, 5), amount="300.00")
    fixture.spend(category="Food", on=date(2026, 9, 5), amount="300.00")
    fixture.spend(category="Food", on=date(2026, 10, 5), amount="300.00")

    settings = Settings(BANK_TOKEN_ENCRYPTION_KEY="x" * 44, BASELINE_WINDOW_MONTHS=2)
    assert Settings(BANK_TOKEN_ENCRYPTION_KEY="x" * 44).baseline_window_months == 3

    service = get_summary_service(db=db, settings=settings)
    summary = service.get_summary(month="2026-10", today=TODAY)

    assert summary["baseline_months_count"] == 2
    assert row_for(summary, "Food")["baseline_amount"] == "300.00"


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

    All three months behind the one on screen are fully classified -- every row they
    hold is filed, so coverage by amount reads 0% unfiled for each. August is
    nevertheless missing transactions, because syncs stopped on the 2nd and did not
    resume until the 20th of September, so the 3rd of August to the 20th was never
    asked about.

    Food is 600 in July, 100 in the gap-ridden August and 300 in September. Excluding
    August gives a baseline of 450; admitting it on its classification alone gives
    333.33, understated by a month whose figures were never complete. An understated
    baseline is the one that makes ordinary spend look like an anomaly.
    """
    db = make_session()
    fixture = Fixture(db, synced=False)
    # Covers July in full: the window reaching back from 2 August spans it.
    fixture.sync_daily(date(2026, 7, 1), date(2026, 8, 2))
    # Then nothing until late September. [Jul 21, Aug 2] and [Aug 21, Sep 20] leave
    # the 3rd to the 20th of August unasked, while September is covered from here on.
    fixture.sync_daily(date(2026, 9, 20), date(2026, 10, 26))

    fixture.spend(category="Food", on=date(2026, 7, 5), amount="600.00")
    fixture.spend(category="Food", on=date(2026, 8, 5), amount="100.00")
    fixture.spend(category="Food", on=date(2026, 9, 5), amount="300.00")
    fixture.spend(category="Food", on=date(2026, 10, 5), amount="450.00")

    summary = fixture.summary()

    assert summary["baseline_months_count"] == 2
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
    fixture.sync_daily(date(2026, 7, 1), date(2026, 8, 2))
    fixture.sync_daily(date(2026, 8, 3), date(2026, 9, 19), status="skipped")
    fixture.sync_daily(date(2026, 9, 20), date(2026, 10, 26))

    fixture.spend(category="Food", on=date(2026, 7, 5), amount="600.00")
    fixture.spend(category="Food", on=date(2026, 8, 5), amount="100.00")
    fixture.spend(category="Food", on=date(2026, 9, 5), amount="300.00")
    fixture.spend(category="Food", on=date(2026, 10, 5), amount="450.00")

    summary = fixture.summary()

    assert summary["baseline_months_count"] == 2
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
