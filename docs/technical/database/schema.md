# BurnRate Database Schema

## Goal

This document proposes the first PostgreSQL schema for BurnRate.

The schema is designed to support:

* Personal account aggregation through Enable Banking
* Idempotent account and transaction imports
* Categorization rules
* Monthly budgets
* Burn rate and runway calculations
* Clear separation between integration data and product domain data

---

## Schema Design Principles

The database should follow these principles:

* PostgreSQL is the default persistence layer
* Monetary values use exact numeric types, not floats
* Timestamps are stored in UTC
* Enable Banking identifiers are preserved for idempotent sync
* Integration-specific tables remain separate from core product tables
* Derived metrics are calculated from source data, not stored as primary truth

---

## Main Table Groups

The first schema can be organized into four groups:

1. Integration tables
2. Core finance tables
3. Classification and budgeting tables
4. Operational tables

---

## Integration Tables

For the first version, the schema may be coupled directly to Enable Banking.

That means the integration tables can use Enable Banking-specific naming instead of a provider-agnostic abstraction.

### `enable_banking_app_configs`

Stores configuration metadata for the Enable Banking application used by this BurnRate instance.

Suggested columns:

* `id` UUID primary key
* `app_id` TEXT not null
* `environment` TEXT not null
* `redirect_url` TEXT not null
* `restricted_mode` BOOLEAN not null
* `created_at` TIMESTAMPTZ not null
* `updated_at` TIMESTAMPTZ not null

Suggested constraints:

* Unique on `app_id`

Notes:

* Secret material such as the private key should stay in environment variables or a secret store, not in this table.

---

### `enable_banking_connections`

Represents one authorization relationship between BurnRate and one ASPSP through Enable Banking.

Suggested columns:

* `id` UUID primary key
* `aspsp_name` TEXT not null
* `aspsp_country` TEXT not null
* `psu_type` TEXT not null
* `session_id` TEXT
* `session_status` TEXT
* `authorized_at` TIMESTAMPTZ
* `last_synced_at` TIMESTAMPTZ
* `active` BOOLEAN not null
* `created_at` TIMESTAMPTZ not null
* `updated_at` TIMESTAMPTZ not null

Suggested indexes:

* Index on `(aspsp_country, aspsp_name)`
* Index on `session_id`

Notes:

* For the first version, one user may still have multiple connections if multiple banks are linked.

---

### `enable_banking_account_mappings`

Maps Enable Banking account identifiers to local BurnRate accounts.

Suggested columns:

* `id` UUID primary key
* `enable_banking_connection_id` UUID not null
* `external_account_id` TEXT not null
* `external_account_hash` TEXT
* `account_id` UUID not null
* `last_seen_at` TIMESTAMPTZ not null
* `created_at` TIMESTAMPTZ not null
* `updated_at` TIMESTAMPTZ not null

Suggested constraints:

* Foreign key `enable_banking_connection_id -> enable_banking_connections.id`
* Foreign key `account_id -> accounts.id`
* Unique on `external_account_id`

---

## Core Finance Tables

### `accounts`

Represents local BurnRate accounts.

Suggested columns:

* `id` UUID primary key
* `display_name` TEXT not null
* `currency` TEXT not null
* `included_in_calculations` BOOLEAN not null
* `included_in_runway` BOOLEAN not null
* `latest_balance_amount` NUMERIC(18,2)
* `latest_balance_currency` TEXT
* `last_synced_at` TIMESTAMPTZ
* `created_at` TIMESTAMPTZ not null
* `updated_at` TIMESTAMPTZ not null

Suggested indexes:

* Index on `included_in_calculations`
* Index on `included_in_runway`

---

### `transactions`

Represents imported account transactions.

Suggested columns:

* `id` UUID primary key
* `account_id` UUID not null
* `enable_banking_transaction_id` TEXT
* `booking_date` DATE
* `value_date` DATE
* `amount` NUMERIC(18,2) not null
* `currency` TEXT not null
* `description` TEXT
* `merchant_name` TEXT
* `counterparty_name` TEXT
* `direction` TEXT not null
* `status` TEXT not null
* `category_id` UUID
* `matched_rule_id` UUID
* `excluded_at` TIMESTAMPTZ
* `raw_payload` JSONB
* `imported_at` TIMESTAMPTZ not null
* `created_at` TIMESTAMPTZ not null
* `updated_at` TIMESTAMPTZ not null

