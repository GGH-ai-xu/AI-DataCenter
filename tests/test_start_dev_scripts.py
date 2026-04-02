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
        helper = (ROOT / "scripts" / "electron-dev-session.ps1").read_text(encoding="utf-8")

        self.assertIn('. "$PSScriptRoot\\dev-launch-helpers.ps1"', script)
        self.assertIn('. "$PSScriptRoot\\electron-dev-session.ps1"', script)
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
        self.assertIn("DESKTOP_DEV_SERVER_URL", helper)
        self.assertIn("DESKTOP_DEV_BACKEND_URL", helper)
        self.assertIn("DESKTOP_DEV_AGENT_URL", helper)
        self.assertIn("DESKTOP_DEV_SESSION_FILE", helper)
        self.assertIn("DESKTOP_DEV_LAUNCHER_PID", helper)
        self.assertIn("GPU Desktop Shell", script)
        self.assertNotIn("npm run start", script)
        self.assertIn("Start-ManagedServiceProcess", script)
        self.assertIn("Register-ProcessLogPump", script)
        self.assertIn("Register-ManagedServiceShutdown", script)

    def test_start_electron_dev_ps1_uses_shared_single_terminal_helpers(self):
        script = (ROOT / "scripts" / "start-electron-dev.ps1").read_text(encoding="utf-8")

        self.assertIn('. "$PSScriptRoot\\dev-launch-helpers.ps1"', script)
        self.assertIn('. "$PSScriptRoot\\electron-dev-session.ps1"', script)
        self.assertIn("Start-ManagedServiceProcess", script)
        self.assertIn("Register-ProcessLogPump", script)
        self.assertIn("Register-ManagedServiceShutdown", script)
        self.assertNotIn('Start-WindowProcess -Title "GPU Agent"', script)
        self.assertNotIn('Start-WindowProcess -Title "GPU Backend"', script)
        self.assertNotIn('Start-WindowProcess -Title "GPU Frontend"', script)

    def test_start_electron_dev_ps1_tracks_desktop_shell_lifecycle(self):
        script = (ROOT / "scripts" / "start-electron-dev.ps1").read_text(encoding="utf-8")

        self.assertIn("$desktopBootstrapProcess = Start-DesktopShellProcess", script)
        self.assertIn("$desktopSessionFile = New-DesktopDevSessionFilePath", script)
        self.assertIn("$desktopSessionInfo = Wait-DesktopDevSessionInfo -SessionFile $desktopSessionFile", script)
        self.assertIn("$desktopRootPid = [int]$desktopSessionInfo.pid", script)
        self.assertIn("$desktopProcess = [System.Diagnostics.Process]::GetProcessById", script)
        self.assertIn("Register-EngineEvent -SourceIdentifier PowerShell.Exiting", script)
        self.assertIn("taskkill /PID $event.MessageData.DesktopPid /T /F", script)
        self.assertIn("$desktopProcess.WaitForExit()", script)
        self.assertIn("Desktop shell exited with code", script)
        self.assertNotIn('Start-WindowProcess -Title "GPU Desktop Shell"', script)

    def test_start_electron_dev_ps1_replaces_running_desktop_shell_session_before_starting_new_one(self):
        script = (ROOT / "scripts" / "electron-dev-session.ps1").read_text(encoding="utf-8")
        launcher = (ROOT / "scripts" / "start-electron-dev.ps1").read_text(encoding="utf-8")

        self.assertIn("function Get-RunningDesktopShellRootProcess", script)
        self.assertIn("function Test-DesktopDevSessionPid", script)
        self.assertIn("Stop-OrphanedDesktopShellSession -DesktopRootProcess $existingDesktopProcess -RepoRoot $root", launcher)
        self.assertNotIn("Desktop shell already running", launcher)

    def test_start_electron_dev_ps1_cleans_existing_desktop_session_before_relaunch(self):
        script = (ROOT / "scripts" / "electron-dev-session.ps1").read_text(encoding="utf-8")

        self.assertIn("function Stop-OrphanedDesktopShellSession", script)
        self.assertIn("Found existing Electron dev session", script)
        self.assertIn("taskkill /PID $targetPid /T /F", script)
        self.assertIn("[string]$RepoRoot", script)

    def test_electron_dev_session_helper_waits_for_session_file_and_launcher_path(self):
        script = (ROOT / "scripts" / "electron-dev-session.ps1").read_text(encoding="utf-8")

        self.assertIn("function Prepare-ElectronDevLauncher", script)
        self.assertIn("function New-DesktopDevSessionFilePath", script)
        self.assertIn("function Test-DesktopDevSessionPid", script)
        self.assertIn("function Wait-DesktopDevSessionInfo", script)
        self.assertIn("ConvertFrom-Json", script)
        self.assertIn("Get-Process -Id $desktopPid", script)
        self.assertIn("launcherPid", script)

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

    def test_dev_launch_helpers_register_real_engine_exit_cleanup(self):
        script = (ROOT / "scripts" / "dev-launch-helpers.ps1").read_text(encoding="utf-8")

        self.assertIn("Register-EngineEvent -SourceIdentifier PowerShell.Exiting", script)
        self.assertNotIn('Register-EngineEvent -SourceIdentifier "$($script:EventSourcePrefix).shutdown"', script)

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

    def test_build_desktop_shell_cleans_pyinstaller_runtime_cache(self):
        script = (ROOT / "scripts" / "build-desktop-shell.ps1").read_text(encoding="utf-8")

        self.assertIn("function Reset-BuildTarget", script)
        self.assertIn('Reset-BuildTarget -Name "GPUGovernanceBackend"', script)
        self.assertIn('Reset-BuildTarget -Name "GPUServerAgent"', script)
        self.assertIn('Reset-BuildTarget -Name "GPUGovernanceWorkbench"', script)
        self.assertIn('"PyInstaller", "--clean", "--noconfirm"', script)
        self.assertIn('"--distpath", $distPyInstallerDir', script)
        self.assertIn('"--workpath", $pyInstallerWorkDir', script)

    def test_vite_config_reads_dynamic_proxy_targets(self):
        config = (ROOT / "frontend" / "vite.config.js").read_text(encoding="utf-8")

        self.assertIn("process.env.DEV_BACKEND_URL", config)
        self.assertIn("process.env.DEV_BACKEND_WS_URL", config)

    def test_desktop_shell_supports_dev_server_mode(self):
        script = (ROOT / "desktop-shell" / "main.js").read_text(encoding="utf-8")
        helper = (ROOT / "desktop-shell" / "devSessionBinding.js").read_text(encoding="utf-8")

        self.assertIn("DESKTOP_DEV_SERVER_URL", script)
        self.assertIn("DESKTOP_DEV_BACKEND_URL", script)
        self.assertIn("DESKTOP_DEV_AGENT_URL", script)
        self.assertIn("function desktopDevServerUrl()", script)
        self.assertIn("function ensureDesktopDevServices", script)
        self.assertIn("markManagedServiceExternal('backend'", script)
        self.assertIn("markManagedServiceExternal('agent'", script)
        self.assertIn("DESKTOP_DEV_SESSION_FILE", helper)
        self.assertIn("DESKTOP_DEV_LAUNCHER_PID", helper)

    def test_desktop_shell_uses_explicit_dev_session_binding_module(self):
        script = (ROOT / "desktop-shell" / "main.js").read_text(encoding="utf-8")
        helper = (ROOT / "desktop-shell" / "devSessionBinding.js").read_text(encoding="utf-8")

        self.assertIn("require('./devSessionBinding')", script)
        self.assertIn("writeDesktopDevSession", script)
        self.assertIn("startDesktopDevLauncherWatch", script)
        self.assertIn("clearDesktopDevSession", script)
        self.assertIn("function writeDesktopDevSession()", helper)
        self.assertIn("function startDesktopDevLauncherWatch", helper)
        self.assertIn("process.kill(launcherPid, 0)", helper)

    def test_desktop_shell_uses_distinct_app_user_model_id_for_dev_mode(self):
        script = (ROOT / "desktop-shell" / "main.js").read_text(encoding="utf-8")

        self.assertIn("function currentAppUserModelId()", script)
        self.assertIn("desktopDevModeEnabled() ? `${APP_ID}.dev` : APP_ID", script)
        self.assertIn("app.setAppUserModelId(currentAppUserModelId())", script)

    def test_desktop_shell_dev_mode_close_quits_instead_of_minimize_to_tray(self):
        script = (ROOT / "desktop-shell" / "main.js").read_text(encoding="utf-8")

        self.assertIn("function supportsTrayCloseFlow()", script)
        self.assertIn("function forceDesktopDevShutdownExit(", script)
        self.assertIn("return !desktopDevModeEnabled()", script)
        self.assertIn("if (!supportsTrayCloseFlow()) {", script)
        self.assertIn("void requestAppShutdown()", script)
        self.assertIn("mainWindow.on('closed', () => {\n    mainWindow = null\n    if (!desktopDevModeEnabled()) {\n      return\n    }\n    if (!isQuitting) {\n      void requestAppShutdown()\n      return\n    }\n    forceDesktopDevShutdownExit()\n  })", script)
        self.assertIn("app.on('window-all-closed', () => {\n    if (process.platform === 'darwin') {\n      return\n    }\n    if (desktopDevModeEnabled()) {\n      forceDesktopDevShutdownExit()\n      return\n    }\n    void requestAppShutdown()\n  })", script)
        self.assertNotIn("clearDesktopDevSession()\n    allowWindowClose = true", script)

    def test_start_electron_dev_ps1_cleans_running_process_before_starting_new_session(self):
        script = (ROOT / "scripts" / "start-electron-dev.ps1").read_text(encoding="utf-8")

        self.assertIn("while ($existingDesktopProcess) {", script)
        self.assertIn("Stop-OrphanedDesktopShellSession -DesktopRootProcess $existingDesktopProcess -RepoRoot $root", script)
        self.assertNotIn("Desktop shell already running", script)

    def test_desktop_shell_ignores_activate_and_second_instance_while_quitting(self):
        script = (ROOT / "desktop-shell" / "main.js").read_text(encoding="utf-8")

        self.assertIn("app.on('second-instance', () => {\n    if (isQuitting) {\n      return\n    }", script)
        self.assertIn("app.on('activate', async () => {\n    if (isQuitting) {\n      return\n    }", script)

    def test_desktop_shell_does_not_show_startup_error_during_shutdown(self):
        script = (ROOT / "desktop-shell" / "main.js").read_text(encoding="utf-8")

        self.assertIn("async function launchWorkbenchWithRecovery()", script)
        self.assertIn("async function launchWorkbenchWithRecovery() {\n  if (isQuitting) {\n    closeSplashWindow()\n    return\n  }", script)
        self.assertIn("if (isQuitting || allowWindowClose) {\n      closeSplashWindow()\n      return\n    }", script)
        self.assertIn("emitBootStatus('启动失败，请检查日志目录', 100)\n    await showStartupError(error)", script)
        self.assertIn("closeSplashWindow()", script)

    def test_desktop_shell_release_runtime_aligns_with_start_dev_baseline(self):
        script = (ROOT / "desktop-shell" / "main.js").read_text(encoding="utf-8")

        self.assertIn("webReferenceEntry: 'start-dev.bat'", script)
        self.assertIn("webReferenceLabel: '网页版基准入口：start-dev.bat'", script)
        self.assertIn("function frontendSourceLabel()", script)
        self.assertIn("function backendSourceLabel()", script)
        self.assertIn("function agentSourceLabel()", script)
        self.assertIn("AGENT_URL: agentBaseUrl(agentPort)", script)


if __name__ == "__main__":
    unittest.main()
