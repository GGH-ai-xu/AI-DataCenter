# AI 助手交互卡分组 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 AI 助手线程从“消息 / 事件平铺”重构为“每条用户输入一张交互卡”，让同一次对话的回复、计划、审批、执行和结果都归属到同一张卡片内。

**Architecture:** 保持后端 schema、SSE 和 runtime 持久化不变，只在前端新增 `interaction[]` 视图模型。`buildAgentWorkbenchThread()` 负责把 `chatMessages + runtimeSession + runtimeEvents` 归并成交互卡数据，新组件树负责渲染“摘要 + 步骤 + 详情”两层结构，并复用已有 plan / approval / tool / result / error 子卡。

**Tech Stack:** Vue 3 SFC, Node `node:test`, Python `unittest`, Vite

---

## File Structure

- Modify: `frontend/src/lib/agentWorkbenchThread.js`
  - 将线程一级对象从 `items[]` 改成 `interactions[]`，保留 `topbar`，新增 `leadMessage`。
- Modify: `frontend/src/lib/agentWorkbenchThread.test.js`
  - 用失败测试锁定 chat-only、runtime、两次用户输入、历史会话回放四类交互归属。
- Create: `frontend/src/components/agent/AgentInteractionList.vue`
  - 渲染交互卡列表与前置提示消息。
- Create: `frontend/src/components/agent/AgentInteractionCard.vue`
  - 渲染单次交互的头部、助手摘要、步骤条和展开/收起入口。
- Create: `frontend/src/components/agent/AgentInteractionSteps.vue`
  - 渲染紧凑步骤摘要条。
- Create: `frontend/src/components/agent/AgentInteractionDetail.vue`
  - 在详情区复用已有 runtime 子卡，并透传审批事件。
- Modify: `frontend/src/components/agent/AgentThread.vue`
  - 改为基于 `interactions` 渲染，不再渲染平铺 item。
- Modify: `frontend/src/components/agent/AgentWorkbench.vue`
  - 将 `thread-items` 改为 `interactions` 和 `lead-message`。
- Modify: `frontend/src/views/AIAssistant.vue`
  - 适配新的 workbench view 字段。
- Delete: `frontend/src/components/agent/AgentThreadItem.vue`
  - 停止使用旧的平铺 item 路由组件。
- Modify: `tests/test_frontend_ui_structure.py`
  - 新增交互卡组件存在性与旧平铺组件退场断言。

## Task 1: Lock The Interaction View Model With Failing Tests

**Files:**
- Modify: `frontend/src/lib/agentWorkbenchThread.test.js`

- [ ] **Step 1: 写出失败测试，锁定“单次聊天 = 一张交互卡”**

在 `frontend/src/lib/agentWorkbenchThread.test.js` 增加以下测试：

```js
test('buildAgentWorkbenchThread groups one user message and one assistant reply into one interaction', () => {
  const view = buildAgentWorkbenchThread({
    chatMessages: [
      { id: 'intro', role: 'assistant', content: '你好，我是 AI 治理助手。' },
      { id: 'u1', role: 'user', content: 'GPU 0 为什么不可用？' },
      { id: 'a1', role: 'assistant', content: 'GPU 0 当前被驱动标记为异常。' },
    ],
    runtimeSession: null,
    runtimeEvents: [],
  })

  assert.equal(view.leadMessage?.id, 'intro')
  assert.equal(view.interactions.length, 1)
  assert.equal(view.interactions[0].userMessage.content, 'GPU 0 为什么不可用？')
  assert.equal(view.interactions[0].assistantReply, 'GPU 0 当前被驱动标记为异常。')
  assert.equal(view.interactions[0].runtimeCards.length, 0)
  assert.equal(view.interactions[0].status, 'completed')
})
```

- [ ] **Step 2: 写出失败测试，锁定 runtime 事件归属到最近一次用户输入**

继续添加：

```js
test('buildAgentWorkbenchThread attaches runtime cards to the latest user interaction', () => {
  const view = buildAgentWorkbenchThread({
    chatMessages: [
      { id: 'u1', role: 'user', content: '把 GPU 0 功耗限制到 220W' },
      { id: 'a1', role: 'assistant', content: '已进入执行链，正在生成计划。' },
    ],
    runtimeSession: {
      session_id: 's1',
      status: 'awaiting_approval',
      live_phase: 'awaiting_approval',
      goal_json: { raw_message: '把 GPU 0 功耗限制到 220W' },
    },
    runtimeEvents: [
      { event_type: 'PlanCreated', payload: {}, sequence: 1, timestamp: 1 },
      { event_type: 'AwaitingApproval', payload: { actions: [{}] }, sequence: 2, timestamp: 2 },
    ],
  })

  assert.equal(view.interactions.length, 1)
  assert.equal(view.interactions[0].runtimeCards.length, 2)
  assert.equal(view.interactions[0].runtimeCards[0].kind, 'plan_card')
  assert.equal(view.interactions[0].runtimeCards[1].kind, 'approval_card')
  assert.equal(view.interactions[0].status, 'awaiting_approval')
})
```

