# BurnRate Enable Banking Integration

## Goal

This document explains how BurnRate should integrate with Enable Banking for the first version.

The intended setup is:

* Production environment
* Restricted production mode
* Only the owner's own linked bank accounts
* Account information access, not payment initiation

This is not a generic multi-user open banking product setup.

It is a personal deployment model centered on connecting the owner's own accounts safely and reliably.

---

## Integration Mode

BurnRate should use Enable Banking in restricted production mode.

This means:

* The application runs against the production Enable Banking environment
* The application is activated by linking specific bank accounts to it
* Only those linked accounts are returned by the API
* The app is meant for personal/internal usage, not general public onboarding

According to Enable Banking's FAQ, a restricted production app can still go through the authorization flow with an ASPSP, but the API only returns the accounts that were previously linked to the application.

For BurnRate, that is exactly the desired behavior.

---

## What BurnRate Needs From Enable Banking

BurnRate should rely on:

* One Enable Banking account in the Control Panel
* One registered API application
* One application private key
* One or more whitelisted redirect URLs
* A set of linked personal bank accounts in restricted production mode

BurnRate does not need dedicated TPP infrastructure for the first version.

It should rely on Enable Banking's default infrastructure and app-level JWT authentication.

---

## App Registration

The initial setup should follow this shape:

1. Sign in to the Enable Banking Control Panel.
2. Create an API application.
3. Select `Production`.
4. Use the default infrastructure that relies on Enable Banking authorization.
5. Generate the private key in the browser or provide your own public key.
6. Configure the redirect URL that BurnRate will use for the authorization callback.
7. Activate the application in restricted mode by linking the bank accounts that BurnRate should be allowed to access.

In production on the default infrastructure, Enable Banking currently requires additional application details such as description, privacy policy URL, terms of service URL, and a data protection email.

Even though BurnRate is intended for personal use, the project should assume these registration requirements exist.

---

## Credentials and Secrets

BurnRate should store the following configuration securely:

* `ENABLE_BANKING_APP_ID`
* `ENABLE_BANKING_PRIVATE_KEY`
* `ENABLE_BANKING_REDIRECT_URL`
* `ENABLE_BANKING_ENVIRONMENT=production`

The application ID is used as the JWT `kid`.

The private key is used to sign JWTs with `RS256` for every API request.

This private key should be treated as a long-lived secret and never exposed to the Web UI or Telegram layer.

---

## Runtime Authorization Flow

The normal BurnRate connection flow should be:

1. BurnRate requests the list of available ASPSPs for a country.
2. The user selects the bank to connect.
3. BurnRate calls Enable Banking's authorization start endpoint.
4. Enable Banking returns a redirect URL.
5. BurnRate sends the user to that URL.
6. The user authenticates with the bank and confirms consent.
7. The bank and Enable Banking redirect back to BurnRate with a `code`.
8. BurnRate exchanges the `code` for a session.
9. BurnRate uses that session to discover accessible accounts.
10. Enable Banking only returns accounts that were already linked to the restricted production application.

After the session is created, BurnRate can fetch balances and transactions for those accounts.

The connection flow is started from the Web UI ("Connect a bank"), which calls the authorization
start endpoint and sends the browser to the returned bank URL. Because the bank redirects the user's
browser to the callback, the callback endpoint responds with a **redirect back to the Web UI**
(`WEB_BASE_URL`) carrying a result, rather than returning JSON:

* `?connect=success&accounts=N&imported=M` when accounts were imported
* `?connect=empty` when authorization succeeded but no linked accounts were returned (restricted production)
* `?connect=error&message=...` when the callback could not be completed

The Web UI reads these parameters, shows a result banner, and refreshes connections and accounts.

---

## API Calls BurnRate Should Use

At minimum, BurnRate should support these Enable Banking operations:

* `GET /aspsps`
  To show available banks by country.
* `POST /auth`
  To begin the bank authorization and consent flow.
* `POST /sessions`
  To exchange the callback `code` for a session.
* `GET /accounts/{account_id}/balances`
  To read the latest balances.
* `GET /accounts/{account_id}/transactions`
  To import transaction history and refresh it later.
* `DELETE /sessions/{session_id}`
  To revoke or clean up sessions when needed.

BurnRate should send a JWT `Authorization` header with every request.

---

## Restricted Production Behavior

Restricted production mode has an important consequence for product behavior:

* A successful user authorization does not guarantee any accounts will be returned.
* If the authorized account is not one of the accounts previously linked to the application, the API can return an empty account list.

BurnRate should treat this as a known integration state, not as an unexpected backend failure.

The UI should explain the situation clearly, for example:

`This bank account is not linked to the Enable Banking application used by this BurnRate instance.`

This is especially important because the owner may authorize successfully at the bank and still see no usable accounts if the wrong account was used during consent.

---

