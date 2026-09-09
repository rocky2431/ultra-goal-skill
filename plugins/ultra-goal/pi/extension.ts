import { spawn } from "node:child_process";
import { readFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { Type } from "typebox";
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";

const scripts = join(dirname(fileURLToPath(import.meta.url)), "../skills/ultragoal/scripts");

// Run the existing Python contract, without a shell or a second state store.
export function python(args: string[], cwd: string, input = "", signal?: AbortSignal): Promise<{ code: number; stdout: string; stderr: string }> {
  return new Promise((resolve, reject) => {
    const child = spawn(process.env.ULTRA_GOAL_PYTHON || "python3", args, {
      cwd, stdio: "pipe", signal,
    });
    child.stdout.setEncoding("utf8");
    child.stderr.setEncoding("utf8");
    let stdout = "", stderr = "";
    child.stdout.on("data", data => { stdout += data; });
    child.stderr.on("data", data => { stderr += data; });
    child.on("error", reject);
    child.on("close", code => resolve({ code: code ?? 1, stdout, stderr }));
    child.stdin.on("error", () => {});
    child.stdin.end(input);
  });
}

export default function ultraGoal(pi: ExtensionAPI) {
  let recovery: string | undefined;
  let recoverySession: string | undefined;

  async function owned(ctx: ExtensionContext) {
    if (process.env.ULTRA_GOAL_HOOKS_DISABLED === "1") return false;
    try {
      const lines = (await readFile(join(ctx.cwd, ".goals/active"), "utf8")).trim().split(/\r?\n/);
      return lines.length === 2 && lines[1] === `session ${ctx.sessionManager.getSessionId()}`;
    } catch { return false; }
  }

  async function hook(ctx: ExtensionContext, script: string, name: string, extra = {}) {
    if (!await owned(ctx)) return undefined;
    const session = ctx.sessionManager.getSessionId();
    try {
      const result = await python([join(scripts, script), "--host", "pi"], ctx.cwd,
        JSON.stringify({ hook_event_name: name, cwd: ctx.cwd, session_id: session, ...extra }));
      if (session !== ctx.sessionManager.getSessionId() || result.code !== 0) return undefined;
      if (!result.stdout.trim()) return undefined;
      try { return JSON.parse(result.stdout); }
      catch { return { systemMessage: result.stdout.trim() }; }
    } catch { return undefined; } // Hook failures cannot stop unrelated work.
  }

  async function recover(ctx: ExtensionContext, source: string) {
    recovery = undefined;
    recoverySession = ctx.sessionManager.getSessionId();
    const result = await hook(ctx, "goal_session_start.py", "SessionStart", { source });
    recovery = result?.hookSpecificOutput?.additionalContext;
  }

  pi.on("session_start", async (event, ctx) => { await recover(ctx, event.reason === "resume" ? "resume" : "startup"); });
  pi.on("session_shutdown", async () => { recovery = undefined; recoverySession = undefined; });
  pi.on("session_before_compact", async (_event, ctx) => { await hook(ctx, "goal_pre_compact.py", "PreCompact"); });
  pi.on("session_compact", async (_event, ctx) => { await recover(ctx, "compact"); });
  pi.on("input", async (event, ctx) => {
    if (event.source !== "extension") await hook(ctx, "goal_prompt_submit.py", "UserPromptSubmit");
  });
  pi.on("before_agent_start", async (_event, ctx) => { await recover(ctx, "resume"); });
  pi.on("context", async (event, ctx) => {
    if (!recovery || recoverySession !== ctx.sessionManager.getSessionId() || !await owned(ctx)) return;
    return { messages: [...event.messages, {
      role: "custom" as const, customType: "ultra-goal-recovery", content: recovery,
      display: false, timestamp: Date.now(),
    }] };
  });
  pi.on("tool_result", async (event, ctx) => {
    if (event.toolName !== "bash") return;
    const name = event.isError ? "PostToolUseFailure" : "PostToolUse";
    await hook(ctx, event.isError ? "goal_tool_failure.py" : "goal_tool_success.py", name, {
      tool_name: "bash", tool_input: event.input,
      tool_response: event.content.filter(part => part.type === "text").map(part => part.text).join("\n"),
    });
  });
  pi.on("agent_end", async (event, ctx) => {
    const signal = ctx.signal;
    const last = [...event.messages].reverse().find(message => message.role === "assistant");
    // Aborts/provider failures must never trigger a corrective run.
    if (!last || last.stopReason !== "stop" || signal?.aborted || ctx.hasPendingMessages()) return;
    const result = await hook(ctx, "goal_stop.py", "Stop");
    if (signal?.aborted || ctx.hasPendingMessages()) return;
    if (result?.decision === "block") {
      pi.sendMessage({ customType: "ultra-goal-verification", content: result.reason, display: true },
        { deliverAs: "followUp", triggerTurn: true });
    } else if (result?.systemMessage && ctx.hasUI) {
      ctx.ui.notify(result.systemMessage, "info");
    }
  });

  pi.registerTool({
    name: "ultra_goal", label: "UltraGoal",
    description: "Use an already accepted UltraGoal contract. Arm or explicitly rebind with this Pi session's real ID; verify a completion claim, inspect the diff, or disarm on cancellation. Read the ultragoal Skill and goal-run instructions first. Arming does not schedule an unattended loop.",
    parameters: Type.Object({
      action: Type.Union(["session", "arm", "rebind", "verify", "diff", "disarm"].map(value => Type.Literal(value))),
      slug: Type.Optional(Type.String()), claim: Type.Optional(Type.String()),
      allowNoGit: Type.Optional(Type.Boolean()),
    }),
    async execute(_id, params, signal, _update, ctx) {
      const session = ctx.sessionManager.getSessionId();
      if (params.action === "session") {
        return { content: [{ type: "text", text: session }], details: { sessionId: session } };
      }
      if (!params.slug) throw new Error("A goal slug is required.");
      const args = [join(scripts, "goal_run.py"), params.action,
        "--root", ctx.cwd, "--session-id", session];
      if (params.claim !== undefined) args.push("--claim", params.claim);
      if (params.allowNoGit) args.push("--allow-no-git");
      args.push("--", params.slug);
      const result = await python(args, ctx.cwd, "", signal);
      if (result.code !== 0) throw new Error(result.stderr || result.stdout || `UltraGoal exited ${result.code}`);
      await recover(ctx, "resume");
      return { content: [{ type: "text", text: result.stdout }], details: { exitCode: result.code } };
    },
  });
}
