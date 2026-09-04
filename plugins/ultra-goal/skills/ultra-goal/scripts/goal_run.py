#!/usr/bin/env python3
"""Arm a validated goal: the one fence that validates, authorizes and arms.

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
  covers only the run-private files), so it is committed with the run's first
  turn and a rewrite shows in `git log`;
- the review baseline (the git revision, or `none` outside Git) is
  write-once, so a re-arm cannot hand the reviewer an empty range;
- `.goals/.gitignore` names the run-private files, `*.candidate` included -
  a live claim must not ride into a commit.

`diff` prints the reviewer's range from the same baseline file the review
and critic skills read, with the same ancestor guard: a baseline that is no
longer an ancestor of HEAD means history moved under the run, and the
honest output says the range is unreliable instead of trusting the diff.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from goal_hooks import (  # noqa: E402
    SPEC_BASELINE_SUFFIX,
    _read_marker,
    _valid_slug,
    frozen_digest,
)
from validate_artifact import validate_paths  # noqa: E402


GIT_BASELINE_SUFFIX = ".baseline"
IGNORE_ENTRIES = (".work/", "active", "*.candidate")


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, timeout=30
    )


def _write_once(path: Path, text: str) -> bool:
    """Write `text` to `path` only if it holds nothing. True if it holds it now.

    Write-once is what makes a baseline evidence rather than a suggestion:
    the arming revision survives re-arms and restarts, and a run that wants
    it moved has to delete it - which shows in `git log`.
    """
    if path.is_file() and path.read_text(encoding="utf-8").strip():
        return False
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    except (OSError, UnicodeError):
        return False
    return True


def _armed_slug(marker: Path) -> str | None:
    """The marker's slug line - the first line, never the whole file.

    The marker legitimately grows a `session <id>` second line the first
    time a Stop claims the run, so comparing the whole marker text against
    the slug (the shape this file was ported from) broke both re-arming and
    disarming for exactly the runs that had started.
    """
    slug, _session = _read_marker(marker)
    return slug


def arm(root: Path, slug: str) -> str:
    if _valid_slug(slug) != slug:
        raise ValueError("Expected a goal slug, not a path.")
    goals = root / ".goals"
    goal_file = goals / f"{slug}.goal.md"
    decisions = goals / f"{slug}.decisions.md"
    if not goal_file.is_file() or not decisions.is_file():
        raise ValueError(
            "The goal or paired decisions record is missing. Do not author one "
            "here - that is the interview's job, and a run against an artifact "
            "nobody agreed to is the failure this design exists to prevent."
        )
    report = validate_paths([str(goal_file), str(decisions)])
    errors = [f for f in report.findings if f.severity == "error"]
    if errors:
        raise ValueError(
            "Artifact validation failed: " + "; ".join(f.message for f in errors)
        )

    marker = goals / "active"
    if marker.is_file() and _armed_slug(marker) is not None:
        current = _armed_slug(marker)
        if current != slug:
            raise ValueError(
                f"Another goal is armed ({current}); disarm it explicitly first "
                "(`goal_run.py disarm <slug>`). Arming must never silently "
                "retarget the hooks of a running goal."
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
        return f"{slug} is already armed; baselines unchanged."

    revision = _git(root, "rev-parse", "HEAD")
    base = revision.stdout.strip() if revision.returncode == 0 else "none"

    spec_digest = frozen_digest(goal_file.read_text(encoding="utf-8"))
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
    _write_once(goals / f"{slug}{GIT_BASELINE_SUFFIX}", base + "\n")

    ignore = goals / ".gitignore"
    existing = ignore.read_text(encoding="utf-8") if ignore.is_file() else ""
    additions = [e for e in IGNORE_ENTRIES if e not in existing.splitlines()]
    if additions:
        ignore.write_text(
            existing.rstrip("\n") + ("\n" if existing else "")
            + "\n".join(additions) + "\n",
            encoding="utf-8",
        )

    marker.write_text(slug + "\n", encoding="utf-8")
    kept_note = (
        " (a previous run's spec baseline is still the authorized one - fresh "
        "start to re-arm a changed spec)"
        if spec_kept else ""
    )
    return (
        f"{slug} armed. Spec baseline {spec_digest}; review baseline {base}.{kept_note} "
        "The gate is live: completion claims are judged against the frozen "
        "sections as they stand now."
    )


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
    )
    parser.add_argument("action", choices=("arm", "diff", "disarm"))
    parser.add_argument("slug")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    try:
        if args.action == "arm":
            print(arm(args.root, args.slug))
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
