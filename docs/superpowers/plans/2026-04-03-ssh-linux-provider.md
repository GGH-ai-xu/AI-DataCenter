# SSH Linux Provider Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Linux-only SSH runtime provider that lets `/import` scan, import, monitor, and govern selected GPUs without deploying the host-side HTTP Agent.

**Architecture:** Keep the existing import-layer-to-console boundary, but replace the hardwired `AgentClient` dependency with a provider abstraction. Extend the current connection/import APIs to accept provider-aware payloads, add an `SshLinuxProvider` backed by `asyncssh` plus native Linux commands, and keep the console scoped to the imported GPU indexes through the existing `ImportContextService`.

**Tech Stack:** FastAPI, Pydantic, `asyncssh`, existing `AgentClient`, existing import-context and runtime-scope services, Vue 3 `<script setup>`, Pinia, `node:test`, Python `unittest`, Vite build verification.

---

## File Map

**Create:**
- `backend/app/services/runtime_provider.py`
  Purpose: define the provider protocol and immutable runtime target model shared by HTTP and SSH implementations.
- `backend/app/services/http_agent_provider.py`
  Purpose: adapt the current HTTP Agent behavior to the new provider interface without changing payload shapes.
- `backend/app/services/runtime_provider_manager.py`
  Purpose: own the active provider, runtime status, probe/switch flows, and disconnect-reconnect state machine.
- `backend/app/services/credential_store.py`
  Purpose: persist SSH credentials separately from non-sensitive target config and return masked snapshots for APIs.
- `backend/app/services/ssh_command_executor.py`
  Purpose: execute SSH commands, wrap `sudo -S`, pin host fingerprints, and capture stdout/stderr/timeouts in one place.
- `backend/app/services/ssh_linux_parsers.py`
  Purpose: parse `nvidia-smi`, `ps`, and `/proc` output into the exact GPU/system/process structures the frontend already consumes.
- `backend/app/services/ssh_linux_provider.py`
  Purpose: implement realtime reads and governance actions for Linux hosts through SSH.
- `tests/test_runtime_provider_manager.py`
  Purpose: lock provider switching, active-provider closing, reconnect state transitions, and invalidation thresholds.
- `tests/test_credential_store.py`
  Purpose: lock secret persistence, masking, and overwrite semantics.
- `tests/test_ssh_linux_provider.py`
  Purpose: lock SSH command parsing, sudo behavior, host fingerprint validation, and Linux control commands.
- `tests/test_ssh_import_flow.py`
  Purpose: lock provider-aware scan/import API behavior and imported-GPU validation for SSH targets.

**Modify:**
- `backend/requirements.txt`
  Purpose: add the async SSH dependency used by the backend runtime provider.
- `backend/app/services/connection_settings.py`
  Purpose: evolve the existing config service from HTTP-only settings to provider-aware runtime target persistence.
- `backend/app/models/schemas.py`
  Purpose: add provider-aware request models for scan/import and SSH credentials.
- `backend/app/services/import_context.py`
  Purpose: store provider metadata with the imported GPU scope.
- `backend/app/services/collection_pipeline.py`
  Purpose: keep the concurrent snapshot helper provider-agnostic.
- `backend/app/main.py`
  Purpose: bootstrap the provider manager, expose runtime status in health, and route collection/governance through the active provider.
- `backend/app/api/system.py`
  Purpose: accept provider-aware payloads, return masked SSH/runtime state, and switch runtime targets during import commit.
- `backend/app/services/scheduler.py`
  Purpose: resolve the current provider through the manager before executing control actions after re-import or reconnect.
- `backend/app/services/ai_control.py`
  Purpose: execute AI-driven governance through the current provider instead of a fixed HTTP client.
- `tests/test_connection_settings.py`
  Purpose: replace HTTP-only assumptions with provider-aware normalization and persistence expectations.
- `tests/test_import_layer_structure.py`
  Purpose: lock the SSH import form fields and provider-type wiring in the frontend.
- `frontend/src/services/api.js`
  Purpose: send provider-aware scan/import payloads.
