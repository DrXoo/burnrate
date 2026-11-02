from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from burnrate.domain.sync_coverage import SyncGap

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


_TENSE_SUFFIXES = {
    "month_closed": " · month closed",
    "month_not_started": " · not started yet",
}
"""The month's tense, in the words the dashboard's badge uses.

Taken from the status rather than from a clock of the bot's own, which is why the status
names the tense at all -- see ``docs/adr/0002-safe-to-spend-today-definition.md``. The
wording matches the page deliberately: an owner who reads both should not have to
reconcile two vocabularies for the same payload.
"""


_COMPARISON_PHRASES = {
    "no_baseline": "no baseline yet",
    "in_line": "in line with usual",
    "below": "{magnitude} below usual",
    "above": "{magnitude} above usual",
    "anomalous": "unusually high · {magnitude} above usual",
}


def _comparison_phrase(comparison: dict[str, Any]) -> str:
    """Words for a band the backend already decided.

    The bot renders; it does not band. A client that re-derives a threshold is how
    an on-plan month came to flip to a warning around day 26, and ticket 17 is where
    this formatter stopped working out a month's tense for itself. The wording
    matches the dashboard's, so an owner who reads both does not have to reconcile
    two vocabularies for one payload.

    The magnitude is rounded to a whole percent: the owner is deciding whether to
    care, not auditing.
    """
    deviation = comparison["deviation_percent"]
    magnitude = "" if deviation is None else f"{abs(round(deviation)):.0f}%"
    return _COMPARISON_PHRASES[comparison["comparison_status"]].format(magnitude=magnitude)


def _comparison_lines(payload: dict[str, Any], currency: str | None) -> list[str]:
    """What the month's spending looks like against what is normal, or nothing.

    Omitted entirely when the backend offers no comparison, rather than stated as
    the dashboard states it. The asymmetry is deliberate: a screen the owner is
    looking at makes an absent line ambiguous, and it reads as "nothing to say about
    your spending"; a chat reply is a list of facts, and a fact that is not known is
    simply not among them.

    Only the comparable half is judged, and the rest is disclosed beside it rather
    than folded in -- the shape Unbudgeted Spend already has above. See
    ``docs/product/metrics.md``.
    """
    if payload.get("baseline_status") != "ok":
        return []
    comparison = payload["comparable_spend_baseline"]
    # Read off the band, never off the amount beside it. A baseline of zero or less
    # is one the backend refuses to divide by, so the band already says
    # ``no_baseline`` while the amount still reads "0.00" -- and keyed on the amount
    # this line published "normally 0.00 EUR · no baseline yet".
    if comparison["comparison_status"] == "no_baseline":
        return []
    baseline = comparison["baseline_amount"]
    months = payload["baseline_months_count"]
    lines = [
        f"   ↳ {_money(payload['comparable_spend_amount'], currency)} comparable"
        f" · normally {_money(baseline, currency)}"
        f" · {_comparison_phrase(comparison)} ({months}-month avg)"
    ]
    uncomparable = payload["uncomparable_spend_amount"]
    if Decimal(uncomparable) != 0:
        lines.append(f"   ↳ {_money(uncomparable, currency)} cannot be compared")
    return lines


def format_sync_gap_alert(*, gap: SyncGap) -> str:
    """The unprompted version of the summary's sync line, sent when the worker returns.

    Two messages, and the difference is whether there is anything to do. When days
    are already lost, **no action is offered**, because none recovers them -- offering
    a reconnection would be a lie, and the owner's real cost is that they have been
    reading understated figures for those months. When the days can still be had, this
    is an ask with a date on it.

    Takes the gap rather than a payload: this one has no request behind it, so there
    is no payload to read it off.
    """
    days = gap.missing_days
    plural = "day" if days == 1 else "days"
    span = (
        str(gap.oldest_missing_day)
        if gap.oldest_missing_day == gap.newest_missing_day
        else f"{gap.oldest_missing_day} to {gap.newest_missing_day}"
    )
    lines = [
        "⚠️ Bank data missing",
        "━━━━━━━━━━━━━━━━━━",
        "",
        f"{days} {plural} were never fetched: {span}.",
    ]
    if gap.unrecoverable_days > 0:
        lines += [
            "",
            "They are gone for good -- the provider only serves the last 30 days.",
            "Every figure reported for those months is understated.",
        ]
    else:
        lines += [
            "",
            f"Still recoverable until {gap.recoverable_until}.",
            "Reconnect the bank before then and they will be fetched.",
        ]
    return "\n".join(lines)


