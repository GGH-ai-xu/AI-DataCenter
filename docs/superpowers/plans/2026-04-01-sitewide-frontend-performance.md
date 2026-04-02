# Sitewide Frontend Performance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove duplicated realtime and polling work, then cut repeated list and chart recomputation so the Vue frontend stays responsive under live telemetry.

**Architecture:** Keep Pinia as the single data sink, move expensive derivations into small plain-JS helpers that can be tested with Node's built-in test runner, and make pages subscribe to shared domain state instead of recomputing raw arrays locally. Use one WebSocket gateway, one refresh coordinator, page-domain cache metadata, and visible-tab-only chart updates.

**Tech Stack:** Vue 3, Pinia, Vue Router, Axios, ECharts, Node test runner, Vite

---

## File Map

- Modify: `frontend/package.json`
- Create: `frontend/src/lib/realtimeSummaries.js`
- Create: `frontend/src/lib/realtimeSummaries.test.js`
- Create: `frontend/src/lib/domainRefresh.js`
- Create: `frontend/src/lib/domainRefresh.test.js`
- Create: `frontend/src/lib/historyTransforms.js`
- Create: `frontend/src/lib/historyTransforms.test.js`
- Create: `frontend/src/composables/useDomainRefresh.js`
- Create: `frontend/src/composables/useDashboardData.js`
- Create: `frontend/src/composables/useTaskManagerData.js`
- Create: `frontend/src/composables/useMonitorData.js`
- Create: `frontend/src/composables/useEnergyData.js`
- Create: `frontend/src/stores/app.test.js`
- Modify: `frontend/src/stores/app.js`
- Modify: `frontend/src/composables/useWebSocket.js`
- Modify: `frontend/src/App.vue`
- Modify: `frontend/src/views/Dashboard.vue`
- Modify: `frontend/src/views/Scheduler.vue`
- Modify: `frontend/src/views/TaskManager.vue`
- Modify: `frontend/src/views/MonitorCenter.vue`
- Modify: `frontend/src/views/EnergyOptimization.vue`
- Modify: `frontend/src/components/charts/PowerTrendChart.vue`
- Modify: `frontend/src/views/GpuDetail.vue`

### Task 1: Add Frontend Logic Test Coverage and Shared Realtime Summary Helpers

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/src/lib/realtimeSummaries.js`
- Create: `frontend/src/lib/realtimeSummaries.test.js`

- [ ] **Step 1: Write the failing summary/filter test file**

```js
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  buildDashboardSummary,
  normalizeProcesses,
  buildTaskSummary,
  filterProcesses,
} from './realtimeSummaries.js'

test('buildDashboardSummary counts priorities, users, hot gpus, and critical alerts', () => {
  const summary = buildDashboardSummary({
    gpus: [{ index: 0, temperature: 82 }, { index: 1, temperature: 61 }],
    processes: [
      { pid: 1, username: 'alice', priority: 'urgent' },
      { pid: 2, username: 'bob', priority: 'deferrable' },
      { pid: 3, username: 'alice' },
    ],
    alerts: [
      { id: 1, severity: 'critical' },
      { id: 2, severity: 'warning' },
      { id: 3, severity: 'critical' },
    ],
  })
  assert.equal(summary.activeUsers, 2)
  assert.equal(summary.urgentTasks, 1)
  assert.equal(summary.deferrableTasks, 1)
  assert.equal(summary.normalTasks, 1)
  assert.equal(summary.hotGpuCount, 1)
  assert.equal(summary.criticalAlerts.length, 2)
})

test('normalizeProcesses sorts manageable tasks first and adds haystack text', () => {
  const normalized = normalizeProcesses([
    { pid: 2, username: 'bob', manageable: false, gpu_memory_used: 1024, command: 'python b.py' },
    { pid: 1, username: 'alice', gpu_memory_used: 4096, command: 'python a.py' },
  ])
  assert.equal(normalized[0].pid, 1)
  assert.match(normalized[0].haystack, /alice/)
  assert.equal(normalized[1].manageable, false)
})