## Recommended BurnRate Persistence

BurnRate should store Enable Banking integration data separately from product-level financial data.

Suggested integration records:

### Enable Banking Application Config

* App ID
* Redirect URL
* Environment
* Whether restricted production mode is enabled

### Bank Connection

Represents one bank authorization relationship.

Suggested fields:

* Internal connection id
* ASPSP name
* ASPSP country
* PSU type
* Enable Banking session id
* Session status
* Authorized at
* Last synced at

### External Account Mapping

Maps Enable Banking account identifiers to BurnRate accounts.

Suggested fields:

* Internal mapping id
* Connection id
* External account id
* Account hash if provided
* Local account id
* Last seen at

This separation keeps integration mechanics distinct from the core `Account` and `Transaction` domain model.

---

## Sync Strategy

For the first version, BurnRate should use a simple sync strategy:

1. Manual first connection through the Web UI
2. Full initial fetch of balances and transactions
3. Scheduled refresh through the sync worker
4. Idempotent upsert of accounts, balances, and transactions

BurnRate should assume that transaction imports may be paginated or refreshed incrementally over time, and it should preserve external identifiers needed for safe re-sync behavior.

### How Often The Scheduled Refresh Runs

`SYNC_CRON` is `0 11,20 * * *` — twice a day, at 12:00 and 21:00 Europe/Madrid in
winter. **This is a regulated ceiling and not a tuning parameter.**

PSD2's RTS, [Article 36(5)(b) of Commission Delegated Regulation (EU) 2018/389][rts],
limits account-information access **where the account holder is not actively requesting
it**. [EBA Q&A 2019_4631][qa] puts the number at "no more than four times in a 24-hour
period", "unless a higher frequency is agreed between the AISP and the ASPSP". A sync
spends one access per call per account, so the cadence and the number of accounts
together decide whether BurnRate is inside the rule.

It was `*/30 * * * *` — 48 runs a day — from Phase 1 until 2026-11-03, when Openbank
began refusing with `ASPSP_RATE_LIMIT_EXCEEDED` within an hour of being connected. ING
had served 37 runs the same day, which is ING declining to enforce a limit it may
enforce at any time, not evidence that the cadence was sound.

What the four are counted *against* — per consent, per account, or per account and
request type — is not settled by the Q&A, and this owner's measurements exclude the two
strict readings for Openbank. **Read
`docs/adr/0015-two-unattended-syncs-a-day.md` before changing this value**: it holds
the measurements, what remains unknown, and what would justify a different number.

An access the owner asked for, while present, is outside the budget. BurnRate does not
yet send the PSU-presence headers that mark a request as attended, so every call it
makes is unattended whoever triggered it — including a manual sync from the Web UI.

[rts]: https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32018R0389
[qa]: https://www.eba.europa.eu/single-rule-book-qa/qna/view/publicId/2019_4631

### One Fetch Window, One Call

BurnRate makes **one** transactions call per account, with no `transaction_status`, over a trailing 30-day window — the same window the sweep below is scoped to.

It used to make two, a default call for booked rows and a `PDNG` call for pending ones, because Enable Banking returns one status per call. The second call spent a third of the per-account access budget described above and never returned a row from either of this owner's banks. It was removed on 2026-11-03; the amendment to `docs/adr/0003-pending-spend-is-load-bearing.md` holds the measurement and its limits.

Pending transactions are still handled. A response's `pending` array is read whichever call produced it, and `SCHD` normalizes to pending, so a bank that volunteers a held or scheduled row on the ordinary call is stored and swept exactly as before. What a bank will no longer be *asked* for is holds it reports only on request — the way to discover such a bank is to make the call once and look, not to make it twice a day for every bank for ever.

That is a constraint, not three numbers that happen to agree. The sweep deletes a pending row the bank stopped reporting, and the *booked* call is the only thing that can bring its settled copy back — so the booked window has to cover at least the window the sweep judges. When the booked call ran from the first of the current month instead, it did not: for the first 30 days of every month the sweep judged days the booked call never re-asked about. A hold that pended on the 31st and booked overnight under that same date was deleted as absent and never re-imported, so the charge existed in neither status and the previous month was understated for good — the exact loss ADR-0003 calls self-healing. Re-importing a settled charge is idempotent and the volume is one owner's, so the cheap direction is to widen the booked call rather than narrow the sweep.

Anything that changes one of the three windows has to change all of them, which is why they are derived from a single value in the service rather than per call site. That value is `TRANSACTION_WINDOW`, and it is public because there is now a **fourth reader outside the integration**: baseline coverage.

A month is only trustworthy as baseline input if successful syncs asked about every one of its days, and "every one of its days" is this window's length — a run on day S asked about `[S - 30, S]`, so a month is covered only when the windows of its successful runs *union* to span it. Two runs 25 days apart cover a month between them although neither does alone. Widening this window therefore makes more months qualify as baseline input, and narrowing it makes fewer; it is no longer only a question of what gets fetched and swept. `BaselineService` imports the constant rather than restating 30, which is the same invariant this section already exists to protect.