- [ ] **Step 3: 写出失败测试，锁定多轮用户输入必须拆成两张交互卡**

继续添加：

```js
test('buildAgentWorkbenchThread splits consecutive user turns into separate interactions', () => {
  const view = buildAgentWorkbenchThread({
    chatMessages: [
      { id: 'u1', role: 'user', content: '先解释一下当前 GPU 状态' },
      { id: 'a1', role: 'assistant', content: '当前共有 3 张可用卡。' },
      { id: 'u2', role: 'user', content: '把 GPU 1 功耗限制到 240W' },
      { id: 'a2', role: 'assistant', content: '已进入执行链。' },
    ],
    runtimeSession: {
      session_id: 's2',
      status: 'running',
      live_phase: 'executing',
      goal_json: { raw_message: '把 GPU 1 功耗限制到 240W' },
    },
    runtimeEvents: [
      { event_type: 'PlanCreated', payload: {}, sequence: 1, timestamp: 1 },
    ],
  })

  assert.equal(view.interactions.length, 2)
  assert.equal(view.interactions[0].runtimeCards.length, 0)
  assert.equal(view.interactions[1].userMessage.content, '把 GPU 1 功耗限制到 240W')
  assert.equal(view.interactions[1].runtimeCards.length, 1)
})
```

- [ ] **Step 4: 写出失败测试，锁定“历史 session 回放”也能生成交互卡**

继续添加：

```js
test('buildAgentWorkbenchThread builds an interaction from runtime session message when chat history is empty', () => {
  const view = buildAgentWorkbenchThread({
    chatMessages: [{ id: 'intro', role: 'assistant', content: '你好，我是 AI 治理助手。' }],
    runtimeSession: {
      session_id: 's3',
      status: 'completed',
      live_phase: 'completed',
      goal_json: { raw_message: '执行一次公平性巡检' },
      summary: '执行一次公平性巡检',
    },
    runtimeEvents: [
      { event_type: 'SessionCompleted', payload: { summary: '巡检已完成' }, sequence: 1, timestamp: 1 },
    ],
  })

  assert.equal(view.interactions.length, 1)
  assert.equal(view.interactions[0].userMessage.content, '执行一次公平性巡检')
  assert.equal(view.interactions[0].runtimeCards[0].kind, 'result_card')
})
```

- [ ] **Step 5: 运行测试，确认当前实现确实失败**

Run:

```bash
cd /mnt/e/code/ai-datacenter/frontend
node --test src/lib/agentWorkbenchThread.test.js
```

Expected: FAIL because `leadMessage` / `interactions` 还不存在，当前实现仍返回平铺 `items[]`。

## Task 2: Implement The Interaction View Model

**Files:**
- Modify: `frontend/src/lib/agentWorkbenchThread.js`

- [ ] **Step 1: 实现交互分组基础结构**

将返回结构改为：

```js
return {
  topbar: {},
  leadMessage,
  interactions,
}
```

其中 `leadMessage` 仅承接首条 intro assistant 消息；`interactions` 中每项至少包含：

```js
{
  id: 'interaction-u1',
  userMessage: { id: 'u1', content: '...' },
  assistantMessages: [],
  assistantReply: '',
  runtimeCards: [],
  status: 'processing',
  steps: [],
}
```

- [ ] **Step 2: 实现聊天分组逻辑**

按 `chatMessages` 原顺序遍历：

```js
if (message.role === 'assistant' && index === 0 && message.id === 'intro') {
  leadMessage = buildMessageItem(message, index)
  continue
}
if (message.role === 'user') {
  current = createInteractionFromUserMessage(message, index)
  interactions.push(current)
  continue
}
appendAssistantMessage(current, message)
```

要求：
- 没有 `current` 时遇到 assistant 普通消息，不创建假交互。
- 多条 assistant 消息收集到 `assistantMessages[]`，`assistantReply` 用换行拼接。

- [ ] **Step 3: 实现 runtime 归属规则与状态映射**

当 `runtimeEvents.length > 0` 或 `runtimeSession` 存在时：

```js
const target = findRuntimeTargetInteraction(interactions, runtimeSession)
for (const event of runtimeEvents) {
  target.runtimeCards.push(buildRuntimeItem(event))
}
target.status = mapInteractionStatus(runtimeSession, target.runtimeCards)
target.steps = buildInteractionSteps(target.runtimeCards, target.status)
```