test('buildTaskSummary and filterProcesses share one normalized list', () => {
  const normalized = normalizeProcesses([
    { pid: 1, username: 'alice', priority: 'urgent', gpu_memory_used: 4096, command: 'train.py' },
    { pid: 2, username: 'bob', priority: 'deferrable', gpu_memory_used: 2048, command: 'idle.py' },
    { pid: 3, username: 'sys', manageable: false, gpu_memory_used: 0, command: 'dwm.exe' },
  ])
  const summary = buildTaskSummary(normalized)
  const filtered = filterProcesses(normalized, { keyword: 'train', priority: 'all', includeAll: false })
  assert.equal(summary.manageableCount, 2)
  assert.equal(summary.backgroundCount, 1)
  assert.equal(summary.userCount, 2)
  assert.equal(summary.totalGpuMemory, 6144)
  assert.deepEqual(filtered.map((proc) => proc.pid), [1])
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm --prefix frontend run test -- src/lib/realtimeSummaries.test.js`
Expected: FAIL with `Cannot find module .../realtimeSummaries.js` or a missing `test` script.

- [ ] **Step 3: Add the Node test script and implement the shared realtime helpers**

```json
{
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview",
    "test": "node --test"
  }
}
```

```js
const DEFAULT_PRIORITY = 'normal'

export function buildDashboardSummary({ gpus = [], processes = [], alerts = [] }) {
  const usernames = new Set()
  let urgentTasks = 0
  let deferrableTasks = 0
  let normalTasks = 0
  let hotGpuCount = 0

  for (const gpu of gpus) {
    if (Number(gpu.temperature || 0) >= 80) hotGpuCount += 1
  }

  for (const process of processes) {
    usernames.add(process.username || 'unknown')
    const priority = process.priority || DEFAULT_PRIORITY
    if (priority === 'urgent') urgentTasks += 1
    else if (priority === 'deferrable') deferrableTasks += 1
    else normalTasks += 1
  }

  return {
    activeUsers: usernames.size,
    urgentTasks,
    deferrableTasks,
    normalTasks,
    hotGpuCount,
    criticalAlerts: alerts.filter((alert) => alert.severity === 'critical').slice(0, 4),
  }
}

export function normalizeProcesses(processes = []) {
  return [...processes].map((proc) => {
    const username = proc.username || 'unknown'
    const manageable = proc.manageable !== false
    return {
      ...proc,
      username,
      manageable,
      priority: proc.priority || DEFAULT_PRIORITY,
      gpu_memory_used: Number(proc.gpu_memory_used || 0),
      haystack: `${proc.pid} ${proc.name || ''} ${username} ${proc.command || ''}`.toLowerCase(),
    }
  }).sort((a, b) => {
    const manageableDelta = Number(b.manageable) - Number(a.manageable)
    if (manageableDelta) return manageableDelta
    return b.gpu_memory_used - a.gpu_memory_used
  })
}

export function buildTaskSummary(processes = []) {
  const usernames = new Set()
  const summary = { manageableCount: 0, backgroundCount: 0, userCount: 0, urgentCount: 0, deferrableCount: 0, totalGpuMemory: 0 }
  for (const proc of processes) {
    if (!proc.manageable) {
      summary.backgroundCount += 1
      continue
    }
    summary.manageableCount += 1
    usernames.add(proc.username)
    summary.totalGpuMemory += proc.gpu_memory_used
    if (proc.priority === 'urgent') summary.urgentCount += 1
    if (proc.priority === 'deferrable') summary.deferrableCount += 1
  }
  summary.userCount = usernames.size
  return summary
}

export function filterProcesses(processes = [], options = {}) {
  const { keyword = '', priority = 'all', includeAll = false } = options
  const term = keyword.trim().toLowerCase()
  const visible = includeAll ? processes : processes.filter((proc) => proc.manageable)
  return visible.filter((proc) => (priority === 'all' || proc.priority === priority) && (!term || proc.haystack.includes(term)))
}
```

- [ ] **Step 4: Run the shared helper tests**

Run: `npm --prefix frontend run test -- src/lib/realtimeSummaries.test.js`
Expected: PASS with 3 passing tests.

- [ ] **Step 5: Commit the helper layer**

```bash
git add frontend/package.json frontend/src/lib/realtimeSummaries.js frontend/src/lib/realtimeSummaries.test.js
git commit -m "test: add frontend realtime summary coverage"
```

### Task 2: Add a Shared Refresh Coordinator and Domain Refresh Composable

**Files:**
- Create: `frontend/src/lib/domainRefresh.js`
- Create: `frontend/src/lib/domainRefresh.test.js`
- Create: `frontend/src/composables/useDomainRefresh.js`

- [ ] **Step 1: Write the failing refresh coordinator tests**

```js
import test from 'node:test'
import assert from 'node:assert/strict'
import { createDomainRefreshCoordinator } from './domainRefresh.js'

test('deduplicates concurrent requests by key', async () => {
  let calls = 0
  const coordinator = createDomainRefreshCoordinator()
  const loader = async () => ({ calls: ++calls })
  const [first, second] = await Promise.all([
    coordinator.run('dashboard:governance', loader, { staleTime: 0 }),
    coordinator.run('dashboard:governance', loader, { staleTime: 0 }),
  ])
  assert.equal(calls, 1)
  assert.deepEqual(first, second)
})

test('reuses fresh cached data before stale time expires', async () => {
  let now = 1000
  const coordinator = createDomainRefreshCoordinator({ now: () => now })
  let calls = 0
  await coordinator.run('monitor:system', async () => ({ calls: ++calls }), { staleTime: 5000 })
  now = 2000
  const cached = await coordinator.run('monitor:system', async () => ({ calls: ++calls }), { staleTime: 5000 })
  assert.equal(calls, 1)
  assert.equal(cached.fromCache, true)
})

test('skips hidden refreshes unless forced', async () => {
  const coordinator = createDomainRefreshCoordinator({ isVisible: () => false })
  const skipped = await coordinator.run('energy:overview', async () => ({ ok: true }), { staleTime: 0 })
  assert.equal(skipped.skipped, 'hidden')
  const forced = await coordinator.run('energy:overview', async () => ({ ok: true }), { force: true, staleTime: 0 })
  assert.equal(forced.data.ok, true)
})
```

- [ ] **Step 2: Run the coordinator tests to verify they fail**

Run: `npm --prefix frontend run test -- src/lib/domainRefresh.test.js`
Expected: FAIL with `Cannot find module .../domainRefresh.js`.

- [ ] **Step 3: Implement the shared coordinator and Vue wrapper**

```js
export function createDomainRefreshCoordinator(options = {}) {
  const now = options.now || (() => Date.now())
  const isVisible = options.isVisible || (() => typeof document === 'undefined' || !document.hidden)
  const cache = new Map()
  const inFlight = new Map()

  function snapshot(key) {
    return cache.get(key) || { data: null, error: null, lastUpdatedAt: 0 }
  }

  async function run(key, loader, policy = {}) {
    const { force = false, staleTime = 0 } = policy
    const current = snapshot(key)
    if (!force && !isVisible()) return { ...current, skipped: 'hidden' }
    if (!force && current.lastUpdatedAt > 0 && now() - current.lastUpdatedAt < staleTime) {
      return { ...current, fromCache: true }
    }
    if (inFlight.has(key)) return inFlight.get(key)
    const request = Promise.resolve(loader()).then((data) => {
      const next = { data, error: null, lastUpdatedAt: now() }
      cache.set(key, next)
      return next
    }).finally(() => {
      inFlight.delete(key)
    })
    inFlight.set(key, request)
    return request
  }

  return { run, snapshot, invalidate: (key) => cache.delete(key) }
}
```

```js
import { onMounted, onUnmounted } from 'vue'
import { useAppStore } from '../stores/app'
import { createDomainRefreshCoordinator } from '../lib/domainRefresh'

const coordinator = createDomainRefreshCoordinator()

export function useDomainRefresh(options) {
  const { section, key = null, intervalMs = 0, staleTime = 0, enabled = () => true, loader, applyData } = options
  const store = useAppStore()
  let timer = null

  function currentKey() {
    return typeof key === 'function' ? key() : key
  }

  async function refresh(policy = {}) {
    if (!enabled()) return null
    const domainKey = currentKey()
    const refreshKey = domainKey ? `${section}:${domainKey}` : section
    store.beginDomainRequest(section, domainKey)
    try {
      const result = await coordinator.run(refreshKey, loader, { force: policy.force === true, staleTime })
      if (result.data !== null) applyData?.(result.data)
      store.completeDomainRequest(section, domainKey, result.data, result.lastUpdatedAt)
      return result
    } catch (error) {
      store.failDomainRequest(section, domainKey, error)
      throw error
    }
  }

  onMounted(() => {
    void refresh()
    if (intervalMs > 0) timer = setInterval(() => { void refresh() }, intervalMs)
  })
  onUnmounted(() => {
    if (timer) clearInterval(timer)
  })

  return { refresh }
}
```

- [ ] **Step 4: Run the coordinator tests**

Run: `npm --prefix frontend run test -- src/lib/domainRefresh.test.js`
Expected: PASS with 3 passing tests.

- [ ] **Step 5: Commit the refresh foundation**

```bash
git add frontend/src/lib/domainRefresh.js frontend/src/lib/domainRefresh.test.js frontend/src/composables/useDomainRefresh.js
git commit -m "feat: add shared frontend refresh coordinator"
```

### Task 3: Unify the WebSocket Path and Expand Pinia Domain State

**Files:**
- Create: `frontend/src/stores/app.test.js`
- Modify: `frontend/src/stores/app.js`
- Modify: `frontend/src/composables/useWebSocket.js`
- Modify: `frontend/src/App.vue`

- [ ] **Step 1: Write the failing store integration test**

```js
import test from 'node:test'
import assert from 'node:assert/strict'
import { createPinia, setActivePinia } from 'pinia'
import { useAppStore } from './app.js'

test('applyRealtimePayload updates raw data, summaries, and capped alerts', () => {
  setActivePinia(createPinia())
  const store = useAppStore()
  store.applyRealtimePayload({
    gpus: [{ index: 0, temperature: 83, power_usage: 200 }],
    processes: [{ pid: 1, username: 'alice', priority: 'urgent', gpu_memory_used: 4096 }],
    alerts: Array.from({ length: 120 }, (_, index) => ({ id: index + 1, severity: 'critical' })),
  })
  assert.equal(store.gpus.length, 1)
  assert.equal(store.normalizedProcesses.length, 1)
  assert.equal(store.dashboardSummary.hotGpuCount, 1)
  assert.equal(store.alerts.length, 100)
})
```

- [ ] **Step 2: Run the store test to verify it fails**

Run: `npm --prefix frontend run test -- src/stores/app.test.js`
Expected: FAIL because `applyRealtimePayload` and the new derived state do not exist yet.

- [ ] **Step 3: Expand the Pinia store with domain metadata and shared summaries**

```js
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { buildDashboardSummary, buildTaskSummary, normalizeProcesses } from '../lib/realtimeSummaries'

const requestState = () => ({ loading: false, error: null, lastUpdatedAt: 0, inFlight: false, data: null })

export const useAppStore = defineStore('app', () => {
  const gpus = ref([])
  const system = ref(null)
  const processes = ref([])
  const alerts = ref([])
  const wsConnected = ref(false)
  const workspaceReady = ref(false)
  const dataSourceStatus = ref({ connected: false, simulated: false, gpu_count: 0 })
  const domains = ref({
    dashboard: { governance: requestState(), connection: requestState(), desktop: requestState() },
    scheduler: { status: requestState(), carbon: requestState(), audit: requestState(), evaluation: requestState() },
    tasks: { governance: requestState() },
    monitor: { system: requestState(), training: requestState(), users: requestState(), timeline: requestState() },
    energy: { overview: requestState(), prediction: requestState(), ai: requestState() },
  })

  const normalizedProcesses = computed(() => normalizeProcesses(processes.value))
  const dashboardSummary = computed(() => buildDashboardSummary({ gpus: gpus.value, processes: normalizedProcesses.value, alerts: alerts.value }))
  const taskSummary = computed(() => buildTaskSummary(normalizedProcesses.value))
  const totalPower = computed(() => gpus.value.reduce((sum, gpu) => sum + Number(gpu.power_usage || 0), 0))
  const avgTemperature = computed(() => gpus.value.length ? Math.round(gpus.value.reduce((sum, gpu) => sum + Number(gpu.temperature || 0), 0) / gpus.value.length) : 0)
  const totalMemoryUsed = computed(() => gpus.value.reduce((sum, gpu) => sum + Number(gpu.memory_used || 0), 0))
  const totalMemoryTotal = computed(() => gpus.value.reduce((sum, gpu) => sum + Number(gpu.memory_total || 0), 0))
  const avgUtilization = computed(() => gpus.value.length ? Math.round(gpus.value.reduce((sum, gpu) => sum + Number(gpu.gpu_utilization || 0), 0) / gpus.value.length) : 0)
  const dataSourceLabel = computed(() => {
    if (!dataSourceStatus.value.connected) return { text: '数据源离线', level: 'offline', color: '#999' }
    if (dataSourceStatus.value.simulated) return { text: '模拟演示', level: 'simulated', color: '#B8860B' }
    return { text: '真实采集', level: 'real', color: '#2E8B57' }
  })

  function domainEntry(section, key) {
    return key ? domains.value[section][key] : domains.value[section]
  }
  function beginDomainRequest(section, key = null) {
    Object.assign(domainEntry(section, key), { loading: true, error: null, inFlight: true })
  }
  function completeDomainRequest(section, key = null, data = null, lastUpdatedAt = Date.now()) {
    Object.assign(domainEntry(section, key), { loading: false, error: null, inFlight: false, lastUpdatedAt, data })
  }
  function failDomainRequest(section, key = null, error) {
    Object.assign(domainEntry(section, key), { loading: false, error: error instanceof Error ? error.message : String(error), inFlight: false })
  }
  function replaceProcesses(nextProcesses) {
    processes.value = nextProcesses || []
  }
  function setWorkspaceReady(value) {
    workspaceReady.value = Boolean(value)
  }
  function applyRealtimePayload(data) {
    if (data.gpus) gpus.value = data.gpus
    if (data.system) system.value = data.system
    if (data.processes) processes.value = data.processes
    if (data.alerts?.length) alerts.value = [...data.alerts, ...alerts.value].slice(0, 100)
    dataSourceStatus.value = {
      connected: true,
      simulated: Boolean(data.agent_info?.simulated),
      gpu_count: data.gpus?.length || dataSourceStatus.value.gpu_count,
    }
  }

  return { gpus, system, processes, alerts, wsConnected, workspaceReady, dataSourceStatus, dataSourceLabel, domains, normalizedProcesses, dashboardSummary, taskSummary, totalPower, avgTemperature, totalMemoryUsed, totalMemoryTotal, avgUtilization, beginDomainRequest, completeDomainRequest, failDomainRequest, replaceProcesses, setWorkspaceReady, applyRealtimePayload }
})
```

- [ ] **Step 4: Replace the duplicate App-level WebSocket implementation with a thin gateway**

```js
export function useWebSocket(options = {}) {
  const { onRealtimeMessage, onConnectionChange } = options
  const connected = ref(false)
  let socket = null
  let retryTimer = null
  let retryDelay = 1000

  function clearRetry() {
    if (retryTimer) clearTimeout(retryTimer)
    retryTimer = null
  }

  function connect() {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    socket = new WebSocket(`${protocol}//${location.host}/ws`)
    socket.onopen = () => {
      connected.value = true
      retryDelay = 1000
      onConnectionChange?.(true)
    }
    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.type === 'realtime') onRealtimeMessage?.(data)
      } catch {}
    }
    socket.onclose = () => {
      connected.value = false
      onConnectionChange?.(false)
      clearRetry()
      retryTimer = setTimeout(connect, retryDelay)
      retryDelay = Math.min(retryDelay * 2, 30000)
    }
    socket.onerror = () => socket?.close()
  }

  function disconnect() {
    clearRetry()
    socket?.close()
    socket = null
  }

  onUnmounted(disconnect)
  return { connected, connect, disconnect }
}
```

```js
const { connected: wsConnected, connect, disconnect } = useWebSocket({
  onRealtimeMessage: (payload) => store.applyRealtimePayload(payload),
  onConnectionChange: (connected) => {
    store.wsConnected = connected
  },
})

