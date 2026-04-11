# 集群执行闭环 Phase 2 设计

日期：2026-04-10

## 1. 背景

当前系统已经具备：

- `job.submit / job.plan / reschedule.plan`
- `queue.reconcile`
- `allocation.release / node.drain / node.undrain`
- dispatch 失败显式落成 `failed`

但执行生命周期仍然是不闭合的：

- 节点 Agent 只负责 `launch`，不会把作业终态回传给后端
- 后端只知道作业被发出去，不知道它何时成功、失败或退出
- `cluster_allocations / cluster_reservations` 不会在作业完成后自动回收
- `job.cancel` 只改本地状态，不会真实终止节点上的运行进程

这意味着当前控制面还没有真正掌握“作业已经结束、资源已经释放”的事实。

## 2. 备选方案

### 方案 A：后端拉取节点运行态，显式调和

做法：

- 节点 Agent 暴露 runtime job 列表与按 handle 终止接口
- 后端在 `reconcile_and_dispatch()` 前先拉取每个节点的 runtime job 快照
- 将已经结束的作业显式落成 `succeeded / failed / canceled`
- 同步释放 allocation / reservation

优点：

- 最符合当前架构，继续由 `cluster_control` 作为唯一真相
- 不需要新增 Agent 回调鉴权与跨节点反向连通
- 便于调试，所有真实状态更新都由控制面显式触发

缺点：

- 不是实时推送，而是显式调和
- 如果不触发调和，终态可见性会滞后

### 方案 B：节点 Agent 主动回调后端

做法：

- 作业完成后，Agent 主动向后端回传终态

优点：

- 理论上实时

缺点：

- 要新增回调鉴权、目标地址配置、失败重试
- 会把当前单向执行链改成双向信道，复杂度明显上升

### 方案 C：后台 daemon 持续轮询节点运行态

做法：

- 后端起一个长期轮询任务，定时同步 runtime jobs

优点：

- 比手工触发更自动

缺点：

- 会引入新一层后台状态机与停止/重启问题
- 当前代码库还没有成熟的 cluster runtime daemon 生命周期管理

## 3. 选型

本阶段采用方案 A。

理由：

- 它是当前代码库最小、最稳定、最容易验证的一刀
- 先把“控制面可真实观测终态并释放资源”做实，比立即追求 push 实时性更重要
- 一旦这个基础闭环成立，后面无论加 daemon 还是 push callback，都是在既有真相面之上增强，而不是重写

## 4. 本阶段目标

本阶段只实现以下闭环：

1. 节点 Agent 能暴露 runtime job 快照
2. 节点 Agent 能按 `job_handle` 终止运行中的作业
3. 后端能在调和时把 runtime job 终态映射到 `cluster_jobs`
4. 后端能在作业终态后释放 allocation / reservation
5. `job.cancel` 对运行中作业走真实后端终止，而不是仅改本地状态
6. cluster console 能看到 `succeeded / failed / canceled` 等终态

## 5. 非目标

本阶段不实现：

- 节点 Agent 主动回调后端
- 后台自动轮询 daemon
- retry policy
- backend health-aware dispatch
- 抢占
- 迁移
- SSH / Local execution backend 的真实作业执行

## 6. 设计方案

### 6.1 节点 Agent runtime 扩展

扩展 `RuntimeStore` 与 `JobRuntime`：

- 记录 `state`
- 记录 `exit_code`
- 记录 `finished_at`
- 记录失败时的 `last_error`

新增 Agent API：

- `GET /api/runtime/jobs`
  - 返回当前所有 runtime jobs
  - 在返回前先执行一次 reap，将已退出进程更新为终态
- `POST /api/runtime/jobs/{job_handle}/terminate`
  - 真实终止对应进程
  - 将 runtime job 状态更新为 `canceled`

终态定义：

- 退出码 `0` -> `succeeded`
- 非 `0` 退出码 -> `failed`
- 通过 terminate 接口终止 -> `canceled`

### 6.2 后端 execution backend 扩展

扩展 `HTTPAgentProcessBackend`：

- `list_jobs(node)`：读取节点 runtime job 列表
- `terminate_job(node, job_handle)`：终止指定 runtime job

`SSHProcessBackend` / `LocalProcessBackend` 继续显式 `NotImplementedError`。

### 6.3 运行态调和

新增一个专门的 runtime 调和模块，由控制面调用：

- 按节点聚合当前 `active` allocation
- 对每个节点拉取一次 runtime job 快照
- 用 `runtime_job_handle` 对齐 allocation
- 对已经终态的 runtime job：
  - 更新 `cluster_jobs.status`
  - 对失败态写入 `last_error`
  - 将 allocation 标记为 `released`
  - 将 reservation 标记为 `released`

这样 `reconcile_and_dispatch()` 会变成两段：

1. 先同步并回收已终态运行作业
2. 再继续推进 `queued / pending` 作业

### 6.4 取消作业

`job.cancel` 对运行中的作业不再只改本地状态，而是：

1. 找到该作业的 `active` allocation
2. 取出 `runtime_job_handle`
3. 调用 execution backend 真实终止
4. 将 job 显式落成 `canceled`
5. 释放 allocation / reservation

如果运行中作业缺少 `runtime_job_handle`，本阶段明确报错，不做静默降级。

### 6.5 状态语义

本阶段控制面支持的关键状态：

- `queued`
- `pending`
- `dispatching`
- `running`
- `succeeded`
- `failed`
- `canceled`
- `paused`
- `rejected`

其中：

- `failed` 既可以表示 dispatch 失败，也可以表示 runtime 执行失败
- 区分方式由 `last_plan_type / last_error` 体现

### 6.6 控制台展示

cluster console 不新增大块结构，只补运行终态可见性：

- `ClusterJobLedger`
  - 正常显示 `succeeded / failed / canceled`
  - 对 `failed` 继续显示 `lastError`
- `queue.reconcile`
  - summary 增加 `completed`
  - summary 增加 `canceled`
  - summary 增加 `released`

## 7. 测试策略

坚持 TDD：

1. 先写节点 Agent 红灯测试
2. 再写控制面 runtime 调和红灯测试
3. 再写取消运行中作业红灯测试
4. 最后跑 Windows 定向验证

重点回归：

- 运行中作业在节点上结束后，调和能把控制面状态更新为 `succeeded / failed`
- 终态后 allocation / reservation 被自动释放
- `job.cancel` 会真实触发节点终止
- `queue.reconcile` 能在同一次调用里先回收已结束作业，再继续推进等待队列
