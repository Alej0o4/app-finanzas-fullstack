# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

## Before exploring, read these

- **`CONTEXT.md`** at the repo root, or
- **`CONTEXT-MAP.md`** at the repo root if it exists: it points at one `CONTEXT.md` per context. Read each one relevant to the topic.
- **`docs/adr/`**: read ADRs that touch the area you're about to work in.

Oikos has neither `CONTEXT.md` nor `docs/adr/` yet. **Proceed silently** — don't flag their absence, don't suggest creating them upfront. The `/domain-modeling` skill (reached via `/grill-with-docs` and `/improve-codebase-architecture`) creates them lazily when terms or decisions actually get resolved. Until then, `docs/ROADMAP.md`, `docs/specs/fase_NN_spec.md`, `backend/docs/BUSINESS_RULES.md`, and `backend/docs/ARCHITECTURE.md` / `frontend/docs/ARCHITECTURE.md` are Oikos's real sources of domain vocabulary and rationale — read those instead.

## File structure

Single-context repo (this is Oikos's layout):

```
/
├── CONTEXT.md          (does not exist yet — created lazily by /domain-modeling)
├── docs/adr/           (does not exist yet — created lazily by /domain-modeling)
└── backend/ frontend/
```

## Use the glossary's vocabulary

Once `CONTEXT.md` exists: when your output names a domain concept (in an issue title, a refactor proposal, a hypothesis, a test name), use the term as defined there. Don't drift to synonyms the glossary explicitly avoids.

If the concept you need isn't in the glossary yet, that's a signal: either you're inventing language the project doesn't use (reconsider) or there's a real gap (note it for `/domain-modeling`).

## Flag ADR conflicts

Once `docs/adr/` exists: if your output contradicts an existing ADR, surface it explicitly rather than silently overriding.
