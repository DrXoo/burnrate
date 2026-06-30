# BurnRate Implementation Roadmap

## Goal

This document proposes the implementation roadmap for BurnRate.

The roadmap is designed to reduce delivery risk while keeping the work aligned with the product vision.

It should help answer:

* What should be built first?
* Which risks should be validated early?
* How should the project move from design documents to a usable product?

---

## Delivery Strategy

BurnRate should not be built strictly bottom-up or strictly top-down.

Instead, the project should use a middle-out strategy:

* Establish the core backend and data model early
* Validate Enable Banking integration as soon as possible
* Build the user-facing product loop on top of real imported data
* Add automation and secondary interfaces only after the main flow works

This approach avoids two common mistakes:

* Overbuilding infrastructure before proving the product loop
* Building UI flows before the banking integration and sync model are stable

---

## Guiding Principle

The first goal is not to build the full platform.

The first goal is to prove that BurnRate can reliably do this end-to-end:

1. Connect one of the owner's real bank accounts through Enable Banking
2. Import balances and transactions into PostgreSQL
3. Show that data in the Web UI
4. Categorize transactions
5. Define budgets
6. Produce a useful summary with money left, burn rate, and runway

If that loop works, BurnRate has a real foundation.

---

## Phase 1: Foundations

### Objective

Create the minimal technical base required for the rest of the implementation.

### Scope

* Choose backend framework and project structure
* Create PostgreSQL setup
* Define Docker Compose-based local and self-hosted runtime model
* Create migrations system
* Implement environment and secret configuration
* Add initial `.env.example`
* Define initial runtime services: `backend`, `web`, `postgres`, and `sync-worker`
* Create initial database schema
* Define core modules for domain, application, and infrastructure

### Deliverables

* Backend project boots successfully
* PostgreSQL is reachable from the application
* Docker Compose can start the core local stack
* Initial migrations can be applied and rolled back
* Core schema exists for accounts, transactions, categories, rules, budgets, connections, and sync sessions
* Local development setup is documented

### Definition of Done

* A developer can clone the repo, configure environment variables, start the local stack with Docker Compose, run migrations, and start working without manual database edits

---

## Phase 2: Enable Banking Vertical Slice

### Objective

Prove the biggest external dependency early by implementing a narrow but real integration slice with Enable Banking.

### Scope

* JWT generation using app private key
* Enable Banking client module
* Fetch available ASPSPs
* Start authorization flow
* Handle redirect callback
* Exchange callback code for session
* Fetch linked accounts
* Fetch balances
* Fetch transactions
* Persist imported data idempotently

### Deliverables

* A user can start the bank linking flow from BurnRate
* BurnRate receives a valid callback from Enable Banking
* BurnRate stores linked accounts
* BurnRate imports balances and transactions into PostgreSQL
* Repeated imports do not duplicate transactions

### Definition of Done

* BurnRate successfully imports real data from at least one linked production account in restricted production mode

### Why This Phase Comes Early

Enable Banking is the biggest implementation risk.

If the integration, callback handling, restricted account linking, or transaction import behavior is more complex than expected, the team should discover that before building too much UI and application logic around assumptions.

---

## Phase 3: Core Product Loop

### Objective

Turn imported bank data into the first usable version of the product.

Detailed execution plan:

* See [Phase 3 Plan](./phase-3-plan.md)

### Scope

* Transaction list view
* Unknown transaction queue
* Manual categorization
* Rule creation from manual categorization
* Category management
* Budget management
* Summary calculations
* Web UI screens for summary, transactions, unknown queue, and budgets

### Deliverables

* Imported transactions are visible in the Web UI
* Uncategorized items are clearly separated
* The user can assign categories manually
* Rules can be saved and reused
* Monthly budgets can be defined
* BurnRate shows money left, monthly spending, burn rate, and runway

### Definition of Done

* A real user can connect an account, review transactions, categorize unknowns, set budgets, and understand their current financial position without using external tools

---

## Phase 4: Sync Automation

### Objective

Move from manual sync behavior to reliable background refresh.

### Scope

* Sync worker process
* Scheduled synchronization jobs
* Sync session tracking
* Error handling and retry policy
* Connection health visibility
* Safe re-sync behavior for existing accounts and transactions

### Deliverables

* Background sync can refresh account data without user interaction
* Sync results are logged in `sync_sessions`
* Failures are visible and diagnosable
* The system does not create duplicates during repeated refreshes
* The `sync-worker` runs as an explicit runtime service in the deployment model

### Definition of Done

* BurnRate can refresh linked accounts automatically on a schedule and recover cleanly from common sync failures

---

## Phase 5: Product Hardening

### Objective

Make the MVP reliable, understandable, and pleasant enough for regular personal use.

### Scope

* Better error messages and edge-case handling
* Empty-state UX
* Restricted-production UX for no-linked-account cases
* Basic observability and logs
* Integration and end-to-end tests for core flows
* Backup and restore considerations

### Deliverables

* The app explains common failure cases clearly
* Important actions and failures are logged
* The core happy path has test coverage
* The system is stable enough for day-to-day use by the owner

### Definition of Done

* BurnRate is dependable enough that the owner can use it as their normal monthly spending visibility tool

---

## Phase 6: Secondary Interface

### Objective

Expose stable backend capabilities through Telegram after the main Web UI product loop is already solid.

### Scope

* Summary command
* Budget status command
* Unknown transaction visibility
* Optional lightweight categorization actions

### Deliverables

* Telegram can surface the same summary information already available in the backend
* Telegram remains a secondary read-oriented client

### Definition of Done

* The owner can check BurnRate summaries from Telegram without needing Telegram-specific business logic

---

## Suggested Build Order Inside the Codebase

Within the implementation itself, the work should usually progress in this order:

1. Database and migrations
2. Domain models and repository interfaces
3. Enable Banking infrastructure client
4. Application services for sync and import
5. API endpoints
6. Web UI for the happy path
7. Categorization and budgeting logic
8. Background sync worker
9. Telegram integration

This keeps the architecture honest while still delivering vertical slices early.

---

## Milestone View

The roadmap can also be summarized as a set of milestones:

### Milestone A: Data In

BurnRate can connect to Enable Banking and import real balances and transactions.

### Milestone B: Data Understood

BurnRate can show imported transactions, classify unknowns, and store rules.

### Milestone C: Data Becomes Insight

BurnRate can manage budgets and calculate money left, burn rate, and runway.

### Milestone D: Data Stays Fresh

BurnRate can refresh automatically through the sync worker.

### Milestone E: Access Anywhere

BurnRate can expose stable summaries through Telegram.

---

## What Not To Do Early

The roadmap intentionally avoids these early investments:

* Multi-provider abstraction before the first provider works
* Multi-user design before the single-owner product loop works
* Advanced analytics before basic budgeting and categorization work
* Telegram-first flows before the Web UI and backend are stable
* Overly generic infrastructure before restricted production Enable Banking is proven

---

## Recommended Immediate Next Steps

If implementation starts now, the next practical tasks should be:

1. Finalize the schema and connection-related tables
2. Choose the backend stack and migration tool
3. Scaffold the Docker Compose runtime with `postgres`, `backend`, `web`, and `sync-worker`
4. Scaffold the backend project structure
5. Implement the Enable Banking client and JWT signing
6. Build the auth callback and first account import flow

That sequence gives BurnRate the fastest path to a real working vertical slice.
