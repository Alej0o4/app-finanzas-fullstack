# Issue tracker: Local Markdown

Oikos has no remote issue tracker in active use (git remote points at GitHub, but this repo tracks work as markdown files, not GitHub Issues). This repo already has an established per-phase spec convention — respect it instead of inventing a new one.

## Conventions

- **Specs** (produced by `/to-spec`): one file per roadmap phase at `docs/specs/fase_NN_spec.md`, matching the existing convention (`fase_07_spec.md` … `fase_16_spec.md`). The next spec is `fase_17_spec.md` unless the user names a different phase number. Check `docs/ROADMAP.md` for the phase this work belongs to before naming the file — don't guess a number that collides with an existing or planned phase.
- **Tickets** (produced by `/to-tickets`, when work needs breaking into tracer-bullet slices below the spec level): one file per ticket at `.scratch/<feature-slug>/issues/<NN>-<slug>.md`, numbered from `01`. There is no prior convention for this granularity in Oikos, so this falls back to the skill's generic local-markdown default.
- Triage state is recorded as a `Status:` line near the top of each ticket file (the `triage` skill is not installed in this repo, so no label vocabulary applies here — this is just the raw status line the ticket format uses).
- Comments and conversation history append to the bottom of a file under a `## Comments` heading.

## Oikos additions to the spec template

`/to-spec` is a vendored upstream skill (`.agents/skills/to-spec`, pinned in `skills-lock.json`) — don't edit it; a skills update would overwrite the change. These two additions apply on top of its template whenever a skill writes or edits `docs/specs/fase_NN_spec.md`. Both ideas, plus `/analyze-spec`, are borrowed from GitHub spec-kit, which was evaluated 2026-09-25 and deliberately **not** adopted as a tool: for a single owner who is both PM and implementer, its spec/plan/tasks split, `specs/NNN-*` numbering, and `constitution.md` would duplicate `docs/specs/fase_NN_spec.md`, `.scratch/`, and `CLAUDE.md` without adding a reader. Don't reintroduce it piecemeal beyond these three pieces without asking.

### 1. `[NEEDS CLARIFICATION: …]` markers

`/to-spec` synthesizes without interviewing, so anything the conversation (usually a `/grilling` session) left unresolved must be **visible in the spec**, not silently assumed:

- Put the marker inline, exactly where the decision lives: `[NEEDS CLARIFICATION: ¿el tope aplica por cuenta o global?]`. One specific question per marker, with the options if there are obvious ones.
- Only for decisions that change scope, the data model, an API contract, or UX in a way the owner would notice. Anything else: pick a reasonable default and state it as a decision.
- More than ~3 markers means the design isn't settled — go back to `/grilling` instead of publishing a spec full of holes.
- A spec with open markers is **not ready to implement**. When the owner answers, replace the marker with the decision and record it in the spec's `## Decisiones resueltas con el usuario (YYYY-MM-DD)` section (existing convention, see `fase_26_spec.md`).

### 2. Tagged `## Orden de ejecución` section

Every spec large enough to have more than one implementation step includes an `## Orden de ejecución` section (existing convention since Fase 25). Each step carries an area tag, its dependencies, and `[P]` when it can run in parallel:

```
1. [backend] app/core/auth_cookies.py + security.py — Decisiones B1, B3.
   Depende de: —
2. [backend] [P] app/core/csrf.py + wiring en main.py — Decisión B5.
   Depende de: 1
3. [frontend] [P] lib/api.ts + lib/authSession.ts — Decisiones F1, F2.
   Depende de: —  (verificable solo con 1–2 corriendo)
4. [verif] Prueba manual end-to-end.
   Depende de: 1, 2, 3
```

- **Area tags**: `[backend]`, `[frontend]`, `[docs]`, `[infra]`, `[verif]`. They map to who can take the step: `backend-engineer`, `frontend-engineer`, `qa-engineer` (for `[verif]` and test-writing steps).
- **`Depende de:`** lists step numbers, or `—`. No cycles.
- **`[P]`** means "can run at the same time as the other steps whose dependencies are also satisfied" — only if it **doesn't touch the same files** as those steps. Two steps editing `auth.py` are never `[P]`, even if they're logically independent.
- Each step names the `Decisión` IDs it implements, so `/analyze-spec` can check that every decision has a step and every step has a decision.
- `[docs]` steps are mandatory whenever a shared API contract changes (both `backend/docs/API_REFERENCE.md` and `frontend/docs/API_CONTRACT.md`, per `CLAUDE.md`).

Before implementing a spec, and again when closing the phase, run `/analyze-spec` (`.claude/skills/analyze-spec/SKILL.md`).

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
