# 2026-04-09 AI 助手执行账本重构设计

## 背景

当前 `frontend/src/views/AIAssistant.vue` 的“执行控制”页虽然已经接入 goal runtime session，但主视觉仍停留在“输入框 + 按钮 + 简单 timeline”的第一版控制台形态。页面能发起会话，也能看到少量事件，但仍有三个核心问题：

1. 执行过程不可视化。当前右侧并不存在真正的执行账本，只有薄弱的 timeline 列表，无法清晰表达 agent 当前跑到哪一轮、哪一步、卡在什么地方。
2. LLM 可观测性不足。现有 runtime 事件只覆盖 `GoalParsed / PlanCreated / StepStarted / StepCompleted / AwaitingApproval / PlanRevised / SessionFailed / SessionCompleted` 这些粗粒度节点，没有记录每次 LLM 请求、响应、解析结果和失败原因。
3. 页面主次关系不对。左侧输入与右侧轨迹没有形成“控制 + 观察”的稳定双栏，首屏仍然更像动作面板，而不是可调试的 agent 运行台。

用户目标已经明确：

- 页面采用稳定双栏。
- 右侧以“调试级事件账本”为主角。
- 不只展示大体流程，而要展示每一步 LLM 调用事件。
- 默认展示摘要，点击后展开原始 prompt / response / arguments / error。

## 目标

- 将 AI 助手执行页重构为“左侧 Control Dock + 右侧 Execution Ledger”的稳定双栏工作台。
- 将 runtime 事件模型升级为可观测的分层事件流，覆盖 LLM 推理、计划生成、审批、执行、失败和重规划。
- 让右侧账本能以轮次和事件卡的方式解释 agent 在做什么，而不是只罗列 event type。
- 保持页面对普通用户可读：默认摘要、关键事件高亮、历史事件折叠。

## 非目标

- 本轮不重做聊天解释页和模型配置页的信息架构，只重构 `AIAssistant.vue` 的执行控制子页。
- 本轮不引入额外的 mock / fallback 伪事件来“补好看”，所有账本内容必须来自真实 runtime 事件。
- 本轮不实现跨 session 的历史检索工作台，只关注当前 session 的执行可视化。

## 设计结论

最终采用 `方案 A · 调试账本台`：

- 左侧保留输入与控制操作。
- 右侧常驻事件账本，作为页面主叙事面。
- 事件账本以轮次和时间组织，支持关键事件高亮和详情展开。

放弃其他方向的原因：

- `方案 B · 上控下账本`：执行账本仍拿不到主视觉位置，控制与观察继续抢纵向空间。
- `方案 C · 原始日志台`：信息虽全，但太像开发者控制台，普通操作态压迫感强，不利于审批和执行对象摘要并入。

## 信息架构

执行控制页重构为两个主区域。

### 左栏：Control Dock

职责是“发起”和“继续”，不负责承载细碎执行细节。

包含：

- 目标输入区
- 快捷指令 chip
- 权限模式选择
- 风险确认
- 主动作按钮：`创建会话` / `批准并继续执行`
- 当前会话摘要卡
  - session id
  - 当前状态
  - 待审批动作数
  - 最近错误摘要

左栏的设计原则：

- 在任何状态下都保持高度稳定。
- 即使右侧账本滚动很长，左侧发起和审批动作也不应被挤走。
- 左侧只显示“当前最关键的控制事实”，详细执行内容全部交给右侧账本。

### 右栏：Execution Ledger

右栏是页面主角，用于解释 agent 的真实执行过程。

包含：

- 固定顶部的运行总览条
- 轮次分组的事件账本
- 每条事件卡的摘要与可展开详情

右栏回答三个问题：

- Agent 现在跑到哪一步？
- 最近发生了什么？
- 它为什么做出当前决定？

## 交互骨架

### 页面空状态

没有 session 时，右侧不留白，而是显示完整的“待开始账本”框架：

- 总览条：`未开始`
- 空状态卡：
  - 目标解析会出现在这里
  - LLM 请求/响应会按轮次记录在这里
  - 审批与执行结果会按事件流落在这里

这样在创建会话前后，页面的双栏骨架不发生突变。

### 会话创建后

