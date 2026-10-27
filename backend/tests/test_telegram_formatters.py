from __future__ import annotations

from typing import Any

import pytest

from burnrate.telegram.formatters import (
    HELP_TEXT,
    format_budgets,
    format_expiry_alert,
    format_reconnect_alert,
    format_summary,
    format_sync_notification,
    format_unknown,
)


def make_summary(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "month": "2026-06",
        "safe_to_spend_today_amount": "80.00",
        "safe_to_spend_status": "on_track",
        "current_balance_amount": "500.00",
        "current_balance_currency": "EUR",
        "monthly_spending_amount": "120.00",
        "monthly_income_amount": "0.00",
        "net_cash_flow_amount": "-120.00",
        "unbudgeted_spending_amount": "0.00",
        "monthly_budget_amount": "200.00",
        "money_left_amount": "80.00",
        "average_daily_spend_amount": "4.00",
        "projected_month_end_spend_amount": "120.00",
        "days_elapsed": 30,
        "days_in_month": 30,
        "budget_usage": [],
        # No comparison by default, so every test above keeps its meaning: each of
        # them is about a figure rather than about what is normal for the owner.
        "baseline_status": "insufficient_history",
        "baseline_months_count": 0,
        "comparable_spend_amount": "0.00",
        "uncomparable_spend_amount": "0.00",
        "comparable_spend_baseline": {
            "baseline_amount": None,
            "deviation_percent": None,
            "comparison_status": "no_baseline",
        },
    }
    payload.update(overrides)
    return payload


def first_money_line(text: str) -> str:
    """The first line of the summary carrying a figure, whatever header precedes it."""
    return next(line for line in text.splitlines() if "EUR" in line)


def allowance_line(text: str) -> str:
    return next(line for line in text.splitlines() if "Safe to spend today" in line)


def test_format_summary_opens_with_the_allowance() -> None:
    text = format_summary(
        make_summary(safe_to_spend_today_amount="7.19", safe_to_spend_status="on_track")
    )

    assert first_money_line(text) == "🟢 Safe to spend today: 7.19 EUR"


def test_format_summary_prompts_for_a_budget_when_there_is_no_allowance() -> None:
    text = format_summary(
        make_summary(
            safe_to_spend_today_amount=None,
            safe_to_spend_status="no_budget",
            monthly_budget_amount="0.00",
        )
    )

    assert allowance_line(text) == "⚪ Safe to spend today: set a monthly budget to get a daily number"
    assert "None" not in text
    assert "0.00" not in allowance_line(text)


@pytest.mark.parametrize(
    ("month", "status"),
    [("2026-05", "month_closed"), ("2026-07", "month_not_started")],
)
def test_format_summary_marks_the_allowance_undefined_outside_the_current_month(
    month: str,
    status: str,
) -> None:
    # Both tenses say the same thing here: the header carries which one it is, and this
    # line only says why there is no number. The month and the status are paired
    # coherently -- May cannot be the month that has not started yet.
    text = format_summary(
        make_summary(
            month=month,
            safe_to_spend_today_amount=None,
            safe_to_spend_status=status,
        )
    )

    assert allowance_line(text) == "⚪ Safe to spend today: only for the current month"
    assert "None" not in text
    assert "Budget left: 80.00 EUR" in text


def test_format_summary_colours_the_allowance_by_its_status() -> None:
    def line(status: str) -> str:
        return allowance_line(
            format_summary(
                make_summary(safe_to_spend_today_amount="12.00", safe_to_spend_status=status)
            )
        )

    assert line("on_track") == "🟢 Safe to spend today: 12.00 EUR"
    assert line("watch") == "🟡 Safe to spend today: 12.00 EUR"
    assert line("over") == "🔴 Safe to spend today: 12.00 EUR"


def test_help_text_describes_what_the_summary_leads_with() -> None:
    summary_line = next(line for line in HELP_TEXT.splitlines() if line.startswith("/summary"))

    assert summary_line == "/summary [YYYY-MM] — what you can spend today, plus the month so far"


def test_format_summary_includes_core_metrics_and_budget() -> None:
    text = format_summary(make_summary())

    assert "Summary for 2026-06" in text
    assert "Balance: 500.00 EUR" in text
    assert "Spent: 120.00 EUR" in text
    assert "Budget: 200.00 EUR" in text
    assert "Budget left: 80.00 EUR" in text
    assert "60% used" in text
    assert "Avg/day: 4.00 EUR (30/30 days)" in text


