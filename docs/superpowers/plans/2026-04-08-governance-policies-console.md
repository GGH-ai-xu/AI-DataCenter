# Governance Policies Console Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the `策略治理` page into a budget-first, switch-first control console with graphical action cards, visible pending state, and inline risk/feedback without changing backend behavior.

**Architecture:** Keep `frontend/src/views/GovernancePoliciesView.vue` as the API-facing coordinator, extract pure draft/pending-state logic into a new helper module, and split the current large workspace UI into focused visual components for the budget console, action dock, advanced policy panel, and per-user rule cards. Keep real execution semantics unchanged: switches edit local draft state, action cards commit, and failures stay explicit.

**Tech Stack:** Vue 3 SFCs, Pinia store state, existing FastAPI-backed REST endpoints, `node:test`, Python `unittest` structure checks.

---

### Task 1: Define The Pending-State Contract

**Files:**
- Create: `frontend/src/lib/governancePoliciesConsoleState.js`
- Create: `frontend/src/lib/governancePoliciesConsoleState.test.js`

- [ ] **Step 1: Write the failing helper tests**

```js
// frontend/src/lib/governancePoliciesConsoleState.test.js
import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildDraftCardState,
  buildExecutionBannerModel,
} from './governancePoliciesConsoleState.js'

test('buildDraftCardState marks budget edits as pending', () => {
  const state = buildDraftCardState({
    kind: 'budget',
    current: { enabled: true, total_power_budget: 1200 },
    draft: { enabled: false, total_power_budget: 1400 },
  })

  assert.equal(state.pending, true)
  assert.equal(state.badgeLabel, '待应用')
  assert.equal(state.actionLabel, '应用预算修改')
})

test('buildDraftCardState keeps untouched carbon card synced', () => {
  const state = buildDraftCardState({
    kind: 'carbon',
    current: { enabled: false, daily_budget_kg: 50 },
    draft: { enabled: false, daily_budget_kg: 50 },
  })

  assert.equal(state.pending, false)
  assert.equal(state.badgeLabel, '已同步')
  assert.equal(state.actionTone, 'quiet')
})

test('buildExecutionBannerModel exposes inline warning for real execution without risk ack', () => {
  const banner = buildExecutionBannerModel({
    actionLabel: '执行一次调度',
    isReal: true,
    riskAcknowledged: false,
    reversible: true,
  })

  assert.equal(banner.tone, 'warning')
  assert.match(banner.detail, /执行一次调度/)
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `node --test frontend/src/lib/governancePoliciesConsoleState.test.js`

Expected: FAIL with `ERR_MODULE_NOT_FOUND` for `governancePoliciesConsoleState.js`.

- [ ] **Step 3: Write the minimal pure helper implementation**

```js
// frontend/src/lib/governancePoliciesConsoleState.js
const KIND_CONFIG = Object.freeze({
  budget: {
    valueKey: 'total_power_budget',
    actionLabel: '应用预算修改',
  },
  carbon: {
    valueKey: 'daily_budget_kg',
    actionLabel: '应用碳预算',
  },
})

function normalizeNumber(value) {
  return Number(value || 0)
}

export function buildDraftCardState({ kind, current = {}, draft = {} }) {
  const config = KIND_CONFIG[kind]
  const valueKey = config.valueKey
  const pending = Boolean(current.enabled) !== Boolean(draft.enabled)
    || normalizeNumber(current[valueKey]) !== normalizeNumber(draft[valueKey])

  return {
    pending,
    badgeLabel: pending ? '待应用' : '已同步',
    badgeTone: pending ? 'pending' : 'ok',
    actionLabel: config.actionLabel,
    actionTone: pending ? 'primary' : 'quiet',
  }
}

export function buildExecutionBannerModel({
  actionLabel = '',
  isReal = false,
  riskAcknowledged = false,
  reversible = false,
} = {}) {
  if (!isReal || riskAcknowledged) {
    return { tone: 'ok', detail: `${actionLabel}可直接执行。`, confirmRequired: false }
  }

  return {
    tone: reversible ? 'warning' : 'critical',
    detail: `${actionLabel}前请先确认风险。`,
    confirmRequired: !reversible,
  }
}
```

- [ ] **Step 4: Re-run tests to verify green**

Run: `node --test frontend/src/lib/governancePoliciesConsoleState.test.js`

Expected: `pass 3`, `fail 0`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/governancePoliciesConsoleState.js frontend/src/lib/governancePoliciesConsoleState.test.js
git commit -m "test: define governance policies console state contract"
```

### Task 2: Split The Policies Workspace Into A Budget Console And Action Dock

