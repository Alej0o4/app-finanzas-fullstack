#!/usr/bin/env bash
# Configuración única por clon: activa los git hooks versionados y regenera la config de
# agentes. Idempotente. Ver docs/agents/harness.md.
set -eu
root=$(git rev-parse --show-toplevel)
cd "$root"

git config core.hooksPath scripts/git-hooks
chmod +x scripts/git-hooks/* scripts/agent-hooks/*.sh scripts/sync-agents.py
python3 scripts/sync-agents.py

command -v jq >/dev/null || echo "⚠ falta jq: los hooks de agentes lo necesitan para leer el payload (sudo apt install jq)"

cat <<'EOF'
✓ git hooks activos (core.hooksPath=scripts/git-hooks)
✓ config de agentes generada desde .agents/

Pasos manuales por herramienta:
  - Codex: aprobar los hooks del proyecto una vez con /hooks (Codex los confía por hash; si
    cambia .codex/hooks.json hay que volver a aprobarlos) y marcar el proyecto como confiable
    para que lea .codex/config.toml.
  - Claude Code / OpenCode: nada, leen su config al abrir el proyecto.
EOF
