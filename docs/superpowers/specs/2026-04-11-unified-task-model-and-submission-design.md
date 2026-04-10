# 统一任务模型与多类型算力任务提交设计

日期：2026-04-11

## 1. 背景

当前平台已经具备两条真实可用但彼此割裂的任务链路：

- 一条是围绕现存 GPU 进程的治理链路，可对计算型进程执行 `pause / resume / terminate / power-limit / priority` 等动作。
- 一条是围绕受管 `JobSpec` 的提交链路，可把一条命令提交到 `cluster_control -> execution_orchestrator -> server-agent job_runtime` 上执行。

但当前实现仍然存在明显缺口：

- `JobSpec` 只能表达非常薄的 batch 命令语义，尚不能稳定表达训练、推理服务、交互式会话、维护任务等不同任务类型。
- 调度器几乎只消费 `gpu/cpu/memory`、`queue state` 和 `drain_state`，没有真实消费任务生命周期差异。
- 人工控制面中的 `job.submit` 仍然是“最小训练任务表单”，默认示例仍然是 `python train.py`。
- Agent runtime 目前具备 `job.submit` capability，但规则规划链路不会稳定生成 `submit_job`。
- 节点侧 runtime 只有“拉起命令 + terminate + 退出码”语义，无法区分 batch / service / session 的运行态差异。

因此，第一阶段必须先补齐统一任务模型和多类型任务提交能力，再继续推进更高阶的抢占、迁移与集群级调度。

## 2. 目标与非目标

### 2.1 目标

- 在保留现有 `JobSpec` 主链路的前提下，将其扩展为统一任务模型。
- 支持至少五类一等任务：`training`、`inference_service`、`interactive_session`、`batch_compute`、`maintenance`。
- 让调度器基于任务类型和生命周期语义做真实决策，而不是只看资源量。
- 让人工控制面和 Agent runtime 共用同一个 `job.submit` 提交入口。
- 让节点侧 runtime 能表达 `batch / service / session` 的基本运行态差异。
- 保持第一阶段可落地，不引入第二套并行任务对象。

### 2.2 非目标

- 第一阶段不实现真实 checkpoint / restore / migrate。
- 第一阶段不实现 Slurm、Kubernetes、Ray 等新执行后端。
- 第一阶段不实现容器级隔离、ingress、滚动更新或服务副本编排。
- 第一阶段不把外部手动启动的裸 GPU 进程强行纳入受管作业生命周期。
- 第一阶段不引入新的上层 `TaskSpec` 对象取代现有 `JobSpec`。

## 3. 用户确认的设计结论

- 第一阶段采用“在现有 `JobSpec` 上增量扩展”的方案，而不是新建第二套任务对象。
- 调度器第一阶段采用“硬约束 + 轻量打分”的方式，不直接上复杂求解器。
- 人工控制面和 Agent runtime 必须共用同一个任务提交模型和 capability 入口。
- 执行后端第一阶段只把 `http_agent` 链路做实，不同时推进 `ssh_process` 和 `local_process` 落地。

## 4. 总体策略

第一阶段沿现有主链路增量演进：

`job.submit -> cluster_control -> scheduler_core -> execution_orchestrator -> HTTPAgentProcessBackend -> server-agent job_runtime`

本次设计不引入新的并行控制面，也不替换掉现有进程治理链路，而是让受管作业链路真正具备多类型任务语义。现存 GPU 进程治理继续保留，作为“导入后治理”和“受管作业之外的兼容能力”存在。

## 5. 统一任务模型

### 5.1 核心字段

在保留现有字段的基础上，为 `JobSpec` 新增以下一等字段：

- `task_kind`
  - 值域：`training | inference_service | interactive_session | batch_compute | maintenance`
- `lifecycle_kind`
  - 值域：`batch | service | session`
- `service_ports`
  - 类型：`list[int]`
  - 表示受管任务对外暴露或内部绑定的端口声明
- `checkpoint_policy`
  - 值域：`none | app_managed`
- `runtime_profile`
  - 类型：结构化对象
  - 第一阶段字段：`expected_duration_seconds`、`restartable`、`latency_sensitive`、`exclusive_gpu`

继续保留并沿用现有字段：

- `entrypoint`
- `args`
- `env`
- `resource_request`
- `placement_constraints`
- `priority`
- `preemptible`
- `max_retries`
- `timeout_seconds`

### 5.2 默认语义

- `training`：默认 `lifecycle_kind=batch`，允许 `checkpoint_policy=app_managed`，默认 `runtime_profile.restartable=true`
- `inference_service`：默认 `lifecycle_kind=service`，默认 `runtime_profile.latency_sensitive=true`，默认 `preemptible=false`
- `interactive_session`：默认 `lifecycle_kind=session`，默认 `runtime_profile.restartable=false`，默认 `preemptible=false`
- `batch_compute`：默认 `lifecycle_kind=batch`，是最通用的离线算力任务
- `maintenance`：默认 `lifecycle_kind=batch`，默认 `runtime_profile.exclusive_gpu=false`，适用于预热、清理、数据整理、环境检查等任务

### 5.3 建模原则

- 不再依赖 `entrypoint` 字符串猜测任务类型。
- 不按任务类别拆成多套 spec。
- 第一阶段的统一任务模型直接挂在现有 `JobSpec` 上。

## 6. 调度器消费规则

第一阶段调度器继续沿用现有 `ClusterSchedulerCore`，但从“资源 best-fit”升级为“硬约束 + 轻量打分”。

### 6.1 硬约束

不满足即不可放置：

