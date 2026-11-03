# BurnRate Implementation Roadmap

## Goal

What has shipped, what is next, in what order, and the exit criterion for each
phase.

**Phase numbers are names, not an order.** They are referenced by ADRs, commits and
tests, so they are never renumbered. The order of what remains is the table below,
and it was re-decided on 2026-11-03.

## How to read this

This document holds **the plan and the measured facts a plan can be wrong about**.
It does not hold the reasoning behind decisions already taken — that lives in
`docs/adr/`, one file per decision, and in the commit history. When a section here
and an ADR disagree, the ADR wins and this file is stale.

It was cut from 1292 lines to this on 2026-11-03. What was removed was
per-phase retrospective prose: gap archaeology, corrections of corrections, and the
argument for decisions that are now ADR-0008 through ADR-0014. What was kept is
anything that would be re-derived at cost, which is mostly **numbers from the live
database**.

---

## Order of what remains

| # | Phase | Why here | Size |
|---|---|---|---|
| ~~1~~ | ~~**13 — Keep the data**~~ | **the backup half shipped 2026-11-03.** The dead-man's switch is parked | done |
| 2 | **11 — "How much do I actually have?"** | the owner says **most of their money sits in accounts it cannot see**, so every balance-derived figure is confidently wrong, not merely incomplete | medium |
| 3 | **14 — "When can I buy it?"** | the first forward-looking thing in the product, and with a salary back its ETA half is a real question again rather than `never` | medium |
| 4 | **10 — "Tell me, don't make me look"** | retention, and after 11 and 14 it finally has something to say | medium |
| 5 | **9b — Commitments** | inverted from detection to confirmation; the detection it was scoped as cannot be built on this data | small |
| 6 | **12 — AI assistance** | narrowed to the categorization copilot and to wording. No dependencies; promote freely | medium |

Act I (Phases 1-7) and Phases 8 and 9a have shipped. Phase 9b is the only part of a
shipped phase still open.

---

## Where the product is

### Act I — shipped

Organized around **technical risk**: prove the Enable Banking integration before
building product on assumptions. That was the right axis and it worked.

| Phase | Scope | Status |
|---|---|---|
| 1 | FastAPI, PostgreSQL, Alembic, Docker Compose, core schema | Shipped |
| 2 | Enable Banking vertical slice: JWT signing, auth flow, callback, idempotent import | Shipped |
| 3 | Core product loop: transactions, unknown queue, rules, categories, budgets, summary | Shipped, **minus runway** — see Phase 11 |
| 4 | Sync automation: `sync-worker`, APScheduler cron, sync sessions, retry | Shipped |
| 5 | Product hardening: auth, encryption at rest, observability, test coverage | Shipped |
| 6 | Secondary interface: read-only Telegram bot | Shipped |
| 7 | Operational resilience | **Not started** — re-scoped as Phase 13, now first |

Phase 3's gap is the one that matters: its Definition of Done promised *"money left,
monthly spending, burn rate, and runway"*, and **runway never shipped** — neither the
calculation nor the data model. It stayed closed over that gap for six phases, which
is the reason every phase since has had its Definition of Done checked against the
running product rather than assumed.

### Act II — the pivot

Act I's risk was *"will the integration work?"*. That is retired. Act II's risk is
product-side:

> Will the owner still open this in three months?

So phases are named after **a question the owner asks**, and each exit criterion is
behavioural rather than technical.

### Phase 8 — "How much can I spend today?" — shipped

**Safe to Spend Today** is the dashboard headline and the figure `/summary` opens
with: `max(0, variable_budget_total − variable_budgeted_spend − fixed_overrun) /
days_remaining`. Every threshold the product judges a month by lives in
`burnrate.domain.metrics` with no database session. ADR-0001, ADR-0002.

What the phase actually taught, in three facts worth carrying:

* **Pending spend is load-bearing** (ADR-0003). A card settles one to three days
  later, so an allowance counting only booked spend is optimistic by exactly the
  amount most likely to matter, in the direction that causes overspending. It
  brought the **Effective Date** (booking, then value, then import date) and a
  reconciliation sweep with it.
* **The slices are asymmetric.** Pending counts in the variable slice only, so the
  variable slice cannot be computed as `monthly_spending − fixed_spent`.
* **A figure must name its tense.** `safe_to_spend_status` carries `month_closed`
  and `month_not_started` so no interface re-derives it; two separate defects were
  one page stating something about a month it did not know.