def test_format_summary_includes_income_net_and_unbudgeted_when_present() -> None:
    text = format_summary(
        make_summary(
            monthly_income_amount="2000.00",
            net_cash_flow_amount="1880.00",
            unbudgeted_spending_amount="15.00",
        )
    )

    assert "Income: 2000.00 EUR" in text
    assert "Net: 1880.00 EUR" in text
    assert "unbudgeted" in text
    assert "Projected: 120.00 EUR" in text


def test_format_summary_hides_income_line_without_income() -> None:
    text = format_summary(make_summary())

    assert "Income:" not in text
    assert "unbudgeted" not in text


def test_format_summary_hides_budget_lines_when_no_budget() -> None:
    text = format_summary(make_summary(monthly_budget_amount="0.00"))

    assert "Budget:" not in text
    assert "Money left:" not in text


def test_format_budgets_lists_categories_with_status_icons() -> None:
    payload = make_summary(
        budget_usage=[
            {
                "category_name": "Food",
                "spent_amount": "220.00",
                "budget_amount": "200.00",
                "remaining_amount": "-20.00",
                "currency": "EUR",
                "utilization_percent": 110.0,
                "status": "over",
            }
        ]
    )

    text = format_budgets(payload)

    assert "Budget status for 2026-06" in text
    assert "🔴 Food: 220.00 / 200.00 EUR (110%)" in text
    assert "-20.00 EUR left" in text


def test_format_summary_shows_planned_daily_pace_when_available() -> None:
    text = format_summary(make_summary(expected_daily_spend_amount="10.00"))

    assert "Avg/day: 4.00 EUR (30/30 days) · plan 10.00 EUR/day" in text


def test_format_summary_omits_planned_pace_without_variable_budget() -> None:
    text = format_summary(make_summary(expected_daily_spend_amount="0.00"))

    assert "plan" not in text


def test_format_budgets_marks_fixed_pending_as_estimate() -> None:
    payload = make_summary(
        budget_usage=[
            {
                "category_name": "Rent",
                "spent_amount": "0.00",
                "budget_amount": "900.00",
                "remaining_amount": "900.00",
                "currency": "EUR",
                "utilization_percent": 0.0,
                "status": "on_track",
                "is_fixed": True,
            }
        ]
    )

    text = format_budgets(payload)

    assert "⚪ Rent (fixed): not yet paid · 900.00 EUR est." in text
    assert "0% used" not in text


def test_format_budgets_marks_fixed_paid_with_tag() -> None:
    payload = make_summary(
        budget_usage=[
            {
                "category_name": "Utilities",
                "spent_amount": "120.00",
                "budget_amount": "100.00",
                "remaining_amount": "-20.00",
                "currency": "EUR",
                "utilization_percent": 120.0,
                "status": "over",
                "is_fixed": True,
            }
        ]
    )

    text = format_budgets(payload)

    assert "🔴 Utilities (fixed): 120.00 / 100.00 EUR (120%)" in text


def test_format_budgets_handles_no_budgets() -> None:
    assert format_budgets(make_summary(budget_usage=[])) == "No active budgets for 2026-06."


def test_format_unknown_lists_transactions() -> None:
    result = {
        "total_count": 3,
        "transactions": [
            {
                "booking_date": "2026-06-10",
                "amount": "-30.00",
                "currency": "EUR",
                "merchant_name": "Coffee Shop",
                "counterparty_name": None,
                "description": "card payment",
            },
            {
                "booking_date": "2026-06-11",
                "amount": "-12.00",
                "currency": "EUR",
                "merchant_name": None,
                "counterparty_name": None,
                "description": None,
            },
        ],
    }

    text = format_unknown(result)

    assert "3 unknown transaction(s)" in text
    assert "2026-06-10  -30.00 EUR  Coffee Shop" in text
    assert "(no description)" in text
    assert "and 1 more" in text


def test_format_sync_notification_includes_uncategorized_nudge() -> None:
    text = format_sync_notification(new_count=3, uncategorized_count=2)

    assert "🔔 3 new transactions imported." in text
    assert "2 still need a category — send /unknown." in text


def test_format_sync_notification_singular_and_no_nudge() -> None:
    text = format_sync_notification(new_count=1, uncategorized_count=0)

    assert "🔔 1 new transaction imported." in text
    assert "/unknown" not in text


def test_format_sync_notification_singular_uncategorized() -> None:
    text = format_sync_notification(new_count=2, uncategorized_count=1)

    assert "1 still needs a category — send /unknown." in text


def test_format_expiry_alert_covers_soon_and_expired() -> None:
    text = format_expiry_alert(
        [
            {"aspsp_name": "ING", "expired": False, "days": 3},
            {"aspsp_name": "BBVA", "expired": True, "days": -1},
        ]
    )

    assert "ING — access expires in 3 days" in text
    assert "BBVA — access expired" in text
    assert "Reconnect the account" in text


