# Money the owner moves in is a transfer, and the deficit it funds is counted once

A credit that arrives from another of the owner's own accounts is a **transfer**,
not income. It is excluded from income, from Net Cash Flow and from every
baseline built on them, and it is **disclosed beside** the net it funded as an
Inbound Transfer. The deficit is counted once, in the net; the draw is reported
as its funding, never added to it.

This is worth recording because the obvious reading is wrong in two opposite
directions and the owner reached for both of them.

## It is not income

The category carrying these credits was typed `income`, and the product's rule
was already right: `Category.type == "income"` is what both income queries select
on, so a transfer category reaches neither side of the net. Only the datum was
wrong — fixed by `0009_from_savings_is_a_transfer`.

The cost of getting it wrong, measured on the live database rather than reasoned
about:

| Month | Reported income | Of that, a savings draw | Reported net | Real net |
|---|---|---|---|---|
| 2026-07 | 2,424.75 | 2,000.00 | — | — |
| 2026-08 | 2,980.20 | 2,000.00 | — | — |
| 2026-09 | 2,180.20 | 1,200.00 | — | — |
| **2026-10** | **8,896.20** | **7,841.00** | **−354.88** | **−8,195.88** |

October's −354.88 was not wrong by a rounding. **It was measuring how much the
current account drained and calling it what the owner kept** — the balance sat at
164.51 — while 7,841.00 left a savings account BurnRate cannot see. The two
figures reconcile exactly: 7,841.00 from savings plus 354.88 from the current
account is the 8,195.88 of wealth the month actually cost.

## It is not a second loss either

The owner's own reading when this was found was that a savings draw is a *double*
loss: the savings go, and then the money is spent. The first half is real and the
second half is the same money. The draw **funds** the spending; counting both
would report October at −16,036.88 for a month that cost 8,195.88.

So there is one loss, paid from two pockets, and the net already names it. What
the net cannot say is *which* pockets — which is why the draw is disclosed rather
than merely excluded. A deficit of 8,195.88 with nothing beside it is a worse
screen than the wrong number it replaces.

## Why the disclosure is not called a savings draw

BurnRate has **one linked account** and no way to designate a balance as savings
— the gap Phase 3 left open, which Phase 11's Cushion is where it belongs. So the
product cannot know the money came from savings. It can only know it came from an
account it does not see, and the term says exactly that much and no more. Naming
it after savings would claim a fact the product has no way to hold.

## Consequences

**Every past month's reported figures change.** Income falls, Net Cash Flow falls
by the same amount, the savings rate falls with it, and the income and net cash
flow baselines are rebuilt from the corrected months. That is the correction, not
a side effect of it. Spending is untouched: a transfer was never on that side.

**The disclosure assumes every transfer in came from outside**, which holds while
one account is linked and stops holding at the second. A transfer between two
linked accounts lands as a credit on one and a debit on the other, and the credit
leg would be reported as money from outside when nothing entered the owner's
world. Closing that needs the two legs recognised as one movement — amount, date
window, opposite sign — and there is no case to test it against today. **The
trigger is the second linked account**, and the constraint is stated beside the
query rather than only here.

**A category's type stays uneditable through the API.** Correcting one is a
migration, as this was, so that rewriting what every past month reported stays a
decision someone makes deliberately rather than a control to click past. The
asymmetry with `deactivate_budget` — which *does* let the owner rewrite past
months from a button — is deliberate: cancelling a budget is a statement about one
commitment in one window, and ADR-0005 records why that one is safe to hand over.
