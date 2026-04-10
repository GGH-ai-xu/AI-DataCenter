import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, os.path.join(ROOT, "server-agent"))

from controllers import power_control  # noqa: E402


def _completed(args: list[str], returncode: int = 0, stdout: str = "", stderr: str = ""):
    return subprocess.CompletedProcess(
        args=args,
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


class PowerControlTests(unittest.TestCase):
    def test_set_power_limit_rejects_scope_unsupported_output(self):
        with mock.patch.object(
            power_control,
            "_run_nvidia_smi",
            return_value=_completed(
                ["nvidia-smi", "-i", "0", "-pl", "120"],
                stdout=(
                    "Changing power management limit is not supported in current scope "
                    "for GPU: 00000000:01:00.0.\nAll done.\n"
                ),
            ),
        ) as mocked_run:
            result = power_control.set_power_limit(0, 120)

        self.assertFalse(result["success"])
        self.assertIn("not supported in current scope", result["error"].lower())
        self.assertEqual(mocked_run.call_count, 1)

    def test_set_power_limit_rejects_when_readback_does_not_match_target(self):
        with mock.patch.object(
            power_control,
            "_run_nvidia_smi",
            side_effect=[
                _completed(["nvidia-smi", "-i", "0", "-pl", "120"], stdout="All done.\n"),
                _completed(
                    [
                        "nvidia-smi",
                        "-i",
                        "0",
                        "--query-gpu=power.limit",
                        "--format=csv,noheader,nounits",
                    ],
                    stdout="125.0\n",
                ),
            ],
        ):
            result = power_control.set_power_limit(0, 120)

        self.assertFalse(result["success"])
        self.assertIn("未生效", result["error"])
        self.assertIn("125.0W", result["error"])

    def test_set_power_limit_succeeds_when_readback_matches_target(self):
        with mock.patch.object(
            power_control,
            "_run_nvidia_smi",
            side_effect=[
                _completed(["nvidia-smi", "-i", "0", "-pl", "120"], stdout="All done.\n"),
                _completed(
                    [
                        "nvidia-smi",
                        "-i",
                        "0",
                        "--query-gpu=power.limit",
                        "--format=csv,noheader,nounits",
                    ],
                    stdout="120.0\n",
                ),
            ],
        ):
            result = power_control.set_power_limit(0, 120)

        self.assertTrue(result["success"])
        self.assertEqual(result["gpu_index"], 0)
        self.assertEqual(result["power_limit"], 120)
        self.assertEqual(result["applied_power_limit"], 120.0)


if __name__ == "__main__":
    unittest.main()