One gap is still open and deliberately deferred to 9b: **a manual categorization on
a hold is lost when the hold books under a new identifier**, for a bank supplying no
stable pending id. The obvious fix — exempting categorized rows from the sweep the
way Ignored rows are exempt — **is wrong and must not be taken**: an Ignored row is
excluded from every figure, so a surviving twin is clutter, while a categorized
pending twin *counts* alongside its booked self and the dinner is spent twice. What
fixes it is identity matching, which is 9b's work. Unreachable against the one bank
restricted production has.

### Phase 9a — "Is this normal?" — shipped, and the claim shrank

Baselines exist, are derived every request with no snapshot table (ADR-0008), read
only months the bank was actually asked about (ADR-0009), treat a one-month Fixed
Budget as the owner declaring an event (ADR-0011), and use a median for aggregates
and a mean for categories (ADR-0012).

**The goal was withdrawn rather than met** — ADR-0014. A baseline is a second answer
where the budget already answers, so it survives for income and for telling the owner
a budget is unrealistic, and nowhere else. The live output is *"not enough history to
compare yet"*, and that sentence is the correct output, not a placeholder.

Still open from 9a, both cheap, both in the revised Definition of Done:

* **One line per figure saying which kind of blank it is.** A blank now means "no
  history", "deliberately not compared" or "nobody asked", and they look identical.
  `BaselineStatus` is `ok | insufficient_history | month_not_started`; the other two
  kinds have no representation.
* **The dashboard's Budget pulse rows are silent while the Categories page's rows
  compare.** Same categories, same month. The payload exists and joins by category
  id. `budget_usage` is the wrong carrier alone — it holds only budgeted categories.

And one piece of misplaced code, recorded rather than ridden along on a feature:
`as_utc` is a clock concern living in `services/connection_expiry.py`, imported by
baseline sync coverage. Two readers now, so the next one is the trigger to move it.

---

## What the live data says

Measured on **2026-11-03** against the running database, not reasoned about. These
are the facts that kill plans, and every one of them has killed one.

> **Revised at 17:25 the same day**, when a second bank was connected and two of the
> facts below stopped being true. The tables are the new readings. That the document
> needed rewriting six hours after it was written is not an embarrassment, it is the
> method working: it is ordered by measurements, so a new measurement reorders it.

### Money the product cannot see

| | |
|---|---|
| Accounts in the system | **3**, across **two banks**, total visible **€1,753.08** |
| ING current | €51.54, 624 transactions from 2026-06-01 |
| Openbank current | **€1,701.54**, 25 transactions from 2026-10-19 |
| Openbank second account | €0.00, no transactions, purpose unknown |
| Savings accounts | **still none.** The ING savings account is not synced and does not exist as a row |
| Money held outside what the product can see | **most of it** — the owner, asked directly on 2026-11-03 |
| Last income | **2026-10-29, €1,823.50**, a payroll from a new employer, into Openbank |
| The income before it | 2026-10-09, €980.20 `Abono prestación INEM` — the last unemployment payment |
| Drawn from savings in 5 months | €13,041.00 over 8 transfers, typed `transfer` by ADR-0010 |

**The product is still blind to the number that matters, and connecting a second bank
did not fix it — it moved it.** It now sees €1,753.08 and the owner says the majority
of their money is somewhere it cannot reach. So "Current balance", the cushion, and
every *"can I afford this"* answer are computed on a minority of the money, and are
wrong by an amount the product cannot bound.

This is why Phase 11 stays second, and why its manual-account half stopped being the
optional one. A cushion computed today would not be an incomplete number, it would be
a **confidently wrong** one.

### History

| | |
|---|---|
| Transactions | 624 across 6 calendar months |
| Categories / budgets | 25 / 11 |
| Permanently dead months | **2026-08 and 2026-09** — a 36-day worker outage lost 30 Aug to 3 Sep, and the bank's fetch window is 30 days, so they can never be fetched |
| Unclassified | **2026-06 only: 29 debit rows, 66.6% of the month's outgoing euros.** Every other month is at 0.0% |
| Qualifying Months available | 0 today. From 2026-12 the window reaches Sep (dead), Oct (a divorce) and Nov |

Classifying June fixes **June's own reported figures**, which have always been
understated. It does **not** unblock December: a 3-month window from December does
not reach June, and widening to 5 reaches July's severance instead. 29 rows.

