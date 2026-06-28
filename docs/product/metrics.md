# BurnRate Metric Definitions

To keep the product consistent, BurnRate should use clear definitions for the core metrics it exposes.

## Money Left

"Money left" means the amount of budget still available for the current month after subtracting categorized spending from the user-defined monthly budgets.

This is a budgeting metric, not simply the raw bank balance.

---

## Current Balance

"Current balance" means the latest known balance across the accounts the user has chosen to include in BurnRate.

This value should reflect imported account balances when available.

If balances are not available from the provider, BurnRate may estimate them from historical data, but the UI should make that clear.

---

## Monthly Spending

"Monthly spending" means the sum of all expense transactions during the current calendar month across included accounts.

Refunds, transfers, and income should not be counted as spending.

---

## Burn Rate

"Burn rate" means the average rate at which money is being spent during the current month.

This should usually be expressed as:

* Daily average spending
* Projected month-end spending

---

## Runway

"Runway" means how long the user can continue sustaining their current deficit before their designated savings are exhausted.

This metric should only use savings accounts or balances the user explicitly marks as available for runway calculations.

Example:

* Savings available for runway: 10,000EUR
* Average monthly deficit: 500EUR
* Estimated runway: 20 months
