# Issue tracker: Local Markdown

Oikos has no remote issue tracker in active use (git remote points at GitHub, but this repo tracks work as markdown files, not GitHub Issues). This repo already has an established per-phase spec convention — respect it instead of inventing a new one.

## Conventions

- **Specs** (produced by `/to-spec`): one file per roadmap phase at `docs/specs/fase_NN_spec.md`, matching the existing convention (`fase_07_spec.md` … `fase_16_spec.md`). The next spec is `fase_17_spec.md` unless the user names a different phase number. Check `docs/ROADMAP.md` for the phase this work belongs to before naming the file — don't guess a number that collides with an existing or planned phase.
- **Tickets** (produced by `/to-tickets`, when work needs breaking into tracer-bullet slices below the spec level): one file per ticket at `.scratch/<feature-slug>/issues/<NN>-<slug>.md`, numbered from `01`. There is no prior convention for this granularity in Oikos, so this falls back to the skill's generic local-markdown default.
- Triage state is recorded as a `Status:` line near the top of each ticket file (the `triage` skill is not installed in this repo, so no label vocabulary applies here — this is just the raw status line the ticket format uses).
- Comments and conversation history append to the bottom of a file under a `## Comments` heading.

## When a skill says "publish to the issue tracker"

- If the output is a **spec**: write or update `docs/specs/fase_NN_spec.md`.
- If the output is a **ticket** (a slice of implementation work): create a new file under `.scratch/<feature-slug>/issues/`, creating the directory if needed.

## When a skill says "fetch the relevant ticket"

Read the file at the referenced path (`docs/specs/fase_NN_spec.md` for a spec, or the `.scratch/...` path for a ticket). The user will normally pass the path or phase number directly.

## Wayfinding operations

Used by `/wayfinder`. The **map** is a file with one **child** file per ticket.

- **Map**: `.scratch/<effort>/map.md` (the Notes / Decisions-so-far / Fog body).
- **Child ticket**: `.scratch/<effort>/issues/NN-<slug>.md`, numbered from `01`, with the question in the body. A `Type:` line records the ticket type (`research`/`prototype`/`grilling`/`task`); a `Status:` line records `claimed`/`resolved`.
- **Blocking**: a `Blocked by: NN, NN` line near the top. A ticket is unblocked when every file it lists is `resolved`.
- **Frontier**: scan `.scratch/<effort>/issues/` for files that are open, unblocked, and unclaimed; first by number wins.
- **Claim**: set `Status: claimed` and save before any work.
- **Resolve**: append the answer under an `## Answer` heading, set `Status: resolved`, then append a context pointer (gist + link) to the map's Decisions-so-far in `map.md`.

## Pull requests as a triage surface

Not applicable — the `triage` skill is not installed in this repo.
