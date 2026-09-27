#!/usr/bin/env python3
"""Proyecta la config canónica de agentes (`.agents/`) a cada herramienta.

Fuentes (se editan a mano):
  .agents/agents/<nombre>.md   subagentes: frontmatter `name`, `description`, `tools`
                               (nombres de Claude Code), `claude-model` opcional; el cuerpo
                               es el prompt.
  .agents/mcp.json             servidores MCP: {"servers": {<nombre>: {command, args, env?}}}

Destinos (generados, no editar):
  .claude/agents/*.md          Claude Code
  .opencode/agents/*.md        OpenCode
  .codex/agents/*.toml         Codex
  .mcp.json                    MCP de Claude Code
  opencode.json → "mcp"        MCP de OpenCode (el resto del archivo se conserva)
  .codex/config.toml           MCP de Codex

Uso:
  python3 scripts/sync-agents.py          # escribe los destinos
  python3 scripts/sync-agents.py --check  # exit 1 si algún destino está desactualizado
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_AGENTS = ROOT / ".agents" / "agents"
SRC_MCP = ROOT / ".agents" / "mcp.json"
BANNER = "GENERADO por scripts/sync-agents.py desde {src} — no editar a mano."
WRITE_TOOLS = {"Write", "Edit", "NotebookEdit"}


def parse_agent(path: Path) -> dict:
    text = path.read_text()
    if not text.startswith("---\n"):
        sys.exit(f"{path}: falta el frontmatter")
    head, body = text[4:].split("\n---\n", 1)
    meta = {}
    for line in head.splitlines():
        if line.strip():
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
    for key in ("name", "description"):
        if not meta.get(key):
            sys.exit(f"{path}: falta `{key}` en el frontmatter")
    tools = [t.strip() for t in meta.get("tools", "").split(",") if t.strip()]
    return {
        "name": meta["name"],
        "description": meta["description"],
        "claude_model": meta.get("claude-model"),
        "tools": tools,
        "can_write": not tools or bool(WRITE_TOOLS & set(tools)),
        "can_bash": not tools or "Bash" in tools,
        "body": body.strip() + "\n",
        "src": path.relative_to(ROOT).as_posix(),
    }


def yaml_str(value: str) -> str:
    # JSON es YAML válido: comillas dobles con escapes, a salvo de `:` y `#` en la descripción.
    return json.dumps(value, ensure_ascii=False)


def toml_str(value: str) -> str:
    # Las cadenas JSON son cadenas básicas TOML válidas.
    return json.dumps(value, ensure_ascii=False)


def toml_multiline(value: str) -> str:
    if "'''" not in value:
        return "'''\n" + value + "'''"
    return toml_str(value)


def claude_agent(a: dict) -> str:
    lines = ["---", f"name: {a['name']}", f"description: {yaml_str(a['description'])}"]
    if a["tools"]:
        lines.append("tools: " + ", ".join(a["tools"]))
    if a["claude_model"]:
        lines.append(f"model: {a['claude_model']}")
    lines += ["---", "", f"<!-- {BANNER.format(src=a['src'])} -->", "", a["body"]]
    return "\n".join(lines)


def opencode_agent(a: dict) -> str:
    lines = [
        "---",
        f"description: {yaml_str(a['description'])}",
        "mode: subagent",
        "permission:",
        f"  edit: {'allow' if a['can_write'] else 'deny'}",
        f"  bash: {'allow' if a['can_bash'] else 'deny'}",
        "---",
        "",
        f"<!-- {BANNER.format(src=a['src'])} -->",
        "",
        a["body"],
    ]
    return "\n".join(lines)


def codex_agent(a: dict) -> str:
    sandbox = "workspace-write" if a["can_write"] else "read-only"
    return "\n".join(
        [
            f"# {BANNER.format(src=a['src'])}",
            f"name = {toml_str(a['name'])}",
            f"description = {toml_str(a['description'])}",
            f'sandbox_mode = "{sandbox}"',
            f"developer_instructions = {toml_multiline(a['body'])}",
            "",
        ]
    )


def mcp_outputs(servers: dict, outputs: dict) -> None:
    src = SRC_MCP.relative_to(ROOT).as_posix()

    claude = {"mcpServers": {}}
    for name, s in servers.items():
        entry = {"command": s["command"], "args": s.get("args", [])}
        if s.get("env"):
            entry["env"] = s["env"]
        claude["mcpServers"][name] = entry
    outputs[ROOT / ".mcp.json"] = json.dumps(claude, indent=2, ensure_ascii=False) + "\n"

    oc_path = ROOT / "opencode.json"
    oc = json.loads(oc_path.read_text()) if oc_path.exists() else {}
    oc["mcp"] = {}
    for name, s in servers.items():
        entry = {"type": "local", "command": [s["command"], *s.get("args", [])], "enabled": True}
        if s.get("env"):
            entry["environment"] = s["env"]
        oc["mcp"][name] = entry
    outputs[oc_path] = json.dumps(oc, indent=2, ensure_ascii=False) + "\n"

    toml = [f"# {BANNER.format(src=src)}", ""]
    for name, s in servers.items():
        toml.append(f"[mcp_servers.{name}]")
        toml.append(f"command = {toml_str(s['command'])}")
        toml.append("args = [" + ", ".join(toml_str(x) for x in s.get("args", [])) + "]")
        if s.get("env"):
            toml.append(f"[mcp_servers.{name}.env]")
            toml += [f"{k} = {toml_str(v)}" for k, v in s["env"].items()]
        toml.append("")
    outputs[ROOT / ".codex" / "config.toml"] = "\n".join(toml)


def build() -> tuple[dict, list]:
    outputs: dict[Path, str] = {}
    targets = {
        ROOT / ".claude" / "agents": (".md", claude_agent),
        ROOT / ".opencode" / "agents": (".md", opencode_agent),
        ROOT / ".codex" / "agents": (".toml", codex_agent),
    }
    agents = [parse_agent(p) for p in sorted(SRC_AGENTS.glob("*.md"))]
    for directory, (ext, render) in targets.items():
        for a in agents:
            outputs[directory / f"{a['name']}{ext}"] = render(a)
    # Archivos generados de agentes que ya no tienen fuente → se borran.
    stale = [
        p
        for directory, (ext, _) in targets.items()
        if directory.exists()
        for p in directory.glob(f"*{ext}")
        if p not in outputs
    ]
    if SRC_MCP.exists():
        mcp_outputs(json.loads(SRC_MCP.read_text())["servers"], outputs)
    return outputs, stale


def main() -> int:
    check = "--check" in sys.argv[1:]
    outputs, stale = build()
    drift = [p for p, c in outputs.items() if not p.exists() or p.read_text() != c]
    if check:
        for p in drift + stale:
            print(f"desactualizado: {p.relative_to(ROOT)}")
        if drift or stale:
            print("Corre: python3 scripts/sync-agents.py")
            return 1
        return 0
    for p in drift:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(outputs[p])
        print(f"escrito: {p.relative_to(ROOT)}")
    for p in stale:
        p.unlink()
        print(f"borrado: {p.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