Only a `success` session counts as coverage, and the status this excludes most importantly is `skipped`. An expired consent writes a `skipped` session per attempt and fetches nothing, so the gap it opens is papered over with an unbroken chain of session rows: anything counting rows rather than successes would read the months the owner was disconnected as fully covered, and build their baselines on months missing transactions outright.

### Pending Transaction Reconciliation

An upsert alone cannot keep the pending set honest: a hold the bank cancels simply stops appearing, and nothing in a later response says it is gone.

After a **fully successful** fetch for an account — both calls, every page — BurnRate deletes the pending rows the window reaches whose external identifier was absent from *every* response of that sync. This does two jobs:

* A cancelled hold stops counting as spend and leaves the review queue, instead of accumulating as a phantom forever.
* A hold that settles under a *different* identifier leaves no twin. The dedup key falls back to a content hash that includes the booking date, which a pending row lacks, so one purchase can hash differently once it books. The sweep removes the hold, because a transaction that has booked stops appearing in the pending response.

Five constraints make the sweep safe, and each will look like a bug without this note:

* **It is gated on a complete fetch.** A response truncated by a mid-pagination failure lists none of the holds on the pages that never arrived, so sweeping on it would delete live rows. The scheduled worker isolates a per-connection failure and commits the session anyway, so a partial sweep would persist.
* **It is gated on a legible payload, which is not the same thing.** A failure that raises is only one way to learn nothing: a 200 whose body is in none of the shapes BurnRate parses, and a 200 error envelope, both read as a successful fetch of zero rows, and an empty identifier set deletes every hold in the window. So every page must arrive in a recognised shape — a `transactions` list, a `transactions` object holding `booked` or `pending`, or those arrays at the top level — before the sweep runs. The shape test mirrors the extractor's branches one for one, and an object is not recognised merely by being an object: a bank nesting its rows under some other key reports its holds perfectly clearly in a dialect BurnRate does not speak, and reading that as an empty window sweeps live holds against the bank's own evidence that they are there. A legible response with no rows is a real claim and does sweep, which is what restricted production reporting an empty account means.
* **It is scoped to the account, and to the window's lower bound only.** A pending row older than the trailing window was never asked about, and its absence is not evidence that it is gone. There is deliberately no upper bound: a row the bank dates *after* today is inside the fetch's subject matter whatever date it carries, and an upper bound at today merely put scheduled payments out of reach — `SCHD` normalizes to pending and resolves its Effective Date to the day it falls due, so a standing order the owner cancelled before it was ever charged would have counted as that month's spend for ever.
* **It tests both calls, not just the `PDNG` one.** A pending row does not only arrive through the pending call: `SCHD` normalizes to pending status, and BurnRate merges a response's `pending` array whichever call returned it. Comparing against the pending response alone deletes a standing order the booked call just reported, and the next sync re-imports it — so the row oscillates, re-announcing itself as new and losing its category every other sync.
* **It skips rows the owner marked Ignored.** That flag records a decision the owner made; deleting the row would hand the transaction back to the unknown queue on the next import. `excluded_at` is deliberately not reused as a soft-delete marker for swept rows — it means Ignored, and overloading it would corrupt the term.

Deletion rather than flagging is safe because the trailing window makes a wrong deletion self-healing on the next sync — which holds only while the booked call covers that window, as above. See ADR-0003 for why pending spend is load-bearing in the first place.

### Which Array A Row Arrived In

A response can mark status per transaction or by which array a row sits in, and the two are not interchangeable. BurnRate flattens `booked` and `pending` into one list, so it carries each row's position alongside it: a row with no status of its own, or one BurnRate does not recognise, is stored as whatever its array implies. A flat `transactions` list has no array to imply anything, so those rows fall back to the status the *call* asked for — the `PDNG` request is the bank's own context for the answer, and a bank that uses the flat shape and marks status by response would otherwise have every hold stored as settled.

An explicit status still wins, because a `BOOK` row inside a `pending` array is the bank saying it has settled. Defaulting to booked regardless was wrong in three directions at once for a bank that marks by array: it under-reported pending spend, it fed a partial authorization to the fixed step projection — a 1.00 pre-authorization projecting 900.00 of rent as 1.00, the failure ADR-0003 exists to prevent — and it hid the row from the sweep, which filters on pending status, so it was never cleaned up either.

Status codes are matched case-insensitively. They are documented upper case and nothing enforces it, and a near miss is not a harmless one: a lower-case `pdng` in the booked array would read as money already settled, and a lower-case `cncl` as spend the owner never made.

Which shape the real bank sends is still unknown, so all of them are covered.