**Files:**
- Create: `frontend/src/components/governance/PolicyBudgetConsole.vue`
- Create: `frontend/src/components/governance/PolicyActionDock.vue`
- Create: `frontend/src/components/governance/PolicyAdvancedPanel.vue`
- Modify: `frontend/src/components/governance/GovernancePoliciesWorkspace.vue`
- Modify: `frontend/src/views/GovernancePoliciesView.vue`
- Test: `tests/test_governance_workbench_structure.py`
- Test: `tests/test_frontend_ui_structure.py`

- [ ] **Step 1: Extend the failing structure tests for the new layout**

```python
# tests/test_governance_workbench_structure.py
def test_policies_workspace_keeps_budget_first_and_action_dock_split(self):
    text = (ROOT / "frontend/src/components/governance/GovernancePoliciesWorkspace.vue").read_text(encoding="utf-8")

    self.assertIn("PolicyBudgetConsole", text)
    self.assertIn("PolicyActionDock", text)
    self.assertIn("budget-card-state", text)
    self.assertIn("carbon-card-state", text)

def test_policies_view_uses_inline_execution_banner(self):
    text = (ROOT / "frontend/src/views/GovernancePoliciesView.vue").read_text(encoding="utf-8")

    self.assertIn("buildExecutionBannerModel", text)
    self.assertIn("executionBanner", text)
```

- [ ] **Step 2: Run the structure tests and watch them fail**

Run: `python3 -m unittest tests.test_governance_workbench_structure tests.test_frontend_ui_structure -q`

Expected: FAIL because `PolicyBudgetConsole.vue`, `PolicyActionDock.vue`, and the new computed names do not exist yet.

- [ ] **Step 3: Implement the view coordinator and visual split**

```js
// frontend/src/views/GovernancePoliciesView.vue (script excerpt)
import PolicyBudgetConsole from '../components/governance/PolicyBudgetConsole.vue'
import PolicyActionDock from '../components/governance/PolicyActionDock.vue'
import { buildDraftCardState, buildExecutionBannerModel } from '../lib/governancePoliciesConsoleState.js'

const budgetDraft = ref({ enabled: false, total_power_budget: 1200 })
const carbonDraft = ref({ enabled: false, daily_budget_kg: 50 })

const budgetCardState = computed(() => buildDraftCardState({
  kind: 'budget',
  current: budget.value,
  draft: budgetDraft.value,
}))

const carbonCardState = computed(() => buildDraftCardState({
  kind: 'carbon',
  current: carbonBudget.value,
  draft: carbonDraft.value,
}))

const executionBanner = computed(() => buildExecutionBannerModel({
  actionLabel: '执行一次调度',
  isReal: props.execution.isReal,
  riskAcknowledged: props.execution.riskAcknowledged,
  reversible: true,
}))
```

```vue
<!-- frontend/src/components/governance/GovernancePoliciesWorkspace.vue -->
<script setup>
import PolicyBudgetConsole from './PolicyBudgetConsole.vue'
import PolicyActionDock from './PolicyActionDock.vue'
import PolicyAdvancedPanel from './PolicyAdvancedPanel.vue'

const props = defineProps({
  budget: Object,
  budgetDraft: Object,
  budgetCardState: Object,
  carbonBudget: Object,
  carbonDraft: Object,
  carbonCardState: Object,
  autoEnabled: Boolean,
  executionBanner: Object,
  scheduleResult: Object,
  showAdvanced: Boolean,
  rulesUsers: Array,
  gpuTargets: Array,
  powerInputs: Object,
  handlers: Object,
})

const emit = defineEmits(['toggle-advanced'])
</script>

<template>
  <div class="policies-console-layout">
    <PolicyBudgetConsole
      :budget="props.budget"
      :budget-draft="props.budgetDraft"
      :budget-card-state="props.budgetCardState"
      :carbon-budget="props.carbonBudget"
      :carbon-draft="props.carbonDraft"
      :carbon-card-state="props.carbonCardState"
      :handlers="props.handlers"
    />

    <PolicyActionDock
      :auto-enabled="props.autoEnabled"
      :execution-banner="props.executionBanner"
      :schedule-result="props.scheduleResult"
      :show-advanced="props.showAdvanced"
      :handlers="props.handlers"
      @toggle-advanced="emit('toggle-advanced')"
    />

    <PolicyAdvancedPanel
      v-if="props.showAdvanced"
      :rules-users="props.rulesUsers"
      :gpu-targets="props.gpuTargets"
      :power-inputs="props.powerInputs"
      :handlers="props.handlers"
    />
  </div>
</template>
```

- [ ] **Step 4: Run tests to verify the split works**