onMounted(() => {
  updateClock()
  clockTimer = setInterval(updateClock, 1000)
  connect()
  setupInterceptor((msg, type) => toastRef.value?.show(msg, type))
  void refreshWorkspaceStatus()
  workspaceTimer = setInterval(() => { void refreshWorkspaceStatus() }, 15000)
  void loadDesktopInfo()
})

onUnmounted(() => {
  clearInterval(clockTimer)
  clearInterval(workspaceTimer)
  disconnect()
})
```

- [ ] **Step 5: Run the store tests**

Run: `npm --prefix frontend run test -- src/stores/app.test.js`
Expected: PASS with the new store integration test.

- [ ] **Step 6: Commit the unified realtime data path**

```bash
git add frontend/src/stores/app.js frontend/src/stores/app.test.js frontend/src/composables/useWebSocket.js frontend/src/App.vue
git commit -m "refactor: unify frontend realtime data flow"
```

### Task 4: Move Dashboard and Scheduler Refresh Logic to Shared Domain Loaders

**Files:**
- Create: `frontend/src/composables/useDashboardData.js`
- Modify: `frontend/src/views/Dashboard.vue`
- Modify: `frontend/src/views/Scheduler.vue`

- [ ] **Step 1: Create a dashboard data composable that owns the three independent loaders**

```js
import { computed } from 'vue'
import { getConnectionConfig, getFairnessGovernance, getSchedulerStatus, getSystemSelfCheck, healthCheck } from '../services/api'
import { useAppStore } from '../stores/app'
import { useDomainRefresh } from './useDomainRefresh'

