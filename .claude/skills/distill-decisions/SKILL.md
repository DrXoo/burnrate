---
name: distill-decisions
description: "Close out a shipped feature: harvest the decisions worth keeping from its spec, tickets and implementation history, route each to its real home, then delete the scratch directory."
disable-model-invocation: true
---

# Distill Decisions

Run this when a feature is **done** and its `.scratch/<feature-slug>/` directory
is about to be deleted. It is the executable form of the ticket lifecycle in
`docs/agents/issue-tracker.md`: promote what is durable, then remove the
scaffolding.

**Your job is triage, not transcription.** Most of what a spec calls a decision
does not deserve an ADR, and a successful run of this skill usually produces one
or two ADRs and a longer list of things deliberately left to die. A `docs/adr/`
full of reversible, unsurprising decisions is worse than an empty one, because it
buries the few that matter.

## The bar

`domain-modeling` owns the ADR format and the bar for writing one. Read
[ADR-FORMAT.md](../domain-modeling/ADR-FORMAT.md) and apply its three-part test
unchanged: **hard to reverse**, **surprising without context**, and **the result
of a real trade-off**. All three, or it is not an ADR.

Do not restate or relax that bar here. If a candidate fails it, route it
elsewhere or drop it.

## Where the good candidates actually are

The spec's decisions were made *before* the work, which means they were obvious
enough to plan. They are mostly reversible and rarely surprising, so most of them
fail the bar.

The decisions worth keeping are usually the ones **nobody planned**: the approach
that was tried and backed out, the constraint discovered halfway through, the
place where the obvious implementation turned out to be wrong. A future reader
hits exactly these and wonders why the code looks like that. Look hardest here.

## Process

### 1. Gather the sources

- `.scratch/<feature-slug>/spec.md` — its `Implementation Decisions` and
  `Testing Decisions` sections are the planned set
- `.scratch/<feature-slug>/issues/*.md` — including any `## Comments` sections,
  where mid-flight corrections tend to land
- The conversation context, if the implementation happened in this session
- `git log` for the feature's commits, read for *why* rather than what. Tickets
  are committed and later deleted, so history holds anything already removed.
- The diff against the branch point, where it contradicts the spec. A
  divergence between what was planned and what was built is a decision that
  got made without being recorded.

### 2. Route every candidate

Each candidate goes to exactly one destination. Most land in the last two.

| Destination | For |
|---|---|
| An ADR in `docs/adr/` | Passes all three parts of the bar |
| `GLOSSARY.md` | A term the feature introduced or sharpened. Vocabulary only — `domain-modeling` forbids implementation detail there |
| `docs/technical/` | Changes to architecture, schema or integration behaviour, per the Documentation Rules in `AGENTS.md` |
| A test | Behaviour that should be pinned by a test and is not. Report this as a **test gap**, not as an ADR — a test fails when the decision is broken, which no document does. See the `tdd` skill. |
| Nothing | Reversible, unsurprising, or no real alternative existed. It stays in git history and that is sufficient. |

When a candidate was a genuine trade-off with a non-obvious rejected option,
use ADR-FORMAT's optional **Considered Options** section. Dead ends found during
implementation are the main reason that section exists: without it, someone
re-proposes the thing that already failed.

### 3. Quiz the user

Present a numbered table: candidate, proposed destination, and one line of
justification. For ADR candidates, name which of the three parts it satisfies —
if you cannot name all three, it is not an ADR.

Ask explicitly:

- Does anything here deserve an ADR that you are routing to nothing?
- Does any proposed ADR actually fail the bar?
- Did anything happen during implementation that none of these sources captured?

The last question matters most, because the highest-value decisions are the ones
that were never written down anywhere. Iterate until the user approves.

### 4. Write

Write the approved destinations. For ADRs, scan `docs/adr/` for the highest
existing number and increment; create the directory lazily if this is the
repo's first ADR.

Report test gaps as findings. Do not write the tests here: that is an
implementation task with its own red-green loop.

### 5. Delete the scaffolding

Confirm with the user, then `rm -rf .scratch/<feature-slug>/` and commit the
deletion together with the promoted docs, so one commit shows both what was
kept and what was discarded.

Never delete before the promotions are written. If the user declines any part
of the routing, stop and leave the directory in place.
