# BurnRate Backend

This directory contains the FastAPI backend, Alembic migrations, and the sync worker entrypoint for BurnRate.

## Tests

Run pytest from this directory, with the `dev` extra installed:

```
pytest
```

Not from the repository root. `Settings` loads `env_file=".env"` relative to the
working directory, so a run started one level up reads the deployment `.env` instead
of the test defaults: `ENABLE_BANKING_PRIVATE_KEY_PATH` then points at the container's
`/run/secrets/enable-banking.pem`, and `test_enable_banking_callback_stays_public`
fails with a `FileNotFoundError` that has nothing to do with the code under test.