- `frontend/src/views/ImportWorkspace.vue`
  Purpose: hold provider selection, SSH auth inputs, scan feedback, and import submission.
- `frontend/src/components/import/ImportSourcePanel.vue`
  Purpose: render `http_local`, `http_remote`, and `ssh_linux` source modes and their provider-specific fields.
- `frontend/src/components/import/ImportHardwareSummary.vue`
  Purpose: show SSH capability results such as host fingerprint, sudo readiness, and runtime target summary.
- `frontend/src/stores/app.js`
  Purpose: store provider-aware runtime status without treating `reconnecting` as “needs redirect”.
- `frontend/src/App.vue`
  Purpose: keep route gating tied to import-context validity while surfacing provider/reconnect status in the shell.
- `frontend/src/lib/importContext.js`
  Purpose: add small helpers for formatting provider-aware import labels.
- `frontend/src/lib/importContext.test.js`
  Purpose: cover any new provider label helpers.
- `frontend/src/stores/app.test.js`
  Purpose: lock reconnect-aware store behavior and provider-aware realtime payload handling.

### Task 1: Introduce Provider-Aware Runtime Core

**Files:**
- Create: `backend/app/services/runtime_provider.py`
- Create: `backend/app/services/http_agent_provider.py`
- Create: `backend/app/services/runtime_provider_manager.py`
- Modify: `backend/app/services/connection_settings.py`
- Modify: `tests/test_connection_settings.py`
- Create: `tests/test_runtime_provider_manager.py`

- [ ] **Step 1: Write failing backend tests for provider-aware config normalization and manager switching**

Add these tests:

```python
# tests/test_connection_settings.py
def test_normalize_ssh_target_payload(self):
    target = self.service.normalize_payload({
        "provider_type": "ssh_linux",
        "label": "训练机 A",
        "host": "10.0.0.8",
        "port": 22,
        "username": "gpuops",
        "auth_type": "password",
        "sudo_enabled": True,
        "host_fingerprint": "SHA256:demo",
    })
    self.assertEqual(target.provider_type, "ssh_linux")
    self.assertEqual(target.host, "10.0.0.8")
    self.assertEqual(target.username, "gpuops")
    self.assertTrue(target.sudo_enabled)

# tests/test_runtime_provider_manager.py
class FakeProvider:
    def __init__(self, name):
        self.name = name
        self.closed = False
    async def close(self):
        self.closed = True

async def test_switch_closes_previous_provider(self):
    manager = RuntimeProviderManager(lambda target, secret: FakeProvider(target.label))
    first = await manager.switch(FakeTarget(label="A"), None)
    second = await manager.switch(FakeTarget(label="B"), None)
    assert first.closed is True
    assert second.name == "B"
```

- [ ] **Step 2: Run the new tests to confirm the runtime provider modules do not exist yet**

Run:

```bash
cmd.exe /c "cd /d E:\Code\AI-DataCenter && .\.venv\Scripts\python.exe -m unittest tests.test_connection_settings tests.test_runtime_provider_manager -v"
```

Expected:

- FAIL with `AttributeError` or `ModuleNotFoundError` for `normalize_payload`, `runtime_provider`, or `RuntimeProviderManager`.

- [ ] **Step 3: Implement the provider protocol, HTTP adapter, provider manager, and provider-aware connection settings**

Add the core runtime model and manager:

```python
# backend/app/services/runtime_provider.py
from dataclasses import dataclass
from typing import Literal, Protocol

ProviderType = Literal["http_local", "http_remote", "ssh_linux"]
AuthType = Literal["password", "private_key"]

@dataclass(frozen=True)
class RuntimeTarget:
    provider_type: ProviderType
    label: str
    agent_url: str | None = None
    host: str | None = None
    port: int | None = None
    username: str | None = None
    auth_type: AuthType | None = None
    sudo_enabled: bool = False
    host_fingerprint: str | None = None
    credential_id: str | None = None

class RuntimeProvider(Protocol):
    async def health_check(self) -> dict | None: ...
    async def get_all_gpus(self) -> list[dict]: ...
    async def get_system_info(self) -> dict | None: ...
    async def get_processes(self) -> list[dict]: ...
    async def set_power_limit(self, gpu_index: int, power_limit: int) -> dict: ...
    async def pause_task(self, pid: int) -> dict: ...
    async def resume_task(self, pid: int) -> dict: ...
    async def terminate_task(self, pid: int) -> dict: ...
    async def close(self) -> None: ...
```

