"""Frontend race regression, driven through Node when the runtime is present.

The Python suite stays standard-library only: when Node is not installed the
check is skipped instead of making the baseline suite depend on extra tooling.
Run the harness directly with: node tests/frontend_upload_race.test.js
"""
import shutil
import subprocess
import unittest
from pathlib import Path

NODE = shutil.which("node")
SCRIPT = Path(__file__).with_name("frontend_upload_race.test.js")


@unittest.skipUnless(NODE, "需要 Node.js 运行前端竞态回归")
class FrontendRaceTest(unittest.TestCase):
    def test_upload_keeps_the_project_captured_at_submission_start(self):
        result = subprocess.run(
            [NODE, str(SCRIPT)], capture_output=True, text=True, timeout=60
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("FRONTEND RACE: 2 PASS, 0 FAIL", result.stdout)


if __name__ == "__main__":
    unittest.main()
