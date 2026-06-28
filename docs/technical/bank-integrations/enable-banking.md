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

* How should BurnRate refresh expired or inactive sessions?
* Should BurnRate support multiple bank connections from day one, or only one connection first?
* Which callback state data should be persisted to protect against replay or mismatched redirects?
* How should the UI distinguish `authorization succeeded but no linked accounts were returned` from `authorization failed`?
