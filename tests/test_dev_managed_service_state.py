import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DevManagedServiceStateTests(unittest.TestCase):
    def test_repository_managed_process_match_uses_cim_creation_date_when_runtime_process_is_missing(self):
        powershell = shutil.which("powershell.exe")
        if not powershell:
            self.skipTest("powershell.exe not available")

        helper = ROOT / "scripts" / "dev-managed-service-state.ps1"
        helper_windows = subprocess.run(
            ["wslpath", "-w", str(helper)],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        command = (
            "$ErrorActionPreference='Stop'; "
            f". '{helper_windows}'; "
            "$entry = [pscustomobject]@{"
            "ServiceName='Frontend'; "
            "ProcessId=321; "
            "StartTime='2026-04-09T03:04:05.0000000Z'; "
            "ExecutablePath='C:\\\\Program Files\\\\nodejs\\\\node.exe'; "
            "Signature=@('npm-cli.js', 'run', 'dev')"
            "}; "
            "$snapshot = [pscustomobject]@{"
            "RuntimeProcess=$null; "
            "CimProcess=[pscustomobject]@{"
            "ExecutablePath='C:\\\\Program Files\\\\nodejs\\\\node.exe'; "
            "CommandLine='\"C:\\\\Program Files\\\\nodejs\\\\node.exe\" npm-cli.js run dev'; "
            "CreationDate='20260409030405.000000+000'"
            "}"
            "}; "
            "$result = Test-RepositoryManagedStartDevProcess -Entry $entry -Snapshot $snapshot; "
            "Write-Output $result"
        )
        result = subprocess.run(
            [powershell, "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "True", result.stdout)


if __name__ == "__main__":
    unittest.main()
