# Domain Docs

How the engineering skills should consume this repo's domain documentation when
exploring the codebase.

This repo is **single-context**: one `GLOSSARY.md` at the root and one
`docs/adr/` directory. There are no monorepo signals (no `pnpm-workspace.yaml`,
no `packages/`, no root `package.json`), so the multi-context layout with a
`GLOSSARY-MAP.md` does not apply here.

## Before exploring, read these

- **`GLOSSARY.md`** at the repo root
- **`docs/adr/`**: read ADRs that touch the area you're about to work in

If any of these files don't exist, **proceed silently**. Don't flag their
absence; don't suggest creating them upfront. The `/domain-modeling` skill
(reached via `/grill-with-docs`) creates them lazily when terms or decisions
actually get resolved.

As of this setup, neither exists yet. That is the expected starting state.

## File structure

```
/
├── GLOSSARY.md                 ← not created yet
├── AGENTS.md
├── docs/
│   ├── adr/                    ← not created yet
│   ├── agents/                 ← this directory
│   ├── product/
│   └── technical/
├── backend/src/burnrate/
└── web/src/
```

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor proposal,
a hypothesis, a test name), use the term as defined in `GLOSSARY.md`. Don't
drift to synonyms the glossary explicitly avoids.

If the concept you need isn't in the glossary yet, that's a signal: either
you're inventing language the project doesn't use (reconsider) or there's a real
gap (note it for `/domain-modeling`).

BurnRate already has a de facto vocabulary spread across
`docs/product/metrics.md` and `docs/technical/domain.md` — money left, burn
rate, runway, cushion, safe to spend, booked vs pending, fixed vs variable
budget. When `GLOSSARY.md` is written, it should reconcile with those documents
rather than compete with them.

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly rather than
silently overriding:

> _Contradicts ADR-0007 (event-sourced orders), but worth reopening because…_
