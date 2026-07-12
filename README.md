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

## Access & Login

BurnRate is single-user and gated by a password. Every API endpoint except the
health probe, the login endpoints, and the bank OAuth callback requires a valid
session, and the backend **fails closed**: until you configure a password it
refuses all protected requests with `503`.

Set it up once:

1. Generate the credentials (a hashed password and a cookie-signing key):

   ```
   docker compose run --rm backend python -m burnrate.generate_auth_secrets
   ```

   It prompts for a password and prints `AUTH_PASSWORD_HASH=…` and
   `AUTH_SECRET_KEY=…`.

2. Paste both lines into your `.env`, then restart: `docker compose up -d`.

   > ⚠️ Docker Compose interpolates `$` in `.env` values, and the Argon2 hash is
   > full of `$`. In the `.env` loaded by Compose, **double every `$`** in
   > `AUTH_PASSWORD_HASH` (e.g. `$$argon2id$$v=19$$m=65536,...`). The generator
   > prints a ready-to-paste compose-escaped line. If login always says the
   > password is wrong, this is almost certainly why — check
   > `docker compose exec backend printenv AUTH_PASSWORD_HASH` against your `.env`.

3. Open the Web UI and sign in with the password you chose.

Notes:

* The password is never stored — only its Argon2 hash lives in `.env`.
* Sessions are HttpOnly, `SameSite=Strict` cookies that expire after
  `AUTH_SESSION_MAX_AGE` (default 7 days) and slide forward while you use the app.
* Keep `AUTH_COOKIE_SECURE=true` in production (HTTPS). Set it to `false` only for
  local `http://localhost` development, otherwise the browser drops the cookie.
* Repeated wrong passwords lock a client for `AUTH_LOGIN_LOCKOUT_SECONDS`.
* The interactive API docs (`/docs`, `/openapi.json`) are only served when
  `APP_ENV=development`.

## Telegram Bot

BurnRate ships a read-only Telegram bot as a secondary interface. It runs as its
own `telegram-bot` worker and reuses the same backend services as the Web UI, so
it never computes metrics on its own.

To enable it:

1. Create a bot with [@BotFather](https://t.me/BotFather) and copy the token into `TELEGRAM_BOT_TOKEN`.
2. Message the bot once and check `docker compose logs telegram-bot` for your chat id.
3. Add that id to `TELEGRAM_ALLOWED_CHAT_IDS` (comma-separated for more than one) and restart the worker.

Messages from any chat id not on the allow-list are ignored. Available commands:

* `/summary [YYYY-MM]` — money left, spending, burn rate, and runway
* `/budgets [YYYY-MM]` — budget status per category
* `/unknown` — transactions still waiting to be categorized
* `/help` — list commands

Leaving `TELEGRAM_BOT_TOKEN` empty keeps the bot disabled.

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
