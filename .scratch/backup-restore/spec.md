# Phase 13 (part 1): a backup you have restored

## Problem Statement

The owner's financial history exists in exactly one place. The database is 10 MB,
has never been copied, and lives on a single Docker volume on a single host with no
schedule, no script and no procedure.

It is not replaceable. The bank's fetch window is thirty days, which the product has
already proved the hard way: a 36-day worker outage in 2026 lost 30 August to 3
September permanently, and those days can never be fetched again. Everything older
than thirty days is unrecoverable by construction.

And a `pg_dump` on its own does not get the owner back to a working product. Two
secret artefacts live only on this host and are both in `.gitignore`:

* `.env` holds `BANK_TOKEN_ENCRYPTION_KEY`, without which every stored bank token is
  unreadable ciphertext; `AUTH_SECRET_KEY` and `AUTH_PASSWORD_HASH`, without which
  nobody can log in; plus `POSTGRES_PASSWORD` and `TELEGRAM_BOT_TOKEN`.
* `secrets/enable-banking.pem` signs every Enable Banking request. Without it the
  product cannot call the bank at all, so it cannot even re-authorize.

## Solution

A nightly backup set on this host, verified at the moment it is written, plus a
restore script that has actually been run.

Three decisions shape it:

* **The restore is the deliverable, not the dump.** An untested backup is a belief.
  The phase is not done when a file appears; it is done when a restore has
  reproduced the owner's data on a clean stack.
* **A backup set is the database plus the two secrets**, because any one of the
  three alone does not restore a working product.
* **Same host, for now.** This protects against a bad migration, a wrong `DELETE`,
  a dropped table and Postgres corruption. It does **not** protect against losing
  the host. That limit is accepted deliberately — "at least we have something" — and
  the one-line destination change is the upgrade path.

## User Stories

1. As the owner, I want the database copied every night without my doing anything,
   so that a mistake costs me a day rather than my history.
2. As the owner, I want each backup verified as readable the moment it is written, so
   that I am not keeping a directory of truncated files I believe in.
3. As the owner, I want the row counts recorded beside each dump, so that a restore
   can be checked against what was backed up rather than against my memory.
4. As the owner, I want `.env` and the Enable Banking signing key in the same backup
   set as the dump, so that a restore gives me a product that can log in and talk to
   the bank.
5. As the owner, I want old backups pruned automatically, so that the host does not
   fill up and silently stop backing up.
6. As the owner, I want backups stored outside the repository, so that
   `git clean -xdf` cannot delete them.
7. As the owner, I want a restore script that takes a backup set and a target
   database, so that restoring is one command rather than remembering `pg_restore`
   flags under pressure.
8. As the owner, I want the restore script to refuse to overwrite the live database
   unless I say so explicitly, so that the recovery tool is not itself a way to lose
   data.
9. As the owner, I want the restore procedure written down, so that the version of me
   who needs it is not the version who wrote it.
10. As the owner, I want a restore to have been performed at least once against a
    clean target, so that the first time it runs is not the day I need it.
11. As the owner, I want to know a restore reproduced the data, so that I can compare
    counts rather than trust an exit code.
12. As a future agent, I want the test suite to prove backup and restore round-trip,
    so that a change to either script cannot silently break recovery.
13. As a future agent, I want the suite to stay green on a machine with no running
    stack, so that an integration test does not become a reason to skip the suite.

## Implementation Decisions

* **Two shell scripts in a new `scripts/` directory**, not Python. They orchestrate
  `pg_dump`, `pg_restore` and `cp` through `docker compose exec`; wrapping that in
  Python would add a layer without adding a decision. Nothing in them is a financial
  rule, so no architectural boundary is involved.
* **A backup set is a timestamped directory** holding four files: the custom-format
  dump, a copy of `.env`, a copy of the Enable Banking private key, and a manifest.
* **The manifest records what was backed up**: UTC timestamp, the Alembic revision at
  the time, and a row count per product table. It is what a restore is checked
  against.
* **Verification happens at write time.** A dump that `pg_restore --list` cannot read
  is deleted and the run fails loudly, because keeping an unreadable dump is worse
  than having none — it converts a known gap into a false belief.
* **Secrets are copied in the clear.** On this host `.env` is already in the clear, so
  encrypting the copy adds no protection and adds a key that can be lost. The backup
  set directory is created with owner-only permissions. When a destination off this
  host is added, encryption becomes necessary and that is the moment for it.
* **Backups live outside the repository**, defaulting to `~/burnrate-backups`,
  overridable by environment variable. Inside the repo a gitignored directory would
  be destroyed by `git clean -xdf`, which is a realistic way to lose them.
* **Retention keeps the most recent sets** and prunes the rest, count-based rather
  than age-based so that a long gap in runs cannot prune everything that survives.
* **The restore script refuses the live database by default.** Restoring is itself
  destructive; it requires an explicit flag to target the database the stack uses.
* **Scheduling is a host `cron` entry**, not a container. A backup that lives inside
  the stack cannot run when the stack is the thing that is broken.
* **The dead-man's switch for the sync worker is out of scope** and parked by the
  owner. It is the open case from ADR-0013 and is a separate concern from copying
  data.

## Testing Decisions

**One seam, agreed with the owner**: an integration test that runs the real
`scripts/backup.sh` and `scripts/restore.sh` against a scratch database created
inside the Postgres container that already exists, and asserts the restored row
counts equal the manifest's.

* It is the highest seam available and the only one that tests the claim the phase
  makes. Unit-testing the retention arithmetic would test the wrapper, not the belief.
* It needs no new infrastructure: the target is a second database in the running
  container, created and dropped by the test. The live database is never written to.
* **It is marked `integration` and skips when the stack is not up**, so the existing
  531-test SQLite suite stays green on any machine. The marker is registered in
  `pyproject.toml`; this is the first test in the project that needs a running
  service, so the guard is part of the ticket rather than an afterthought.
* The round trip is asserted on **row counts per table plus the Alembic revision**,
  not on a dump checksum: a dump is allowed to differ byte for byte between runs, and
  what matters is that the data arrives.

Out of scope, deliberately: restoring onto a different Postgres major version, and
testing the cron schedule itself.
