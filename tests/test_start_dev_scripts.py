import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class StartDevScriptTests(unittest.TestCase):
    def test_install_deps_batch_calls_all_setup_scripts(self):
        script = (ROOT / "install-deps.bat").read_text(encoding="utf-8")

        self.assertIn(r"scripts\setup-uv-env.ps1", script)
        self.assertIn(r"scripts\setup-frontend.ps1", script)
        self.assertIn(r"scripts\setup-desktop-shell.ps1", script)

    def test_start_dev_batch_calls_powershell_launcher(self):
        script = (ROOT / "start-dev.bat").read_text(encoding="utf-8")

        self.assertIn(r"scripts\start-dev.ps1", script)

    def test_start_electron_dev_batch_calls_powershell_launcher(self):
        script = (ROOT / "start-electron-dev.bat").read_text(encoding="utf-8")

        self.assertIn(r"scripts\start-electron-dev.ps1", script)

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

    def test_start_electron_dev_ps1_contains_dynamic_port_and_env_injection(self):
        script = (ROOT / "scripts" / "start-electron-dev.ps1").read_text(encoding="utf-8")

        self.assertIn("function Get-FreePort", script)
        self.assertIn("$agentPort = Get-FreePort", script)
        self.assertIn("$backendPort = Get-FreePort", script)
        self.assertIn("$frontendPort = Get-FreePort", script)
        self.assertIn('.venv\\Scripts\\python.exe', script)
        self.assertIn('frontend\\node_modules', script)
        self.assertIn('desktop-shell\\node_modules', script)
        self.assertIn('desktop-shell\\node_modules\\.bin\\electron.cmd', script)
        self.assertIn("GPU_AGENT_PORT", script)
        self.assertIn("AGENT_URL", script)
        self.assertIn("DEV_BACKEND_URL", script)
        self.assertIn("DEV_BACKEND_WS_URL", script)
        self.assertIn("DESKTOP_DEV_SERVER_URL", script)
        self.assertIn("DESKTOP_DEV_BACKEND_URL", script)
        self.assertIn("DESKTOP_DEV_AGENT_URL", script)
        self.assertIn("GPU Desktop Shell", script)
        self.assertIn("npm run start", script)

    def test_setup_desktop_shell_installs_desktop_dependencies(self):
        script = (ROOT / "scripts" / "setup-desktop-shell.ps1").read_text(encoding="utf-8")

        self.assertIn('desktop-shell', script)
        self.assertIn("npm", script)
        self.assertIn("ci", script)
        self.assertIn("--include=dev", script)
        self.assertIn("ELECTRON_MIRROR", script)
        self.assertIn("npmmirror.com/mirrors/electron/", script)
        self.assertIn("Desktop shell dependencies installed.", script)

    def test_vite_config_reads_dynamic_proxy_targets(self):
        config = (ROOT / "frontend" / "vite.config.js").read_text(encoding="utf-8")

        self.assertIn("process.env.DEV_BACKEND_URL", config)
        self.assertIn("process.env.DEV_BACKEND_WS_URL", config)

    def test_desktop_shell_supports_dev_server_mode(self):
        script = (ROOT / "desktop-shell" / "main.js").read_text(encoding="utf-8")

        self.assertIn("DESKTOP_DEV_SERVER_URL", script)
        self.assertIn("DESKTOP_DEV_BACKEND_URL", script)
        self.assertIn("DESKTOP_DEV_AGENT_URL", script)
        self.assertIn("function desktopDevServerUrl()", script)
        self.assertIn("function ensureDesktopDevServices", script)
        self.assertIn("markManagedServiceExternal('backend'", script)
        self.assertIn("markManagedServiceExternal('agent'", script)


if __name__ == "__main__":
    unittest.main()
