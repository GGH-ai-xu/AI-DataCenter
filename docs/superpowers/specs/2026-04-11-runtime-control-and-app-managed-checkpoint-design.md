# 作业级真实运行时控制与应用自管检查点设计

日期：2026-04-11

## 1. 背景

当前代码库已经具备三层基础能力：

- 集群作业模型、排队与抢占规划
- Agent 与人工共用的 capability 控制面
- 节点侧 runtime job 的启动、列举、终止

但执行闭环仍然不完整，具体体现在：

- `job.pause / job.resume` 目前只改控制面状态，不会真实作用到节点进程
- `checkpoint_policy` 已经从表单传到 runtime payload，但没有任何 checkpoint/restore 执行链路
- `preempt_then_place` 当前仍然等价于“取消作业并释放资源”，不具备可恢复让位能力
- `HTTPAgentProcessBackend` 只支持 `launch / list / terminate`

这意味着系统已经能做“调度决策”，但还不能把“作业级真实控制”落到下位机。

## 2. 已核对的代码依据

本设计直接基于以下现有实现：

- `backend/app/services/cluster_control/control_plane.py`
  - `pause_job()` / `resume_job()` 仍然只调用 `change_job_state()`
- `backend/app/services/cluster_control/control_plane_job_actions.py`
  - `cancel_running_job()` 已经具备“找到 allocation -> 调 orchestrator -> 回写状态”的真实控制模式
- `backend/app/services/cluster_control/execution_orchestrator.py`
  - 当前仅编排 `create_reservation / launch_job / list_jobs / terminate_job`
- `backend/app/services/cluster_control/execution_backend.py`
  - 仅 `HTTPAgentProcessBackend` 有实现，且方法范围很窄
- `server-agent/job_runtime.py`
  - 当前只有 `launch / list_jobs / terminate`
- `server-agent/runtime_store.py`
  - 当前只保存 reservation 与 runtime job 基本信息
- `server-agent/controllers/task_control.py`
  - 已经有基于 `psutil` 的真实 `suspend / resume / terminate`
- `frontend/src/lib/controlCapabilityForms.js`
  - 已有 `job.pause / job.resume / job.cancel / job.requeue / job.preempt` 的人工入口
- `frontend/src/components/cluster/ClusterJobLedger.vue`
  - 已有作业账本与紧凑操作位

## 3. 目标

本阶段目标是把当前系统升级为“作业级真实运行时控制闭环 v1”：

1. `job.pause / job.resume` 从纯状态切换升级为真实 runtime 控制
2. 引入应用自管 checkpoint/restore 协议
3. 让控制面、Agent、人工控制台看到同一套 runtime 驱动状态
4. 为后续“可恢复让位、迁移、重排”打基础

## 4. 非目标

本阶段不实现：

- 平台级通用进程内存冻结/恢复
- SSH / Local backend 的完整 runtime 控制实现
- 自动 checkpoint 驱动的抢占迁移
- 真正跨节点迁移
- LLM 规划策略重写

## 5. 备选方案

### 方案 A：扩展现有 runtime job 模型，采用文件契约式 app-managed checkpoint

做法：

- 直接扩展现有 `JobRuntime` 和 `RuntimeStore`
- 将 `pause / resume` 真实下沉到节点进程
- checkpoint 采用控制目录 + 结果清单的应用自管契约
- restore 复用当前 launch 模型，加 `manifest_path` 语义

优点：

- 与现有 `Popen + RuntimeStore + HTTPAgentProcessBackend` 架构兼容度最高
- 可直接复用现有 `psutil suspend/resume`
- 适配你们已存在的 `checkpoint_policy = app_managed`
- 为后续迁移保留扩展空间

缺点：

- 应用必须配合实现 checkpoint 协议
- checkpoint 是显式中间态，不是平台直接完成

### 方案 B：信号或回调式 app-managed checkpoint

做法：

- 平台通过信号、hook command 或本地 HTTP callback 触发应用保存

优点：

- 某些训练框架集成更轻

缺点：

- Windows / Linux 差异更大
- 契约不统一
- 当前代码库没有 hook 生命周期模型

### 方案 C：引入 supervisor / wrapper 运行层

做法：

- 所有作业由 supervisor 包装启动，再由 supervisor 管 pause/resume/checkpoint/restore

优点：

- 长期最规整

缺点：

- 改动范围过大
- 不适合当前阶段先补真实控制闭环的目标

## 6. 选型

本阶段采用方案 A。

理由：

- 它最大化复用现有 runtime API 与 execution backend 结构
- 能先把“假动作”修正为“真动作”
- 以最低复杂度把 `checkpoint_policy` 从元数据升级为真实协议
- 不会提前把阶段目标膨胀成“平台级通用冻结/迁移框架”

## 7. 设计方案

