#!/usr/bin/env bash
# Hook "después de editar": formatea y autocorrige lint en los archivos tocados.
#   backend/**/*.py          → ruff check --fix + ruff format
#   frontend/**/*.{ts,tsx}   → eslint --fix + prettier --write
# Nunca falla (siempre exit 0): formatear es una comodidad, el gate real es el pre-commit.
set -u
. "$(dirname "$0")/lib.sh"

# Busca un binario primero en el checkout actual y después en el principal (worktrees).
find_bin() { # <ruta-archivo> <subruta-del-binario>
  local root main
  root=$(repo_root_of "$1") || return 1
  main=$(main_root_of "$1") || main="$root"
  for r in "$root" "$main"; do
    [ -x "$r/$2" ] && { echo "$r/$2"; return 0; }
  done
  return 1
}

while IFS= read -r f; do
  [ -f "$f" ] || continue
  root=$(repo_root_of "$f") || continue
  case "$f" in
    "$root"/backend/*.py)
      ruff=$(find_bin "$f" backend/venv/bin/ruff || command -v ruff) || continue
      (cd "$root/backend" && "$ruff" check --fix "$f" >/dev/null 2>&1; "$ruff" format "$f" >/dev/null 2>&1)
      ;;
    "$root"/frontend/*.ts | "$root"/frontend/*.tsx)
      # eslint resuelve sus plugins desde frontend/node_modules del mismo checkout; en un
      # worktree sin `pnpm install` se omite en vez de usar los binarios del principal.
      bin="$root/frontend/node_modules/.bin"
      [ -x "$bin/eslint" ] || continue
      (cd "$root/frontend" && "$bin/eslint" --fix "$f" >/dev/null 2>&1; "$bin/prettier" --write "$f" >/dev/null 2>&1)
      ;;
  esac
done < <(hook_paths "$@")
exit 0
