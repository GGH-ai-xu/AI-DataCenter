# Dashboard 巡检总表卡 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把总览页 `巡检` 区域改造成 B2 巡检总表卡，去掉长条检查清单的首屏观感，同时保留真实巡检明细与展开能力。

**Architecture:** 先在 `dashboardPageModels` 中补齐总表卡所需的纯派生字段，让 Vue 模板只负责展示，不在模板里重复计算优先项、健康进度和事实卡警告态。然后重写 `DashboardHealthTab.vue` 的模板与样式，把结构收敛为“总表头 + 状态块 + 动作条 + 折叠明细”，并用结构测试锁死旧布局不会回流。

**Tech Stack:** Vue 3 SFC, Vite, Node `node:test`, Python `unittest`

---

## File Map

- Modify: `frontend/src/lib/dashboardPageModels.js` - 为巡检总表卡增加纯派生字段，如健康进度、主处理项、剩余优先项数量，以及 facts 卡的 `tone`
- Modify: `frontend/src/lib/dashboardPageModels.test.js` - 为新派生字段和等待巡检场景补回归测试
- Modify: `frontend/src/components/dashboard/DashboardHealthTab.vue` - 将现有 hero/长条列表/按钮改为单卡总表布局
- Modify: `tests/test_dashboard_workspace_structure.py` - 新增巡检总表卡的静态结构断言，防止回到旧的长条布局

### Task 1: Add Derived Dashboard Health Board State

**Files:**
- Modify: `frontend/src/lib/dashboardPageModels.test.js`
- Modify: `frontend/src/lib/dashboardPageModels.js`
- Test: `frontend/src/lib/dashboardPageModels.test.js`

- [ ] **Step 1: Write the failing model regression**

```js
test('buildDashboardHealthModel exposes board metadata for the B2 health card', () => {
  const waitingModel = buildDashboardHealthModel({
    importedLabel: '未导入 GPU',
    wsConnected: false,
    selfCheck: {},
  })

  assert.equal(waitingModel.healthProgressLabel, '等待巡检')
  assert.equal(waitingModel.totalCheckCount, 0)
  assert.equal(waitingModel.healthyCheckCount, 0)
  assert.equal(waitingModel.primaryCheck, null)
  assert.equal(waitingModel.remainingPriorityCount, 0)
  assert.equal(waitingModel.hasChecks, false)

  const model = buildDashboardHealthModel({
    importedLabel: '已导入 3 张卡',
    wsConnected: false,
    selfCheck: {
      summary: {
        title: '2 项异常',
        message: '其中 1 项影响实时采集',
      },
      checks: [
        { key: 'gpu-agent', label: 'GPU Agent', status: 'critical', detail: '实时采集失败' },
        { key: 'ws', label: 'WebSocket', status: 'warning', detail: '连接断开' },
        { key: 'llm', label: 'AI 助手', status: 'ok', detail: '正常' },
      ],
      ws_connections: 0,
      llm_available: false,
    },
  })

  assert.equal(model.healthProgressLabel, '健康 1 / 3')
  assert.equal(model.totalCheckCount, 3)
  assert.equal(model.healthyCheckCount, 1)
  assert.equal(model.primaryCheck?.key, 'gpu-agent')
  assert.equal(model.remainingPriorityCount, 1)
  assert.equal(model.hasChecks, true)
  assert.equal(model.factCards[1].tone, 'warning')
  assert.equal(model.factCards[2].tone, 'warning')
  assert.equal(model.factCards[3].tone, 'warning')
})
```

- [ ] **Step 2: Run the model test and confirm failure**

Run: `node --test frontend/src/lib/dashboardPageModels.test.js`

Expected: FAIL because `healthProgressLabel`, `totalCheckCount`, `healthyCheckCount`, `primaryCheck`, `remainingPriorityCount`, `hasChecks`, and `factCards[*].tone` do not exist yet.

- [ ] **Step 3: Implement the derived board fields in the model**

```js
function buildHealthProgressLabel(healthyCheckCount, totalCheckCount) {
  if (!totalCheckCount) {
    return '等待巡检'
  }
  return `健康 ${healthyCheckCount} / ${totalCheckCount}`
}

export function buildDashboardHealthModel(input = {}) {
  const checks = input.selfCheck?.checks || []
  const priorityChecks = checks.filter((item) => item.status === 'critical' || item.status === 'warning')
  const healthyChecks = checks.filter((item) => item.status === 'ok')
  const totalCheckCount = priorityChecks.length + healthyChecks.length
  const healthyCheckCount = healthyChecks.length
  const wsConnections = Number(input.selfCheck?.ws_connections || 0)
  const llmAvailable = Boolean(input.selfCheck?.llm_available)

  return {
    summary: input.selfCheck?.summary || { title: '等待巡检', message: '当前还没有巡检结果。' },
    factCards: [
      { label: '导入范围', value: input.importedLabel || '未导入 GPU', tone: 'neutral' },
      { label: '实时连接', value: input.wsConnected ? '在线' : '离线', tone: input.wsConnected ? 'ok' : 'warning' },
      { label: 'AI 助手', value: llmAvailable ? '已启用' : '未启用', tone: llmAvailable ? 'ok' : 'warning' },
      { label: 'WebSocket', value: `${wsConnections} 条`, tone: wsConnections > 0 ? 'ok' : 'warning' },
    ],
    priorityChecks,
    healthyChecks,
    totalCheckCount,
    healthyCheckCount,
    healthProgressLabel: buildHealthProgressLabel(healthyCheckCount, totalCheckCount),
    primaryCheck: priorityChecks[0] || null,
    remainingPriorityCount: Math.max(priorityChecks.length - 1, 0),
    hasChecks: totalCheckCount > 0,
  }
}
```