### 7.1 节点 runtime API 扩展

在 `server-agent/main.py` 新增以下接口：

- `POST /api/runtime/jobs/{job_handle}/pause`
- `POST /api/runtime/jobs/{job_handle}/resume`
- `POST /api/runtime/jobs/{job_handle}/checkpoint`
- `POST /api/runtime/jobs/{job_handle}/restore`
- `GET /api/runtime/jobs/{job_handle}`
- `GET /api/runtime/jobs/{job_handle}/checkpoint`

保留现有：

- `POST /api/runtime/reservations`
- `POST /api/runtime/jobs/launch`
- `GET /api/runtime/jobs`
- `POST /api/runtime/jobs/{job_handle}/terminate`

### 7.2 runtime job 控制语义

`pause`：

- 通过 runtime store 找到 job 对应 PID
- 复用 `controllers/task_control.py` 的 `psutil.Process(pid).suspend()`
- runtime job 状态从 `running / ready` 进入 `paused`

`resume`：

- 复用 `psutil.Process(pid).resume()`
- runtime job 状态从 `paused` 进入 `running`
- 对 service job 继续复用 readiness 检测，回到 `ready`

`checkpoint`：

- 仅允许 `checkpoint_policy == app_managed`
- 节点侧写入 checkpoint 请求文件
- runtime job 状态进入 `checkpoint_requested`
- agent 轮询 checkpoint 结果文件并显式更新为 `checkpoint_ready` 或 `checkpoint_failed`

`restore`：

- 基于 manifest 重新 launch 作业
- 复用现有 launch payload
- 附加 restore 上下文环境变量
- runtime job 状态进入 `restoring`，随后回到 `running / ready`

### 7.3 应用自管 checkpoint 契约

每个 runtime job 创建固定目录：

- `runtime/<job_handle>/control/`
- `runtime/<job_handle>/artifacts/`

launch 时向应用注入：

- `AIDC_JOB_HANDLE`
- `AIDC_JOB_ID`
- `AIDC_CONTROL_DIR`
- `AIDC_ARTIFACT_ROOT`
- `AIDC_CHECKPOINT_POLICY`
- `AIDC_RESTORE_FROM`

其中 `AIDC_RESTORE_FROM` 只在 restore 场景注入。

checkpoint 请求文件：

- `checkpoint-request.json`
  - `checkpoint_id`
  - `artifact_root`
  - `timeout_seconds`
  - `requested_at`
  - `reason`

checkpoint 结果文件：

- `checkpoint-result.json`
  - 成功：
    - `checkpoint_id`
    - `status = ready`
    - `manifest_path`
    - `artifact_paths`
    - `completed_at`
  - 失败：
    - `checkpoint_id`
    - `status = failed`
    - `error`
    - `completed_at`

平台不解析训练框架内部内容，只校验结果文件是否完整。

### 7.4 execution backend 扩展

扩展 `HTTPAgentProcessBackend`：

- `get_job(node, job_handle)`
- `pause_job(node, job_handle)`
- `resume_job(node, job_handle)`
- `checkpoint_job(node, job_handle, payload)`
- `get_checkpoint(node, job_handle)`
- `restore_job(node, payload)`

`SSHProcessBackend` 与 `LocalProcessBackend` 继续显式 `NotImplementedError`，不在本阶段实现。

### 7.5 execution orchestrator 扩展

`ExecutionOrchestrator` 扩展为统一 runtime 控制入口，新增：

- `pause_runtime_job(node, job_handle)`
- `resume_runtime_job(node, job_handle)`
- `checkpoint_runtime_job(node, job_handle, payload)`
- `restore_runtime_job(node, payload)`
- `get_runtime_job(node, job_handle)`
- `get_runtime_checkpoint(node, job_handle)`

launch/dispatch 主链路保持现有行为，不与新控制动作混写在同一 helper 中。

### 7.6 cluster control 作业动作

新增真实作业动作 helper，放在 `control_plane_job_actions.py`：

- `pause_running_job()`
- `resume_paused_job()`
- `request_checkpoint_for_job()`
- `restore_checkpointed_job()`

它们统一遵循：

1. 读取 job 与 allocation
2. 找到 node 与 runtime handle
3. 调 orchestrator
4. 根据 runtime 返回更新 `cluster_jobs / cluster_allocations`
5. 返回刷新后的 job projection

`change_job_state()` 继续保留，但只用于纯控制面状态变更，不再承担真实 runtime job 控制。

### 7.7 状态机

#### job 状态

保留现有：

- `queued`
- `pending`
- `running`
- `ready`
- `paused`
- `failed`
- `succeeded`
- `canceled`
- `preempting`
- `preempted`
- `requeue_requested`

新增：

- `pausing`
- `resuming`
- `checkpoint_requested`
- `checkpointing`
- `checkpoint_ready`
- `checkpoint_failed`
- `restoring`

