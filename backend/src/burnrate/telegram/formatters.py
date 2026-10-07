from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

HELP_TEXT = "\n".join(
    [
        "BurnRate bot — read-only spending visibility.",
        "",
        "/summary [YYYY-MM] — what you can spend today, plus the month so far",
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


def _allowance_line(payload: dict[str, Any], currency: str | None) -> str:
    """The headline: what the owner may spend today, read off the backend's status.

    The icon is the same status vocabulary the budget rows use, so a colour means
    the same thing everywhere the bot prints one.
    """
    status = payload["safe_to_spend_status"]
    if status == "no_budget":
        # No zero here: "0.00" would claim the owner may spend nothing, which is a
        # different and untrue thing to say. Tell them what to do instead.
        return "⚪ Safe to spend today: set a monthly budget to get a daily number"
    if status in {"month_closed", "month_not_started"}:
        # "Today" is not in the month being asked about. The budget-left line below
        # already reports how that month stands, so this line only says why the
        # allowance is absent.
        #
        # The two tenses are deliberately rendered alike *here* and are available to be
        # told apart: the lines under this one still describe a month that has not begun
        # as if it were in progress -- a used-budget bar, a pace over zero elapsed days,
        # a projection. Fixing that is ticket 17, and it now reads this status rather
        # than deriving the tense from a clock of the bot's own.
        return "⚪ Safe to spend today: only for the current month"
    icon = _BUDGET_STATUS_ICONS[status]
    return f"{icon} Safe to spend today: {_money(payload['safe_to_spend_today_amount'], currency)}"


def format_summary(payload: dict[str, Any]) -> str:
    currency = payload["current_balance_currency"]
    lines = [
        f"📊 Summary for {payload['month']}",
        "━━━━━━━━━━━━━━━━━━",
        "",
        _allowance_line(payload, currency),
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
        lines.append(f"✅ Budget left: {_money(payload['money_left_amount'], currency)}")
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
    return "\n".join(lines)


def _budget_bar(payload: dict[str, Any], *, segments: int = 10) -> str:
    budget = Decimal(payload["monthly_budget_amount"])
    money_left = Decimal(payload["money_left_amount"])
    used_pct = ((budget - money_left) / budget * 100) if budget > 0 else Decimal("0")
    ratio = max(Decimal("0"), used_pct) / Decimal("100")
    filled = min(segments, int((ratio * segments).to_integral_value(rounding=ROUND_HALF_UP)))
    bar = "█" * filled + "░" * (segments - filled)
    return f"[{bar}] {used_pct:.0f}% used"


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


def format_expiry_alert(items: list[dict[str, Any]]) -> str:
    """Warn that one or more bank connections are lapsing (or have lapsed).

    ``items`` are dicts with ``aspsp_name``, ``expired`` (bool) and ``days`` (int).
    """
    lines = ["⚠️ Bank connection needs attention:", ""]
    for item in items:
        name = item["aspsp_name"]
        if item["expired"]:
            lines.append(f"• {name} — access expired, syncing has stopped")
        else:
            days = item["days"]
            when = "today" if days <= 0 else (f"in {days} day" + ("" if days == 1 else "s"))
            lines.append(f"• {name} — access expires {when}")
    lines.append("")
    lines.append("Reconnect the account in the app to keep your data fresh.")
    return "\n".join(lines)


def format_reconnect_alert(names: list[str]) -> str:
    """Tell the user a bank connection stopped and must be re-authorized in the app.

    ``names`` are the affected banks' display names. Sent as soon as a sync detects
    a closed session or a rejected (401) account request, so the user can reconnect
    without waiting to notice missing transactions.
    """
    if len(names) == 1:
        headline = f"🔒 {names[0]} disconnected — action needed:"
    else:
        headline = "🔒 Bank connections disconnected — action needed:"
    lines = [headline, ""]
    for name in names:
        lines.append(f"• {name} — your bank ended the session, syncing has stopped")
    lines.append("")
    lines.append("Open BurnRate settings and reconnect the account to resume syncing.")
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
