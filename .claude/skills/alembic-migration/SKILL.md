---
name: alembic-migration
description: Generate and apply an Alembic migration for a backend schema change in Oikos. Use whenever a change to backend/app/models/models.py needs a corresponding database migration.
---

# Alembic Migration

Oikos manages schema exclusively through Alembic (`backend/alembic/`). There is no `create_all()` and no ad-hoc `_ensure_*_column()` helper anymore — every schema change goes through a reviewed migration. See CLAUDE.md and `docs/specs/fase_07_spec.md` for the history of why.

## Steps

1. Make the model change in `backend/app/models/models.py` first.
2. Generate the migration (from `backend/`, with the venv):
   ```sh
   cd backend && ./venv/bin/alembic revision --autogenerate -m "<short description>"
   ```
3. **Always read the generated file in `backend/alembic/versions/` by hand before applying it.** Autogenerate misses things: it won't detect renamed columns/tables (it drops+adds instead), doesn't infer `server_default` for backfilling existing rows on a new `NOT NULL` column, and doesn't know about custom constraints (like the `UNIQUE(user_id, category_id, month, year)` on `budgets`) unless they're expressed as SQLAlchemy-level constructs.
4. Fix the migration by hand if needed — e.g. add a `server_default` + a follow-up `op.alter_column` to drop the default, if backfilling a `NOT NULL` column on existing data.
5. Apply it:
   ```sh
   cd backend && ./venv/bin/alembic upgrade head
   ```
6. Verify: check the migration is idempotent-safe if it might run twice, and confirm `alembic downgrade -1` works if the change is meant to be reversible (not required for every migration, but check before assuming it).

## Notes

- Never suggest `Base.metadata.create_all()` as a shortcut — that's the pattern Phase 7 deliberately removed.
- If the change affects a shared API contract, remember the CLAUDE.md rule: update both `backend/docs/API_REFERENCE.md` and `frontend/docs/API_CONTRACT.md` in the same change.
