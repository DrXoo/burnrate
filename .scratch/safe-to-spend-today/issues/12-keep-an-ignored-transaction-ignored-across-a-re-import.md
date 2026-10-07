# 12: Keep an Ignored transaction Ignored across a re-import

**What to build:** One defect, found by `/code-review` on ticket 10 and reproduced end
to end. A transaction the owner marked **Ignored** gets a category back on the next
sync and counts as spend again, while the row still reads as excluded in the ledger
and stays out of the unknown queue — so the money returns to Safe to Spend Today and
nothing on screen says it did.

Pre-existing, and reachable today in the owner's own configuration. It is not a
correction on ticket 10: the window widening there extends the exposure by about a
month of history, but the defect already fired on the *next* sync for anything
excluded in the current month, which is where almost every exclusion is made.

**Blocked by:** None

**Status:** done

- [x] A re-imported transaction the owner marked Ignored keeps no category and reaches no spend figure
- [x] The rule engine states which rows it may categorize, rather than leaving it to `category_id is None`
- [x] Ignored is enforced where the money is counted: the spend and income queries say so, instead of depending on a NULL category to drop the row from a join
- [x] A test at the sync seam covers the re-import, and one at seam 2 covers the figure
- [x] The owner can still un-ignore a transaction, through both `categorize_transaction` and `restore_transaction`
- [x] `GLOSSARY.md`'s **Ignored** entry and `docs/technical/domain.md` record that the disposition survives a re-import

## The defect

`CategorizationService.exclude_transaction` clears the category and stamps
`excluded_at`: the row leaves the unknown queue and, because every spend query joins
`Category`, it leaves the figures too. `RulesService.apply_rule_to_transaction` then
guards only on `category_id is not None` and never reads `excluded_at`, and
`_upsert_transaction` calls it on every re-imported row. So a row the owner excluded
*and* that matches an active rule is handed its category straight back.

Reproduced against the current branch, one account, one rule on the merchant name:

```
imported, categorized : category=True  excluded=False spend=15.99
owner marks Ignored   : category=False excluded=True  spend=0.00
next sync re-imports  : category=True  excluded=True  spend=15.99
```

The last line is the defect: `excluded_at` is still set, so the ledger keeps showing
`excluded: true` and the unknown queue stays quiet, while the 15.99 is back in
monthly spending and therefore back out of the allowance. The owner has no way to
notice from the UI — the row looks exactly as they left it.

**Why it bites harder than it looks.** A rule is the normal way a recurring charge
gets its category, and a reimbursed or mis-posted instance of a recurring charge is
exactly what gets excluded. So the rows most likely to be Ignored are the rows most
likely to match a rule. The exclusion also survives in name, which means the figures
and the ledger disagree permanently rather than visibly.

## The two halves of the fix

**1 — The cause: the rule engine must not categorize an Ignored row.** Ignored is a
decision the owner made, and the rule engine exists to resolve rows nobody has
decided about. `apply_rule_to_transaction` returning early on `excluded_at is not
None` is the whole change. The sweep already respects the flag for the same reason
(`_sweep_stale_pending_transactions`), so the precedent and its wording exist.

**2 — The class: the spend queries should state the exclusion.** `GLOSSARY.md`
defines Ignored as "excluded from every metric", and today that is enforced only as a
side effect of a NULL category dropping the row from an inner join on `Category`.
`_count_uncategorized_transactions` filters `excluded_at` explicitly; `_get_monthly_spend`,
`_get_monthly_income` and `_get_budget_category_spend` do not. Any future path that
leaves a category on an excluded row — a manual fix-up, a backfill, a second rule
engine — lands the same bug. Stating the predicate where the money is counted makes
the term mean what the glossary says it means.

Worth deciding while here: whether `excluded_at` should also be cleared when a rule
*would* have matched, i.e. whether Ignored is a permanent disposition or one the
owner re-confirms. The current services say permanent until the owner acts
(`categorize_transaction` and `restore_transaction` both clear it), and nothing here
argues for changing that.

## Not in scope

* The performance note from the same review — one `SELECT` for the existing row plus
  a fresh `RulesService` per imported row, now paid over roughly twice as many rows
  per sync. Real, and `AGENTS.md` ranks performance last. `/simplify` territory once
  this is correct.

## Comments

**The fix is the two halves the ticket described, and the reproduction table closes.**
`apply_rule_to_transaction` now asks `_awaits_categorization` instead of testing
`category_id is not None`, and the three money queries state the exclusion. Run end to
end against the fake client, the last line reads `category=False excluded=True
spend=0.00` where it read `category=True excluded=True spend=15.99`.

**The decision the ticket left open stays where it was.** Ignored is permanent until the
owner acts; nothing here argued for re-confirming it when a rule would have matched.
What changed is *which* owner actions lift it — see the review section below, which
added a third and corrected a fourth.

