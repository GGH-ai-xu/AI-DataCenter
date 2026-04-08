# SSH Partial GPU Availability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 SSH Linux 导入在单卡异常时仍能显示并导入可用 GPU，同时显式标注异常 GPU 的状态和错误原因。

**Architecture:** 将当前整机级 `nvidia-smi --query-gpu=...` 采集拆成“两阶段”流程：先枚举 GPU 基础身份，再对每张卡独立采集指标。后端返回统一 GPU 结构并新增可用性字段，导入扫描与前端选卡页据此区分“可用卡”和“异常卡”，异常卡保留展示但不可导入、不可治理。

**Tech Stack:** Python 3.10+/FastAPI/asyncssh/unittest，Vue 3/Vite/node:test

---

## File Structure

- Create: `backend/app/services/ssh_linux_gpu_collection.py`
  负责 GPU 基础身份枚举、单卡查询命令生成、可用卡/异常卡结果组装与汇总错误构建。
- Modify: `backend/app/services/ssh_linux_provider.py`
  接入新的按卡采集流程，保持 provider 对外接口不变，并缩减文件内聚度避免继续膨胀。
- Modify: `backend/app/services/ssh_linux_parsers.py`
  补充 GPU 身份解析与可用性结构组装辅助函数。
- Modify: `backend/app/services/runtime_provider_manager.py`
  让 probe 能接受“部分 GPU 可用”的 SSH 结果，并在全卡异常时保持显式失败。
- Modify: `backend/app/api/system_import.py`
  默认仅选择可用卡，提交时拒绝导入异常卡索引。
- Modify: `backend/app/models/schemas.py`
  给 GPU schema 增加 `available/status/error/pci_bus_id` 字段。
- Create: `tests/test_ssh_linux_provider_partial_gpu.py`
  覆盖“部分可用 / 全部异常 / 进程采集仍可用”的核心行为。
- Create: `tests/test_ssh_import_partial_gpu_flow.py`
  覆盖扫描默认选卡与提交拒绝异常卡的导入流程。
- Modify: `frontend/src/composables/createImportWorkspaceController.js`
  扫描成功后默认只选可用卡。
- Modify: `frontend/src/composables/createImportWorkspaceController.test.js`
  覆盖默认选卡行为。
- Create: `frontend/src/lib/importGpuAvailability.js`
  统一封装前端“是否可选”“可用卡索引列表”等判断，避免把逻辑散落在组件里。
- Modify: `frontend/src/components/import/ImportGpuGrid.vue`
  在选卡网格中禁用异常卡并展示错误摘要。
- Create: `frontend/src/components/import/ImportHardwareGpuCards.vue`
  拆出验机页 GPU 卡片展示，避免 `ImportHardwareStage.vue` 超过 300 行。
- Modify: `frontend/src/components/import/ImportHardwareStage.vue`
  接入新组件，展示异常卡状态与摘要统计。

### Task 1: Backend GPU Shape And Parser Foundations

**Files:**
- Modify: `backend/app/models/schemas.py`
- Modify: `backend/app/services/ssh_linux_parsers.py`
- Test: `tests/test_ssh_linux_provider_partial_gpu.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_parse_gpu_identity_rows_extracts_bus_id():
    raw = "0, GPU-aaa, RTX 4090, 00000000:17:00.0\n"
    parsed = parse_gpu_identity_rows(raw)
    assert parsed == [{
        "index": 0,
        "uuid": "GPU-aaa",
        "name": "RTX 4090",
        "pci_bus_id": "00000000:17:00.0",
    }]


def test_build_unavailable_gpu_row_preserves_identity_and_error():
    row = build_unavailable_gpu_row(
        {"index": 1, "uuid": "GPU-bbb", "name": "RTX 3090", "pci_bus_id": "00000000:65:00.0"},
        "Unable to determine the device handle",
        timestamp=10.0,
    )
    assert row["available"] is False
    assert row["status"] == "error"
    assert row["error"] == "Unable to determine the device handle"
    assert row["pci_bus_id"] == "00000000:65:00.0"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cmd.exe /c "cd /d E:\Code\AI-DataCenter && .venv\Scripts\python.exe -m unittest tests.test_ssh_linux_provider_partial_gpu -v"`