export function useDashboardData() {
  const store = useAppStore()

  const governance = useDomainRefresh({
    section: 'dashboard',
    key: 'governance',
    intervalMs: 8000,
    staleTime: 4000,
    loader: async () => {
      const [{ data: schedulerData }, { data: healthData }, { data: fairnessData }, { data: selfCheckData }] = await Promise.all([
        getSchedulerStatus(),
        healthCheck(),
        getFairnessGovernance(),
        getSystemSelfCheck(),
      ])
      return { scheduler: schedulerData, health: healthData, fairness: fairnessData, selfCheck: selfCheckData }
    },
  })

  const connection = useDomainRefresh({
    section: 'dashboard',
    key: 'connection',
    staleTime: 15000,
    loader: async () => (await getConnectionConfig()).data,
  })

  return {
    dashboardSummary: computed(() => store.dashboardSummary),
    taskSummary: computed(() => store.taskSummary),
    governanceState: computed(() => store.domains.dashboard.governance),
    connectionState: computed(() => store.domains.dashboard.connection),
    refreshGovernance: governance.refresh,
    refreshConnection: connection.refresh,
  }
}
```

- [ ] **Step 2: Rewire `Dashboard.vue` to consume store summaries instead of scanning raw arrays**

```js
import { useDashboardData } from '../composables/useDashboardData'

