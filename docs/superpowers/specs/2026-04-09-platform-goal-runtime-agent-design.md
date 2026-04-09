# 平台内目标驱动 Agent Runtime 设计

日期：2026-04-09

## 背景

当前 AI-DataCenter 后端已经具备一批分散但真实可用的治理能力：

- 统一运行时接入与切换，见 [backend/app/main.py](/mnt/e/code/ai-datacenter/backend/app/main.py) 和 [backend/app/services/runtime_provider_manager.py](/mnt/e/code/ai-datacenter/backend/app/services/runtime_provider_manager.py)
- 调度与预算治理，见 [backend/app/services/scheduler.py](/mnt/e/code/ai-datacenter/backend/app/services/scheduler.py)
- AI 控制台规划与执行，见 [backend/app/services/ai_control.py](/mnt/e/code/ai-datacenter/backend/app/services/ai_control.py)
- 公平治理分析，见 [backend/app/services/governance.py](/mnt/e/code/ai-datacenter/backend/app/services/governance.py)
- 能耗分析与优化建议，见 [backend/app/services/energy_analytics.py](/mnt/e/code/ai-datacenter/backend/app/services/energy_analytics.py)
- LLM 能力层，见 [backend/app/services/llm.py](/mnt/e/code/ai-datacenter/backend/app/services/llm.py)

这些能力已经足够支撑“平台会思考、会执行、会解释”的产品方向，但当前系统本质上仍然是多个服务围绕 `AppState` 协作：

- 调度、控制台、治理、能耗分析各自维护自己的输入上下文和动作模型
- 规划与执行链路重复存在，缺少统一计划对象
- 失败后缺少显式的步骤级重规划机制
- 审批、能力选择、运行边界、事件轨迹并不是 runtime 的一等公民

用户目标不是继续给现有服务补一个“更聪明的控制台”，而是把平台重构为一个真正的、平台内可控的目标驱动 Agent runtime：

- 用户用自然语言下达平台内目标
- runtime 自行理解目标、生成计划、选择能力、执行与重规划
- 高权限模式下具备强自治
- 低权限模式下只要涉及实时操作就必须先征得用户同意
- 全程可解释、可审计、可回放，不退化成黑盒代理

## 目标

本次设计的目标如下：

- 将现有平台能力统一收编到一个平台内目标驱动 Agent runtime
- 支持“自然语言输入 -> 结构化目标 -> 步骤计划 -> 执行 -> ReAct -> 结束”的单次任务会话
- 明确区分高权限模式与低权限模式
- 让所有平台能力以标准化 capability 形式暴露给 runtime，而不是继续散落为 API 直调
- 将失败处理、局部重规划、审批插入、事件轨迹和审计回放纳入统一 runtime 模型
- 保持平台边界清晰，避免系统滑向通用代理或桌面自动化代理

## 非目标

本次设计不做以下事项：

- 不将 Agent 扩展为平台外通用代理
- 不允许 runtime 越过平台内领域能力，直接依赖前端模拟点击完成核心任务
- 不构建长期驻留的后台自治目标系统
- 不让 LLM 直接接管底层执行器
- 不把本次工作扩展为“重写整套后端业务逻辑”
- 不在本次设计中引入完整通用 memory、工具市场、跨会话自主学习系统

## 用户确认的设计结论

### 1. 作用域边界

Agent 只处理 AI-DataCenter 平台内部事务，不扩展到平台外通用任务。

### 2. 输入形式

用户以自然语言为主提出要求，runtime 内部负责将自然语言转换为结构化目标。

### 3. 会话模型

一次用户指令对应一个单次任务会话：

- 接收目标
- 规划并执行
- 完成后结束

不做持续驻留的长期目标代理。

### 4. 执行通道

核心任务优先走平台内部的后端领域能力，不依赖 UI 驱动作为主要执行路径。

### 5. 权限模型

需要同时支持两种权限模式：

- 高权限模式
- 低权限模式

其中低权限模式的关键约束已经明确：

- 只要不是纯分析，而是会触发实时操作，就必须先征得用户同意

### 6. 自治级别

用户要求 runtime 具备强 ReAct 能力：

- 高权限模式下，如果原计划失败，runtime 可以在不再次询问的前提下，自主改用另一种平台内实现路径
- 条件是：仍然满足原目标、原约束和平台边界