```python
# backend/app/services/http_agent_provider.py
class HttpAgentProvider:
    def __init__(self, target: RuntimeTarget):
        self.target = target
        self.client = AgentClient(target.agent_url or "")
```

```python
# backend/app/services/runtime_provider_manager.py
class RuntimeProviderManager:
    def __init__(self, factory, reconnect_limit: int = 6):
        self._factory = factory
        self._provider = None
        self._target = None
        self._reconnect_limit = reconnect_limit
        self._reconnect_failures = 0
        self._status = "idle"

    async def switch(self, target: RuntimeTarget, secret: dict | None):
        next_provider = await self._factory(target, secret)
        previous = self._provider
        self._provider = next_provider
        self._target = target
        self._status = "connected"
        self._reconnect_failures = 0
        if previous:
            await previous.close()
        return next_provider

    async def probe_target(self, target: RuntimeTarget, secret: dict | None):
        provider = await self._factory(target, secret)
        try:
            health = await provider.health_check()
            return {"status": "connected" if health else "offline", "health": health}
        finally:
            await provider.close()

    async def current_provider(self):
        return self._provider

    async def status(self) -> dict:
        return {"status": self._status, "target": self._target}

    async def mark_failure(self, reason: str) -> dict:
        self._reconnect_failures += 1
        self._status = "invalid" if self._reconnect_failures >= self._reconnect_limit else "reconnecting"
        return {"status": self._status, "reason": reason, "failures": self._reconnect_failures}
```

```python
# backend/app/services/connection_settings.py
def normalize_payload(self, payload: dict) -> RuntimeTarget:
    provider_type = payload.get("provider_type") or "http_local"
    if provider_type == "ssh_linux":
        return RuntimeTarget(
            provider_type="ssh_linux",
            label=(payload.get("label") or "SSH Linux").strip(),
            host=(payload.get("host") or "").strip(),
            port=int(payload.get("port") or 22),
            username=(payload.get("username") or "").strip(),
            auth_type=payload.get("auth_type") or "password",
            sudo_enabled=bool(payload.get("sudo_enabled")),
            host_fingerprint=(payload.get("host_fingerprint") or "").strip() or None,
            credential_id=payload.get("credential_id"),
        )

def update_target(self, target: RuntimeTarget, credential_id: str | None = None) -> RuntimeTarget:
    persisted = replace(target, credential_id=credential_id or target.credential_id)
    self._state = asdict(persisted)
    self._persist()
    return persisted
```

- [ ] **Step 4: Run the provider-core backend tests again**

Run:

```bash
cmd.exe /c "cd /d E:\Code\AI-DataCenter && .\.venv\Scripts\python.exe -m unittest tests.test_connection_settings tests.test_runtime_provider_manager -v"
```

Expected:

- PASS with provider-aware normalization and manager switching covered.

- [ ] **Step 5: Commit the provider-core slice**

```bash
git add backend/app/services/runtime_provider.py backend/app/services/http_agent_provider.py backend/app/services/runtime_provider_manager.py backend/app/services/connection_settings.py tests/test_connection_settings.py tests/test_runtime_provider_manager.py
git commit -m "feat: add provider-aware runtime core"
```

### Task 2: Add Credential Storage And SSH Linux Provider

**Files:**
- Create: `backend/app/services/credential_store.py`
- Create: `backend/app/services/ssh_command_executor.py`
- Create: `backend/app/services/ssh_linux_parsers.py`
- Create: `backend/app/services/ssh_linux_provider.py`
- Create: `tests/test_credential_store.py`
- Create: `tests/test_ssh_linux_provider.py`
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Write failing tests for masked secret storage, host fingerprint pinning, GPU CSV parsing, and sudo command wrapping**

Add these tests:

```python
# tests/test_credential_store.py
def test_save_and_mask_password_secret(self):
    store = CredentialStore(self.secret_path)
    credential_id = store.save({"password": "secret", "sudo_password": "rootpw"})
    masked = store.masked_snapshot(credential_id)
    self.assertEqual(masked["password"], "********")
    self.assertEqual(masked["sudo_password"], "********")

# tests/test_ssh_linux_provider.py
def test_parse_gpu_query_output(self):
    rows = "0, GPU-aaa, RTX 4090, 61, 280.5, 320.0, 87, 40, 8192, 24564, 16372, 35, 2100, 10500\n"
    parsed = parse_gpu_rows(rows, timestamp=1.0)
    self.assertEqual(parsed[0]["index"], 0)
    self.assertEqual(parsed[0]["name"], "RTX 4090")
    self.assertEqual(parsed[0]["power_limit"], 320.0)

async def test_executor_wraps_sudo_command_and_rejects_fingerprint_mismatch(self):
    executor = SshCommandExecutor(target, {"password": "pw", "sudo_password": "rootpw"})
    with self.assertRaisesRegex(ValueError, "host fingerprint"):
        await executor.connect()
```

- [ ] **Step 2: Run the SSH-specific tests to confirm the SSH runtime layer does not exist yet**

Run:

```bash
cmd.exe /c "cd /d E:\Code\AI-DataCenter && .\.venv\Scripts\python.exe -m unittest tests.test_credential_store tests.test_ssh_linux_provider -v"
```

Expected:

- FAIL because `CredentialStore`, `SshCommandExecutor`, or parser/provider symbols are missing.

- [ ] **Step 3: Implement the secret store, SSH executor, parser helpers, provider, and dependency**

Add the dependency:

```txt
# backend/requirements.txt
asyncssh==2.17.0
```

Add the SSH runtime building blocks:

```python
# backend/app/services/credential_store.py
class CredentialStore:
    def save(self, payload: dict) -> str:
        credential_id = payload.get("credential_id") or secrets.token_hex(12)
        self._data[credential_id] = {k: v for k, v in payload.items() if v}
        self._persist()
        return credential_id

    def read(self, credential_id: str) -> dict:
        return dict(self._data.get(credential_id, {}))

    def masked_snapshot(self, credential_id: str) -> dict:
        return {key: "********" for key in self.read(credential_id)}
```

```python
# backend/app/services/ssh_command_executor.py
async def connect(self) -> None:
    key = asyncssh.import_private_key(self.secret["private_key"], self.secret.get("private_key_passphrase")) if self.secret.get("private_key") else None
    self._connection = await asyncssh.connect(self.target.host, port=self.target.port, username=self.target.username, known_hosts=None, password=self.secret.get("password") or None, client_keys=[key] if key else None)
    actual = self._connection.get_server_host_key().get_fingerprint()
    if self.target.host_fingerprint and actual != self.target.host_fingerprint:
        raise ValueError(f"host fingerprint mismatch: {actual}")

async def run(self, command: str, use_sudo: bool = False, timeout: float = 10.0) -> CommandResult:
    wrapped = f"sudo -S -p '' {command}" if use_sudo else command
    result = await self._connection.run(wrapped, input=self._sudo_input(use_sudo), check=False, timeout=timeout)
    return CommandResult(code=result.exit_status, stdout=result.stdout, stderr=result.stderr)
```

```python
# backend/app/services/ssh_linux_parsers.py
def parse_gpu_rows(raw: str, timestamp: float) -> list[dict]:
    rows = []
    for line in raw.splitlines():
        index, uuid, name, temp, power_usage, power_limit, gpu_util, mem_util, mem_used, mem_total, mem_free, fan, sm_clock, mem_clock = [part.strip() for part in line.split(",")]
        rows.append({"index": int(index), "uuid": uuid, "name": name, "temperature": int(temp), "power_usage": float(power_usage), "power_limit": float(power_limit), "gpu_utilization": int(gpu_util), "memory_utilization": int(mem_util), "memory_used": int(mem_used), "memory_total": int(mem_total), "memory_free": int(mem_free), "fan_speed": int(fan), "clock_sm": int(sm_clock), "clock_mem": int(mem_clock), "timestamp": timestamp})
    return rows
```

