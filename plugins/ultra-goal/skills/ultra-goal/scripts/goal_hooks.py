#!/usr/bin/env python3
"""Shared activation and fail-open plumbing for the goal hooks.

Every hook's first act is to decide whether a goal is active in this project.
Where none is, that decision is the entire run: nothing is read beyond one
marker file, nothing is written, no command is executed, and the exit code is 0.

That early exit is the only thing standing between an installed hook and a
project that never asked for one, so it is deliberately dumb: one file, one
line, no parsing that can fail in an interesting way. Every failure path in
this module ends in "not active" rather than in an exception.

The same applies to the handlers this module runs. A hook that raises must not
be able to stop the host from working - the historical failure here is a Stop
hook that blocked forever because its own check was broken.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any, Callable


GOALS_DIR = ".goals"
# The sections a run may never edit. Their digest is recorded by the gate on the
# first turn and compared on every later one.
FROZEN_SECTIONS = ("intent", "boundary", "anchor")
ACTIVE_MARKER = "active"
DISABLE_ENV = "ULTRA_GOAL_HOOKS_DISABLED"
# A slug names one artifact in `.goals/`. It is never a path.
SLUG_MAX = 100
# The marker's optional second line names the session that owns the run. A
# session id is ownership information, not an anti-forgery key: any process
# that can write files can write the marker. What the line buys is that a
# *different* session's ordinary hooks - a Stop that would gate, a prompt
# that would reset the streak, an injection that would hand over the spec -
# leave the run alone.
SESSION_MAX = 200
# The Stop registration in hooks/hooks.json declares this timeout, and the host
# kills the hook process when it expires. Every budget inside the gate has to
# fit under it, so the number lives here once and a test pins it against the
# manifest - two copies with no stated relationship is how a gate acquires a
# ceiling nobody chose.
#
# 600 is the hooks reference's documented default for a `command` hook, and it
# is used here for exactly that reason. The previous 200 was a number I picked,
# which capped every anchor in this design at under three minutes - so an anchor
# that legitimately takes five was permanently `unknown`, held there by a limit
# its owner never chose. That is the failure `## Stop condition` forbids, and it
# had migrated into the clock. A long anchor still costs only what the artifact
# declares: `budget:` is the owner's number, and this is only its ceiling.
HOOK_TIMEOUT_SECONDS = 600
# Headroom for reading the artifact, the log, and writing the event.
ANCHOR_BUDGET_CEILING = 570
DEFAULT_ANCHOR_BUDGET = 180


@dataclass(frozen=True)
class ActiveGoal:
    """The goal this project is currently running."""

    slug: str
    goals_dir: Path
    goal_path: Path
    events_path: Path
    decisions_path: Path
    marker_path: Path
    owner_session: str | None = None


@dataclass(frozen=True)
class HostFacts:
    """What a host will actually do with a blocked Stop.

    `continuation_budget` is how many times in a row this gate may block one
    host turn before it releases the stop with its own reason; `None` means no
    cap is known, so the gate's own ceiling is the only bound. The budget is
    one less than a host's documented cap where one exists, so the last word
    is the gate's reason and never the host's force-end warning - the host cap
    is the backstop, not the budget. Every number cites where it came from: a
    budget without a source is a constant copied from Claude Code.

    `chain_flag` names the Stop-input field through which the host itself
    reports whether this Stop is a continuation of a blocked one - an explicit
    false is a directly observed fresh chain, so the budget's count starts
    from zero rather than inheriting the log's tail. It is set only where the
    host's reference documents the field *and* its meaning; a field name
    without documented semantics is an inference, and this project does not
    mechanise on inference.
    """

    continuation_budget: int | None
    source: str
    chain_flag: str | None = None


HOSTS: dict[str, HostFacts] = {
    # Claude Code counts consecutive Stop blocks and force-ends at 8; the
    # count is raisable via CLAUDE_CODE_STOP_HOOK_BLOCK_CAP. Read from the
    # running 2.1.260 binary, whose "check stop_hook_active" advice is printed
    # only after the cap is exceeded - post-mortem advice, not general
    # guidance, and reading it as general guidance is how this gate came to
    # block exactly once per host turn.
    "claude": HostFacts(
        7,
        "host cap 8 consecutive blocks (CLAUDE_CODE_STOP_HOOK_BLOCK_CAP default, "
        "Claude Code 2.1.260 binary)",
        # The hooks reference documents the field, and the binary's cap
        # message states its meaning: true while this stop continues a
        # previously blocked one.
        chain_flag="stop_hook_active",
    ),
    # zCode's hooks reference: "After 3 consecutive continuations the run is
    # force-ended to prevent infinite loops" (zcode.z.ai/en/docs/hooks).
    "zcode": HostFacts(
        2,
        "host cap 3 consecutive continuations (zCode hooks reference)",
        # Declared degradation, and both halves are the reference's fault: it
        # lists stop_hook_active among Stop's input fields but spells no
        # semantics for it, and its exactly-seven event list includes no turn
        # boundary at all - so this host offers neither a readable chain flag
        # nor a turn identity, and the streak resets only on facts this gate
        # itself observed (an allow, or a chain-ender). What the run loses,
        # named: a blocked chain that ends without one of those - an owner
        # interrupt, an error, a session end - carries its tail into the next
        # turn, which can park one block early (budget 2, so one block of it
        # already spent). The release is loud and names its reason; what is
        # never claimed is a turn-scoped budget this host cannot observe.
        chain_flag=None,
    ),
    # Kimi triggers a blocking Stop only while `!stopHookContinuationUsed`
    # (0.40.1 binary: the flag is a local of runStepLoop, one call per host
    # turn, so one continuation per turn is the mechanical max) - its
    # reference documents no cap at all. The turn boundary is the host's own
    # TurnStarted event (registered: goal_turn_started.py), which fires for
    # every new turn whatever its origin - user, task or system_trigger -
    # and carries turn_id; the reference's UserPromptSubmit means only that a
    # user sent a message. The binary passes a stopHookActive input too, but
    # constant-false by construction (it is only read inside the !used
    # guard), so it carries no information.
    "kimi": HostFacts(
        1,
        "host triggers a blocking Stop at most once per turn (Kimi 0.40.1 binary)",
        chain_flag=None,
    ),
    # No cap in Codex's hooks reference and none visible in the 0.150.1
    # binary; the documented self-guard is the stop_hook_active input. UNVERIFIED
    # that unbounded blocking is allowed - if a hidden cap exists, the host's
    # force-end is the backstop.
    "codex": HostFacts(
        None,
        "no cap documented (Codex hooks reference) or visible in the 0.150.1 binary",
        # learn.chatgpt.com/docs/hooks: "Whether this turn was already
        # continued by Stop" - documented field and meaning.
        chain_flag="stop_hook_active",
    ),
}
# A host the table has never heard of gets the smallest documented budget
# rather than Claude's eight: an unknown cap can only be undershot safely.
UNKNOWN_HOST = HostFacts(
    1, "unknown host: the smallest budget any measured host allows"
)
# The shared hooks/hooks.json speaks Claude Code's format and is what an
# untagged invocation runs under; every other entry point tags itself.
DEFAULT_HOST = "claude"


def host_facts(host: str | None) -> HostFacts:
    return HOSTS.get(host or DEFAULT_HOST, UNKNOWN_HOST)


def _valid_slug(raw: str) -> str | None:
    slug = raw.strip()
    if not slug or len(slug) > SLUG_MAX:
        return None
    # The marker holds a slug, not a path. Traversal is not a goal.
    if slug != Path(slug).name or slug in {".", ".."}:
        return None
    if any(ch in slug for ch in ("/", "\\", "\0")):
        return None
    return slug


def _valid_session(raw: str) -> str | None:
    """A session token: one lineless, pathless, printable word.

    Claude Code and Codex send UUID-shaped ids; anything hostile-looking is
    ignored rather than rejected, because the marker is fail-open by design -
    an unreadable session line means an unclaimed goal, never a dead gate.
    """
    token = raw.strip()
    if not token or len(token) > SESSION_MAX:
        return None
    if token != Path(token).name or token in {".", ".."}:
        return None
    if any(ch in token for ch in ("/", "\\", "\0", " ", "\t")):
        return None
    if not token.isprintable():
        return None
    return token


def _read_marker(marker: Path) -> tuple[str | None, str | None]:
    """The marker's slug line and its optional `session <id>` line.

    Still deliberately dumb: fixed first line, one optional keyed line, and
    anything unparsable reads as absent rather than fatal.
    """
    try:
        lines = [
            line.strip()
            for line in marker.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except (OSError, UnicodeError):
        return None, None
    if not lines:
        return None, None
    session: str | None = None
    for line in lines[1:]:
        key, sep, value = line.partition(" ")
        if sep and key.lower() == "session":
            token = _valid_session(value)
            if token is not None:
                session = token
    return lines[0], session


def active_goal(cwd: Any) -> ActiveGoal | None:
    """Return the active goal for `cwd`, or None. Never raises."""
    try:
        if not isinstance(cwd, (str, Path)) or not str(cwd):
            return None
        goals = Path(cwd) / GOALS_DIR
        marker = goals / ACTIVE_MARKER
        if not marker.is_file():
            return None
        raw_slug, session = _read_marker(marker)
        slug = _valid_slug(raw_slug or "")
        if slug is None:
            return None
        goal = goals / f"{slug}.goal.md"
        if not goal.is_file():
            return None
        return ActiveGoal(
            slug=slug,
            goals_dir=goals,
            goal_path=goal,
            events_path=goals / f"{slug}.events.jsonl",
            decisions_path=goals / f"{slug}.decisions.md",
            marker_path=marker,
            owner_session=session,
        )
    except (OSError, UnicodeError, ValueError):
        return None


def event_session(event: dict[str, Any]) -> str | None:
    """The session identity the host put in the payload, where it does.

    Read only as `session_id`: the field the Claude Code hooks reference
    documents for every event, and the one the Codex Stop probe receipts
    carry. Kimi's Stop input is `{stopHookActive: ...}` and nothing else
    (0.40.1 binary), and zCode has never loaded a hook on this machine - so
    absence is normal there. An event with no session identity cannot be
    told apart from the owner's and is not excluded: a declared degradation,
    not a proxy read of a field no reference documents.
    """
    value = event.get("session_id")
    if isinstance(value, str):
        return _valid_session(value)
    return None


def owns_goal(goal: ActiveGoal, event: dict[str, Any]) -> bool:
    """Is this event the owning session's?

    Enforced exactly when both sides name a session: the marker's line and
    the event's `session_id`. Anything else - an unclaimed marker, an
    id-less event - passes, because an undistinguishable event is not
    evidence of a stranger.
    """
    session = event_session(event)
    if session is None or goal.owner_session is None:
        return True
    return session == goal.owner_session


def claim_session(goal: ActiveGoal, session: str) -> None:
    """Record `session` as the run's owner in the marker. First write wins.

    Called by the Stop hook the first time a session-carrying Stop arrives
    over an unclaimed goal. Concurrent first Stops race and the last writer
    wins - ownership information, not a lock.
    """
    try:
        goal.marker_path.write_text(
            f"{goal.slug}\nsession {session}\n", encoding="utf-8"
        )
    except (OSError, UnicodeError):
        pass


def emit(payload: dict[str, Any]) -> None:
    """Write one JSON object to stdout. Silent on failure."""
    try:
        sys.stdout.write(json.dumps(payload, ensure_ascii=False))
    except (TypeError, ValueError, OSError):
        pass


def run_hook(
    event_name: str,
    handler: Callable[[dict[str, Any], ActiveGoal, str | None], dict[str, Any] | None],
    stdin_text: str | None = None,
    env: dict[str, str] | None = None,
    host: str | None = None,
) -> int:
    """Run `handler` only when this really is `event_name` on an active goal.

    Returns an exit code. It is always 0: a hook that cannot decide must let
    the host continue. Blocking, where a hook is entitled to it, travels through the
    emitted JSON rather than through the exit code, so a crash can never be
    mistaken for a deliberate block.

    There is deliberately no `stop_hook_active` early exit here. That flag
    marks a continuation - a turn this gate itself kept alive - and the guard
    it used to implement made the gate block exactly once per host turn, which
    is the difference between a loop and a nudge. The guard against a gate
    that denies forever is the per-host continuation budget in `HOSTS`,
    counted from this gate's own events. The flag is still read, but only as
    a boundary fact and only for the hosts whose references document both the
    field and its meaning (Claude Code and Codex spell `stop_hook_active`;
    Kimi's binary passes a constant camelCase `stopHookActive` that carries
    no information) - an explicit false tells the gate a fresh chain began,
    it never suppresses the check itself.
    """
    try:
        environ = os.environ if env is None else env
        if environ.get(DISABLE_ENV) == "1":
            return 0

        raw = sys.stdin.read() if stdin_text is None else stdin_text
        try:
            event = json.loads(raw)
        except (json.JSONDecodeError, UnicodeError, TypeError):
            return 0
        if not isinstance(event, dict):
            return 0
        if event.get("hook_event_name") != event_name:
            return 0

        goal = active_goal(event.get("cwd"))
        if goal is None:
            return 0
        if not owns_goal(goal, event):
            # Another session's event over this cwd's goal: not its run to
            # gate, inject into, or reset. Silent and side-effect free.
            return 0

        payload = handler(event, goal, host)
        if payload:
            emit(payload)
        return 0
    except BaseException:  # noqa: BLE001 - a hook must never take the host down
        return 0


def append_event(goal: ActiveGoal, entry: dict[str, Any]) -> None:
    """Append one line to the goal's event log. Silent on failure."""
    try:
        goal.goals_dir.mkdir(parents=True, exist_ok=True)
        with goal.events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
    except (OSError, UnicodeError, TypeError, ValueError):
        pass


