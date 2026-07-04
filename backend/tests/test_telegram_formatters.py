from __future__ import annotations

from typing import Any

from burnrate.telegram.formatters import (
    format_budgets,
    format_summary,
    format_unknown,
)


def make_summary(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "month": "2026-06",
        "current_balance_amount": "500.00",
        "current_balance_currency": "EUR",
        "runway_balance_amount": "1500.00",
        "runway_balance_currency": "EUR",
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
        "runway_months_left": "12.50",
        "runway_status": "stable",
        "budget_usage": [],
    }
    payload.update(overrides)
    return payload


def test_format_summary_includes_core_metrics_and_budget() -> None:
    text = format_summary(make_summary())

    assert "Summary for 2026-06" in text
    assert "Balance: 500.00 EUR" in text
    assert "Spent: 120.00 EUR" in text
    assert "Budget: 200.00 EUR" in text
    assert "Left: 80.00 EUR" in text
    assert "60% used" in text
    assert "Avg/day: 4.00 EUR (30/30 days)" in text
    assert "Runway: 12.50 months" in text


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


def test_format_summary_reports_untracked_runway() -> None:
    text = format_summary(
        make_summary(runway_status="not_available", runway_months_left=None)
    )

    assert "Runway: not tracked" in text


def test_format_summary_reports_stable_runway_without_months() -> None:
    text = format_summary(make_summary(runway_status="stable", runway_months_left=None))

    assert "Runway: stable" in text


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


def test_format_unknown_handles_empty_queue() -> None:
    text = format_unknown({"total_count": 0, "transactions": []})

    assert "No unknown transactions" in text
