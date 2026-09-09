"""Opt-in native Pi extension loader check; no provider/model calls."""
import os
from pathlib import Path
import subprocess
import sys
import unittest

from test_goal_hooks import Harness, GOAL, GREEN


@unittest.skipUnless(os.environ.get("ULTRA_GOAL_TEST_PI_SDK"), "Set ULTRA_GOAL_TEST_PI_SDK to an installed Pi package root")
class PiExtensionTests(Harness):
    def test_native_adapter_lifecycle(self):
        anchor = f'"{sys.executable}" -c "from pathlib import Path; raise SystemExit(0 if Path(\'result.txt\').exists() else 1)"'
        self.make_loop(goal=GOAL.replace(GREEN, anchor))
        repo = Path(__file__).resolve().parents[1]
        result = subprocess.run([
            "node", str(repo / "tests/pi_extension_check.mjs"),
            os.environ["ULTRA_GOAL_TEST_PI_SDK"], str(self.cwd),
            str(repo / "plugins/ultra-goal/pi/extension.ts"),
        ], capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