def _sync_gap_lines(payload: dict[str, Any]) -> list[str]:
    """Days the bank was never asked about, worded off the backend's own status.

    Two sentences, because they ask for different things. ``lost`` asks for nothing --
    no action recovers those days -- but the owner has been reading figures for those
    months that were understated, and that is worth knowing even though it is too
    late. ``expiring`` asks for a reconnection, and the date is what makes it an ask
    rather than a complaint.

    The status is read, never derived: the dashboard says the same thing from the same
    field, which is the amendment ``ADR-0002`` records.
    """
    gap = payload.get("sync_gap")
    # ``lost_elsewhere`` is a real loss in some other month, and saying it here would
    # be the furniture this scoping exists to remove. The month it belongs to says it.
    if not gap or gap["status"] == "lost_elsewhere":
        return []
    days = gap["missing_days"]
    plural = "day" if days == 1 else "days"
    head = f"⚠️ {days} {plural} of bank data missing since {gap['oldest_missing_day']}"
    if gap["status"] == "lost":
        return [head, "   ↳ gone for good -- those months are understated", ""]
    return [head, f"   ↳ recoverable until {gap['recoverable_until']} -- reconnect the bank", ""]


def format_summary(payload: dict[str, Any]) -> str:
    currency = payload["current_balance_currency"]
    tense = _TENSE_SUFFIXES.get(payload["safe_to_spend_status"], "")
    lines = [
        f"📊 Summary for {payload['month']}{tense}",
        "━━━━━━━━━━━━━━━━━━",
        "",
        # Above every figure, because it qualifies all of them: the owner read two
        # months of understated totals without anything saying the bank had never
        # been asked about five of their days.
        *_sync_gap_lines(payload),
        _allowance_line(payload, currency),
        "",
        f"💰 Balance: {_money(payload['current_balance_amount'], currency)}",
        "",
        f"💸 Spent: {_money(payload['monthly_spending_amount'], currency)}",
    ]

    if Decimal(payload.get("unbudgeted_spending_amount", "0.00")) != 0:
        lines.append(f"   ↳ incl. {_money(payload['unbudgeted_spending_amount'], currency)} unbudgeted")

    lines.extend(_comparison_lines(payload, currency))

    # Income alone used to gate this block, which went silent on exactly the month it
    # matters most: one whose every inflow was the owner moving their own money in has
    # no income at all, and a deficit with nothing beside it is the thing to report.
    inbound = Decimal(payload.get("inbound_transfer_amount", "0.00"))
    if Decimal(payload.get("monthly_income_amount", "0.00")) > 0 or inbound != 0:
        net_icon = "📈" if Decimal(payload["net_cash_flow_amount"]) >= 0 else "📉"
        lines.append(f"💵 Income: {_money(payload['monthly_income_amount'], currency)}")
        lines.append(f"{net_icon} Net: {_money(payload['net_cash_flow_amount'], currency)}")
        if inbound != 0:
            # Neither income nor spend: it funded the net above rather than forming
            # part of it, so it reads as the net's cause and never as a figure of
            # its own.
            lines.append(
                f"   ↳ {_money(payload['inbound_transfer_amount'], currency)}"
                " moved in from an unsynced account"
            )

    # A month that has not started has no elapsed day, so every figure that describes
    # progress has nothing to describe: the usage bar reads 20% used of a month nobody
    # has lived, the average divides by zero days, and the projection presents a plan as
    # an expected outcome. The budget and what is already committed to it survive,
    # because those are the two things such a month really has -- a standing order
    # carrying a future value date is filed there by its Effective Date.
    reports_progress = payload["safe_to_spend_status"] != "month_not_started"

    if Decimal(payload["monthly_budget_amount"]) > 0:
        lines.append("")
        lines.append(f"🎯 Budget: {_money(payload['monthly_budget_amount'], currency)}")
        lines.append(f"✅ Budget left: {_money(payload['money_left_amount'], currency)}")
        if reports_progress:
            lines.append(f"   {_budget_bar(payload)}")

    if not reports_progress:
        return "\n".join(lines)

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