### Data at rest

| | |
|---|---|
| Database size | **10 MB** |
| Backups | **none.** No dump, no cron, no script |
| Storage | one Docker volume, `burnrate_postgres-data`, on this host |
| `BANK_TOKEN_ENCRYPTION_KEY` | a restore without it yields undecryptable bank tokens |

The product has **already suffered irreversible data loss** — the 36-day hole — and
the response was to build an alert about it (ADR-0013), not a copy of the data. This
is Phase 13, and it is why Phase 13 moved from last to first.

### Signals a feature was scoped against and does not have

| Field | ING — 624 rows | Openbank — 25 rows |
|---|---|---|
| `counterparty_name` | present in **13** | present in **2** |
| `merchant_name` | present in 319, frequently the **owner's own name** | present in **2** |
| `bank_transaction_code` | one value, `"Banca online"`, on every row | absent |
| `merchant_category_code` | never | never |
| Usable signal | a Spanish free-text `description`, nothing else | the same |

**This was measured on one bank in the morning and confirmed against a second the
same evening.** That matters more than the numbers: the obvious objection to 9b's
finding was that it described ING rather than the data, and a different bank with a
different card and a different country of spend is poorer still — 8% of rows carry a
merchant name against ING's 51%. The poverty is a property of what Enable Banking
returns, not of one ASPSP, and connecting a third bank will not rescue 9b.

9b's scope line — *"same counterparty, stable cadence, similar amount"* — names a
field that does not exist. Exact description matching finds 19 strings recurring in
three or more months, but **splits three of the eight real subscriptions in half**
(Claude, Google One, ChatGPT each arrive under two strings), and the round-up saver
contributes **260 near-identical rows** of €0.01-€1.94 on every day of the month.

---

## Who this is for

> **Corrected twice on 2026-11-03**, six hours apart. The morning version replaced
> *"a salaried person"* with a drawdown profile, because the live data showed no
> salary since July's severance. At 17:25 a second bank was connected and a
> **€1,823.50 payroll from a new employer, dated 29 October, monthly** appeared with
> it. The morning correction was right about the data it had and wrong about the
> owner by ten days.
>
> This section's own closing instruction — *"If the owner returns to a salary,
> re-read this section before re-ordering"* — fired within six hours of being
> written. **Keep it.** It has now earned its place twice, and it is the only line
> here that survives being wrong.

BurnRate targets **its owner, newly back on a salary, whose savings sit mostly in
accounts the product cannot see, and who does not want to overspend.** That implies,
in order:

* **Safe to Spend Today is the daily driver again, and now it can be right.** A
  monthly income to pace against is the thing it was built for. But it is computed
  from budgets and **knows nothing about the balance**, and the balance it would read
  is a minority of the money. The fix is Phase 11, not a change to Phase 8.
* **The cushion demotes to reassurance, exactly as this section predicted** — and its
  input is missing, which is now the bigger problem. *"My savings cover N months"* is
  no longer the number that changes a decision day to day, but it is still the number
  the owner cannot see at all, and the only one Phase 3 ever promised.
* **The baseline becomes reachable, and is still not reachable yet.** One payslip is
  not a normal, Openbank holds fifteen days, and Qualifying Months is still **0**.
  ADR-0014 stands on its own grounds regardless: a baseline is a second answer where
  the budget already answers.
* **Phase 14 inverts back to ETAs**, as written. With a surplus, *"when can I buy
  it"* is a real question again, and *"what does this cost me in cushion"* becomes
  the secondary framing rather than the only honest one.

One live caution the new bank introduces: **the product cannot tell "this account did
not exist before 19 October" from "we only fetched from 19 October."** Here it is the
former, confirmed by the account's first transaction being the owner seeding it with
€200. A month-level figure spanning both banks before that date is ING-only and does
not say so.

If the owner's income changes again, re-read this section before re-ordering. It is
the single most important input below, and it has been stale twice.

---

## The ordering principle for what remains

Act II was ordered by product value. What two phases measured is that **the binding
constraint is data, not features**:

1. 9a shipped a complete baseline engine whose live output is a blank, because the
   history it needs does not exist and two months of it are permanently gone.
2. Its real return came from **reading the live database**, not from the feature:
   `From Savings` typed as income (a factor-of-23 error in net cash flow), a worker
   dead for 36 days with nothing saying so, and migration `0008` unapplied in
   production for an entire phase.

