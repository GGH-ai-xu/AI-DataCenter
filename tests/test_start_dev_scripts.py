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

        self.assertIn('. "$PSScriptRoot\\dev-launch-helpers.ps1"', script)
        self.assertIn("$agentPort = Get-FreePort", script)
        self.assertIn("$backendPort = Get-FreePort", script)
        self.assertIn("$frontendPort = Get-FreePort", script)
        self.assertIn("GPU_AGENT_PORT", script)
        self.assertIn("AGENT_URL", script)
        self.assertIn("DEV_BACKEND_URL", script)
        self.assertIn("DEV_BACKEND_WS_URL", script)
        self.assertIn('.venv\\Scripts\\python.exe', script)
        self.assertIn('frontend\\node_modules', script)
        self.assertIn('Resolve-NpmCliPath -NodePath $nodeCmd', script)
        self.assertIn("Start-ManagedServiceProcess", script)
        self.assertIn("Register-ProcessLogPump", script)
        self.assertIn("Register-ManagedServiceShutdown", script)
        self.assertIn('-FilePath $nodeCmd', script)
        self.assertIn('$npmCliPath, "run", "dev"', script)

    def test_start_dev_ps1_uses_shared_single_terminal_helpers(self):
        script = (ROOT / "scripts" / "start-dev.ps1").read_text(encoding="utf-8")

        self.assertIn('. "$PSScriptRoot\\dev-launch-helpers.ps1"', script)
        self.assertIn("Start-ManagedServiceProcess", script)
        self.assertIn("Register-ProcessLogPump", script)
        self.assertIn("Register-ManagedServiceShutdown", script)
        self.assertNotIn('Start-WindowProcess -Title "GPU Agent"', script)
        self.assertNotIn('Start-WindowProcess -Title "GPU Backend"', script)
        self.assertNotIn('Start-WindowProcess -Title "GPU Frontend"', script)

    def test_start_electron_dev_ps1_contains_dynamic_port_and_env_injection(self):
        script = (ROOT / "scripts" / "start-electron-dev.ps1").read_text(encoding="utf-8")

        self.assertIn('. "$PSScriptRoot\\dev-launch-helpers.ps1"', script)
        self.assertIn("$agentPort = Get-FreePort", script)
        self.assertIn("$backendPort = Get-FreePort", script)
        self.assertIn("$frontendPort = Get-FreePort", script)
        self.assertIn('.venv\\Scripts\\python.exe', script)
        self.assertIn('frontend\\node_modules', script)
        self.assertIn('desktop-shell\\node_modules', script)
        self.assertIn("Prepare-ElectronDevLauncher", script)
        self.assertIn("GPUGovernanceWorkbench.exe", script)
        self.assertIn("electron.exe", script)
        self.assertNotIn('desktop-shell\\node_modules\\.bin\\electron.cmd', script)
        self.assertIn('Resolve-NpmCliPath -NodePath $nodeCmd', script)
        self.assertIn("GPU_AGENT_PORT", script)
        self.assertIn("AGENT_URL", script)
        self.assertIn("DEV_BACKEND_URL", script)
        self.assertIn("DEV_BACKEND_WS_URL", script)
        self.assertIn("DESKTOP_DEV_SERVER_URL", script)
        self.assertIn("DESKTOP_DEV_BACKEND_URL", script)
        self.assertIn("DESKTOP_DEV_AGENT_URL", script)
        self.assertIn("GPU Desktop Shell", script)
        self.assertNotIn("npm run start", script)
        self.assertIn("Start-ManagedServiceProcess", script)
        self.assertIn("Register-ProcessLogPump", script)
        self.assertIn("Register-ManagedServiceShutdown", script)

    def test_start_electron_dev_ps1_uses_shared_single_terminal_helpers(self):
        script = (ROOT / "scripts" / "start-electron-dev.ps1").read_text(encoding="utf-8")

        self.assertIn('. "$PSScriptRoot\\dev-launch-helpers.ps1"', script)
        self.assertIn("Start-ManagedServiceProcess", script)
        self.assertIn("Register-ProcessLogPump", script)
        self.assertIn("Register-ManagedServiceShutdown", script)
        self.assertNotIn('Start-WindowProcess -Title "GPU Agent"', script)
        self.assertNotIn('Start-WindowProcess -Title "GPU Backend"', script)
        self.assertNotIn('Start-WindowProcess -Title "GPU Frontend"', script)

    def test_start_electron_dev_ps1_launches_desktop_shell_without_powershell_host(self):
        script = (ROOT / "scripts" / "start-electron-dev.ps1").read_text(encoding="utf-8")

        self.assertIn("function Start-DesktopShellProcess", script)
        self.assertIn("Start-Process cmd.exe", script)
        self.assertIn("-WindowStyle Hidden", script)
        self.assertIn('start "" /d', script)
        self.assertNotIn('Start-WindowProcess -Title "GPU Desktop Shell"', script)

    def test_dev_launch_helpers_define_log_prefix_and_cleanup_functions(self):
        script = (ROOT / "scripts" / "dev-launch-helpers.ps1").read_text(encoding="utf-8")

        self.assertIn("function Write-ServiceLog", script)
        self.assertIn("function Start-ManagedServiceProcess", script)
        self.assertIn("function Register-ProcessLogPump", script)
        self.assertIn("function Stop-ManagedServiceProcesses", script)
        self.assertIn("[ConsoleCancelEventHandler]", script)

    def test_dev_launch_helpers_use_utf8_process_decoding_and_strip_ansi(self):
        script = (ROOT / "scripts" / "dev-launch-helpers.ps1").read_text(encoding="utf-8")

        self.assertIn("StandardOutputEncoding = [System.Text.Encoding]::UTF8", script)
        self.assertIn("StandardErrorEncoding = [System.Text.Encoding]::UTF8", script)
        self.assertIn("function Normalize-ServiceLogMessage", script)
        self.assertIn("[System.Text.RegularExpressions.Regex]::Replace", script)

    def test_dev_launchers_initialize_utf8_console_output(self):
        helper = (ROOT / "scripts" / "dev-launch-helpers.ps1").read_text(encoding="utf-8")
        start_dev = (ROOT / "scripts" / "start-dev.ps1").read_text(encoding="utf-8")
        start_electron = (ROOT / "scripts" / "start-electron-dev.ps1").read_text(encoding="utf-8")

        self.assertIn("function Initialize-ConsoleEncoding", helper)
        self.assertIn("[Console]::OutputEncoding = [System.Text.Encoding]::UTF8", helper)
        self.assertIn("$OutputEncoding = [System.Text.Encoding]::UTF8", helper)
        self.assertIn("Initialize-ConsoleEncoding", start_dev)
        self.assertIn("Initialize-ConsoleEncoding", start_electron)

    def test_python_launchers_force_utf8_stdio_for_single_terminal_logs(self):
        start_dev = (ROOT / "scripts" / "start-dev.ps1").read_text(encoding="utf-8")
        start_electron = (ROOT / "scripts" / "start-electron-dev.ps1").read_text(encoding="utf-8")

        self.assertIn('PYTHONIOENCODING = "utf-8"', start_dev)
        self.assertIn('PYTHONUTF8 = "1"', start_dev)
        self.assertIn('PYTHONIOENCODING = "utf-8"', start_electron)
        self.assertIn('PYTHONUTF8 = "1"', start_electron)

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

    def test_desktop_shell_uses_distinct_app_user_model_id_for_dev_mode(self):
        script = (ROOT / "desktop-shell" / "main.js").read_text(encoding="utf-8")

        self.assertIn("function currentAppUserModelId()", script)
        self.assertIn("desktopDevModeEnabled() ? `${APP_ID}.dev` : APP_ID", script)
        self.assertIn("app.setAppUserModelId(currentAppUserModelId())", script)


if __name__ == "__main__":
    unittest.main()