## 总体方案

本次采用 `Goal Runtime` 方案，而不是继续沿用“意图分类 + API 分发”的命令路由器模式。

### 方案核心

将平台重构为一个围绕以下主链运行的目标执行 runtime：

`Goal Input -> Goal Parser -> Planner -> Capability Selector -> Plan Validator -> Approval Gate -> Step Executor -> Result Synthesizer`

在 `Step Executor` 周围增加显式的 `Execution Supervisor`，为每个步骤提供强 ReAct 内循环：

`Observe -> Reason -> Act -> Check -> Replan`

这套方案的目标不是让系统“更像聊天机器人”，而是让平台具备一个统一的代理执行内核：

- 所有能力通过 capability 暴露
- 所有动作通过 plan 组织
- 所有重规划通过 event trail 留痕
- 所有权限差异通过 runtime 节点控制

### 为什么不采用更轻的 Command Router

如果只做命令路由器，短期内可以把自然语言映射到现有 API，但很快会再次遇到这些问题：

- 同一目标需要跨多个领域 API 协同
- 失败后没有统一的局部重规划入口
- 审批逻辑只能分散写在每个接口周围
- 新增能力后仍然需要继续堆 `if/else`

用户目标是“完整目标驱动 Agent runtime”，因此必须引入统一目标对象、统一计划对象和统一 capability 层。

## Runtime 核心架构

### 1. Goal Input

职责：

- 接收用户自然语言目标
- 创建单次任务会话
- 记录原始用户表述

它只负责接收，不做解释与规划。

### 2. Goal Parser

职责：

- 将自然语言解析为结构化目标
- 提炼作用域、约束、完成条件、终止条件、权限模式

它产出的结果是 `GoalSpec`，而不是具体执行步骤。

### 3. Planner

职责：

- 根据 `GoalSpec` 和当前平台状态生成初始 `ExecutionPlan`
- 只描述计划结构，不直接执行

它要为后续失败处理预留局部重规划入口。

### 4. Capability Selector

职责：

- 在 capability registry 中选择最合适的实现路径
- 根据 provider 能力、当前作用域和约束决定具体使用哪些 capability

这一步是 runtime 与具体领域能力的桥梁。

### 5. Plan Validator

职责：

- 校验参数是否合法
- 校验 capability 是否可用
- 校验动作是否在导入范围内
- 校验当前路径是否符合权限和平台规则

高权限模式不会跳过这一层。高权限只意味着 runtime 可以少问用户，不意味着可以越界。

### 6. Approval Gate

职责：

- 在低权限模式下，接住所有需要审批的实时操作
- 将计划切分为“已完成部分”和“待审批部分”
- 等待用户决定是否继续

审批不是一个 UI 按钮，而是 runtime 中的正式节点。

### 7. Step Executor

职责：

- 执行当前步骤绑定的 capability
- 返回结构化执行结果
- 不自己决定整体策略

### 8. Execution Supervisor

职责：

- 收集步骤结果和最新状态
- 做失败分类
- 决定继续、改道、重试、审批回插或终止
- 触发局部重规划

它是强 ReAct runtime 的核心。

### 9. Result Synthesizer

职责：

- 汇总最终执行结果
- 给出完成状态、失败原因、改道摘要、审批摘要
- 在任务完成后结束会话

## 三个一等公民对象

### 1. GoalSpec

`GoalSpec` 是对用户目标的标准化表示，描述“要达成什么”，不描述“怎么做”。

建议字段：

- `intent`: 用户原始意图与标准化后的目标语义
- `scope`: 当前主机、GPU、任务域、导入范围
- `constraints`: 用户显式约束和平台默认约束
- `permission_mode`: `high` 或 `low`
- `done_when`: 满足什么条件算完成
- `abort_when`: 满足什么条件必须终止

约束：

- `GoalSpec` 不包含具体 capability 名称
- `GoalSpec` 可以被 ReAct 多次重用
- 同一 session 内，`GoalSpec` 是全程稳定的真源之一

### 2. ExecutionPlan

`ExecutionPlan` 负责把 `GoalSpec` 变成可执行的步骤计划。

建议字段：

- `steps`
- `preconditions`
- `success_predicate`
- `fallback_paths`
- `approval_required`
- `replan_budget`

