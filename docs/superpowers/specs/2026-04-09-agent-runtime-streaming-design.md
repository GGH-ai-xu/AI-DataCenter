# 2026-04-09 AI 助手与 Goal Runtime 流式输出设计

## 背景

当前平台的 LLM 调用链已经具备两条真实业务路径：

- `frontend/src/views/AIAssistant.vue` 中的 AI 问答助手，通过 `backend/app/api/ai.py` 调用 `backend/app/services/llm.py` 的 `chat()`
- AI 执行控制台中的目标驱动 runtime，通过 `backend/app/api/agent_runtime.py`、`backend/app/services/goal_runtime/service.py` 和 `backend/app/services/goal_runtime/reasoning_trace.py` 调用 `LLMService.generate_control_plan()`

这两条链路现在都属于“一次性返回”模式：

1. 前端发起普通 HTTP 请求
2. 后端等待模型完整返回
3. 前端一次性收到完整文本或完整规划结果

这一模式在功能上可用，但已经不满足用户对可用性和可观察性的要求：

1. AI 问答助手在模型生成阶段只有等待，没有逐步输出体验。
2. 执行控制台虽然已经有 session 和执行账本，但规划阶段仍然是黑盒，用户看不到模型正在形成中的推理文本。
3. 现有 execution ledger 只能在模型完成后再展示结果，无法做到“边规划、边入账、边解释”。
4. 如果简单把每个 token/chunk 都持久化为事件，虽然能回放全过程，但会造成不必要的高频写入和存储膨胀。

用户已经明确本轮方向：

- AI 问答助手和执行控制台都要支持真实流式输出
- 执行控制台必须先创建 session，再在同一个 session 内持续流式推进
- 执行控制台需要同时看到“规划生成中的文本预览”和“结构化账本事件”
- 流式中间文本不能导致存储爆炸，因此后端只保留最新快照和最终完整结果，不持久化每个增量 chunk

## 目标

- 为 AI 问答助手增加真实流式输出通道，而不是等待完整回答后一次性返回
- 为 goal runtime 增加“session 先创建，规划与账本持续推送”的流式执行链
- 让执行控制台右侧账本在规划阶段就可以实时刷新，而不是等模型结束后再整体回填
- 在不造成高频事件膨胀的前提下，支持断线恢复和当前规划进度恢复
- 明确区分“支持流式”和“不支持流式”的模型能力，不做假流、伪流或静默退化

## 非目标

- 本轮不把整个平台改成统一的通用事件总线协议
- 本轮不引入逐 token 的永久持久化回放
- 本轮不重做 energy / scheduler / governance 等其他 LLM 调用页面的交互，只覆盖 AI 问答助手和执行控制台
- 本轮不使用 mock token 回放去伪造流式体验

## 用户确认的关键约束

### 1. 流式范围

流式输出同时覆盖：

- AI 问答助手
- AI 执行控制台的规划阶段

### 2. 执行控制台 session 生命周期

执行控制台采用“先创建 session，再持续推流”的模式：

1. 用户点击创建会话
2. 后端立即返回 `session_id`
3. 前端立刻连接该 session 的流式通道
4. 规划文本、账本事件、审批状态和最终结果都落在同一个 session 中

### 3. 流式中间文本持久化策略

用户明确不接受逐 chunk 增量持久化。

本轮采用：

- 只持久化当前最新快照
- 最终完成时再持久化完整结果

也就是说，流式增量只用于实时展示，不会直接写成 append-only 历史事件。

## 方案对比

### 方案 A：统一能力下的双通道流式 runtime

- 问答助手增加独立 SSE 通道
- 执行控制台新增 session stream 通道
- goal runtime 在 session 内同时推送流式规划文本和结构化账本事件

优点：

- 问答和执行控制使用一致的流式能力模型
- 执行控制不会拆成“临时文本流”和“最终 session 账本”两套状态
- 能与现有 goal runtime session / event / ledger 结构直接衔接

缺点：

- 后端与前端都需要增加新的流式层

### 方案 B：问答真流式，执行控制临时流式

- 问答助手走真实 stream
- 执行控制台只在前端显示临时流式文本，session 仍等完整结果再写入

