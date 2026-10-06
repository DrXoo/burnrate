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

**Status:** ready-for-agent

- [ ] A re-imported transaction the owner marked Ignored keeps no category and reaches no spend figure
- [ ] The rule engine states which rows it may categorize, rather than leaving it to `category_id is None`
- [ ] Ignored is enforced where the money is counted: the spend and income queries say so, instead of depending on a NULL category to drop the row from a join
- [ ] A test at the sync seam covers the re-import, and one at seam 2 covers the figure
- [ ] The owner can still un-ignore a transaction, through both `categorize_transaction` and `restore_transaction`
- [ ] `GLOSSARY.md`'s **Ignored** entry and `docs/technical/domain.md` record that the disposition survives a re-import

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