关键要求：

- 不是一次性文本计划
- 每一步都能被执行器消费
- 每一步都能被监督器修改或替换
- 必须支持只重规划“剩余步骤”，而不是整单重做

### 3. Capability

平台内每个可调用能力都必须以标准化 capability 形式注册。

建议字段：

- `name`
- `domain`
- `input_schema`
- `side_effect_level`
- `requires_scope`
- `supported_providers`

关键要求：

- runtime 不直接拼装 API 名称
- capability 必须可验证、可审计、可约束
- capability 必须能声明自己的副作用等级和 provider 兼容性

## Capability 分层

本次设计将 capability 分为 4 层。

### L1: Observe / Query

纯读取能力，不改变平台和真实资源状态。

示例：

- `runtime.snapshot.read`
- `tasks.list`
- `energy.metrics.read`

### L2: Analyze / Synthesize

基于已读数据进行分析、解释、规划、报告生成，但不直接触发实时副作用。

示例：

- `energy.report.generate`
- `governance.fairness.analyze`
- `agent.plan.generate`

### L3: Workspace Mutation

修改平台工作台状态，但不直接影响真实资源。

示例：

- `policy.draft.save`
- `agent.session.note`
- `workspace.preference.update`

### L4: Runtime Action

会直接影响真实主机、任务或治理状态的动作。

示例：

- `tasks.pause`
- `tasks.terminate`
- `scheduler.power_limit.set`
- `scheduler.run_once`

## 权限模型

### 低权限模式

低权限模式下：

- L1 / L2 直接允许
- L3 直接允许
- L4 必须经过 `Approval Gate`

关键约束：

- 只要 ReAct 产生了新的 L4 动作集合，就必须重新审批
- 不能复用不再覆盖当前动作集的旧审批

这里显式约定：

- 低权限模式只对“会影响真实资源或真实治理状态的实时操作”强制审批
- 不影响真实资源的工作台级写操作不纳入本次审批范围

### 高权限模式

高权限模式下：

- L1 / L2 / L3 / L4 都可以由 runtime 自主执行
- 但仍然必须经过参数校验、作用域校验、provider 能力校验和平台规则校验

高权限不意味着：

- 可以跨出导入范围
- 可以调用不受支持的 capability
- 可以跳过平台默认规则

### 非法路径

无论高权限还是低权限，以下情况都属于非法路径：

- 不在导入范围内
- provider 不支持
- 参数非法
- 目标与平台边界冲突

这类路径不能靠 ReAct 越权修复，只能：

- 请求用户修正目标
- 或直接终止本次会话

## 强 ReAct 执行模型

强 ReAct 的核心不是“让 runtime 多试几次”，而是让 runtime 在有边界的能力图里进行可追踪的局部重规划。

每个步骤执行后都进入以下内循环：

### 1. Observe

读取：

- capability 返回值
- 最新 runtime snapshot
- 资源状态变化
- 成功或失败信号

### 2. Reason

判断失败或变化属于哪类：

- 参数问题
- capability 不可用
- 作用域冲突
- 目标状态变化
- provider 能力缺失
- 可恢复执行异常

### 3. Act

基于分类决定：

- 继续后续步骤
- 同路径重试
- 换 capability
- 补前置步骤
- 进入审批
- 或直接终止

### 4. Check

确认新动作仍满足：

- 原始 `GoalSpec`
- 当前权限模式
- 导入作用域
- 平台规则

### 5. Replan

只重写剩余计划，不重做整个任务。

约束：

- 必须保留计划变化原因
- 必须有显式的重规划预算和停止条件

## 失败分类

### Recoverable Failure

允许通过 ReAct 继续推进的失败，例如：

- capability 当前不可用，但存在同域替代路径
- 参数需要重新补齐
- 目标状态变化导致剩余步骤失效

### Approval-Blocked Failure

本质不是技术失败，而是 runtime 进入了需要用户同意的分叉点，例如：

- 低权限模式下出现新的 L4 动作
- 原本是分析路径，重规划后变成真实执行路径

### Terminal Failure

必须终止会话的失败，例如：

- 不存在任何合法 capability 路径
- 重规划预算耗尽且没有新信息
- 目标本身与平台边界冲突

## 事件轨迹与审计回放

