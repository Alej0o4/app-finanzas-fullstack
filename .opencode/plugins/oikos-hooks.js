// Adaptador de OpenCode para los hooks compartidos de Oikos (scripts/agent-hooks/).
// La lógica vive en los scripts; aquí solo se traduce el evento de OpenCode al mismo payload
// JSON que usan Claude Code y Codex ({ cwd, tool_name, tool_input }) y se pasa por stdin.
//   - tool.execute.before → guard-env.sh (exit 2 = bloquear, motivo en stderr)
//   - tool.execute.after  → format-file.sh (nunca bloquea)
import { spawnSync } from "child_process";
import { join } from "path";

const EDIT_TOOLS = new Set(["edit", "write", "patch", "apply_patch", "multiedit"]);

export const OikosHooks = async ({ directory, worktree }) => {
  const root = worktree || directory;
  const argsByCall = new Map();

  const run = (script, input) =>
    spawnSync(join(root, "scripts", "agent-hooks", script), [], {
      input: JSON.stringify({ cwd: directory, tool_name: input.tool, tool_input: input.args }),
      encoding: "utf8",
      timeout: 60_000,
    });

  return {
    "tool.execute.before": async (input, output) => {
      if (!EDIT_TOOLS.has(input.tool)) return;
      argsByCall.set(input.callID, output.args);
      const r = run("guard-env.sh", { tool: input.tool, args: output.args });
      if (r.status === 2) throw new Error(r.stderr.trim() || "Bloqueado por guard-env.sh");
    },
    "tool.execute.after": async (input) => {
      if (!EDIT_TOOLS.has(input.tool)) return;
      const args = argsByCall.get(input.callID);
      argsByCall.delete(input.callID);
      if (args) run("format-file.sh", { tool: input.tool, args });
    },
  };
};
