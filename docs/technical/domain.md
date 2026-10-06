# BurnRate Domain Model

## Goal

This document defines the main business concepts BurnRate should use internally so the product, API, and persistence layers speak the same language.

The domain model is intended to be stored in PostgreSQL for the first version.

---

## Core Entities

### Account

Represents a bank account included in BurnRate.

Suggested attributes:

* Internal account id
* Provider account id
* Provider name
* Display name
* Currency
* Included in calculations flag
* Included in runway flag
* Latest known balance
* Last synced at

`Provider account id` should be unique per provider.

---

### Transaction

Represents one financial movement imported from a provider or created internally for bookkeeping of import state.

Suggested attributes:

* Internal transaction id
* Provider transaction id
* Account id
* Booking date
* Value date
* Amount
* Currency
* Description
* Merchant or counterparty
* Direction
* Category id
* Status
* Rule id that assigned the category

`Amount` should be stored as a precise numeric value, not a float.

`Booking date` and `value date` should remain distinct when the provider supplies both.

`Effective date` is the date that places a transaction in a month: its booking
date, or its value date, or the day it was imported, in that order. It is
resolved in query rather than stored, so every month-windowed figure asks one
shared expression (`burnrate/db/effective_date.py`) instead of reading a date
column directly.

Booking date stays first in that chain so no figure already reported to the
owner is restated; the fallbacks only reach rows a window on booking date could
not see at all. Pending transactions are the reason the chain exists: the
provider has no booking date for them yet, and a null booking date satisfies no
month comparison in SQL, so such a row belonged to no month and reached no
review queue. The import date is a last resort for a row the provider dated not
at all, and it resolves on the *database session's* calendar day rather than the
owner's -- SQL has no portable timezone conversion, so a charge imported within
hours of a month boundary can land in the adjacent month until it books. That the
day is UTC is a deployment precondition, not a property of the expression:
PostgreSQL defaults the session to UTC, and setting `TZ` or `PGTZ` on the database
container would silently move undated charges between months with no test able to
catch it. See the docstring in `db/effective_date.py`.

`Provider transaction id` should be unique per provider when reliably available.

Suggested statuses:

* Pending
* Booked
* Unknown
* Ignored

Pending and booked transactions should be stored in the same transaction model, differentiated by status.

---

### Category

Represents a spending or income classification used by budgets and reporting.

Suggested attributes:

* Internal category id
* Name
* Type
* Active flag

Suggested types:

* Expense
* Income
* Transfer

---

### Categorization Rule

Represents a reusable rule that maps transactions into categories automatically.

Suggested attributes:

* Internal rule id
* Match field
* Match operator
* Match value
* Category id
* Priority
* Active flag
* Created from manual classification flag

For the first version, rules should match only against transaction naming fields such as description, merchant, or counterparty text.

Suggested match operators:

* Contains
* Equals
* Starts with
* Ends with
* Regex

Rules should not depend on transaction amount or account-level conditions in the first version.

Rules should be deterministic and evaluated in a stable order.

---

### Budget

Represents a monthly spending target for one category.

Suggested attributes:

* Internal budget id
* Category id
* Amount
* Period type
* Active from
* Active to

For the first version, monthly budgets are sufficient.

Budgets should be defined per category.

There is no need for a separate global monthly budget entity in the first version, because the overall budget can be derived as the sum of all active category budgets.

---

### Sync Session

Represents one synchronization attempt with a bank provider.

Suggested attributes:

* Internal sync session id
* Provider name
* Started at
* Finished at
* Status
* Imported transaction count
* Error summary

This entity helps with traceability and troubleshooting.

Timestamps should be stored in UTC.

---

## Derived Concepts

### Current Balance

The latest known sum of balances across included accounts.

---

### Monthly Spending

The sum of expense transactions within the current calendar month.

Income transactions should not be mixed into this metric.

---

### Money Left

The remaining monthly budget after subtracting categorized spending from configured budgets.

The total monthly budget is derived from the sum of all active category budgets.

---

### Burn Rate

The current pace of spending, typically represented as daily average spending and projected month-end spending.

---

### Runway

The estimated time remaining before designated savings are exhausted, based on the current monthly deficit.

---

## Important Invariants

BurnRate should preserve the following invariants:

* A transaction must belong to exactly one account
* A transaction may have zero or one assigned category
* Unknown transactions are uncategorized transactions that require review
* Every transaction belongs to exactly one month, resolved by its effective date
* Transfer categories should not inflate spending metrics
* Income should remain a minimal classification concern and should not drive budget reporting in the first version
* Runway should only use balances from accounts explicitly included for runway calculations
* Imported provider identifiers should support idempotent re-sync behavior
* Monetary values should be stored with exact precision

---

## Current Modeling Decisions

The following decisions are currently assumed for implementation:

* Pending and booked transactions should share one transaction model with a status field
* Rules should support text-based matching only, using operators such as contains, equals, starts with, ends with, and regex
* Rules should not depend on transaction amount or account conditions in the first version
* Budgets should exist only per category, with the general monthly budget derived from their sum
* Income should remain secondary to expense visibility and can be grouped under a minimal income classification model
* PostgreSQL should be the default persistence target for the first version
