// Exercise the actual Pi loader/registered handlers against the Python gate.
import assert from "node:assert/strict";
import { readFile, writeFile, access, unlink } from "node:fs/promises";
import { resolve, join } from "node:path";
import { pathToFileURL } from "node:url";

const [sdk, root, extension] = process.argv.slice(2);
const { loadExtensions } = await import(pathToFileURL(join(sdk, "dist/core/extensions/loader.js")));
const loaded = await loadExtensions([resolve(extension)], root);
assert.deepEqual(loaded.errors, []);
const ext = loaded.extensions[0];
const sent = [], notifications = [];
loaded.runtime.sendMessage = (message, options) => { sent.push({ message, options }); };
let session = "foreign-session";
const ctx = {
  cwd: root, hasUI: true, hasPendingMessages: () => false,
  sessionManager: { getSessionId: () => session },
  ui: { notify: text => notifications.push(text) },
};
async function emit(name, event = {}) {
  const results = [];
  for (const handler of ext.handlers.get(name) ?? []) results.push(await handler(event, ctx));
  return results.find(value => value !== undefined);
}
const candidate = join(root, ".goals/demo.candidate");
const events = join(root, ".goals/demo.events.jsonl");
const normalEnd = { messages: [{ role: "assistant", stopReason: "stop" }] };
await writeFile(candidate, "claiming completion\n");
await emit("session_start", { reason: "startup" });
assert.equal(await emit("context", { messages: [] }), undefined);
await emit("agent_end", normalEnd);
assert.equal(sent.length, 0);
await access(candidate); // Foreign session must not consume a candidate or log.
await assert.rejects(access(events));

session = "session-aaa";
await emit("session_start", { reason: "resume" });
assert.match((await emit("context", { messages: [] })).messages[0].content, /active goal/);
await emit("session_before_compact");
await emit("session_compact");
assert.match((await emit("context", { messages: [] })).messages[0].content, /just compacted/);
await emit("input", { source: "interactive" });
await emit("agent_end", { messages: [{ role: "assistant", stopReason: "aborted" }] });
await access(candidate); // Cancellation cannot launch or consume verification.
assert.equal(sent.length, 0);
await emit("agent_end", normalEnd);
assert.equal(sent.length, 1);
assert.equal(sent[0].options.deliverAs, "followUp");
assert.equal(sent[0].options.triggerTurn, true);
await assert.rejects(access(candidate));
await writeFile(candidate, "claim again\n");
await emit("input", { source: "extension" }); // Corrective follow-up does not reset budget.
await emit("agent_end", normalEnd);
assert.equal(sent.length, 1);
assert.match(notifications.at(-1), /bound|budget/);

await emit("input", { source: "rpc" });
await writeFile(join(root, "result.txt"), "done\n");
const tool = ext.tools.get("ultra_goal").definition;
assert.equal((await tool.execute("test", { action: "session" }, undefined, undefined, ctx)).content[0].text, session);
await assert.rejects(tool.execute("test", { action: "arm", slug: "--help" }, undefined, undefined, ctx));
await assert.rejects(tool.execute("test", { action: "arm", slug: "../../escape" }, undefined, undefined, ctx));
const verified = await tool.execute("test", { action: "verify", slug: "demo", claim: "result exists" }, undefined, undefined, ctx);
assert.equal(JSON.parse(verified.content[0].text).verification_passed, true);
await emit("agent_end", normalEnd); // Ordinary stop after explicit verification is inert.
assert.equal(sent.length, 1);
await emit("input", { source: "rpc" });
const abort = new AbortController();
ctx.signal = abort.signal;
await unlink(join(root, "result.txt"));
await writeFile(candidate, "candidate interrupted during verification\n");
const checking = emit("agent_end", normalEnd);
abort.abort();
await checking;
assert.equal(sent.length, 1);
const before = await readFile(events, "utf8");
session = "foreign-session";
await emit("session_start", { reason: "fork" });
assert.equal(await emit("context", { messages: [] }), undefined);
await assert.rejects(tool.execute("test", { action: "verify", slug: "demo", claim: "wrong session" }, undefined, undefined, ctx));
assert.equal(await readFile(events, "utf8"), before);
await emit("session_shutdown");
console.log("PASS: Pi loader, recovery, compaction, session isolation, cancellation, bounded follow-up, native-ID verification");
