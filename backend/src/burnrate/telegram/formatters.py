from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

HELP_TEXT = "\n".join(
    [
        "BurnRate bot — read-only spending visibility.",
        "",
        "/summary [YYYY-MM] — money left, spending, burn rate, and runway",
        "/budgets [YYYY-MM] — budget status per category",
        "/unknown [YYYY-MM] — transactions still waiting to be categorized (this month)",
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
        "━━━━━━━━━━━━━━━━━━",
        "",
        f"💰 Balance: {_money(payload['current_balance_amount'], currency)}",
        "",
        f"💸 Spent: {_money(payload['monthly_spending_amount'], currency)}",
    ]

    if Decimal(payload.get("unbudgeted_spending_amount", "0.00")) != 0:
        lines.append(f"   ↳ incl. {_money(payload['unbudgeted_spending_amount'], currency)} unbudgeted")

    if Decimal(payload.get("monthly_income_amount", "0.00")) > 0:
        net_icon = "📈" if Decimal(payload["net_cash_flow_amount"]) >= 0 else "📉"
        lines.append(f"💵 Income: {_money(payload['monthly_income_amount'], currency)}")
        lines.append(f"{net_icon} Net: {_money(payload['net_cash_flow_amount'], currency)}")

    if Decimal(payload["monthly_budget_amount"]) > 0:
        lines.append("")
        lines.append(f"🎯 Budget: {_money(payload['monthly_budget_amount'], currency)}")
        lines.append(f"✅ Left: {_money(payload['money_left_amount'], currency)}")
        lines.append(f"   {_budget_bar(payload)}")

    lines.append("")
    # Burn rate is the variable daily pace (fixed lump payments excluded). When a
    # planned pace is available, show it alongside so over/under-pace is obvious.
    avg_line = (
        f"⏱ Avg/day: {_money(payload['average_daily_spend_amount'], currency)} "
        f"({payload['days_elapsed']}/{payload['days_in_month']} days)"
    )
    expected_daily = payload.get("expected_daily_spend_amount")
    if expected_daily is not None and Decimal(expected_daily) > 0:
        avg_line += f" · plan {_money(expected_daily, currency)}/day"
    lines.append(avg_line)
    lines.append(f"🔮 Projected: {_money(payload['projected_month_end_spend_amount'], currency)}")
    lines.append("")
    lines.append(_runway_line(payload))
    return "\n".join(lines)


def _budget_bar(payload: dict[str, Any], *, segments: int = 10) -> str:
    budget = Decimal(payload["monthly_budget_amount"])
    money_left = Decimal(payload["money_left_amount"])
    used_pct = ((budget - money_left) / budget * 100) if budget > 0 else Decimal("0")
    ratio = max(Decimal("0"), used_pct) / Decimal("100")
    filled = min(segments, int((ratio * segments).to_integral_value(rounding=ROUND_HALF_UP)))
    bar = "█" * filled + "░" * (segments - filled)
    return f"[{bar}] {used_pct:.0f}% used"


def _runway_line(payload: dict[str, Any]) -> str:
    status = payload["runway_status"]
    if status == "not_available":
        return "🛟 Runway: not tracked\n   (select reserve accounts in the web app)"

    months_left = payload["runway_months_left"]
    if months_left is None:
        return "🛟 Runway: stable\n   (spending within budget)"

    currency = payload["runway_balance_currency"]
    return (
        f"🛟 Runway: {months_left} months\n"
        f"   {_money(payload['runway_balance_amount'], currency)} reserve · {status}"
    )


def format_budgets(payload: dict[str, Any]) -> str:
    budget_usage = payload["budget_usage"]
    if not budget_usage:
        return f"No active budgets for {payload['month']}."

    lines = [f"💰 Budget status for {payload['month']}", ""]
    for item in budget_usage:
        currency = item["currency"]
        is_fixed = item.get("is_fixed", False)
        label = f"{item['category_name']} (fixed)" if is_fixed else item["category_name"]
        # A fixed lump payment that hasn't been charged yet isn't "on track" — it's
        # pending. Show its estimate instead of a green 0%-used line.
        if is_fixed and Decimal(item["spent_amount"]) <= 0:
            lines.append(f"⚪ {label}: not yet paid · {_money(item['budget_amount'], currency)} est.")
            continue
        icon = _BUDGET_STATUS_ICONS.get(item["status"], "•")
        lines.append(
            f"{icon} {label}: "
            f"{item['spent_amount']} / {_money(item['budget_amount'], currency)} "
            f"({item['utilization_percent']:g}%) — {_money(item['remaining_amount'], currency)} left"
        )
    return "\n".join(lines)


def format_sync_notification(*, new_count: int, uncategorized_count: int) -> str:
    plural = "s" if new_count != 1 else ""
    lines = [f"🔔 {new_count} new transaction{plural} imported."]
    if uncategorized_count > 0:
        verb = "needs" if uncategorized_count == 1 else "need"
        lines.append(f"{uncategorized_count} still {verb} a category — send /unknown.")
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