const {
  dashboardSummary,
  governanceState,
  connectionState,
  refreshGovernance,
  refreshConnection,
} = useDashboardData()

const activeUsers = computed(() => dashboardSummary.value.activeUsers)
const urgentTasks = computed(() => dashboardSummary.value.urgentTasks)
const deferrableTasks = computed(() => dashboardSummary.value.deferrableTasks)
const normalTasks = computed(() => dashboardSummary.value.normalTasks)
const criticalAlerts = computed(() => dashboardSummary.value.criticalAlerts)
const hotGpuCount = computed(() => dashboardSummary.value.hotGpuCount)

watch(activeTab, () => {
  if (activeTab.value === 'access') void refreshConnection()
  else void refreshGovernance()
}, { immediate: true })
```

- [ ] **Step 3: Rewire `Scheduler.vue` to reuse the scheduler domain cache instead of its own timer**

```js
import { useDomainRefresh } from '../composables/useDomainRefresh'

const schedulerRefresh = useDomainRefresh({
  section: 'scheduler',
  key: 'status',
  intervalMs: 15000,
  staleTime: 10000,
  loader: async () => ({
    status: (await getSchedulerStatus()).data,
    carbon: (await getCarbonBudget()).data,
  }),
})

onMounted(() => {
  void schedulerRefresh.refresh({ force: true })
  void loadAuditLogs()
  void loadEvaluation()
})
```

- [ ] **Step 4: Run the existing unit tests plus a frontend build**

Run: `npm --prefix frontend run test`
Expected: PASS for the helper and store test files.

Run: `npm --prefix frontend run build`
Expected: Vite build completes successfully with no compile errors.

- [ ] **Step 5: Commit the dashboard/scheduler refactor**

```bash
git add frontend/src/composables/useDashboardData.js frontend/src/views/Dashboard.vue frontend/src/views/Scheduler.vue
git commit -m "refactor: slim dashboard and scheduler refresh paths"
```

### Task 5: Refactor TaskManager to Use Shared Normalized State and Debounced Filtering

**Files:**
- Create: `frontend/src/composables/useTaskManagerData.js`
- Modify: `frontend/src/views/TaskManager.vue`

- [ ] **Step 1: Create the task-manager composable around the tested helpers**

```js
import { computed, onUnmounted, ref, watch } from 'vue'
import { getFairnessGovernance, getTasks } from '../services/api'
import { filterProcesses } from '../lib/realtimeSummaries'
import { useDomainRefresh } from './useDomainRefresh'
import { useAppStore } from '../stores/app'