So: **the measuring exercise can be done without building the feature, and it is
what has paid.** Before scoping anything below, read the live data for it first. Two
phases running, that is where the findings came from.

And the corollary, which is the ordering above: keep the data, then make the product
see all of it, then build on it. Nothing downstream of a 36-day hole is worth more
than not having the next one.

---

## Phase 13 — Keep the data

### Objective

Make the owner's financial history survivable. It is 10 MB, it is irreplaceable
beyond the bank's 30-day window, and it has never been copied.

### Scope

* `pg_dump`-based backup script wired for Docker Compose, scheduled on this host.
* Restore script, and a **restore exercised at least once** onto a clean stack.
* `BANK_TOKEN_ENCRYPTION_KEY` handled explicitly in the backup story: where it
  lives, how it is backed up separately, and what a restore without it produces.
* A **dead-man's switch for the sync worker**, which is the one case ADR-0013 left
  open: a process that is not running cannot report itself, so a timely warning
  during an outage has to come from outside the process. This is deployment, and it
  belongs here rather than in a feature.

### Notes

The restore is the deliverable, not the dump. An untested backup is a belief.

### Definition of Done

A restore has been performed onto a clean stack and reproduces the owner's
transactions, categories, budgets and a **working bank connection**. A 36-day worker
outage would now be noticed within a day by something that is not the worker.

### Definition of Done: checked (the backup half, 2026-11-03)

Checked by running it, not by reading it.

| Clause | Result | Evidence |
|---|---|---|
| A restore has been performed | **Met** | A set was taken and restored into a scratch database. All ten tables matched the manifest row for row -- 624 transactions, 4,169 sync sessions -- and the Alembic revision came back as `0009_from_savings_is_a_transfer` |
| ...onto a clean stack | **Met in substance, not literally** | The target was a freshly created database in the running container, not a second host. What a separate host would additionally prove is Docker and Compose coming up from nothing, which is not what is at risk here |
| ...and reproduces a working bank connection | **Met** | All three stored bank sessions decrypted using `BANK_TOKEN_ENCRYPTION_KEY` taken from the backup set's own `env` copy, including the active one expiring 2027-01-12. This is the clause most easily assumed and worst to get wrong, so it was executed rather than reasoned about |
| A worker outage is noticed within a day | **Not met** | The dead-man's switch is parked by the owner. It is a separate concern from copying data and remains the open case from ADR-0013 |

**Phase 13 is therefore half closed, deliberately and with the remainder named** --
which is the shape Phase 3 got wrong by closing over a gap nobody wrote down.

One defect was found by a test rather than by review, and it is the kind this phase
is about: the backup script's cleanup trap did not fire, because an ERR trap is not
inherited into shell functions without `set -E` and every command that can fail runs
through one. A failed backup left its partial set on disk **looking like a backup**.
The test that caught it was written before the script.

### What is left

* The **dead-man's switch** for the sync worker, parked.
* A destination **off this host**, with the secret copies encrypted once they travel.
  The only line that changes is `BURNRATE_BACKUP_DIR`.

---

## Phase 11 — "How much do I actually have?"

Absorbs the manual-account feature, because they are the same migration and the
cushion is uncomputable without it. Closes the Phase 3 gap and makes the product's
own name mean something.

### Objective

Let the product see every balance the owner has, including the ones the bank will not
send, and state how long they would last.

### Scope

* **Account purpose.** Migration: `accounts.purpose` as `spending | savings`.
  `included_in_calculations` is not a substitute — it decides *whether* an account
  counts, not *as what*.
* **Manual accounts.** A manual account is a row in `accounts` with **no
  `enable_banking_account_mappings` row**. The table already carries no
  provider-specific column, so this needs no new table and no provider abstraction —
  it is the "keep integration tables separate from product tables" rule in
  `AGENTS.md` paying out.
* **A manual balance is a claim with a date.** A separate `balance_confirmed_at`,
  **not** `last_synced_at`: conflating them makes the sync-gap alert lie about an
  account that was never synced. Every surface showing a manual balance shows how old
  it is.
* **Cushion**: savings balance ÷ trailing median monthly expenses — *"my savings
  cover N months"*. Well-defined whether or not the owner is in deficit, which the
  original runway definition was not: savings ÷ average monthly *deficit* is infinite
  for anyone who saves.
