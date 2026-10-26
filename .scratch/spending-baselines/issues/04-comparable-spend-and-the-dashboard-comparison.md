# 04: Comparable Spend, Uncomparable Spend, and the dashboard's comparison

**What to build:** The dashboard shows monthly spending, income and net cash flow each
against its own baseline, as a second line beneath figures the owner already reads. The
spending comparison is computed over **only** the categories that have a baseline, and
the spend that could not be compared is reported beside it rather than inside it.

This is the ticket where the owner's October reads correctly: one category with no
history holding the great majority of the month must not turn a quiet month into a
report of catastrophic overspending.

**Blocked by:** 02.

**Status:** ready-for-agent

- [ ] Monthly spending is shown against a baseline computed only over the categories that have one
- [ ] The Uncomparable Spend total is reported beside the comparison and never counted inside it
- [ ] A month in which one uncomparable category exceeds the entire comparable total does not move the comparison, and the comparison still reports the ordinary categories honestly
- [ ] Income and net cash flow are each shown against their own baseline
- [ ] Safe to Spend Today is given no baseline
- [ ] The comparisons appear beneath the existing figures; no new page is added
- [ ] An absent baseline is null in the payload rather than zero, and renders as no claim rather than as a figure
- [ ] Paging back to a closed month shows that month's comparison against the months before it
- [ ] Below the minimum Qualifying Month count, the dashboard states that there is not enough history rather than showing an empty comparison
- [ ] Every pre-existing summary field is unchanged, asserted as a regression
- [ ] Tests live only at the pure-domain seam, the summary service seam, and page rendering
- [ ] Including uncomparable categories in the aggregate puts the October-shaped test red
