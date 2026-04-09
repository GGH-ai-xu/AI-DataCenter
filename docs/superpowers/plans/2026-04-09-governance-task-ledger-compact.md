# 治理页任务账本紧凑行 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把治理页任务账本改造成紧凑双行清单，默认保留优先级与动作按钮，并通过行内展开查看完整说明和命令。

**Architecture:** 先把“哪一条展开、过滤后如何自动关闭”的交互状态抽成纯函数并用 `node:test` 锁住，再把已经超限的 `TaskProcessLedger.vue` 拆成“列表容器 + 行组件”。最终由新行组件承载紧凑双行布局、只读状态和内嵌详情区，父组件只负责列表渲染与单展开控制。

**Tech Stack:** Vue 3 SFC, Node `node:test`, Python `unittest`

---

## File Map

- Create: `frontend/src/lib/governanceTaskLedgerUi.js` - 管理账本详情展开状态的纯函数，负责单展开和过滤后自动关闭
- Create: `frontend/src/lib/governanceTaskLedgerUi.test.js` - `governanceTaskLedgerUi` 的纯函数回归测试
- Create: `frontend/src/components/tasks/TaskProcessLedgerRow.vue` - 单条紧凑账本行，负责默认双行布局、动作按钮和行内详情
- Modify: `frontend/src/components/tasks/TaskProcessLedger.vue` - 缩成列表容器，只负责遍历、展开状态和空态
- Modify: `tests/test_governance_workbench_structure.py` - 新增治理账本紧凑行结构回归

### Task 1: Add Testable Ledger Detail Expansion State

**Files:**
- Create: `frontend/src/lib/governanceTaskLedgerUi.test.js`
- Create: `frontend/src/lib/governanceTaskLedgerUi.js`
- Test: `frontend/src/lib/governanceTaskLedgerUi.test.js`

- [ ] **Step 1: Write the failing UI state regression**

```js
import test from 'node:test'
import assert from 'node:assert/strict'

import { syncExpandedPid, toggleExpandedPid } from './governanceTaskLedgerUi.js'

test('toggleExpandedPid keeps only one row open and collapses the active row', () => {
  assert.equal(toggleExpandedPid(null, 41), 41)
  assert.equal(toggleExpandedPid(41, 41), null)
  assert.equal(toggleExpandedPid(41, 52), 52)
})

test('syncExpandedPid closes detail when the expanded row is no longer visible', () => {
  assert.equal(syncExpandedPid(41, [{ pid: 41 }, { pid: 52 }]), 41)
  assert.equal(syncExpandedPid(41, [{ pid: 52 }]), null)
  assert.equal(syncExpandedPid(null, [{ pid: 52 }]), null)
})
```

- [ ] **Step 2: Run the UI state test and confirm failure**

Run: `node --test frontend/src/lib/governanceTaskLedgerUi.test.js`

Expected: FAIL because `frontend/src/lib/governanceTaskLedgerUi.js` does not exist yet.

- [ ] **Step 3: Implement the pure expansion helpers**

```js
function normalizePid(pid) {
  const normalized = Number(pid)
  return Number.isFinite(normalized) ? normalized : null
}

export function toggleExpandedPid(currentPid, nextPid) {
  const current = normalizePid(currentPid)
  const next = normalizePid(nextPid)
  if (next === null) {
    return current
  }
  return current === next ? null : next
}

export function syncExpandedPid(expandedPid, processes = []) {
  const current = normalizePid(expandedPid)
  if (current === null) {
    return null
  }
  const visible = processes.some((proc) => normalizePid(proc?.pid) === current)
  return visible ? current : null
}
```

- [ ] **Step 4: Re-run the UI state regression**

Run: `node --test frontend/src/lib/governanceTaskLedgerUi.test.js`

Expected: PASS with both tests green.

- [ ] **Step 5: Commit the UI state groundwork**

```bash
git add frontend/src/lib/governanceTaskLedgerUi.js frontend/src/lib/governanceTaskLedgerUi.test.js
git commit -m "feat: add governance ledger detail state helpers"
```

### Task 2: Split The Oversized Ledger File And Implement Compact Rows