- [ ] **Step 4: Re-run the model regression**

Run: `node --test frontend/src/lib/dashboardPageModels.test.js`

Expected: PASS, including the new board metadata test.

- [ ] **Step 5: Commit the model groundwork**

```bash
git add frontend/src/lib/dashboardPageModels.js frontend/src/lib/dashboardPageModels.test.js
git commit -m "feat: add dashboard health board state"
```

### Task 2: Replace The Health Tab Long Strips With The B2 Board Card

**Files:**
- Modify: `tests/test_dashboard_workspace_structure.py`
- Modify: `frontend/src/components/dashboard/DashboardHealthTab.vue`
- Test: `tests/test_dashboard_workspace_structure.py`
- Test: `frontend/src/lib/dashboardPageModels.test.js`

- [ ] **Step 1: Write the failing structure regression**

```python
def test_dashboard_health_tab_uses_board_card_layout(self):
    text = (ROOT / 'frontend/src/components/dashboard/DashboardHealthTab.vue').read_text(encoding='utf-8')

    self.assertIn('dashboard-health__board-head', text)
    self.assertIn('dashboard-health__progress', text)
    self.assertIn('dashboard-health__action', text)
    self.assertIn('dashboard-health__toggle', text)
    self.assertIn('props.model.primaryCheck', text)
    self.assertIn('props.model.healthProgressLabel', text)
    self.assertIn('props.model.hasChecks', text)
    self.assertNotIn('dashboard-health__hero', text)
    self.assertNotIn('class="btn-tech"', text)
```

- [ ] **Step 2: Run the structure test and confirm failure**

Run: `python3 -m unittest tests.test_dashboard_workspace_structure -q`

Expected: FAIL because `DashboardHealthTab.vue` still contains `dashboard-health__hero`, the old check-list layout, and the `btn-tech` button.

- [ ] **Step 3: Rewrite `DashboardHealthTab.vue` as a single B2 board card**

