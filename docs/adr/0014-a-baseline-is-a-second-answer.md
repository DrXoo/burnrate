# A baseline is a second answer where the budget already answers

A baseline is offered for **monthly income** and for **telling the owner a budget
is unrealistic**, and for nothing else. Every other figure on the dashboard either
has no baseline or states, in one line, which kind of blank it is. The original
goal — *"every headline figure is shown against its own baseline"* — is withdrawn,
not deferred.

## Why the goal was wrong rather than unmet

Phase 9a scored **3 of 8** against that clause, and the first reading was that
there were five gaps to close. The second reading is the correct one: **the owner
has already told the product what normal is. It is the budget.**

Where a budget exists, a baseline is a second, derived, fragile answer to a
question already answered, and the two can disagree in front of the owner. Worse,
it competes with the hero metric: *"is this normal?"* and *"am I on plan?"* are
different questions, and the product exists to answer the second. Safe to Spend
Today uses no baseline at all.

Two places are not a second answer, and they are the whole of what survives:

* **Income**, because nobody budgets their income. History is the only possible
  source of normal.
* **An unrealistic budget.** Budget €450 of food against €600 spent every month
  and the budget says `over` forever and teaches nothing. The baseline says *"this
  month is like your months"* — it does not compete with the budget there, it
  corrects it.

## What forced it

The owner's objection, on 2026-11-02: *an unforeseen expense wrecks the baseline,
unforeseen expenses happen easily, and having to wait months for it to be clean
again is bad design.* Measured against the live data, the objection was right
about startup fragility and wrong about the mechanism, and four examples separate:

| Case | What it actually is | What the product should do |
|---|---|---|
| A mortgage | a new recurring commitment | the owner enters a Fixed Budget; the baseline should rise **at once**. A baseline that takes three months to notice is wrong for being slow, not fragile |
| A car, a trip | an **event**, already declared | read the bounded Fixed Budget window — ADR-0011 |
| A car repair | a small one-off | absorbed and never reported. Measured: removing €565.40 of `Car Maintenance` from July moves a 3-month spend mean by **7.5%**, inside the in-line band |
| A divorce, a severance | an event too large for any window to absorb | there is nothing to average. Refuse to answer |

The generalisation in row three is the load-bearing one: **a one-off small enough
not to budget is small enough not to move a mean, and one large enough to move a
mean is one the owner would have budgeted.** The gap between the two is narrower
than it looks from outside.

## The measurement that ended the argument

Every answer the product could have published on 2026-12-01 was false. The owner's
five months of history, corrected after `From Savings` was retyped and July
classified:

| Month | Net | What it is |
|---|---|---|
| 2026-07 | **+€2,909.73** | a severance |
| 2026-08 | −€1,596.91 | ordinary — **permanently disqualified**, 36-day sync hole |
| 2026-09 | −€1,568.45 | ordinary — **permanently disqualified** |
| 2026-10 | **−€8,208.87** | a divorce |
| 2026-11 | in progress | — |

| Scenario | Qualifying | Baseline | Verdict |
|---|---|---|---|
| Window 3, as shipped | Oct, Nov | −€4,888.66 | a divorce is half of normal |
| Window 5, July classified | Jul, Oct, Nov | −€2,289.20 | a severance cancelling a divorce — defensible-looking **accident** |
| Window 5 + the event rule | Jul, Oct, Nov | **+€395.41** | removes the divorce, keeps the severance: tells an owner burning €1,600/month that they normally save €395 |

**The owner's only two ordinary months are the two the bank was never asked
about.** Everything that qualifies is an event. The baseline was not missing a
rule; there was nothing normal to average.

## Consequences

**Refusing to answer is the feature, not a placeholder.** `BASELINE_MINIMUM_MONTHS`
is 3 and the product says *"not enough history to compare yet"*. That sentence is
the correct output, and it will be the live output into 2027.

**Every "no" owes a reason on screen.** A blank beside a figure now means three
different things — "no history for this", "deliberately not compared", "nobody
asked" — and they looked identical. One line per figure naming which it is was the
cheap fix the 8-baseline goal obscured.

**A clause that names no enumerable set cannot be checked.** *"Every headline
figure"* was neither true nor false until someone invented the denominator at
close, and the first attempt got it wrong by missing Burn rate — the one figure
that already carried a comparison, against the budget rather than against the
owner's past. The replacement names eight figures and fixes each answer in
advance. Phase 11's *"no documented metric remains unimplemented"* has the same
shape and is enumerated before it starts.

**A Definition of Done can fail by being met too little or by being worth meeting
too little, and the second takes longer to notice.** This one failed the second
way, eight months of scope and six ADRs in.

**The structural answer is still a wider window, and it is still blocked.** Twelve
months with a median makes outliers stop mattering and brings the robust
statistics that are out of scope today within reach. Five months exist and two are
dead. Every parameter change before then is a patch on N=3 and is recorded as one.
