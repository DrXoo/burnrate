# A used category is archived, never deleted

Categories could only ever be created. `Category.active` existed and three
guards already refused an inactive category — assigning a transaction, opening a
budget, creating a rule — but nothing could set it to false, so the locks were
installed and the key was never cut.

Three things reference a category: transactions, budgets and rules. Its budget
rows are what past months reported, so deleting them would change figures those
months already published — the same history `0005` went to some length to keep
stable. Deleting is therefore allowed only while **nothing** references the
category, which is the typo case and genuinely costs nothing; a referenced one is
refused, and the refusal names every blocker at once. Retiring a category that
has history is archiving: it keeps every row that already points at it and only
closes the category to new spend.

Archiving is itself refused while anything would still file into it — a budget
whose window reaches the current month or later, or an active rule targeting it.
A hidden category that keeps collecting is the one outcome archiving exists to
prevent.

## Considered Options

**Cascade-deleting the category with its budgets and rules**, returning its
transactions to the review queue, the way `delete_rule` already does for rules.
Rejected: a rule is a convenience and a budget is a record. Dropping budget rows
rewrites what closed months reported, and the transactions landing back in the
queue silently changes every budget-basis figure for those months too. There is
also no way back, where archiving has one.

**Archiving only, with no delete at all.** Rejected as the smaller mistake in
the other direction: a category created by typo has nothing pointing at it, and
leaving it in an archive list for ever is clutter with no upside.

**Cancelling the blocking budget and switching off the blocking rules as part of
archiving.** Rejected: both are visible, undoable acts with their own meaning,
and doing either silently inside a third one hides it. The refusal names what is
in the way so the owner clears it deliberately.

## Consequences

**The categories a new transaction may be filed against are a different set from
the categories that are listed.** Archived ones stay in the list — the Categories
page is where they come back from — but leave every assignment picker. The
month's transaction filter keeps them, because seeing what a retired category
used to cost is the reason it was kept. That distinction is derived once, beside
the category state it reads, so the pickers cannot drift apart.

**A transaction already filed under an archived category carries that category in
its own picker**, marked, and it is not offered to any other row. Archiving does
not touch rows already filed, so such a transaction is still categorised, and a
controlled `select` whose value matches no option falls back to its first — a
categorised row reading as unassigned, and refiled elsewhere on the next pick.

**Reopening a budget answers to the archive guard too.** Without it, the way to
get a live budget on an archived category was to cancel the budget, archive the
category — permitted, because a closed window reaches no month — and then
reactivate. The month's total would then count a category nothing can be filed
against: a budget that can only ever be underspent.

**`Category.active` is now reachable, so its three original guards finally
fire.** Any fourth path that assigns spend, opens a budget or files by rule must
check it as well; the existing ones are the pattern.
