# Development Pipeline

How a feature moves from a roadmap phase to shipped code in this repo.

The pipeline exists because `AGENTS.md` already mandates TDD and
documentation-in-the-same-change; this is the operational form of those rules,
not a new policy.

## Shape

```
  ONCE PER FEATURE
    roadmap phase
        ↓
    1. /grill-with-docs     design tree + GLOSSARY.md + anticipated ADRs
        ↓
    2. /to-spec             synthesis + AGREED SEAMS → .scratch/<slug>/spec.md
        ↓
    3. /to-tickets          vertical slices + blocking edges → issues/NN-*.md
        ↓
  PER TICKET, ON THE FRONTIER
    ┌─→ 4. tdd              red → green at the agreed seams
    │       ↓
    └── 5. /code-review     refactor + cleanup lives HERE
        ↓
  ONCE PER FEATURE
    6. Definition of Done   check the phase's DoD in the roadmap
        ↓
    7. /distill-decisions   harvest → route → delete .scratch/<slug>/
```

Stages 1-3 run once. Stages 4-5 loop per ticket, working the frontier (any
ticket whose blockers are all done). Stages 6-7 run once at the end.

## The stages

### 1. `/grill-with-docs`

Stress-tests the design before any code exists. Dispatches to `grilling` (the
relentless round-based interview) and `domain-modeling` (which writes
`GLOSSARY.md` and ADRs the moment a term or decision crystallises).

Entry point is a phase from `docs/technical/roadmap.md`. Skip this only for work
whose design is genuinely settled; the cost of skipping it shows up in stage 2
as a spec that keeps changing.

### 2. `/to-spec`

Synthesises the conversation into `.scratch/<feature-slug>/spec.md`. No
interview — that already happened in stage 1.

**This is where the testing seams are agreed**, and that is the stage's most
important output. `tdd` refuses to write a test at an unconfirmed seam, so an
unspecified seam stalls stage 4. Prefer existing seams, use the highest one
available, and aim for as few as possible.

### 3. `/to-tickets`

Breaks the spec into tracer-bullet vertical slices, each declaring the tickets
that block it, written to `.scratch/<feature-slug>/issues/NN-<slug>.md`.

Each slice cuts a complete path through every layer and is sized for one fresh
context window. Wide mechanical refactors are the exception and sequence as
expand → migrate in batches → contract.

### 4. `tdd`

The red → green loop, at the seams agreed in stage 2. Auto-invokes; it does not
need calling by name.

One seam, one test, one minimal implementation per cycle. Vertical slices, never
all-tests-then-all-implementation.

### 5. `/code-review`

Claude Code's **built-in** `/code-review`, not an installed skill — see
`.claude/skills/README.md` for why upstream's was deliberately skipped.

Refactoring belongs here. `tdd` explicitly excludes it from the red → green
loop, so this stage is not optional: it is where the loop's deliberate
minimalism gets cleaned up. `/simplify` covers the quality-only pass.

Run `/security-review` as well for anything touching auth, the encrypted bank
tokens, or the Enable Banking integration.

### 6. Definition of Done

Before closing a feature, re-read its phase in `docs/technical/roadmap.md` and
check every item in that phase's **Definition of Done**.

This gate exists because the repo has already failed it once: Phase 3's DoD
required a runway metric, the phase was treated as complete without it, and the
gap went unnoticed for six phases because nothing downstream depended on it. A
phase is not done because its tickets are closed. It is done when its DoD is
satisfied, or when the gap is recorded explicitly in the roadmap.

### 7. `/distill-decisions`

Harvests the decisions worth keeping, routes each to an ADR / `GLOSSARY.md` /
`docs/technical/` / a test gap / nothing, then deletes
`.scratch/<feature-slug>/`.

Most candidates are deliberately dropped. See `docs/agents/issue-tracker.md` for
the lifecycle and the skill itself for the routing table.

## Decisions get recorded at both ends

Stage 1 and stage 7 both write ADRs, and they are not redundant:

- **Stage 1 captures anticipated decisions** — the trade-offs visible while
  designing, argued before code existed.
- **Stage 7 captures discovered decisions** — the dead end that was backed out,
  the constraint found halfway through, the place the obvious approach was
  wrong. These are the higher-value ones, because a future reader hits exactly
  these and wonders why the code looks like that.

To make stage 7 cheap, leave breadcrumbs during stage 4: put the *why* in commit
messages and append mid-flight corrections to the ticket's `## Comments`.

## Not a stage

- **`codebase-design`** is a reference, not a session. Consult it in stage 2 and
  stage 4 when the shape of an interface is itself in question — it is the
  shared source of the module, interface, depth, seam, adapter and locality
  vocabulary.
- **`domain-modeling`** is reached through `/grill-with-docs` and
  `/distill-decisions` rather than run directly, though calling it alone is fine
  when all that is needed is a glossary entry or one ADR.
- Upstream's `implement` and `implement-spec` skills are **not installed**. This
  repo implements through `tdd` directly.
