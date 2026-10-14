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

The Web UI should remain a presentation client over the backend APIs, with no financial logic of its own. The line, so it stays checkable: if a result is compared against a constant, or displayed to the owner as a figure with a unit, it belongs in the domain; if it only ever becomes a pixel width or an arc length, it is presentation. So the gauges' 270° sweep and the amount-to-fraction conversions live in the UI, while every threshold, band and verdict is read from a backend status field. The dashboard's headline tone comes from `safe_to_spend_status`, its per-category verdicts from each budget row's `status`, and its savings verdict from `savings_status`, so the dashboard and the bot cannot disagree. The same line applies to the clock: a month's tense is a label rather than a financial rule, but a client deciding it against a month of its own disagrees with the backend for part of every month-end. So the backend decides it and names it — `safe_to_spend_status` carries `month_closed` or `month_not_started` — and no client compares months at all. Both of them used to, and two of the three readings were wrong; see `docs/adr/0002-safe-to-spend-today-definition.md`. The same rule covers which month a figure belongs to: every month-scoped read names the month on screen and the backend answers for it, including the budget list, whose rows carry a status read against that month rather than against today. A client that fetched the month's figures and the month's budgets by two different rules showed one month's total beside another month's rows; see `docs/adr/0005-budget-windows-are-month-granular.md`.

Which month is current is the same kind of answer, and it comes from the same place: the Web UI holds the selected month as `""` until the backend names one, and `summary.current_month` is what it adopts. There is no clock in `web/src` that produces a month. This costs a two-phase first load, because an omitted month is not one question: `/summary` answers for its own current month, while `/transactions`, `/transactions/uncategorized` and `.../count` answer for every month ever. So the summary is fetched first, its `current_month` becomes the selection, and the three ledger views are then scoped to it. A cleared month — which a native `<input type="month">` can always produce — re-enters that same path rather than falling back to a browser-side default, and because asking for the same month twice has to mean "ask again", the loader is keyed on a token every selection bumps rather than on the month alone. Without it the one month that could never be re-requested would be the unresolved one, which is what a failed opening summary leaves behind. For the same reason, nothing requests a ledger view before a month exists: an edit can land in that window, and the three views answer an omitted month with every transaction ever.

A payload is also only ever written for the month that is still selected. A background refresh closes over the filters of the render that started it, so it records the month it was started for and discards its own result if the owner has moved on; the loader keyed on the new month is already fetching that month's figures. A refresh that fails is reported twice, because the two facts are different: a toast says the edit it followed did land while the figures did not, and `summaryError` marks the figures left on screen once that toast has faded.

`web/` carries two test seams, both on Vitest. The first is `useBurnRateData` with `lib/api` faked, and it exists for concurrency rather than coverage: which state survives two responses landing out of order is not observable in a render. The second is page rendering through `renderToStaticMarkup`, with a page component's props supplied directly and assertions on the wording the owner would read — not a DOM-interaction seam, so there is no clicking and no effects, and a page that pulls data in an effect is exercised only through the states its props can reach. The two share one `SummaryDashboard` fixture via `fakeApi`'s `summaryFor`, rather than keeping two copies of a 22-field literal that would drift. Renderings outside a page component are still read by eye.

The Telegram bot runs as its own long-polling worker (`burnrate.telegram_bot`). It is a read-only presentation client: it dispatches chat commands to the same application services the API uses and formats their output, without implementing any financial logic of its own. `/summary` leads with Safe to Spend Today and reads both its colour and the month's tense from `safe_to_spend_status`, the same field the dashboard's headline tone and badge come from, so the two interfaces cannot disagree about the owner's position or about which side of today the month falls on. A month that has not started reports its budget and what is already committed to it, and omits the lines that describe progress — a usage bar, a daily pace and a month-end projection have nothing to describe before the month begins. Access is restricted to an allow-list of chat ids (`TELEGRAM_ALLOWED_CHAT_IDS`), matching the single-owner model.

Its polling loop treats every answer Telegram gives as survivable. Two failure shapes reach it and they are not the same type: a transport failure raises an `httpx.HTTPError`, while a request that completed and was *refused* raises a `TelegramAPIError` — a 429 flood limit, a 409 from a second poller, a 5xx on Telegram's side. Both are transient, so both back off and retry rather than ending the process, and a rejection that names a `retry_after` waits exactly that long instead of guessing. The distinction is load-bearing: the loop once caught only the transport case, so a single 429 on `getUpdates` propagated out of `main()` and killed the worker after fifteen hours of healthy polling. Nothing restarted it, because no compose service declared a restart policy; all of them now do, as the backstop for the crash that has not been thought of yet. Rejections are logged with their detail, since that first crash recorded no `retry_after` and left nothing to diagnose.

---

## Suggested Deployment Shape

For an initial self-hosted deployment, BurnRate can be shipped as:

* One backend service
* One sync worker
* One Telegram bot worker
* One Web UI service
* One PostgreSQL database

This keeps the first deployment model simple while leaving room to split services later if needed.

The Web UI service is also the only one published. Its nginx serves the SPA and proxies `/api/v1/` and `/enable_banking_items/` to the backend, so the browser only ever talks to the origin it loaded the page from and no request is cross-origin — which is why `APP_CORS_ORIGINS` is nearly inert and why the backend binds loopback. See `docs/adr/0004-the-web-origin-is-the-only-origin.md` for the trade-off and for the two headers that are load-bearing, and `docs/technical/deployment.md` for what a deployment has to get right.

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
* A service that resolves a civil date must take the instant from an injectable clock, because the month-end boundary is the only place the derivation is ever wrong and it is reachable only by choosing the instant. `civil_date` requires the instant rather than defaulting to the wall clock, so this is enforced by the signature; where the timezone comes from varies with what the service already holds, and both forms are recorded in `burnrate/clock.py`
* The resolved current month must be reported to clients rather than left for each one to derive, because only the backend knows `APP_TIMEZONE`