Expected: FAIL with missing parser/helper symbols.

- [ ] **Step 3: Write minimal implementation**

```python
def parse_gpu_identity_rows(raw: str) -> list[dict]:
    rows = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        index, uuid, name, pci_bus_id = _split_csv_row(line)
        rows.append({
            "index": _to_int(index),
            "uuid": uuid,
            "name": name,
            "pci_bus_id": pci_bus_id,
        })
    return rows


def build_unavailable_gpu_row(identity: dict, error: str, timestamp: float) -> dict:
    return {
        **identity,
        "temperature": 0,
        "power_usage": 0.0,
        "power_limit": 0.0,
        "gpu_utilization": 0,
        "memory_utilization": 0,
        "memory_used": 0,
        "memory_total": 0,
        "memory_free": 0,
        "fan_speed": 0,
        "clock_sm": 0,
        "clock_mem": 0,
        "available": False,
        "status": "error",
        "error": error,
        "timestamp": timestamp,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cmd.exe /c "cd /d E:\Code\AI-DataCenter && .venv\Scripts\python.exe -m unittest tests.test_ssh_linux_provider_partial_gpu -v"`

Expected: PASS for parser foundation tests.

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/schemas.py backend/app/services/ssh_linux_parsers.py tests/test_ssh_linux_provider_partial_gpu.py
git commit -m "feat: add ssh gpu availability schema"
```

### Task 2: Provider Per-GPU Collection And Partial Success

**Files:**
- Create: `backend/app/services/ssh_linux_gpu_collection.py`
- Modify: `backend/app/services/ssh_linux_provider.py`
- Test: `tests/test_ssh_linux_provider_partial_gpu.py`

- [ ] **Step 1: Write the failing tests**

```python
async def test_get_all_gpus_returns_available_and_unavailable_rows(self):
    provider.executor = FakeScriptedExecutor([
        (
            GPU_IDENTITY_QUERY,
            CommandResult(code=0, stdout="0, GPU-aaa, RTX 4090, 00000000:17:00.0\n1, GPU-bbb, RTX 4090, 00000000:65:00.0\n", stderr=""),
        ),
        (
            build_gpu_metrics_query(0),
            CommandResult(code=0, stdout="0, GPU-aaa, RTX 4090, 61, 280.5, 320.0, 87, 40, 8192, 24564, 16372, 35, 2100, 10500\n", stderr=""),
        ),
        (
            build_gpu_metrics_query(1),
            CommandResult(code=255, stdout="Unable to determine the device handle for GPU0000:65:00.0: Unknown Error\n", stderr=""),
        ),
    ])
    rows = await provider.get_all_gpus()
    assert [row["available"] for row in rows] == [True, False]
    assert rows[1]["error"].startswith("Unable to determine")


async def test_get_all_gpus_raises_when_all_gpus_are_unavailable(self):
    provider.executor = FakeScriptedExecutor([
        (
            GPU_IDENTITY_QUERY,
            CommandResult(code=0, stdout="0, GPU-aaa, RTX 4090, 00000000:17:00.0\n", stderr=""),
        ),
        (
            build_gpu_metrics_query(0),
            CommandResult(code=255, stdout="Unable to determine the device handle for GPU0000:17:00.0: Unknown Error\n", stderr=""),
        ),
    ])
    with self.assertRaisesRegex(RuntimeError, "GPU 0"):
        await provider.get_all_gpus()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cmd.exe /c "cd /d E:\Code\AI-DataCenter && .venv\Scripts\python.exe -m unittest tests.test_ssh_linux_provider_partial_gpu -v"`

Expected: FAIL because provider still uses whole-machine query semantics.

- [ ] **Step 3: Write minimal implementation**

```python
GPU_IDENTITY_QUERY = (
    "nvidia-smi --query-gpu=index,uuid,name,pci.bus_id "
    "--format=csv,noheader,nounits"
)


