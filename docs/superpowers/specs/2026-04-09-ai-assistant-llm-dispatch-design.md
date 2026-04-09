# 2026-04-09 AI 助手统一入口 LLM 判路设计

## 背景

当前 AI 助手页面已经收敛为单一聊天工作台，但提交链路仍然保留了一层前端本地判意图逻辑：

- `frontend/src/lib/agentWorkbenchIntent.js` 用正则将输入分成 `chat / runtime / confirm`
- `frontend/src/composables/useAiAssistantWorkbench.js` 根据这个结果决定：
  - 直接走 `/api/ai/chat/stream`
  - 直接走 `/api/agent-runtime/sessions`
  - 或弹出“按解释处理 / 按执行处理”的二次确认

这套实现已经不符合当前产品目标：

1. 用户面对的是一个统一聊天框，不应该被迫理解“解释”和“执行”两条技术通道。
2. 前端关键词规则是硬编码判路器，不是真正的 Agent 交互。
3. “帮我处理一下”这类模糊请求，本质上应该由助手继续追问，而不是弹出一个路由选择卡片。
4. 真实执行仍然需要进入 runtime 审批链，但“是否进入执行链”的判断不应该继续写死在前端。

用户的明确方向是：

- 删除“按解释处理 / 按执行处理”的前端二选一交互
- 用户永远只输入一句自然语言
- 由 LLM 来决定当前输入应当进入“聊天”还是“执行”
- 如果信息不足，助手就在聊天线程里继续追问，而不是暴露第三种模式
- 真实执行仍然保留现有 runtime 审批和执行链

## 目标

- 将 AI 助手输入链路收敛为单一提交入口。
- 删除前端本地 `chat / runtime / confirm` 关键词判路逻辑。
- 新增后端统一判路接口，由 LLM 返回结构化路由结果。
- 保持对用户可见的模式只有两种：
  - 聊天
  - 执行
- 将“信息不足时继续追问”收敛为聊天结果的一种，不再作为独立路由模式暴露。
- 保留现有 runtime 会话、审批、事件流、执行账本的真实链路。

## 非目标

- 本轮不将聊天流和 runtime 流合并成单一 SSE 协议。
- 本轮不重写 goal runtime planner 或 capability registry。
- 本轮不引入新的本地 fallback 规则分类器。
- 本轮不让聊天接口直接绕过 runtime 审批执行真实动作。
- 本轮不重做 AI 助手页面布局，仅移除与旧判路方式耦合的交互。

## 现状问题

### 前端职责过重

当前前端直接承担“识别用户想聊天还是想执行”的职责，这会带来三个问题：

1. 规则不可扩展，新增意图只能继续堆关键词。
2. 与 LLM 驱动的 Agent 方向冲突，前端比模型更早决定了行为路径。
3. 模糊输入无法自然演进为多轮对话，只能退化成一个选择题。

### 用户心智不统一

从用户视角看，AI 助手已经是一个聊天工作台，但系统内部仍然暴露了“解释通道”和“执行通道”的实现细节。这种设计会让用户被迫理解系统边界，而不是直接表达目标。

### 执行边界不能丢

虽然前端关键词判路应该删掉，但 runtime 的审批边界不能消失。涉及真实操作时，仍然必须通过现有 runtime 会话来显式记录计划、审批和执行过程。

## 方案比较

### 方案 A：前端统一输入，后端继续用规则判路

优点：

- 改动最小
- 不依赖 LLM 新能力

缺点：

- 只是把硬编码从前端挪到后端
- 无法满足“交给 LLM 判断”的目标
- 对模糊请求的多轮追问能力仍然很弱

### 方案 B：前端统一输入，后端 LLM 判路，执行仍走现有 runtime

优点：

- 用户只看到一个聊天入口
- 判路逻辑从前端硬编码升级为模型驱动
- 执行审批边界不变
- 可以把澄清自然收敛成聊天追问

缺点：

- 需要新增一层结构化 LLM 调用和接口契约
- 前后端提交流程都要改

### 方案 C：所有请求全部并入 runtime

优点：

- 入口最统一
- 所有事件天然在一条会话链里

缺点：

- 将简单问答也强制 runtime 化，成本过高
- 会让现有聊天流和 runtime 流的边界在本轮大范围重构

## 设计结论

采用 `方案 B`。

原则如下：

1. 用户只面对一个输入框。
2. 系统内部仍然只有两类用户可感知结果：
   - 聊天
   - 执行
3. “澄清”不是第三种模式，而是聊天回复的一种形式。
4. 只要进入真实执行，仍然必须通过 runtime session。
5. 不允许新增静默 fallback；LLM 判路失败时要显式报错。

## 顶层架构

### 前端

`AIAssistant.vue` 页面继续作为统一聊天工作台承载者，不新增新的模式开关。

`useAiAssistantWorkbench.js` 的提交逻辑变为：

1. 接收用户输入
2. 先调用新的 `dispatch` 接口
3. 根据 `dispatch` 返回结果决定：
   - 直接插入一条聊天回复
   - 打开现有 chat stream
   - 启动现有 runtime session

删除：

- `frontend/src/lib/agentWorkbenchIntent.js`
- `pendingRouteConfirm`
- `resolveRouteConfirm`
- route confirm 卡片链路

### 后端

新增 AI 工作台统一判路接口：

- `POST /api/ai/workbench/dispatch`

它只负责一件事：结合实时上下文，让 LLM 输出当前请求应当进入“聊天”还是“执行”。

真正执行仍然复用：

- `POST /api/agent-runtime/sessions`
- runtime session stream
- approval flow

真正聊天流仍然复用：

- `POST /api/ai/chat/stream`

## 接口契约

### 请求

请求结构保持简单：

