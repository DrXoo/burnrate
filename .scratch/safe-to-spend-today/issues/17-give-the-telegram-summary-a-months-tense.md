# 17: Give the Telegram summary a month's tense

**What to build:** `/summary <a future month>` prints a live-month reading of a month
that has not started. Found by `/code-review` on ticket 11.

**Blocked by:** None

**Status:** done

- [x] A month that is not the current one is named as such in the first lines of the output, not only in the allowance line
- [x] A month that has not started does not report a used-budget bar, a daily pace over zero days, or a projection as if it were in progress
- [x] The bot and the dashboard describe the same payload's month the same way
- [x] The tense comes from the payload, not from a clock of the bot's own — done by ticket 16, which put it in `safe_to_spend_status` as `month_closed` / `month_not_started`
- [x] Seam 4 carries the renderings

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

## Comments

**The tense is one line, taken from the status.** `📊 Summary for 2026-07 · not started
yet` and `· month closed`, using the dashboard's own badge words — `badge: "Month
closed"` and `badge: "Not started yet"` in `DashboardPage.tsx`. That is how the third
criterion is met: not by two descriptions that happen to agree, but by the same words
read off the same field. The current month's header is unchanged and has a test saying so.

**Only the not-started case loses its progress lines.** A month with no elapsed day has
no pace to report, nothing used, and no outcome to project, so the usage bar, the
`Avg/day` line and the `Projected` line are omitted. The budget and the spend already
committed to it stay, because those are the two things such a month really has — a
standing order carrying a future value date is filed there by its Effective Date.

A closed month keeps all three and has its own test saying so. It elapsed in full: its
pace is a real average, its bar is a real outcome, and its projection equals its actual.
The suppression is deliberately not "every month the owner is not in", and the test is
what stops it widening to that later.

**What the three renderings now look like**, which is what the ticket asked seam 4 to
carry:

```
📊 Summary for 2026-07 · not started yet     📊 Summary for 2026-05 · month closed
⚪ Safe to spend today: only for the…        ⚪ Safe to spend today: only for the…
💰 Balance: 500.00 EUR                       💰 Balance: 500.00 EUR
💸 Spent: 80.00 EUR                          💸 Spent: 120.00 EUR
🎯 Budget: 400.00 EUR                        🎯 Budget: 200.00 EUR
✅ Budget left: 320.00 EUR                   ✅ Budget left: 80.00 EUR
                                                [██████░░░░] 60% used
                                             ⏱ Avg/day: 4.00 EUR (30/30 days)
                                             🔮 Projected: 120.00 EUR
```

**One fixture was incoherent and is fixed.** Ticket 16's mechanical rename left
`test_format_summary_marks_the_allowance_undefined_outside_the_current_month` asserting
on May 2026 paired with `month_not_started` — a payload that cannot exist. It is now
parametrized over both tenses with the month paired correctly, which also pins that the
allowance line reads the same for both: the header carries which tense it is, so this
line only has to say why there is no number.

**`architecture.md` carried a claim the ticket 16 split had already made false** — that
the summary reports `current_month` and "the client compares the two months it is
given". No client compares anything now. Corrected, and the Telegram paragraph gains
what a not-started month reports.