def test_format_expiry_alert_singular_day() -> None:
    text = format_expiry_alert([{"aspsp_name": "ING", "expired": False, "days": 1}])

    assert "expires in 1 day" in text


def test_format_reconnect_alert_single_bank_names_it() -> None:
    text = format_reconnect_alert(["ING"])

    assert "🔒 ING disconnected — action needed:" in text
    assert "ING — your bank ended the session, syncing has stopped" in text
    assert "reconnect the account to resume syncing" in text


def test_format_reconnect_alert_multiple_banks_generic_headline() -> None:
    text = format_reconnect_alert(["ING", "BBVA"])

    assert "🔒 Bank connections disconnected — action needed:" in text
    assert "ING — your bank ended the session" in text
    assert "BBVA — your bank ended the session" in text


def test_format_unknown_handles_empty_queue() -> None:
    text = format_unknown({"total_count": 0, "transactions": []})

    assert "No unknown transactions" in text


def header(text: str) -> str:
    return text.splitlines()[0]


# The month's tense, named in the first line, in the same words the dashboard's badge
# uses -- "Month closed" and "Not started yet". The bot and the page describe the same
# payload, so an owner who reads both should not have to reconcile two vocabularies.
#
# status, the header it earns, what the owner typed
TENSE_HEADER_EXAMPLES = [
    ("month_closed", "📊 Summary for 2026-05 · month closed", "/summary 2026-05 in June"),
    ("month_not_started", "📊 Summary for 2026-07 · not started yet", "/summary 2026-07 in June"),
]


@pytest.mark.parametrize(
    ("status", "expected_header", "_what_the_owner_typed"),
    TENSE_HEADER_EXAMPLES,
)
def test_format_summary_names_the_months_tense_in_its_first_line(
    status: str,
    expected_header: str,
    _what_the_owner_typed: str,
) -> None:
    month = "2026-05" if status == "month_closed" else "2026-07"
    text = format_summary(
        make_summary(
            month=month,
            safe_to_spend_today_amount=None,
            safe_to_spend_status=status,
        )
    )

    assert header(text) == expected_header


def test_format_summary_leaves_the_current_months_header_alone() -> None:
    text = format_summary(make_summary())

    assert header(text) == "📊 Summary for 2026-06"


def future_month_summary() -> dict[str, Any]:
    """July asked for in June: an 80.00 standing order due, against a 400.00 budget.

    Nothing has elapsed, so the figures that describe progress have nothing to describe.
    What the month does have is a plan and the spend already committed to it.
    """
    return make_summary(
        month="2026-07",
        safe_to_spend_today_amount=None,
        safe_to_spend_status="month_not_started",
        monthly_spending_amount="80.00",
        monthly_budget_amount="400.00",
        money_left_amount="320.00",
        average_daily_spend_amount="0.00",
        expected_daily_spend_amount="12.90",
        projected_month_end_spend_amount="400.00",
        days_elapsed=0,
        days_in_month=31,
    )


def test_format_summary_does_not_report_progress_for_a_month_that_has_not_started() -> None:
    """A month with no elapsed days has no pace, no usage and no outcome to project.

    It printed all three: a used-budget bar, an average over 0/31 days with a planned
    pace beside it, and a month-end projection -- while the dashboard captioned the
    identical payload "Not started yet". The plan and what is already committed to it
    stay, because those are the two things the month really has.
    """
    text = format_summary(future_month_summary())

    assert "% used" not in text
    assert "Avg/day" not in text
    assert "days)" not in text
    assert "Projected" not in text
    # What the month does have.
    assert "🎯 Budget: 400.00 EUR" in text
    assert "✅ Budget left: 320.00 EUR" in text
    assert "💸 Spent: 80.00 EUR" in text


def test_format_summary_still_reports_progress_for_a_month_that_has_closed() -> None:
    """A closed month elapsed in full, so its pace and usage are an outcome.

    Only the not-started case loses them. Asserted so the suppression cannot quietly
    widen to every month the owner is not in.
    """
    text = format_summary(
        make_summary(
            month="2026-05",
            safe_to_spend_today_amount=None,
            safe_to_spend_status="month_closed",
        )
    )

    assert "% used" in text
    assert "⏱ Avg/day: 4.00 EUR (30/30 days)" in text
    assert "🔮 Projected: 120.00 EUR" in text