```json
{
  "message": "帮我把 2 号卡功耗降到 220W"
}
```

### 响应

只允许两种 `route_kind`：

#### 1. 聊天

```json
{
  "route_kind": "chat",
  "reply_mode": "inline",
  "reply": "你是希望我解释当前功耗偏高的原因，还是希望我直接执行一次治理动作？"
}
```

或：

```json
{
  "route_kind": "chat",
  "reply_mode": "stream"
}
```

语义：

- `reply_mode = inline`
  代表这次判路结果本身就是一条要直接展示的助手消息
- `reply_mode = stream`
  代表这条输入已经明确是聊天问答，前端接下来应继续调用现有聊天流接口拿正式回复

#### 2. 执行

```json
{
  "route_kind": "runtime",
  "message": "帮我把 2 号卡功耗降到 220W"
}
```

语义：

- 当前输入已经足够明确，可以进入 runtime 会话创建流程
- 前端随后继续调用现有 runtime session 启动接口

### 不引入第三种模式

模型如果认为信息不足，不返回 `clarify`。而是返回：

- `route_kind = chat`
- `reply_mode = inline`
- `reply = 一条追问`

这样用户看到的仍然是普通聊天线程，不会再看到额外模式切换。

## LLM 判路职责

新增一个专用的结构化判路提示词，用于让 LLM 在实时上下文下完成以下判断：

1. 当前输入是解释/问答类，还是执行/控制类
2. 如果是执行类，信息是否已经足够进入 runtime
3. 如果信息不足，应该给出什么追问

判路结果必须是严格 JSON，字段稳定，便于前后端消费。

### 判路规则约束

模型必须遵守以下约束：

- 只能输出 `chat` 或 `runtime`
- 不允许输出第三类模式
- 不允许直接执行动作
- 对执行类请求，如果缺少关键信息，必须返回 `chat + inline`
- 对明显解释型问题，应优先返回 `chat`

### 关键信息不足的例子

- “帮我处理一下”
- “优化一下这个情况”
- “帮我调低功耗”

这些请求都不应该直接进入 runtime，除非目标对象和约束已经明确。

## 实时上下文

判路接口使用的上下文来源与现有聊天接口保持一致，至少包括：

- 当前导入范围内 GPU 状态
- 当前系统资源摘要
- 当前 GPU 进程摘要

这样 LLM 的判断基于真实环境，而不是脱离上下文的纯文本分类。

## 错误处理

### LLM 未配置

`dispatch` 接口不做静默 fallback。

如果 LLM 未配置、调用失败、返回非 JSON，接口直接返回显式错误。前端将该错误转换成线程中的明确失败消息，例如：

- `AI 判路失败，请检查模型配置。`
- `AI 判路结果格式错误。`

### 聊天流失败

当 `dispatch` 已返回 `chat + stream`，但后续聊天流失败时，前端继续沿用现有聊天流错误提示，不补本地规则分流兜底。

### runtime 启动失败

当 `dispatch` 已返回 `runtime`，但 runtime session 创建失败时，继续沿用现有 runtime 错误呈现逻辑。

## 前端改动要点

### 需要删除

- `frontend/src/lib/agentWorkbenchIntent.js`
- `frontend/src/lib/agentWorkbenchIntent.test.js`
- `pendingRouteConfirm` 相关状态
- `resolveRouteConfirm` 相关流程
- route confirm 卡片生成逻辑
- `AgentThread` 中与 `choose-route` 相关的事件链

### 需要新增

- `dispatchAiWorkbenchMessage` API 封装
- workbench 提交链路的新分流处理

### 新的提交流程

1. 用户发送消息
2. 前端将用户消息插入线程
3. 前端调用 `dispatch`
4. 根据响应：
   - `chat + inline`：插入一条 assistant message
   - `chat + stream`：打开现有 chat stream
   - `runtime`：启动现有 runtime session

## 后端改动要点

### Schema

新增工作台判路请求/响应模型，至少包含：

- 请求：
  - `message`
- 响应：
  - `route_kind`
  - `reply_mode`
  - `reply`
  - `message`

### API

在 `backend/app/api/ai.py` 中新增 `dispatch` 接口，职责只有：

1. 加载实时上下文
2. 调用 LLM 判路
3. 返回结构化结果

它不直接启动 runtime，也不直接复用聊天流输出文本。

### Service

在 `backend/app/services/llm.py` 中新增一个专用方法：

- `dispatch_workbench_message(...)`

该方法负责：

1. 组装判路提示词
2. 调用模型
3. 解析 JSON
4. 做最小结构校验

## 测试策略

### 后端

新增 API 测试覆盖以下场景：

1. 明确问答请求返回 `chat + stream`
2. 模糊请求返回 `chat + inline`
3. 明确执行请求返回 `runtime`
4. LLM 未配置返回显式错误
5. 模型输出非 JSON 返回显式错误

### 前端

新增或更新 workbench 测试覆盖以下场景：

1. 提交输入时先调用 `dispatch`
2. `chat + inline` 时直接追加助手消息
3. `chat + stream` 时调用现有 chat stream
4. `runtime` 时调用现有 runtime session 启动接口
5. 不再存在 route confirm 交互链

### 结构测试

更新结构测试，确保：

- 不再依赖 `agentWorkbenchIntent.js`
- 不再存在 `choose-route`
- 不再存在 `pendingRouteConfirm`

## 验收标准

满足以下条件即视为完成：

1. AI 助手页面不再出现“按解释处理 / 按执行处理”的二次确认
2. 用户只使用一个输入框即可完成问答、追问和执行发起
3. 模糊请求会在聊天线程里收到助手追问
4. 明确执行请求仍然走 runtime 审批执行链
5. 前端已删除本地关键词判路器
6. 判路失败时系统明确报错，不引入静默 fallback