export function useTaskManagerData(keyword, selectedPriority, showAllProcesses) {
  const store = useAppStore()
  const debouncedKeyword = ref('')
  let keywordTimer = null

  watch(keyword, (value) => {
    if (keywordTimer) clearTimeout(keywordTimer)
    keywordTimer = setTimeout(() => {
      debouncedKeyword.value = value
    }, 160)
  }, { immediate: true })

  onUnmounted(() => {
    if (keywordTimer) clearTimeout(keywordTimer)
  })

  const refresh = useDomainRefresh({
    section: 'tasks',
    key: 'governance',
    intervalMs: 30000,
    staleTime: 10000,
    loader: async () => {
      const [{ data: taskData }, { data: fairnessData }] = await Promise.all([getTasks(), getFairnessGovernance()])
      return { processes: taskData.processes || [], fairness: fairnessData }
    },
    applyData: (payload) => {
      store.replaceProcesses(payload.processes)
    },
  })

  const filteredProcesses = computed(() => filterProcesses(store.normalizedProcesses, {
    keyword: debouncedKeyword.value,
    priority: selectedPriority.value,
    includeAll: showAllProcesses.value,
  }))

  return {
    filteredProcesses,
    taskSummary: computed(() => store.taskSummary),
    fairnessState: computed(() => store.domains.tasks.governance.data?.fairness || null),
    refreshTaskGovernance: refresh.refresh,
  }
}
```

- [ ] **Step 2: Update `TaskManager.vue` to remove repeated process scans**

```js
import { useTaskManagerData } from '../composables/useTaskManagerData'

const {
  filteredProcesses,
  taskSummary,
  fairnessState,
  refreshTaskGovernance,
} = useTaskManagerData(keyword, selectedPriority, showAllProcesses)

const manageableProcessCount = computed(() => taskSummary.value.manageableCount)
const backgroundProcessCount = computed(() => taskSummary.value.backgroundCount)
const userCount = computed(() => taskSummary.value.userCount)
const urgentCount = computed(() => taskSummary.value.urgentCount)
const deferrableCount = computed(() => taskSummary.value.deferrableCount)
const totalGpuMemory = computed(() => taskSummary.value.totalGpuMemory)