- 资源约束：`gpu / cpu / memory`
- 节点可调度约束：`schedulable / drain_state`
- 端口冲突约束：`service_ports` 不得与同节点已运行的受管 `service / session` 任务冲突
- 生命周期兼容约束：节点如声明只接收某类生命周期任务，则不兼容任务不得放置
- 独占约束：`runtime_profile.exclusive_gpu=true` 时，目标 GPU 不得与其他 active allocation 共享

### 6.2 打分规则

在多个候选节点均满足硬约束时，按任务类型做轻量排序：

- `service` 且 `latency_sensitive=true`：优先资源余量更稳定、波动更小的节点
- `batch` 且 `restartable=true`：优先吃碎片资源，不占用最优服务节点
- `interactive_session`：优先响应余量高的节点
- `maintenance`：默认最低优先，尽量不挤占训练和服务任务

### 6.3 第一阶段不执行但要进入模型的语义

- `preemptible` 与 `runtime_profile.restartable`
  - 第一阶段用于判断“未来是否可被抢占”
  - 不在本阶段执行真实抢占
- `checkpoint_policy=app_managed`
  - 第一阶段只作为“未来可恢复/可迁移”的显式标记
  - 不做迁移执行

### 6.4 重排预演

保留现有 `reschedule.plan`，但增强返回理由：

- 为什么某个 service 任务不适合迁走
- 为什么某个 batch 任务更适合回收
- 为什么某个 session 任务应保留原位

## 7. 人工控制面与 Agent 统一提交

### 7.1 单一提交入口

第一阶段继续使用唯一真实提交 capability：

- `job.submit`

不新增 Agent 专用提交 API，也不新增人工专用提交 API。人工和 Agent 都向同一份任务模型提交。

### 7.2 人工控制面

将当前最小训练表单升级为通用任务提交表单：

- 先选择 `task_kind`
- 再带出对应默认值
- 再显示该类型需要填写的补充字段

第一阶段按类型显示如下关键字段：

- `training`：资源申请、命令、预期时长、checkpoint 能力、是否允许重启
- `inference_service`：资源申请、启动命令、端口声明、是否延迟敏感
- `interactive_session`：资源申请、启动命令、可选端口声明
- `batch_compute`：资源申请、启动命令、重试与超时
- `maintenance`：启动命令、低优先执行语义

### 7.3 Agent runtime

为规则规划链路补稳定的 `submit_job` 提取路径，使其在无 LLM 或 LLM 失败时仍可识别常见请求：

- 提交训练任务
- 提交推理服务任务
- 启动交互式会话
- 提交低优先离线批处理任务

Agent 与人工的差异只保留在：

- 来源
- 审批路径
- 可视化回放

不保留在任务模型本身。

## 8. 节点运行态与执行后端边界

### 8.1 执行后端边界

第一阶段只把 `HTTPAgentProcessBackend` 做强，不扩展新的已落地 backend。`ssh_process` 和 `local_process` 保持后续阶段实现。

### 8.2 节点侧运行态

节点侧 `server-agent job_runtime` 从“命令拉起器”升级为“多类型任务运行态记录器”，第一阶段至少补齐这些字段：

- `task_kind`
- `lifecycle_kind`
- `reservation_id`
- `pid`
- `state`
- `started_at`
- `finished_at`
- `service_ports`
- `runtime_profile`
- `health_state`
- `readiness_state`
- `last_error`

### 8.3 第一阶段状态模型

- `queued`
- `dispatching`
- `running`
- `ready`
- `paused`
- `succeeded`
- `failed`
- `canceled`

其中：

- `batch` 任务通常走 `running -> succeeded / failed`
- `service / session` 任务可进入 `ready`

### 8.4 第一阶段最小 readiness 方案

- 如果任务声明了 `service_ports`，则以目标端口被该任务占用作为基础 `ready` 信号
- 如果未声明端口，则仅视为 `running`

第一阶段不做 HTTP 自定义健康探针、readiness command、sidecar 和自动 ingress / 代理配置。

### 8.5 作业控制边界

- 裸 GPU 进程治理继续保留现有 `tasks.pause / resume / terminate`
- 受管 job 第一阶段必须保证 `cancel` 真正有效
- `job.pause / job.resume` 只允许继续面向可暂停的 `batch / training` 任务演进
- `service / session` 默认不开放 pause / resume

## 9. 存储与 API 演进

- 扩展现有集群作业与节点 runtime 持久化结构，新增任务语义字段和运行态字段，但不引入第二套表。
- 扩展现有：

- `ClusterJobSubmitRequest`
- `job.submit` capability 参数结构
- `cluster_jobs` 响应模型
- `runtime jobs` 响应结构

原则：

- 向前兼容旧字段
- 新字段有明确默认值
- 不保留“训练任务专用入口”

## 10. 验收标准

第一阶段完成后，应满足以下条件：

- 可以通过人工控制面提交五类一等任务，而不是只提交最小训练命令。
- Agent 在常见自然语言输入下可稳定生成 `submit_job` 并提交统一任务对象。
- 调度器会真实消费 `task_kind / lifecycle_kind / service_ports / runtime_profile` 的一部分语义。
- 推理服务和交互式会话任务可进入 `ready`，而不仅仅是 `running`。
- 端口声明冲突会阻止非法放置。
- 第一阶段不引入第二套任务对象，不破坏现有 `JobSpec` 主链路。

## 11. 分阶段边界

本设计仅覆盖第一阶段基础层。后续阶段再继续推进：

- checkpoint contract
- 真实抢占执行
- 恢复与迁移
- 多执行后端
- 更复杂的队列和租户策略