* **Deficit runway** retained as a conditional view, shown only when trailing net
  cash flow is actually negative. The original definition, scoped to where it applies.
* Expose both through `/summary`, the dashboard, and the `/runway` Telegram command
  already promised in `docs/product/mvp.md`.
* Update `docs/product/metrics.md` in the same change.

### The defect this feature introduces if built naively

`SummaryService` sums `Account.latest_balance_amount` across every account with
`included_in_calculations = true` — see `summary_service.py:405-409`. Across the
three spending accounts live today that sum is correct. **Adding a savings account
with a balance silently inflates "Current balance"**, the one figure the owner reads
as *what is in my account right now*. A €20,000 savings balance would publish
€21,753.08 beside a €32/day allowance.

So every balance read must state the purpose it wants. Enumerate them before
starting; there are few.

Two things that are **not** affected, verified rather than assumed, so that nobody
"fixes" them:

* **Baselines.** They join `Account` through `Transaction`, and a manual account has
  no transactions.
* **Qualifying Months.** Sync coverage is computed from `sync_sessions` globally, not
  per account, so a manual account cannot disqualify a month.

### What this phase must not become

* **No double-entry.** A transfer out of the current account does **not** credit the
  savings account. `AGENTS.md` rules out a ledger, and an auto-posting manual balance
  is one. The most the product may do is notice that €500 left as a `transfer` since
  the last confirmation and **ask the owner to confirm the new balance**.
* **No asset values.** A savings balance is cash. Net-worth and investment tracking
  are explicit non-goals in `docs/product/overview.md`.

### Before writing any code

This was *"re-run the consent and find out whether ING exposes the savings account;
ten minutes, and it can delete half this phase."* **Half of it ran on 2026-11-03** —
against Openbank, not ING — and the result was two accounts, one of them empty, and
no savings account. It did not delete half the phase.

What remains of that check is the ING half, and it is **no longer a gate**. The owner
has since stated that most of their money is in accounts the product cannot see, so
manual accounts are required whatever ING answers; the ING answer only decides
whether one specific balance stops needing to be typed by hand. It will be run in
person when the owner is next at the host's location, which is also when the ING
consent is renewed before it lapses on **2027-01-12**.

The thing actually worth doing before writing code is smaller and is not a bank
question: **find out what the second Openbank account is.** It carries €0.00 and no
transactions, and `purpose` is the column this phase is about to add.

### Definition of Done

Enumerated, per ADR-0014's lesson about clauses that name no set:

1. The dashboard states how many months the owner's savings would cover, from a
   balance the owner entered by hand.
2. "Current balance" means spending money and is unchanged by adding a savings
   account. Asserted by a test that adds one.
3. A manual balance shows when it was last confirmed, on every surface it appears.
4. **No documented metric remains unimplemented**, and the set is enumerated here so
   the check is arithmetic rather than judgement. `docs/product/metrics.md` has **ten
   metric sections**; nine are implemented and were checked under Phases 8 and 9a.
   The tenth is `## Runway`, which holds **Cushion** and **Deficit Runway**. Those two
   are the whole of what this clause covers.

---

## Phase 14 — "When can I buy it?"

New on 2026-11-03, from the owner. The first forward-looking feature in the product,
and the first consumer the net-cash-flow baseline has ever had.

### Objective

Let the owner name the things they want to buy, in priority order, and get a straight
answer about each: when, and what it costs them.

### Scope

* **A Goal**: name, target amount, priority, optional deadline. Funded **sequentially
  in priority order**, not in parallel — it is simpler and it is how people actually
  buy.
* **The monthly amount available for goals is stated by the owner, not derived.** A
  Savings Goal is the same primitive as a budget: the owner declares the intent and
  the product measures reality against it. The baseline is the **reality check**, not
  the input — *"you planned €400 a month and your typical month puts aside €90"*.
* **Primary output depends on which way the money is flowing**, and both must exist:
  * While there is a surplus, **which is the live case again since 2026-10-29**: an
    **ETA per goal**, and *"what can I afford"* — the largest single purchase that
    does not push goal #1 past its deadline.
  * While there is a drawdown: the cost of a purchase in **cushion**. *"This monitor
    costs you 3.1 weeks."* An ETA is `never` and saying so is the honest output.
  * Both exist and the product picks by measuring, not by configuration. The owner's
    direction of cash flow has reversed twice in five months, and a roadmap section
    had to be rewritten both times; the feature should not need rewriting at all.
