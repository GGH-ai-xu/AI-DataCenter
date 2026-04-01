# Performance Hotpath Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce latency and resource waste in backend collection, SQLite hot paths, agent-side sampling, replay generation, and frontend high-frequency refresh/render paths without changing public API contracts.

**Architecture:** Keep current REST and WebSocket payloads stable, but optimize internal execution paths. Backend changes focus on concurrency, batch database operations, and lower-complexity replay computation; frontend changes focus on active-tab-only refresh and reducing repeated array/chart recomputation.

**Tech Stack:** FastAPI, asyncio, aiosqlite, httpx, psutil, Vue 3, Pinia, ECharts, Python unittest

## File Map

- `backend/app/main.py`: keep the collection loop orchestration thin and move concurrent snapshot collection into a named helper.
- `backend/app/services/data_store.py`: add batch-friendly persistence entry points and delegate replay/process helpers instead of expanding inline complexity.
- `backend/app/services/replay_frames.py`: hold replay bucket helpers so the database layer stays focused on querying.
- `backend/app/ws/realtime.py`: make WebSocket fan-out concurrent and prune dead sockets after send completion.
- `server-agent/collectors/system_monitor.py`: replace blocking CPU sampling with a non-blocking sampler helper.
- `server-agent/collectors/task_monitor.py`: add short-lived process snapshot caching and reuseable clone helpers.
- `server-agent/main.py`: route `/api/processes` and `/api/training/logs` through the cached process snapshot path.
- `frontend/src/views/MonitorCenter.vue`: refresh only the active tab and stop unconditional polling for heavyweight training data.
- `frontend/src/views/TaskManager.vue`: normalize process rows once and derive counts from a single summary pass.
- `frontend/src/components/charts/PowerTrendChart.vue`: update ECharts option incrementally on GPU prop changes instead of interval-based full rebuilds.
- `frontend/src/views/GpuDetail.vue`: precompute chart-ready arrays once per history refresh.
- `tests/test_performance_hotpaths.py`: backend behavior tests for concurrent reads, batch persistence, replay aggregation, and concurrent broadcast.
- `tests/test_agent_sampling_structure.py`: agent structure tests for non-blocking CPU sampling and cached process snapshots.
- `tests/test_frontend_performance_structure.py`: frontend structure tests for active-tab refresh and reduced repeated recomputation.

---

### Task 1: Lock backend hotpath expectations with failing tests

**Files:**
- Create: `tests/test_performance_hotpaths.py`
- Test: `tests/test_performance_hotpaths.py`

- [ ] **Step 1: Write the failing test**

```python
import asyncio
import os
import sys
import time
import unittest
from unittest import mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.services.data_store import DataStore  # noqa: E402
from app.ws.realtime import ConnectionManager  # noqa: E402
from app.main import collect_agent_snapshot  # noqa: E402


class CollectSnapshotTests(unittest.IsolatedAsyncioTestCase):
    async def test_collect_agent_snapshot_runs_agent_reads_concurrently(self):
        order = []

        class FakeAgent:
            async def get_all_gpus(self):
                order.append("gpus:start")
                await asyncio.sleep(0.05)
                order.append("gpus:end")
                return [{"index": 0}]

            async def get_system_info(self):
                order.append("system:start")
                await asyncio.sleep(0.05)
                order.append("system:end")
                return {"cpu_percent": 10}

            async def get_processes(self):
                order.append("proc:start")
                await asyncio.sleep(0.05)
                order.append("proc:end")
                return [{"pid": 1, "gpu_index": 0}]

        started = time.perf_counter()
        snapshot = await collect_agent_snapshot(FakeAgent())
        elapsed = time.perf_counter() - started

        self.assertEqual(snapshot["gpus"][0]["index"], 0)
        self.assertLess(elapsed, 0.12)
        self.assertIn("system:start", order)
        self.assertIn("proc:start", order)


class DataStoreBatchTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.store = DataStore(":memory:")
        await self.store.init()

    async def asyncTearDown(self):
        await self.store.close()

    async def test_save_alerts_batches_in_single_transaction(self):
        alerts = [
            {"gpu_index": 0, "alert_type": "temp", "severity": "warning", "message": "a", "value": 80, "threshold": 85, "timestamp": 1.0},
            {"gpu_index": 1, "alert_type": "temp", "severity": "critical", "message": "b", "value": 90, "threshold": 85, "timestamp": 2.0},
        ]
        await self.store.save_alerts(alerts)
        rows = await self.store.get_alerts(limit=10)
        self.assertEqual(len(rows), 2)

    async def test_replay_frames_counts_active_tasks_without_per_bucket_walk(self):
        now = 1_700_000_000
        await self.store._db.executemany(
            \"\"\"INSERT INTO process_history
               (pid, gpu_index, username, command, gpu_memory_used, first_seen, last_seen, is_active)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)\"\"\",
            [
                (101, 0, "alice", "python a.py", 100, now, now + 3600, 0),
                (202, 1, "bob", "python b.py", 100, now + 1800, now + 5400, 0),
            ],
        )
        await self.store._db.commit()

        with mock.patch("app.services.data_store.time.time", return_value=now + 7200):
            frames = await self.store.get_replay_frames(hours=2, bucket_minutes=30)

        counts = [frame["active_task_count"] for frame in frames]
        self.assertEqual(counts[:4], [1, 2, 2, 1])


class BroadcastTests(unittest.IsolatedAsyncioTestCase):
    async def test_broadcast_sends_to_connections_concurrently(self):
        manager = ConnectionManager()

        class FakeSocket:
            def __init__(self):
                self.messages = []

            async def send_text(self, message):
                await asyncio.sleep(0.05)
                self.messages.append(message)

        sockets = [FakeSocket(), FakeSocket(), FakeSocket()]
        manager._connections = set(sockets)

        started = time.perf_counter()
        await manager.broadcast({"type": "realtime", "gpus": []})
        elapsed = time.perf_counter() - started

        self.assertLess(elapsed, 0.12)
        self.assertTrue(all(socket.messages for socket in sockets))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -3 -m unittest tests.test_performance_hotpaths -v`
