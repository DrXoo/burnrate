"""Effective Date: where a transaction sits in the calendar.

Every month-windowed query resolves month membership through the expression
below rather than reading a date column directly, so the rule has one
definition. It is a SQL expression and not a domain function because it must
resolve per row inside the query -- there is nothing here for the application
layer to decide. See Effective Date in ``GLOSSARY.md``.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import ColumnElement, and_, func

from burnrate.db.models import Transaction


def effective_date() -> ColumnElement[date]:
    """Booking date, then value date, then the day the row was imported.

    Booking date stays first in the chain, so every figure the owner already
    relies on is unchanged to the cent -- the fallbacks only fire on rows that a
    month window on ``booking_date`` could not see at all. A pending card
    authorization is the common case: the bank has no booking date for it yet,
    and ``booking_date >= month_start`` never matches NULL.

    The import date is a last resort for a row the bank dated not at all, and it
    does not resolve on the owner's calendar day: SQL has no portable timezone
    conversion, and SQLite -- which the tests run on -- carries no timezone
    database at all, so a timezone-aware form could not be exercised by the same
    expression that ships. A charge imported within a few hours of a month
    boundary can therefore land in the adjacent month. That is within the noise of
    using an import instant as a proxy for a date the bank withheld, and it
    self-corrects as soon as the charge books.

    Which day it does resolve on is the *database session's*, not UTC:
    ``date(timestamptz)`` in PostgreSQL converts through the session ``TimeZone``,
    so the same instant yields 2026-06-30 under ``UTC`` and 2026-07-01 under
    ``Europe/Madrid``. The deployment must therefore keep the session in UTC --
    which it is, by PostgreSQL default -- because setting ``TZ`` or ``PGTZ`` in the
    environment would silently move undated charges between months. The test suite
    cannot catch that: SQLite's ``date()`` reads the stored naive UTC wall clock
    and is unaffected, so the two dialects compiling this expression identically
    does not make their runtime semantics identical.
    """
    return func.coalesce(
        Transaction.booking_date,
        Transaction.value_date,
        func.date(Transaction.imported_at),
    )


def within_month(*, month_start: date, month_end: date) -> ColumnElement[bool]:
    """The month window itself: a transaction whose Effective Date lands in the month.

    Half-open, ``[month_start, month_end)``, so consecutive months neither overlap
    nor leave a gap. Callers pass the window and get a predicate, rather than
    pairing ``>=`` and ``<`` correctly at each of the six query sites -- the
    boundary convention is decided here once.

    The expression renders twice in the emitted SQL, once per comparison, because
    SQLAlchemy writes out each occurrence of a column element. That is left alone:
    the coalesce is three column reads and a cast, and the alternatives (a CTE, or
    an inclusive ``BETWEEN`` over ``month_end`` minus a day) cost more clarity than
    they save work.
    """
    resolved = effective_date()
    return and_(resolved >= month_start, resolved < month_end)