**Files:**
- Modify: `tests/test_governance_workbench_structure.py`
- Modify: `frontend/src/components/tasks/TaskProcessLedger.vue`
- Create: `frontend/src/components/tasks/TaskProcessLedgerRow.vue`
- Test: `tests/test_governance_workbench_structure.py`
- Test: `frontend/src/lib/governanceTaskLedgerUi.test.js`

- [ ] **Step 1: Write the failing compact ledger structure regression**

```python
def test_governance_task_ledger_uses_compact_rows_with_inline_details(self):
    parent_text = (ROOT / "frontend/src/components/tasks/TaskProcessLedger.vue").read_text(encoding="utf-8")
    row_text = (ROOT / "frontend/src/components/tasks/TaskProcessLedgerRow.vue").read_text(encoding="utf-8")

    self.assertIn("TaskProcessLedgerRow", parent_text)
    self.assertIn("expandedPid", parent_text)
    self.assertIn("syncExpandedPid", parent_text)
    self.assertIn("toggleExpandedPid", parent_text)
    self.assertIn("查看详情", row_text)
    self.assertIn("收起详情", row_text)
    self.assertIn("task-process-ledger-row__summary", row_text)
    self.assertIn("task-process-ledger-row__details", row_text)
    self.assertIn("task-process-ledger-row__readonly", row_text)
    self.assertNotIn("task-process-ledger__governance", row_text)
    self.assertNotIn("task-process-ledger__actions", row_text)
```

- [ ] **Step 2: Run the structure regression and confirm failure**

Run: `python3 -m unittest tests.test_governance_workbench_structure -q`

Expected: FAIL because `TaskProcessLedgerRow.vue` is missing and the parent component does not manage `expandedPid`.

- [ ] **Step 3: Slim the parent ledger component into a container**

```vue
<script setup>
import { ref, watch } from 'vue'

import TaskProcessLedgerRow from './TaskProcessLedgerRow.vue'
import { syncExpandedPid, toggleExpandedPid } from '../../lib/governanceTaskLedgerUi.js'

const props = defineProps({
  processes: {
    type: Array,
    required: true,
  },
  showAllProcesses: {
    type: Boolean,
    default: false,
  },
  priorityColors: {
    type: Object,
    required: true,
  },
  helpers: {
    type: Object,
    required: true,
  },
  handlers: {
    type: Object,
    required: true,
  },
})

const expandedPid = ref(null)

const priorityOptions = [
  { value: 'urgent', label: '紧急' },
  { value: 'normal', label: '普通' },
  { value: 'deferrable', label: '可延迟' },
]

function priorityTone(priority = 'normal') {
  return props.priorityColors[priority] || props.priorityColors.normal
}

function priorityStyle(priority = 'normal') {
  const tone = priorityTone(priority)
  return {
    color: tone.color,
    background: tone.bg,
  }
}

function isExpanded(proc) {
  return Number(expandedPid.value) === Number(proc.pid)
}

function toggleDetails(proc) {
  expandedPid.value = toggleExpandedPid(expandedPid.value, proc.pid)
}

watch(
  () => props.processes,
  (processes) => {
    expandedPid.value = syncExpandedPid(expandedPid.value, processes)
  },
  { deep: true },
)
</script>

<template>
  <div class="task-process-ledger">
    <TaskProcessLedgerRow
      v-for="proc in props.processes"
      :key="proc.pid"
      :proc="proc"
      :expanded="isExpanded(proc)"
      :priority-options="priorityOptions"
      :priority-style="priorityStyle"
      :helpers="props.helpers"
      :handlers="props.handlers"
      @toggle-details="toggleDetails(proc)"
    />

    <div v-if="!props.processes.length" class="task-process-ledger__empty">
      {{ props.showAllProcesses ? '暂无匹配的 GPU 相关进程。' : '当前没有可治理任务，可切换到“全部 GPU 相关进程”查看背景与系统进程。' }}
    </div>
  </div>
</template>

<style scoped>
.task-process-ledger {
  display: grid;
  gap: 10px;
}

.task-process-ledger__empty {
  padding: 42px 18px;
  text-align: center;
  color: var(--text-muted);
  border-radius: var(--radius-lg);
  border: 1px dashed rgba(0, 212, 170, 0.16);
  background: rgba(255, 255, 255, 0.02);
}
</style>
```

