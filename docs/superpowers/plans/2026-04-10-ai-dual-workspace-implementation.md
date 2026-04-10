# AI Dual Workspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让当前智能工作台与远端 graph 版本同时具备真实可访问、可运行的入口，并修复 merge 过程中引入的 AI workbench 后端回归。

**Architecture:** 先修复 merge 后端的缺失链路，再把 `/ai` 从单页改成智能域壳层，拆成 `workbench` 和 `graph` 两个子页。当前 `AIAssistant.vue` 保留为工作台页，新增 `AIGraphWorkspace.vue` 承接 graph import / view / qa / strategy，并通过路由 query 把图谱策略页生成的控制指令回送到工作台。

**Tech Stack:** FastAPI, Python unittest, Vue 3, Vue Router, Vite, node:test

---

## File Map

### Backend

- Modify: `backend/app/services/llm.py`
  - 补回 `dispatch_workbench_message()`、判路 prompt、结构化 JSON 解析入口，保留 graph 相关方法共存
- Modify: `backend/app/models/graph_schemas.py`
  - 新增 graph strategy request schema
- Modify: `backend/app/api/graph.py`
  - 新增 `/api/graph/strategy`
  - 在 graph 域内部重建运行态上下文，不再依赖已删除的 `ai_control.py`

### Frontend

- Modify: `frontend/src/main.js`
  - 把 `/ai` 改成二级子路由壳层
- Create: `frontend/src/views/AIWorkspaceLayout.vue`
  - 只负责智能域 tabs 和子路由承载
- Modify: `frontend/src/views/AIAssistant.vue`
  - 保持工作台主体不变
  - 增加从 graph 页回填 query 的消费逻辑
- Create: `frontend/src/views/AIGraphWorkspace.vue`
  - 组合现有 graph 组件，承接远端 graph UI
- Modify: `frontend/src/services/api.js`
  - 新增 graph strategy API 封装
- Modify: `frontend/src/composables/useConsoleShell.js`
  - 让左侧“智能”导航匹配 `/ai/*`

### Tests

- Create: `tests/test_ai_workbench_dispatch_api.py`
  - 覆盖 `/api/ai/workbench/dispatch` 和 `LLMService.dispatch_workbench_message`
- Modify: `tests/test_frontend_ui_structure.py`
  - 增加 AI 双页壳层、graph 页挂载、工作台不回退的结构断言
- Modify: `frontend/src/lib/routeAccess.test.js`
  - 覆盖 `/ai/graph` 的可访问性
- Optional Modify: `tests/test_real_data_only_structure.py`
  - 若有必要，补一条 graph 页不是孤立代码的断言

---

### Task 1: Repair AI Workbench Dispatch Regression

**Files:**
- Modify: `backend/app/services/llm.py`
- Create: `tests/test_ai_workbench_dispatch_api.py`
- Test: `tests/test_ai_workbench_dispatch_api.py`
- Test: `tests/test_llm_streaming.py`

- [ ] **Step 1: Write the failing backend regression test**

Create `tests/test_ai_workbench_dispatch_api.py` with both route-level and service-level assertions:

