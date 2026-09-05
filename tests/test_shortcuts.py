import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


spec = importlib.util.spec_from_file_location(
    "install_shortcuts", Path(__file__).resolve().parents[1] / "scripts/install_shortcuts.py"
)
shortcuts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shortcuts)


class ShortcutTests(unittest.TestCase):
    def test_native_files_share_the_original_skill_and_are_idempotent(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "source with spaces/SKILL.md"
            source.parent.mkdir()
            source.write_text("---\nname: ultra-goal\ndescription: Fixture\n---\n", encoding="utf-8")
            for host, paths in {
                "claude": (".claude/commands/UG.md", ".claude/commands/ultragoal.md"),
                "codex": (".agents/skills/ug/SKILL.md", ".agents/skills/ultragoal/SKILL.md"),
                "kimi": (".kimi-code/skills/ug/SKILL.md", ".kimi-code/skills/ultragoal/SKILL.md"),
                "zcode": (".zcode/skills/ug/SKILL.md", ".zcode/skills/ultragoal/SKILL.md"),
            }.items():
                with self.subTest(host=host):
                    home = root / host
                    installed = shortcuts.install_shortcuts(host, home, source)
                    self.assertEqual([home / path for path in paths], installed)
                    for path in installed:
                        text = path.read_text(encoding="utf-8")
                        locator = next(line for line in text.splitlines() if line.startswith("Read the UltraGoal"))
                        target = Path(json.loads(locator.split(" at ", 1)[1]))
                        self.assertEqual(source.resolve(), target)
                        self.assertEqual(source.read_bytes(), target.read_bytes())
                    before = {path: path.stat().st_mtime_ns for path in installed}
                    shortcuts.install_shortcuts(host, home, source)
                    self.assertEqual(before, {path: path.stat().st_mtime_ns for path in installed})
                    self.assertEqual(sorted(paths), sorted(p.relative_to(home).as_posix() for p in home.rglob("*") if p.is_file()))

    def test_conflict_or_missing_source_leaves_user_files_alone(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            collision = root / ".claude/commands/ultragoal.md"
            collision.parent.mkdir(parents=True)
            collision.write_text("Owner's existing command", encoding="utf-8")
            with self.assertRaises(FileNotFoundError):
                shortcuts.install_shortcuts("claude", root, root / "missing/SKILL.md")
            with self.assertRaises(FileExistsError):
                shortcuts.install_shortcuts("claude", root, shortcuts.DEFAULT_SKILL)
            self.assertEqual("Owner's existing command", collision.read_text(encoding="utf-8"))
            self.assertFalse((collision.parent / "UG.md").exists())


if __name__ == "__main__":
    unittest.main()
