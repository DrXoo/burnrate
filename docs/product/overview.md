# BurnRate Product Overview

## Vision

Most personal finance applications focus on wealth tracking, investments, assets, liabilities, and long-term financial analysis.

BurnRate focuses on a much simpler question:

> How much money do I have left, and how fast am I spending it?

The goal is not to become an accounting platform or a personal ERP.

The goal is to provide a clear, real-time understanding of spending, budgets, and financial runway with as little user effort as possible.

BurnRate should feel more like checking fuel level in a car than managing a spreadsheet.

---

## Problem Statement

Most people do not struggle because they lack financial data.

They struggle because they lack financial visibility.

Banking apps show transactions.
Budgeting apps require manual categorization.
Financial platforms overwhelm users with charts, assets, net worth calculations, and investment tracking.

Users need answers to simple questions:

* How much money do I have available right now?
* How much have I spent this month?
* Which categories are consuming my budget?
* How many days can I continue spending at this rate?
* Am I burning through my savings too quickly?

BurnRate exists to answer these questions automatically.

---

## Core Principles

### Automation First

The user should not spend time categorizing transactions manually.

The system should learn from previous decisions and continuously improve categorization accuracy through rules.

---

### Budget Visibility

Budgets are first-class citizens.

Every screen should help users understand:

* Budget assigned
* Budget consumed
* Budget remaining

---

### Simplicity Over Features

If a feature does not help answer:

> "How much money do I have left?"

it probably does not belong in BurnRate.

---

### Self Hosted

Users should own their financial data.

BurnRate should run locally on a Raspberry Pi, Mini PC, Home Server, NAS, or VPS.

No cloud dependency should be required.

---

### API Driven

All functionality should be accessible through APIs.

The Web UI, Telegram Bot, and future clients should consume the same backend APIs.

---

## Target Users

### Primary

**A salaried person who does not want to overspend.**

Income is regular and roughly predictable. The problem is not knowing whether
they can afford their life; it is drifting past what they intended to spend
without noticing until the month is over.

For this user the valuable information is the daily allowance and the deviation
from their own normal — not the absolute levels, which are stable and therefore
carry little information.

This narrowing is deliberate. It decides which metric leads the product and in
what order features are built; see `docs/technical/roadmap.md`.

### Also served

These users are served by the same feature set without changing its priorities:

* Individuals tracking monthly spending
* Families managing household budgets
* People trying to reduce expenses
* Users who want financial awareness without financial complexity

### Not currently optimized for

* People living from savings while unemployed — the deficit runway metric exists
  for this case, but the product does not lead with it
* Freelancers with irregular income — the monthly budgeting model assumes
  predictable income and would need rework to serve them well

---

## Non Goals

BurnRate is NOT:

* An accounting platform
* An invoicing platform
* An investment tracker
* A crypto portfolio manager
* A tax management solution
* A net-worth dashboard

Those problems are already solved by other products.
