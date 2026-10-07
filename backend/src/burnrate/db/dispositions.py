"""Disposition: what the owner has decided about a transaction.

A disposition is the owner's decision, not the bank's report. Two of them are
queried often enough that the predicates live here rather than being spelled at
each call site: a figure asks whether a row is Ignored, and a review queue asks
whether a row is still undecided. Both were written inline at six sites across
three services, each site free to get it subtly wrong, which is how a null
category came to stand in for an exclusion. See Ignored in ``GLOSSARY.md``.

**``excluded_at`` is not ``status == "ignored"``.** The word names two unrelated
things in this codebase, and no query should test one to get the other:

* ``excluded_at`` is the disposition below -- the owner excluded this row from
  every metric, and it survives a re-import.
* ``status == "ignored"`` is a *provider* status, written by the import from the
  Enable Banking codes ``CNCL`` and ``RJCT`` (see
  ``EnableBankingService._normalize_transaction_status``). It means the bank
  cancelled or rejected the payment, which the owner never decided anything
  about. Such a row is already outside ``COMMITTED_STATUSES``, so it reaches no
  spend figure by a different route entirely.

Both spellings are load-bearing and neither is worth a migration to rename, so
the collision is recorded rather than resolved. ``GLOSSARY.md`` keeps Cancelled
as the term for the provider status for the same reason.
"""

from __future__ import annotations

from sqlalchemy import ColumnElement, and_

from burnrate.db.models import Transaction


def not_ignored() -> ColumnElement[bool]:
    """Rows the owner has not excluded: everything a metric is allowed to count.

    ``GLOSSARY.md`` defines Ignored as excluded from every metric, and every money
    figure states that here rather than inheriting it. The figures used to get it
    for free, because excluding a row also cleared its category and the spend
    queries dropped rows with no category -- by an inner join on ``Category`` in
    two of them and by ``category_id IN (...)`` in the third. That made the
    definition a consequence of how three queries happened to be shaped, so any
    path that left a category on an excluded row put the money back: the rule
    engine re-categorizing a re-imported row was one, a manual fix-up or a
    backfill is the next.
    """
    return Transaction.excluded_at.is_(None)


def awaiting_categorization() -> ColumnElement[bool]:
    """Rows still undecided: no category, and not resolved by exclusion either.

    This is the review queue's membership test, and the set the categorization
    rules are allowed to act on. Ignored has to be stated because an Ignored row
    holds no category either, so ``category_id IS NULL`` alone reads the owner's
    decision as an absence of one.

    ``RulesService._awaits_categorization`` is the row-at-hand twin of this, for
    the one caller holding an ORM object rather than building a query.
    """
    return and_(Transaction.category_id.is_(None), not_ignored())