```python
import os
import sys
import types
import unittest
from unittest import mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from fastapi import HTTPException  # noqa: E402
from app.api.ai import dispatch_workbench_message  # noqa: E402
from app.models.schemas import AiWorkbenchDispatchRequest  # noqa: E402
from app.services.llm import LLMService  # noqa: E402


class FakeAgent:
    async def get_all_gpus(self):
        return []

    async def get_system_info(self):
        return {}

    async def get_processes(self):
        return []


class FakeImportContext:
    def filter_gpus(self, gpus):
        return gpus

    def filter_processes(self, processes):
        return processes


class FakePrivacy:
    def sanitize_processes(self, processes):
        return processes


class FakeLLM:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    async def dispatch_workbench_message(self, message, gpu_context=""):
        self.calls.append((message, gpu_context))
        if self.error:
            raise self.error
        return dict(self.result)


class AIWorkbenchDispatchRouteTests(unittest.IsolatedAsyncioTestCase):
    def test_llm_service_exposes_dispatch_workbench_message(self):
        self.assertTrue(hasattr(LLMService, "dispatch_workbench_message"))

    async def test_dispatch_returns_chat_stream_result(self):
        fake_llm = FakeLLM({"route_kind": "chat", "reply_mode": "stream"})
        fake_state = types.SimpleNamespace(
            llm=fake_llm,
            agent=FakeAgent(),
            import_context=FakeImportContext(),
            privacy=FakePrivacy(),
        )
        fake_main = types.SimpleNamespace(app_state=fake_state)

        with mock.patch.dict(sys.modules, {"app.main": fake_main}):
            result = await dispatch_workbench_message(
                AiWorkbenchDispatchRequest(message="为什么 GPU 0 不可用？")
            )

        self.assertEqual(result["route_kind"], "chat")
        self.assertEqual(result["reply_mode"], "stream")

    async def test_dispatch_returns_runtime_result(self):
        fake_llm = FakeLLM(
            {"route_kind": "runtime", "message": "把 GPU 0 功耗限制到 220W"}
        )
        fake_state = types.SimpleNamespace(
            llm=fake_llm,
            agent=FakeAgent(),
            import_context=FakeImportContext(),
            privacy=FakePrivacy(),
        )
        fake_main = types.SimpleNamespace(app_state=fake_state)

        with mock.patch.dict(sys.modules, {"app.main": fake_main}):
            result = await dispatch_workbench_message(
                AiWorkbenchDispatchRequest(message="把 GPU 0 功耗限制到 220W")
            )

        self.assertEqual(result["route_kind"], "runtime")
        self.assertEqual(result["message"], "把 GPU 0 功耗限制到 220W")

    async def test_dispatch_raises_503_when_llm_missing(self):
        fake_state = types.SimpleNamespace(
            llm=None,
            agent=FakeAgent(),
            import_context=FakeImportContext(),
            privacy=FakePrivacy(),
        )
        fake_main = types.SimpleNamespace(app_state=fake_state)

        with mock.patch.dict(sys.modules, {"app.main": fake_main}):
            with self.assertRaises(HTTPException) as ctx:
                await dispatch_workbench_message(
                    AiWorkbenchDispatchRequest(message="帮我处理一下")
                )

        self.assertEqual(ctx.exception.status_code, 503)
```

- [ ] **Step 2: Run the regression test and confirm it fails**

Run:

```bash
timeout 60s python3 -m unittest tests.test_ai_workbench_dispatch_api -v
```

Expected:

```text
FAIL: test_llm_service_exposes_dispatch_workbench_message
```

- [ ] **Step 3: Port the dispatch prompt and method back into `LLMService`**

In `backend/app/services/llm.py`, import and keep the local-main workbench dispatch pieces while preserving graph methods. Add these exact structures near the existing prompt definitions and helper methods:

```python
WORKBENCH_DISPATCH_PROMPT = """你是 AI 助手统一工作台的判路器。

你的任务是判断用户当前这句话应该进入：
1. chat：解释、分析、问答
2. runtime：需要进入目标驱动执行链

要求：
- 只返回 JSON
- 如果是 chat，返回 {"route_kind":"chat","reply_mode":"inline|stream"}
- 如果是 runtime，返回 {"route_kind":"runtime","message":"整理后的执行目标"}
- 澄清、解释、分析、为什么、怎么看、总结、说明，优先走 chat
- 涉及执行、调整、暂停、恢复、终止、调度、限功、预算、治理动作，走 runtime
"""


def _normalize_workbench_dispatch_result(parsed: dict, fallback_message: str) -> dict:
    route_kind = str(parsed.get("route_kind") or "").strip().lower()
    if route_kind == "runtime":
        message = str(parsed.get("message") or fallback_message).strip()
        if not message:
            raise ValueError("AI 工作台判路结果缺少 runtime message")
        return {"route_kind": "runtime", "message": message}

    if route_kind == "chat":
        reply_mode = str(parsed.get("reply_mode") or "stream").strip().lower()
        if reply_mode not in {"inline", "stream"}:
            reply_mode = "stream"
        payload = {"route_kind": "chat", "reply_mode": reply_mode}
        if reply_mode == "inline":
            payload["reply"] = str(parsed.get("reply") or "").strip()
        return payload

    raise ValueError("AI 工作台判路结果缺少合法 route_kind")
```