### Transient Error Retries

Enable Banking API calls are retried automatically on transient failures inside the infrastructure client (`EnableBankingClient`):

* Network/transport errors and timeouts are retried.
* HTTP `500`, `502`, `503`, and `504` responses are retried.
* Other `4xx` responses (auth, permission, not-found) are not retried, since a retry cannot fix them.

Retries use exponential backoff configured by `ENABLE_BANKING_MAX_RETRIES` and `ENABLE_BANKING_RETRY_BACKOFF_SECONDS`.

**`429` is not in that list, and it used to be.** It is not a transient failure: it is
`ASPSP_RATE_LIMIT_EXCEEDED`, meaning the unattended access budget described above is
spent. A quantity measured in hours or days cannot change across a backoff measured in
seconds, so the retry is certain to fail, and it is itself charged as an access.
Retrying therefore turned one over-budget call into four and pushed recovery further
into the next day. Measured on 2026-11-03: a single rate-limited `/balances` call cost
four accesses on its own retries.

That holds whichever way the four are counted, which is why it was fixed ahead of the
cadence question being settled.

### What A Spent Allowance Looks Like To A Client

A sync refused for rate limiting answers **503** with a structured body:

```json
{"detail": {"code": "bank_rate_limit", "message": "This bank's daily allowance ..."}}
```

Every other bank failure keeps the generic `502` and its prose detail, for the two
reasons `_bank_error` records: the body can carry provider detail that must not be
echoed, and a bank `401` reused as BurnRate's own would read as the owner's session
expiring and log them out.

**The discriminator is `code`, not the status, and that is forced rather than
preferred.** This endpoint already answers `429` from BurnRate's own
`enable_banking_sync` limiter when the owner clicks too fast, and the backend answers
`503` when no password is configured. Either status reused here would be ambiguous
with something that has a different remedy, so clients match on `code`.

The `message` is written by the backend and not composed by the client, per ADR-0002:
a state each client describes is a state each client can describe differently. It
promises no refill time, because banks differ on whether the window rolls or resets at
midnight, and a guessed time would be a fabricated promise. What it does say is that
nothing is lost — true, and the same self-healing property the sync-gap alert rests on,
since a later successful sync still reaches back across the fetch window.

A rate limit is logged by name rather than left as a bare traceback, because a `429`
and a `503` otherwise differ by one number while calling for opposite reactions — a
`503` means something is wrong, a `429` means wait. The bank's response body is not
logged, for the same reason the API layer refuses to echo it to a client.

The Telegram bot *does* retry its own `429`s, and that is not an inconsistency to
tidy up. Telegram's flood limit is measured in seconds and the response names a
`retry_after`, so waiting is both possible and instructed. A bank's is measured in
days and names nothing. Same status code, opposite correct behaviour — see
`docs/technical/architecture.md` for the crash that made the Telegram case
load-bearing.

### Expired Or Inactive Sessions

Before a scheduled or manual re-sync, BurnRate fetches the Enable Banking session and checks its status.

If the session is no longer `AUTHORIZED` (for example `EXPIRED`, `REVOKED`, or `CANCELLED`):

* BurnRate does not attempt to fetch balances or transactions.
* The connection is marked inactive so the background worker stops retrying a doomed sync every cycle.
* A `sync_session` row is recorded with status `skipped` and an explanatory `error_summary`.
* The connection must be re-authorized through the Web UI to resume syncing.

---

## Responsibilities by Layer

### Presentation Layer

Responsibilities:

* Let the owner choose a bank
* Redirect to the authorization URL
* Show connection status and linked account results
* Explain restricted-mode empty account results clearly

### API Layer

Responsibilities:

* Start the authorization flow
* Receive the callback
* Expose connection and sync endpoints to the Web UI

### Application Layer

Responsibilities:

* Build the authorization request
* Exchange callback code for session
* Persist integration metadata
* Trigger initial and recurring sync flows

### Infrastructure Layer

Responsibilities:

* Generate JWT-authenticated requests
* Call Enable Banking endpoints
* Normalize accounts, balances, and transactions
* Handle provider-specific response details

---

## Practical BurnRate Assumptions

For the MVP, BurnRate should assume:

* There is one owner of the installation
* The owner connects only their own bank accounts
* All supported accounts are pre-linked in restricted production mode
* Bank access is initiated from the Web UI, not Telegram
* Telegram is read-oriented and secondary

This keeps the first version aligned with the actual product goal instead of drifting into a multi-tenant onboarding design.

---

## Open Implementation Questions

These are still worth deciding at implementation time:

* Should BurnRate support multiple bank connections from day one, or only one connection first?
* Which callback state data should be persisted to protect against replay or mismatched redirects?
* How should the UI distinguish `authorization succeeded but no linked accounts were returned` from `authorization failed`?