* **The affordability verdict is deterministic.** A goal is out of reach when its ETA
  exceeds its deadline, or when funding it drops the cushion below a floor. No model
  is required to say that a €35,000 car is fourteen years away at €200 a month.
* **Give Safe to Spend Today a consequence.** *"Dinner tonight costs 2 days of the
  monitor"* is the most decision-changing sentence the product could say, and it is
  division, not AI. This is the cheapest part of the phase and possibly the most
  valuable.

### Where a model genuinely helps, and only here

The owner's ask was for advice: *how much to save, when to buy, what I could afford,
and whether what I want is out of line with how I live.* Three of those four are
arithmetic over the figures above. The fourth is a judgement about sequencing and
tone, and that is the model's whole job:

* It **selects and words** — which goal to mention, how to say that a priority order
  and a funding order disagree.
* It **never computes** an ETA, a surplus, an affordability verdict or a cushion.
  Those are domain functions with tests, per ADR-0001.
* Behind a domain interface (`GoalAdvisor`), opt-in, and the phase works with it
  disabled. Phase 12's constraints apply in full.

### Boundaries

* **Cash purchases funded from savings.** No interest, no amortization, no asset
  values, no investment returns. A house enters as *the deposit*, not as the house —
  anything else is the net-worth tracker the product refuses to be.
* **No scraping of prices.** A goal's amount is a number the owner types.
* A goal is not a budget and does not touch the allowance. Budgets pace a month;
  goals consume what a month leaves over.

### Definition of Done

The owner can list four things they want, in priority order, and the product states
for each one either a date or the number of weeks of cushion it costs — and says
which of their goals is out of line with how they currently live, from a rule with a
test rather than from a sentence a model wrote.

---

## Phase 10 — "Tell me, don't make me look"

### Objective

Invert the interaction model. Today Telegram is a pull interface for a dashboard the
owner has to remember to open.

### Scope

* Weekly digest over Telegram: what changed, where the month is heading, one
  suggested action.
* Event-triggered alerts, deterministic and rate-limited:
  * projected overspend crosses the monthly budget
  * a category crosses its threshold
  * **the cushion crosses a month boundary** — "your savings now cover 4 months"
  * **a goal's date moves** by more than a week
  * a commitment changes price or fails to appear
  * the unknown queue grows past a threshold
  * **a manual balance has not been confirmed in N days**
* Alert preferences and quiet hours.
* The bot stays free of financial logic.

### Notes

The infrastructure already exists; the design work is **restraint**. An alert that
fires too often gets muted, and a muted channel is worse than no channel. ADR-0013 is
the worked example: the first sync-gap alert would have sat above every month's
figures until December with nothing to do about it, and the owner caught it in one
sentence — *"are we going to show this all the time, even in November?"*

This phase was previously ordered second and is now fourth, because what it had to
say was *"this month is unlike your months"* — which needs a baseline that will not
exist until 2027. After Phases 11 and 14 it has the cushion and the goals to talk
about, which are figures the owner acts on and which move for real reasons.

### Definition of Done

Over a full month, the owner learns something actionable they did not already know,
without having opened the Web UI — and has not muted the bot.

---

## Phase 9b — Commitments

### Objective

Tell the owner what they are committed to every month, and when the price changes.

### Scope, inverted on 2026-11-03

The phase was scoped as **detection** — *"same counterparty, stable cadence, similar
amount"* — and the data section above is why that cannot be built: there is no
counterparty, the only signal is Spanish free text, exact matching splits three of
eight subscriptions, and 260 round-up rows defeat any cadence threshold. Merchant
normalization is not an improvement to 9b; it would **be** 9b, and it needs a model.

Meanwhile the owner knows all eight of their subscriptions and can type them in ten
minutes. So:

* **A Commitment is entered by the owner**: name, expected amount, cadence, and
  optionally the categories or description fragments that match it. A list the owner
  confirms, not a list the product guesses.
* **Price-change and missing-charge detection run against that list**, which is the
  part the owner genuinely does not know. Matching a *known* string is a different
  and much easier problem than discovering an unknown one.
* **Total monthly commitment cost**, which is the figure the original scope wanted
  and the one thing the owner cannot add up at a glance.
