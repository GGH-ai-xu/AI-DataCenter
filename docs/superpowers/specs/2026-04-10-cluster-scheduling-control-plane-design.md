# 集群级算力调度控制面设计

日期：2026-04-10

## 1. 背景

当前平台的核心抽象仍然是“GPU + 进程治理”。系统可以观测节点状态、限制功耗、暂停/恢复/终止进程，并通过自然语言把用户目标转换成有限的治理动作。这个架构适合单机或少量主机的运维治理，但不足以支撑集群级调度。

目标系统需要支持：

- 作业提交
- 队列管理
- 节点与设备放置
- 抢占
- 迁移
- 多租户配额与公平性
- 能耗与碳策略
- 目标驱动 Agent runtime

因此，系统必须从“围绕实时进程治理”升级为“围绕作业与分配进行调度”。

## 2. 目标与非目标

### 2.1 目标

- 建立集群级控制面，统一管理 `Cluster / Node / Device / Queue / Tenant / Job / Allocation / Policy / Reservation / ExecutionBackend`。
- 用新调度内核替换现有“动作列表直接执行”的模式。
- 建立插件化执行后端，第一版以自研进程执行器为主。
- 将节点侧 `server-agent` 升级为 `Node Runtime`，支持作业生命周期和资源分配。
- 将 Agent runtime 升级为目标驱动控制器，以 `Job / Allocation / Policy / Plan` 为核心操作对象。

### 2.2 非目标

- 第一版不实现容器编排。
- 第一版不实现在线热迁移。
- 第一版不实现 checkpoint 恢复。
- 第一版不实现 gang scheduling、DAG 作业或多节点分布式启动编排。
- 第一版不直接对接 Slurm 或 Kubernetes，但接口需为后续对接保留扩展点。

## 3. 总体策略

采用“并行新控制面，逐步替换旧治理链路”的方案。

- 保留现有治理系统可运行。
- 新建独立的 `Cluster Control Plane`、`Scheduler Core`、`Execution Backend Layer`、`Node Runtime`、`Policy Engine`、`Agent Runtime`。
- 现有功耗治理、进程治理和导入范围控制逐步下沉为新系统中的策略能力、兼容 capability 或底层 provider。

这样可以避免被现有“GPU/进程治理”抽象绑定，同时复用现有的运行时 provider、审计、审批、实时状态流和前端工作台骨架。

## 4. 系统架构

系统拆分为六个子系统：

1. `Cluster Control Plane`
   - 维护资源、作业、队列、租户、策略、分配和预留的系统真相。
2. `Scheduler Core`
   - 将 `JobSpec` 转换为 `PlacementPlan`、`PreemptionPlan` 或 `MigrationPlan`。
3. `Execution Backend Layer`
   - 将计划下发到节点或其他执行后端。
4. `Node Runtime`
   - 在节点侧执行作业、维护本地分配状态、回传心跳和事件。
5. `Policy Engine`
   - 提供配额、公平性、优先级、抢占、放置、能耗和安全策略。
6. `Agent Runtime`
   - 将用户目标转换为标准对象、触发审批、编排执行、流式回报结果。

边界定义：

- 控制面负责状态真相。
- 调度器负责计划生成。
- 执行后端负责计划落地。
- 节点运行时负责节点上的实际作业生命周期。
- Agent runtime 只操作控制面对象和标准 capability，不直接调用底层 provider 或系统命令。

## 5. 核心数据模型

### 5.1 资源树

- `Cluster`
  - `cluster_id`, `name`, `labels`, `status`, `scheduler_version`, `created_at`, `updated_at`
- `Node`
  - `node_id`, `cluster_id`, `hostname`, `agent_endpoint`, `backend_kind`, `status`, `schedulable`, `drain_state`, `labels`, `taints`, `capacity`, `allocatable`, `usage`, `heartbeat_at`
- `Device`
  - `device_id`, `node_id`, `device_kind`, `parent_device_id`, `vendor`, `model`, `topology`, `capacity`, `allocatable`, `usage`, `health`, `labels`

说明：

- 资源树必须统一建模 GPU、CPU、内存、网络和未来的 MIG slice。
- 进程列表只作为节点运行时观测数据，不再作为调度真相。

### 5.2 调度对象

- `Queue`
  - `queue_id`, `name`, `state`, `priority_policy`, `default_priority`, `max_concurrency`, `admission_policy`, `allowed_tenants`, `placement_policy_ref`, `preemption_policy_ref`
- `Tenant`
  - `tenant_id`, `name`, `state`, `quota_policy_ref`, `fairness_policy_ref`
- `User`
  - `user_id`, `tenant_id`, `name`, `roles`, `state`
- `Project`
  - `project_id`, `tenant_id`, `name`, `queue_bindings`, `budget_policy_ref`, `labels`

### 5.3 作业与分配