强 ReAct runtime 不能只存最终结果，必须保存 session event trail。

### 事件模型

每条用户指令对应一个 session，至少记录这些事件：

- `GoalParsed`
- `PlanCreated`
- `StepExecuted`
- `ApprovalRequested`
- `ApprovalResolved`
- `PlanRevised`
- `SessionCompleted`
- `SessionAborted`

### 设计要求

- 审批是事件，不是零散布尔值
- 计划变化是事件，不是覆盖式状态写入
- 最终页面既能看执行摘要，也能按 session 回放全流程

### 用户可见的回放能力

治理页面和 Agent 页面应能回放：

- 为什么生成这份计划
- 为什么切换 capability
- 哪一步需要审批
- 哪一步失败且不可恢复
- 最终为什么完成或终止

## 与现有代码的映射

本次重构不是推倒重来，而是围绕现有基础设施重组。

### 可以继续沿用的底座

- 运行时 provider 切换与探测： [backend/app/services/runtime_provider_manager.py](/mnt/e/code/ai-datacenter/backend/app/services/runtime_provider_manager.py)
- 导入范围与作用域控制： [backend/app/services/import_context.py](/mnt/e/code/ai-datacenter/backend/app/services/import_context.py)
- 实时采集与 runtime snapshot： [backend/app/main.py](/mnt/e/code/ai-datacenter/backend/app/main.py)

### 需要被 capability 化的现有能力

- 任务控制接口： [backend/app/api/tasks.py](/mnt/e/code/ai-datacenter/backend/app/api/tasks.py)
- 调度接口与预算接口： [backend/app/api/scheduler.py](/mnt/e/code/ai-datacenter/backend/app/api/scheduler.py)
- 能耗分析接口： [backend/app/api/energy.py](/mnt/e/code/ai-datacenter/backend/app/api/energy.py)
- AI 控制台接口： [backend/app/api/ai.py](/mnt/e/code/ai-datacenter/backend/app/api/ai.py)

### 需要被收编进 runtime 的现有服务

- `SchedulerEngine` 要从“策略+执行器”收敛为一组 capability 和 planning helpers
- `ai_control.py` 要从独立执行链收敛为 Goal Runtime 的一个入口层
- `GovernanceService` 和 `EnergyAnalytics` 要更多产出 L1/L2/L3/L4 capability，而不是各自维护独立编排

## 迁移原则

### 1. 先建 runtime 内核，再迁移业务能力

先完成：

- GoalSpec
- ExecutionPlan
- Capability registry
- Approval Gate
- Execution Supervisor
- Session event trail

再逐步把现有业务能力接进来。

### 2. 先覆盖平台内已有动作，不扩域

第一阶段只收编当前已经稳定存在的能力：

- 读取 runtime 状态
- 读取任务和治理信息
- 运行调度
- 调整预算
- 暂停 / 恢复 / 终止任务
- 限功率
- 生成报告和分析

### 3. 保持现有硬边界

重构期间不得引入：

- 静默 fallback
- 越权执行
- 无审计的自治动作
- 直接 UI 驱动替代领域能力

## 验证要求

设计落地后，至少要能验证以下场景：

### 1. 高权限自治改道

用户下达一个平台内实时目标后，原 capability 路径失败，runtime 能在不再次询问的前提下切换到另一条合法路径完成目标。

### 2. 低权限审批回插

用户下达分析型目标，ReAct 过程中产生新的 L4 动作，runtime 能暂停并请求审批，而不是直接执行。

### 3. 非法路径终止

当目标越过导入范围或 provider 不支持时，runtime 明确终止并说明原因，而不是继续猜。

### 4. Session 回放

用户能查看单次任务从目标解析、计划生成、执行、重规划到结束的完整事件链。

## 结论

本次设计将 AI-DataCenter 的平台侧智能治理能力从“多个服务协作”提升为“统一目标驱动 Agent runtime”。

最终形态不是通用代理，也不是简单命令路由器，而是一个具备以下特征的平台内代理执行内核：

- 目标一等公民
- 计划一等公民
- capability 一等公民
- 强 ReAct 但不越界
- 高低权限清晰分层
- 全流程可解释、可审批、可回放

这套设计能在不放弃现有后端基础设施的前提下，为后续实现真正的 Agent 化平台提供稳定骨架。
