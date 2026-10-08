# BurnRate Agent Guide

## Purpose

This file provides implementation guidance for coding agents working in this repository.

BurnRate is a personal finance product focused on spending visibility, budgets, and runway.

Before implementing features, read:

* `README.md`
* `docs/technical/architecture.md`
* `docs/technical/domain.md`
* `docs/technical/database/schema.md`
* `docs/technical/roadmap.md`
* `docs/technical/bank-integrations/enable-banking.md`

---

## Implementation Priorities

When making code changes, prioritize in this order:

1. Correctness
2. Clarity
3. Testability
4. Simplicity
5. Performance

Do not introduce clever abstractions unless they clearly reduce complexity.

Prefer straightforward code that is easy to change.

---

## Clean Code Expectations

Code should be:

* Small in scope
* Easy to read
* Easy to test
* Explicit in naming
* Low in side effects

Prefer:

* Short functions with one clear purpose
* Descriptive names over comments
* Early returns over deeply nested conditionals
* Composition over large procedural flows
* Explicit data transformations over hidden magic

Avoid:

* Long methods that mix orchestration and domain rules
* Repeated conditional logic spread across files
* Premature generic abstractions
* Hidden dependencies
* Unclear boolean flags without meaningful names

---

## SOLID Guidance

Use SOLID as a decision filter, not as a reason to over-engineer.

### Single Responsibility Principle

Each module should have one reason to change.

Examples:

* Enable Banking client code should not calculate budgets
* Controllers should not contain business rules
* Repositories should not decide product behavior

### Open/Closed Principle

Prefer extending behavior through clear seams rather than rewriting stable code.

Do not add plugin-style abstractions before the second real use case exists.

### Liskov Substitution Principle

If interfaces are introduced, implementations should behave consistently and not surprise callers.

### Interface Segregation Principle

Prefer small focused interfaces over large service contracts.

For example, a sync use case should not depend on a giant repository API if it only needs a few persistence operations.

### Dependency Inversion Principle

High-level application logic should depend on domain contracts or explicit interfaces, not directly on infrastructure details.

Examples:

* Application services should not be tightly coupled to HTTP request objects
* Domain logic should not depend on Enable Banking response shapes
* Core logic should not depend directly on SQL query builders

---

## TDD Expectations

Default to TDD when implementing behavior.

Use this cycle:

1. Write or update a failing test
2. Implement the smallest change that makes it pass
3. Refactor while keeping tests green

Tests should focus first on:

* Domain rules
* Application use cases
* Integration boundaries that are easy to regress

Prefer:

* Unit tests for domain and calculation logic
* Integration tests for database persistence
* Focused integration tests for Enable Banking flows
* End-to-end tests only for the most important user journeys

Avoid:

* Writing large amounts of code before adding tests
* Heavy mocking that hides broken behavior
* Brittle tests tied to internal implementation details

### Two failure modes worth naming

**A test double that agrees with the code cannot disagree with it.** Phase 8 hit
this four times. A fake bank client that returns its payload whatever window was
requested makes a wrong fetch window unobservable — three review passes found that
defect by reading and none by running it. A fake that only ever puts pending rows
where the implementation expects them encodes the same assumption as the code, so
no amount of mutation testing reaches the case. When a double answers a question
the code never asked, make it answer the request instead: a second double that is
strict about one dimension is cheaper than the bug.

**Mutation-check every test that passes on arrival.** A test written after the
code it covers, or one that goes green without a red step, has not been shown to
have teeth. Break the implementation deliberately and confirm the test fails.
Phase 8 found a real gap this way that no natural fixture could reach, and found
one test that passed *under* its own mutation because the fixture's dates happened
to work out against the month the suite ran in.

If TDD is not practical for a specific change, explain why in the final summary and still add the highest-value tests possible.

---

## Architecture Boundaries

Keep these boundaries intact:

* Presentation layer handles user interaction and display
* API layer translates requests into use cases
* Application layer orchestrates workflows
* Domain layer owns business meaning and calculations
* Infrastructure layer handles PostgreSQL, Enable Banking, and job execution

Do not let:

* Web or Telegram clients calculate financial metrics
* Enable Banking response models leak directly into domain logic
* SQL persistence concerns spread into domain code

---

## BurnRate-Specific Rules

For the MVP:

* The system is single-owner oriented
* The primary bank integration is Enable Banking
* The production model is restricted production mode with the owner's own linked accounts
* The primary interface is the Web UI
* Telegram is secondary

Do not generalize early into:

* Multi-provider banking abstractions
* Multi-tenant user models
* Ledger/accounting systems
* Advanced reporting platforms

---

## Database Rules

When implementing persistence:

* Use PostgreSQL
* Use migrations from the beginning
* Store money in exact numeric fields, never floating point
* Store timestamps in UTC
* Preserve Enable Banking identifiers for idempotent sync
* Keep integration tables separate from product tables

Derived metrics such as money left, burn rate, and runway should be computed from source data, not treated as primary stored truth.

---

## Enable Banking Rules

When implementing the bank integration:

* Keep Enable Banking code isolated in infrastructure
* Keep JWT signing and secret handling out of presentation code
* Treat restricted-production empty account results as a valid product state
* Make sync imports idempotent
* Preserve raw payloads where useful for debugging and parser evolution

Do not assume:

* Successful authorization always means accounts will be returned
* One bank flow behaves exactly like another
* Pending and booked transactions can be treated identically in all calculations

---

## Refactoring Rules

Refactor aggressively only when tests protect the change.

While refactoring:

* Preserve behavior first
* Remove duplication second
* Improve naming third
* Extract abstractions only when the new shape is clearly better

Do not perform broad architectural rewrites while implementing a small feature unless the feature is blocked without them.

---

## Documentation Rules

When implementation changes architecture, schema, or integration behavior:

* Update the relevant docs in the same change
* Keep docs aligned with actual implementation
* Prefer changing existing docs over creating duplicate explanations

Relevant docs usually include:

* `docs/technical/architecture.md`
* `docs/technical/domain.md`
* `docs/technical/database/schema.md`
* `docs/technical/bank-integrations/enable-banking.md`
* `docs/technical/roadmap.md`

---

## Final Standard

A good BurnRate implementation change should feel:

* Small but solid
* Simple but not naive
* Well-tested
* Aligned with the documented architecture
* Easy for the next person or agent to extend

---

## Agent skills

### Development pipeline

Features move from a roadmap phase through `/grill-with-docs` → `/to-spec` → `/to-tickets`, then `tdd` + `/code-review` per ticket, then a Definition-of-Done check, then `/distill-decisions`. See `docs/agents/pipeline.md`.

### Issue tracker

Issues and specs live as markdown files under `.scratch/<feature-slug>/`, versioned with the repo. They are scaffolding: once a feature ships, its durable decisions are promoted to `docs/adr/` and the directory is deleted. See `docs/agents/issue-tracker.md`.

### Domain docs

Single-context: one `GLOSSARY.md` at the root plus `docs/adr/`, both created lazily by `/domain-modeling`. See `docs/agents/domain.md`.
