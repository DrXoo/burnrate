# A whole-month baseline is a median; a category's is a mean

`figure_baseline_amount`, which computes the baseline for **monthly income** and
**net cash flow**, is a **median** over the Qualifying Months in the window.
`category_baseline`, which computes a per-category baseline, stays a **mean**. The
asymmetry is the decision, and it is not an inconsistency waiting to be tidied.

## Why the aggregates needed it

A per-category baseline is protected by `BASELINE_PRESENCE_FLOOR`: a category with
spend in fewer than two Qualifying Months is denied a mean, so an event in a new
category never becomes a normal. **The aggregates have no such notion** — a
whole-month figure cannot be "spent in too rarely" — so they had no protection at
all, and the exemption was deliberate and documented.

That exemption is the hole the owner's October 2026 walked through, and it is the
one no budget closes. The Event Budget rule (ADR-0011) reads a bounded window as
the owner declaring an event, which covers the €8,053.83 divorce. It cannot cover
July's **€5,500.00 severance**, because an exceptional *income* has no window to
bound. Measured over {July, October, November}:

| Figure | Mean | Median |
|---|---|---|
| Net cash flow | −€2,289.20 | **−€1,568.45** |
| Monthly income | €2,653.38 | **€1,055.20** |

The income figure is the sharper one, because unlike net cash flow it carries a
**verdict**. With the mean, the month the owner's income returned to normal would
have published *"60% below usual"* — a product telling someone out of work that
their income had collapsed.

## Why 9a rejected a median, and why that was right then

9a recorded:

> At the two Qualifying Months the minimum allows, a median *is* the mean. Robust
> statistics need a distribution, and per-transaction distributions are out of
> scope by decision, not by omission.

Correct on the floor it had. A median of two is the mean of two. **A median of
three is not** — it rejects exactly one outlier, which is precisely what a divorce
month or a severance month is. So raising `BASELINE_MINIMUM_MONTHS` from 2 to 3
is what made this available, and the two changes only work together: either alone
leaves the owner with a published figure built from events.

That composition was not foreseen when the minimum was raised. It is recorded here
because the reverse also holds: **lowering the minimum back to 2 silently turns
this median back into a mean**, and nothing in the code would say so.

## Why a category keeps the mean

`category_baseline` divides by **every** Qualifying Month in the window, treating a
month the category was absent from as a real zero, *"because for a recurring
expense that absence is information"*. A median would discard that: a category
with spend in two of three months would report its typical month as the spend,
losing the fact that one month had none. The presence floor already does the
protecting there, and it does it better than a median could — it refuses to answer
at all rather than answering from too little.

So the rule is: **protection by refusing (a floor) where the data supports it,
protection by robustness (a median) where it does not.**

## Consequences

**"Normally" now means typical rather than average**, which is the claim the
product was already making in words. The behaviour that changes most is irregular
income: someone paid once in three months now has a typical month of **nothing**,
where the mean reported a third of a payslip as monthly income. That is the honest
answer, and it is a change.

**A median of zero is reachable where a mean of zero was not.**
`deviation_percent` and `comparison_status` already treat a baseline of zero or
less as absent, so it lands as "nothing to compare against" rather than as a
division — the guard predates this and was written for a refund cancelling a
month, which the presence floor made nearly unreachable. It is no longer nearly
unreachable, so that docstring's "nearly" is now carrying less weight than it
reads.

**The mean is not kept anywhere as a second answer.** Two statistics for one
figure is how two readers come to disagree about what normal is, which is the
defect `burnrate.db.counted_spend` and `burnrate.db.budget_windows` both exist to
prevent.

**The function had no test of its own before this change.** It was exercised only
through `BaselineService`, and every fixture in that module seeds months with
identical figures — where a median and a mean agree. That is how a plain mean
survived in the one figure that needed robustness most, and it is why this change
added a service-seam test with an outlier in the window as well as the pure ones.

**This does not deliver the long window.** Twelve months with a median remains the
target shape in the roadmap; the median half arrived early because three months
turned out to be enough for it. The window is still blocked on history.