```python
# backend/app/services/ssh_linux_provider.py
class SshLinuxProvider:
    async def get_all_gpus(self) -> list[dict]:
        raw = await self.executor.run(NVIDIA_SMI_GPU_QUERY)
        return parse_gpu_rows(raw.stdout, time.time())

    async def set_power_limit(self, gpu_index: int, power_limit: int) -> dict:
        cmd = f"nvidia-smi -i {int(gpu_index)} -pl {int(power_limit)}"
        result = await self.executor.run(cmd, use_sudo=True)
        return {"success": result.code == 0, "gpu_index": gpu_index, "power_limit": power_limit, "error": result.stderr.strip()}
```

- [ ] **Step 4: Run the SSH-layer tests again**

Run:

```bash
cmd.exe /c "cd /d E:\Code\AI-DataCenter && .\.venv\Scripts\python.exe -m unittest tests.test_credential_store tests.test_ssh_linux_provider -v"
```

Expected:

- PASS with parser, masking, sudo, and fingerprint checks covered.

- [ ] **Step 5: Commit the SSH runtime slice**

```bash
git add backend/requirements.txt backend/app/services/credential_store.py backend/app/services/ssh_command_executor.py backend/app/services/ssh_linux_parsers.py backend/app/services/ssh_linux_provider.py tests/test_credential_store.py tests/test_ssh_linux_provider.py
git commit -m "feat: add ssh linux runtime provider"
```

### Task 3: Extend Import APIs To Accept Provider-Aware Payloads

**Files:**
- Modify: `backend/app/models/schemas.py`
- Modify: `backend/app/services/import_context.py`
- Modify: `backend/app/api/system.py`
- Create: `tests/test_ssh_import_flow.py`

- [ ] **Step 1: Write failing API tests for SSH scan/import and imported GPU validation**

Add these tests:

```python
async def test_scan_import_context_returns_ssh_capabilities(self):
    response = await scan_import_context(ImportScanRequest(
        provider={"provider_type": "ssh_linux", "label": "训练机 A", "host": "10.0.0.8", "port": 22, "username": "gpuops", "auth_type": "password", "sudo_enabled": True},
        credentials={"password": "secret", "sudo_password": "rootpw"},
    ))
    self.assertTrue(response["success"])
    self.assertEqual(response["provider"]["provider_type"], "ssh_linux")
    self.assertIn("host_fingerprint", response["capabilities"])

async def test_commit_import_context_rejects_missing_selected_gpu(self):
    with self.assertRaises(HTTPException):
        await commit_import_context(ImportCommitRequest(
            provider={"provider_type": "ssh_linux", "label": "训练机 A", "host": "10.0.0.8", "port": 22, "username": "gpuops", "auth_type": "password", "sudo_enabled": True},
            credentials={"password": "secret", "sudo_password": "rootpw"},
            gpu_indexes=[9],
        ))
```

- [ ] **Step 2: Run the import-flow tests to verify the old schema cannot satisfy them**

Run:

```bash
cmd.exe /c "cd /d E:\Code\AI-DataCenter && .\.venv\Scripts\python.exe -m unittest tests.test_ssh_import_flow -v"
```

Expected:

- FAIL because `ImportScanRequest` and `ImportCommitRequest` are still HTTP-only.

- [ ] **Step 3: Implement provider-aware request models, import metadata, and system API wiring**

Make the request schema explicit:

```python
# backend/app/models/schemas.py
class ProviderConfigRequest(BaseModel):
    provider_type: str = Field(pattern=r"^(http_local|http_remote|ssh_linux)$")
    label: str = Field(default="", max_length=120)
    agent_url: str | None = Field(default=None, max_length=300)
    host: str | None = Field(default=None, max_length=255)
    port: int | None = Field(default=None, ge=1, le=65535)
    username: str | None = Field(default=None, max_length=120)
    auth_type: str | None = Field(default=None, pattern=r"^(password|private_key)$")
    sudo_enabled: bool = False
    host_fingerprint: str | None = Field(default=None, max_length=200)

class CredentialPayloadRequest(BaseModel):
    password: str = Field(default="", max_length=5000)
    private_key: str = Field(default="", max_length=20000)
    private_key_passphrase: str = Field(default="", max_length=5000)
    sudo_password: str = Field(default="", max_length=5000)
```

