# Issue tracker: Local Markdown

Issues and specs for this repo live as markdown files in `.scratch/`.

BurnRate is single-owner and self-hosted, so work is tracked beside the code
rather than in a hosted tracker. `.scratch/` is **not** in `.gitignore`, so
these files are versioned with the repo on purpose: a ticket and the commit that
closes it travel together.

## Conventions

- One feature per directory: `.scratch/<feature-slug>/`
- The spec is `.scratch/<feature-slug>/spec.md`
- Implementation issues are one file per ticket at
  `.scratch/<feature-slug>/issues/<NN>-<slug>.md`, numbered from `01` in
  dependency order (blockers first), never a single combined tickets file
- Blocking edges are a `Blocked by: NN, NN` line near the top of each issue
  file. A ticket is unblocked when every file it lists is done.
- Triage state is a `Status:` line near the top of each issue file. The `triage`
  skill is **not installed in this repo**, so there is no label vocabulary and no
  `triage-labels.md`. Skills that want to mark a ticket as agent-ready write
  `Status: ready-for-agent`; anything else is free text.
- Comments and conversation history append to the bottom of the file under a
  `## Comments` heading

## Ticket lifecycle

Tickets are **scaffolding, not record**. A `.scratch/<feature-slug>/` directory
exists while the feature is in flight and is deleted once it ships. What survives
is the decisions, not the task breakdown.

Deleting is only safe after the durable parts have been promoted out, because
`to-spec` writes real decisions into the spec body (its `Implementation
Decisions` and `Testing Decisions` sections) and the spec lives inside the
directory about to be removed.

### On feature completion

Run `/distill-decisions`. It harvests the candidates, routes each one, and
deletes the directory once the promotions are written. It applies the
`domain-modeling` bar for what earns an ADR, so most candidates are
deliberately dropped rather than recorded.

The routing it follows:

1. **Why it was built this way** → an ADR in `docs/adr/`. Anything in the spec's
   `Implementation Decisions` that constrains future work belongs here, not in a
   deleted file.
2. **Vocabulary the feature introduced** → `GLOSSARY.md`.
3. **Architecture, schema or integration changes** → the existing docs under
   `docs/technical/`, per the Documentation Rules in `AGENTS.md`. This is the
   same rule that already applies per-change, applied once more at completion.
4. **What the system now does** → the tests. A test named for behaviour is the
   most reliable record of a decision, because it fails when the decision is
   broken. See the `tdd` skill.
5. Then `rm -rf .scratch/<feature-slug>/` and commit the deletion.

### Why the tickets are versioned anyway

`.scratch/` is deliberately not in `.gitignore`. Committing tickets and later
deleting them means git history keeps them recoverable, so the deletion loses
nothing: the raw slicing and acceptance criteria stay available for archaeology
("why did we cut it this way?") without cluttering the working tree.

If a decision only ever existed in a ticket body and was never promoted, it is
in git history rather than gone — but treat that as a miss in the promotion
step, not as the intended storage.

## When a skill says "publish to the issue tracker"

Create a new file under `.scratch/<feature-slug>/`, creating the directory if
needed.

## When a skill says "fetch the relevant ticket"

Read the file at the referenced path. The owner will normally pass the path or
the issue number directly.

## Wayfinding operations

Used by `/wayfinder`, which is **not currently installed**. Retained so the
convention is already settled if it ever is.

- **Map**: `.scratch/<effort>/map.md` (the Notes / Decisions-so-far / Fog body).
- **Child ticket**: `.scratch/<effort>/issues/NN-<slug>.md`, numbered from `01`,
  with the question in the body. A `Type:` line records the ticket type
  (`research`/`prototype`/`grilling`/`task`); a `Status:` line records
  `claimed`/`resolved`.
- **Blocking**: a `Blocked by: NN, NN` line near the top. A ticket is unblocked
  when every file it lists is `resolved`.
- **Frontier**: scan `.scratch/<effort>/issues/` for files that are open,
  unblocked, and unclaimed; first by number wins.
- **Claim**: set `Status: claimed` and save before any work.
- **Resolve**: append the answer under an `## Answer` heading, set
  `Status: resolved`, then append a context pointer to the map's
  Decisions-so-far in `map.md`.

## Switching to GitHub later

`origin` points at `github.com:DrXoo/burnrate`, so GitHub Issues is a viable
alternative. It needs the `gh` and `jq` CLIs installed and `gh auth login`
completed — neither CLI is present today, which is why this repo is on local
markdown. Re-run `/setup-matt-pocock-skills` to switch.