优点：

- 改造量更小

缺点：

- 会形成“临时流式状态”和“正式 runtime 状态”两套来源
- 调试时容易出现前端看到的实时文本与最终账本不对齐的问题

### 方案 C：统一事件总线协议

- 问答与执行控制全部只消费统一事件流
- 文本、账本、状态都由前端自己从 event frame 组装

优点：

- 最彻底、最统一

缺点：

- 超出本轮范围，落地风险明显偏高

## 设计结论

本轮采用 `方案 A`。

原因如下：

- 它能够让问答与执行控制都获得真实流式体验
- 它不会把执行控制拆成两套状态体系
- 它能复用现有 goal runtime 的 session、event、ledger 结构，而不是推翻重来
- 它比统一事件总线方案更收敛，更适合在当前仓库中分阶段落地

## 总体架构

### 1. AI 问答助手

新增独立的流式问答接口：

- 保留现有非流式问答接口
- 新增流式问答 SSE 接口，返回 `text/event-stream`

前端发送问题后：

1. 立即插入一条 assistant 占位消息
2. 连接问答流
3. 持续接收文本 delta 与 snapshot
4. 最终收到完整文本和 suggestions

### 2. 执行控制台

执行控制台拆成两个职责明确的接口：

- `POST /sessions`：只负责创建 session
- `GET /sessions/{session_id}/stream`：持续输出该 session 的流式规划与运行事件

前端行为：

1. 创建 session
2. 连接 session stream
3. 实时更新规划文本预览
4. 实时增量写入 execution ledger
5. 在审批点或终态停留在同一 session 中继续交互

### 3. 存储

流式规划文本不进入 append-only 事件表。

后端只保留：

- 当前最新规划文本快照，可覆盖更新
- 最终完整 LLM 响应与结构化计划，进入正式事件账本

## 后端协议设计

### AI 问答助手流式接口

新增一个流式问答接口，逻辑位置仍归属 `backend/app/api/ai.py`。

接口形式固定为：

- `POST /api/ai/chat/stream`
- `Content-Type: text/event-stream`

之所以使用 `POST`，是因为问答输入天然需要请求体，不适合塞进 query string。

推荐事件帧：

- `start`
  - 表示本次回答正式开始
- `delta`
  - 本次新增的文本片段
- `snapshot`
  - 当前累计文本快照
- `completed`
  - 最终完整文本和 suggestions
- `error`
  - 终止性错误

保留现有普通 `chat` 接口，供非流式模式或兼容路径使用。

### Goal Runtime Session Stream 接口

在 `backend/app/api/agent_runtime.py` 中新增 session 级流式接口。

现有接口职责调整为：

- `POST /sessions`
  - 只创建 session，并立刻返回 `session_id`
- `GET /sessions/{session_id}`
  - 查询当前 session summary
- `GET /sessions/{session_id}/events`
  - 查询已持久化账本事件
- `GET /sessions/{session_id}/stream`
  - 查询该 session 的流式事件

推荐的 stream event 类型：

- `session_started`
- `planner_delta`
- `planner_snapshot`
- `runtime_event`
- `session_status`
- `completed`
- `error`

其中：

- `planner_delta` 只用于实时展示，不落 append-only 历史库
- `planner_snapshot` 用于当前进度恢复
- `runtime_event` 对应正式 execution ledger 事件

### 前端传输方式

虽然流格式采用 SSE 帧，但前端不能依赖浏览器原生 `EventSource`。

原因是当前平台认证依赖 `Authorization: Bearer ...` 请求头，而原生 `EventSource` 无法稳定自定义该 header。

因此前端流式实现固定为：

- 使用 `fetch`
- 携带现有 Bearer token
- 通过 `ReadableStream` 读取响应体
- 在前端解析 `text/event-stream` 帧

这意味着本轮的“流式协议”是 SSE frame format，而不是浏览器 `EventSource` API 绑定。

## 模型能力探测

`backend/app/services/llm.py` 需要新增显式的流式能力接口，而不是让调用方猜测或伪装退化。

建议新增：

- `supports_chat_stream()`
- `supports_control_plan_stream()`
- `chat_stream()`
- `generate_control_plan_stream()`

