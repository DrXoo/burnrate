# Vendored Agent Skills

These skills are copied from [mattpocock/skills](https://github.com/mattpocock/skills),
upstream commit `24fe0ef7737efae15c87225755e9f6f5965e4888` (2026-10-04).

They are vendored rather than referenced, so they do not update on their own.
To re-sync, clone upstream and copy the directories again.

## Requested

| Skill | Upstream path | Notes |
|---|---|---|
| `grill-with-docs` | `skills/engineering/` | Stub only; dispatches to `grilling` + `domain-modeling` |
| `to-spec` | `skills/engineering/` | Needs `docs/agents/issue-tracker.md` from `setup-matt-pocock-skills` |
| `to-tickets` | `skills/engineering/` | This is the skill asked for as "to-issues"; no `to-issues` exists upstream |
| `tdd` | `skills/engineering/` | Works standalone; references `codebase-design` for seam vocabulary |

## Installed as dependencies

| Skill | Required by | Why |
|---|---|---|
| `grilling` | `grill-with-docs` | Hard dependency. Lives under `skills/productivity/` upstream, not `engineering/` |
| `domain-modeling` | `grill-with-docs` | Hard dependency. Also writes the `GLOSSARY.md` and ADRs the other skills read |
| `setup-matt-pocock-skills` | `to-spec`, `to-tickets` | Writes the issue-tracker and domain-doc config both skills expect |
| `codebase-design` | `tdd` | Soft dependency; shared vocabulary for module, interface, depth, seam |

## Locally authored (not from upstream)

| Skill | Why it exists |
|---|---|
| `distill-decisions` | Closes out a shipped feature: harvests decisions from its spec, tickets and implementation history, routes each to an ADR / `GLOSSARY.md` / `docs/technical/` / a test gap / nothing, then deletes `.scratch/<feature-slug>/`. Upstream has no equivalent — `retro` is about improving the agent's environment (lint, navigation pointers, `AGENTS.md` hygiene), not about distilling product decisions. Delegates ADR format and the three-part bar to `domain-modeling` rather than redefining them. |

A re-sync from upstream will not touch this directory, but do not expect
upstream to maintain it either.

## Deliberately NOT installed

* **`code-review`** — the upstream skill of that name collides with Claude Code's
  built-in `/code-review`. `tdd` references it for the refactor stage, which
  falls back to the built-in. Installing it would shadow a command that already
  works.
* **`triage`** — not requested. `setup-matt-pocock-skills` detects its absence
  and skips the triage-label section, so nothing is left half-configured.

## Per-repo configuration: done

`/setup-matt-pocock-skills` was run on 2026-10-05. It wrote:

* `docs/agents/issue-tracker.md` — **local markdown** under `.scratch/<feature-slug>/`.
  GitHub was the skill's default (the remote points there) but needs the `gh` and
  `jq` CLIs, neither of which is installed on this machine.
* `docs/agents/domain.md` — single-context domain docs (root `GLOSSARY.md` plus
  `docs/adr/`), created lazily by `/domain-modeling` rather than upfront.
* An `## Agent skills` section appended to `AGENTS.md` pointing at both.

No `docs/agents/triage-labels.md` was written, because `triage` is not installed
and the skill skips that section when it is absent.

`to-spec` and `to-tickets` are therefore ready to use. Re-run the setup skill
only to switch trackers or start over.