async def collect_gpu_rows(run_checked, logger, timestamp: float) -> list[dict]:
    identities = parse_gpu_identity_rows((await run_checked(GPU_IDENTITY_QUERY)).stdout)
    rows = []
    failures = []
    for identity in identities:
        command = build_gpu_metrics_query(identity["index"])
        result = await run_command(command)
        if result.code == 0:
            rows.extend(parse_gpu_metric_rows(result.stdout, timestamp, identity))
            continue
        error = _command_error_message(result, command)
        logger.warning(...)
        rows.append(build_unavailable_gpu_row(identity, error, timestamp))
        failures.append((identity["index"], error))
    if rows and any(row["available"] for row in rows):
        return rows
    raise RuntimeError(build_gpu_collection_error(failures))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cmd.exe /c "cd /d E:\Code\AI-DataCenter && .venv\Scripts\python.exe -m unittest tests.test_ssh_linux_provider_partial_gpu -v"`

Expected: PASS for partial-success provider behavior.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ssh_linux_gpu_collection.py backend/app/services/ssh_linux_provider.py tests/test_ssh_linux_provider_partial_gpu.py
git commit -m "feat: collect ssh gpu metrics per device"
```

### Task 3: Process Mapping And Import Probe Rules

**Files:**
- Modify: `backend/app/services/ssh_linux_provider.py`
- Modify: `backend/app/services/runtime_provider_manager.py`
- Modify: `backend/app/api/system_import.py`
- Create: `tests/test_ssh_import_partial_gpu_flow.py`
- Modify: `tests/test_runtime_provider_manager.py`

- [ ] **Step 1: Write the failing tests**

```python
async def test_get_processes_ignores_unavailable_gpu_in_uuid_map(self):
    provider.executor = FakeScriptedExecutor([
        (GPU_IDENTITY_QUERY, CommandResult(code=0, stdout="0, GPU-aaa, RTX 4090, 00000000:17:00.0\n1, GPU-bbb, RTX 4090, 00000000:65:00.0\n", stderr="")),
        (build_gpu_metrics_query(0), CommandResult(code=0, stdout="0, GPU-aaa, RTX 4090, 61, 280.5, 320.0, 87, 40, 8192, 24564, 16372, 35, 2100, 10500\n", stderr="")),
        (build_gpu_metrics_query(1), CommandResult(code=255, stdout="Unable to determine the device handle for GPU0000:65:00.0: Unknown Error\n", stderr="")),
        (GPU_PROCESS_QUERY, CommandResult(code=0, stdout="1234, GPU-aaa, 4096\n", stderr="")),
        (mock.ANY, CommandResult(code=0, stdout="1234 alice python 3600 12.5 python train.py\n", stderr="")),
    ])
    rows = await provider.get_processes()
    assert rows[0]["gpu_index"] == 0


async def test_commit_import_context_rejects_unavailable_gpu_indexes(self):
    runtime.probe_result["gpus"] = [
        {"index": 0, "name": "RTX 4090", "available": True},
        {"index": 1, "name": "RTX 4090", "available": False, "error": "Unknown Error"},
    ]
    with self.assertRaises(HTTPException) as raised:
        await commit_import_context(request_with_gpu_indexes([1]))
    assert "GPU 1 当前不可用" in str(raised.exception.detail)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cmd.exe /c "cd /d E:\Code\AI-DataCenter && .venv\Scripts\python.exe -m unittest tests.test_ssh_import_partial_gpu_flow tests.test_runtime_provider_manager -v"`

Expected: FAIL because import validation and process mapping still treat all GPUs as uniformly available.

- [ ] **Step 3: Write minimal implementation**

```python
async def get_processes(self) -> list[dict]:
    gpu_rows = await self.get_all_gpus()
    gpu_map = {
        item["uuid"]: int(item["index"])
        for item in gpu_rows
        if item.get("available", True)
    }
    compute_rows = parse_compute_process_rows(
        (await self._run_checked(GPU_PROCESS_QUERY)).stdout,
        gpu_map,
    )
    ...


def _available_gpu_indexes(gpus: list[dict]) -> set[int]:
    return {
        int(item.get("index", -1))
        for item in gpus
        if item.get("available", True)
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cmd.exe /c "cd /d E:\Code\AI-DataCenter && .venv\Scripts\python.exe -m unittest tests.test_ssh_import_partial_gpu_flow tests.test_runtime_provider_manager -v"`