* **A rule for the round-up saver.** 260 rows of €0.01-€1.94 that are savings
  transfers, not spending. They should be typed as transfers and stop being noise in
  every figure and every future matcher.
* **The last open Phase 8 gap**: carrying a manual categorization across the
  pending-to-booked transition needs the two rows recognised as one — match on
  amount, a date window and the description. Still unreachable against the one bank
  restricted production has, so it is built only if that bank turns out to supply
  unstable pending identifiers.

### Definition of Done

The commitments present in the live data at close, **listed by name in the spec**,
all appear with their monthly total, and a price change on any one of them is
reported without the owner having gone looking.

---

## Phase 12 — AI assistance

### Objective

Use a model where deterministic rules genuinely cannot reach, without making the
product depend on one.

### Scope

* **Categorization copilot** — the primary deliverable. Rules stay the fast path;
  what the rule engine misses goes to a model, which proposes a category **and a
  generalized rule**. The owner confirms once and the confirmation writes the rule,
  so the system becomes **more** deterministic with use.
  `created_from_manual_classification` and `apply_to_existing_uncategorized` in
  `RulesService` already support this shape.
* **Goal and digest narration** (Phases 14 and 10): the numbers and the triggers stay
  deterministic; the model selects what deserves mention and writes the prose.
* **Merchant normalization**, only if 9b's inverted scope turns out not to be enough.
* Natural-language queries over existing APIs. Lowest priority — demos well, gets
  used least.

### Architecture constraints

* A domain-level interface (`CategorySuggester`, `GoalAdvisor`). Application logic
  depends on that, never on a provider SDK or response shape.
* One implementation until a second real use case exists. No multi-provider
  abstraction.
* **Opt-in and degradable.** `docs/product/overview.md` promises no required cloud
  dependency, and sending transaction data to a hosted model is in tension with that.
  Every phase above must work with the feature off.
* A suggestion never writes a category without confirmation. Suggestions are
  proposals; rules are truth.

### Notes

No dependencies; promote freely. The case for promoting it has sharpened three times:
classifying July took one afternoon and changed what three months report, and the
backlog is what disqualifies months from being baseline input. But the remaining
backlog is now **29 rows in one month**, so the cheap version of this phase is an
afternoon of manual classification, and the expensive version should wait until the
queue is a recurring cost again.

### Definition of Done

The unknown queue can be cleared in a fraction of the taps it takes today, every
confirmation leaves a reusable rule behind, and turning the feature off degrades the
product without breaking it.

---

## Frozen

Not "never", but blocked on something specific, and recorded so they are not
re-proposed.

| Item | Blocked on |
|---|---|
| **A 12-month baseline window** | history. Five months exist, two are permanently dead. Twelve months with a median is the target shape and makes outliers stop mattering; every parameter change before then is a patch on N=3 |
| **A monthly snapshot table** | the window. 9a measured the cost before refusing it — 6 statements to 13-15 live, 25 at the ceiling — and named widening the window as the trigger to reopen it, against measurement rather than against 9a's estimate |
| **Per-transaction anomaly flagging** | a distribution. Two Qualifying Months with eleven rows in a category is not one |
| **Email parsing for transfers** | nothing — it is declined. An IMAP or OAuth integration plus a per-bank Spanish-language parser with no idempotency key, to maintain a number the owner can confirm in ten seconds. It reintroduces exactly the dirty free-text matching that sank 9b's original scope. The manual balance plus a confirmation prompt in the weekly digest gets nearly all of it |
| **Recurring-charge *detection*** | a model, and 9b's inverted scope may make it unnecessary |
| **An Exceptional Charge flag** | declined twice by the owner. The pace half is solved by a bounded Fixed Budget, the baseline half by the Event Budget rule reading that same window (ADR-0011). The one case neither covers — a one-off inside an *ordinary* category, a boiler repair under `Home` — is unreached in the live data |

---

## What not to do

* **Multi-provider banking abstraction.** One provider works; a second is not on the
  roadmap. A manual account is not a second provider — it has no provider.
* **Multi-tenant or multi-user models.** Single-owner by design.
* **Net-worth or investment tracking.** An explicit non-goal, and Phase 14 is the
  phase most likely to drift into it.
* **A ledger or double-entry accounting.** Phase 11's manual balance is the phase
  most likely to drift into it.
