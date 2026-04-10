# 集群作业让位、重排、回收与推进执行设计

日期：2026-04-11

## 1. 背景

当前项目已经具备以下能力：

- 统一任务模型已经落在现有 `JobSpec` 主链路上，支持 `training`、`inference_service`、`interactive_session`、`batch_compute`、`maintenance`。
- 提交链路已经打通：
  - `job.submit`
  - `cluster_control`
  - `scheduler_core`
  - `execution_orchestrator`
  - `server-agent job_runtime`
- 调度器已经能够消费一部分任务语义：
  - `task_kind`
  - `lifecycle_kind`
  - `service_ports`
  - `runtime_profile.exclusive_gpu`
  - `runtime_profile.latency_sensitive`
- 节点运行态已经支持最小 `ready` 语义：
  - 声明 `service_ports` 的任务可以在端口可达后进入 `ready`

但当前系统仍然缺少完整调度系统最关键的一段：

- 任务之间还不会真实让位。
- 调度器只会给出首次放置结果，不会给出“先回收谁、再推进谁”的执行决策。
- `preemptible`、`allow_preempt`、`checkpoint_policy` 等字段仍主要停留在元数据层。
- reconcile 仍偏向“扫描并推进 pending job”，还没有形成多轮执行闭环。
- `pause_job / resume_job / cancel_job` 对不同任务生命周期的控制语义还不够真实。

因此，下一阶段的目标不是继续增加任务种类，而是把系统升级成能够真实完成：

- 让位
- 重排
- 回收
- 推进

的调度执行控制面。

## 2. 目标与非目标

### 2.1 目标

- 让高优先级任务能够通过多轮 reconcile，真实推动低优先级任务让位。
- 让调度器不只给出 `placement`，还能够给出“先做什么，再放什么”的可执行决策。
- 让 `batch / service / session` 的控制语义明确分层，而不是统一套用同一组动作。
- 让回收、requeue、release、推进成为统一调和链路的一部分。
- 让人工控制和 Agent 自动调和共用同一套作业控制能力。

### 2.2 非目标

- 本阶段不实现真实 checkpoint / restore。
- 本阶段不实现进程级或容器级在线迁移。
- 本阶段不引入新的全局求解器或约束优化引擎。
- 本阶段不落地 `ssh_process` 与 `local_process` 后端。
- 本阶段不实现 service 副本扩缩容或滚动更新。

## 3. 设计结论

### 3.1 继续采用增量演进，不推翻现有链路

保留现有主链路：

`ClusterReconcileController -> ClusterControlPlaneService -> ClusterSchedulerCore -> ExecutionOrchestrator -> server-agent job_runtime`

本阶段只在该链路上补“决策 + 执行 + 反馈”的闭环，不引入第二套并行调度控制面。

### 3.2 先做“真实回收与推进”，再做 checkpoint / migrate

当前项目距离完整迁移系统仍缺少：

- 生命周期控制语义
- 多轮执行波次
- victim 选择
- 回收后推进

因此，本阶段优先顺序必须是：

1. 让位与回收
2. 重排与 requeue
3. 推进与状态回传
4. 之后才是 checkpoint / restore / migrate

### 3.3 继续坚持“人工与 Agent 共用能力面”

本阶段新增的调度动作必须同时具备：

- 自动 reconcile 可触发
- Agent capability 可触发
- 人工控制面可触发

不允许出现“自动系统才能做，人工做不了”的并行接口层。

## 4. 总体架构

本阶段把当前系统拆成四个连续层次：

### 4.1 计划层

输入：

- 待调度 job
- 当前 cluster node
- 当前 active allocation
- 当前 runtime 状态
- 治理规则与优先级

输出：

- 一个显式 `SchedulingDecision`

### 4.2 控制层

控制层负责把 `SchedulingDecision` 解释成具体控制动作，例如：

- `pause job`
- `cancel job`
- `release allocation`
- `mark requeue`
- `dispatch placement`