Expected: FAIL because `collect_agent_snapshot()` and `save_alerts()` do not exist, replay behavior is still on the old implementation, and broadcast is still serial.

- [ ] **Step 3: Write minimal implementation**

```python
async def collect_agent_snapshot(agent):
    gpus, system, processes = await asyncio.gather(
        agent.get_all_gpus(),
        agent.get_system_info(),
        agent.get_processes(),
    )
    return {"gpus": gpus, "system": system, "processes": processes}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -3 -m unittest tests.test_performance_hotpaths -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_performance_hotpaths.py backend/app/main.py backend/app/services/data_store.py backend/app/ws/realtime.py
git commit -m "test: lock backend performance hotpaths"
```

### Task 2: Optimize backend collection loop and batched writes

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/app/services/data_store.py`
- Modify: `backend/app/ws/realtime.py`
- Test: `tests/test_performance_hotpaths.py`

- [ ] **Step 1: Write the failing test**

```python
self.assertIn("asyncio.gather(", inspect.getsource(collect_agent_snapshot))
self.assertTrue(hasattr(DataStore, "save_alerts"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -3 -m unittest tests.test_performance_hotpaths -v`
Expected: FAIL on missing concurrent helper or batch methods.

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/main.py
async def collect_agent_snapshot(agent):
    gpus, system, processes = await asyncio.gather(
        agent.get_all_gpus(),
        agent.get_system_info(),
        agent.get_processes(),
    )
    return {"gpus": gpus, "system": system, "processes": processes}

# backend/app/services/data_store.py
async def save_alerts(self, alerts: list[dict]):
    if not self._db or not alerts:
        return
    rows = [
        (
            alert["gpu_index"], alert["alert_type"], alert["severity"],
            alert["message"], alert["value"], alert["threshold"], alert["timestamp"],
        )
        for alert in alerts
    ]
    await self._db.executemany(
        \"\"\"INSERT INTO alerts (gpu_index, alert_type, severity, message, value, threshold, timestamp)
           VALUES (?, ?, ?, ?, ?, ?, ?)\"\"\",
        rows,
    )
    await self._db.commit()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -3 -m unittest tests.test_performance_hotpaths -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/main.py backend/app/services/data_store.py backend/app/ws/realtime.py tests/test_performance_hotpaths.py
git commit -m "feat: optimize backend collection hotpath"
```

### Task 3: Remove N+1 process tracking and optimize replay frame generation

**Files:**
- Modify: `backend/app/services/data_store.py`
- Test: `tests/test_performance_hotpaths.py`

- [ ] **Step 1: Write the failing test**

```python
async def test_track_processes_reuses_single_active_snapshot(self):
    await self.store.track_processes([
        {"pid": 10, "gpu_index": 0, "username": "alice", "command": "python", "gpu_memory_used": 1},
        {"pid": 20, "gpu_index": 1, "username": "bob", "command": "python", "gpu_memory_used": 2},
    ])
    rows = await self.store.get_process_timeline(24)
    self.assertEqual({row["pid"] for row in rows}, {10, 20})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -3 -m unittest tests.test_performance_hotpaths -v`
Expected: FAIL because process tracking and replay logic have not been updated to the new batch/difference model.

- [ ] **Step 3: Write minimal implementation**

```python
cursor = await self._db.execute(
    "SELECT id, pid FROM process_history WHERE is_active = 1"
)
active_rows = {
    int(row["pid"]): int(row["id"])
    for row in await cursor.fetchall()
}
updates = []
inserts = []
current_pids = set()

for proc in normalized_processes:
    pid = int(proc["pid"])
    current_pids.add(pid)
    payload = (
        now,
        int(proc.get("gpu_index", -1)),
        proc.get("username", "unknown"),
        proc.get("command", ""),
        int(proc.get("gpu_memory_used", 0)),
    )
    if pid in active_rows:
        updates.append((*payload, active_rows[pid]))
        continue
    inserts.append(
        (
            pid,
            int(proc.get("gpu_index", -1)),
            proc.get("username", "unknown"),
            proc.get("command", ""),
            int(proc.get("gpu_memory_used", 0)),
            now,
            now,
        )
    )

await self._db.executemany(
    """UPDATE process_history
       SET last_seen = ?, gpu_index = ?, username = ?, command = ?, gpu_memory_used = ?
       WHERE id = ?""",
    updates,
)
await self._db.executemany(
    """INSERT INTO process_history
       (pid, gpu_index, username, command, gpu_memory_used, first_seen, last_seen, is_active)
       VALUES (?, ?, ?, ?, ?, ?, ?, 1)""",
    inserts,
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -3 -m unittest tests.test_performance_hotpaths -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/data_store.py tests/test_performance_hotpaths.py
git commit -m "feat: batch process tracking and replay aggregation"
```

### Task 4: Reduce agent-side blocking and repeated scans

**Files:**
- Modify: `server-agent/collectors/system_monitor.py`
- Modify: `server-agent/collectors/task_monitor.py`
- Modify: `server-agent/collectors/training_monitor.py`
- Modify: `server-agent/main.py`
- Create: `tests/test_agent_sampling_structure.py`
- Test: `tests/test_agent_sampling_structure.py`

- [ ] **Step 1: Write the failing test**

```python
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class AgentSamplingStructureTests(unittest.TestCase):
    def test_system_monitor_uses_non_blocking_cpu_sampling(self):
        text = (ROOT / "server-agent/collectors/system_monitor.py").read_text(encoding="utf-8")
        self.assertNotIn("cpu_percent(interval=0.1)", text)

    def test_task_monitor_defines_snapshot_cache(self):
        text = (ROOT / "server-agent/collectors/task_monitor.py").read_text(encoding="utf-8")
        self.assertIn("CACHE_TTL_SECONDS", text)
        self.assertIn("get_cached_gpu_processes", text)

    def test_training_monitor_uses_cached_processes(self):
        text = (ROOT / "server-agent/main.py").read_text(encoding="utf-8")
        self.assertIn("get_cached_gpu_processes", text)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -3 -m unittest tests.test_agent_sampling_structure -v`
Expected: FAIL because the cache and non-blocking sampling path do not yet exist.

- [ ] **Step 3: Write minimal implementation**

```python
CACHE_TTL_SECONDS = 2.0
_cache = {"expires_at": 0.0, "processes": []}

def get_cached_gpu_processes(device_count: int, simulate: bool = False) -> List[dict]:
    now = time.time()
    if now < _cache["expires_at"]:
        return [dict(item) for item in _cache["processes"]]
    processes = get_all_gpu_processes(device_count, simulate=simulate)
    _cache["processes"] = [dict(item) for item in processes]
    _cache["expires_at"] = now + CACHE_TTL_SECONDS
    return processes
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -3 -m unittest tests.test_agent_sampling_structure -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add server-agent/collectors/system_monitor.py server-agent/collectors/task_monitor.py server-agent/main.py tests/test_agent_sampling_structure.py
git commit -m "feat: cache agent process scans"
```

### Task 5: Lock frontend refresh and compute contracts with failing tests

**Files:**
- Create: `tests/test_frontend_performance_structure.py`
- Test: `tests/test_frontend_performance_structure.py`

- [ ] **Step 1: Write the failing test**

```python
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class FrontendPerformanceStructureTests(unittest.TestCase):
    def test_monitor_center_refreshes_only_active_tab(self):
        text = (ROOT / "frontend/src/views/MonitorCenter.vue").read_text(encoding="utf-8")
        self.assertIn("refreshActiveTab", text)
        self.assertNotIn("tasks.push(loadTraining())", text)
        self.assertNotIn("tasks.push(loadUsers())", text)
        self.assertNotIn("tasks.push(loadTimeline())", text)

    def test_power_trend_chart_no_longer_uses_interval_rebuild(self):
        text = (ROOT / "frontend/src/components/charts/PowerTrendChart.vue").read_text(encoding="utf-8")
        self.assertNotIn("setInterval(updateChart, 1000)", text)
        self.assertIn("watch(() => props.gpus", text)

    def test_gpu_detail_precomputes_chart_series(self):
        text = (ROOT / "frontend/src/views/GpuDetail.vue").read_text(encoding="utf-8")
        self.assertIn("processedHistory", text)

    def test_task_manager_uses_single_normalized_process_list(self):
        text = (ROOT / "frontend/src/views/TaskManager.vue").read_text(encoding="utf-8")
        self.assertIn("normalizedProcesses", text)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -3 -m unittest tests.test_frontend_performance_structure -v`
Expected: FAIL because refresh and compute code still use the old all-tab/full-rebuild paths.

- [ ] **Step 3: Write minimal implementation**

```javascript
// frontend/src/views/MonitorCenter.vue
const tabLoaders = {
  system: loadSystemDetail,
  training: loadTraining,
  users: loadUsers,
  timeline: loadTimeline,
}

async function refreshActiveTab() {
  loading.value = true
  try {
    await tabLoaders[activeTab.value]()
  } finally {
    loading.value = false
  }
}

watch(activeTab, () => {
  refreshActiveTab()
})

// frontend/src/components/charts/PowerTrendChart.vue
watch(
  () => props.gpus,
  (gpus) => {
    appendHistory(gpus)
    updateChartOption()
  },
  { deep: false, immediate: true },
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -3 -m unittest tests.test_frontend_performance_structure -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_frontend_performance_structure.py frontend/src/views/MonitorCenter.vue frontend/src/views/TaskManager.vue frontend/src/components/charts/PowerTrendChart.vue frontend/src/views/GpuDetail.vue
git commit -m "test: lock frontend performance structure"
```

### Task 6: Implement frontend active-tab refresh and reduced recomputation

**Files:**
- Modify: `frontend/src/views/MonitorCenter.vue`
- Modify: `frontend/src/views/TaskManager.vue`
- Modify: `frontend/src/components/charts/PowerTrendChart.vue`
- Modify: `frontend/src/views/GpuDetail.vue`
- Test: `tests/test_frontend_performance_structure.py`

- [ ] **Step 1: Write the failing test**

```python
self.assertIn("watch(activeTab", text)
self.assertIn("normalizedProcesses", task_text)
self.assertIn("processedHistory", detail_text)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -3 -m unittest tests.test_frontend_performance_structure -v`
Expected: FAIL until the new refresh/computation path is implemented.

- [ ] **Step 3: Write minimal implementation**

```javascript
const normalizedProcesses = computed(() =>
  sortProcesses(store.processes.map((proc) => ({
    ...proc,
    priority: proc.priority || 'normal',
    manageable: proc.manageable !== false,
    username: proc.username || 'unknown',
    gpu_memory_used: Number(proc.gpu_memory_used || 0),
    haystack: `${proc.pid} ${proc.name || ''} ${proc.username || ''} ${proc.command || ''}`.toLowerCase(),
  })))
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -3 -m unittest tests.test_frontend_performance_structure -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/MonitorCenter.vue frontend/src/views/TaskManager.vue frontend/src/components/charts/PowerTrendChart.vue frontend/src/views/GpuDetail.vue tests/test_frontend_performance_structure.py
git commit -m "feat: reduce frontend refresh and recompute costs"
```

### Task 7: Full verification

**Files:**
- Verify only

- [ ] **Step 1: Run backend and structure tests**

Run: `py -3 -m unittest tests.test_performance_hotpaths tests.test_agent_sampling_structure tests.test_frontend_performance_structure -v`
Expected: PASS

- [ ] **Step 2: Run repository regression suite**

Run: `py -3 -m unittest discover -s tests -p test_*.py`
Expected: PASS

- [ ] **Step 3: Run frontend production build**

Run: `cd frontend && npm run build`
Expected: exit code 0

- [ ] **Step 4: Run Electron main-process syntax check if desktop files changed transitively**

Run: `cd desktop-shell && node --check main.js`
Expected: exit code 0

- [ ] **Step 5: Commit**

```bash
git add .
git commit -m "test: verify performance hotpath optimization"
```
