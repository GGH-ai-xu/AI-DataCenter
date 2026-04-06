import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DevConsoleHelperTests(unittest.TestCase):
    def test_dev_launch_helpers_sources_console_helper(self):
        script = (ROOT / "scripts" / "dev-launch-helpers.ps1").read_text(encoding="utf-8")

        self.assertIn('. "$PSScriptRoot\\dev-console-helpers.ps1"', script)

    def test_console_helper_writes_logs_through_console_stream(self):
        script = (ROOT / "scripts" / "dev-console-helpers.ps1").read_text(encoding="utf-8")

        self.assertIn("function Write-ConsoleLine", script)
        self.assertIn("[System.Threading.Monitor]::Enter($script:ConsoleWriteLock)", script)
        self.assertIn("[Console]::Out.WriteLine($Message)", script)
        self.assertIn("[Console]::Out.Flush()", script)
        self.assertNotIn("Write-Host", script)

    def test_console_helper_initializes_utf8_console_io(self):
        script = (ROOT / "scripts" / "dev-console-helpers.ps1").read_text(encoding="utf-8")

        self.assertIn("[Console]::InputEncoding = $utf8", script)
        self.assertIn("[Console]::OutputEncoding = $utf8", script)
        self.assertIn("$OutputEncoding = $utf8", script)


if __name__ == "__main__":
    unittest.main()
