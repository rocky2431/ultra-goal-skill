#!/usr/bin/env python3
"""Arm a validated goal: the fence that validates and binds an authorized run.

Arming used to be a shell fence in the command body, and three findings were
its fault class: a script path no root variable reached, a validation step
whose failure prose could be talked past, and an unconditional overwrite of
`.goals/active` that silently retargeted every hook in the directory. A
function call whose exception is the refusal makes those structurally
impossible rather than guarded - which is why this file exists even though
the shell fence could have been patched.

What arming must establish, before any Stop can run:

- the artifact and its decisions record exist and validate (errors refuse);
- another goal is not already armed - a different slug refuses, because
  overwriting it redirected an owner-authorized run, and disarming is an
  explicit owner act (`disarm`);
- the run's authorized spec baseline is recorded once, from the artifact as
  it stands at arming, into `.goals/<slug>.spec.baseline`. The gate compares
  every later Stop against that file and never against a digest found in
  the event log - the run can write the log, and round 4's laundering probe
  replaced it with a run-authored row carrying an edited digest and was
  allowed through. The file is deliberately NOT gitignored (`.goals/.gitignore`
  covers only the run-private files), so an authorized commit can preserve it
  and make later rewrites visible;
- the review baseline is the Git revision by default, or `none` only after an
  explicit `--allow-no-git` choice; it is write-once, so a re-arm cannot hand
  the reviewer an empty range;
- `.goals/.gitignore` names the run-private files, `*.candidate` included -
  a live claim must not ride into a commit.

`diff` prints the reviewer's range from the same baseline file the review
and critic skills read, with the same ancestor guard: a baseline that is no
longer an ancestor of HEAD means history moved under the run, and the
honest output says the range is unreliable instead of trusting the diff.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import re
import subprocess
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent))
from goal_hooks import (  # noqa: E402
    SPEC_BASELINE_SUFFIX,
    _read_marker,
    _valid_slug,
    _valid_session,
    frozen_digest,
    read_events,
    active_goal,
    ActiveGoal,
    append_event,
    completion_attempt,
    completion_attempts,
)
from validate_artifact import validate_paths  # noqa: E402
from goal_contract import pin_verification, check_protection, input_digest  # noqa: E402


GIT_BASELINE_SUFFIX = ".baseline"
IGNORE_ENTRIES = (".work/", "active", "*.candidate", "*.verification.lock")
PACKAGE_CONFIRMATION = "confirm package checkpoint"
FROZEN_CONFIRMATION = re.compile(r"\bfrozen:([0-9a-f]{12})\b", re.I)


def package_confirmation_digest(path: Path) -> str | None:
    """Read the final owner row without treating it as authenticated consent."""
    text = path.read_text(encoding="utf-8").split("\n## ", 1)[0]
    rows = [line.strip() for line in text.splitlines() if line.strip().startswith("|")]
    header = next((row for row in rows if "decision" in row.lower()), None)
    if header is None:
        return None
    headings = [cell.strip().lower() for cell in header.strip("|").split("|")]
    if not {"decision", "why", "who"} <= set(headings):
        return None
    decision_index, why_index, who_index = (
        headings.index("decision"), headings.index("why"), headings.index("who")
    )
    for row in rows[rows.index(header) + 1 :]:
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        if len(cells) <= max(decision_index, why_index, who_index):
            continue
        if (cells[decision_index].strip("` ").lower() == PACKAGE_CONFIRMATION
                and cells[who_index].lower() == "owner"):
            match = FROZEN_CONFIRMATION.search(cells[why_index])
            return match.group(1).lower() if match else None
    return None


def initiating_session(explicit: str | None = None) -> str:
    """Resolve a native identity before arming; never infer it from a hook.

    A nested host can inherit even a single parent's identity variable.
    Therefore no environment variable is selected implicitly.
    """
    if explicit is not None:
        session = _valid_session(explicit)
        if session is not None:
            return session
        raise ValueError("Invalid --session-id; use the current native session ID.")
    raise ValueError(
        "An explicit initiating session ID is required before arming. Pass "
        "--session-id <current-native-session-id>; do not guess, copy another "
        "task's ID, or wait for the first Stop to claim this goal."
    )


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    command = ["git", "-C", str(root), *args]
    try:
        return subprocess.run(command, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as exc:
        return subprocess.CompletedProcess(command, 127, "", str(exc))


def _write_once(path: Path, text: str) -> bool:
    """Write `text` to `path` only if it holds nothing. True if it holds it now.

    Write-once is what makes a baseline evidence rather than a suggestion:
    the arming revision survives re-arms and restarts, and a run that wants
    it moved has to delete it. Git preserves that change only if committed.
    """
    if path.is_file() and path.read_text(encoding="utf-8").strip():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


def _armed_slug(marker: Path) -> str | None:
    """The marker's slug line - the first line, never the whole file.

    Arming writes both slug and session identity. Compare only the slug here;
    ownership checks are separate and a rebind explicitly changes the session.
    """
    slug, _session = _read_marker(marker)
    return slug


def arm(
    root: Path,
    slug: str,
    session_id: str | None = None,
    allow_no_git: bool = False,
) -> str:
    if _valid_slug(slug) != slug:
        raise ValueError("Expected a goal slug, not a path.")
    session = initiating_session(session_id)
    goals = root / ".goals"
    goal_file = goals / f"{slug}.goal.md"
    decisions = goals / f"{slug}.decisions.md"
    if not goal_file.is_file() or not decisions.is_file():
        raise ValueError(
            "The goal or paired decisions record is missing. Do not author one "
            "here - that is the interview's job, and a run against an artifact "
            "nobody agreed to is the failure this design exists to prevent."
        )
    marker = goals / "active"
    legacy_resume = marker.is_file() and _armed_slug(marker) == slug
    report = validate_paths([str(goal_file), str(decisions)])
    errors = [
        finding for finding in report.findings
        if finding.severity == "error"
        and not (legacy_resume and finding.code.startswith("OWNER_CONFIRMATION_"))
    ]
    if errors:
        raise ValueError(
            "Artifact validation failed: " + "; ".join(f.message for f in errors)
        )

    if not legacy_resume:
        recorded = package_confirmation_digest(decisions)
        current = frozen_digest(goal_file.read_text(encoding="utf-8"))
        if recorded != current:
            raise ValueError(
                "OWNER_CONFIRMATION_STALE: the package confirmation does not match "
                "the current frozen goal terms. Read back checkpoint C again, then "
                "replace its frozen digest before arming."
            )
    audit_goal = ActiveGoal(slug, goals, goal_file, goals / f"{slug}.events.jsonl", decisions, marker, session)
    prior_events = read_events(audit_goal)
    if any(e.get("event") == "frozen_spec_changed" for e in prior_events):
        raise ValueError("This goal was closed after frozen conditions changed; start a newly authorized goal.")
    prior_spec = goals / f"{slug}{SPEC_BASELINE_SUFFIX}"
    if prior_spec.is_file() and prior_spec.read_text().strip() != frozen_digest(goal_file.read_text()):
        raise ValueError("Frozen conditions differ from the armed baseline; start a newly authorized goal.")
    if marker.is_file() and _armed_slug(marker) is not None:
        current = _armed_slug(marker)
        if current != slug:
            raise ValueError(
                f"Another goal is armed ({current}); disarm it explicitly first "
                "(`goal_run.py disarm <slug>`). Arming must never silently "
                "retarget the hooks of a running goal."
            )
        _, owner_session = _read_marker(marker)
        if owner_session != session:
            raise ValueError(
                "This goal belongs to another session or has a legacy unbound "
                "marker. Only an owner-authorized `rebind` may transfer it; "
                "ordinary arming cannot take over a run."
            )
        # Same slug: idempotent re-arm. The baselines are write-once and must
        # not be re-derived now - the run may already have started, and a
        # baseline invented after work began authorizes whatever the file
        # says today.
        spec_baseline = goals / f"{slug}{SPEC_BASELINE_SUFFIX}"
        if not spec_baseline.is_file():
            raise ValueError(
                "This armed run has no recorded spec baseline, and one cannot be "
                "invented after work may have begun. A fresh start (remove "
                "active, the events log and both baselines by hand) is the way "
                "to re-arm."
            )
        check_protection(active_goal(root), goal_file.read_text())
        (goals / f"{slug}.verification.lock").touch(exist_ok=True)
        return f"{slug} is already armed; baselines unchanged."

    revision = _git(root, "rev-parse", "HEAD")
    if revision.returncode != 0 and not allow_no_git:
        raise ValueError(
            "Arming requires a usable Git HEAD by default; `git init` alone is not "
            "enough. Use the enclosing repository or create a reviewed baseline commit "
            "before arming. If this is not a project, Git is unavailable, or the owner "
            "declines baseline creation, rerun with --allow-no-git; step-history "
            "coverage and committed Writer-Session exclusion will be unavailable."
        )
    base = revision.stdout.strip() if revision.returncode == 0 else "none"

    spec_digest = frozen_digest(goal_file.read_text(encoding="utf-8"))
    pin_verification(root, slug, goal_file.read_text(encoding="utf-8"))
    # Order matters: every sidecar exists before the marker does, so no Stop
    # can arrive over an armed marker whose baseline is missing. The
    # baselines are write-once: a re-arm after a disarm keeps the previous
    # spec baseline as the authorized one, and if the artifact was edited
    # in between the gate closes the new run loudly on its first Stop
    # (frozen_spec_changed) rather than silently re-authorizing it - a
    # deliberate new spec goes through the fresh start, which removes the
    # baselines by hand.
    spec_kept = not _write_once(
        goals / f"{slug}{SPEC_BASELINE_SUFFIX}", spec_digest + "\n"
    )
    git_baseline = goals / f"{slug}{GIT_BASELINE_SUFFIX}"
    _write_once(git_baseline, base + "\n")
    recorded_base = git_baseline.read_text(encoding="utf-8").strip()
    (goals / f"{slug}.verification.lock").touch(exist_ok=True)

    ignore = goals / ".gitignore"
    existing = ignore.read_text(encoding="utf-8") if ignore.is_file() else ""
    additions = [e for e in IGNORE_ENTRIES if e not in existing.splitlines()]
    if additions:
        ignore.write_text(
            existing.rstrip("\n") + ("\n" if existing else "")
            + "\n".join(additions) + "\n",
            encoding="utf-8",
        )

    # Exclusive creation prevents a concurrent arm from overwriting an
    # already active goal. A hook seeing a partial marker stays inert.
    if not append_event(audit_goal, {"event": "session_binding_requested",
                                    "ts": datetime.now(timezone.utc).isoformat(), "sessions": [session]}):
        raise ValueError("Cannot record the executing session before activation.")
    with marker.open("x", encoding="utf-8") as handle:
        handle.write(f"{slug}\nsession {session}\n")
    kept_note = (
        " (a previous run's spec baseline is still the authorized one - fresh "
        "start to re-arm a changed spec)"
        if spec_kept else ""
    )
    retained = len(completion_attempts(read_events(active_goal(root))))
    git_note = (
        " No-Git mode was explicitly selected: step-history coverage and committed "
        "Writer-Session exclusion are unavailable."
        if recorded_base == "none"
        else ""
    )
    return (
        f"{slug} armed for session {session}. Spec baseline {spec_digest}; review baseline {recorded_base}.{kept_note} "
        "The gate is live: completion claims are judged against the frozen "
        f"sections as they stand now.{git_note} "
        f"{retained} earlier completion attempt(s) are retained; re-arming does "
        "not reset the ceiling. A fresh run needs a new authorized goal or "
        "the documented explicit reset."
    )


def rebind(root: Path, slug: str, session_id: str | None = None) -> str:
    """Explicit owner-authorized recovery into a different native session.

    This command transfers ownership, not authority or frozen conditions.
    The caller must already have permission to resume this run. Pending
    completion claims belong to the previous session and are discarded.
    """
    if _valid_slug(slug) != slug:
        raise ValueError("Expected a goal slug, not a path.")
    session = initiating_session(session_id)
    goals = root / ".goals"
    marker = goals / "active"
    if _armed_slug(marker) != slug:
        raise ValueError("The active marker does not name this goal.")
    spec_file = goals / f"{slug}.goal.md"
    baseline = goals / f"{slug}{SPEC_BASELINE_SUFFIX}"
    if not baseline.is_file() or baseline.read_text().strip() != frozen_digest(spec_file.read_text()):
        raise ValueError("Frozen conditions changed or the armed baseline is missing; start a newly authorized goal.")
    check_protection(active_goal(root), spec_file.read_text())
    if not append_event(active_goal(root), {"event": "session_binding_requested",
            "ts": datetime.now(timezone.utc).isoformat(),
            "sessions": [_read_marker(marker)[1], session]}):
        raise ValueError("Cannot preserve previous executing sessions before rebind.")
    candidate = goals / f"{slug}.candidate"
    candidate.unlink(missing_ok=True)
    marker.write_text(f"{slug}\nsession {session}\n", encoding="utf-8")
    return f"{slug} rebound to session {session}; baselines preserved, previous completion claim discarded."


def disarm(root: Path, slug: str) -> str:
    marker = root / ".goals" / "active"
    if not marker.is_file() or _armed_slug(marker) != slug:
        raise ValueError(
            "The active marker does not name this goal; nothing was removed."
        )
    try:
        marker.unlink()
    except OSError as exc:
        raise ValueError(f"The marker could not be removed: {exc}") from exc
    candidate = root / ".goals" / f"{slug}.candidate"
    try:
        candidate.unlink()
    except OSError:
        pass
    return (
        f"{slug} disarmed. The events log and baselines remain for audit; a "
        "fresh start removes them by hand."
    )


def review_diff(root: Path, slug: str) -> str:
    """The reviewer's range, with the ancestor guard the skills carry.

    A baseline that is not an ancestor of HEAD means history was rewritten
    under the run; the range is then unreliable and saying so is the honest
    output - the ported shape this file is based on lacked the guard.
    """
    marker = root / ".goals" / "active"
    if not marker.is_file() or _armed_slug(marker) != slug:
        raise ValueError("This goal is not armed.")
    base_file = root / ".goals" / f"{slug}{GIT_BASELINE_SUFFIX}"
    base = base_file.read_text(encoding="utf-8").strip() if base_file.is_file() else ""
    if not base or base == "none":
        return (
            "ultra-goal: no review range can be formed - this run recorded no "
            "git baseline. Report the review as unavailable rather than "
            "reviewing an unbounded tree."
        )
    guard = _git(root, "merge-base", "--is-ancestor", base, "HEAD")
    warning = (
        ""
        if guard.returncode == 0 else
        f"ultra-goal: baseline {base} is not an ancestor of HEAD - history "
        "moved under the run and the recorded range is unreliable. Report that "
        "instead of trusting this diff.\n"
    )
    diff = _git(root, "diff", "--no-ext-diff", base, "--")
    untracked = _git(
        root, "ls-files", "--others", "--exclude-standard"
    )
    return (
        f"{warning}Review baseline: {base}\n\n{diff.stdout}\n\n"
        "Untracked files (review only those inside the goal boundary):\n"
        f"{untracked.stdout}"
    )


def verify(root: Path, slug: str, session_id: str | None = None,
           claim: str = "Proposed completion of the accepted contract") -> dict:
    """Run the existing gate as a tool, so its result precedes final delivery.

    This is an explicit completion attempt, not a synthetic host Stop or a
    continuation driver. The same frozen terms, evidence and attempt ceiling apply.
    """
    from goal_stop import handle

    session = initiating_session(session_id)
    goal = active_goal(root)
    if goal is None or goal.slug != slug or goal.owner_session != session:
        raise ValueError("Verify requires the active goal's bound native session.")
    if not isinstance(claim, str) or not claim.strip():
        raise ValueError("A completion claim must be nonempty.")
    attempt_id = uuid.uuid4().hex
    message = handle({"session_id": session, "verification_id": attempt_id}, goal,
                     command=True, claim=claim)
    observations = [e for e in read_events(goal) if e.get("verification_id") == attempt_id]
    measured = [e for e in observations if completion_attempt(e)]
    observation = measured[-1] if measured else None
    passed = bool(observation and observation.get("verification_passed") is True)
    return {"verification_passed": passed, "fresh_check": observation is not None,
            "observation": observation, "message": message,
            "event_log": f".goals/{slug}.events.jsonl"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
    )
    parser.add_argument(
        "action",
        choices=("arm", "diff", "disarm", "rebind", "review-inputs", "spec-digest", "verify"),
    )
    parser.add_argument("slug")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--session-id", help="Current native session ID, never another task's ID")
    parser.add_argument("--claim", default="Proposed completion of the accepted contract")
    parser.add_argument(
        "--allow-no-git",
        action="store_true",
        help="Arm without a usable HEAD after accepting reduced audit coverage",
    )
    args = parser.parse_args(argv)
    try:
        if args.action == "verify":
            result = verify(args.root, args.slug, args.session_id, args.claim)
            print(json.dumps(result, ensure_ascii=False))
            return 0 if result["verification_passed"] else 1
        elif args.action == "review-inputs":
            if _valid_slug(args.slug) != args.slug:
                raise ValueError("Expected a goal slug, not a path.")
            print(input_digest(args.root, (args.root / ".goals" / f"{args.slug}.goal.md").read_text()))
        elif args.action == "spec-digest":
            if _valid_slug(args.slug) != args.slug:
                raise ValueError("Expected a goal slug, not a path.")
            goal = args.root / ".goals" / f"{args.slug}.goal.md"
            print(frozen_digest(goal.read_text(encoding="utf-8")))
        elif args.action == "arm":
            print(arm(args.root, args.slug, args.session_id, args.allow_no_git))
        elif args.action == "rebind":
            print(rebind(args.root, args.slug, args.session_id))
        elif args.action == "diff":
            print(review_diff(args.root, args.slug))
        else:
            print(disarm(args.root, args.slug))
        return 0
    except (ValueError, OSError) as exc:
        print(f"ultra-goal: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    # Arming refuses loudly rather than fail-open: this is an owner act, not
    # a host hook, so exit 1 with a message is the contract.
    raise SystemExit(main())