### 4.3 执行层

执行层继续沿用现有：

- `ClusterControlPlaneService`
- `ExecutionOrchestrator`
- `HTTPAgentProcessBackend`
- `server-agent job_runtime`

但要增加对不同生命周期任务的显式动作限制。

### 4.4 反馈层

反馈层读取：

- runtime job state
- allocation state
- reservation state

并把这些状态回写为 cluster 控制面可消费的：

- job status
- allocation status
- reconcile summary

## 5. 调度决策模型

### 5.1 新的调度决策对象

当前 `PlacementPlan` 主要表达“放置结果”。本阶段需要升级为能够表达执行前置动作的统一决策对象。第一阶段实现时可以保留 `PlacementPlan` 类型名，但其语义必须扩展为以下 plan type：

- `place`
- `wait`
- `reject`
- `preempt_then_place`
- `release_then_place`
- `requeue`
- `hold`

### 5.2 每类决策的含义

- `place`
  - 当前可直接放置
- `wait`
  - 当前没有可接受的回收路径，只能继续等待
- `reject`
  - 因治理规则、生命周期约束或资源请求非法而拒绝
- `preempt_then_place`
  - 需要先让一个或多个可抢占任务让位，再放置目标任务
- `release_then_place`
  - 需要先释放 allocation 或终止维护类任务，再放置目标任务
- `requeue`
  - 某个运行中任务不再保留当前资源，应转回等待队列
- `hold`
  - 当前既不应该推进也不应该回收，等待下一轮状态变化

### 5.3 决策附带信息

决策除了 `plan_type` 之外，还必须显式带出：

- `selected_node`
- `selected_devices`
- `reason`
- `score_breakdown`
- `victim_job_ids`
- `victim_allocation_ids`
- `followup_job_ids`
- `required_actions`

其中：

- `victim_job_ids`
  - 表示本轮让位/回收涉及哪些作业
- `victim_allocation_ids`
  - 表示本轮需要释放哪些 allocation
- `required_actions`
  - 是真正要由控制层执行的动作序列

## 6. 任务生命周期控制语义

### 6.1 按生命周期定义可执行动作

#### `batch`

适用：

- `training`
- `batch_compute`
- 部分 `maintenance`

允许：

- `pause`
- `resume`
- `cancel`
- `requeue`

#### `service`

适用：

- `inference_service`

允许：

- `cancel`
- `recreate`
- `replace`

默认不允许：

- `pause`
- `resume`

#### `session`

适用：

- `interactive_session`

允许：

- `cancel`

可选允许：

- `resume`

是否允许 `resume` 取决于后端运行时能力；本阶段默认不承诺。

### 6.2 生命周期与让位策略

在 victim 选择时采用以下规则：

- `service`
  - 默认最后才考虑回收
- `session`
  - 默认不作为优先回收对象
- `batch`
  - 是本阶段的主要让位对象
- `maintenance`
  - 优先于训练任务被回收

## 7. Victim 选择规则

### 7.1 候选集过滤

只有满足以下条件的任务才能成为让位候选：

- 当前存在 active allocation
- 当前状态允许被回收
- `preemptible = true`
- 当前用户治理规则 `allow_preempt = true`
- 任务生命周期支持本阶段的回收动作

### 7.2 候选排序

当多个任务可回收时，按以下优先顺序选择：

1. `maintenance`
2. `batch_compute`
3. `training`
4. `interactive_session`
5. `inference_service`

同一类型内，再按以下原则排序：

- 优先级低的先回收
- `restartable = true` 的先回收
- 非 `latency_sensitive` 的先回收
- 非 `exclusive_gpu` 的先回收
- 占用目标 GPU 集更多的优先回收

### 7.3 本阶段回收动作

本阶段不做 checkpoint 恢复，因此 victim 只允许两种回收结果：

- `cancel + requeue`
- `release allocation`

