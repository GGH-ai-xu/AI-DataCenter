import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class RuntimeMasterKeyScriptTests(unittest.TestCase):
    def test_runtime_master_key_helper_exists_and_persists_repo_runtime_file(self):
        helper_path = ROOT / "scripts" / "runtime-master-key.ps1"

        self.assertTrue(helper_path.exists(), str(helper_path))
        script = helper_path.read_text(encoding="utf-8")

        self.assertIn("function Ensure-RepoRuntimeMasterKey", script)
        self.assertIn('Join-Path $RepoRoot "runtime\\.gpu-gov-master-key"', script)
        self.assertIn("GPU_GOV_MASTER_KEY", script)
        self.assertIn("RandomNumberGenerator", script)
        self.assertIn("Set-Content", script)

    def test_start_dev_injects_repo_runtime_master_key_into_backend(self):
        script = (ROOT / "scripts" / "start-dev.ps1").read_text(encoding="utf-8")

        self.assertIn('. "$PSScriptRoot\\runtime-master-key.ps1"', script)
        self.assertIn("$runtimeMasterKey = Ensure-RepoRuntimeMasterKey -RepoRoot $root", script)
        self.assertIn('GPU_GOV_MASTER_KEY = $runtimeMasterKey', script)

    def test_start_electron_dev_injects_repo_runtime_master_key_into_backend(self):
        script = (ROOT / "scripts" / "start-electron-dev.ps1").read_text(encoding="utf-8")

        self.assertIn('. "$PSScriptRoot\\runtime-master-key.ps1"', script)
        self.assertIn("$runtimeMasterKey = Ensure-RepoRuntimeMasterKey -RepoRoot $root", script)
        self.assertIn('GPU_GOV_MASTER_KEY = $runtimeMasterKey', script)

    def test_runtime_master_key_helper_executes_and_reuses_same_value(self):
        powershell = shutil.which("powershell.exe")
        if not powershell:
            self.skipTest("powershell.exe not available")

        helper = ROOT / "scripts" / "runtime-master-key.ps1"
        with tempfile.TemporaryDirectory() as tempdir:
            command = (
                "$ErrorActionPreference='Stop'; "
                f". '{helper}'; "
                f"$key1 = Ensure-RepoRuntimeMasterKey -RepoRoot '{tempdir}'; "
                f"$key2 = Ensure-RepoRuntimeMasterKey -RepoRoot '{tempdir}'; "
                "Write-Output $key1; "
                "Write-Output $key2"
            )
            result = subprocess.run(
                [powershell, "-NoProfile", "-Command", command],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
            self.assertEqual(len(lines), 2, result.stdout)
            self.assertEqual(lines[0], lines[1])
            self.assertGreater(len(lines[0]), 20)
            self.assertTrue((Path(tempdir) / "runtime" / ".gpu-gov-master-key").exists())


if __name__ == "__main__":
    unittest.main()
