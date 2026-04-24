"""Smoke test for scripts/preflight_soapboxx.py."""

import os
import subprocess
import sys
import unittest


class TestPreflightSoapboxx(unittest.TestCase):
    def test_preflight_exits_zero(self):
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        script = os.path.join(root, "scripts", "preflight_soapboxx.py")
        proc = subprocess.run(
            [sys.executable, script, "--repo", root, "--no-tests"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=180,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)


if __name__ == "__main__":
    unittest.main()