- `JobSpec`
  - `job_id`, `tenant_id`, `project_id`, `queue_id`, `submitter_id`, `job_type`, `image_or_runtime`, `entrypoint`, `args`, `env`, `resource_request`, `resource_limit`, `placement_constraints`, `priority`, `preemptible`, `restart_policy`, `max_retries`, `timeout_seconds`, `created_at`
- `JobRuntime`
  - `job_id`, `state`, `current_allocation_id`, `attempt`, `exit_code`, `failure_reason`, `started_at`, `finished_at`, `last_transition_at`
- `Allocation`
  - `allocation_id`, `job_id`, `node_id`, `device_bindings`, `cpu_set`, `memory_bytes`, `gpu_bindings`, `network_reservation`, `status`, `reservation_id`, `execution_backend`, `launch_spec`, `created_at`, `released_at`
- `Reservation`
  - `reservation_id`, `scope`, `owner_type`, `owner_id`, `reserved_resources`, `status`, `expires_at`, `created_at`

原则：

- `Job` 是调度真相。
- `Allocation` 是作业拿到资源的具体实例。
- 迁移本质上是旧 allocation 释放加新 allocation 建立。

### 5.4 策略与后端

- `Policy`
  - 细分为 `QuotaPolicy`、`FairnessPolicy`、`PreemptionPolicy`、`PlacementPolicy`、`EnergyPolicy`、`SecurityPolicy`
- `ExecutionBackend`
  - `backend_id`, `kind`, `version`, `target_scope`, `capabilities`, `connection_profile`, `health`, `last_heartbeat_at`

## 6. 调度内核

调度内核由五个阶段组成：

1. 需求归一化
   - 统一处理 API 作业提交、Agent 目标驱动请求和系统内部重调度请求。
   - 输出标准 `JobSpec` 或 `RescheduleSpec`。
2. 准入控制与队列管理
   - 检查权限、配额、合法性、安全策略。
   - 决定 queue、默认优先级和 admission 结果。
3. 候选资源筛选
   - 逐层过滤 cluster、node、device。
   - 明确记录未命中的过滤原因。
4. 打分与约束求解
   - 先应用硬约束，再做多维打分。
   - 输出 `PlacementPlan`、`QueueWaitPlan`、`PreemptionPlan` 或 `MigrationPlan`。
5. 执行、补偿与回滚
   - 创建 reservation。
   - 建立 allocation。
   - 调用 execution backend。
   - 根据运行时回执更新状态。
   - 失败时释放 reservation/allocation 并重规划或终止。

第一版的调度器不直接输出 `pause_task`、`set_power_limit` 等动作数组，而是输出包含以下字段的计划对象：

- `job_id`
- `plan_type`
- `candidate_nodes`
- `selected_node`
- `selected_devices`
- `reservation_spec`
- `execution_backend`
- `launch_spec`
- `score_breakdown`
- `alternatives`

## 7. 抢占与迁移

### 7.1 抢占

第一版采用“暂停型抢占”：

- 高优先级作业无法放置时触发抢占分析。
- 调度器基于 `PreemptionPolicy` 选择 victim jobs。
- 只有可抢占且满足 grace period 的作业可被选为 victim。
- 执行结果是：
  - victim job 进入 `preempting`
  - 节点侧暂停作业
  - 释放 allocation
  - 新作业获得资源并启动
  - victim 返回 queue 或等待恢复

### 7.2 迁移

第一版只支持“暂停后迁移”：

- 先在目标节点创建 reservation 与 allocation。
- 暂停源节点作业。
- 释放源节点 allocation。
- 在目标节点启动新的 attempt。
- 更新 `JobRuntime.current_allocation_id` 和作业 lineage。

不支持在线热迁移。

## 8. Execution Backend 与 Node Runtime

### 8.1 Execution Backend

第一版提供三个 backend 实现：

- `HTTPAgentProcessBackend`
- `SSHProcessBackend`
- `LocalProcessBackend`

主路径为 `HTTPAgentProcessBackend`。控制面统一通过 backend 接口操作 `allocation` 和 `job_handle`，不直接以裸 PID 为主键。

### 8.2 Node Runtime

现有 `server-agent` 升级为节点运行时，新增职责：

- 节点资源库存与健康上报
- 本地 reservation / allocation 状态维护
- 作业启动、暂停、恢复、取消、清理
- 日志与事件采集
- 节点重启后的状态恢复

第一版作业模型采用“受控进程作业”：

- 通过 `working_dir + command + args + env + bind_spec` 启动
- 支持 `CUDA_VISIBLE_DEVICES` GPU 绑定
- 支持 CPU 绑定
- 支持工作目录和日志目录绑定

第一版不做容器隔离和 cgroup 全量隔离，但接口预留升级空间。

## 9. Capability 体系升级

Capability 体系重构为五类：

- 观测类
  - `cluster.snapshot.read`, `node.inventory.read`, `job.list`, `job.get`, `allocation.list`, `queue.status.read`, `policy.list`
