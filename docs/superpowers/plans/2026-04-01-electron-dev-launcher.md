# Electron Dev Launcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a dedicated Windows Electron development launcher that starts the source backend stack on dynamic ports and opens Electron against the live Vite workbench.

**Architecture:** Keep the existing browser launcher unchanged. Add a separate Electron launcher script that mirrors the dynamic port workflow, then teach the Electron main process to detect development URLs and treat backend and agent as external services instead of packaged executables.

**Tech Stack:** PowerShell, Windows batch, Python unittest, Electron, Node.js, Vite

---

### Task 1: Lock the new launcher contract with failing tests

**Files:**
- Modify: `tests/test_start_dev_scripts.py`
- Test: `tests/test_start_dev_scripts.py`

- [ ] **Step 1: Write the failing test**

```python
def test_start_electron_dev_batch_calls_powershell_launcher(self):
    script = (ROOT / "start-electron-dev.bat").read_text(encoding="utf-8")
    self.assertIn(r"scripts\start-electron-dev.ps1", script)

def test_start_electron_dev_ps1_contains_dynamic_port_env_injection(self):
    script = (ROOT / "scripts" / "start-electron-dev.ps1").read_text(encoding="utf-8")
    self.assertIn("DESKTOP_DEV_SERVER_URL", script)
    self.assertIn("DESKTOP_DEV_BACKEND_URL", script)
    self.assertIn("DESKTOP_DEV_AGENT_URL", script)

def test_desktop_shell_supports_dev_server_mode(self):
    script = (ROOT / "desktop-shell" / "main.js").read_text(encoding="utf-8")
    self.assertIn("DESKTOP_DEV_SERVER_URL", script)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -3 -m unittest tests.test_start_dev_scripts -v`
Expected: FAIL because `start-electron-dev.bat` and `scripts/start-electron-dev.ps1` do not exist and `desktop-shell/main.js` lacks Electron dev mode markers.

- [ ] **Step 3: Write minimal implementation**

```text
Add the launcher files and main-process dev-mode helpers required by the assertions.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -3 -m unittest tests.test_start_dev_scripts -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_start_dev_scripts.py start-electron-dev.bat scripts/start-electron-dev.ps1 desktop-shell/main.js
git commit -m "feat: add electron dev launcher"
```

### Task 2: Implement the Windows Electron launcher

**Files:**
- Create: `start-electron-dev.bat`
- Create: `scripts/start-electron-dev.ps1`
- Modify: `tests/test_start_dev_scripts.py`
- Test: `tests/test_start_dev_scripts.py`

- [ ] **Step 1: Write the failing test**

```python
self.assertIn('desktop-shell\\node_modules', script)
self.assertIn("GPU_AGENT_PORT", script)
self.assertIn("AGENT_URL", script)
self.assertIn("DEV_BACKEND_URL", script)
self.assertIn("DESKTOP_DEV_SERVER_URL", script)
self.assertIn("npm run start", script)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -3 -m unittest tests.test_start_dev_scripts -v`
Expected: FAIL because the launcher does not yet include the full validation and Electron command wiring.

- [ ] **Step 3: Write minimal implementation**

```powershell
$desktopShellNodeModules = Join-Path $root "desktop-shell\node_modules"
$desktopCommand = "`$env:DESKTOP_DEV_SERVER_URL='$frontendUrl'; `$env:DESKTOP_DEV_BACKEND_URL='$backendUrl'; `$env:DESKTOP_DEV_AGENT_URL='$agentUrl'; & '$npmCmd' run start"
Start-WindowProcess -Title "GPU Desktop Shell" -Workdir $desktopShellDir -Command $desktopCommand
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -3 -m unittest tests.test_start_dev_scripts -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add start-electron-dev.bat scripts/start-electron-dev.ps1 tests/test_start_dev_scripts.py
git commit -m "feat: add electron dev startup script"
```

### Task 3: Teach Electron to consume development services

**Files:**
- Modify: `desktop-shell/main.js`
- Modify: `tests/test_start_dev_scripts.py`
- Test: `tests/test_start_dev_scripts.py`

- [ ] **Step 1: Write the failing test**

```python
self.assertIn("function desktopDevServerUrl()", script)
self.assertIn("function ensureDesktopDevServices", script)
self.assertIn("markManagedServiceExternal('backend'", script)
self.assertIn("markManagedServiceExternal('agent'", script)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -3 -m unittest tests.test_start_dev_scripts -v`
Expected: FAIL because Electron still always runs packaged bootstrap.

- [ ] **Step 3: Write minimal implementation**

```javascript
function desktopDevServerUrl() { ... }
async function ensureDesktopDevServices(onStatus = () => {}) { ... }
async function launchWorkbench() {
  await createSplashWindow()
  if (desktopDevServerUrl()) {
    await ensureDesktopDevServices(emitBootStatus)
  } else {
    await ensureServices(emitBootStatus)
  }
  await createMainWindow()
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -3 -m unittest tests.test_start_dev_scripts -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add desktop-shell/main.js tests/test_start_dev_scripts.py
git commit -m "feat: support electron dev service mode"
```

### Task 4: Verify the Windows development flow

**Files:**
- Modify: `desktop-shell/package.json` only if command wiring requires it
- Test: `tests/test_start_dev_scripts.py`

- [ ] **Step 1: Run launcher regression tests**

Run: `py -3 -m unittest tests.test_start_dev_scripts -v`
Expected: PASS

- [ ] **Step 2: Run repository regression suite**

Run: `py -3 -m unittest discover -s tests -p test_*.py`
Expected: PASS

- [ ] **Step 3: Run frontend production build**

Run: `cd frontend && npm run build`
Expected: exit code 0

- [ ] **Step 4: Sanity check Electron dependencies**

Run: `cd desktop-shell && npm run start`
Expected: Electron boots against the Vite URL when launched through the new script environment.

- [ ] **Step 5: Commit**

```bash
git add .
git commit -m "test: verify electron dev launcher"
```