Suggested constraints:

* Foreign key `account_id -> accounts.id`
* Foreign key `category_id -> categories.id`
* Foreign key `matched_rule_id -> categorization_rules.id`
* Unique on `enable_banking_transaction_id` when present

Suggested indexes:

* Index on `account_id`
* Index on `booking_date`
* Index on `status`
* Index on `category_id`
* Index on `(account_id, booking_date)`

Notes:

* `raw_payload` is useful for traceability and future parser improvements.
* `status` should support values such as `pending`, `booked`, `unknown`, and `ignored`.
* `status = 'ignored'` and `excluded_at` are **different things that share a word**.
  The status is the provider's: the import writes it from the Enable Banking codes
  `CNCL` and `RJCT`, meaning the bank cancelled or rejected the payment. `excluded_at`
  is the owner's decision to exclude a row from every metric -- the Ignored
  disposition in `GLOSSARY.md`, which calls the status Cancelled to keep the two
  apart. No query should test one to get the other; the predicates live in
  `burnrate/db/dispositions.py`.
* Month placement does **not** read `booking_date` directly. Every month-windowed
  query compares the effective date -- `coalesce(booking_date, value_date,
  date(imported_at))` -- so that a pending row with no booking date still belongs
  to a month. See `burnrate/db/effective_date.py` and the Transaction section of
  `docs/technical/domain.md`.
* That makes the window non-sargable, so the `booking_date` indexes above no
  longer serve it and those queries plan as sequential scans. Deliberate for now:
  single-owner volumes make the difference immeasurable (cost 38 to 84 over 487
  rows), and `AGENTS.md` ranks performance last. The fix when it is needed is an
  expression index on the coalesce, or the stored `effective_date` column that
  Phase 8 deferred because it needs a backfill -- the latter restores plain
  indexing and is the better end state.
* The first version can stay coupled to Enable Banking transaction identifiers.

---

## Classification and Budgeting Tables

### `categories`

Represents transaction categories.

Suggested columns:

* `id` UUID primary key
* `name` TEXT not null
* `type` TEXT not null
* `active` BOOLEAN not null
* `created_at` TIMESTAMPTZ not null
* `updated_at` TIMESTAMPTZ not null

Suggested constraints:

* Unique on `name`

Notes:

* `type` should support values such as `expense`, `income`, and `transfer`.
* `name` is editable after creation and is the only label any surface shows for a
  category, so nothing stores a copy of it. Uniqueness is enforced
  case-insensitively by the application, which is stricter than the exact database
  constraint. See `docs/adr/0006-a-categorys-name-is-the-only-name-it-has.md`.
* `active` is how a category is retired, and it is the only way to retire one that
  has history: rows are deleted only while nothing references them. Four guards read
  this column and refuse an inactive category -- assigning a transaction, opening a
  budget, creating a rule, and reopening a cancelled budget. See
  `docs/adr/0007-a-used-category-is-archived-never-deleted.md` for why deleting a
  referenced category is refused rather than cascaded.

---

### `categorization_rules`

Represents reusable text-based categorization rules.

Suggested columns:

* `id` UUID primary key
* `name` TEXT
* `match_field` TEXT not null
* `match_operator` TEXT not null
* `match_value` TEXT not null
* `category_id` UUID not null
* `priority` INTEGER not null
* `active` BOOLEAN not null
* `created_from_manual_classification` BOOLEAN not null
* `created_at` TIMESTAMPTZ not null
* `updated_at` TIMESTAMPTZ not null

Suggested constraints:

* Foreign key `category_id -> categories.id`

Suggested indexes:

* Index on `active`
* Index on `priority`
* Index on `category_id`

Notes:

* `match_field` should target transaction naming fields only, such as `description`, `merchant_name`, or `counterparty_name`.
* `match_operator` should support `contains`, `equals`, `starts_with`, `ends_with`, and `regex`.

---

### `budgets`

Represents category-level monthly budgets.

Suggested columns:

* `id` UUID primary key
* `category_id` UUID not null
* `amount` NUMERIC(18,2) not null
* `currency` TEXT not null
* `period_type` TEXT not null
* `active_from` DATE not null
* `active_to` DATE
* `created_at` TIMESTAMPTZ not null
* `updated_at` TIMESTAMPTZ not null

