# BurnRate MVP Scope

## MVP v1 Scope

The first version of BurnRate should solve a narrow and practical problem well:

* Sync transactions from one or more bank accounts
* Categorize transactions automatically where possible
* Let users review unknown transactions quickly
* Show monthly budget status by category
* Estimate burn rate and financial runway
* Deliver this information through a Web UI, Telegram, and APIs

The first version should NOT attempt to support:

* Complex multi-currency workflows
* Joint-account reconciliation logic
* Invoice, tax, or bookkeeping workflows
* Investment performance tracking
* Advanced forecasting models
* Full desktop-style financial reporting

---

## MVP Features

### Bank Synchronization

Import transactions automatically from supported Open Banking providers.

Initial target:

* Enable Banking
* ING

Future:

* Any PSD2/Open Banking compatible institution

---

### Transaction Storage

Store transactions locally.

Required fields:

* Date
* Amount
* Description
* Account
* Category

---

### Rule Engine

Users can create categorization rules.

Example:

"MERCADONA" -> Food

"REPSOL" -> Car

"NETFLIX" -> Subscriptions

Rules are automatically applied to future transactions.

---

### Unknown Queue

Transactions that cannot be categorized automatically are placed into an Unknown queue.

The user can review and categorize them manually.

Optional:

Create permanent rule from classification.

---

### Budget Management

Users define monthly budgets.

Example:

Food: 300EUR

Transport: 100EUR

Health: 250EUR

Entertainment: 50EUR

BurnRate continuously calculates remaining budget.

---

### Burn Rate Calculation

Calculate:

* Daily spending average
* Monthly spending projection
* Savings consumption rate
* Estimated financial runway

For the authoritative definitions, including the two forms of runway and why the
deficit-based form does not apply to every user, see
`docs/product/metrics.md`.

---

### Web UI

Primary user interface.

The main product experience should be delivered through a simple Web UI focused on:

* Current balance visibility
* Monthly spending overview
* Budget status by category
* Unknown transaction review
* Burn rate and runway summary

The Web UI should be fast to scan, mobile-friendly, and simpler than a traditional budgeting dashboard.

---

### Telegram Integration

Secondary interface for quick access and lightweight interaction.

Commands:

/summary

/unknown

/budgets

/categorize

/runway

/sync

---

## Example User Flow

The ideal first-run experience should be simple:

1. The user connects a bank provider and imports transactions.
2. BurnRate applies existing categorization rules automatically.
3. Uncategorized transactions appear in the Unknown queue.
4. The user classifies unknown items and optionally saves new rules.
5. BurnRate updates monthly category budgets and remaining budget instantly.
6. The user checks `/summary` or `/runway` to understand current financial status.

This flow should be faster than maintaining a spreadsheet and simpler than configuring a traditional budgeting app.

---

## Success Criteria

A user should be able to answer the following questions in under 10 seconds:

* How much can I spend today without putting the month at risk?
* How much money do I have left this month?
* What category is consuming the most budget?
* How many uncategorized transactions exist?
* How many months of expenses do my savings cover?
* Am I spending above or below my target?

If BurnRate can answer these reliably, the project is successful.

---

## Status

MVP v1 as scoped above is delivered, with one exception: financial runway was
never implemented. See `docs/technical/roadmap.md` for the current plan, the
record of that gap, and the redefinition of the metric.
