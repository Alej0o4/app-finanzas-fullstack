# CLAUDE.md

Las instrucciones del proyecto viven en `AGENTS.md` (fuente única para Claude Code, Codex y
OpenCode). Este archivo solo lo importa y agrega lo exclusivo de Claude Code.

@AGENTS.md

## Solo Claude Code

- Los subagentes de `.claude/agents/` y el MCP de `.mcp.json` se **generan** desde `.agents/`
  con `python3 scripts/sync-agents.py` — editar la fuente en `.agents/`, no los generados. Los
  hooks de `.claude/settings.json` llaman a `scripts/agent-hooks/`; la lógica se cambia ahí. Ver
  `docs/agents/harness.md`.
- Revisión de código (paso 9 de `docs/WORKFLOW.md`): `/code-review`.
- Hechos del proyecto que deban valer para cualquier herramienta van en `AGENTS.md` o `docs/`,
  no en la auto-memoria de Claude Code (Codex y OpenCode no la ven).
