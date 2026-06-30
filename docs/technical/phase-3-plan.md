# BurnRate Phase 3 Plan

## Goal

Phase 3 should turn the working Enable Banking integration into the first real product loop.

At the end of this phase, BurnRate should no longer feel like a bank-sync prototype.

It should feel like a usable spending tool.

---

## Current Starting Point

Phase 1 and Phase 2 already give BurnRate:

* A working backend scaffold
* PostgreSQL persistence and migrations
* Enable Banking account linking
* Initial account, balance, and transaction import
* Manual re-sync support
* Connection inspection endpoints

This means Phase 3 does not need to start from infrastructure.

It can focus on product behavior.

---

## Phase 3 Objective

A real user should be able to:

1. See imported transactions in the Web UI
2. Identify uncategorized transactions quickly
3. Categorize transactions manually
4. Save categorization rules for future reuse
5. Define monthly category budgets
6. See summary metrics such as money left, monthly spending, burn rate, and runway

---

## Delivery Strategy

Phase 3 should still be built as thin vertical slices.

The safest order is:

1. Read-only visibility first
2. Manual categorization second
3. Rule creation and reuse third
4. Budget workflows fourth
5. Summary calculations and dashboard last

This order matters because:

* It gives us a usable UI early
* It validates the transaction model before adding behavior on top
* It prevents summary logic from being built on unstable categorization assumptions

---

## Phase 3 Milestones

### Milestone 3.1: Transaction Visibility

Objective:

Expose imported data clearly through backend APIs and a first Web UI view.

Scope:

* Add backend read endpoints for:
  * accounts
  * transactions
  * uncategorized transaction count
* Support basic transaction filtering:
  * account
  * month
  * status
  * categorized vs uncategorized
* Create the first Web UI pages:
  * connection overview
  * account list
  * transaction list

Definition of done:

* A user can open the Web UI and inspect imported balances and transactions without touching PostgreSQL

Notes:

* Sorting, pagination, and filtering should be good enough for real use, not perfect
* This is the first slice that replaces direct database inspection

---

### Milestone 3.2: Unknown Queue And Manual Categorization

Objective:

Turn uncategorized imports into an explicit review workflow.

Scope:

* Add backend endpoints for:
  * listing uncategorized transactions
  * assigning a category to a transaction
* Define a stable category model for the first version
* Add a Web UI screen for the Unknown queue
* Allow classifying one transaction at a time

Definition of done:

* A user can open the Unknown queue, pick a category, and see the transaction leave the queue immediately

Notes:

* This is the first truly product-critical loop
* Keep the UI direct and fast rather than “admin panel” heavy

---

### Milestone 3.3: Rule Creation And Reuse

Objective:

Make manual categorization pay off over time.

Scope:

* Add backend endpoints for:
  * creating a categorization rule from a transaction
  * listing rules
  * enabling or disabling rules
* Implement rule application for:
  * newly imported transactions
  * optionally existing uncategorized transactions on demand
* Support the agreed rule operators:
  * contains
  * equals
  * starts with
  * ends with
  * regex
* Add simple rule visibility in the Web UI

Definition of done:

* A user can classify a transaction, save a rule, re-sync, and see later matching transactions categorized automatically

Notes:

* Rule priority should stay deterministic from the start
* Keep rule scope text-based only in Phase 3

---

### Milestone 3.4: Budget Management

Objective:

Let the user define monthly targets per category.

Scope:

* Add backend endpoints for:
  * listing budgets
  * creating budgets
  * updating budgets
  * deactivating budgets
* Add category-budget linkage rules
* Build a basic Web UI for budget CRUD

Definition of done:

* A user can define active monthly budgets for categories and see them persisted correctly

Notes:

* Global budget remains derived from the sum of category budgets
* We should avoid overdesigning recurring budget complexity in this phase

---

### Milestone 3.5: Summary And Dashboard

Objective:

Turn transactions and budgets into the core BurnRate view.

Scope:

* Add summary calculation services for:
  * current balance
  * monthly spending
  * money left
  * uncategorized count
  * burn rate
  * runway
* Add backend summary endpoints
* Add the first real dashboard screen in the Web UI

Definition of done:

* A user can answer the main product questions from the dashboard in under 10 seconds

Notes:

* Transfer and income handling must not inflate spending metrics
* Runway must only use balances from accounts included in runway calculations

---

## Cross-Cutting Work During Phase 3

These tasks should be handled alongside the milestones rather than postponed:

* Improve transaction import diagnostics, especially where providers return zero transactions
* Keep API responses stable and typed
* Add integration tests for the categorization and budget flows
* Add seed data or fixtures for local UI development
* Keep the Web UI mobile-friendly from the first real screens

---

## Suggested Build Order In Code

Within implementation, the preferred order is:

1. Read APIs for accounts and transactions
2. Web UI transaction list
3. Categories and unknown queue endpoints
4. Manual categorization UI
5. Rule creation and application
6. Budget APIs and budget UI
7. Summary calculation services
8. Summary/dashboard UI

This keeps the backend honest while giving the frontend real data early.

---

## Explicit Non-Goals For Phase 3

Phase 3 should not expand into:

* Telegram product work
* Full sync automation
* Multi-provider abstraction
* Advanced forecasting
* Complex reporting exports
* Fine-grained access control

Those concerns belong to later phases.

---

## Definition Of Done For Phase 3

Phase 3 is complete when:

* Imported transactions are visible in the Web UI
* Uncategorized transactions can be reviewed quickly
* Categories can be assigned manually
* Rules can be created and reused
* Monthly budgets can be managed
* The dashboard shows current balance, monthly spending, money left, burn rate, and runway
* A user can complete the main workflow without reading logs or querying PostgreSQL