Expected: PASS for import filtering and process mapping.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ssh_linux_provider.py backend/app/services/runtime_provider_manager.py backend/app/api/system_import.py tests/test_ssh_import_partial_gpu_flow.py tests/test_runtime_provider_manager.py
git commit -m "fix: allow ssh import with partial gpu availability"
```

### Task 4: Frontend Availability UX

**Files:**
- Create: `frontend/src/lib/importGpuAvailability.js`
- Modify: `frontend/src/composables/createImportWorkspaceController.js`
- Modify: `frontend/src/composables/createImportWorkspaceController.test.js`
- Modify: `frontend/src/components/import/ImportGpuGrid.vue`
- Create: `frontend/src/components/import/ImportHardwareGpuCards.vue`
- Modify: `frontend/src/components/import/ImportHardwareStage.vue`

- [ ] **Step 1: Write the failing tests**

```javascript
test('scan success selects only available gpu indexes by default', async () => {
  const controller = createImportWorkspaceController(...)
  await controller.handleSavedHostScan(1)
  assert.deepEqual(controller.selectedGpuIndexes.value, [0, 2])
})

test('select all excludes unavailable gpus in selection stage helper', () => {
  assert.deepEqual(selectableGpuIndexes([
    { index: 0, available: true },
    { index: 1, available: false },
  ]), [0])
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- createImportWorkspaceController.test.js`

Expected: FAIL because controller currently selects every returned GPU.

- [ ] **Step 3: Write minimal implementation**

```javascript
export function isImportableGpu(gpu) {
  return gpu?.available !== false
}

export function selectableGpuIndexes(gpus = []) {
  return gpus
    .filter(isImportableGpu)
    .map((gpu) => Number(gpu.index))
}

state.selectedGpuIndexes.value = data.success
  ? selectableGpuIndexes(data.gpus)
  : []
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- createImportWorkspaceController.test.js`

Expected: PASS, and UI components render unavailable cards as disabled with visible error text.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/importGpuAvailability.js frontend/src/composables/createImportWorkspaceController.js frontend/src/composables/createImportWorkspaceController.test.js frontend/src/components/import/ImportGpuGrid.vue frontend/src/components/import/ImportHardwareGpuCards.vue frontend/src/components/import/ImportHardwareStage.vue
git commit -m "feat: show unavailable ssh gpus in import flow"
```

### Task 5: Regression Verification

**Files:**
- Test: `tests/test_ssh_linux_provider.py`
- Test: `tests/test_ssh_linux_provider_command_errors.py`
- Test: `tests/test_ssh_linux_provider_partial_gpu.py`
- Test: `tests/test_ssh_import_partial_gpu_flow.py`
- Test: `tests/test_runtime_provider_manager.py`
- Test: `frontend/src/composables/createImportWorkspaceController.test.js`

- [ ] **Step 1: Run focused backend tests**

```bash
cmd.exe /c "cd /d E:\Code\AI-DataCenter && .venv\Scripts\python.exe -m unittest tests.test_ssh_linux_provider tests.test_ssh_linux_provider_command_errors tests.test_ssh_linux_provider_partial_gpu tests.test_ssh_import_partial_gpu_flow tests.test_runtime_provider_manager -v"
```

Expected: all backend tests PASS.

- [ ] **Step 2: Run focused frontend tests**

```bash
cd frontend && npm test -- createImportWorkspaceController.test.js
```

Expected: import controller tests PASS.

- [ ] **Step 3: Run structure/smoke checks for touched areas**

```bash
cmd.exe /c "cd /d E:\Code\AI-DataCenter && .venv\Scripts\python.exe -m compileall backend/app"
cd frontend && npm run build
```

Expected: compile/build PASS without new errors.

- [ ] **Step 4: Review spec coverage**

```text
- 单卡异常不再拖垮整机扫描 -> Task 2
- 异常卡显式状态与错误 -> Task 1 + Task 2 + Task 4
- 默认只选可用卡 -> Task 3 + Task 4
- 异常卡不可导入不可治理 -> Task 3 + Task 4
- 全卡异常仍显式失败 -> Task 2 + Task 3
```

- [ ] **Step 5: Commit**

```bash
git add backend/app frontend/src tests docs/superpowers/plans/2026-04-08-ssh-partial-gpu-availability.md
git commit -m "feat: support partial ssh gpu availability"
```