Thread provider metadata into the import context and API:

```python
# backend/app/services/import_context.py
"provider_type": provider_type,
"source_label": source_label,
"target_summary": target_summary,
```

```python
# backend/app/api/system.py
target = app_state.connection.normalize_payload(req.provider.model_dump())
probe = await app_state.runtime.probe_target(target, req.credentials.model_dump())
credential_id = app_state.credentials.save(req.credentials.model_dump())
saved_target = app_state.connection.update_target(target, credential_id=credential_id)
await app_state.runtime.switch(saved_target, app_state.credentials.read(credential_id))
```

- [ ] **Step 4: Run the import-flow tests again**

Run:

```bash
cmd.exe /c "cd /d E:\Code\AI-DataCenter && .\.venv\Scripts\python.exe -m unittest tests.test_ssh_import_flow tests.test_import_context -v"
```

Expected:

- PASS with provider-aware scan/commit payloads and SSH import metadata persisted.

- [ ] **Step 5: Commit the provider-aware import API slice**

```bash
git add backend/app/models/schemas.py backend/app/services/import_context.py backend/app/api/system.py tests/test_ssh_import_flow.py
git commit -m "feat: add provider-aware import api"
```

### Task 4: Route Collection And Governance Through The Active Provider

**Files:**
- Modify: `backend/app/services/collection_pipeline.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/services/scheduler.py`
- Modify: `backend/app/services/ai_control.py`
- Modify: `tests/test_runtime_provider_manager.py`
- Modify: `tests/test_performance_hotpaths.py`

- [ ] **Step 1: Add failing tests for reconnect transitions and provider-agnostic collection**

Add these tests:

```python
# tests/test_runtime_provider_manager.py
async def test_mark_failure_transitions_to_invalid_after_limit(self):
    manager = RuntimeProviderManager(factory, reconnect_limit=2)
    await manager.switch(FakeTarget(label="A"), None)
    await manager.mark_failure("dial tcp timeout")
    state = await manager.mark_failure("dial tcp timeout")
    assert state["status"] == "invalid"

# tests/test_performance_hotpaths.py
snapshot = await collect_agent_snapshot(FakeProvider())
self.assertEqual(snapshot["system"]["cpu_percent"], 12.5)
```

- [ ] **Step 2: Run the runtime-manager and hotpath tests to confirm reconnect logic is still missing**

Run:

```bash
cmd.exe /c "cd /d E:\Code\AI-DataCenter && .\.venv\Scripts\python.exe -m unittest tests.test_runtime_provider_manager tests.test_performance_hotpaths -v"
```

Expected:

- FAIL because `mark_failure` or provider-aware runtime state is not implemented yet.

- [ ] **Step 3: Update the collection loop, scheduler, and AI control to use the manager’s active provider and reconnect state**

Implement the manager-driven runtime access:

```python
# backend/app/services/collection_pipeline.py
async def collect_agent_snapshot(provider) -> dict[str, Any]:
    gpus, system, processes = await asyncio.gather(
        provider.get_all_gpus(),
        provider.get_system_info(),
        provider.get_processes(),
    )
```

```python
# backend/app/main.py
provider = await app_state.runtime.current_provider()
snapshot, priorities = await asyncio.gather(
    collect_agent_snapshot(provider),
    app_state.store.get_all_task_priorities(),
)
connection = app_state.connection.snapshot(await app_state.runtime.status())
```

```python
# backend/app/services/scheduler.py
provider = await self.runtime_manager.current_provider()
response = await provider.set_power_limit(target["gpu_index"], target["power_limit"])
```

```python
# backend/app/services/ai_control.py
provider = await app_state.runtime.current_provider()
response = await provider.pause_task(target["pid"])
```

- [ ] **Step 4: Run the runtime-manager and hotpath tests again**

Run:

