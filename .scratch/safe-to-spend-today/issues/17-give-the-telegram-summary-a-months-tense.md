# 17: Give the Telegram summary a month's tense

**What to build:** `/summary <a future month>` prints a live-month reading of a month
that has not started. Found by `/code-review` on ticket 11.

**Blocked by:** None

**Status:** recorded — a known defect, not scheduled

- [ ] A month that is not the current one is named as such in the first lines of the output, not only in the allowance line
- [ ] A month that has not started does not report a used-budget bar, a daily pace over zero days, or a projection as if it were in progress
- [ ] The bot and the dashboard describe the same payload's month the same way
- [x] The tense comes from the payload, not from a clock of the bot's own — done by ticket 16, which put it in `safe_to_spend_status` as `month_closed` / `month_not_started`
- [ ] Seam 4 carries the renderings

## The defect

`/summary 2026-07` on 15 June, with an 80.00 standing order due in July, prints an
honest allowance line and then six dishonest ones:

```
⚪ Safe to spend today: only for the current month
...
🎯 Budget: 400.00 EUR
✅ Budget left: 320.00 EUR
   [██░░░░░░░░] 20% used
⏱ Avg/day: 0.00 EUR (0/31 days) · plan 12.90 EUR/day
🔮 Projected: 400.00 EUR
```

A used-budget bar, a daily pace over zero elapsed days and a month-end projection, all
for a month that has not begun. After ticket 11 the dashboard captions the identical
payload "July 2026 · planned / Not started yet", so the two interfaces now describe the
same month differently — and the projection figure itself is wrong for a second,
separate reason, which is ticket 15.

## Why this is recorded rather than scheduled

The gap is ticket 08's, not ticket 11's: the formatter never had a tense. The bot is
the secondary interface by `AGENTS.md`, the allowance line — the one the ticket made
the headline — is already honest, and the owner can only land on a non-current month by
typing it, since `/summary` with no argument defaults to the current one. So it is
real, it is visible, and nothing routes the owner into it by accident.

`format_summary` already receives everything it needs: the payload carries
`current_month` as of ticket 11.

## What ticket 16 left here

Ticket 16 took the enum split that both this file and 16 had recorded as the
alternative, so the formatter no longer has a "where does tense come from" question in
front of it. `safe_to_spend_status` is `month_closed` or `month_not_started`, the
allowance line already branches on both — rendered alike on purpose — and the fourth
criterion above is met.

What is left is the rendering, which is the whole of the defect above: the used-budget
bar, the pace over zero elapsed days and the projection are still printed for a month
that has not begun. The projection figure itself was ticket 15's and is now correct, so
the remaining work is suppressing or re-wording three lines at seam 4, not deciding
anything.

## Testing

Seam 4, the Telegram summary formatter — pure dict in, string out, with
`test_telegram_formatters.py` as prior art. The three renderings are a month that has
closed, a month that has not started, and the current month unchanged.