onMounted(() => {
  void refreshTaskGovernance({ force: true })
})
```

- [ ] **Step 3: Verify the task page still builds cleanly**

Run: `npm --prefix frontend run test`
Expected: PASS for existing tests.

Run: `npm --prefix frontend run build`
Expected: PASS with `TaskManager.vue` consuming the shared composable.

- [ ] **Step 4: Commit the Task Manager refactor**

```bash
git add frontend/src/composables/useTaskManagerData.js frontend/src/views/TaskManager.vue
git commit -m "refactor: slim task manager derived state"
```

### Task 6: Cache Monitor and Energy Tabs and Update Charts Only for Visible Tabs

**Files:**
- Create: `frontend/src/composables/useMonitorData.js`
- Create: `frontend/src/composables/useEnergyData.js`
- Modify: `frontend/src/views/MonitorCenter.vue`
- Modify: `frontend/src/views/EnergyOptimization.vue`

- [ ] **Step 1: Add page composables that fetch only the active tab payload**

```js
export function useMonitorData(activeTab, timelineHours) {
  const loaders = {
    system: async () => (await getSystemDetail()).data,
    training: async () => (await getTrainingProgress()).data.training || [],
    users: async () => (await getUserStats()).data.users || [],
    timeline: async () => (await getTaskHistory(timelineHours.value)).data.timeline || [],
  }

  return useDomainRefresh({
    section: 'monitor',
    key: () => activeTab.value,
    intervalMs: 10000,
    staleTime: 10000,
    enabled: () => Boolean(activeTab.value),
    loader: () => loaders[activeTab.value](),
  })
}
```

```js
export function useEnergyData(activeTab) {
  const overviewLoader = async () => ({
    metrics: (await getEnergyMetrics(24)).data,
    breakdown: (await getTimeBreakdown(24)).data,
    efficiency: (await getGpuEfficiency()).data,
    scheduler: (await getSchedulerStatus()).data,
  })
  const predictionLoader = async () => ({
    prediction: (await getPowerPrediction(24)).data,
    scheduleHistory: (await getScheduleHistory(72)).data,
    historyComparison: (await getHistoryComparison(72)).data,
  })
  const aiLoader = async () => ({
    insight: (await getAiInsight()).data,
    anomalies: (await getAiAnomalies()).data,
  })

  const loaderMap = { overview: overviewLoader, prediction: predictionLoader, ai: aiLoader }

  return useDomainRefresh({
    section: 'energy',
    key: () => activeTab.value,
    intervalMs: 30000,
    staleTime: 15000,
    enabled: () => Boolean(activeTab.value),
    loader: () => loaderMap[activeTab.value](),
  })
}
```

- [ ] **Step 2: Update `MonitorCenter.vue` so only the active tab mounts and refreshes heavy charts**

```js
import { computed, watch } from 'vue'
import { useMonitorData } from '../composables/useMonitorData'
import { useAppStore } from '../stores/app'

const store = useAppStore()
const monitorRefresh = useMonitorData(activeTab, timelineHours)

watch(activeTab, () => {
  void monitorRefresh.refresh({ force: true })
}, { immediate: true })

const systemDetail = computed(() => store.domains.monitor.system.data)
const trainingData = computed(() => store.domains.monitor.training.data || [])
const userStats = computed(() => store.domains.monitor.users.data || [])
const taskTimeline = computed(() => store.domains.monitor.timeline.data || [])
const showSystemCharts = computed(() => activeTab.value === 'system')
const showTrainingCharts = computed(() => activeTab.value === 'training')
const showTimeline = computed(() => activeTab.value === 'timeline')
```

- [ ] **Step 3: Update `EnergyOptimization.vue` so each tab owns only its own data and chart work**

```js
import { watch } from 'vue'
import { useEnergyData } from '../composables/useEnergyData'
import { useAppStore } from '../stores/app'

const store = useAppStore()
const energyRefresh = useEnergyData(activeTab)

watch(activeTab, () => {
  void energyRefresh.refresh({ force: true })
}, { immediate: true })