Also add the service methods back into `LLMService`:

```python
@classmethod
def parse_structured_json(cls, content: str, *, label: str) -> dict:
    parsed = cls._parse_json_response(content)
    if not isinstance(parsed, dict):
        raise ValueError(f"{label}不是合法 JSON")
    return parsed


async def dispatch_workbench_message(
    self,
    user_message: str,
    gpu_context: str = "",
) -> dict:
    messages = [{"role": "system", "content": WORKBENCH_DISPATCH_PROMPT}]
    if gpu_context:
        messages.append({
            "role": "system",
            "content": f"当前GPU集群实时状态：\n{gpu_context}",
        })
    messages.append({"role": "user", "content": user_message})

    content = await self._call_with_retry(
        model=self.model,
        messages=messages,
        temperature=0.1,
        max_tokens=400,
    )
    parsed = self.parse_structured_json(content, label="AI 工作台判路结果")
    return _normalize_workbench_dispatch_result(parsed, user_message)
```

- [ ] **Step 4: Re-run focused backend tests**

Run:

```bash
timeout 60s python3 -m unittest tests.test_ai_workbench_dispatch_api tests.test_llm_streaming -v
```

Expected:

```text
Ran ... tests in ...s
OK
```

- [ ] **Step 5: Commit the regression fix**

```bash
git add backend/app/services/llm.py tests/test_ai_workbench_dispatch_api.py
git commit -m "fix: restore ai workbench dispatch runtime"
```

---

### Task 2: Restore Graph Strategy API Inside the Graph Domain

**Files:**
- Modify: `backend/app/models/graph_schemas.py`
- Modify: `backend/app/api/graph.py`
- Test: `backend/tests/test_graph_strategy.py`

- [ ] **Step 1: Add a graph strategy request schema**

Append this request model in `backend/app/models/graph_schemas.py` after `GraphQaRequest`:

```python
class GraphStrategyRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    max_nodes: int = Field(default=10, ge=4, le=16)
    max_relationships: int = Field(default=12, ge=4, le=24)
```

- [ ] **Step 2: Add a graph-runtime context builder to remove the deleted `ai_control.py` dependency**

In `backend/app/api/graph.py`, add a local helper that reconstructs the runtime context using existing services:

```python
import json

from app.services.graph_strategy import (
    build_graph_strategy_context,
    build_graph_strategy_fallback,
)


async def _build_graph_runtime_context(app_state) -> dict:
    gpus = app_state.import_context.filter_gpus(await app_state.agent.get_all_gpus() or [])
    processes = app_state.import_context.filter_processes(await app_state.agent.get_processes() or [])
    priorities = await app_state.store.get_all_task_priorities()
    sanitized_processes = app_state.privacy.sanitize_processes(processes)
    budget = app_state.scheduler.get_budget_status(gpus)

    llm_context = {
        "time_period": get_time_period_label(),
        "budget": budget,
        "gpus": [
            {
                key: gpu.get(key)
                for key in (
                    "index",
                    "name",
                    "temperature",
                    "power_usage",
                    "power_limit",
                    "gpu_utilization",
                    "memory_used",
                    "memory_total",
                )
            }
            for gpu in gpus
        ],
        "manageable_processes": [
            {
                "pid": proc.get("pid"),
                "gpu_index": proc.get("gpu_index"),
                "name": proc.get("name"),
                "username": proc.get("username"),
                "priority": priorities.get(proc.get("pid"), proc.get("priority", "normal")),
                "gpu_memory_used": proc.get("gpu_memory_used", 0),
                "command": proc.get("command", ""),
            }
            for proc in sanitized_processes[:12]
        ],
    }
    return {
        "gpus": gpus,
        "processes": processes,
        "budget": budget,
        "llm_context": json.dumps(llm_context, ensure_ascii=False, indent=2),
    }
```

- [ ] **Step 3: Expose `/api/graph/strategy`**

In `backend/app/api/graph.py`, add the route using the rebuilt runtime context:

