#!/usr/bin/env python3
"""Add native UG/ug and ultragoal entrypoints to an existing UltraGoal copy."""

import argparse
import json
import os
from pathlib import Path


DEFAULT_SKILL = (
    Path(__file__).resolve().parents[1]
    / "plugins/ultra-goal/skills/ultra-goal/SKILL.md"
)


def install_shortcuts(host: str, home: Path, skill: Path) -> list[Path]:
    skill = skill.expanduser().resolve(strict=True)
    if not skill.is_file() or skill.name != "SKILL.md":
        raise ValueError("--skill must point to the existing UltraGoal SKILL.md")
    roots = {
        "claude": home / ".claude/commands",
        "codex": home / ".agents/skills",
        "kimi": Path(os.environ.get("KIMI_CODE_HOME") or home / ".kimi-code").expanduser() / "skills",
        "zcode": home / ".zcode/skills",
    }
    files = {}
    for name in (("UG", "ultragoal") if host == "claude" else ("ug", "ultragoal")):
        destination = roots[host] / (f"{name}.md" if host == "claude" else f"{name}/SKILL.md")
        files[destination] = (
            f"---\nname: {name}\n"
            "description: Use UltraGoal to create, inspect or modify an executable goal.\n"
            "---\n\n"
            f"Read the UltraGoal entry file at {json.dumps(str(skill), ensure_ascii=False)}\n"
            "and follow it for the owner's request. Resolve its resource paths relative\n"
            "to that file's directory, not this shortcut. If it is unavailable, report\n"
            "the missing source; do not invent a replacement procedure.\n\n"
            "This shortcut does not install hooks. Use the existing UltraGoal plugin\n"
            "for its run command, review roles and host hooks.\n"
        )
    # Check both names before writing either; never replace another user's command.
    for destination, content in files.items():
        if destination.is_symlink() or (
            destination.exists()
            and (not destination.is_file() or destination.read_text(encoding="utf-8") != content)
        ):
            raise FileExistsError(f"Refusing to replace an existing shortcut: {destination}")
    for destination, content in files.items():
        if not destination.exists():
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("x", encoding="utf-8") as stream:
                stream.write(content)
    return list(files)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", choices=("claude", "codex", "kimi", "zcode"), required=True)
    parser.add_argument("--home", type=Path, default=Path.home(), help="Target user home")
    parser.add_argument("--skill", type=Path, default=DEFAULT_SKILL,
                        help="Existing UltraGoal SKILL.md; defaults to this checkout")
    args = parser.parse_args()
    try:
        for path in install_shortcuts(args.host, args.home.expanduser().resolve(), args.skill):
            print(path)
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