* **Making the AI load-bearing.** If a disabled model breaks a core flow, the design
  is wrong.
* **More alerts than the owner will tolerate.** Phase 10 fails by over-firing.
* **Charts for their own sake.** The product competes with a fuel gauge, not with a
  BI tool. A new visualization has to change a decision.
* **A second spelling of a window rule.** `burnrate.db.budget_windows`,
  `burnrate.db.counted_spend` and `domain.sync_coverage` each exist because two
  readers disagreed about one rule once.

---

## Milestone view

* **Data In** — Enable Banking, real balances and transactions. Shipped.
* **Data Understood** — transactions, unknown queue, rules. Shipped.
* **Data Becomes Insight** — budgets, money left, burn rate. Shipped.
* **Data Stays Fresh** — the sync worker. Shipped, and it stopped for 36 days.
* **Access Anywhere** — Telegram. Shipped.
* **Data Becomes a Decision** (8) — one number that changes what the owner does
  today. Shipped.
* **Data Gets a Memory** (9a) — the comparison exists and refuses to speak when it
  cannot speak honestly. Shipped, with the claim shrunk to income and unrealistic
  budgets.
* **Data Survives** (13) — backup and restore, proven by running it. Shipped, minus
  the dead-man's switch.
* **Data Is Complete** (11) — every balance the owner has, and how long it lasts.
* **Data Gets a Future** (14) — what they want to buy, and what it costs them.
* **Data Speaks First** (10) — BurnRate reaches out instead of waiting.
* **Data Gets Named** (9b) — the commitments, confirmed rather than guessed.
* **Data Gets Help** (12) — the model handles the tail the rules cannot.

---

## Immediate next steps

1. ~~**Back up the database, and exercise a restore.**~~ **Shipped 2026-11-03.**
   Nightly sets on this host, each verified readable as it is written, and a restore
   actually performed -- including decrypting the live bank session from the key in
   the backup set, which is the half of a recovery that is easiest to assume. The
   dead-man's switch is parked; a destination off this host is the upgrade.
2. ~~**Re-run the Enable Banking consent to see whether ING will send the savings
   account.**~~ **Partly done 2026-11-03**: Openbank is connected (two accounts,
   €1,701.54, consent to 2027-05-02). The ING half waits for the owner to be at the
   host's location, where the router is theirs — which is the same trip that renews
   the ING consent before **2027-01-12**. It is no longer a gate on Phase 11.
3. **Classify June's 29 rows.** Twenty minutes. It fixes June's own figures, which
   have always been wrong; it does not unblock December.
4. **Close 9a's two cheap gaps**: one line per figure naming which kind of blank it
   is, and the dashboard's silent Budget pulse rows. Both are in the revised
   Definition of Done.
5. **Then Phase 11.** No longer the hero metric — a salary returned on 2026-10-29
   and Safe to Spend Today took that back — but it is the oldest unkept promise in
   the product, and the owner has confirmed that most of their money is in accounts
   it cannot see. Every balance-derived figure is wrong until it ships.

### Deferred by decision, not by oversight

**An HTTPS door on the host for the bank callback.** Enable Banking only accepts an
HTTPS redirect, the whitelisted URL points at a hostname the owner no longer serves,
and on 2026-11-03 the Openbank callback had to be completed by **retyping the URL
against the LAN address by hand** — one attempt was already lost to a stray double
slash returning 404, and an authorization code is single-use and expires in minutes.

The fix is small and known: `listen 443 ssl` on the nginx that already proxies
`/enable_banking_items/`, a certificate by **DNS-01** (which needs no inbound
connectivity, so it works against a DuckDNS record pointing at a private address),
and `443:443` published. The owner has deferred it on the grounds that the next
renewal will be done in person with control of the router. Recorded here so that the
decision is visible when the ING consent approaches **2027-01-12**, and so the
scramble is a choice rather than a surprise.

### The lesson each of these is paying for

Phase 3 closed over a known gap and it stayed closed for six phases. Phase 8's gap
list grew twice *after* its own Definition-of-Done check. 9a's check **passed on the
tests and failed on the data** — only reading the running product showed the
difference. And ADR-0014 is the narrowest version of all three: 9a's Definition of
Done was not met too little, it was **worth meeting too little**, and that takes
longer to notice than a missing feature.

This revision is that lesson applied to the document itself. The two phases ordered
first are the two nobody was asking for, and the data is what asked.