若当前模型或 provider 不支持真实 stream：

- 明确暴露该能力缺失
- 前端必须知道当前是非流式模式
- 禁止通过延时切片或伪 token 回放去模拟流式体验

## Goal Runtime 内部状态机

### session 对外状态

对外仍沿用当前主状态：

- `running`
- `awaiting_approval`
- `completed`
- `failed`
- `aborted`

### session 内部细分阶段

为前端和 stream 增加更细粒度的 `live_phase`：

- `planning`
- `executing`
- `awaiting_approval`
- `completed`
- `failed`
- `aborted`

这样可以在不打乱现有 session status 语义的前提下，让 UI 明确区分“模型正在规划”和“步骤正在执行”。

### session 创建顺序

当前 `GoalRuntimeService.start_session()` 是一次性完成规划和执行。

本轮要改为：

1. 立刻创建 session 行
2. 初始 `status=running`
3. 初始 `live_phase=planning`
4. 异步启动规划任务
5. 规划过程中持续向 stream 推送文本与 runtime event
6. 规划完成后进入：
   - `awaiting_approval`，如果需要审批
   - `running + executing`，如果可直接执行
7. 最终进入终态

`POST /sessions` 的职责因此变成“创建并启动”，而不是“等待会话完整运行完再返回”。

## 流式文本持久化

### 不做的事

本轮明确不做：

- 每个 delta/chunk 都写一条 event
- 每个 token 都写入 event store
- 把文本流本身当作历史账本主存储

### 要做的事

引入 session 级的流式状态存储，逻辑字段建议包括：

- `session_id`
- `stream_kind`
- `latest_text`
- `latest_char_count`
- `updated_at`
- `revision`

这里的核心语义是：

- `latest_text` 永远只表示当前最新快照
- 新快照写入时覆盖旧值
- 不追加历史版本

### 最终完整结果

模型完成后，最终完整结果仍然进入正式账本事件：

- `LLMResponseReceived.payload.response_full`
- `LLMPlanExtracted.payload.structured_plan`

如果规划失败：

- 写 `LLMCallFailed`
- 必要时带上 `response_partial`

## 快照落库节流

为了控制写入频率，快照只在满足阈值时持久化。

推荐阈值采用双条件任一满足：

- 距离上次落库超过 `800ms`
- 或累计新增超过 `240` 个字符

这样可以兼顾：

- 长输出时的可恢复性
- 对数据库写入频率的控制

SSE 仍可以比落库频率更高地持续向前端推送 delta。

## 前端设计

### AI 问答助手

问答助手在发送消息后，前端不再等待完整回复，而是：

1. 立刻插入一条 assistant 占位消息
2. 建立问答 stream
3. 接收 `delta` 时追加内容
4. 接收 `snapshot` 时以快照覆盖当前消息内容
5. 接收 `completed` 时补全最终建议
6. 接收 `error` 时终止并显示明确错误

这能让问答区获得真实流式体验，并保留最终 suggestions。

### 执行控制台

执行控制台保持既有双栏布局：

- 左侧 `AgentControlDock`
- 右侧 `AgentExecutionLedger`

但右侧账本顶部需要新增一个 `PlannerLivePanel`：

1. 位于 overview bar 下方
2. 显示当前规划阶段
3. 显示当前最新规划文本快照
4. 在规划完成后可收纳为摘要或最终版本

右侧信息层次变为：

1. `AgentRunOverviewBar`
2. `PlannerLivePanel`
3. 关键事件
4. 轮次明细

### 前端状态拆分

执行控制台的前端状态分为两层：

#### 正式 runtime 状态

- `runtimeSession`
- `runtimeEvents`
- `ledgerRefreshError`

#### 流式规划状态

- `plannerStreamActive`
- `plannerLiveText`
- `plannerLiveRevision`
- `plannerLivePhase`
- `plannerStreamError`

这两层必须分离：

- `runtimeSession/runtimeEvents` 表示正式可回放的 session 状态
- `plannerLive*` 表示当前进行中的流式文本状态

### 前端刷新策略

现有 `agentRuntimeSessionPolling` 不删除，但角色降级。