#### allocation 状态

保留现有：

- `active`
- `paused`
- `releasing`
- `released`
- `canceled`

新增：

- `checkpointing`
- `restoring`

### 7.8 持久化模型

#### cluster 侧

`cluster_jobs` 增加 checkpoint 指针字段：

- `checkpoint_id`
- `checkpoint_status`
- `checkpoint_manifest_path`
- `checkpoint_error`
- `checkpoint_updated_at`

新增表 `cluster_checkpoints`：

- `checkpoint_id`
- `job_id`
- `allocation_id`
- `node_id`
- `status`
- `manifest_path`
- `artifact_paths_json`
- `error`
- `created_at`
- `updated_at`

这样 `cluster_jobs` 保存“最近一次 checkpoint 指针”，`cluster_checkpoints` 保存历史明细。

#### node runtime 侧

`RuntimeStore` 的 runtime job 记录增加：

- `control_dir`
- `artifact_root`
- `checkpoint_state`
- `checkpoint_id`
- `checkpoint_manifest_path`
- `checkpoint_error`
- `paused_at`
- `resumed_at`

### 7.9 reconcile 策略

本阶段不立即把 scheduler 改造成 checkpoint-aware preemption。

调和器只做两件事：

1. 能识别 runtime 的 `paused / running / ready / checkpoint_ready / checkpoint_failed`
2. 把这些真实状态同步回 cluster control

`preempt_then_place` 仍保持当前“取消并释放”的执行语义。

checkpoint 先作为独立作业动作落地，待主链路稳定后再接入抢占/迁移。

## 8. 前端与人工控制

### 8.1 capability 表单

在 `frontend/src/lib/controlCapabilityForms.js` 增加：

- `job.checkpoint`
- `job.restore`

`job.checkpoint` 字段：

- `job_id`
- `timeout_seconds` 可选

`job.restore` 字段：

- `job_id`
- `checkpoint_id` 可选

不要求用户手填 `manifest_path`。

### 8.2 作业账本展示

`ClusterJobLedger.vue` 增加对以下状态的紧凑展示：

- `pausing`
- `resuming`
- `checkpoint_requested`
- `checkpointing`
- `checkpoint_ready`
- `checkpoint_failed`
- `restoring`

每条作业增加一块精简 checkpoint 信息：

- 当前 checkpoint 状态
- 最近一次 checkpoint id
- 查看详情按钮

### 8.3 操作按钮

按钮可见性规则扩展为：

- `running / ready`
  - `pause`
  - `checkpoint`
  - `requeue`
  - `preempt`
  - `cancel`
- `paused`
  - `resume`
  - `checkpoint`
  - `requeue`
  - `cancel`
- `checkpoint_ready`
  - `restore`
  - `requeue`
- `checkpoint_failed`
  - `checkpoint`
  - `cancel`

## 9. Agent 接入

新增 capability：

- `job.checkpoint`
- `job.restore`

放入 cluster execution capability 层，而不是裸 PID task capability 层。

补充 heuristic / planner action 映射：

- `checkpoint_job -> job.checkpoint`
- `restore_job -> job.restore`

`goal_parser.py` 的 `JOB_ACTIONS` 也要补上 checkpoint/restore，确保 runtime goal 的完成条件可正确表达。

## 10. 实现顺序

### 阶段 1：真实 pause/resume

目标：

- runtime API 支持 `pause/resume`
- orchestrator/backend 打通
- `job.pause / job.resume` 真实控制下位机
- cluster state 与 runtime state 一致

### 阶段 2：app-managed checkpoint/restore

目标：

- checkpoint 请求与结果契约落地
- runtime store 记录 checkpoint 元数据
- `job.checkpoint / job.restore` 打通
- 前端与 Agent 可见 checkpoint 状态

### 阶段 3：checkpoint-aware preemption

本设计只定义入口，不在本阶段实现。

## 11. 测试策略

坚持 TDD，优先补红灯测试：

1. server-agent runtime API
   - `pause`
   - `resume`
   - `checkpoint`
   - `restore`
2. execution backend/orchestrator
   - 新接口调用正确
3. cluster control
   - `job.pause / job.resume / job.checkpoint / job.restore`
4. frontend
   - capability form
   - 状态映射
   - 账本操作显示

Windows 侧验证优先：

- 后端 pytest
- 前端 `npm test`
- 前端 `npm run build`

## 12. 风险与约束

- app-managed checkpoint 的成败依赖业务进程配合实现契约
- 如果应用不写 `checkpoint-result.json`，平台必须显式超时报错，不能静默成功
- 当前阶段不处理 checkpoint artifact 的远程复制
- checkpoint 成功不等于 restore 一定成功，restore 仍然由应用自行负责
