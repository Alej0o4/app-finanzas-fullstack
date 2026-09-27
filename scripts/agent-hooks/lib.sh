# Funciones compartidas por los hooks de agentes (Claude Code, Codex, OpenCode).
# Se carga con `. "$(dirname "$0")/lib.sh"`; no se ejecuta directo.

# Imprime una ruta absoluta por línea con los archivos que toca la llamada a herramienta.
#   - Con argumentos: cada argumento es una ruta (así llama el plugin de OpenCode).
#   - Sin argumentos: lee el payload JSON del hook por stdin. Claude Code y Codex usan el
#     mismo formato: `tool_input.file_path` (Write/Edit) o, en Codex, un parche de
#     `apply_patch` con encabezados `*** Add|Update|Delete File: <ruta>` / `*** Move to: <ruta>`.
hook_paths() {
  local base="$PWD" raw
  if [ "$#" -gt 0 ]; then
    raw=$(printf '%s\n' "$@")
  else
    local payload
    payload=$(cat)
    base=$(printf '%s' "$payload" | jq -r '.cwd // empty' 2>/dev/null)
    [ -n "$base" ] || base="$PWD"
    raw=$(
      printf '%s' "$payload" | jq -r '
        (.tool_input.file_path, .tool_input.filePath, .tool_input.path,
         (.tool_response | objects | .filePath)) // empty' 2>/dev/null
      printf '%s' "$payload" | jq -r '.tool_input | .. | strings' 2>/dev/null |
        sed -n -E 's/^\*\*\* (Add File|Update File|Delete File|Move to): (.*)$/\2/p'
    )
  fi
  printf '%s\n' "$raw" | while IFS= read -r p; do
    [ -n "$p" ] || continue
    case "$p" in /*) ;; *) p="$base/$p" ;; esac
    printf '%s\n' "$p"
  done | sort -u
}

# Raíz del checkout que contiene la ruta dada (funciona también dentro de un worktree).
repo_root_of() {
  git -C "$(dirname "$1")" rev-parse --show-toplevel 2>/dev/null
}

# Raíz del checkout principal: en un worktree, `backend/venv` no existe y se reutiliza el del
# checkout principal.
main_root_of() {
  local common
  common=$(git -C "$(dirname "$1")" rev-parse --path-format=absolute --git-common-dir 2>/dev/null) || return 1
  dirname "$common"
}