新的原则是：

- `stream first`
- `polling for recovery only`

也就是说：

- SSE 正常工作时，以流为主，不依赖轮询
- SSE 断线或恢复失败时，再启动 polling 去校准 session 与事件列表

### 账本更新策略

执行账本不应在流式期间频繁全量重刷。

推荐策略：

- 收到 `runtime_event` 时，直接增量 append 到本地 `runtimeEvents`
- 收到 `session_status` 时，merge 到本地 `runtimeSession`
- 仅在断线恢复或校准时，才重新拉取全量 `events`

这样 execution ledger 才能保持顺滑，不闪动、不整块重算。

### 审批点行为

当规划流推进到审批点时：

- 后端 session 进入 `awaiting_approval`
- 左侧显示待审批动作并解锁批准按钮
- 右侧高亮 `AwaitingApproval`
- `PlannerLivePanel` 停留在最终规划文本

用户点击批准后，执行阶段应继续沿同一个 session stream 推进，而不是切换成另一套临时状态。

## 错误处理

### 模型调用前错误

包括：

- LLM 未配置
- 模型或 provider 不支持流式能力
- 请求参数非法

处理原则：

- 明确报错
- 不创建伪流
- 不伪装成“空输出但成功”

### 流中断错误

包括：

- 上游 provider 中途断连
- 网络异常
- 超时

处理原则：

- stream 发出 `error`
- session 状态同步到失败或中断态
- 前端结束 loading，并给出恢复提示

### 结构化解析错误

包括：

- 模型输出流完成，但结构化提取失败

处理原则：

- 写入正式 failure event，例如 `LLMCallFailed`
- execution ledger 高亮失败事件
- 不吞错，不假装成功进入执行阶段

### 前端连接错误

包括：

- SSE 建连失败
- 中途断开
- 页面切换或销毁

处理原则：

- 明确展示 `stream disconnected / recovering`
- 退回 polling 恢复
- 不伪造“仍在流式生成”

## 测试边界

### 后端单元测试

需要覆盖：

- `LLMService.chat_stream()` 的增量产出行为
- `generate_control_plan_stream()` 的增量产出与最终结构化结果
- 非流式模型的能力判定
- 流式快照的覆盖式持久化，不发生 append-only 膨胀

### 后端接口测试

需要覆盖：

- AI 问答 stream 的事件顺序
- runtime session 创建后可立即返回 `session_id`
- session stream 可输出 `planner_delta / planner_snapshot / runtime_event / completed`
- 审批前后 stream 仍保持 session 一致性

### 前端纯函数与控制器测试

需要覆盖：

- 流式 delta + snapshot 的文本拼接与覆盖
- runtime_event 的增量写账本
- stream 断线后自动切换到 polling recovery
- 非流式模式下的显式能力提示

### 前端结构测试

需要覆盖：

- `AIAssistant.vue` 使用新的 live panel
- 问答区不再只依赖一次性普通 POST 模式
- 执行页在 control tab 下同时具备：
  - control dock
  - planner live panel
  - execution ledger

## 落地顺序

为了降低改造风险，本轮实施顺序建议分三段：

### 第一阶段：问答助手流式化

- 为 `LLMService` 增加 chat stream 能力
- 新增问答 SSE 接口
- 让 `AgentChatPane` 支持流式回答

### 第二阶段：执行控制台流式化

- 调整 session 创建时序
- 新增 session stream 接口
- 让 execution ledger 接入实时 runtime event
- 新增 `PlannerLivePanel`

### 第三阶段：恢复与收口

- 增加快照覆盖式持久化
- 增加 stream 断线恢复
- 校准 polling recovery
- 补齐完整回归测试

## 结果预期

落地完成后，平台将具备以下体验：

- AI 问答助手可以真正逐步输出回答
- 执行控制台在创建 session 后，立即进入实时规划状态
- 用户可以同时看到：
  - 模型正在形成中的规划文本
- 结构化 runtime 账本事件
  - 审批点和执行结果
- 存储层不会因流式输出而爆炸增长
- 不支持流式的模型会被明确识别，而不是通过伪流掩盖真实能力差异
