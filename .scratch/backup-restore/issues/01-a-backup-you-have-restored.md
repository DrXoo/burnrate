# 01: A backup you have restored

**What to build:** the owner's database and the two secrets that make it usable are
copied to a timestamped backup set every night, each set is verified readable when it
is written, and a single command restores a chosen set into a target database. The
restore has been performed at least once against a clean target and the result
checked against the manifest, so the first run is not the day it is needed.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] `scripts/backup.sh` writes a timestamped backup set outside the repository,
      containing the custom-format dump, a copy of `.env`, a copy of the Enable
      Banking private key, and a manifest holding the UTC timestamp, the Alembic
      revision and a row count per product table
- [ ] The set directory and the secret copies are owner-readable only
- [ ] A dump that `pg_restore --list` cannot read fails the run loudly and is not
      left behind, because an unreadable dump kept is a false belief
- [ ] Retention keeps the most recent N sets by count and prunes older ones
- [ ] `scripts/restore.sh` takes a backup set and a target database and restores it,
      printing row counts so the result can be compared with the manifest
- [ ] `scripts/restore.sh` refuses to target the live database unless an explicit
      flag is passed
- [ ] An `integration`-marked test runs both scripts against a scratch database in
      the running Postgres container and asserts the restored row counts and Alembic
      revision match the manifest; it skips when the stack is not up, and the
      existing suite stays green with no stack
- [ ] The nightly schedule is installed as a host cron entry, not inside the stack
- [ ] The restore procedure is documented, including what a restore without
      `BANK_TOKEN_ENCRYPTION_KEY` or the signing key produces
- [ ] A restore has actually been run and its outcome recorded, and Phase 13's
      Definition of Done is checked in the roadmap against that run
