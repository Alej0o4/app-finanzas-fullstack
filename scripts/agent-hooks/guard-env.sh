#!/usr/bin/env bash
# Hook "antes de editar": bloquea la escritura directa de archivos .env (secretos reales).
# Las plantillas (.env.example) sí se pueden editar.
#
# Contrato común a las tres herramientas: exit 0 = permitir; exit 2 + motivo en stderr = bloquear.
# Claude Code y Codex (PreToolUse) interpretan exit 2 como denegación; el plugin de OpenCode
# lanza un error con el stderr.
set -u
. "$(dirname "$0")/lib.sh"

while IFS= read -r f; do
  name=$(basename "$f")
  case "$name" in
    .env.example | *.env.example) ;;
    .env | .env.* | *.env)
      echo "Bloqueado: edición directa de $name (usar .env.example para plantillas; los secretos los edita el dueño a mano)." >&2
      exit 2
      ;;
  esac
done < <(hook_paths "$@")
exit 0