是否支持 `pause + resume` 只对 `batch` 有条件开放，不作为本阶段的默认依赖路径。

## 8. Reconcile 执行波次

### 8.1 一轮 reconcile 的执行顺序

每轮 reconcile 按以下顺序执行：

1. 读取 runtime 反馈并更新 terminal / released 状态
2. 读取所有 queue 中待推进 job
3. 对每个待推进 job 生成 `SchedulingDecision`
4. 如果决策是 `preempt_then_place / release_then_place`
   - 先下发 required actions
   - 标记目标 job 进入等待推进状态
5. 如果决策是 `place`
   - 直接 dispatch
6. 下一轮 reconcile 再检查回收是否完成
7. 一旦资源腾出，继续推进目标 job

### 8.2 Reconcile 不是单轮完成，而是多轮推进

本阶段必须明确接受：

- “让位”不是一轮函数调用就完成
- “重排”不是立即结果
- “推进”依赖 runtime 状态回传

因此，reconcile 的本质是：

- 有状态控制循环

而不是：

- 静态 planner

## 9. 状态模型扩展

### 9.1 Job 状态

本阶段 job status 至少扩展为：

- `queued`
- `pending`
- `preempting`
- `preempted`
- `requeue_requested`
- `dispatching`
- `running`
- `ready`
- `paused`
- `succeeded`
- `failed`
- `canceled`

### 9.2 Allocation 状态

allocation status 至少扩展为：

- `active`
- `paused`
- `releasing`
- `released`
- `orphaned`

### 9.3 状态设计原则

- job 状态反映“作业控制视角”
- allocation 状态反映“资源绑定视角”
- runtime job 状态反映“节点执行视角”

三者不能混用，但必须能通过 projection 被统一展示。

## 10. 人工与 Agent 能力面

### 10.1 新增统一控制能力

本阶段应新增或补强以下 capability：

- `job.requeue`
- `job.preempt`
- `allocation.release`
- `queue.reconcile`
- `reschedule.plan`

其中：

- Agent 可以调用这些 capability 自动推进调度
- 人工控制面也可以直接调用

### 10.2 UI 与自动系统一致

人工控制面必须能看到：

- 当前哪些 job 正在让位
- 哪些 allocation 正在释放
- 哪个高优先级 job 正在等待推进
- 本轮 reconcile 的推进结果

## 11. 与 checkpoint / migrate 的关系

本阶段为后续迁移预留接口，但不直接实现。

具体原则：

- `checkpoint_policy`
  - 只作为未来能力标记
- `runtime_profile.restartable`
  - 作为 victim 选择的重要信号
- `preempted`
  - 为未来 checkpoint-based 恢复保留状态入口

也就是说，本阶段完成后，系统已经具备：

- 真实回收
- 真实 requeue
- 多轮推进

下一阶段才在此基础上补：

- 应用自管 checkpoint
- restore
- migrate

## 12. 验收标准

本阶段完成后，应满足以下条件：

- 高优先级 `batch` 任务可以通过多轮 reconcile 推动低优先级可抢占任务让位。
- 调度器可以输出不止 `placement` 的执行型决策。
- `service / session / batch` 的控制语义有明确边界，不再统一套用。
- 被回收的任务会进入可追踪状态，而不是直接消失。
- allocation 的释放与 job 的推进可以在多轮 reconcile 中连续发生。
- Agent 和人工控制面可以调用同一套让位/重排/回收能力。

## 13. 实施顺序

为了兼容当前代码，本阶段建议实施顺序固定为：

1. 扩展调度决策模型
2. 扩展 job / allocation 状态模型
3. 落地 victim 选择器
4. 重构 reconcile 为多轮执行波次
5. 补强 lifecycle 控制语义
6. 将新动作暴露给 Agent 与人工控制面

这个顺序不能颠倒。

如果先做 UI 或 Agent，而调度决策与状态模型没成型，后续一定会返工。
