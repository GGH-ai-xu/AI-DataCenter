# Left Workbench Tabs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert all six major workbench pages from top tabs to a shared left-side sticky workbench navigation on desktop, with a top horizontal tab strip on mobile.

**Architecture:** Keep `WorkspaceTabs` as the only shared tab component, add a small `orientation` API to it, and introduce shared layout utility classes in `frontend/src/style.css`. Each page keeps its own `activeTab` and content blocks, but wraps content in a common `workspace-nav-layout` skeleton so the left rail is visually and behaviorally consistent.

**Tech Stack:** Vue 3 SFCs, shared global CSS in `frontend/src/style.css`, Python `unittest` regression tests, Vite build run from the Windows environment.

---

## File Map

**Modify:**
- `frontend/src/components/workspace/WorkspaceTabs.vue`
  Purpose: add a vertical orientation mode while keeping the existing `v-model` API.
- `frontend/src/style.css`
  Purpose: add shared two-column workbench layout classes, sticky left-nav behavior, and responsive mobile fallback.
- `frontend/src/views/Dashboard.vue`
  Purpose: move workbench navigation into a left rail for `overview / access / live`.
- `frontend/src/views/Scheduler.vue`
  Purpose: move workbench navigation into a left rail for `control / results / audit`.
- `frontend/src/views/MonitorCenter.vue`
  Purpose: move workbench navigation into a left rail for `system / training / users / timeline`.
- `frontend/src/views/TaskManager.vue`
  Purpose: move workbench navigation into a left rail for task governance sections.
- `frontend/src/views/EnergyOptimization.vue`
  Purpose: move workbench navigation into a left rail for energy analysis sections.
- `frontend/src/views/AIAssistant.vue`
  Purpose: move workbench navigation into a left rail for `control / chat / model`.
- `tests/test_frontend_ui_structure.py`
  Purpose: add regression coverage for shared left-workbench layout and shared vertical-tab usage.

---

### Task 1: Add Failing Regression Tests For Left Workbench Layout

**Files:**
- Modify: `tests/test_frontend_ui_structure.py`
- Test: `tests/test_frontend_ui_structure.py`

- [ ] **Step 1: Write the failing tests**

Add these test cases near the existing frontend structure assertions:

```python
    def test_workspace_tabs_support_vertical_orientation(self):
        text = (ROOT / "frontend/src/components/workspace/WorkspaceTabs.vue").read_text(encoding="utf-8")
        self.assertIn("orientation", text)
        self.assertIn("workspace-tabs--vertical", text)

    def test_workbench_pages_use_left_nav_layout(self):
        for rel in [
            "frontend/src/views/Dashboard.vue",
            "frontend/src/views/Scheduler.vue",
            "frontend/src/views/MonitorCenter.vue",
            "frontend/src/views/TaskManager.vue",
            "frontend/src/views/EnergyOptimization.vue",
            "frontend/src/views/AIAssistant.vue",
        ]:
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertIn("workspace-nav-layout", text, rel)
            self.assertIn("workspace-nav-layout__nav", text, rel)
            self.assertIn("workspace-nav-layout__content", text, rel)
            self.assertIn('orientation="vertical"', text, rel)

    def test_shared_style_defines_sticky_workbench_nav(self):
        text = (ROOT / "frontend/src/style.css").read_text(encoding="utf-8")
        self.assertIn(".workspace-nav-layout", text)
        self.assertIn(".workspace-nav-layout__nav", text)
        self.assertIn("position: sticky", text)
        self.assertIn(".workspace-tabs--vertical", text)
```

- [ ] **Step 2: Run the test file to verify it fails**

Run:

```bash
cmd.exe /c "cd /d E:\Code\AI-DataCenter && py -3 -m unittest tests.test_frontend_ui_structure -v"
```

Expected:

- FAIL on missing `orientation` support in `WorkspaceTabs.vue`
- FAIL on missing `workspace-nav-layout` wrappers in the six views
- FAIL on missing sticky left-nav style in `frontend/src/style.css`

- [ ] **Step 3: Commit the red tests**

```bash
git add tests/test_frontend_ui_structure.py
git commit -m "test: add left workbench layout regression coverage"
```

---

### Task 2: Implement Shared Vertical Tabs And Sticky Workbench Layout

**Files:**
- Modify: `frontend/src/components/workspace/WorkspaceTabs.vue`
- Modify: `frontend/src/style.css`
- Test: `tests/test_frontend_ui_structure.py`

- [ ] **Step 1: Extend `WorkspaceTabs.vue` with an orientation prop**

Update the component to support a vertical modifier class:

```vue
<script setup>
import { computed } from 'vue'

const props = defineProps({
  items: {
    type: Array,
    required: true,
  },
  modelValue: {
    type: String,
    required: true,
  },
  orientation: {
    type: String,
    default: 'horizontal',
  },
})

const emit = defineEmits(['update:modelValue'])

const rootClass = computed(() => ({
  'workspace-tabs--vertical': props.orientation === 'vertical',
}))
</script>

<template>
  <div class="workspace-tabs" :class="rootClass">
    <button
      v-for="item in items"
      :key="item.key"
      type="button"
      class="workspace-tab"
      :class="{ 'workspace-tab--active': modelValue === item.key }"
      @click="emit('update:modelValue', item.key)"
    >
      <span class="workspace-tab__label">{{ item.label }}</span>
      <span v-if="item.desc" class="workspace-tab__desc">{{ item.desc }}</span>
    </button>
  </div>
</template>
```

- [ ] **Step 2: Add shared workbench layout classes in `frontend/src/style.css`**

Insert the new layout and vertical-tab styles close to the existing `.workspace-tabs` block:

```css
.workspace-nav-layout {
  display: grid;
  grid-template-columns: 248px minmax(0, 1fr);
  gap: 20px;
  align-items: start;
  margin: 18px 0 22px;
}

.workspace-nav-layout__nav {
  position: sticky;
  top: 20px;
  align-self: start;
}

.workspace-nav-layout__content {
  min-width: 0;
}

.workspace-tabs--vertical {
  display: grid;
  gap: 10px;
  margin: 0;
}

.workspace-tabs--vertical .workspace-tab {
  min-width: 0;
  width: 100%;
}

.workspace-tabs--vertical .workspace-tab__label,
.workspace-tabs--vertical .workspace-tab__desc {
  white-space: normal;
  overflow-wrap: anywhere;
  word-break: break-word;
}

@media (max-width: 980px) {
  .workspace-nav-layout {
    grid-template-columns: 1fr;
  }

  .workspace-nav-layout__nav {
    position: static;
  }

  .workspace-tabs--vertical {
    display: flex;
    overflow-x: auto;
    padding-bottom: 2px;
  }

  .workspace-tabs--vertical .workspace-tab {
    min-width: 170px;
    flex: 0 0 auto;
  }
}
```

- [ ] **Step 3: Run the structure tests to verify shared layer passes**

Run:

```bash
cmd.exe /c "cd /d E:\Code\AI-DataCenter && py -3 -m unittest tests.test_frontend_ui_structure -v"
```

Expected:

- shared-component and style assertions now pass
- page-level left-layout assertions still fail until the views are migrated

- [ ] **Step 4: Commit the shared layer**

```bash
git add frontend/src/components/workspace/WorkspaceTabs.vue frontend/src/style.css tests/test_frontend_ui_structure.py
git commit -m "feat: add shared left workbench tab layout"
```

---

### Task 3: Migrate Dashboard, Scheduler, And MonitorCenter To The Shared Left Rail

**Files:**
- Modify: `frontend/src/views/Dashboard.vue`
- Modify: `frontend/src/views/Scheduler.vue`
- Modify: `frontend/src/views/MonitorCenter.vue`
- Test: `tests/test_frontend_ui_structure.py`

- [ ] **Step 1: Wrap each page with the common nav/content skeleton**

For each page, replace the top-level `WorkspaceTabs` placement with this pattern:

```vue
<div class="workspace-nav-layout">
  <aside class="workspace-nav-layout__nav">
    <WorkspaceTabs
      v-model="activeTab"
      :items="dashboardTabs"
      orientation="vertical"
    />
  </aside>

  <section class="workspace-nav-layout__content">
    <template v-if="activeTab === 'overview'">
      <!-- existing overview content -->
    </template>
    <template v-else-if="activeTab === 'access'">
      <!-- existing access content -->
    </template>
    <template v-else>
      <!-- existing live content -->
    </template>
  </section>
</div>
```

Use the same structure in:

- `Dashboard.vue` with `dashboardTabs`
- `Scheduler.vue` with `schedulerTabs`
- `MonitorCenter.vue` with `monitorTabs`

- [ ] **Step 2: Flatten each page so only the right content area switches**

When moving content into `workspace-nav-layout__content`, keep these rules:

```vue
<!-- good: nav stays fixed, content changes inside the content column -->
<section class="workspace-nav-layout__content">
  <div v-if="activeTab === 'control'" class="sched-grid">
    ...
  </div>
  <div v-else-if="activeTab === 'results'" class="sched-grid">
    ...
  </div>
  <div v-else class="sched-grid">
    ...
  </div>
</section>
```

Do not move `WorkspaceSummary` into the right column. It must stay above the shared workbench layout.

- [ ] **Step 3: Run tests after migrating the first three pages**

