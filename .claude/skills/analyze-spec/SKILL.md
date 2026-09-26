---
name: analyze-spec
description: Read-only consistency check of an Oikos phase spec (docs/specs/fase_NN_spec.md). Two modes — before implementing (open questions, project invariants, internal consistency, stale file references, execution-order tags) and when closing a phase (spec vs. actual diff, missing docs/tests). Use when the user says "analiza el spec", "revisa el spec antes de implementar", "cierra la fase", or after /to-spec produces a spec.
---

# Analyze Spec

Oikos's lightweight substitute for spec-kit's `/analyze` + `/converge` (see "Oikos additions to the spec template" in `docs/agents/issue-tracker.md`). It **reports; it never edits** the spec or the code unless the user asks after seeing the report.

## Input

A phase number or path: `/analyze-spec 29`, `/analyze-spec docs/specs/fase_29_spec.md`, optionally with `cierre` for the closing mode. No argument → the highest-numbered `docs/specs/fase_NN_spec.md`. Mode defaults to **pre-implementation** unless the user says `cierre`/"cerrar la fase" or the current branch already has commits implementing the spec (`git log main..HEAD`), in which case ask which mode they want.

## Mode A — pre-implementation

Read the whole spec. Then run these checks:

1. **Open questions.** Any `[NEEDS CLARIFICATION: …]` left → the spec is not ready. List each one with its section.

2. **Project invariants.** Read the sources, don't work from memory: `CLAUDE.md` (Architecture + Cross-cutting conventions), `backend/docs/BUSINESS_RULES.md`, and `frontend/docs/STATE_AND_FETCHING.md` if the spec touches the frontend. Those files win over this list. At minimum check that the spec doesn't:
   - use `float` for money (must be `Decimal` in schemas, `Numeric(14,2)` in models);
   - compute balances, budget progress, or dashboard aggregates in the frontend;
   - change `models.py` without an Alembic migration step (`/alembic-migration`);
   - change an API contract without a `[docs]` step updating **both** `backend/docs/API_REFERENCE.md` and `frontend/docs/API_CONTRACT.md`;
   - raise `HTTPException` from routers for a business rule instead of a `DomainError` subclass;
   - make system categories (`user_id = NULL`) editable/deletable, or skip ownership checks;
   - add a mutation without the query invalidations it needs, or call `api` with an absolute `/api/...` path;
   - propose new security/auth hardening that nobody asked for (out of priority since the 2026-09-19 pivot, see `CLAUDE.md`).

3. **Internal consistency.**
   - Every numbered decision appears in at least one `## Orden de ejecución` step, and every step names the decisions it implements.
   - Every decision that changes behavior has a matching testing decision (or an explicit reason why it's verified manually).
   - The files-touched table (if any) matches the steps; the out-of-scope section doesn't contradict a decision.
   - Terms are used consistently (same name for the same concept throughout; check `CONTEXT.md` if it exists).
   - Vague requirements without a checkable criterion ("rápido", "intuitivo", "robusto").

4. **Stale references** — Oikos's most common real failure (see "Hallazgos de exploración" in `fase_26_spec.md`). For every file path, function, component, endpoint, or env var the spec names, confirm it exists and still looks the way the spec assumes (use `graphify query`/`graphify explain` first, then grep/read the specific lines). Also look for **blast radius the spec missed**: other call sites of the thing being changed.

5. **Execution order.** Every step has an area tag (`[backend]`/`[frontend]`/`[docs]`/`[infra]`/`[verif]`) and a `Depende de:` line; no cycles; no `[P]` step touches the same files as another step that could run at the same time.

## Mode B — closing (`cierre`)

1. `git diff main...HEAD --stat` and `git log main..HEAD --oneline` (or the range the user gives).
2. For each numbered decision: **implemented / partial / missing / deviated**, pointing at the file(s). A deviation isn't automatically wrong — Fase 28 added two exception classes mid-implementation for good reasons — but it must be recorded in the spec or the changelog entry.
3. Files changed that no decision explains.
4. Testing decisions without a corresponding test in the diff.
5. Docs that should have moved and didn't: both API contract docs (if a contract changed), `backend/docs/BUSINESS_RULES.md` (if a rule changed), `docs/CHANGELOG.md` entry for the phase, `docs/ROADMAP.md` / `docs/TODO.md` items it closes, `CLAUDE.md` if an operational fact changed.
6. Suggest `/run-tests` if it hasn't been run on this branch — don't run it as part of this skill.

## Output

One table, most severe first, then a one-line verdict (`listo para implementar` / `listo para cerrar` / `bloqueado por N hallazgos CRÍTICO/ALTO`). Write it in Spanish, like the rest of Oikos's docs.

| Severidad | Check | Dónde (sección del spec / archivo) | Hallazgo | Recomendación |
|---|---|---|---|---|

- **CRÍTICO** — violates a project invariant (check 2), or an open `[NEEDS CLARIFICATION]`. Fix the spec; never dilute the rule to make the spec pass.
- **ALTO** — a stale reference or missed blast radius, a decision with no step, a missing migration or contract-docs step, a decision missing from the diff at close.
- **MEDIO** — a missing testing decision, bad or missing `[P]`/`Depende de:` tags, an unrecorded deviation.
- **BAJO** — terminology drift, vague wording, cosmetics.

If there are no findings, say so in one line. Don't pad the table.
