import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class StartDevScriptTests(unittest.TestCase):
    def test_start_dev_batch_calls_powershell_launcher(self):
        script = (ROOT / "start-dev.bat").read_text(encoding="utf-8")

        self.assertIn(r"scripts\start-dev.ps1", script)

    def test_start_dev_ps1_contains_dynamic_port_and_env_injection(self):
        script = (ROOT / "scripts" / "start-dev.ps1").read_text(encoding="utf-8")

        self.assertIn("function Get-FreePort", script)
        self.assertIn("$agentPort = Get-FreePort", script)
        self.assertIn("$backendPort = Get-FreePort", script)
        self.assertIn("$frontendPort = Get-FreePort", script)
        self.assertIn("GPU_AGENT_PORT", script)
        self.assertIn("AGENT_URL", script)
        self.assertIn("DEV_BACKEND_URL", script)
        self.assertIn("DEV_BACKEND_WS_URL", script)
        self.assertIn('.venv\\Scripts\\python.exe', script)
        self.assertIn('frontend\\node_modules', script)
        self.assertIn("`$env:GPU_AGENT_PORT", script)
        self.assertIn("`$env:PORT", script)
        self.assertIn("`$env:AGENT_URL", script)
        self.assertIn("`$env:DEV_BACKEND_URL", script)
        self.assertIn("`$env:DEV_BACKEND_WS_URL", script)

    def test_vite_config_reads_dynamic_proxy_targets(self):
        config = (ROOT / "frontend" / "vite.config.js").read_text(encoding="utf-8")

        self.assertIn("process.env.DEV_BACKEND_URL", config)
        self.assertIn("process.env.DEV_BACKEND_WS_URL", config)


if __name__ == "__main__":
    unittest.main()