def read_events(goal: ActiveGoal) -> list[dict[str, Any]]:
    """Read the goal's event log. A malformed line is skipped, not fatal."""
    events: list[dict[str, Any]] = []
    try:
        if not goal.events_path.is_file():
            return events
        for line in goal.events_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except (json.JSONDecodeError, UnicodeError):
                continue
            if isinstance(entry, dict):
                events.append(entry)
    except (OSError, UnicodeError):
        return events
    return events


def sections(text: str) -> dict[str, str]:
    """Map lowercased `## ` headings to their body text."""
    found: dict[str, str] = {}
    current: str | None = None
    body: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            if current is not None:
                found[current] = "\n".join(body)
            current = line[3:].strip().lower()
            body = []
        elif current is not None:
            body.append(line)
    if current is not None:
        found[current] = "\n".join(body)
    return found


def frozen_digest(spec: str) -> str:
    """Digest exactly the sections the run may not edit.

    Machine-written and machine-compared, which is the only reason it is worth
    anything: the model authors the artifact, so its own account of whether the
    goal moved is a claim. This is not tamper-proof - an agent can write any
    file it can read - but the event log is committed, so a moved goalpost turns
    up in `--audit` and in `git log` instead of passing silently. Making it
    visible is the achievable property; making it impossible is not.
    """
    parts = sections(spec)
    joined = "\n".join(parts.get(name, "") for name in FROZEN_SECTIONS)
    return hashlib.sha256(joined.encode("utf-8", "replace")).hexdigest()[:12]
