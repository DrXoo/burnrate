# BurnRate Technical Flows

## Goal

This document describes the main runtime flows of BurnRate in a diagram-oriented format.

The goal is to make the architecture easier to reason about by showing how the main components collaborate during common operations.

---

## Flow 1: Bank Synchronization

This flow shows how BurnRate imports accounts, balances, and transactions from Enable Banking.

```mermaid
sequenceDiagram
    participant Scheduler as Scheduler / Trigger
    participant Worker as Sync Worker
    participant App as Application Layer
    participant Bank as Enable Banking Adapter
    participant DB as PostgreSQL

    Scheduler->>Worker: Start sync job
    Worker->>App: Run sync use case
    App->>Bank: Request latest account and transaction data
    Bank-->>App: Normalized provider payloads
    App->>DB: Upsert accounts and balances
    App->>DB: Import or update transactions idempotently
    App->>DB: Store sync session metadata
    App-->>Worker: Sync completed
```

Key points:

* The worker runs the sync, but the business flow lives in the application layer.
* Enable Banking remains behind an adapter boundary.
* Imports must be idempotent so repeated syncs do not duplicate transactions.

---

## Flow 2: Automatic Categorization

This flow shows how imported transactions are categorized using stored rules.

```mermaid
sequenceDiagram
    participant Worker as Sync Worker
    participant App as Application Layer
    participant Domain as Domain Rules
    participant DB as PostgreSQL

    Worker->>App: Process imported transactions
    App->>DB: Load active categorization rules
    App->>Domain: Evaluate rules against transaction text
    Domain-->>App: Matching category or no match
    App->>DB: Save category and matched rule
    App->>DB: Mark unmatched transactions as unknown
```

Key points:

* Rules should match only transaction naming fields such as description or merchant text.
* Matching behavior belongs to application and domain logic, not to the bank integration.
* Unknown transactions remain visible for later user review.

---

## Flow 3: Manual Categorization From Web UI

This flow shows how a user reviews an unknown transaction and optionally creates a reusable rule.

```mermaid
sequenceDiagram
    participant User as User
    participant Web as Web UI
    participant API as API Layer
    participant App as Application Layer
    participant DB as PostgreSQL

    User->>Web: Open unknown transactions
    Web->>API: Request unknown queue
    API->>App: Load unknown transactions
    App->>DB: Query unknown transactions
    DB-->>App: Unknown transactions
    App-->>API: Queue data
    API-->>Web: Queue response
    User->>Web: Assign category and save rule
    Web->>API: Submit categorization command
    API->>App: Categorize transaction
    App->>DB: Update transaction category
    App->>DB: Optionally create new rule
    API-->>Web: Updated result
```

Key points:

* The Web UI stays thin and relies on backend APIs.
* Manual categorization can improve future automation by generating a rule.
* The unknown queue is a normal product workflow, not an error state.

---

## Flow 4: Summary Generation

This flow shows how BurnRate assembles the main budget and runway summary for a client.

```mermaid
sequenceDiagram
    participant Client as Web UI / Telegram
    participant API as API Layer
    participant App as Application Layer
    participant Domain as Domain Calculations
    participant DB as PostgreSQL

    Client->>API: Request summary
    API->>App: Build summary use case
    App->>DB: Load balances, budgets, transactions, and rules context
    DB-->>App: Source data
    App->>Domain: Calculate spending, money left, burn rate, and runway
    Domain-->>App: Derived metrics
    App-->>API: Summary payload
    API-->>Client: Renderable summary
```

Key points:

* Clients should never calculate financial metrics themselves.
* The backend owns the definitions of spending, money left, burn rate, and runway.
* Web UI and Telegram should consume the same summary capabilities.

---

## Flow 5: Layer and Runtime Relationship

This diagram shows the difference between logical layers and deployed components.

```mermaid
flowchart TD
    subgraph Clients
        WEB[Web UI]
        TG[Telegram]
    end

    subgraph Backend["Backend API Service"]
        API[API Layer]
        APP[Application Layer]
        DOM[Domain Layer]
    end

    subgraph Worker["Sync Worker"]
        JOB[Job Runner]
        APP2[Application Layer]
        DOM2[Domain Layer]
    end

    subgraph Infra["Infrastructure"]
        BANK[Enable Banking Adapter]
        DB[(PostgreSQL)]
    end

    WEB --> API
    TG --> API
    API --> APP
    APP --> DOM
    APP --> BANK
    APP --> DB
    JOB --> APP2
    APP2 --> DOM2
    APP2 --> BANK
    APP2 --> DB
```

Key points:

* `Presentation`, `API`, `Application`, and `Domain` are logical layers.
* `Backend API Service` and `Sync Worker` are runtime components that reuse those layers.
* The bank adapter and PostgreSQL live in infrastructure.