要求：
- 默认归属到最后一个用户交互。
- 若当前会话无用户消息但 `runtimeSession.goal_json.raw_message` 存在，则创建一张仅含用户输入的交互卡。
- `status` 只输出 `processing / awaiting_approval / completed / failed` 四类。

- [ ] **Step 4: 跑测试直到 view model 通过**

Run:

```bash
cd /mnt/e/code/ai-datacenter/frontend
node --test src/lib/agentWorkbenchThread.test.js
```

Expected: PASS

## Task 3: Replace The Flat Thread Renderer With Interaction Cards

**Files:**
- Create: `frontend/src/components/agent/AgentInteractionList.vue`
- Create: `frontend/src/components/agent/AgentInteractionCard.vue`
- Create: `frontend/src/components/agent/AgentInteractionSteps.vue`
- Create: `frontend/src/components/agent/AgentInteractionDetail.vue`
- Modify: `frontend/src/components/agent/AgentThread.vue`
- Modify: `frontend/src/components/agent/AgentWorkbench.vue`
- Modify: `frontend/src/views/AIAssistant.vue`
- Delete: `frontend/src/components/agent/AgentThreadItem.vue`

- [ ] **Step 1: 新增交互卡组件树**

组件职责：

```vue
<!-- AgentInteractionList.vue -->
<AgentThreadMessage v-if="leadMessage" :item="leadMessage" />
<AgentInteractionCard
  v-for="interaction in interactions"
  :key="interaction.id"
  :interaction="interaction"
/>
```

```vue
<!-- AgentInteractionCard.vue -->
<header>用户输入 + 状态标签</header>
<section v-if="interaction.assistantReply">助手摘要</section>
<AgentInteractionSteps :steps="interaction.steps" :status="interaction.status" />
<AgentInteractionDetail v-if="expanded" :interaction="interaction" />
```

- [ ] **Step 2: 复用现有 runtime 子卡，不重写审批逻辑**

在 `AgentInteractionDetail.vue` 里按 `runtimeCards` 的 `kind` 渲染：

```vue
<AgentThreadPlanCard v-if="card.kind === 'plan_card'" :item="card" />
<AgentThreadApprovalCard
  v-else-if="card.kind === 'approval_card'"
  :item="card"
  @approve="emit('approve', $event)"
  @reject="emit('reject', $event)"
/>
```

保留 `tool / result / error` 分支；不再使用 `AgentThreadItem.vue`。

- [ ] **Step 3: 接线到工作台**

在 `AgentWorkbench.vue` 和 `AIAssistant.vue` 将：

```vue
:thread-items="workbenchView.items"
```

替换为：

```vue
:lead-message="workbenchView.leadMessage"
:interactions="workbenchView.interactions"
```

`AgentThread.vue` 只做简单透传，不再维护 item 粒度分发。

- [ ] **Step 4: 本地构建一次，确认没有 SFC/prop 错误**

Run:

```bash
cd /mnt/e/code/ai-datacenter/frontend
npm run build
```

Expected: PASS

## Task 4: Lock The New Structure And Regression Coverage

**Files:**
- Modify: `tests/test_frontend_ui_structure.py`

- [ ] **Step 1: 增加结构断言，锁定新组件树**

在 `tests/test_frontend_ui_structure.py` 增加：

```python
def test_ai_assistant_thread_uses_interaction_card_components(self):
    for rel in [
        "frontend/src/components/agent/AgentInteractionList.vue",
        "frontend/src/components/agent/AgentInteractionCard.vue",
        "frontend/src/components/agent/AgentInteractionSteps.vue",
        "frontend/src/components/agent/AgentInteractionDetail.vue",
    ]:
        self.assertTrue((ROOT / rel).exists(), rel)

    thread_text = (ROOT / "frontend/src/components/agent/AgentThread.vue").read_text(encoding="utf-8")
    self.assertIn("AgentInteractionList", thread_text)
    self.assertNotIn("AgentThreadItem", thread_text)
```

- [ ] **Step 2: 运行仓库级结构测试**

Run:

```bash
cd /mnt/e/code/ai-datacenter
timeout 60s python -m unittest tests.test_frontend_ui_structure -q
```

Expected: PASS

- [ ] **Step 3: 运行本轮最小回归集**

Run:

```bash
cd /mnt/e/code/ai-datacenter/frontend
node --test src/lib/agentWorkbenchThread.test.js
cd /mnt/e/code/ai-datacenter
timeout 60s python -m unittest tests.test_frontend_ui_structure -q
```

Expected: PASS

## Self-Review

- Spec coverage: 已覆盖交互一级对象改造、按用户输入分组、助手摘要归并、步骤摘要条、默认折叠详情、历史 session 回放。
- Placeholder scan: 无 `TODO / TBD / similar to` 占位项。
- Type consistency: 计划统一使用 `leadMessage / interactions / assistantReply / runtimeCards / steps / status` 字段名。