```vue
<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  model: {
    type: Object,
    required: true,
  },
})

const showHealthyChecks = ref(false)
const displayedPriorityChecks = computed(() => props.model.priorityChecks || [])
const displayedHealthyChecks = computed(() => props.model.healthyChecks || [])
const actionCheck = computed(() => props.model.primaryCheck || null)
const actionEyebrow = computed(() => actionCheck.value ? '当前需处理项' : '当前无待处理项')
const actionBadgeLabel = computed(() => actionCheck.value ? actionCheck.value.label : '状态正常')
const actionBadgeClass = computed(() => {
  if (!actionCheck.value) {
    return 'status-badge--ok'
  }
  return actionCheck.value.status === 'critical' ? 'status-badge--critical' : 'status-badge--warning'
})
const actionTitle = computed(() => {
  if (actionCheck.value) {
    return actionCheck.value.detail
  }
  if (!props.model.hasChecks) {
    return '等待首轮巡检完成后再查看明细。'
  }
  return '当前巡检未发现 critical 或 warning 项。'
})
</script>

<template>
  <section class="tech-card dashboard-health">
    <div class="dashboard-health__board">
      <header class="dashboard-health__board-head">
        <div class="dashboard-health__summary">
          <div class="section-title">主体巡检</div>
          <strong>{{ props.model.summary.title }}</strong>
          <p>{{ props.model.summary.message }}</p>
        </div>
        <span class="status-badge status-badge--ok dashboard-health__progress">
          {{ props.model.healthProgressLabel }}
        </span>
      </header>

      <div class="dashboard-health__grid">
        <article
          v-for="item in props.model.factCards"
          :key="item.label"
          class="dashboard-health__item"
          :class="[
            item.tone === 'warning' ? 'dashboard-health__item--warning' : '',
            item.tone === 'ok' ? 'dashboard-health__item--ok' : '',
          ]"
        >
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
        </article>
      </div>

      <div class="dashboard-health__action">
        <div class="dashboard-health__action-copy">
          <span class="dashboard-health__eyebrow">{{ actionEyebrow }}</span>
          <div class="dashboard-health__action-main">
            <span class="status-badge" :class="actionBadgeClass">{{ actionBadgeLabel }}</span>
            <strong>{{ actionTitle }}</strong>
          </div>
          <p v-if="props.model.remainingPriorityCount > 0">
            另有 {{ props.model.remainingPriorityCount }} 项待关注。
          </p>
        </div>
        <button
          v-if="props.model.hasChecks"
          type="button"
          class="dashboard-health__toggle"
          @click="showHealthyChecks = !showHealthyChecks"
        >
          {{ showHealthyChecks ? '收起健康项' : '查看全部健康项' }}
        </button>
      </div>
    </div>

    <div v-if="showHealthyChecks && props.model.hasChecks" class="dashboard-health__details">
      <article
        v-for="item in displayedPriorityChecks"
        :key="item.key"
        class="dashboard-health__detail dashboard-health__detail--priority"
      >
        <span
          class="status-badge"
          :class="item.status === 'critical' ? 'status-badge--critical' : 'status-badge--warning'"
        >
          {{ item.label }}
        </span>
        <div>{{ item.detail }}</div>
      </article>
      <article
        v-for="item in displayedHealthyChecks"
        :key="item.key"
        class="dashboard-health__detail"
      >
        <span class="status-badge status-badge--ok">{{ item.label }}</span>
        <div>{{ item.detail }}</div>
      </article>
    </div>
  </section>
</template>

<style scoped>
.dashboard-health,
.dashboard-health__board,
.dashboard-health__summary,
.dashboard-health__grid,
.dashboard-health__details {
  display: grid;
  gap: 16px;
}

.dashboard-health {
  padding: 22px 24px;
}

.dashboard-health__board {
  gap: 18px;
  padding: 20px;
  border-radius: 24px;
  border: 1px solid var(--console-border, rgba(255, 255, 255, 0.08));
  background:
    linear-gradient(145deg, rgba(14, 20, 29, 0.94), rgba(10, 15, 22, 0.9)),
    var(--console-surface, rgba(255, 255, 255, 0.04));
}

.dashboard-health__board-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.dashboard-health__summary strong,
.dashboard-health__item strong,
.dashboard-health__action-main strong {
  font-size: 1.08rem;
  color: var(--console-text, var(--text-primary));
}

.dashboard-health__summary p,
.dashboard-health__action-copy p,
.dashboard-health__detail div {
  font-size: 0.9rem;
  line-height: 1.7;
  color: var(--console-text-secondary, var(--text-secondary));
}

.dashboard-health__progress {
  white-space: nowrap;
}

.dashboard-health__grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.dashboard-health__item,
.dashboard-health__action,
.dashboard-health__detail {
  padding: 16px;
  border-radius: 18px;
  border: 1px solid var(--console-border, rgba(255, 255, 255, 0.08));
}

.dashboard-health__item {
  background: rgba(255, 255, 255, 0.03);
}

.dashboard-health__item--warning {
  background: rgba(242, 207, 123, 0.1);
  border-color: rgba(242, 207, 123, 0.2);
}

.dashboard-health__item--ok {
  background: rgba(108, 210, 167, 0.08);
}

.dashboard-health__item span,
.dashboard-health__eyebrow {
  font-size: 0.76rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--console-text-muted, var(--text-muted));
}

.dashboard-health__action {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  background: rgba(255, 255, 255, 0.025);
}

.dashboard-health__action-copy,
.dashboard-health__action-main {
  display: grid;
  gap: 10px;
}

.dashboard-health__toggle {
  border: 0;
  border-radius: 14px;
  padding: 12px 18px;
  color: var(--console-text, var(--text-primary));
  background: rgba(74, 101, 255, 0.16);
  cursor: pointer;
}

.dashboard-health__details {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.dashboard-health__detail {
  background: var(--console-surface, rgba(255, 255, 255, 0.04));
}

.dashboard-health__detail--priority {
  border-color: rgba(242, 207, 123, 0.2);
}

@media (max-width: 980px) {
  .dashboard-health__board-head,
  .dashboard-health__action {
    grid-template-columns: 1fr;
    display: grid;
  }

  .dashboard-health__grid,
  .dashboard-health__details {
    grid-template-columns: 1fr;
  }
}
</style>
```

- [ ] **Step 4: Re-run the focused regressions**

Run: `python3 -m unittest tests.test_dashboard_workspace_structure tests.test_frontend_ui_structure -q`

Expected: PASS, including the new dashboard health board structure assertion.

Run: `node --test frontend/src/lib/dashboardPageModels.test.js`

Expected: PASS, confirming the component still aligns with the new model shape.

- [ ] **Step 5: Commit the B2 board card UI**

```bash
git add tests/test_dashboard_workspace_structure.py frontend/src/components/dashboard/DashboardHealthTab.vue
git commit -m "feat: redesign dashboard health tab as board card"
```
