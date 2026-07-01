# BurnRate

BurnRate is a self-hosted personal finance tool focused on a simple question:

> How much money do I have left, and how fast am I spending it?

Most finance apps try to become complete wealth dashboards, accounting tools, or investment trackers.

BurnRate is intentionally narrower.

It focuses on spending visibility, category budgets, and financial runway with as little user effort as possible.

The experience should feel more like checking the fuel level in a car than managing a spreadsheet.

## What BurnRate Does

BurnRate is designed to:

* Import bank transactions automatically
* Categorize transactions using reusable rules
* Surface uncategorized transactions quickly
* Show monthly budget consumption by category
* Estimate burn rate and savings runway
* Expose the same information through APIs, a Web UI, and Telegram

## MVP Summary

The first version of BurnRate should solve a narrow and practical problem well:

* Sync transactions from one or more bank accounts
* Categorize transactions automatically where possible
* Let users review unknown transactions quickly
* Show monthly budget status by category
* Estimate burn rate and financial runway
* Deliver this information through a Web UI, Telegram, and APIs

The first version should not attempt to become a complete accounting or reporting platform.

## Planned Interfaces

All product capabilities should be exposed through the same backend APIs.

Initial interfaces:

* Web UI
* Telegram bot

The Web UI should be the primary user experience.

## Phase 1 Stack

The initial implementation scaffold uses:

* Backend: `FastAPI`
* Database: `PostgreSQL`
* Migrations: `Alembic`
* Tests: `pytest`
* Runtime: `Docker Compose`

The `web` service is currently a lightweight placeholder so the deployment shape stays aligned with the architecture while the backend and integration work are built first.

## Documentation

* [Product Overview](./docs/product/overview.md)
* [MVP Scope](./docs/product/mvp.md)
* [Metric Definitions](./docs/product/metrics.md)
* [Architecture](./docs/technical/architecture.md)
* [Domain Model](./docs/technical/domain.md)
* [Technical Flows](./docs/technical/flows.md)
* [Enable Banking Integration](./docs/technical/bank-integrations/enable-banking.md)
* [Database Schema](./docs/technical/database/schema.md)
* [Deployment Model](./docs/technical/deployment.md)
* [Implementation Roadmap](./docs/technical/roadmap.md)