Suggested constraints:

* Foreign key `category_id -> categories.id`

Suggested indexes:

* Index on `category_id`
* Index on `active_from`
* Index on `active_to`

Notes:

* For the first version, `period_type` is expected to be `monthly`.
* The total monthly budget is derived by summing active category budgets.
* **The window is month-granular at both ends, and the counting rule is why.** A
  budget is counted in full for any month its `[active_from, active_to]` window
  touches at all — there is no proration — so a window edge landing one day inside a
  month hands that month the whole amount. Both edges are therefore month
  boundaries: `active_from` is required to be a 1st, and `active_to` is always a
  month end or NULL. Cancelling records the last day of the month *before* the one
  the owner is in, so the month they cancel in drops the budget — cancelling says
  the commitment is gone, the rest of this month included. An open window
  (`active_to` NULL) is the normal state and rolls forward indefinitely, which is
  why nothing asks the owner to close a month; changing an amount from a given month
  creates the next row and closes the previous one automatically. Cancelling is
  undoable: reactivating clears `active_to` on the same row, and is refused when a
  later budget for the category has taken over. Proration is the alternative and was
  weighed and deferred; see
  `docs/adr/0005-budget-windows-are-month-granular.md`.
* **A budget's status is relative to a month, not to today.** The same window rule
  decides both what a month's total counts and whether a row is `active`,
  `scheduled` or `inactive` for the month being viewed, so `GET /budgets` takes the
  same optional `?month=YYYY-MM` as `/summary` and defaults to the month the owner
  is in. `burnrate.db.budget_windows` holds the rule for both readers.

---

## Operational Tables

### `sync_sessions`

Tracks synchronization attempts and outcomes.

Suggested columns:

* `id` UUID primary key
* `enable_banking_connection_id` UUID
* `started_at` TIMESTAMPTZ not null
* `finished_at` TIMESTAMPTZ
* `status` TEXT not null
* `imported_accounts_count` INTEGER not null
* `imported_transactions_count` INTEGER not null
* `error_summary` TEXT
* `created_at` TIMESTAMPTZ not null
* `updated_at` TIMESTAMPTZ not null

Suggested constraints:

* Foreign key `enable_banking_connection_id -> enable_banking_connections.id`

Suggested indexes:

* Index on `status`
* Index on `started_at`

Notes:

* This table helps debugging sync problems and understanding refresh history.

---

### `enable_banking_auth_requests`

Tracks outbound authorization attempts before the callback completes.

Suggested columns:

* `id` UUID primary key
* `enable_banking_connection_id` UUID
* `state` TEXT not null
* `redirect_url` TEXT not null
* `aspsp_name` TEXT not null
* `aspsp_country` TEXT not null
* `psu_type` TEXT not null
* `expires_at` TIMESTAMPTZ
* `completed_at` TIMESTAMPTZ
* `created_at` TIMESTAMPTZ not null
* `updated_at` TIMESTAMPTZ not null

Suggested constraints:

* Foreign key `enable_banking_connection_id -> enable_banking_connections.id`
* Unique on `state`

Notes:

* This table is useful for callback validation and replay protection.

---

## Relationship Summary

At a high level, the main relationships are:

* One `enable_banking_connection` can map to many `enable_banking_account_mappings`
* One `account` can have many `transactions`
* One `category` can be referenced by many `transactions`
* One `category` can have many `budgets`
* One `category` can be targeted by many `categorization_rules`
* One `enable_banking_connection` can have many `sync_sessions`

---

## Suggested First Migration Order

A practical creation order would be:

1. `enable_banking_app_configs`
2. `accounts`
3. `categories`
4. `categorization_rules`
5. `budgets`
6. `enable_banking_connections`
7. `enable_banking_account_mappings`
8. `transactions`
9. `sync_sessions`
10. `enable_banking_auth_requests`

---

## Out of Scope for the First Version

The initial schema does not need:

* Multi-user ownership tables
* Payment initiation tables
* Separate reporting snapshot tables
* Full audit-event streams
* Ledger-style double-entry accounting structures

These can be added later if the project expands beyond the current product scope.