```python
@router.post("/strategy")
async def generate_graph_strategy(request: Request, req: GraphStrategyRequest):
    require_authenticated_user(request)

    from app.main import app_state

    message = req.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="请输入优化目标")

    graph_view = await app_state.graph.view_graph(query="", limit=180)
    if not graph_view["ok"]:
        status_code = 503 if not graph_view["neo4j_connected"] or not graph_view["configured"] else 500
        raise HTTPException(status_code=status_code, detail=graph_view["message"])

    runtime_context = await _build_graph_runtime_context(app_state)
    strategy_context = build_graph_strategy_context(
        message,
        graph_view,
        runtime_context,
        max_nodes=req.max_nodes,
        max_relationships=req.max_relationships,
    )
    fallback = build_graph_strategy_fallback(message, strategy_context)

    llm_result = None
    if app_state.llm:
        llm_result = await app_state.llm.generate_graph_strategy_plan(
            message,
            strategy_context["context_text"],
            strategy_context["runtime_summary"],
        )

    payload = llm_result or fallback
    return {
        "message": message,
        "summary": payload.get("summary") or fallback["summary"],
        "strategy_steps": payload.get("strategy_steps") or fallback["strategy_steps"],
        "control_prompt": payload.get("control_prompt") or fallback["control_prompt"],
        "code_title": payload.get("code_title") or fallback["code_title"],
        "code_language": payload.get("code_language") or fallback["code_language"],
        "code_snippet": payload.get("code_snippet") or fallback["code_snippet"],
        "risk_notice": payload.get("risk_notice") or fallback["risk_notice"],
        "evidence": payload.get("evidence") or fallback["evidence"],
        "follow_ups": payload.get("follow_ups") or fallback["follow_ups"],
        "used_llm": bool(llm_result),
        "matched_node_count": strategy_context["matched_node_count"],
        "matched_relationship_count": strategy_context["matched_relationship_count"],
        "paper_titles": strategy_context["paper_titles"],
        "evidence_nodes": strategy_context["evidence_nodes"],
        "evidence_relationships": strategy_context["evidence_relationships"],
        "focus": strategy_context["focus"],
        "runtime_summary": strategy_context["runtime_summary"],
    }
```

- [ ] **Step 4: Add a focused backend test for the new strategy endpoint contract**

Create or extend `backend/tests/test_graph_strategy.py` with a FastAPI-level unit that verifies the route shape:

```python
async def test_graph_strategy_returns_fallback_payload_when_llm_missing(self):
    fake_graph = FakeGraphStore(...)
    fake_scheduler = FakeScheduler(...)
    fake_state = types.SimpleNamespace(
        llm=None,
        graph=fake_graph,
        scheduler=fake_scheduler,
        agent=FakeAgent(),
        import_context=FakeImportContext(),
        privacy=FakePrivacy(),
        store=FakeStore(),
    )
    ...
    result = await generate_graph_strategy(request, GraphStrategyRequest(message="高峰期降低总功耗"))
    self.assertIn("strategy_steps", result)
    self.assertIn("control_prompt", result)
    self.assertIn("runtime_summary", result)
```

- [ ] **Step 5: Run focused graph backend tests**

Run:

```bash
timeout 60s env PYTHONPATH=backend python3 -m unittest backend.tests.test_graph_strategy -v
```

Expected:

```text
Ran ... tests in ...s
OK
```

- [ ] **Step 6: Commit the graph strategy backend restoration**

```bash
git add backend/app/models/graph_schemas.py backend/app/api/graph.py backend/tests/test_graph_strategy.py
git commit -m "feat: restore graph strategy api"
```

---

### Task 3: Introduce the AI Workspace Shell and Nested Routes

**Files:**
- Create: `frontend/src/views/AIWorkspaceLayout.vue`
- Modify: `frontend/src/main.js`
- Modify: `frontend/src/composables/useConsoleShell.js`
- Modify: `frontend/src/lib/routeAccess.test.js`
- Test: `frontend/src/lib/routeAccess.test.js`

- [ ] **Step 1: Write the route-level failing test**

Extend `frontend/src/lib/routeAccess.test.js` with a concrete `/ai/graph` access case:

```javascript
test('ready users can access nested ai routes', () => {
  const result = resolveRouteAccess({
    path: '/ai/graph',
    user: { id: 1, must_change_password: false },
    workspaceReady: true,
  })

  assert.deepEqual(result, { allow: true, redirectTo: null })
})
```

- [ ] **Step 2: Create the AI shell view**

Create `frontend/src/views/AIWorkspaceLayout.vue`:

```vue
<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import WorkspaceTabs from '../components/workspace/WorkspaceTabs.vue'

const route = useRoute()
const router = useRouter()

const aiTabs = [
  { key: 'workbench', label: '智能工作台', desc: '问答与执行' },
  { key: 'graph', label: '图谱智能', desc: '入图与推理' },
]

const activeTab = computed(() => (
  route.path.startsWith('/ai/graph') ? 'graph' : 'workbench'
))

function selectTab(nextTab) {
  void router.push(nextTab === 'graph' ? '/ai/graph' : '/ai/workbench')
}
</script>

<template>
  <div class="workspace-nav-layout">
    <div class="workspace-nav-layout__nav">
      <WorkspaceTabs
        :model-value="activeTab"
        :items="aiTabs"
        @update:model-value="selectTab"
      />
    </div>
    <div class="workspace-nav-layout__content">
      <router-view />
    </div>
  </div>
</template>
```

- [ ] **Step 3: Nest `/ai` routes in `frontend/src/main.js`**

Replace the current single-route AI entry:

```javascript
const loadAIWorkspaceLayoutView = () => import('./views/AIWorkspaceLayout.vue')
const loadAIGraphWorkspaceView = () => import('./views/AIGraphWorkspace.vue')
```

Then update the route tree:

```javascript
{
  path: 'ai',
  component: loadAIWorkspaceLayoutView,
  meta: { hideShellHeader: true },
  children: [
    { path: '', redirect: '/ai/workbench' },
    { path: 'workbench', name: 'AIAssistant', component: loadAIAssistantView, meta: { hideShellHeader: true } },
    { path: 'graph', name: 'AIGraphWorkspace', component: loadAIGraphWorkspaceView, meta: { hideShellHeader: true } },
  ],
},
```

- [ ] **Step 4: Fix sidebar path matching for `/ai/*`**

Update the AI nav item in `frontend/src/composables/useConsoleShell.js`:

```javascript
{ path: '/ai', matchPrefix: '/ai', label: '智能', icon: '智', desc: '工作台与图谱智能', group: 'support' },
```

- [ ] **Step 5: Run the route test**

Run:

```bash
node --test frontend/src/lib/routeAccess.test.js
```

Expected:

```text
✔ ready users can access nested ai routes
```

- [ ] **Step 6: Commit the routing shell**

```bash
git add frontend/src/views/AIWorkspaceLayout.vue frontend/src/main.js frontend/src/composables/useConsoleShell.js frontend/src/lib/routeAccess.test.js
git commit -m "feat: split ai workspace routes"
```

---

### Task 4: Mount the Graph Workspace Page and Bridge Strategy Output Back to Workbench

**Files:**
- Create: `frontend/src/views/AIGraphWorkspace.vue`
- Modify: `frontend/src/views/AIAssistant.vue`
- Modify: `frontend/src/services/api.js`
- Test: `tests/test_frontend_ui_structure.py`

- [ ] **Step 1: Add the missing graph strategy API client**

In `frontend/src/services/api.js`, add:

```javascript
export const graphStrategy = (payload) => api.post('/graph/strategy', payload)
```

- [ ] **Step 2: Create the graph workspace page**

Create `frontend/src/views/AIGraphWorkspace.vue` and wire the existing graph components instead of rewriting them:

