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
* Tests: `pytest` for the backend, `Vitest` for `web/` (`npm test`)
* Runtime: `Docker Compose`

The `web` service is a React single-page app served by nginx, which proxies `/api/v1` to the backend. It is a presentation client with no financial logic of its own: every threshold, verdict and month is read from a backend field.

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

## Data at Rest

The database holds your full financial history, so it is treated as sensitive:

* **Postgres is not published to the host.** It is reachable only by the app over
  the Docker network. To inspect it, go through the container:
  `docker compose exec postgres psql -U burnrate -d burnrate`.
* **Use a strong `POSTGRES_PASSWORD`.** Note it only applies when the volume is
  first created; to rotate on an existing database, run
  `ALTER USER burnrate WITH PASSWORD '<new>';` then update both
  `POSTGRES_PASSWORD` and the password inside `DATABASE_URL`.
* **Bank session tokens are encrypted at rest** with `BANK_TOKEN_ENCRYPTION_KEY`
  (Fernet), so a stolen dump or backup yields no usable bank access. The key is
  produced by `python -m burnrate.generate_auth_secrets`.

  > ⚠️ **Back up `BANK_TOKEN_ENCRYPTION_KEY`.** Lose it and the stored tokens
  > cannot be decrypted — you would have to reconnect the bank. Rows written
  > before this was introduced are read as plaintext until
  > `alembic upgrade head` rewrites them.

Avoid `$` in `POSTGRES_PASSWORD` (docker compose interpolates it) and in the
password inside `DATABASE_URL` (URL-reserved characters need escaping).

## Backup and Restore

Your history is not replaceable. The bank only serves a **30-day** fetch window, so
anything older than that cannot be re-imported — a 36-day worker outage in 2026 lost
30 August to 3 September for good.

### What a backup set is

`scripts/backup.sh` writes a timestamped directory to `~/burnrate-backups`
(override with `BURNRATE_BACKUP_DIR`) holding **three artefacts and a manifest**,
because the database alone does not restore a working product:

| File | Why it is in the set |
|---|---|
| `burnrate.dump` | the data, in `pg_dump` custom format |
| `env` | a copy of `.env`. Holds `BANK_TOKEN_ENCRYPTION_KEY`, without which every restored bank token is unreadable ciphertext, and `AUTH_SECRET_KEY` / `AUTH_PASSWORD_HASH`, without which nobody can log in |
| `enable-banking.pem` | signs every request to the bank. Without it the product cannot call Enable Banking at all, so it cannot even re-authorize |
| `manifest.txt` | the Alembic revision and an exact row count per table, which is what a restore is checked against |

Every dump is verified readable the moment it is written and the set is deleted if
it is not, because a dump nobody has read is a belief rather than a backup. The row
counts are taken on both sides of the dump and have to agree, so the manifest never
describes a database the dump does not contain.

Retention keeps the most recent 14 sets (`BURNRATE_BACKUP_RETENTION`, at least 1).
It matches timestamped set names only, so anything else you keep in that directory
is neither counted nor deleted.

It runs nightly from a host `cron` entry at 03:30, not from inside the stack — a
backup that lives in the stack cannot run when the stack is what is broken:

```
MAILTO=""
30 3 * * * mkdir -p $HOME/burnrate-backups && cd /home/bots/burnrate && ./scripts/backup.sh >> $HOME/burnrate-backups/backup.log 2>&1
```

The `mkdir` is not redundant: the log redirect is evaluated before the script runs,
so on a host where the directory does not exist yet cron would fail on the redirect
and never reach the backup.

To check a set that has been on disk for months, without restoring it:

```bash
./scripts/verify-dump.sh ~/burnrate-backups/<set>/burnrate.dump
```

It never connects to a database and never writes, so it is safe on any set at any
time. Exit **1** means the dump is unreadable; exit **3** means it could not be
checked at all, usually because the stack is not up — which is exactly the situation
where a tool that conflated the two would tell you an intact backup was corrupt.

### Restoring

```bash
./scripts/restore.sh ~/burnrate-backups/<set> --database burnrate_check
```

It prints the row counts it restored, so compare them with the set's
`manifest.txt`. The live database is **refused** unless you pass `--allow-live`;
restoring is destructive and overwrites everything the stack is using. "Live" means
whatever `POSTGRES_DB` is in `.env`, read from the file and never from the
environment — a guard an exported variable can answer is one a drill can disarm.

A full recovery onto a clean host is three steps, and the first two are manual
because they are secrets:

1. Copy the set's `env` back to `.env` and its `enable-banking.pem` back to
   `secrets/enable-banking.pem`.
2. Bring up Postgres (`docker compose up -d postgres`).
3. `./scripts/restore.sh <set> --database <the POSTGRES_DB from that env> --allow-live`,
   then start the rest of the stack.

Skip step 1 and you get a database that holds your history and nothing that can
read it: the login fails on a different `AUTH_SECRET_KEY`, and the bank tokens raise
*"Could not decrypt a stored bank token"* and have to be reconnected from scratch.

### Exercised on 2026-11-03

Not a procedure nobody has run. A set was taken, restored into a scratch database,
and all ten tables matched the manifest row for row (624 transactions, 4,169 sync
sessions). All three stored bank sessions — including the active one, which expires
2027-01-12 — decrypted using the key from the set's own `env` copy, which is the part
of a recovery that is easiest to assume and worst to get wrong.

`backend/tests/test_backup_restore.py` keeps it honest: it runs the real scripts
against a scratch database on every test run, and skips when the stack is down.
Two rules in these scripts have no automated test and are checked by hand, because
the only way to make either one the sole cause of a failing test is to let that test
restore over the live database or race it: the `--snapshot`-free agreement of the row
counts across the dump, and the cleanup trap's exit status on a signal.

### What this does not protect against

Backups are on **this host**. That covers a bad migration, a wrong `DELETE`, a
dropped table and Postgres corruption. It does **not** cover losing the host. The
upgrade is a destination off it, and the only thing that changes is
`BURNRATE_BACKUP_DIR` — plus encrypting the secret copies, which is unnecessary here
only because `.env` already sits in the clear beside them.

## Telegram Bot

BurnRate ships a read-only Telegram bot as a secondary interface. It runs as its
own `telegram-bot` worker and reuses the same backend services as the Web UI, so
it never computes metrics on its own.

To enable it:

1. Create a bot with [@BotFather](https://t.me/BotFather) and copy the token into `TELEGRAM_BOT_TOKEN`.
2. Message the bot once and check `docker compose logs telegram-bot` for your chat id.
3. Add that id to `TELEGRAM_ALLOWED_CHAT_IDS` (comma-separated for more than one) and restart the worker.

Messages from any chat id not on the allow-list are ignored. Available commands:

* `/summary [YYYY-MM]` — what you can spend today, then balance, spending, budget, and burn rate
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
