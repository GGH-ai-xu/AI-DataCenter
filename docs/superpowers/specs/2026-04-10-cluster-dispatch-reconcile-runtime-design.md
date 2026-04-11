# 集群调和分发闭环设计

日期：2026-04-10

## 1. 背景

当前 `cluster_control` 已经具备：

- `job.submit`
- queue admission
- `job.plan / reschedule.plan`
- `allocation.release / node.drain / node.undrain`

但执行链路仍然停留在“提交时尝试一次 dispatch”。系统还缺少真正的调和分发闭环：

- `queued / pending` 作业不会被持续推进
- dispatch 失败不会显式沉淀成集群作业状态
- reservation 没有进入控制面真相
- cluster console 看不到 dispatch 成功/失败的运行态

## 2. 本阶段目标

本阶段只实现“调和分发闭环”的第一子阶段：

- 为 `queued / pending` 作业增加显式的 reconcile-dispatch 流程
- 为 dispatch 失败增加显式状态和错误落库
- 将 reservation 纳入本地控制面持久化
- 在 cluster console 中展示 dispatch 状态与失败原因
- 提供一个统一的 `queue.reconcile` capability 供人工与 Agent 复用

## 3. 非目标

- 本阶段不实现抢占
- 本阶段不实现迁移
- 本阶段不实现 `SSHProcessBackend` / `LocalProcessBackend` 真正作业启动
- 本阶段不实现节点侧作业完成态回传和回收
- 本阶段不实现 queue daemon 或后台定时调度器

## 4. 设计方案

### 4.1 调和执行模型

新增一个显式的“调和并分发”入口：

- `ClusterControlPlaneService.reconcile_and_dispatch(nodes=...)`

该入口对所有 `queued / pending` 作业按创建顺序执行：

1. 重新计算 placement plan
2. 对 `queue_wait / rejected` 结果继续持久化等待或拒绝原因
3. 对 `placement` 结果进入 dispatch
4. dispatch 成功后进入 `running`
5. dispatch 失败后进入 `failed`

该入口返回一个显式 summary，而不是沉默失败。summary 至少包含：

- `processed`
- `dispatched`
- `waiting`
- `rejected`
- `failed`
- 每个失败作业的 `job_id / error`

### 4.2 作业状态扩展

在现有作业状态上明确支持：

- `queued`
- `pending`
- `dispatching`
- `running`
- `failed`
- `paused`
- `canceled`
- `rejected`

其中：

- `pending` 表示 admission 通过但暂时未被放置
- `dispatching` 表示已选定 node，正在创建 reservation / launch
- `failed` 表示 dispatch 过程失败，需要人工排查或后续 retry

为避免隐藏错误，本阶段不自动 retry，不静默降级回 `pending`。

### 4.3 持久化对象

继续沿用 `cluster_control` SQLite 真相，扩展如下：

- `cluster_jobs`
  - 增加 `last_error`
- `cluster_allocations`
  - 增加 `runtime_job_handle`
- `cluster_reservations`
  - 真正接入 create / list / get / status update

reservation 的职责是记录“控制面已经向节点 runtime 申请了资源保留”。第一版只做本地真相记录，不实现远端 reservation release。

### 4.4 Orchestrator 行为

`ExecutionOrchestrator.dispatch_plan()` 负责：

1. 解析选中节点与 backend
2. 调用 backend 创建 reservation
3. 将 reservation 写入本地 store
4. 调用 backend 启动作业
5. 创建 allocation，记录 `runtime_job_handle`

错误策略：

- reservation 创建失败：直接抛错，由 control plane 将 job 标记为 `failed`
- launch 失败：同样抛错并保留可排查错误，不做 silent cleanup

### 4.5 手工入口与能力面

新增统一 capability：

- `queue.reconcile`

它属于 cluster control 面的真实执行能力，供两条路径复用：

- cluster console 顶部手工按钮
- goal runtime / agent runtime

这比前端直接调用临时 REST 路由更符合当前系统设计，因为所有“真实操作”都走 capability / control plane 审批链。

### 4.6 控制台展示

cluster console 的重点不是做更多大卡片，而是让用户看见当前 dispatch 生命周期。

本阶段作业行展示增加：

- `dispatching / failed / running` 状态
- `last_error`
- `runtime_job_handle`（若存在）

队列卡片展示增加：

- `failedJobs`
- `dispatchingJobs`

顶部工具栏增加“执行队列调和”按钮。

## 5. 测试策略

本阶段坚持 TDD：

- 先写 control plane / orchestrator / API / capability / frontend model 红灯测试
- 再写最小实现
- 再跑 Windows 定向验证

重点回归：

- reconcile 能把 `pending` 作业推进到 `running`
- dispatch 失败时 job 明确落成 `failed` 并记录错误
- reservation / runtime handle 被写入控制面真相
- cluster console 模型能显示 dispatch 失败与运行状态

## 6. 分阶段衔接

完成本阶段后，系统将首次具备“计划 -> 调和 -> 分发 -> 失败显式可见”的基础执行闭环。下一阶段才进入：

- retry / retry policy
- backend health-aware dispatch
- 抢占
- 迁移
- 节点侧完成态回传与 allocation 回收
