"""Smoke test for scripts/eval_ship_gate_batch.py (no golden ship outcomes; env-dependent)."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import unittest


def _load_eval_script():
    repo = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    path = os.path.join(repo, "scripts", "eval_ship_gate_batch.py")
    spec = importlib.util.spec_from_file_location("eval_ship_gate_batch", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestEvalShipGateBatchScript(unittest.TestCase):
    def test_smoke_runs(self):
        repo = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        script = os.path.join(repo, "scripts", "eval_ship_gate_batch.py")
        proc = subprocess.run(
            [sys.executable, script, "--smoke"],
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr + proc.stdout)
        self.assertIn('"n_episodes": 2', proc.stdout)
        self.assertIn("smoke_ok", proc.stdout)
        self.assertIn("smoke_tag", proc.stdout)
        self.assertIn("calib=", proc.stdout)
        self.assertIn("reason=", proc.stdout)

    def test_calibration_eval_label_bands(self):
        m = _load_eval_script()
        self.assertEqual(m.calibration_eval_label(0.7, 0.7, 0.1), "PASS")
        self.assertEqual(m.calibration_eval_label(0.4, 0.7, 0.1), "FAIL")
        self.assertEqual(m.calibration_eval_label(0.7, 0.3, 0.1), "FAIL")
        self.assertEqual(m.calibration_eval_label(0.55, 0.7, 0.1), "REVIEW")

    def test_manifest_loads(self):
        repo = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        path = os.path.join(repo, "config", "eval_manifest.example.json")
        with open(path, encoding="utf-8") as f:
            m = json.load(f)
        self.assertIn("episodes", m)


if __name__ == "__main__":
    unittest.main()
