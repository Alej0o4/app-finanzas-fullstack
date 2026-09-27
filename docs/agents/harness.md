# Harness de agentes — Oikos

> Cómo está armado el soporte para agentes de código (Claude Code, Codex, OpenCode) y qué tocar
> para cambiarlo. Desde el **2026-09-27** el harness no depende de ninguna herramienta: el
> contenido vive en formatos neutros y cada herramienta tiene solo una capa delgada que apunta a
> él. El *qué hacer* sigue en `docs/WORKFLOW.md`; este archivo cubre el *con qué*.

## Principio

**Una fuente por concepto, adaptadores por herramienta.** Si algo se edita en más de un lugar,
es un error de diseño del harness: o se genera o se referencia.

| Concepto | Fuente (se edita) | Claude Code | Codex | OpenCode |
|---|---|---|---|---|
| Instrucciones | `AGENTS.md` | `CLAUDE.md` → `@AGENTS.md` | nativo | nativo |
| Flujo de trabajo | `docs/WORKFLOW.md`, `docs/agents/*` | vía `AGENTS.md` | vía `AGENTS.md` | vía `AGENTS.md` |
| Skills | `.agents/skills/<n>/SKILL.md` | symlinks en `.claude/skills/` | nativo | nativo |
| Subagentes | `.agents/agents/<n>.md` | `.claude/agents/` ⚙ | `.codex/agents/*.toml` ⚙ | `.opencode/agents/` ⚙ |
| MCP | `.agents/mcp.json` | `.mcp.json` ⚙ | `.codex/config.toml` ⚙ | `opencode.json` → `mcp` ⚙ |
| Hooks de edición | `scripts/agent-hooks/*.sh` | `.claude/settings.json` | `.codex/hooks.json` | `.opencode/plugins/oikos-hooks.js` |
| Gate de commit | `scripts/git-hooks/pre-commit` | ← git, igual para todas → | | |

⚙ = generado por `python3 scripts/sync-agents.py`; no se edita a mano (lleva un encabezado
"GENERADO").

## Puesta en marcha (una vez por clon)

```sh
scripts/setup-agent-harness.sh
```

Activa `core.hooksPath=scripts/git-hooks` y regenera la config de agentes. Además, en **Codex**:
aprobar los hooks del proyecto con `/hooks` (Codex los confía por hash; si cambia
`.codex/hooks.json` hay que volver a aprobarlos) y marcar el proyecto como confiable para que lea
`.codex/config.toml`. Claude Code y OpenCode no necesitan pasos manuales.

Requisitos: `jq` y `python3` (los hooks y el sync los usan).

## Cómo cambiar cada cosa

### Instrucciones del proyecto

Editar `AGENTS.md`. Solo lo exclusivo de una herramienta va en su archivo (`CLAUDE.md` para
Claude Code). Hechos que deban sobrevivir a un cambio de herramienta **no** van en la memoria
propia de una herramienta (la auto-memoria de Claude Code, por ejemplo): van en `AGENTS.md` o en
`docs/`.

### Skills

- **Nueva skill propia:** crear `.agents/skills/<nombre>/SKILL.md` con frontmatter `name`
  (minúsculas y guiones, igual al nombre de la carpeta) y `description` (cuándo usarla — es lo
  que dispara la invocación implícita). Después, para Claude Code:
  `ln -s ../../.agents/skills/<nombre> .claude/skills/<nombre>`.
- Escribir las instrucciones sin nombres de herramientas de un agente concreto ("carga la skill
  X", no "call the Skill tool"; "si puedes lanzar subagentes…", no "use the Agent tool").
- **Skills vendoreadas** (`grilling`, `to-spec`, `tdd`, `codebase-design`,
  `improve-codebase-architecture`, `setup-matt-pocock-skills`): fijadas en `skills-lock.json`
  desde `mattpocock/skills`. No editarlas; una actualización pisa los cambios. Las adaptaciones de
  Oikos van en `docs/agents/`.
- **`graphify`:** la gestiona el CLI de graphify en `.claude/skills/graphify/`;
  `.agents/skills/graphify` es un symlink hacia ahí para que Codex y OpenCode la vean.

### Subagentes

Editar o crear `.agents/agents/<nombre>.md`:

```markdown
---
name: backend-engineer
description: Cuándo usarlo (lo lee el agente principal para decidir delegar).
tools: Read, Write, Edit, Bash, Grep, Glob     # nombres de Claude Code
claude-model: sonnet                           # opcional, solo aplica a Claude Code
---

Prompt del subagente.
```

Luego `python3 scripts/sync-agents.py`. `tools` se traduce a permisos: sin `Write`/`Edit` →
`edit: deny` en OpenCode y `sandbox_mode = "read-only"` en Codex; sin `Bash` → `bash: deny` en
OpenCode.

Invocación: Claude Code y OpenCode los delegan solos según la `description` (o `@nombre` en
OpenCode); en Codex se piden por nombre en el prompt ("que `qa-engineer` revise…").

### MCP

Editar `.agents/mcp.json` (`{"servers": {<nombre>: {command, args, env?}}}`) y correr
`python3 scripts/sync-agents.py`. El sync reescribe solo la clave `mcp` de `opencode.json`; el
resto de ese archivo (modelo, permisos, comandos) se edita a mano.

### Hooks

La lógica está en `scripts/agent-hooks/`:

| Script | Cuándo | Qué hace |
|---|---|---|
| `guard-env.sh` | antes de editar | bloquea escribir `.env`/`.env.*`/`*.env` (no `.env.example`) |
| `format-file.sh` | después de editar | `ruff check --fix` + `ruff format` (backend) / `eslint --fix` + `prettier --write` (frontend) |

Contrato común: leen el payload JSON del hook por stdin (formato de Claude Code y Codex:
`tool_input.file_path`, o un parche de `apply_patch` con `*** Update File: <ruta>`) o rutas
como argumentos. `exit 2` + motivo en stderr = bloquear. El plugin de OpenCode arma el mismo JSON
y se lo pasa por stdin, así que un hook nuevo se escribe una vez y se registra en los tres
adaptadores.

Solo en Claude Code queda además `graphify hook-guard` (recordatorio de usar el grafo); en
OpenCode lo cubre `.opencode/plugins/graphify.js` (generado por `graphify opencode install`).

### Gate de commit

`scripts/git-hooks/pre-commit` corre con cualquier herramienta y también sin agente: bloquea
`.env` reales en stage, verifica que los archivos generados estén al día
(`sync-agents.py --check`) y pasa ruff / eslint / prettier sobre los archivos en stage. No corre
pytest (eso sigue siendo la skill `run-tests`). Saltarlo en una emergencia:
`git commit --no-verify`.

## Qué no es portable (y está bien)

- **Revisión de código:** cada herramienta trae la suya (`/code-review`, `/review`, skill
  `code-review` global de OpenCode) — ver el paso 9 de `docs/WORKFLOW.md`.
- **Worktrees automáticos:** Claude Code los crea en `.claude/worktrees/`; en las demás,
  `git worktree add` a mano.
- **Comandos de OpenCode** (`lint-frontend`, `tech-debt` en `opencode.json`): atajos propios de
  OpenCode; lo portable son las skills.