**The bulk path got the guard too, which the ticket's "whole change" sentence did not
cover.** `apply_rule_to_existing_uncategorized` selected on `category_id IS NULL`, so
creating or editing any rule re-categorized every matching Ignored row, not just one the
sync happened to re-import. The web UI sends `apply_to_existing_uncategorized` from all
three of its rule affordances, so this was the common path rather than the rare one.

## What the review found, and where it went

Twelve findings. Ten are fixed in the implementation commit; two are unreachable once
the others are, and are recorded here rather than left open.

**Three were owner-reachable defects this ticket's own criteria did not cover.** The
fifth criterion names `categorize_transaction` and `restore_transaction` as the ways to
un-ignore, and there are four. `create_rule_from_transaction` assigned a category
without lifting the exclusion, and the Transactions page renders "Create rule" on an
Ignored row — only `categorySelect` checks `transaction.excluded`, `ruleAffordance` does
not — so a click produced a row showing a category and a rule that every figure dropped.
That one is sharper *because* of this ticket: before the spend queries stated the
exclusion, the same click left the money visibly mis-counted; after, it disappears
quietly. `uncategorize_transaction` answered "Transaction returned to unknown queue"
while leaving the row excluded and therefore out of it. And the bulk apply above.

**Two were unreachable once those three were closed, and are recorded as such.**
`delete_rule` computes `transactions_returned_to_queue` as `len(matched) - rematched`,
which would count an Ignored row as returned; and `restore_transaction` hard-codes a
null category in its response. Both need a row that is Ignored *and* holds a category or
a matched rule. Every path that writes either field now lifts the exclusion
(`categorize_transaction`, `create_rule_from_transaction`) or respects it (both rule
engine entry points), and `update_rule` and `delete_rule` delegate to those, so no
caller can produce that state. Fixing the symptoms would have been fixing unreachable
code; if a sixth writer ever lands, these two are where it will show.

**One was a factual error in the documentation this ticket added, and the best finding
of the twelve.** The first draft of `domain.md` asserted that Ignored "is a disposition
the owner sets, not a status the provider reports". It is both:
`_normalize_transaction_status` maps the Enable Banking codes `CNCL` and `RJCT` to
`status = 'ignored'`, and `schema.md` has always listed `ignored` among the status
values. One word, two unrelated things — the provider's cancellation and the owner's
`excluded_at` — and the doc denied the one the import actually writes. `GLOSSARY.md`
resolves it in language rather than in the schema: the status is **Cancelled**, the
disposition is **Ignored**, and a rename would need a migration for no behavioural gain.
`schema.md` gains the warning beside its status list, and the `excluded_at` column it
had never documented at all.

**One was a design argument that was right about the problem and wrong about the
destination.** `excluded_at IS NULL` was spelled six ways across four services, and the
review proposed `db/effective_date.py` as the shared home. That module is named for the
Effective Date concept and an exclusion predicate does not belong in it. The predicates
went to a sibling, `db/dispositions.py`, as `not_ignored()` and
`awaiting_categorization()` — the second being the pair that the review queue, the
ledger and the bulk apply had each been spelling for themselves. `RulesService` keeps a
row-at-hand twin, because the sync hands it an ORM object the database has not seen yet.

**One overstated its evidence.** The missing `safe_to_spend_today_amount` assertion was
called a change nothing would catch; mutation says otherwise, since removing the
exclusion moves `monthly_spending_amount` from 285.00 to 345.00 in the same run and that
assertion already existed. The allowance assertion is added anyway — it is the figure
the ticket names as the harm, and it flips `watch` to `over`, which reads as the defect
rather than as an arithmetic difference. The *second* half of that finding was a real
gap: no test ignored a **pending** charge, and pending spend is load-bearing per
ADR-0003, so a hold is a second route into the allowance. That test exists now and fails
at 70.00 against 25.00 when the predicate is removed.

**The remaining three were small and correct.** The exclusion belongs in the bulk
apply's `SELECT` rather than in a Python guard after the rows are hydrated, since the
`WHERE` already made half the guard dead code. `_count_uncategorized_transactions` was
the one query the ticket named as the precedent and the only one still spelling the
predicate inline. And the `NOT_IGNORED` docstring explained the exclusion as a side
effect of a join on `Category`, which is true of two of the three queries —
`_get_budget_category_spend` has no such join and dropped the rows through
`category_id IN (...)` instead. The wrong sentence had been copied into three places.

**Seams.** Five tests, four of them outside the spec's four agreed seams, because three
of these defects are not reachable from any of them: two at the `RulesService` seam, one
at the categorization seam, one at the sync seam and one at seam 2. The spec says no
test is written anywhere else, so this is a deliberate departure and belongs in
`/distill-decisions`. Every one was mutation-checked, which matters more than usual
here: two were green on first run against code an earlier cycle had already fixed, and a
third could not be seen red because the harness dropped the run between the test and
the fix.