watch(() => store.domains.energy.overview.data, async (payload) => {
  if (!payload || activeTab.value !== 'overview') return
  metrics.value = payload.metrics
  breakdown.value = payload.breakdown
  efficiency.value = payload.efficiency
  schedulerState.value = payload.scheduler
  await nextTick()
  renderGauge()
  renderPie()
  renderTrend()
  renderEff()
})
```

- [ ] **Step 4: Run the test suite and a production build**

Run: `npm --prefix frontend run test`
Expected: PASS.

Run: `npm --prefix frontend run build`
Expected: PASS with no new Vite warnings from the monitor/energy pages.

- [ ] **Step 5: Commit the tab-cache refactor**

```bash
git add frontend/src/composables/useMonitorData.js frontend/src/composables/useEnergyData.js frontend/src/views/MonitorCenter.vue frontend/src/views/EnergyOptimization.vue
git commit -m "refactor: cache monitor and energy tab refreshes"
```

### Task 7: Extract Chart Transform Helpers, Stop Full Rebuilds, and Run Final Verification

**Files:**
- Create: `frontend/src/lib/historyTransforms.js`
- Create: `frontend/src/lib/historyTransforms.test.js`
- Modify: `frontend/src/components/charts/PowerTrendChart.vue`
- Modify: `frontend/src/views/GpuDetail.vue`

- [ ] **Step 1: Write the failing chart-transform tests**

```js
import test from 'node:test'
import assert from 'node:assert/strict'
import { appendGpuHistorySample, buildGpuDetailSeries } from './historyTransforms.js'

test('appendGpuHistorySample keeps only the latest points per gpu', () => {
  const history = appendGpuHistorySample({}, [{ index: 0, power_usage: 100 }], new Date('2026-04-01T00:00:00Z'), 2)
  const next = appendGpuHistorySample(history, [{ index: 0, power_usage: 110 }], new Date('2026-04-01T00:01:00Z'), 2)
  const last = appendGpuHistorySample(next, [{ index: 0, power_usage: 120 }], new Date('2026-04-01T00:02:00Z'), 2)
  assert.deepEqual(last[0].map((point) => point.value), [110, 120])
})

test('buildGpuDetailSeries walks the history array once', () => {
  const series = buildGpuDetailSeries([{ timestamp: 1, temperature: 70, power_usage: 200, gpu_utilization: 80, memory_utilization: 60 }])
  assert.equal(series.times.length, 1)
  assert.equal(series.temperatures[0], 70)
  assert.equal(series.powerUsage[0], 200)
})
```

- [ ] **Step 2: Run the chart-transform tests to verify they fail**

Run: `npm --prefix frontend run test -- src/lib/historyTransforms.test.js`
Expected: FAIL with `Cannot find module .../historyTransforms.js`.

- [ ] **Step 3: Implement the chart helpers and replace repeated array walks**

```js
export function appendGpuHistorySample(history = {}, gpus = [], timestamp = new Date(), maxPoints = 60) {
  const next = { ...history }
  for (const gpu of gpus) {
    const current = [...(next[gpu.index] || []), { time: timestamp, value: gpu.power_usage }]
    next[gpu.index] = current.slice(-maxPoints)
  }
  return next
}

export function buildGpuDetailSeries(history = []) {
  const next = { times: [], temperatures: [], powerUsage: [], gpuUtilization: [], memoryUtilization: [] }
  for (const point of history) {
    next.times.push(new Date(point.timestamp * 1000))
    next.temperatures.push(point.temperature)
    next.powerUsage.push(point.power_usage)
    next.gpuUtilization.push(point.gpu_utilization)
    next.memoryUtilization.push(point.memory_utilization)
  }
  return next
}
```

```js
const history = ref({})
watch(() => props.gpus, (gpus) => {
  history.value = appendGpuHistorySample(history.value, gpus || [], new Date(), MAX_POINTS)
  option.value = {
    ...option.value,
    series: Object.entries(history.value).map(([idx, points]) => ({
      name: `GPU ${idx}`,
      type: 'line',
      smooth: true,
      symbol: 'none',
      lineStyle: { width: 2, color: GPU_COLORS[idx] || '#3A5F4B' },
      data: points.map((point) => [point.time, point.value]),
    })),
  }
}, { immediate: true })
```

```js
import { buildGpuDetailSeries } from '../lib/historyTransforms'

const processedHistory = computed(() => buildGpuDetailSeries(history.value))
```

- [ ] **Step 4: Run full verification in the frontend workspace and then smoke it from Windows**

Run: `npm --prefix frontend run test`
Expected: PASS for `realtimeSummaries`, `domainRefresh`, `app`, and `historyTransforms`.

Run: `npm --prefix frontend run build`
Expected: PASS with a successful production bundle.

Run on Windows: `.\start-dev.bat`
Expected: backend + frontend start normally, inactive tabs stop background refresh bursts, and switching between left-side workbench tabs no longer causes obvious stalls.

- [ ] **Step 5: Commit the final chart and verification work**

```bash
git add frontend/src/lib/historyTransforms.js frontend/src/lib/historyTransforms.test.js frontend/src/components/charts/PowerTrendChart.vue frontend/src/views/GpuDetail.vue
git commit -m "perf: reduce frontend chart rebuild work"
```