```bash
cmd.exe /c "cd /d E:\Code\AI-DataCenter && .\.venv\Scripts\python.exe -m unittest tests.test_runtime_provider_manager tests.test_performance_hotpaths tests.test_scheduler -v"
```

Expected:

- PASS with reconnect status, concurrent collection, and control actions routed through the active provider.

- [ ] **Step 5: Commit the active-provider routing slice**

```bash
git add backend/app/services/collection_pipeline.py backend/app/main.py backend/app/services/scheduler.py backend/app/services/ai_control.py tests/test_runtime_provider_manager.py tests/test_performance_hotpaths.py
git commit -m "feat: route runtime operations through provider manager"
```

### Task 5: Rebuild `/import` Around SSH Provider Inputs

**Files:**
- Modify: `frontend/src/views/ImportWorkspace.vue`
- Modify: `frontend/src/components/import/ImportSourcePanel.vue`
- Modify: `frontend/src/components/import/ImportHardwareSummary.vue`
- Modify: `frontend/src/services/api.js`
- Modify: `frontend/src/stores/app.js`
- Modify: `frontend/src/App.vue`
- Modify: `frontend/src/lib/importContext.js`
- Modify: `frontend/src/lib/importContext.test.js`
- Modify: `frontend/src/stores/app.test.js`
- Modify: `tests/test_import_layer_structure.py`

- [ ] **Step 1: Write failing frontend structure and store tests for provider selection, SSH auth fields, and reconnect-aware shell state**

Add these expectations:

```python
# tests/test_import_layer_structure.py
self.assertIn("providerType", import_text)
self.assertIn("authType", import_text)
self.assertIn("sudoEnabled", import_text)
self.assertIn("privateKey", import_text)
```

```javascript
// frontend/src/stores/app.test.js
test('setImportContext keeps workspace ready during reconnecting runtime state', () => {
  setActivePinia(createPinia())
  const store = useAppStore()
  store.applyRealtimePayload({
    import_context: { valid: true, imported_gpu_indexes: [0], provider_type: 'ssh_linux' },
    connection: { status: 'reconnecting', connected: false, provider_type: 'ssh_linux' },
  })
  assert.equal(store.workspaceReady, true)
})
```

- [ ] **Step 2: Run the frontend structure and store tests to confirm the old import page is still Agent-only**

Run:

```bash
cmd.exe /c "cd /d E:\Code\AI-DataCenter && .\.venv\Scripts\python.exe -m unittest tests.test_import_layer_structure -v"
cmd.exe /c "cd /d E:\Code\AI-DataCenter\frontend && node --test src/lib/importContext.test.js src/stores/app.test.js"
```

Expected:

- FAIL because the import page still only exposes `local` / `remote` Agent fields.

- [ ] **Step 3: Implement provider-aware import UI, payload shaping, and reconnect-aware app-shell state**

Update the import UI model:

```vue
<!-- frontend/src/components/import/ImportSourcePanel.vue -->
const isSsh = computed(() => props.providerType === 'ssh_linux')
const isHttpRemote = computed(() => props.providerType === 'http_remote')
```

```vue
<button @click="emit('update:providerType', 'ssh_linux')">SSH Linux</button>
<label v-if="isSsh"><span>用户名</span><input :value="props.username" @input="emit('update:username', $event.target.value)"></label>
<label v-if="isSsh && props.authType === 'private_key'"><span>私钥</span><textarea :value="props.privateKey" @input="emit('update:privateKey', $event.target.value)" /></label>
<label v-if="isSsh"><input type="checkbox" :checked="props.sudoEnabled" @change="emit('update:sudoEnabled', $event.target.checked)"> 启用 sudo</label>
```

```javascript
// frontend/src/views/ImportWorkspace.vue
const providerType = ref('http_local')
const authType = ref('password')
const sshForm = reactive({ host: '', port: 22, username: '', password: '', privateKey: '', privateKeyPassphrase: '', sudoEnabled: false, sudoPassword: '' })
const buildProviderPayload = () => ({ provider_type: providerType.value, label: agentLabel.value, host: sshForm.host, port: sshForm.port, username: sshForm.username, auth_type: authType.value, sudo_enabled: sshForm.sudoEnabled, agent_url: agentUrl.value || null })
const buildCredentialPayload = () => ({ password: sshForm.password, private_key: sshForm.privateKey, private_key_passphrase: sshForm.privateKeyPassphrase, sudo_password: sshForm.sudoPassword })
const payloadBase = () => ({ provider: buildProviderPayload(), credentials: buildCredentialPayload() })
```