- 左栏进入“当前会话”状态。
- 右栏立即载入当前 session 的事件账本。
- 若 session 进入 `awaiting_approval`，左栏主按钮切为“批准并继续执行”，右栏账本顶部同步高亮待审批事件。

### 详情展开

每条事件卡默认只显示摘要信息。点击后展开详情区。

详情区按区块展示：

- Request
- Response
- Action
- Result

原始信息默认折叠，但一旦展开必须可完整查看，不做额外隐藏。

## 事件账本设计

### 组织方式

事件账本按 `round + sequence + timestamp` 组织，而不是简单平铺。

一轮典型执行包含：

1. 目标理解
2. 上下文采样
3. LLM 请求
4. LLM 响应
5. 结构化计划提取
6. 工具/能力调用
7. 结果、失败或重规划

如果发生失败并进入下一轮，则账本显示 `Round 2`、`Round 3`，明确指出 agent 是在哪一轮修正了方案。

### 账本顶部总览条

总览条固定在右栏顶部，滚动时保持可见。

显示字段：

- 当前状态
- 当前 session id
- 事件总数
- LLM 调用次数
- 是否等待审批
- 最近错误
- 本次运行耗时

总览条的目的不是装饰，而是让用户在滚动长账本时仍能保持全局感。

### 事件卡展示规则

每条事件卡默认显示：

- 事件类型标签
- 所属轮次
- 时间
- 状态
- 一行摘要
- 关联对象

点击展开后显示：

- prompt / response 原文
- 结构化计划
- capability 名称与 arguments
- 执行结果
- 错误详情
- 耗时

### 高亮策略

以下事件做高亮展示：

- 最新 LLM 响应
- 当前待审批动作
- 最近一次失败事件
- 最近一次重规划事件
- 最终完成结果

其他历史事件保持紧凑卡片形式，避免账本变成长日志墙。

### 事件类型分层与配色

事件会按语义分层：

- `LLM`：紫蓝色
  - `LLMRequestPrepared`
  - `LLMResponseReceived`
  - `LLMCallFailed`
- `Planning`：青色
  - `GoalParsed`
  - `ContextSnapshotCaptured`
  - `PlanCreated`
  - `LLMPlanExtracted`
  - `PlanRevised`
  - `RuleFallbackUsed`
- `Approval`：琥珀色
  - `AwaitingApproval`
  - `ApprovalAccepted`
  - `ApprovalRejected`
- `Execution Success`：绿色
  - `StepStarted`
  - `StepCompleted`
  - `SessionCompleted`
- `Failure`：红色
  - `StepFailed`
  - `SessionFailed`

配色目的仅是快速识别语义层，不依赖纯颜色传达状态，仍需搭配文字标签。

## 后端 runtime 设计调整

### 当前状态

当前 runtime 事件过于粗粒度：

- `GoalParsed`
- `PlanCreated`
- `StepStarted`
- `StepCompleted`
- `AwaitingApproval`
- `PlanRevised`
- `SessionFailed`
- `SessionCompleted`

同时 `parse_goal_message()` 中当前并未真正使用 LLM 推理链，`llm_service` 仍被丢弃，无法生成用户要求的调试级 LLM 事件。

### 新的事件层级

事件流升级为三层：

#### Session 层

- `SessionStarted`
- `SessionCompleted`
- `SessionFailed`

#### Reasoning 层

- `ContextSnapshotCaptured`
- `LLMRequestPrepared`
- `LLMResponseReceived`
- `LLMPlanExtracted`
- `PlanRevised`
- `RuleFallbackUsed`
- `LLMUnavailable`
- `LLMCallFailed`

#### Execution 层

- `AwaitingApproval`
- `ApprovalAccepted`
- `ApprovalRejected`
- `StepStarted`
- `StepCompleted`
- `StepFailed`

### 事件 payload 结构

每条事件至少包含：

- `event_type`
- `timestamp`
- `round_index`
- `sequence`
- `source`
- `summary`

按需补充：

- `duration_ms`
- `prompt_preview`
- `prompt_full`
- `response_preview`
- `response_full`
- `structured_plan`
- `arguments`
- `result`
- `error`
- `related_entities`

原则：

- 默认展示用 `summary` 和 `*_preview`
- 调试展开用 `*_full`
- 不做 silent truncation 伪成功。若内容太大，应明确存储裁剪标记或按字段边界裁剪，并在 UI 中说明。