- [ ] **Step 4: Create the compact row component with inline details**

```vue
<script setup>
const props = defineProps({
  proc: {
    type: Object,
    required: true,
  },
  expanded: {
    type: Boolean,
    default: false,
  },
  priorityOptions: {
    type: Array,
    required: true,
  },
  priorityStyle: {
    type: Function,
    required: true,
  },
  helpers: {
    type: Object,
    required: true,
  },
  handlers: {
    type: Object,
    required: true,
  },
})

defineEmits(['toggle-details'])
</script>

<template>
  <article class="task-process-ledger-row">
    <div class="task-process-ledger-row__head">
      <div class="task-process-ledger-row__identity">
        <div class="task-process-ledger-row__name">
          {{ props.proc.name || '未命名进程' }}
        </div>
        <div class="task-process-ledger-row__chips">
          <span class="task-process-ledger-row__pid stat-value">PID {{ props.proc.pid }}</span>
          <span class="task-process-ledger-row__gpu">GPU {{ props.proc.gpu_index }}</span>
          <span class="status-badge" :class="props.helpers.getCategoryClass(props.proc)">
            {{ props.helpers.getCategoryLabel(props.proc) }}
          </span>
        </div>
      </div>

      <div class="task-process-ledger-row__controls">
        <label v-if="props.helpers.isManageable(props.proc)" class="task-process-ledger-row__priority">
          <span class="task-process-ledger-row__label">优先级</span>
          <select
            class="priority-select"
            :value="props.proc.priority || 'normal'"
            :style="props.priorityStyle(props.proc.priority || 'normal')"
            @change="props.handlers.changePriority(props.proc, $event.target.value)"
          >
            <option
              v-for="option in props.priorityOptions"
              :key="option.value"
              :value="option.value"
            >
              {{ option.label }}
            </option>
          </select>
        </label>

        <span
          v-else
          class="status-badge task-process-ledger-row__readonly"
          :class="props.helpers.getCategoryClass(props.proc)"
        >
          仅观测
        </span>

        <div v-if="props.helpers.isManageable(props.proc)" class="task-process-ledger-row__buttons">
          <button
            class="btn-tech"
            :disabled="props.handlers.isActionDisabled(props.proc, 'pause')"
            @click="props.handlers.doAction(props.proc, 'pause')"
          >
            暂停
          </button>
          <button
            class="btn-tech"
            :disabled="props.handlers.isActionDisabled(props.proc, 'resume')"
            @click="props.handlers.doAction(props.proc, 'resume')"
          >
            恢复
          </button>
          <button
            class="btn-tech btn-tech--danger"
            :disabled="props.handlers.isActionDisabled(props.proc, 'terminate')"
            @click="props.handlers.doAction(props.proc, 'terminate')"
          >
            终止
          </button>
        </div>
      </div>
    </div>

    <div class="task-process-ledger-row__summary">
      <div class="task-process-ledger-row__meta">
        <span>用户 {{ props.proc.username || '-' }}</span>
        <span :title="props.helpers.gpuMetricTitle(props.proc)">显存 {{ props.helpers.displayGpuMemory(props.proc) }}</span>
        <span :title="props.helpers.cpuMetricTitle(props.proc)">CPU {{ props.helpers.displayCpuPercent(props.proc) }}</span>
      </div>

      <div class="task-process-ledger-row__summary-copy" :title="props.helpers.getManageableReason(props.proc)">
        {{ props.helpers.getReasonSummary(props.proc) }}
      </div>

      <button type="button" class="btn-tech task-process-ledger-row__detail-toggle" @click="$emit('toggle-details')">
        {{ props.expanded ? '收起详情' : '查看详情' }}
      </button>
    </div>

    <div v-if="props.expanded" class="task-process-ledger-row__details">
      <div class="task-process-ledger-row__detail-field">
        <span class="task-process-ledger-row__label">治理说明</span>
        <div class="task-process-ledger-row__detail-text">{{ props.helpers.getManageableReason(props.proc) }}</div>
      </div>
      <div class="task-process-ledger-row__detail-field">
        <span class="task-process-ledger-row__label">命令</span>
        <div class="task-process-ledger-row__detail-text">{{ props.helpers.getCommandPreview(props.proc) }}</div>
      </div>
      <div class="task-process-ledger-row__detail-field">
        <span class="task-process-ledger-row__label">
          {{ props.helpers.isManageable(props.proc) ? '动作提示' : '只读原因' }}
        </span>
        <div class="task-process-ledger-row__detail-text">
          {{ props.helpers.isManageable(props.proc) ? props.helpers.getActionHint(props.proc) : props.helpers.getManageableReason(props.proc) }}
        </div>
      </div>
    </div>
  </article>
</template>

<style scoped>
.task-process-ledger-row {
  display: grid;
  gap: 12px;
  padding: 14px 16px;
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-color);
  background: rgba(255, 255, 255, 0.03);
  box-shadow: var(--shadow-card);
}

.task-process-ledger-row__head,
.task-process-ledger-row__summary {
  display: grid;
  gap: 10px;
}

.task-process-ledger-row__head {
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: start;
}

.task-process-ledger-row__identity,
.task-process-ledger-row__controls,
.task-process-ledger-row__meta,
.task-process-ledger-row__chips,
.task-process-ledger-row__buttons,
.task-process-ledger-row__details {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.task-process-ledger-row__identity,
.task-process-ledger-row__summary {
  min-width: 0;
}

.task-process-ledger-row__name {
  font-size: 0.98rem;
  line-height: 1.45;
  color: var(--text-primary);
  overflow-wrap: anywhere;
}

.task-process-ledger-row__chips,
.task-process-ledger-row__meta {
  font-size: 0.76rem;
  line-height: 1.5;
  color: var(--text-muted);
}

.task-process-ledger-row__controls {
  justify-content: flex-end;
}

.task-process-ledger-row__priority {
  display: grid;
  gap: 4px;
}

.task-process-ledger-row__label {
  font-size: 0.7rem;
  letter-spacing: 0.04em;
  color: var(--text-muted);
}

.priority-select {
  padding: 7px 10px;
  border-radius: 10px;
  border: 1px solid var(--border-color);
  background: rgba(255, 255, 255, 0.04);
  color: var(--text-primary);
  font-size: 0.8rem;
}

.task-process-ledger-row__summary {
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
}

.task-process-ledger-row__summary-copy,
.task-process-ledger-row__detail-text {
  font-size: 0.8rem;
  line-height: 1.6;
  color: var(--text-secondary);
  overflow-wrap: anywhere;
}

.task-process-ledger-row__detail-toggle {
  justify-self: end;
}

.task-process-ledger-row__details {
  display: grid;
  gap: 10px;
  padding-top: 10px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.task-process-ledger-row__detail-field {
  display: grid;
  gap: 4px;
}

.task-process-ledger-row__readonly {
  white-space: nowrap;
}

@media (max-width: 1180px) {
  .task-process-ledger-row__head,
  .task-process-ledger-row__summary {
    grid-template-columns: 1fr;
  }

  .task-process-ledger-row__controls {
    justify-content: flex-start;
  }

  .task-process-ledger-row__detail-toggle {
    justify-self: start;
  }
}

@media (max-width: 720px) {
  .task-process-ledger-row {
    padding: 14px;
  }

  .task-process-ledger-row__buttons {
    width: 100%;
  }
}
</style>
```

- [ ] **Step 5: Re-run the focused regressions**

Run: `python3 -m unittest tests.test_governance_workbench_structure tests.test_frontend_ui_structure -q`

Expected: PASS, including the new compact ledger structure assertion.

Run: `node --test frontend/src/lib/governanceTaskLedgerUi.test.js`

Expected: PASS, confirming one-row-open behavior and filtered-row auto-close logic.

- [ ] **Step 6: Commit the compact ledger UI**

```bash
git add frontend/src/components/tasks/TaskProcessLedger.vue frontend/src/components/tasks/TaskProcessLedgerRow.vue tests/test_governance_workbench_structure.py
git commit -m "feat: compact governance task ledger rows"
```
