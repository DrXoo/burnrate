# BurnRate Architecture

## Goal

BurnRate should be built as a small, modular system that keeps product logic centralized and delivery channels thin.

The architecture should optimize for:

* Self-hosted deployment
* Clear domain boundaries
* Low operational complexity
* Easy extension to new interfaces
* Safe handling of financial data

---

## High-Level Shape

BurnRate should follow an API-centered architecture:

1. A core backend owns business rules, persistence, synchronization, categorization, and calculations.
2. The Web UI consumes backend APIs as the primary user-facing client.
3. Telegram acts as a secondary client for quick actions and summaries.
4. External bank providers are integrated through dedicated synchronization adapters.

This keeps the product logic in one place and avoids duplicating behavior across clients.

---

## Layered Model

BurnRate should separate code by responsibility, not only by framework or process.

The main architectural layers should be:

1. Presentation layer
2. API layer
3. Application layer
4. Domain layer
5. Infrastructure layer

The important distinction is:

* A layer describes where code belongs logically
* A runtime component describes where code runs operationally

For example, the sync worker is not a separate business layer. It is a runtime component that executes application-layer synchronization use cases.

---

## Architectural Layers

### Presentation Layer

Responsibilities:

* Provide user-facing interaction through the Web UI and Telegram
* Capture user input and display results
* Present summaries, unknown queues, budgets, and runway clearly

This layer should contain presentation concerns only.

It should not implement financial rules, categorization behavior, or metric calculations.

---

### API Layer

Responsibilities:

* Expose application capabilities to clients
* Validate requests and enforce authentication
* Return stable response shapes for the Web UI and Telegram
* Translate transport-level requests into application use cases

The API layer is the boundary between clients and backend behavior.

---

### Application Layer

Responsibilities:

* Orchestrate business use cases
* Run synchronization workflows
* Apply categorization rules
* Manage unknown transaction review
* Calculate budget usage, burn rate, and runway
* Coordinate domain logic with persistence and external integrations

This layer should hold the use-case orchestration of the system.

---

### Domain Layer

Responsibilities:

* Represent accounts, transactions, categories, budgets, rules, and derived metrics
* Enforce domain invariants
* Keep financial definitions consistent across features
* Protect business meaning from transport or provider-specific concerns

This layer should remain independent from UI, HTTP, Telegram, and bank-provider payloads.

Metric *policy* -- the thresholds and bands a metric is judged by -- lives in
`burnrate/domain/metrics.py`: pure functions over primitives with no database
session and no ORM import. Services query and delegate to it, so a financial rule
is never read out of a React component or a SQL method. The queries, the
confidence-weighted projection blend and the fixed step projection stay in
`SummaryService`. See `docs/adr/0001-domain-module-for-metric-policy.md`.

---

### Infrastructure Layer

Responsibilities:

* Store accounts, balances, transactions, categories, rules, budgets, and sync state
* Support idempotent transaction imports
* Preserve audit-friendly source data where possible
* Execute background jobs and scheduled tasks
* Integrate with external systems such as bank providers

PostgreSQL should be the default database for the first version.

It fits the project well because BurnRate needs relational consistency, strong constraints, idempotent imports, and reliable aggregation queries for budgets, spending, and runway calculations.

The persistence model should start simple, but from the beginning it should support:

* Migrations
* Unique constraints on provider-owned identifiers where appropriate
* UTC timestamps
* Precise monetary values using fixed-point numeric types instead of floating-point storage

---

## Infrastructure Subareas

### Persistence

Responsibilities:

* Implement repositories and database access
* Persist domain entities and synchronization state
* Enforce database constraints and migrations

Persistence should remain a technical implementation detail behind application and domain behavior.

---

### Bank Integrations

Responsibilities:

* Communicate with Enable Banking
* Pull account, balance, and transaction data
* Normalize provider payloads into internal models
* Capture provider identifiers, checkpoints, and sync metadata

Provider-specific concerns should stay isolated from the core domain model.

---

### Job Execution

Responsibilities:

* Run scheduled sync jobs
* Trigger asynchronous processing when needed
* Isolate long-running sync work from request-response flows

Job execution is infrastructure, not a business layer.

---

## Suggested Request Flow

Example flow for transaction categorization:

1. A sync adapter imports new transactions from a provider.
2. The application layer normalizes and stores them.
3. The rule engine applies matching categorization rules.
4. Unmatched transactions are marked as unknown.
5. The Web UI displays the updated budget and unknown queue.

---

## Runtime Components

The first version can stay simple while still respecting the layered model.

Suggested runtime components:

* Backend API service
* Sync worker
* Telegram bot worker
* Web UI service
* PostgreSQL database

The backend API service should host the API layer and most application logic.

The sync worker should execute synchronization use cases and scheduled jobs, while reusing the same application and domain code as the API service.

The Web UI should remain a presentation client over the backend APIs, with no financial logic of its own. The line, so it stays checkable: if a result is compared against a constant, or displayed to the owner as a figure with a unit, it belongs in the domain; if it only ever becomes a pixel width or an arc length, it is presentation. So the gauges' 270° sweep and the amount-to-fraction conversions live in the UI, while every threshold, band and verdict is read from a backend status field. The dashboard's headline tone comes from `safe_to_spend_status`, its per-category verdicts from each budget row's `status`, and its savings verdict from `savings_status`, so the dashboard and the bot cannot disagree.

The Telegram bot runs as its own long-polling worker (`burnrate.telegram_bot`). It is a read-only presentation client: it dispatches chat commands to the same application services the API uses and formats their output, without implementing any financial logic of its own. Access is restricted to an allow-list of chat ids (`TELEGRAM_ALLOWED_CHAT_IDS`), matching the single-owner model.

---

## Suggested Deployment Shape

For an initial self-hosted deployment, BurnRate can be shipped as:

* One backend service
* One sync worker
* One Telegram bot worker
* One Web UI service
* One PostgreSQL database

This keeps the first deployment model simple while leaving room to split services later if needed.

---

## Design Constraints

The architecture should preserve the following constraints:

* Financial logic must have one source of truth
* Synchronization must be repeatable and idempotent
* Clients must not implement their own metric calculations
* Domain concepts must be defined independently of provider payloads
* Self-hosted operation should remain easy on modest hardware
* Monetary values must not use floating-point storage
* Timestamps must be stored in UTC, while civil dates ("today", "the current month") must be derived in the owner's own timezone, named by `APP_TIMEZONE` (an IANA name, default `UTC`) and resolved through the single `burnrate.clock.civil_date` helper