```javascript
// frontend/src/lib/importContext.js
export function formatImportSourceLabel(context) {
  if (!context?.provider_type) return '导入模式待识别'
  return context.provider_type === 'ssh_linux' ? 'SSH Linux 导入模式' : 'HTTP Agent 导入模式'
}
```

```javascript
// frontend/src/App.vue
if (store.importContext?.valid) {
  appInfo.value.connectionModeLabel = formatImportSourceLabel(store.importContext)
}
```

- [ ] **Step 4: Run the frontend tests and production build again**

Run:

```bash
cmd.exe /c "cd /d E:\Code\AI-DataCenter && .\.venv\Scripts\python.exe -m unittest tests.test_import_layer_structure tests.test_frontend_ui_structure -v"
cmd.exe /c "cd /d E:\Code\AI-DataCenter\frontend && node --test src/lib/importContext.test.js src/stores/app.test.js"
cmd.exe /c "cd /d E:\Code\AI-DataCenter\frontend && npm run build"
```

Expected:

- PASS for structure tests and store tests.
- `npm run build` succeeds, with only existing chunk-size warnings allowed.

- [ ] **Step 5: Commit the frontend SSH import slice**

```bash
git add frontend/src/views/ImportWorkspace.vue frontend/src/components/import/ImportSourcePanel.vue frontend/src/components/import/ImportHardwareSummary.vue frontend/src/services/api.js frontend/src/stores/app.js frontend/src/App.vue frontend/src/lib/importContext.js frontend/src/lib/importContext.test.js frontend/src/stores/app.test.js tests/test_import_layer_structure.py
git commit -m "feat: add ssh provider import workflow"
```

### Task 6: Run Full Regression For HTTP And SSH Paths

**Files:**
- Modify: `tests/test_ssh_import_flow.py`
- Modify: `tests/test_runtime_provider_manager.py`

- [ ] **Step 1: Add final cross-path regression cases for HTTP provider compatibility and SSH reconnect invalidation**

Add these final checks:

```python
async def test_http_import_path_still_returns_connected_snapshot(self):
    response = await scan_import_context(ImportScanRequest(
        provider={"provider_type": "http_remote", "label": "实验室 A", "agent_url": "http://10.0.0.8:8001"},
        credentials={},
    ))
    self.assertEqual(response["provider"]["provider_type"], "http_remote")

async def test_reconnect_limit_marks_import_context_invalid(self):
    state = await manager.mark_failure("timeout")
    self.assertEqual(state["status"], "invalid")
```

- [ ] **Step 2: Run the repository regression suite that covers the new runtime boundary**

Run:

```bash
cmd.exe /c "cd /d E:\Code\AI-DataCenter && .\.venv\Scripts\python.exe -m unittest tests.test_connection_settings tests.test_import_context tests.test_import_control_scope tests.test_import_history_scope tests.test_scheduler tests.test_energy_benchmark tests.test_performance_hotpaths tests.test_runtime_scope tests.test_import_layer_structure tests.test_frontend_ui_structure tests.test_runtime_provider_manager tests.test_credential_store tests.test_ssh_linux_provider tests.test_ssh_import_flow -v"
cmd.exe /c "cd /d E:\Code\AI-DataCenter\frontend && node --test src/lib/importContext.test.js src/stores/app.test.js"
cmd.exe /c "cd /d E:\Code\AI-DataCenter\frontend && npm run build"
```

Expected:

- PASS across backend structure/regression tests, frontend `node:test`, and frontend build.

- [ ] **Step 3: Commit the final compatibility and regression lock**

```bash
git add tests/test_ssh_import_flow.py tests/test_runtime_provider_manager.py
git commit -m "test: lock ssh and http runtime compatibility"
```
