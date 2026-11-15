"""US04 界面动作回归，通过 Node 运行时执行；无 Node 时跳过。

业务与测试仍仅依赖 Python 标准库：
    node tests/frontend_college_review.test.js
"""
import shutil
import subprocess
import unittest
from pathlib import Path

NODE = shutil.which("node")
SCRIPT = Path(__file__).with_name("frontend_college_review.test.js")


@unittest.skipUnless(NODE, "需要 Node.js 运行前端界面动作回归")
class FrontendCollegeReviewTest(unittest.TestCase):
    def test_college_review_form_uses_new_endpoint(self):
        result = subprocess.run(
            [NODE, str(SCRIPT)], capture_output=True, text=True, timeout=60
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("FRONTEND US04: 3 PASS, 0 FAIL", result.stdout)


if __name__ == "__main__":
    unittest.main()
