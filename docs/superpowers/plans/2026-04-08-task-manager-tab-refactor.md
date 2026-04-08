# TaskManager 任务页双主轴重构 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将任务页重构为职责清晰的 `任务处置 / 公平诊断 / 规则配置` 三个工作区，去掉跨页签重复信息，并把数据刷新改为按页签加载。

**Architecture:** 先把任务页的数据请求拆成 `actions / fairness / rules` 三条独立 loader，再把页头摘要和规则合并逻辑抽成纯函数 view model，最后将 `TaskManager.vue` 收口为工作区外壳，新增三个 tab 组件分别承载动作、诊断和策略。规则页继续复用 `UserRulesGrid.vue`，但压缩首屏上下文并改成更紧凑的编辑方式；公平页只保留诊断和跳转入口，不再复制候选让路任务列表。

**Tech Stack:** Vue 3、Pinia、Vite、node:test、Python unittest

---

## File Structure

- Create: `frontend/src/lib/taskManagerLoaders.js`
  负责把任务页 API 请求拆成 `loadActionsBundle()`、`loadFairnessBundle()`、`loadRulesBundle()` 三条独立 loader。
- Create: `frontend/src/lib/taskManagerLoaders.test.js`
  验证三个 loader 的调用边界，防止再次回到“所有页签一起拉整套数据”。
- Create: `frontend/src/lib/taskManagerPageModels.js`
  负责生成页签专属摘要卡、规则页 summary cards，并合并公平用户与持久化规则。
- Create: `frontend/src/lib/taskManagerPageModels.test.js`
  覆盖页签摘要模型切换、规则覆盖率统计和规则合并逻辑。
- Create: `frontend/src/components/tasks/TaskActionsTab.vue`
  承载搜索、筛选、账本、执行模式和候选让路任务侧栏。
- Create: `frontend/src/components/tasks/TaskFairnessTab.vue`
  承载公平指数、用户结构、治理建议和跳转到任务处置的入口。
- Create: `frontend/src/components/tasks/TaskRulesTab.vue`
  承载规则页 summary cards 与 `UserRulesGrid.vue`。
- Modify: `frontend/src/views/TaskManager.vue`
  收口为工作区外壳，负责页签状态、动作处理、页头摘要模型和跨页跳转。
- Modify: `frontend/src/composables/useTaskManagerData.js`
  接入新的 loader，按页签启用 refresh，暴露 `actions/fairness/rules` 三个 domain。
- Modify: `frontend/src/stores/app.js`
  将 `domains.tasks` 从单一 `governance` 改为 `actions/fairness/rules`。
- Modify: `frontend/src/components/tasks/FairnessGaugeCard.vue`
  收口为纯诊断卡，不再保留“治理”语义的标题和说明。
- Modify: `frontend/src/components/tasks/UserRulesGrid.vue`
  移除重复的占比上下文，压缩成“当前负载 + 违规状态 + 可展开编辑”的规则卡。
- Create: `tests/test_task_manager_workspace_structure.py`
  做结构性回归检查，确保任务页完成 tab 拆分、刷新 key 拆分，并移除公平页/规则页中的重复信息。

## Task 1: Split Task Data Loading Into Explicit Loaders

**Files:**
- Create: `frontend/src/lib/taskManagerLoaders.js`
- Create: `frontend/src/lib/taskManagerLoaders.test.js`

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/lib/taskManagerLoaders.test.js`:

```js
import test from 'node:test'
import assert from 'node:assert/strict'

import { createTaskManagerLoaders } from './taskManagerLoaders.js'

test('actions loader requests only task ledger and fairness side rail data', async () => {
  const calls = []
  const api = {
    getTasks: async () => {
      calls.push('tasks')
      return { data: { processes: [{ pid: 1, username: 'alice' }] } }
    },
    getFairnessGovernance: async () => {
      calls.push('fairness')
      return { data: { overview: { fairness_index: 84 }, yield_candidates: [{ pid: 1 }] } }
    },
    getGovernanceRules: async () => {
      calls.push('rules')
      return { data: { rules: [{ username: 'alice' }] } }
    },
  }

  const loaders = createTaskManagerLoaders(api)
  const payload = await loaders.loadActionsBundle()

  assert.deepEqual(calls, ['tasks', 'fairness'])
  assert.equal(payload.processes.length, 1)
  assert.equal(payload.fairness.overview.fairness_index, 84)
})

test('fairness loader requests only fairness diagnostics', async () => {
  const calls = []
  const api = {
    getTasks: async () => {
      calls.push('tasks')
      return { data: { processes: [] } }
    },
    getFairnessGovernance: async () => {
      calls.push('fairness')
      return { data: { recommendations: ['释放高占比用户任务'] } }
    },
    getGovernanceRules: async () => {
      calls.push('rules')
      return { data: { rules: [] } }
    },
  }

  const loaders = createTaskManagerLoaders(api)
  const payload = await loaders.loadFairnessBundle()

  assert.deepEqual(calls, ['fairness'])
  assert.deepEqual(payload.fairness.recommendations, ['释放高占比用户任务'])
})

