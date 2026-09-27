---
name: run-tests
description: Run the full backend and frontend check suite (pytest, ruff, eslint, prettier) for Oikos. Use before considering a change done, since there's no CI yet — this is the manual substitute.
---

# Run Tests

Oikos has no CI/CD configured yet (tracked in `docs/TODO.md` under "Solo si el proyecto crece"). This skill is the manual pre-commit gate until that exists.

## Steps

Run all of these from the repo root. Report failures grouped by suite; don't stop at the first failure — run everything and summarize.

1. **Backend tests**:
   ```sh
   cd backend && ./venv/bin/pytest -v
   ```

2. **Backend lint**:
   ```sh
   cd backend && ./venv/bin/ruff check . && ./venv/bin/ruff format --check .
   ```

3. **Frontend lint**:
   ```sh
   cd frontend && pnpm lint
   ```

4. **Frontend format check**:
   ```sh
   cd frontend && pnpm format:check
   ```

## Notes

- There is no frontend test suite yet (Vitest + React Testing Library is backlog, see `docs/TODO.md`) and no `tsc` typecheck script configured — don't invent one, just note the gap if relevant.
- If `ruff format --check` or `pnpm format:check` fail, offer to run the writing variant (`ruff format .` / `pnpm format`) rather than hand-fixing formatting.
- A failing test is not automatically a regression to fix silently — report what failed and let the user decide, unless they've asked you to fix as you go.
