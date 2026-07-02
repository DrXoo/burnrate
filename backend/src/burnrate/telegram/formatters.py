from __future__ import annotations

from decimal import Decimal
from typing import Any

HELP_TEXT = "\n".join(
    [
        "BurnRate bot — read-only spending visibility.",
        "",
        "/summary [YYYY-MM] — money left, spending, burn rate, and runway",
        "/budgets [YYYY-MM] — budget status per category",
        "/unknown — transactions still waiting to be categorized",
        "/help — show this message",
        "",
        "Month is optional and defaults to the current month.",
    ]
)

UNKNOWN_COMMAND_TEXT = "Unknown command. Send /help to see what I can do."

_BUDGET_STATUS_ICONS = {"over": "🔴", "watch": "🟡", "on_track": "🟢"}


def _money(amount: str, currency: str | None) -> str:
    suffix = f" {currency}" if currency else ""
    return f"{amount}{suffix}"


def format_summary(payload: dict[str, Any]) -> str:
    currency = payload["current_balance_currency"]
    lines = [
        f"📊 Summary for {payload['month']}",
        "",
        f"Balance: {_money(payload['current_balance_amount'], currency)}",
        f"Spent this month: {_money(payload['monthly_spending_amount'], currency)}",
    ]

    if Decimal(payload["monthly_budget_amount"]) > 0:
        lines.append(f"Budget: {_money(payload['monthly_budget_amount'], currency)}")
        lines.append(f"Money left: {_money(payload['money_left_amount'], currency)}")

    lines.append(
        f"Avg/day: {_money(payload['average_daily_spend_amount'], currency)} "
        f"({payload['days_elapsed']}/{payload['days_in_month']} days)"
    )
    lines.append(f"Projected month-end: {_money(payload['projected_month_end_spend_amount'], currency)}")
    lines.append("")
    lines.append(_runway_line(payload))
    return "\n".join(lines)


def _runway_line(payload: dict[str, Any]) -> str:
    status = payload["runway_status"]
    if status == "not_available":
        return "Runway: not tracked (select reserve accounts in the web app)"

    months_left = payload["runway_months_left"]
    if months_left is None:
        return "Runway: stable (spending within budget)"

    currency = payload["runway_balance_currency"]
    return (
        f"Runway: {months_left} months "
        f"({_money(payload['runway_balance_amount'], currency)} reserve, status: {status})"
    )


def format_budgets(payload: dict[str, Any]) -> str:
    budget_usage = payload["budget_usage"]
    if not budget_usage:
        return f"No active budgets for {payload['month']}."

    lines = [f"💰 Budget status for {payload['month']}", ""]
    for item in budget_usage:
        icon = _BUDGET_STATUS_ICONS.get(item["status"], "•")
        currency = item["currency"]
        lines.append(
            f"{icon} {item['category_name']}: "
            f"{item['spent_amount']} / {_money(item['budget_amount'], currency)} "
            f"({item['utilization_percent']:g}%) — {_money(item['remaining_amount'], currency)} left"
        )
    return "\n".join(lines)


def format_unknown(result: dict[str, Any]) -> str:
    total = result["total_count"]
    if total == 0:
        return "🎉 No unknown transactions. Everything is categorized."

    transactions = result["transactions"]
    lines = [f"❓ {total} unknown transaction(s):", ""]
    for transaction in transactions:
        booking_date = transaction["booking_date"] or "—"
        description = (
            transaction["merchant_name"]
            or transaction["counterparty_name"]
            or transaction["description"]
            or "(no description)"
        )
        lines.append(
            f"• {booking_date}  {_money(transaction['amount'], transaction['currency'])}  {description}"
        )

    remaining = total - len(transactions)
    if remaining > 0:
        lines.append("")
        lines.append(f"…and {remaining} more. Categorize them in the web app.")
    return "\n".join(lines)