Run:

```bash
cmd.exe /c "cd /d E:\Code\AI-DataCenter && py -3 -m unittest tests.test_frontend_ui_structure -v"
```

Expected:

- the three migrated pages now satisfy the left-layout assertions
- the test file still fails until the remaining three pages are migrated

- [ ] **Step 4: Commit the first page batch**

```bash
git add frontend/src/views/Dashboard.vue frontend/src/views/Scheduler.vue frontend/src/views/MonitorCenter.vue
git commit -m "refactor: move governance pages to left workbench nav"
```

---

### Task 4: Migrate TaskManager, EnergyOptimization, And AIAssistant To The Shared Left Rail

**Files:**
- Modify: `frontend/src/views/TaskManager.vue`
- Modify: `frontend/src/views/EnergyOptimization.vue`
- Modify: `frontend/src/views/AIAssistant.vue`
- Test: `tests/test_frontend_ui_structure.py`

- [ ] **Step 1: Apply the same layout skeleton to the remaining pages**

Use the identical shell:

```vue
<div class="workspace-nav-layout">
  <aside class="workspace-nav-layout__nav">
    <WorkspaceTabs
      v-model="activeTab"
      :items="taskTabs"
      orientation="vertical"
    />
  </aside>

  <section class="workspace-nav-layout__content">
    <!-- existing tab content blocks -->
  </section>
</div>
```

Map the page/tab sets like this:

- `TaskManager.vue` -> `taskTabs`
- `EnergyOptimization.vue` -> `energyTabs`
- `AIAssistant.vue` -> `assistantTabs`

- [ ] **Step 2: Preserve each page’s current business structure inside the content column**

Keep the existing content sections, but move them under the shared content wrapper:

```vue
<section class="workspace-nav-layout__content">
  <section v-if="activeTab === 'control'" class="tech-card control-console">
    ...
  </section>

  <section v-else-if="activeTab === 'chat'" class="ai-container tech-card">
    ...
  </section>

  <aside v-else class="ai-config tech-card">
    ...
  </aside>
</section>
```

Do not change:

- current tab keys
- page business logic
- the existing summary cards
- the previously completed de-duplication decisions

- [ ] **Step 3: Run the focused structure tests**

Run:

```bash
cmd.exe /c "cd /d E:\Code\AI-DataCenter && py -3 -m unittest tests.test_frontend_ui_structure -v"
```

Expected:

- all structure tests pass

- [ ] **Step 4: Commit the second page batch**

```bash
git add frontend/src/views/TaskManager.vue frontend/src/views/EnergyOptimization.vue frontend/src/views/AIAssistant.vue
git commit -m "refactor: move analysis pages to left workbench nav"
```

---

### Task 5: Run Full Windows Verification And Clean Up Any Layout Regressions

**Files:**
- Modify: `frontend/src/style.css` (only if verification reveals spacing/sticky/mobile issues)
- Test: `tests/test_frontend_ui_structure.py`

- [ ] **Step 1: Run the full backend/frontend regression suite from the Windows environment**

Run:

```bash
cmd.exe /c "cd /d E:\Code\AI-DataCenter && py -3 -m unittest discover -s tests -p test_*.py"
cmd.exe /c "cd /d E:\Code\AI-DataCenter\frontend && npm run build"
```

Expected:

- Python suite: `OK`
- Vite build: success with no syntax errors

- [ ] **Step 2: If layout issues appear, apply only the minimal shared-style fix**

Allowed adjustments are limited to shared layout rules like:

```css
.workspace-nav-layout__nav {
  top: 16px;
}

.workspace-tabs--vertical .workspace-tab {
  padding: 14px 16px;
}

@media (max-width: 980px) {
  .workspace-tabs--vertical {
    gap: 12px;
  }
}
```

Do not introduce per-page special cases unless a single page has a genuine structural need.

- [ ] **Step 3: Re-run verification after any CSS adjustment**

Run:

```bash
cmd.exe /c "cd /d E:\Code\AI-DataCenter && py -3 -m unittest discover -s tests -p test_*.py"
cmd.exe /c "cd /d E:\Code\AI-DataCenter\frontend && npm run build"
```

Expected:

- same green results as Step 1

- [ ] **Step 4: Commit the final verified state**

```bash
git add frontend/src/components/workspace/WorkspaceTabs.vue frontend/src/style.css frontend/src/views/Dashboard.vue frontend/src/views/Scheduler.vue frontend/src/views/MonitorCenter.vue frontend/src/views/TaskManager.vue frontend/src/views/EnergyOptimization.vue frontend/src/views/AIAssistant.vue tests/test_frontend_ui_structure.py
git commit -m "feat: unify workbench pages with left sticky tabs"
```