Run: `python3 -m unittest tests.test_governance_workbench_structure tests.test_frontend_ui_structure -q`

Expected: PASS for the new structure assertions and no regressions in the existing governance shell checks.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/GovernancePoliciesView.vue frontend/src/components/governance/GovernancePoliciesWorkspace.vue frontend/src/components/governance/PolicyBudgetConsole.vue frontend/src/components/governance/PolicyActionDock.vue frontend/src/components/governance/PolicyAdvancedPanel.vue tests/test_governance_workbench_structure.py tests/test_frontend_ui_structure.py
git commit -m "feat: split governance policies into console and dock"
```

### Task 3: Build The Advanced Policy Panel And Split User Rule Cards

**Files:**
- Create: `frontend/src/components/tasks/UserRuleCard.vue`
- Modify: `frontend/src/components/governance/PolicyAdvancedPanel.vue`
- Modify: `frontend/src/components/tasks/UserRulesGrid.vue`
- Modify: `tests/test_governance_workbench_structure.py`
- Modify: `tests/test_frontend_ui_structure.py`

- [ ] **Step 1: Add failing structure tests for the advanced panel split**

```python
# tests/test_governance_workbench_structure.py
def test_advanced_panel_stays_folded_outside_budget_console(self):
    text = (ROOT / "frontend/src/components/governance/PolicyAdvancedPanel.vue").read_text(encoding="utf-8")

    self.assertIn("GPU 限功率", text)
    self.assertIn("用户额度规则", text)
    self.assertNotIn("执行一次调度", text)

def test_user_rules_grid_renders_rule_cards(self):
    text = (ROOT / "frontend/src/components/tasks/UserRulesGrid.vue").read_text(encoding="utf-8")

    self.assertIn("UserRuleCard", text)
    self.assertIn("rules-grid", text)
```

```python
# tests/test_frontend_ui_structure.py
def test_user_rule_cards_keep_graphical_action_buttons(self):
    text = (ROOT / "frontend/src/components/tasks/UserRuleCard.vue").read_text(encoding="utf-8")

    self.assertIn("action-card", text)
    self.assertIn("编辑规则", text)
    self.assertIn("恢复默认", text)
```

- [ ] **Step 2: Run tests to verify failure**

Run: `python3 -m unittest tests.test_governance_workbench_structure tests.test_frontend_ui_structure -q`

Expected: FAIL because `UserRuleCard.vue` does not exist yet and `PolicyAdvancedPanel.vue` still lacks the final advanced control markers.

- [ ] **Step 3: Implement the advanced panel and card split**

```vue
<!-- frontend/src/components/governance/PolicyAdvancedPanel.vue -->
<script setup>
import UserRulesGrid from '../tasks/UserRulesGrid.vue'

const props = defineProps({
  rulesUsers: Array,
  gpuTargets: Array,
  powerInputs: Object,
  handlers: Object,
})
</script>

<template>
  <section class="tech-card policy-advanced-panel">
    <div class="policy-advanced-panel__section-title">GPU 限功率</div>
    <div v-for="gpuIndex in props.gpuTargets" :key="gpuIndex" class="policy-advanced-panel__gpu-line">
      <span>GPU {{ gpuIndex }}</span>
      <input v-model="props.powerInputs[gpuIndex]" type="number" class="task-input" />
      <button type="button" class="action-card" @click="props.handlers.setPower(gpuIndex)">写入限功率</button>
    </div>

    <UserRulesGrid :users="props.rulesUsers" @save="props.handlers.saveRule" @reset="props.handlers.resetRule" />
  </section>
</template>
```

```vue
<!-- frontend/src/components/tasks/UserRulesGrid.vue -->
<script setup>
import UserRuleCard from './UserRuleCard.vue'

const props = defineProps({
  users: { type: Array, default: () => [] },
})

const emit = defineEmits(['save', 'reset'])
</script>

<template>
  <section v-if="props.users.length" class="tech-card rules-panel">
    <div class="rules-grid">
      <UserRuleCard
        v-for="user in props.users"
        :key="user.username"
        :user="user"
        @save="emit('save', $event)"
        @reset="emit('reset', $event)"
      />
    </div>
  </section>
</template>
```

- [ ] **Step 4: Run tests to verify the split passes**

Run: `python3 -m unittest tests.test_governance_workbench_structure tests.test_frontend_ui_structure -q`

Expected: PASS, with advanced controls now isolated from the budget console and user rules moved into per-user cards.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/governance/PolicyAdvancedPanel.vue frontend/src/components/tasks/UserRuleCard.vue frontend/src/components/tasks/UserRulesGrid.vue tests/test_governance_workbench_structure.py tests/test_frontend_ui_structure.py
git commit -m "feat: refine governance advanced policy cards"
```