test('rules loader requests fairness users and stored rules but skips task ledger', async () => {
  const calls = []
  const api = {
    getTasks: async () => {
      calls.push('tasks')
      return { data: { processes: [] } }
    },
    getFairnessGovernance: async () => {
      calls.push('fairness')
      return { data: { users: [{ username: 'alice', task_count: 2 }] } }
    },
    getGovernanceRules: async () => {
      calls.push('rules')
      return { data: { rules: [{ username: 'alice', role: 'protected' }] } }
    },
  }

  const loaders = createTaskManagerLoaders(api)
  const payload = await loaders.loadRulesBundle()

  assert.deepEqual(calls, ['fairness', 'rules'])
  assert.equal(payload.fairness.users[0].username, 'alice')
  assert.equal(payload.rules[0].role, 'protected')
})
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd frontend && node --test src/lib/taskManagerLoaders.test.js
```

Expected: FAIL with `Cannot find module './taskManagerLoaders.js'` or missing export errors.

- [ ] **Step 3: Write minimal implementation**

Create `frontend/src/lib/taskManagerLoaders.js`:

```js
export function createTaskManagerLoaders(api) {
  return {
    async loadActionsBundle() {
      const [{ data: taskData }, { data: fairnessData }] = await Promise.all([
        api.getTasks(),
        api.getFairnessGovernance(),
      ])
      return {
        processes: taskData?.processes || [],
        fairness: fairnessData || {},
      }
    },

    async loadFairnessBundle() {
      const { data } = await api.getFairnessGovernance()
      return {
        fairness: data || {},
      }
    },

    async loadRulesBundle() {
      const [{ data: fairnessData }, { data: rulesData }] = await Promise.all([
        api.getFairnessGovernance(),
        api.getGovernanceRules(),
      ])
      return {
        fairness: fairnessData || {},
        rules: rulesData?.rules || [],
      }
    },
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
cd frontend && node --test src/lib/taskManagerLoaders.test.js
```

Expected: PASS with `3 tests` passed.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/taskManagerLoaders.js frontend/src/lib/taskManagerLoaders.test.js
git commit -m "feat: split task manager loaders"
```

## Task 2: Add Tab-Specific Page Models And Rule Merge Logic

**Files:**
- Create: `frontend/src/lib/taskManagerPageModels.js`
- Create: `frontend/src/lib/taskManagerPageModels.test.js`

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/lib/taskManagerPageModels.test.js`:

```js
import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildRulesPageModel,
  buildTaskWorkspaceModel,
} from './taskManagerPageModels.js'

test('buildTaskWorkspaceModel switches quick stats by active tab', () => {
  const actions = buildTaskWorkspaceModel('actions', {
    taskSummary: {
      manageableCount: 6,
      urgentCount: 2,
    },
    executionModeLabel: '真实执行',
  })
  const fairness = buildTaskWorkspaceModel('fairness', {
    fairnessOverview: {
      fairness_index: 74,
      reclaimable_candidates: 3,
      summary: '存在高占比用户，需要释放部分任务。',
    },
    fairnessUsers: [
      { username: 'alice', memory_share_pct: 62 },
      { username: 'bob', memory_share_pct: 18 },
    ],
  })

  assert.deepEqual(
    actions.quickStats.map((item) => item.label),
    ['可治理任务', '紧急任务', '当前模式'],
  )
  assert.deepEqual(
    fairness.quickStats.map((item) => item.label),
    ['公平指数', '偏斜用户', '建议让路'],
  )
  assert.equal(fairness.quickStats[1].value, '1')
})

test('buildRulesPageModel merges stored rules into fairness users and computes coverage', () => {
  const model = buildRulesPageModel({
    users: [
      {
        username: 'alice',
        task_count: 2,
        gpu_count: 1,
        violation_count: 1,
        governance_rule: null,
      },
      {
        username: 'bob',
        task_count: 1,
        gpu_count: 1,
        violation_count: 0,
        governance_rule: {
          role: 'member',
          max_tasks: 4,
          max_gpu_count: 1,
          max_memory_gb: 8,
          allow_preempt: true,
          note: '',
        },
      },
    ],
    rules: [
      {
        username: 'alice',
        role: 'protected',
        max_tasks: 8,
        max_gpu_count: 2,
        max_memory_gb: 24,
        allow_preempt: false,
        note: 'vip',
      },
    ],
  })

  assert.equal(model.summaryCards[0].value, '2')
  assert.equal(model.summaryCards[1].value, '1')
  assert.equal(model.summaryCards[2].value, '50%')
  assert.equal(model.users[0].governance_rule.role, 'protected')
  assert.equal(model.users[0].violationLabel, '违规 1')
  assert.equal(model.users[1].workloadSummary, '1 个任务 · 1 张GPU')
})
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd frontend && node --test src/lib/taskManagerPageModels.test.js
```

Expected: FAIL with `Cannot find module './taskManagerPageModels.js'` or missing export errors.

- [ ] **Step 3: Write minimal implementation**

Create `frontend/src/lib/taskManagerPageModels.js`:

```js
const DEFAULT_RULE = {
  role: 'member',
  max_tasks: 4,
  max_gpu_count: 1,
  max_memory_gb: 8,
  allow_preempt: true,
  note: '',
}

function stat(label, value, hint) {
  return {
    label,
    value: String(value),
    hint,
  }
}

function skewedUserCount(users = []) {
  return users.filter((user) => Number(user.memory_share_pct || 0) > 35).length
}

export function buildTaskWorkspaceModel(tab, input = {}) {
  if (tab === 'fairness') {
    const overview = input.fairnessOverview || {}
    const users = input.fairnessUsers || []
    return {
      title: '公平诊断',
      description: '这一页只解释当前共享是否均衡，以及应该往哪个方向调整。',
      quickStats: [
        stat('公平指数', overview.fairness_index ?? 100, overview.summary || '当前共享稳定。'),
        stat('偏斜用户', skewedUserCount(users), '只统计显存占比显著偏高的活跃用户'),
        stat('建议让路', overview.reclaimable_candidates ?? 0, '动作执行统一回到任务处置页'),
      ],
    }
  }

  if (tab === 'rules') {
    const summary = input.rulesSummary || {
      activeUsers: 0,
      violatedUsers: 0,
      coveragePct: 0,
    }
    return {
      title: '规则配置',
      description: '这一页只定义用户角色、额度和让路边界。',
      quickStats: [
        stat('活跃用户', summary.activeUsers, '当前导入范围内存在任务的用户'),
        stat('违规用户', summary.violatedUsers, '仅显示规则外的用户数量'),
        stat('覆盖率', `${summary.coveragePct}%`, '已配置持久化规则的用户占比'),
      ],
    }
  }

  const taskSummary = input.taskSummary || {}
  return {
    title: '任务处置',
    description: '这一页只做筛选、分级和执行，让动作与诊断彻底分离。',
    quickStats: [
      stat('可治理任务', taskSummary.manageableCount ?? 0, '当前允许直接执行治理动作的任务'),
      stat('紧急任务', taskSummary.urgentCount ?? 0, '预算紧张时优先保障'),
      stat('当前模式', input.executionModeLabel || '真实执行', '执行模式只在任务处置页表达'),
    ],
  }
}

export function buildRulesPageModel(input = {}) {
  const users = input.users || []
  const rules = input.rules || []
  const ruleMap = new Map(rules.map((rule) => [rule.username, rule]))

  const mergedUsers = users.map((user) => {
    const storedRule = ruleMap.get(user.username)
    const governanceRule = storedRule || user.governance_rule || DEFAULT_RULE
    const violationCount = Number(user.violation_count || 0)
    return {
      ...user,
      governance_rule: governanceRule,
      workloadSummary: `${user.task_count || 0} 个任务 · ${user.gpu_count || 0} 张GPU`,
      violationLabel: violationCount > 0 ? `违规 ${violationCount}` : '规则内',
    }
  })

  const violatedUsers = mergedUsers.filter((user) => Number(user.violation_count || 0) > 0).length
  const coveragePct = mergedUsers.length
    ? Math.round((rules.length / mergedUsers.length) * 100)
    : 0

  return {
    users: mergedUsers,
    summaryCards: [
      stat('活跃用户', mergedUsers.length, '当前有任务的用户'),
      stat('违规用户', violatedUsers, '规则外用户需要优先关注'),
      stat('覆盖率', `${coveragePct}%`, '已设置持久化规则的用户占比'),
    ],
    summary: {
      activeUsers: mergedUsers.length,
      violatedUsers,
      coveragePct,
    },
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
cd frontend && node --test src/lib/taskManagerPageModels.test.js
```

Expected: PASS with `2 tests` passed.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/taskManagerPageModels.js frontend/src/lib/taskManagerPageModels.test.js
git commit -m "feat: add task manager page models"
```

## Task 3: Rewire Store, Composable, And View Shell Around Split Tabs

**Files:**
- Modify: `frontend/src/stores/app.js`
- Modify: `frontend/src/composables/useTaskManagerData.js`
- Create: `frontend/src/components/tasks/TaskActionsTab.vue`
- Create: `frontend/src/components/tasks/TaskFairnessTab.vue`
- Create: `frontend/src/components/tasks/TaskRulesTab.vue`
- Modify: `frontend/src/views/TaskManager.vue`
- Create: `tests/test_task_manager_workspace_structure.py`

- [ ] **Step 1: Write the failing structure regression test**

Create `tests/test_task_manager_workspace_structure.py`:

```python
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TaskManagerWorkspaceStructureTests(unittest.TestCase):
    def test_task_manager_uses_split_tab_components_and_labels(self):
        text = (ROOT / 'frontend/src/views/TaskManager.vue').read_text(encoding='utf-8')
        self.assertIn('TaskActionsTab', text)
        self.assertIn('TaskFairnessTab', text)
        self.assertIn('TaskRulesTab', text)
        self.assertIn("label: '任务处置'", text)
        self.assertIn("label: '公平诊断'", text)
        self.assertIn("label: '规则配置'", text)

    def test_task_manager_data_uses_split_refresh_keys(self):
        text = (ROOT / 'frontend/src/composables/useTaskManagerData.js').read_text(encoding='utf-8')
        self.assertIn("key: 'actions'", text)
        self.assertIn("key: 'fairness'", text)
        self.assertIn("key: 'rules'", text)
        self.assertNotIn("key: 'governance'", text)


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
timeout 60s python -m unittest tests.test_task_manager_workspace_structure
```

Expected: FAIL because `TaskManager.vue` still uses old labels and `useTaskManagerData.js` still uses `key: 'governance'`.

- [ ] **Step 3: Update task domain keys in the app store**

Modify `frontend/src/stores/app.js`:

```js
function createDomainState() {
  return {
    dashboard: {
      overview: requestState(),
      live: requestState(),
      health: requestState(),
    },
    scheduler: {
      status: requestState(),
      carbon: requestState(),
      audit: requestState(),
      evaluation: requestState(),
    },
    tasks: {
      actions: requestState(),
      fairness: requestState(),
      rules: requestState(),
    },
    monitor: {
      system: requestState(),
      training: requestState(),
      users: requestState(),
      timeline: requestState(),
    },
    energy: {
      overview: requestState(),
      prediction: requestState(),
      ai: requestState(),
    },
  }
}
```

- [ ] **Step 4: Replace the task composable with tab-specific refresh logic**

Replace `frontend/src/composables/useTaskManagerData.js` with:

```js
import { computed, onUnmounted, ref, watch } from 'vue'
import {
  getFairnessGovernance,
  getGovernanceRules,
  getTasks,
} from '../services/api.js'
import { createTaskManagerLoaders } from '../lib/taskManagerLoaders.js'
import {
  filterProcesses,
  selectVisibleProcesses,
} from '../lib/realtimeSummaries.js'
import { useDomainRefresh } from './useDomainRefresh.js'
import { useAppStore } from '../stores/app.js'

const KEYWORD_DEBOUNCE_MS = 160
const DEFAULT_ACTIONS_STATE = {
  processes: [],
  fairness: {
    overview: { fairness_index: 100, summary: '当前共享稳定。', reclaimable_candidates: 0 },
    users: [],
    recommendations: [],
    yield_candidates: [],
  },
}
const DEFAULT_FAIRNESS_STATE = {
  fairness: {
    overview: { fairness_index: 100, summary: '当前共享稳定。', reclaimable_candidates: 0 },
    users: [],
    recommendations: [],
    yield_candidates: [],
  },
}
const DEFAULT_RULES_STATE = {
  fairness: {
    overview: { fairness_index: 100, summary: '当前共享稳定。', reclaimable_candidates: 0 },
    users: [],
    recommendations: [],
    yield_candidates: [],
  },
  rules: [],
}

export function useTaskManagerData(options = {}) {
  const store = useAppStore()
  const activeTab = options.activeTab
  const keyword = options.keyword
  const selectedPriority = options.selectedPriority
  const showAllProcesses = options.showAllProcesses
  const refreshEnabled = (tabKey) => !activeTab || activeTab.value === tabKey
  const loaders = createTaskManagerLoaders({
    getTasks,
    getFairnessGovernance,
    getGovernanceRules,
  })

  const debouncedKeyword = ref('')
  let keywordTimer = null

  watch(keyword, (value) => {
    if (keywordTimer) clearTimeout(keywordTimer)
    keywordTimer = setTimeout(() => {
      debouncedKeyword.value = value
    }, KEYWORD_DEBOUNCE_MS)
  }, { immediate: true })

  onUnmounted(() => {
    if (keywordTimer) clearTimeout(keywordTimer)
  })

  const actionsRefresh = useDomainRefresh({
    section: 'tasks',
    key: 'actions',
    intervalMs: 30000,
    staleTime: 10000,
    enabled: () => refreshEnabled('actions'),
    loader: loaders.loadActionsBundle,
    applyData: (payload) => {
      store.replaceProcesses(payload.processes)
    },
  })

  const fairnessRefresh = useDomainRefresh({
    section: 'tasks',
    key: 'fairness',
    intervalMs: 30000,
    staleTime: 10000,
    enabled: () => refreshEnabled('fairness'),
    loader: loaders.loadFairnessBundle,
  })

  const rulesRefresh = useDomainRefresh({
    section: 'tasks',
    key: 'rules',
    intervalMs: 30000,
    staleTime: 10000,
    enabled: () => refreshEnabled('rules'),
    loader: loaders.loadRulesBundle,
  })

  const filteredProcesses = computed(() => filterProcesses(
    store.normalizedProcesses,
    {
      keyword: debouncedKeyword.value,
      priority: selectedPriority?.value,
      includeAll: showAllProcesses?.value,
    },
  ))

  const visibleProcesses = computed(() => selectVisibleProcesses(
    store.normalizedProcesses,
    showAllProcesses?.value,
  ))

  return {
    filteredProcesses,
    visibleProcesses,
    taskSummary: computed(() => store.taskSummary),
    actionsDomain: computed(() => store.domains.tasks.actions),
    fairnessDomain: computed(() => store.domains.tasks.fairness),
    rulesDomain: computed(() => store.domains.tasks.rules),
    actionsState: computed(() => store.domains.tasks.actions.data || DEFAULT_ACTIONS_STATE),
    fairnessState: computed(() => store.domains.tasks.fairness.data || DEFAULT_FAIRNESS_STATE),
    rulesState: computed(() => store.domains.tasks.rules.data || DEFAULT_RULES_STATE),
    refreshActions: actionsRefresh.refresh,
    refreshFairness: fairnessRefresh.refresh,
    refreshRules: rulesRefresh.refresh,
  }
}
```

- [ ] **Step 5: Create tab components for actions, fairness, and rules**

Create `frontend/src/components/tasks/TaskActionsTab.vue`:

```vue
<script setup>
import WorkspacePaneLayout from '../workspace/WorkspacePaneLayout.vue'
import TaskProcessLedger from './TaskProcessLedger.vue'

const props = defineProps({
  keyword: { type: String, required: true },
  selectedPriority: { type: String, required: true },
  showAllProcesses: { type: Boolean, required: true },
  filteredProcesses: { type: Array, required: true },
  visibleProcesses: { type: Array, required: true },
  priorityColors: { type: Object, required: true },
  helpers: { type: Object, required: true },
  handlers: { type: Object, required: true },
  exporting: { type: Boolean, default: false },
  executionMode: { type: String, required: true },
  riskAcknowledged: { type: Boolean, required: true },
  isDryRun: { type: Boolean, required: true },
  isReal: { type: Boolean, required: true },
  executionSummary: { type: String, required: true },
  yieldCandidates: { type: Array, default: () => [] },
})

const emit = defineEmits([
  'update:keyword',
  'update:selectedPriority',
  'update:showAllProcesses',
  'update:executionMode',
  'update:riskAcknowledged',
  'export',
])
</script>

<template>
  <WorkspacePaneLayout>
    <template #main>
      <section class="tech-card toolbar-card">
        <div class="toolbar-card__left">
          <input
            :value="props.keyword"
            class="task-input"
            placeholder="搜索 PID / 用户 / 进程名 / 命令"
            @input="emit('update:keyword', $event.target.value)"
          />
          <select
            :value="props.selectedPriority"
            class="task-select"
            @change="emit('update:selectedPriority', $event.target.value)"
          >
            <option value="all">全部优先级</option>
            <option value="urgent">紧急</option>
            <option value="normal">普通</option>
            <option value="deferrable">可延迟</option>
          </select>
        </div>
        <div class="toolbar-card__right">
          <div class="toolbar-card__switch">
            <button class="btn-tech" :class="{ 'btn-tech--primary': !props.showAllProcesses }" @click="emit('update:showAllProcesses', false)">仅治理任务</button>
            <button class="btn-tech" :class="{ 'btn-tech--primary': props.showAllProcesses }" @click="emit('update:showAllProcesses', true)">全部 GPU 相关进程</button>
          </div>
          <button class="btn-tech" :disabled="props.exporting" @click="emit('export')">
            {{ props.exporting ? '导出中...' : '导出治理报告' }}
          </button>
          <span class="toolbar-card__summary">当前显示 {{ props.filteredProcesses.length }} / {{ props.visibleProcesses.length }} 条</span>
        </div>
      </section>

      <section class="tech-card ledger-panel">
        <div class="ledger-panel__head">
          <div class="panel-card__title">任务账本</div>
          <div class="ledger-panel__hint">动作与诊断拆开后，这里只保留筛选、分级和执行闭环。</div>
        </div>
        <TaskProcessLedger
          :processes="props.filteredProcesses"
          :show-all-processes="props.showAllProcesses"
          :priority-colors="props.priorityColors"
          :helpers="props.helpers"
          :handlers="props.handlers"
        />
      </section>
    </template>

    <template #side>
      <section class="tech-card panel-card">
        <div class="panel-card__title">执行模式</div>
        <div class="mode-box">
          <div class="mode-box__switch">
            <button class="btn-tech" :class="{ 'btn-tech--primary': props.isDryRun }" @click="emit('update:executionMode', 'dry_run')">演练模式</button>
            <button class="btn-tech" :class="{ 'btn-tech--primary': props.isReal }" @click="emit('update:executionMode', 'real')">真实执行</button>
          </div>
          <label v-if="props.isReal" class="mode-box__ack">
            <input
              :checked="props.riskAcknowledged"
              type="checkbox"
              @change="emit('update:riskAcknowledged', $event.target.checked)"
            />
            我已确认会直接作用于真实进程
          </label>
          <div class="mode-box__hint">{{ props.executionSummary }}</div>
        </div>
      </section>

      <section class="tech-card panel-card">
        <div class="panel-card__title">候选让路任务</div>
        <div class="yield-list">
          <div v-for="candidate in props.yieldCandidates.slice(0, 5)" :key="candidate.pid" class="yield-item">
            <div class="yield-item__top">
              <span class="yield-item__pid">PID {{ candidate.pid }}</span>
              <span class="yield-item__priority" :style="{ color: props.priorityColors[candidate.priority || 'normal'].color, background: props.priorityColors[candidate.priority || 'normal'].bg }">
                {{ props.priorityColors[candidate.priority || 'normal'].label }}
              </span>
            </div>
            <div class="yield-item__reason">{{ candidate.yield_reason }}</div>
          </div>
          <div v-if="!props.yieldCandidates.length" class="panel-card__item">当前没有需要优先让路的任务。</div>
        </div>
      </section>
    </template>
  </WorkspacePaneLayout>
</template>
```

Create `frontend/src/components/tasks/TaskFairnessTab.vue`:

```vue
<script setup>
import FairnessGaugeCard from './FairnessGaugeCard.vue'

const props = defineProps({
  overview: { type: Object, default: () => ({}) },
  users: { type: Array, default: () => [] },
  recommendations: { type: Array, default: () => [] },
  reclaimableCount: { type: Number, default: 0 },
})

const emit = defineEmits(['open-actions'])
</script>

<template>
  <section class="fairness-dashboard">
    <FairnessGaugeCard :overview="props.overview" :users="props.users" />

    <div class="fairness-side">
      <div class="tech-card panel-card">
        <div class="panel-card__title">治理建议</div>
        <div class="panel-card__list">
          <div v-for="(item, index) in props.recommendations" :key="index" class="panel-card__item">
            {{ item }}
          </div>
          <div v-if="!props.recommendations.length" class="panel-card__item">
            当前没有额外治理建议。
          </div>
        </div>
      </div>

      <div class="tech-card panel-card">
        <div class="panel-card__title">进入任务处置执行</div>
        <div class="panel-card__item">
          当前有 {{ props.reclaimableCount }} 个候选让路任务；真正的暂停、恢复和终止动作统一在任务处置页完成。
        </div>
        <button class="btn-tech btn-tech--primary" @click="emit('open-actions')">
          查看建议让路任务
        </button>
      </div>
    </div>
  </section>
</template>
```

Create `frontend/src/components/tasks/TaskRulesTab.vue`:

```vue
<script setup>
import UserRulesGrid from './UserRulesGrid.vue'

const props = defineProps({
  summaryCards: { type: Array, default: () => [] },
  users: { type: Array, default: () => [] },
})

const emit = defineEmits(['save', 'reset'])
</script>

<template>
  <div class="task-rules-tab">
    <section class="stats-grid workspace-summary-strip">
      <div v-for="item in props.summaryCards" :key="item.label" class="tech-card stat-card">
        <div class="stat-card__label">{{ item.label }}</div>
        <div class="stat-card__value stat-value">{{ item.value }}</div>
        <div class="stat-card__hint">{{ item.hint }}</div>
      </div>
    </section>

    <UserRulesGrid
      :users="props.users"
      @save="emit('save', $event)"
      @reset="emit('reset', $event)"
    />
  </div>
</template>
```

- [ ] **Step 6: Rewire `TaskManager.vue` to use the new shell, models, and tab components**

Update `frontend/src/views/TaskManager.vue` so the top-level structure becomes:

```vue
<script setup>
import { computed, ref, watch } from 'vue'
import {
  deleteGovernanceRule,
  exportGovernanceReport,
  pauseTask,
  resumeTask,
  saveGovernanceRule,
  setTaskPriority,
  terminateTask,
} from '../services/api'
import { exportTextFile } from '../services/desktopExport'
import TaskActionsTab from '../components/tasks/TaskActionsTab.vue'
import TaskFairnessTab from '../components/tasks/TaskFairnessTab.vue'
import TaskRulesTab from '../components/tasks/TaskRulesTab.vue'
import WorkspaceSummary from '../components/workspace/WorkspaceSummary.vue'
import WorkspaceTabs from '../components/workspace/WorkspaceTabs.vue'
import { useTaskManagerData } from '../composables/useTaskManagerData.js'
import { useExecutionMode } from '../composables/useExecutionMode.js'
import { useActionFeedback } from '../composables/useActionFeedback.js'
import {
  buildRulesPageModel,
  buildTaskWorkspaceModel,
} from '../lib/taskManagerPageModels.js'

const activeTab = ref('actions')
const keyword = ref('')
const selectedPriority = ref('all')
const showAllProcesses = ref(false)
const exporting = ref(false)
const actionLoading = ref({})
const {
  executionMode,
  riskAcknowledged,
  isDryRun,
  isReal,
  modeLabel,
  modeBadgeClass,
  buildExecutionParams,
} = useExecutionMode()
const { actionNotice, showNotice } = useActionFeedback()

const taskTabs = [
  { key: 'actions', label: '任务处置', desc: '筛选与执行' },
  { key: 'fairness', label: '公平诊断', desc: '倾斜与建议' },
  { key: 'rules', label: '规则配置', desc: '额度与角色' },
]

const {
  filteredProcesses,
  visibleProcesses,
  taskSummary,
  actionsState,
  fairnessState,
  rulesState,
  refreshActions,
  refreshFairness,
  refreshRules,
} = useTaskManagerData({
  activeTab,
  keyword,
  selectedPriority,
  showAllProcesses,
})

const rulesPageModel = computed(() => buildRulesPageModel({
  users: rulesState.value.fairness?.users || [],
  rules: rulesState.value.rules || [],
}))

const workspaceModel = computed(() => buildTaskWorkspaceModel(activeTab.value, {
  taskSummary: taskSummary.value,
  fairnessOverview: fairnessState.value.fairness?.overview,
  fairnessUsers: fairnessState.value.fairness?.users || [],
  rulesSummary: rulesPageModel.value.summary,
  executionModeLabel: modeLabel.value,
}))

const executionSummary = computed(() =>
  isReal.value
    ? (riskAcknowledged.value
      ? '当前为真实执行模式，操作会直接作用于可治理 GPU 任务。'
      : '当前为真实执行模式，但还未确认风险，按钮会保持禁用。')
    : '当前为演练模式，只生成预演结果，不会改动真实进程。'
)

watch(activeTab, (nextTab) => {
  if (nextTab === 'actions') {
    void refreshActions({ force: true })
    return
  }
  if (nextTab === 'fairness') {
    void refreshFairness({ force: true })
    return
  }
  void refreshRules({ force: true })
})

function openActionsFromFairness() {
  activeTab.value = 'actions'
  showAllProcesses.value = false
}

// 将当前文件里已经可用的 priorityColors、ledgerHelpers、ledgerHandlers、
// doAction()、changePriority()、handleSaveRule()、handleResetRule()、
// doExportGovernance() 原样迁移到这个新壳层中；本任务不改变这些动作逻辑，只改变它们被哪个子组件渲染。
</script>

<template>
  <div class="task-page ink-page-shell">
    <WorkspaceSummary
      :title="workspaceModel.title"
      :description="workspaceModel.description"
    >
      <template #meta>
        <div class="ink-inline-meta">
          <span class="status-badge" :class="modeBadgeClass">{{ modeLabel }}</span>
          <span class="status-badge status-badge--ok">{{ taskTabs.find((item) => item.key === activeTab)?.label }}</span>
        </div>
      </template>
    </WorkspaceSummary>

    <section class="stats-grid workspace-summary-strip">
      <div v-for="item in workspaceModel.quickStats" :key="item.label" class="tech-card stat-card">
        <div class="stat-card__label">{{ item.label }}</div>
        <div class="stat-card__value stat-value">{{ item.value }}</div>
        <div class="stat-card__hint">{{ item.hint }}</div>
      </div>
    </section>

    <div class="workspace-nav-layout">
      <div class="workspace-nav-layout__nav">
        <WorkspaceTabs v-model="activeTab" :items="taskTabs" />
      </div>

      <section class="workspace-nav-layout__content">
        <div v-if="actionNotice" class="tech-card notice" :class="`notice--${actionNotice.tone}`">
          <div class="notice__title">{{ actionNotice.title }}</div>
          <div class="notice__detail">{{ actionNotice.detail }}</div>
        </div>

        <TaskFairnessTab
          v-if="activeTab === 'fairness'"
          :overview="fairnessState.fairness?.overview || {}"
          :users="fairnessState.fairness?.users || []"
          :recommendations="fairnessState.fairness?.recommendations || []"
          :reclaimable-count="fairnessState.fairness?.overview?.reclaimable_candidates || 0"
          @open-actions="openActionsFromFairness"
        />

        <TaskRulesTab
          v-else-if="activeTab === 'rules'"
          :summary-cards="rulesPageModel.summaryCards"
          :users="rulesPageModel.users"
          @save="handleSaveRule"
          @reset="handleResetRule"
        />

        <TaskActionsTab
          v-else
          :keyword="keyword"
          :selected-priority="selectedPriority"
          :show-all-processes="showAllProcesses"
          :filtered-processes="filteredProcesses"
          :visible-processes="visibleProcesses"
          :priority-colors="priorityColors"
          :helpers="ledgerHelpers"
          :handlers="ledgerHandlers"
          :exporting="exporting"
          :execution-mode="executionMode"
          :risk-acknowledged="riskAcknowledged"
          :is-dry-run="isDryRun"
          :is-real="isReal"
          :execution-summary="executionSummary"
          :yield-candidates="actionsState.fairness?.yield_candidates || []"
          @update:keyword="keyword = $event"
          @update:selected-priority="selectedPriority = $event"
          @update:show-all-processes="showAllProcesses = $event"
          @update:execution-mode="executionMode = $event"
          @update:risk-acknowledged="riskAcknowledged = $event"
          @export="doExportGovernance('markdown')"
        />
      </section>
    </div>
  </div>
</template>
```

- [ ] **Step 7: Run the structure and unit tests**

Run:

```bash
cd frontend && node --test src/lib/taskManagerLoaders.test.js src/lib/taskManagerPageModels.test.js
```

Expected: PASS with `5 tests` passed.

Run:

```bash
timeout 60s python -m unittest tests.test_task_manager_workspace_structure
```

Expected: PASS with `OK`.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/stores/app.js frontend/src/composables/useTaskManagerData.js frontend/src/components/tasks/TaskActionsTab.vue frontend/src/components/tasks/TaskFairnessTab.vue frontend/src/components/tasks/TaskRulesTab.vue frontend/src/views/TaskManager.vue tests/test_task_manager_workspace_structure.py
git commit -m "feat: split task manager tabs"
```

## Task 4: Remove Remaining Redundancy From Fairness And Rules Tabs

**Files:**
- Modify: `tests/test_task_manager_workspace_structure.py`
- Modify: `frontend/src/components/tasks/FairnessGaugeCard.vue`
- Modify: `frontend/src/components/tasks/UserRulesGrid.vue`

- [ ] **Step 1: Extend the structure regression test for duplicate removal**

Update `tests/test_task_manager_workspace_structure.py`:

```python
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TaskManagerWorkspaceStructureTests(unittest.TestCase):
    def test_task_manager_uses_split_tab_components_and_labels(self):
        text = (ROOT / 'frontend/src/views/TaskManager.vue').read_text(encoding='utf-8')
        self.assertIn('TaskActionsTab', text)
        self.assertIn('TaskFairnessTab', text)
        self.assertIn('TaskRulesTab', text)
        self.assertIn("label: '任务处置'", text)
        self.assertIn("label: '公平诊断'", text)
        self.assertIn("label: '规则配置'", text)

    def test_task_manager_data_uses_split_refresh_keys(self):
        text = (ROOT / 'frontend/src/composables/useTaskManagerData.js').read_text(encoding='utf-8')
        self.assertIn("key: 'actions'", text)
        self.assertIn("key: 'fairness'", text)
        self.assertIn("key: 'rules'", text)
        self.assertNotIn("key: 'governance'", text)

    def test_fairness_and_rules_tabs_stop_repeating_actions_and_share_bars(self):
        fairness = (ROOT / 'frontend/src/components/tasks/TaskFairnessTab.vue').read_text(encoding='utf-8')
        rules = (ROOT / 'frontend/src/components/tasks/UserRulesGrid.vue').read_text(encoding='utf-8')
        self.assertIn('查看建议让路任务', fairness)
        self.assertNotIn('yield-item', fairness)
        self.assertNotIn('memory_share_pct', rules)


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
timeout 60s python -m unittest tests.test_task_manager_workspace_structure
```

Expected: FAIL until `UserRulesGrid.vue` 去掉 `memory_share_pct` 相关展示并完成规则页收口。

- [ ] **Step 3: Make the fairness card diagnosis-only**

Modify `frontend/src/components/tasks/FairnessGaugeCard.vue`:

```vue
<template>
  <div class="tech-card fairness-gauge-card">
    <div class="fairness-gauge-card__head">
      <div>
        <div class="fairness-gauge-card__eyebrow">多用户资源倾斜诊断</div>
        <div class="panel-card__title">公平诊断仪表盘</div>
      </div>
      <div class="fairness-gauge-card__seal">衡</div>
    </div>
    <div class="fairness-gauge">
      <div class="fairness-gauge__ring">
        <svg viewBox="0 0 120 120" class="fairness-gauge__svg">
          <circle cx="60" cy="60" r="52" fill="none" stroke="rgba(255, 255, 255, 0.06)" stroke-width="8" />
          <circle
            cx="60"
            cy="60"
            r="52"
            fill="none"
            :stroke="gaugeColor"
            stroke-width="8"
            stroke-linecap="round"
            :stroke-dasharray="`${fairnessIndex * 3.267} 326.7`"
            transform="rotate(-90 60 60)"
            style="transition: stroke-dasharray 1.2s ease"
          />
        </svg>
        <div class="fairness-gauge__value">
          <span class="fairness-gauge__number stat-value" :style="{ color: gaugeColor }">{{ fairnessIndex }}</span>
          <span class="fairness-gauge__label">公平指数</span>
        </div>
      </div>
      <div class="fairness-gauge__info">
        <div class="fairness-gauge__level" :style="{ color: gaugeColor, background: gaugeBg }">
          {{ levelLabel }}
        </div>
        <div class="fairness-gauge__summary">{{ overview.summary || '当前共享状态稳定。' }}</div>
      </div>
    </div>
    <div v-if="users.length" class="fairness-users-dist">
      <div class="fairness-users-dist__title">用户资源占比</div>
      <div class="fairness-bar-list">
        <div v-for="user in users.slice(0, 6)" :key="user.username" class="fairness-bar-item">
          <div class="fairness-bar-item__head">
            <span class="fairness-bar-item__name">{{ user.username }}</span>
            <span class="fairness-bar-item__pct">{{ user.memory_share_pct || 0 }}%</span>
          </div>
          <div class="fairness-bar-item__track">
            <div class="fairness-bar-item__fill" :style="{ width: Math.min(user.memory_share_pct || 0, 100) + '%', background: barColor(user.memory_share_pct || 0) }"></div>
          </div>
          <div class="fairness-bar-item__meta">{{ user.task_count }}任务 · {{ user.gpu_count }}卡</div>
        </div>
      </div>
    </div>
  </div>
</template>
```

- [ ] **Step 4: Compress `UserRulesGrid.vue` into a quieter rules editor**

Replace the interactive portion of `frontend/src/components/tasks/UserRulesGrid.vue` with:

```vue
<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  users: { type: Array, default: () => [] },
})

const emit = defineEmits(['save', 'reset'])

const roleOptions = {
  protected: '保护用户',
  member: '普通用户',
  restricted: '受限用户',
}

const ruleSaving = ref({})
const ruleDrafts = ref({})
const expandedUsers = ref({})

function buildRuleDraft(user) {
  const rule = user.governance_rule || {}
  return {
    role: rule.role || 'member',
    max_tasks: rule.max_tasks ?? 4,
    max_gpu_count: rule.max_gpu_count ?? 1,
    max_memory_gb: rule.max_memory_gb ?? 8,
    allow_preempt: rule.allow_preempt ?? true,
    note: rule.note || '',
  }
}

function syncDrafts(users) {
  const next = {}
  for (const user of users || []) {
    next[user.username] = buildRuleDraft(user)
  }
  ruleDrafts.value = next
}

watch(() => props.users, (users) => syncDrafts(users), { immediate: true })

function toggleEditor(username) {
  expandedUsers.value[username] = !expandedUsers.value[username]
}

async function saveRule(user) {
  const draft = ruleDrafts.value[user.username]
  if (!draft) return
  ruleSaving.value[user.username] = true
  emit('save', {
    username: user.username,
    role: draft.role,
    max_tasks: Number(draft.max_tasks),
    max_gpu_count: Number(draft.max_gpu_count),
    max_memory_gb: Number(draft.max_memory_gb),
    allow_preempt: !!draft.allow_preempt,
    note: draft.note || '',
  })
  ruleSaving.value[user.username] = false
}

async function resetRule(user) {
  ruleSaving.value[user.username] = true
  emit('reset', user.username)
  ruleSaving.value[user.username] = false
}
</script>

<template>
  <section v-if="users.length" class="tech-card rules-panel">
    <div class="rules-panel__head">
      <div class="panel-card__title">用户额度规则</div>
      <div class="rules-panel__hint">这里仅保留做策略判断所需的最小上下文，公平占比与倾斜解释统一留在公平诊断页。</div>
    </div>

    <div class="rules-grid">
      <div v-for="user in users" :key="user.username" class="rule-card">
        <div class="rule-card__top">
          <div>
            <div class="rule-card__name">{{ user.username }}</div>
            <div class="rule-card__meta">{{ user.workloadSummary }}</div>
          </div>
          <span class="rule-card__status" :class="user.violation_count ? 'rule-card__status--warn' : 'rule-card__status--ok'">
            {{ user.violationLabel }}
          </span>
        </div>

        <div v-if="ruleDrafts[user.username]" class="rule-card__summary">
          <span>角色 {{ roleOptions[ruleDrafts[user.username].role] }}</span>
          <span>任务 {{ ruleDrafts[user.username].max_tasks }}</span>
          <span>GPU {{ ruleDrafts[user.username].max_gpu_count }}</span>
          <span>显存 {{ ruleDrafts[user.username].max_memory_gb }} GB</span>
        </div>

        <div class="rule-card__actions">
          <button class="btn-tech" @click="toggleEditor(user.username)">
            {{ expandedUsers[user.username] ? '收起规则' : '编辑规则' }}
          </button>
          <button class="btn-tech" :disabled="ruleSaving[user.username]" @click="saveRule(user)">
            {{ ruleSaving[user.username] ? '保存中...' : '保存规则' }}
          </button>
          <button class="btn-tech" :disabled="ruleSaving[user.username]" @click="resetRule(user)">
            恢复默认
          </button>
        </div>

        <div v-if="expandedUsers[user.username] && ruleDrafts[user.username]" class="rule-card__form">
          <select v-model="ruleDrafts[user.username].role" class="task-select">
            <option value="protected">{{ roleOptions.protected }}</option>
            <option value="member">{{ roleOptions.member }}</option>
            <option value="restricted">{{ roleOptions.restricted }}</option>
          </select>
          <input v-model.number="ruleDrafts[user.username].max_tasks" class="task-input" type="number" min="1" max="64" placeholder="最多任务" />
          <input v-model.number="ruleDrafts[user.username].max_gpu_count" class="task-input" type="number" min="1" max="16" placeholder="最多GPU" />
          <input v-model.number="ruleDrafts[user.username].max_memory_gb" class="task-input" type="number" min="1" step="0.5" max="1024" placeholder="显存额度(GB)" />
          <select v-model="ruleDrafts[user.username].allow_preempt" class="task-select">
            <option :value="true">允许让路</option>
            <option :value="false">保护任务</option>
          </select>
          <input v-model="ruleDrafts[user.username].note" class="task-input task-input--wide" type="text" placeholder="备注" />
        </div>
      </div>
    </div>
  </section>

  <section v-else class="tech-card rules-panel rules-panel--empty">
    <div class="panel-card__title">用户额度规则</div>
    <div class="panel-card__item">当前没有活跃用户需要配置规则。</div>
  </section>
</template>
```

- [ ] **Step 5: Run focused verification**

Run:

```bash
cd frontend && node --test src/lib/taskManagerLoaders.test.js src/lib/taskManagerPageModels.test.js src/lib/realtimeSummaries.test.js
```

Expected: PASS with all tests green.

Run:

```bash
timeout 60s python -m unittest tests.test_task_manager_workspace_structure tests.test_frontend_ui_structure
```

Expected: PASS with `OK`.

- [ ] **Step 6: Commit**

```bash
git add tests/test_task_manager_workspace_structure.py frontend/src/components/tasks/FairnessGaugeCard.vue frontend/src/components/tasks/UserRulesGrid.vue
git commit -m "feat: dedupe task manager fairness and rules tabs"
```

## Spec Coverage Check

- “三个页签职责收口” 对应 Task 2 和 Task 3：页签摘要模型、tab 组件拆分、`TaskManager.vue` 壳层化。
- “候选让路任务只保留在任务处置页” 对应 Task 3 和 Task 4：`TaskActionsTab.vue` 保留候选列表，`TaskFairnessTab.vue` 改成 CTA。
- “公平诊断只保留诊断与建议” 对应 Task 3 和 Task 4：`TaskFairnessTab.vue` 与 `FairnessGaugeCard.vue` 去动作化。
- “规则配置只保留最小上下文” 对应 Task 2 和 Task 4：`buildRulesPageModel()` 合并用户与规则，`UserRulesGrid.vue` 去掉占比上下文并使用 `workloadSummary`。
- “按页签加载数据” 对应 Task 1 和 Task 3：`taskManagerLoaders.js` 与 `useTaskManagerData.js` 的 `actions/fairness/rules` refresh key。

## Placeholder Scan

- 本计划没有 `TODO`、`TBD`、`implement later` 一类占位语。
- 每个需要新增或修改代码的步骤都给出了具体文件名、代码块和测试命令。
- 所有新增函数、文件和测试名称在前后任务中保持一致，没有跨任务改名。