### LLM 调用埋点

如果 runtime 具备 LLM 能力：

- 真正记录每次请求准备、响应接收、结构化提取和失败。
- 明确记录模型名、输入摘要和输出摘要。

如果 runtime 当前不可用 LLM：

- 不伪造 LLM 事件。
- 显式记录 `LLMUnavailable` 或 `RuleFallbackUsed`。
- 账本中直接说明本轮使用规则解析而非模型推理。

这与仓库的 “No Silent Fallbacks” 约束保持一致。

## 前端组件拆分

### 页面层

`frontend/src/views/AIAssistant.vue` 只保留页面级状态组装，不再内联整个执行区 UI。

### 新组件

- `frontend/src/components/agent/AgentControlDock.vue`
  - 左栏输入与控制区
- `frontend/src/components/agent/AgentExecutionLedger.vue`
  - 右栏账本容器
- `frontend/src/components/agent/AgentRunOverviewBar.vue`
  - 账本顶部运行总览
- `frontend/src/components/agent/AgentLedgerRound.vue`
  - 单轮事件组
- `frontend/src/components/agent/AgentLedgerEventCard.vue`
  - 单条事件卡

### 现有组件处理

现有 `frontend/src/components/agent/AgentSessionTimeline.vue` 不再作为主展示组件。本轮直接新增 `AgentExecutionLedger.vue` 及其子组件，并让 `AIAssistant.vue` 改为使用新账本组件；旧 timeline 组件降级为待删除兼容文件，待实现稳定后物理清理。

不接受的路径：

- 保留“旧 timeline + 新账本”双轨展示
- 只在旧 timeline 外面包一层标题和统计条

## 数据流

### 获取与刷新

执行控制页只刷新当前 session，不重刷整页其他域数据。

刷新策略固定为：

- 创建会话后立即拉取一次 session 和 events
- 当状态为 `running` 或 `awaiting_approval` 时，每 2 秒轮询一次
- 状态进入 `completed / failed / aborted` 后停止自动轮询
- 提供手动“刷新账本”入口

### 前端派生数据

账本 UI 需要在前端派生：

- `eventCount`
- `llmCallCount`
- `currentRound`
- `latestError`
- `awaitingApproval`
- `durationMs`
- `highlightedEvents`
- `groupedRounds`

这些派生逻辑应该抽到独立 helper，不直接散落在 `AIAssistant.vue` 模板里。

## 异常处理

失败必须可见，不允许只在按钮旁吐一句提示后丢失。

### Runtime 失败

- LLM 请求失败 -> `LLMCallFailed`
- 计划提取失败 -> `SessionFailed` 或专门的 `PlanExtractionFailed`
- 能力执行失败 -> `StepFailed` / `SessionFailed`

### 前端刷新失败

- 右侧账本顶部显示 `账本刷新失败`
- 保留已有账本数据
- 不清空当前 session 视图

### 审批拒绝

- 落 `ApprovalRejected`
- session 状态进入 `aborted`
- 右侧账本显示明确的终止原因，而不是只显示状态字样

## 测试策略

### 后端

新增或扩展测试以验证：

- 事件顺序正确
- `round_index / sequence / source` 正确写入
- LLM 可用与不可用两条路径都显式产生日志事件
- 审批流和拒绝流都能正确写入事件
- 失败时错误会落进事件 payload

### 前端结构测试

新增结构测试以约束：

- `AIAssistant.vue` 使用 `AgentControlDock` 和 `AgentExecutionLedger`
- 账本存在 `RunOverviewBar / Round / EventCard` 三层结构
- 旧 `AgentSessionTimeline` 不再作为主展示组件

### 前端交互测试

新增测试以验证：

- 运行中自动轮询
- 终态停止轮询
- 展开/折叠详情
- 审批后账本继续推进
- 刷新失败横幅不会清空现有账本

## 实施边界

本设计要求后端事件模型和前端账本 UI 同步升级。只改前端样式、不补事件模型，不算完成；只补事件模型、不重构执行页，也不算完成。

交付标准：

- 用户能在执行页右侧清楚看到每一步 agent 行为。
- 用户能展开查看 LLM prompt / response 与动作参数。
- 用户能区分当前卡在 LLM、审批、执行还是失败。
- 页面首屏主次关系清楚，控制区稳定，账本是主角。
