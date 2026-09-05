"""Shared acceptance contract and evidence checks; no task scheduling.

The owner approves criteria and provenance. These checks bind declared criteria,
evaluator files and review inputs; they do not authenticate a writable filesystem
or prove that a chosen criterion captures the owner's intent.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import zipfile

from goal_hooks import ActiveGoal, sections, read_events, frozen_digest

VERIFICATION_BASELINE_SUFFIX = ".verification.baseline"
ACCEPTANCE = re.compile(r"^\s*[-*]\s+\[[ xX]\]\s+([a-z][a-z0-9_-]*):\s+(.+)$", re.M)


def verification(spec: str) -> dict:
    """Read the exact contract consumed by arming and completion checks."""
    found = sections(spec)
    blocks = re.findall(r"```json\s*\n(.*?)\n```", found.get("verification", ""), re.S)
    if len(blocks) != 1:
        raise ValueError("Verification needs a JSON contract; prose alone cannot declare independent evidence.")
    try:
        data = json.loads(blocks[0])
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid Verification JSON: {exc.msg}") from exc
    if not isinstance(data, dict) or set(data) != {"source", "basis", "protected", "covers", "review"}:
        raise ValueError("Verification requires exactly source, basis, protected, covers and review.")
    if data["source"] not in ("owner-approved", "external") or not isinstance(data["basis"], str) or not data["basis"].strip():
        raise ValueError("Name owner-approved or external evidence and its concrete basis; generator self-review is not a source.")
    _paths(data["protected"])
    if data["source"] == "owner-approved" and not data["protected"]:
        raise ValueError("Owner-approved evaluator definitions need protected files.")
    items = ACCEPTANCE.findall(found.get("acceptance", ""))
    ids = [item[0] for item in items]
    bullets = re.findall(r"^\s*[-*]\s+\[[ xX]\]", found.get("acceptance", ""), re.M)
    if not ids or len(ids) != len(set(ids)) or len(ids) != len(bullets):
        raise ValueError("Acceptance needs unique '- [ ] requirement-id: outcome' entries.")
    covers = data["covers"]
    if not isinstance(covers, dict) or set(covers) != set(ids) or any(v not in ("anchor", "review") for v in covers.values()):
        raise ValueError("Verification covers must map every Acceptance ID exactly once to anchor or review.")
    if not re.search(r"^success:\s*verified\s*$", found.get("stop condition", ""), re.M):
        raise ValueError("Stop condition needs 'success: verified': current anchor and all required review evidence must pass.")
    if not re.search(r"^ceiling:\s*(none|\d+)\s*$", found.get("stop condition", ""), re.M):
        raise ValueError("Stop condition needs an explicit 'ceiling: N' or 'ceiling: none'.")
    review = data["review"]
    if review is None:
        if "review" in covers.values():
            raise ValueError("Acceptance assigned to review requires a review contract.")
    else:
        if not isinstance(review, dict) or set(review) != {"path", "verifiers", "inputs"}:
            raise ValueError("Review requires exactly path, verifiers and inputs; use null when no semantic review is required.")
        _paths([review["path"]]); _paths(review["inputs"])
        if not review["inputs"] or not isinstance(review["verifiers"], list) or not review["verifiers"]:
            raise ValueError("Review needs bounded inputs and at least one approved verifier identity.")
        if any(not isinstance(v, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]*", v) for v in review["verifiers"]):
            raise ValueError("Review verifier identities must be nonempty tokens.")
        receipt = Path(review["path"])
        if any(receipt == Path(p) or Path(p) in receipt.parents for p in review["inputs"]):
            raise ValueError("The review receipt cannot be among its own reviewed inputs.")
    return data


def _paths(paths: object) -> None:
    if not isinstance(paths, list) or any(not isinstance(p, str) or not p or Path(p).is_absolute()
                                        or ".." in Path(p).parts or p == "." for p in paths):
        raise ValueError("Evidence paths must be explicit project-relative files or directories, without '..'.")


def snapshot(root: Path, paths: list[str]) -> dict[str, str]:
    """Hash the declared file set, including additions/removals under directories."""
    _paths(paths)
    files: dict[str, str] = {}
    for raw in paths:
        path = root / raw
        if not path.exists():
            raise ValueError(f"Evidence input is missing: {raw}")
        children = [path, *sorted(path.rglob("*"))] if path.is_dir() else [path]
        for child in children:
            if child.is_symlink() or not child.resolve().is_relative_to(root.resolve()):
                raise ValueError(f"Evidence input must not traverse a symlink: {raw}")
            if child.is_file():
                with child.open("rb") as stream:
                    files[child.relative_to(root).as_posix()] = _stream_digest(stream)
    return files


def _stream_digest(stream) -> str:
    digest = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1 << 20), b""):
        digest.update(chunk)
    return digest.hexdigest()


def _input_digest(spec: str, files: dict[str, str]) -> str:
    payload = json.dumps({"contract": frozen_digest(spec), "files": files},
                         sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def input_digest(root: Path, spec: str) -> str:
    review = verification(spec)["review"]
    if review is None:
        raise ValueError("This goal has no required review.")
    return _input_digest(spec, snapshot(root, review["inputs"]))


def pin_verification(root: Path, slug: str, spec: str) -> None:
    """Write before activation, never silently replace an existing baseline."""
    definition = verification(spec)
    observed = snapshot(root, definition["protected"])
    if definition["source"] == "owner-approved" and not observed:
        raise ValueError("No evaluator files were found in the protected paths.")
    path = root / ".goals" / f"{slug}{VERIFICATION_BASELINE_SUFFIX}"
    if path.exists():
        if json.loads(path.read_text()) != observed:
            raise ValueError("Protected evaluator inputs changed; restore them or start a newly authorized goal.")
        return
    with path.open("x", encoding="utf-8") as handle:
        json.dump(observed, handle, sort_keys=True)
        handle.write("\n")


def check_protection(goal: ActiveGoal, spec: str) -> None:
    baseline = goal.goals_dir / f"{goal.slug}{VERIFICATION_BASELINE_SUFFIX}"
    if not baseline.is_file():
        raise ValueError("No arming-time evaluator baseline; this goal has not established its verification contract.")
    if json.loads(baseline.read_text()) != snapshot(goal.goals_dir.parent, verification(spec)["protected"]):
        raise ValueError("Protected evaluator inputs changed; restore them, do not weaken the checker or re-baseline the run.")


def check_review(goal: ActiveGoal, spec: str, *, retain: bool = False) -> dict | None:
    """Consume a current independent review receipt, never a tool-success proxy.

    Reviewer identity is a declared provenance field, not an authentication token.
    The host/owner must supply the stated input isolation and write authority.
    The final gate retains accepted evidence before recording its result. Reading
    an archive is a separate historical audit, never a missing live receipt fallback.
    """
    contract = verification(spec)
    review = contract["review"]
    if review is None:
        return None
    path = goal.goals_dir.parent / review["path"]
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"Required independent review is missing: {review['path']}")
    receipt_bytes = path.read_bytes()
    receipt = json.loads(receipt_bytes)
    if not isinstance(receipt, dict):
        raise ValueError("Review receipt must be a JSON object.")
    if receipt.get("verifier") not in review["verifiers"]:
        raise ValueError("Review did not name an approved verifier or fallback.")
    session = receipt.get("session_id")
    owners = {goal.owner_session}
    for event in read_events(goal):
        if event.get("event") == "session_binding_requested" and isinstance(event.get("sessions"), list):
            owners.update(s for s in event["sessions"] if isinstance(s, str))
    if not isinstance(session, str) or not session or session in owners:
        raise ValueError("Review needs a distinct verifier session; the generator cannot verify itself.")
    files = snapshot(goal.goals_dir.parent, review["inputs"])
    if receipt.get("input_digest") != _input_digest(spec, files):
        raise ValueError("Review is stale or refers to different inputs; review the current result.")
    required = {key for key, value in contract["covers"].items() if value == "review"}
    if (not isinstance(receipt.get("covers"), list)
            or any(not isinstance(item, str) for item in receipt["covers"])
            or not required.issubset(receipt["covers"])):
        raise ValueError("Review does not cover the required acceptance IDs.")
    if receipt.get("verdict") != "pass" or not isinstance(receipt.get("evidence"), str) or not receipt["evidence"].strip():
        raise ValueError("Independent review did not pass with an evidence explanation.")
    checks = receipt.get("checks")
    if not isinstance(checks, dict) or not required.issubset(checks):
        raise ValueError("Review needs a concrete check with input evidence for every required acceptance ID.")
    for key in required:
        check = checks[key]
        if (not isinstance(check, dict) or not isinstance(check.get("claim"), str)
                or not check["claim"].strip() or not isinstance(check.get("evidence"), list)
                or not check["evidence"]):
            raise ValueError(f"Review check {key} needs a claim and nonempty evidence references.")
        for reference in check["evidence"]:
            if (not isinstance(reference, dict) or not isinstance(reference.get("path"), str)
                    or reference["path"] not in files or not isinstance(reference.get("quote"), str)
                    or not reference["quote"].strip()):
                raise ValueError(f"Review check {key} must quote a file in the declared review inputs.")
            try:
                quoted_bytes = (goal.goals_dir.parent / reference["path"]).read_bytes()
                if hashlib.sha256(quoted_bytes).hexdigest() != files[reference["path"]]:
                    raise ValueError("Review inputs changed while checking their quoted evidence.")
                text = quoted_bytes.decode("utf-8")
            except UnicodeError as exc:
                raise ValueError("Review quotes require a text evidence input.") from exc
            if reference["quote"] not in text:
                raise ValueError(f"Review evidence quote is absent from {reference['path']}.")
    # References establish inspectable support, not semantic entailment or identity.
    evidence = {"path": review["path"], "sha256": hashlib.sha256(receipt_bytes).hexdigest(),
                "verifier": receipt["verifier"], "session_id": session, "input_digest": receipt["input_digest"]}
    if retain:
        evidence["archive"] = _retain_review(goal, spec, receipt_bytes, files, evidence)
    return evidence


def _retain_review(goal: ActiveGoal, spec: str, receipt: bytes, files: dict[str, str], evidence: dict) -> dict:
    """Keep the declared review scope outside disposable work, using bounded memory.

    No size policy narrows an approved evidence set. Disk, permissions and hook
    time still bound this local copy; a failed copy must not become a passed gate.
    """
    root = goal.goals_dir.parent
    directory = goal.goals_dir / f"{goal.slug}.reviews"
    relative = directory.relative_to(root)
    if any(Path(raw) == relative or Path(raw) in relative.parents
           for raw in verification(spec)["review"]["inputs"]):
        raise ValueError("Review archive destination overlaps reviewed inputs; an authorized artifact layout is required.")
    retained = {"receipt.json": receipt, "goal.md": spec.encode("utf-8")}
    manifest = {"version": 1, "input_digest": evidence["input_digest"], "files": {
        **{name: hashlib.sha256(content).hexdigest() for name, content in retained.items()},
        **{f"inputs/{name}": digest for name, digest in files.items()},
    }}
    encoded = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
    path = directory / f"{hashlib.sha256(encoded).hexdigest()}.zip"
    if directory.is_symlink() or not directory.resolve().is_relative_to(root.resolve()):
        raise ValueError("Review archive destination must stay inside the project without a symlink.")
    directory.mkdir(exist_ok=True)
    for event in read_events(goal):
        previous = event.get("review_evidence")
        if (isinstance(previous, dict) and isinstance(previous.get("archive"), dict)
                and previous["archive"].get("path") == path.relative_to(root).as_posix()):
            read_review_archive(root, previous)
            break
    if not path.exists():
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=directory, prefix=".pending-", delete=False) as handle:
                temporary = Path(handle.name)
                with zipfile.ZipFile(handle, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                    for name, content in {"manifest.json": encoded, **retained}.items():
                        entry = zipfile.ZipInfo(name)
                        entry.compress_type = zipfile.ZIP_DEFLATED
                        archive.writestr(entry, content)
                    for name, expected in files.items():
                        source = root / name
                        if source.is_symlink() or not source.resolve().is_relative_to(root.resolve()):
                            raise ValueError(f"Review input changed to a symlink while retaining evidence: {name}")
                        digest = hashlib.sha256()
                        entry = zipfile.ZipInfo(f"inputs/{name}")
                        entry.compress_type = zipfile.ZIP_DEFLATED
                        with source.open("rb") as incoming, archive.open(entry, "w", force_zip64=True) as outgoing:
                            for chunk in iter(lambda: incoming.read(1 << 20), b""):
                                digest.update(chunk)
                                outgoing.write(chunk)
                        if digest.hexdigest() != expected:
                            raise ValueError(f"Review input changed while retaining evidence: {name}")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    with path.open("rb") as stream:
        recorded = {"path": path.relative_to(root).as_posix(), "sha256": _stream_digest(stream)}
    # Reuse is checked as strictly as a historical audit; never silently repair
    # or overwrite an altered package already referenced by previous events.
    read_review_archive(root, {**evidence, "archive": recorded})
    return recorded


def read_review_archive(root: Path, evidence: dict) -> dict:
    """Verify a historical package and return its manifest, without extracting it.

    This proves retained byte identity against the event, not current acceptance,
    semantic entailment or authenticated authorship on a shared writable disk.
    """
    reference = evidence.get("archive")
    if not isinstance(reference, dict) or not isinstance(reference.get("sha256"), str):
        raise ValueError("No retained review archive is recorded for this observation.")
    _paths([reference.get("path")])
    path = root / reference["path"]
    if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("Review archive path must stay inside the project without a symlink.")
    with path.open("rb") as stream:
        if _stream_digest(stream) != reference["sha256"]:
            raise ValueError("Review archive digest mismatch; the retained package changed.")
    try:
        with zipfile.ZipFile(path) as archive:
            encoded = archive.read("manifest.json")
            manifest = json.loads(encoded)
            if (not isinstance(manifest, dict) or manifest.get("version") != 1
                    or not isinstance(manifest.get("files"), dict)
                    or manifest.get("input_digest") != evidence.get("input_digest")
                    or manifest["files"].get("receipt.json") != evidence.get("sha256")
                    or "goal.md" not in manifest["files"]
                    or hashlib.sha256(encoded).hexdigest() != path.stem):
                raise ValueError("Review archive manifest does not match its recorded evidence.")
            names = archive.namelist()
            if len(names) != len(set(names)) or set(names) != {"manifest.json", *manifest["files"]}:
                raise ValueError("Review archive member set does not match its manifest.")
            inputs = {}
            for name, expected in manifest["files"].items():
                if name not in ("receipt.json", "goal.md"):
                    if not name.startswith("inputs/"):
                        raise ValueError("Review archive has an unexpected member path.")
                    _paths([name[len("inputs/"):]])
                    inputs[name[len("inputs/"):]] = expected
                with archive.open(name) as stream:
                    if _stream_digest(stream) != expected:
                        raise ValueError(f"Review archive member digest mismatch: {name}")
            if _input_digest(archive.read("goal.md").decode("utf-8"), inputs) != evidence.get("input_digest"):
                raise ValueError("Review archive inputs and goal do not match the reviewed digest.")
    except (zipfile.BadZipFile, KeyError, UnicodeError) as exc:
        raise ValueError(f"Review archive is unreadable: {exc}") from exc
    return {**reference, "manifest": manifest}
