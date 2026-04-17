"""Smoke test for scripts/verify_soapboxx_backend.py (wrapper / path sanity)."""

import os
import subprocess
import sys
import unittest


class TestVerifySoapboxxBackendScript(unittest.TestCase):
    def test_script_exits_zero_from_repo(self):
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        script = os.path.join(root, "scripts", "verify_soapboxx_backend.py")
        proc = subprocess.run(
            [sys.executable, script, "--repo", root],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)


if __name__ == "__main__":
    unittest.main()