def with_comparison(**overrides: Any) -> dict[str, Any]:
    """A payload carrying the owner's live October, shaped for the bot.

    295.00 spent where 580.00 is usual, with 8400.00 in a category that has no
    history and so cannot be compared to anything.
    """
    payload = {
        "monthly_spending_amount": "8695.00",
        "baseline_status": "ok",
        "baseline_months_count": 2,
        "comparable_spend_amount": "295.00",
        "uncomparable_spend_amount": "8400.00",
        "comparable_spend_baseline": {
            "baseline_amount": "580.00",
            "deviation_percent": -49.1,
            "comparison_status": "below",
        },
    }
    payload.update(overrides)
    return make_summary(**payload)


def comparison_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if "usual" in line or "compared" in line]


def test_format_summary_reports_spending_against_what_is_normal() -> None:
    """With the months the mean rests on, because two is few enough to disclose.

    The wording follows the dashboard's: an owner who reads both should not have to
    reconcile two vocabularies for the same payload, which is the reason the tense
    suffixes already match.
    """
    text = format_summary(with_comparison())

    assert comparison_lines(text) == [
        "   ↳ 295.00 EUR comparable · normally 580.00 EUR · 49% below usual (2-month avg)",
        "   ↳ 8400.00 EUR cannot be compared",
    ]


def test_format_summary_omits_the_comparison_when_the_baseline_is_zero() -> None:
    """A zero baseline is an absent one, and only the status says so.

    The amount is what every reader reached for first, and it is the wrong field: a
    baseline of zero or less is not divided by, so the band is already
    ``no_baseline`` while the amount beside it reads "0.00". Keyed on the amount,
    this line published "normally 0.00 EUR · no baseline yet" -- a figure and a
    denial of it in one breath. The owner's own case is a salary dated the 28th read
    on the 26th, where every Qualifying Month contributes nothing to the cutoff.
    """
    text = format_summary(
        with_comparison(
            comparable_spend_baseline={
                "baseline_amount": "0.00",
                "deviation_percent": None,
                "comparison_status": "no_baseline",
            },
        )
    )

    assert comparison_lines(text) == []


def test_format_summary_omits_the_comparison_with_too_little_history() -> None:
    """Omitted rather than stated, which is the opposite of what the dashboard does.

    The asymmetry is deliberate. The dashboard is a screen the owner is looking at,
    where an absent line is ambiguous and reads as "nothing to say about your
    spending". A chat reply is a list of facts, and a fact that is not known is
    simply not among them.
    """
    text = format_summary(with_comparison(baseline_status="insufficient_history"))

    assert comparison_lines(text) == []
    # The figures themselves are untouched: what is missing is the commentary.
    assert "💸 Spent: 8695.00 EUR" in text


def test_format_summary_reads_the_verdict_off_the_status_not_off_the_figures() -> None:
    """The payload here is deliberately inconsistent, to prove which source wins.

    295.00 against 580.00 is half, which any band derived here would call well
    below. The status says ``in_line``, and that is what must be printed: the bands
    live in the domain and the bot renders words for them. Phase 8 was where this
    was learned -- a client that re-derived a threshold flipped an on-plan month to
    a warning around day 26, and ticket 17 is where this formatter stopped deriving
    a month's tense of its own.
    """
    text = format_summary(
        with_comparison(
            comparable_spend_baseline={
                "baseline_amount": "580.00",
                "deviation_percent": -49.1,
                "comparison_status": "in_line",
            },
        )
    )

    assert "in line with usual" in text
    assert "below usual" not in text


def test_format_summary_omits_the_uncomparable_line_when_there_is_none() -> None:
    text = format_summary(with_comparison(uncomparable_spend_amount="0.00"))

    assert comparison_lines(text) == [
        "   ↳ 295.00 EUR comparable · normally 580.00 EUR · 49% below usual (2-month avg)",
    ]


def test_format_summary_gives_a_month_that_has_not_started_no_comparison() -> None:
    """And keeps ticket 17's suppression of everything else that describes progress.

    Such a month has no outcome to compare, however much history sits behind it. The
    backend says so in the baseline status, so the bot does not work it out from the
    tense -- but the two must agree, and this pins that they do.
    """
    text = format_summary(
        with_comparison(
            safe_to_spend_status="month_not_started",
            baseline_status="month_not_started",
        )
    )

    assert comparison_lines(text) == []
    assert "Avg/day" not in text
    assert "Projected" not in text
    assert "not started yet" in text


def test_format_summary_marks_an_unusually_high_month() -> None:
    text = format_summary(
        with_comparison(
            comparable_spend_amount="1200.00",
            uncomparable_spend_amount="0.00",
            comparable_spend_baseline={
                "baseline_amount": "580.00",
                "deviation_percent": 106.9,
                "comparison_status": "anomalous",
            },
        )
    )

    assert "unusually high · 107% above usual" in text