- 计划类
  - `job.plan`, `allocation.plan`, `reschedule.plan`, `migration.plan`, `preemption.plan`
- 执行类
  - `job.submit`, `job.pause`, `job.resume`, `job.cancel`, `job.retry`, `job.migrate`, `allocation.create`, `allocation.release`, `node.drain`, `node.undrain`
- 策略类
  - `policy.quota.set`, `policy.priority.set`, `policy.preemption.set`, `policy.placement.set`, `policy.energy.set`
- 后端类
  - `backend.local.process.launch`, `backend.http_agent.launch`, `backend.ssh.process.launch`

原则：

- Agent runtime 面向 `job.*`、`allocation.*`、`policy.*`、`reschedule.*` 能力。
- `backend.*` 主要供控制面内部或执行编排器使用，不作为普通用户目标的直接操作对象。

## 10. Agent Runtime 升级

Agent runtime 从“动作生成器”升级为“目标驱动控制器”，流程为：

1. 识别用户意图：
   - `analysis`, `job_submission`, `job_control`, `queue_operation`, `allocation_operation`, `reschedule_operation`, `policy_change`, `cluster_operation`, `incident_response`
2. 生成标准对象：
   - `JobSpec`, `PolicyChangeSpec`, `RescheduleSpec`
3. 选择 capability 路径：
   - 先 plan，再 approval，再 execute，再 observe
4. 监听结果并在失败时重规划：
   - 资源冲突触发重排
   - 信息不足触发澄清
   - 高风险操作触发审批

会话状态必须持久化：

- `goal_spec`
- `current_intent_type`
- `normalized_specs`
- `candidate_plans`
- `approved_plan`
- `execution_state`
- `observation_snapshots`
- `replan_history`
- `final_outcome`

## 11. 审批与安全

采用“按 capability 类别与风险等级审批”的模型：

- 低权限模式
  - 默认允许观测类和计划类
  - 对 `job.submit`、`job.pause/resume/cancel`、`job.migrate`、`allocation.release`、`policy.*`、`node.drain/undrain` 要求审批
- 高权限模式
  - 默认允许大多数执行类 capability
  - 对大规模抢占、批量迁移、配额放宽、节点排空等高风险操作仍要求确认

所有真实执行必须进入统一审计日志和事件流。

## 12. 迁移策略

### 12.1 保留

- 现有运行时 provider 抽象
- 现有导入范围控制
- 现有审计、审批、会话流与前端工作台基础设施
- 现有 `server-agent` 采集能力

### 12.2 下沉或兼容

- 现有功耗治理与进程治理动作逐步下沉为新系统的兼容 capability 或策略能力
- 现有 `SchedulerEngine` 逐步降级为遗留治理策略执行器，不再承担集群级调度核心职责

### 12.3 新主路径

- 新作业提交、放置、抢占和迁移统一通过 `Cluster Control Plane + Scheduler Core + Execution Backend + Node Runtime`

## 13. 第一阶段实施范围

整个目标系统过大，第一阶段只落最小闭环：

- 新建控制面基础模型：`Node / Device / Queue / Job / Allocation / Reservation`
- 新建调度内核最小流程：提交、入队、放置、reservation、allocation、启动、失败重试
- 新建自研进程执行器：`HTTPAgentProcessBackend`
- 将 `server-agent` 升级为节点运行时，支持受控进程作业
- 新建最小 Agent capability：`job.submit`, `job.list`, `job.get`, `job.pause`, `job.resume`, `job.cancel`, `queue.status.read`, `job.plan`
- 前端提供最小可视化：作业提交、队列、作业状态、allocation 状态、Agent 执行事务视图

第一阶段不做：

- Slurm / Kubernetes 对接
- 热迁移
- checkpoint 恢复
- gang scheduling
- 分布式多节点作业

## 14. 验证策略

需要建立四层验证：

- 模型层
  - 数据模型、状态机、事件流的一致性测试
- 调度层
  - 候选筛选、打分、抢占、迁移、回滚测试
- 执行层
  - 节点运行时、allocation 生命周期、节点重启恢复测试
- Agent 层
  - 意图识别、spec 构造、审批、执行、重规划测试

验收标准：

- 可以提交作业并进入 queue
- 可以完成单节点放置并启动
- 可以在资源不足时正确排队或触发暂停型抢占
- 可以对 running job 做暂停、恢复、取消
- 可以对 job 做暂停后迁移
- Agent runtime 可以围绕 `Job / Allocation / Plan` 展示完整执行事务

## 15. 结论

本设计的核心转变是：

- 从“围绕 PID 和 GPU index 的治理系统”
- 升级为“围绕 Job、Allocation、Reservation 和 Policy 的集群级调度系统”

第一阶段的实现计划必须围绕最小闭环展开，而不是继续扩展现有动作集合。