```vue
<script setup>
import { computed, proxyRefs, ref } from 'vue'
import { useRouter } from 'vue-router'

import GraphCatalogViewer from '../components/ai/GraphCatalogViewer.vue'
import GraphCypherPreview from '../components/ai/GraphCypherPreview.vue'
import GraphExecuteResult from '../components/ai/GraphExecuteResult.vue'
import GraphImportPanel from '../components/ai/GraphImportPanel.vue'
import GraphQAPanel from '../components/ai/GraphQAPanel.vue'
import GraphStrategyGenerator from '../components/ai/GraphStrategyGenerator.vue'
import WorkspaceSummary from '../components/workspace/WorkspaceSummary.vue'
import WorkspaceTabs from '../components/workspace/WorkspaceTabs.vue'
import { useAiAssistantLlm } from '../composables/useAiAssistantLlm.js'
import { useGraphWorkspace } from '../composables/useGraphWorkspace.js'
import { graphStrategy } from '../services/api.js'

const router = useRouter()
const graph = proxyRefs(useGraphWorkspace())
const llm = useAiAssistantLlm()
const activeTab = ref('import')
const strategyForm = ref({ message: '' })
const strategyBusy = ref(false)
const strategyResult = ref(null)

const graphTabs = [
  { key: 'import', label: '知识入图', desc: '草稿与写入' },
  { key: 'catalog', label: '图谱展示', desc: '结构浏览' },
  { key: 'qa', label: '图谱问答', desc: '证据问答' },
  { key: 'strategy', label: '策略生成', desc: '模板与指令' },
]

const canGenerateStrategy = computed(() =>
  Boolean(String(strategyForm.value.message || '').trim()) && graph.summary.neo4j_connected
)

async function generateStrategy() {
  if (!canGenerateStrategy.value || strategyBusy.value) return
  strategyBusy.value = true
  try {
    const { data } = await graphStrategy({ message: strategyForm.value.message.trim() })
    strategyResult.value = data
  } finally {
    strategyBusy.value = false
  }
}

function openWorkbenchDraft(prompt, autoRun = false) {
  const message = String(prompt || '').trim()
  if (!message) return
  void router.push({
    path: '/ai/workbench',
    query: autoRun
      ? { draft: message, autorun: '1' }
      : { draft: message },
  })
}

function openGraphQa(question = '') {
  activeTab.value = 'qa'
  if (!question) return
  graph.qaForm.question = question
  void graph.askGraphQuestion(question)
}
</script>
```

The template must mount:

```vue
<WorkspaceSummary title="图谱智能工作区" />
<WorkspaceTabs v-model="activeTab" :items="graphTabs" />
<GraphImportPanel ... />
<GraphCypherPreview ... />
<GraphExecuteResult ... />
<GraphCatalogViewer ... />
<GraphQAPanel ... />
<GraphStrategyGenerator
  ...
  @generate="generateStrategy"
  @use-control="openWorkbenchDraft($event, false)"
  @use-control-plan="openWorkbenchDraft($event, true)"
  @ask="openGraphQa"
/>
```

- [ ] **Step 3: Teach `AIAssistant.vue` to consume graph strategy drafts**

Update `frontend/src/views/AIAssistant.vue` to read route query and prefill or auto-submit without changing the page structure back to tabs:

```vue
<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

async function consumeDraftQuery() {
  const draft = String(route.query.draft || '').trim()
  const autoRun = String(route.query.autorun || '') === '1'
  if (!draft) return

  composerText.value = draft
  await router.replace({ path: '/ai/workbench', query: {} })
  if (autoRun) {
    await submitWorkbenchInput(draft)
  }
}

onMounted(async () => {
  await loadAssistantCapability()
  await loadSessionHistory()
  await consumeDraftQuery()
})

watch(() => route.query, async () => {
  await consumeDraftQuery()
})
</script>
```

- [ ] **Step 4: Add structural assertions for the dual-page AI workspace**

Extend `tests/test_frontend_ui_structure.py` with assertions like:

```python
def test_ai_workspace_layout_hosts_two_subpages(self):
    layout_text = (ROOT / "frontend/src/views/AIWorkspaceLayout.vue").read_text(encoding="utf-8")
    main_text = (ROOT / "frontend/src/main.js").read_text(encoding="utf-8")
    self.assertIn("WorkspaceTabs", layout_text)
    self.assertIn("智能工作台", layout_text)
    self.assertIn("图谱智能", layout_text)
    self.assertIn("path: 'workbench'", main_text)
    self.assertIn("path: 'graph'", main_text)

def test_ai_graph_workspace_mounts_graph_components(self):
    text = (ROOT / "frontend/src/views/AIGraphWorkspace.vue").read_text(encoding="utf-8")
    self.assertIn("GraphImportPanel", text)
    self.assertIn("GraphCatalogViewer", text)
    self.assertIn("GraphQAPanel", text)
    self.assertIn("GraphStrategyGenerator", text)
    self.assertIn("useGraphWorkspace", text)
    self.assertIn("graphStrategy", text)

def test_ai_assistant_consumes_graph_strategy_query_without_restoring_tabs(self):
    text = (ROOT / "frontend/src/views/AIAssistant.vue").read_text(encoding="utf-8")
    self.assertIn("route.query.draft", text)
    self.assertIn("submitWorkbenchInput(draft)", text)
    self.assertNotIn("WorkspaceTabs", text)
```