### Task 4: Polish Visual States, Inline Feedback, And Final Verification

**Files:**
- Modify: `frontend/src/components/governance/PolicyBudgetConsole.vue`
- Modify: `frontend/src/components/governance/PolicyActionDock.vue`
- Modify: `frontend/src/components/governance/PolicyAdvancedPanel.vue`
- Modify: `frontend/src/style.css`
- Test: `tests/test_frontend_ui_structure.py`
- Test: `tests/test_frontend_performance_structure.py`
- Test: `frontend/src/lib/governancePoliciesConsoleState.test.js`

- [ ] **Step 1: Add the last failing assertions for visual state language**

```python
# tests/test_frontend_ui_structure.py
def test_policy_console_exposes_pending_badges_and_inline_risk_banner(self):
    text = (ROOT / "frontend/src/components/governance/PolicyBudgetConsole.vue").read_text(encoding="utf-8")
    dock_text = (ROOT / "frontend/src/components/governance/PolicyActionDock.vue").read_text(encoding="utf-8")

    self.assertIn("待应用", text)
    self.assertIn("policy-budget-console__badge", text)
    self.assertIn("execution-banner", dock_text)
    self.assertIn("execution-banner--", dock_text)
```

```python
# tests/test_frontend_performance_structure.py
def test_policies_console_uses_component_local_layout_instead_of_growing_global_shell(self):
    text = (ROOT / "frontend/src/components/governance/PolicyBudgetConsole.vue").read_text(encoding="utf-8")

    self.assertIn("<style scoped>", text)
    self.assertIn("policy-budget-console", text)
```

- [ ] **Step 2: Run tests to verify red**

Run: `python3 -m unittest tests.test_frontend_ui_structure tests.test_frontend_performance_structure -q`

Expected: FAIL until the pending badge, inline risk banner, and final scoped CSS hooks are in place.

- [ ] **Step 3: Implement the final visual polish**

```vue
<!-- frontend/src/components/governance/PolicyBudgetConsole.vue (template excerpt) -->
<div class="policy-budget-console__card" :class="{ 'policy-budget-console__card--pending': props.budgetCardState.pending }">
  <div class="policy-budget-console__card-head">
    <span class="policy-budget-console__label">总功率预算</span>
    <span class="policy-budget-console__badge" :class="`policy-budget-console__badge--${props.budgetCardState.badgeTone}`">
      {{ props.budgetCardState.badgeLabel }}
    </span>
  </div>
  <button type="button" class="action-card" :class="{ 'action-card--primary': props.budgetCardState.pending }" @click="props.handlers.saveBudget">
    应用预算修改
  </button>
</div>
```

```vue
<!-- frontend/src/components/governance/PolicyActionDock.vue (template excerpt) -->
<div class="execution-banner" :class="`execution-banner--${props.executionBanner.tone}`">
  <strong>真实执行提示</strong>
  <span>{{ props.executionBanner.detail }}</span>
</div>
```

```css
/* frontend/src/style.css */
:root {
  --policy-ok: #4ed4aa;
  --policy-warn: #f4b95d;
  --policy-pending: #8aa0ff;
}
```

- [ ] **Step 4: Run the full verification set**

Run: `node --test frontend/src/lib/governancePoliciesConsoleState.test.js frontend/src/lib/governanceLoaders.test.js frontend/src/lib/governancePageModels.test.js frontend/src/lib/governancePolicyState.test.js frontend/src/lib/governanceReviewModel.test.js frontend/src/lib/governanceTaskLedger.test.js frontend/src/stores/app.test.js frontend/src/lib/routeAccess.test.js`

Expected: `pass 8`, `fail 0`.

Run: `python3 -m unittest tests.test_governance_workbench_structure tests.test_frontend_ui_structure tests.test_frontend_performance_structure -q`

Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/governance/PolicyBudgetConsole.vue frontend/src/components/governance/PolicyActionDock.vue frontend/src/components/governance/PolicyAdvancedPanel.vue frontend/src/components/tasks/UserRuleCard.vue frontend/src/components/tasks/UserRulesGrid.vue frontend/src/views/GovernancePoliciesView.vue frontend/src/components/governance/GovernancePoliciesWorkspace.vue frontend/src/lib/governancePoliciesConsoleState.js frontend/src/lib/governancePoliciesConsoleState.test.js frontend/src/style.css tests/test_governance_workbench_structure.py tests/test_frontend_ui_structure.py tests/test_frontend_performance_structure.py
git commit -m "feat: finish governance policies control console"
```