- [ ] **Step 5: Run the structure regression tests**

Run:

```bash
timeout 60s python3 -m unittest tests.test_frontend_ui_structure -v
```

Expected:

```text
Ran ... tests in ...s
OK
```

- [ ] **Step 6: Commit the dual-page frontend**

```bash
git add frontend/src/views/AIGraphWorkspace.vue frontend/src/views/AIAssistant.vue frontend/src/services/api.js tests/test_frontend_ui_structure.py
git commit -m "feat: add graph ai workspace page"
```

---

### Task 5: Final Verification

**Files:**
- Test: `tests/test_ai_workbench_dispatch_api.py`
- Test: `tests/test_frontend_ui_structure.py`
- Test: `tests/test_real_data_only_structure.py`
- Test: `tests/test_goal_runtime_api.py`
- Test: `tests/test_llm_streaming.py`
- Test: `backend/tests/test_graph_strategy.py`
- Test: `frontend/src/lib/routeAccess.test.js`
- Test: `frontend/src/lib/agentWorkbenchThread.test.js`
- Test: `frontend/src/components/ai/graphStatus.test.js`
- Test: `frontend/src/components/ai/graphViewerTransforms.test.js`

- [ ] **Step 1: Run Python structure and API regressions**

```bash
timeout 60s python3 -m unittest \
  tests.test_ai_workbench_dispatch_api \
  tests.test_frontend_ui_structure \
  tests.test_real_data_only_structure \
  tests.test_goal_runtime_api \
  tests.test_llm_streaming -v
```

Expected:

```text
Ran ... tests in ...s
OK
```

- [ ] **Step 2: Run backend graph strategy tests**

```bash
timeout 60s env PYTHONPATH=backend python3 -m unittest backend.tests.test_graph_strategy -v
```

Expected:

```text
Ran ... tests in ...s
OK
```

- [ ] **Step 3: Run focused frontend node tests**

```bash
node --test \
  frontend/src/lib/routeAccess.test.js \
  frontend/src/lib/agentWorkbenchThread.test.js \
  frontend/src/components/ai/graphStatus.test.js \
  frontend/src/components/ai/graphViewerTransforms.test.js
```

Expected:

```text
ℹ pass ...
ℹ fail 0
```

- [ ] **Step 4: Compile backend modules**

```bash
python3 -m compileall backend/app server-agent
```

Expected:

```text
Listing 'backend/app'...
Listing 'server-agent'...
```

- [ ] **Step 5: Confirm final git state**

```bash
git status --short
```

Expected:

```text
<no output>
```

- [ ] **Step 6: Final integration commit**

```bash
git add backend frontend tests
git commit -m "feat: support dual ai workspaces"
```

---

## Self-Review

- Spec coverage:
  - “先修复当前 merge 中 AI workbench 的后端判路回归” -> Task 1
  - “新增智能域壳层和图谱页路由” -> Task 3
  - “挂载 graph workspace 页面” -> Task 4
  - “graph strategy 至少具备页面入口和 API 连通性” -> Task 2 + Task 4
  - “当前 AIAssistant 不回退成旧 tabs” -> Task 4 structural test
- Placeholder scan:
  - 没有 `TODO`、`TBD`、`类似 Task N`
- Type consistency:
  - 新增视图名统一为 `AIWorkspaceLayout.vue` / `AIGraphWorkspace.vue`
  - Graph strategy API 统一为 `/api/graph/strategy` 和 `graphStrategy()`
  - workbench 回填 query 统一使用 `draft` / `autorun`
