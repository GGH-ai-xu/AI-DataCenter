# 集群自动调和控制器设计

日期：2026-04-10

## 1. 背景

当前系统已经支持：

- `queue.reconcile` 手工触发
- runtime 终态回传与自动资源回收
- `job.cancel` 对运行中作业走真实 terminate

但控制面仍然缺少“持续执行”的自动控制器：

- 需要用户手动点一次调和，队列才会继续推进
- 运行时不可用时没有显式的调和跳过状态
- 集群控制台看不到自动调和是否开启、最近是否成功

## 2. 目标

本阶段实现自动调和控制器第一刀：

1. 后端启动一个后台 `ClusterReconcileController`
2. 控制器按固定间隔执行集群调和
3. 运行时不健康时跳过本轮并显式记录原因
4. 手工 `POST /api/cluster/reconcile` 与后台循环共用同一套控制器状态
5. 前端展示自动调和开关、最近一次运行结果和最近错误

## 3. 备选方案

### 方案 A：独立后台控制器服务

做法：

- 新建 `ClusterReconcileController`
- 在 FastAPI lifespan 中启动
- 控制器依赖注入：
  - `nodes_loader`
  - `reconcile_runner`
  - `runtime_status_reader`

优点：

- 责任清晰，不污染 `ClusterControlPlaneService`
- 背景 loop、手工 run-once、状态缓存都统一在同一个服务里
- 方便后面继续补 retry policy

缺点：

- 需要新增状态 API 和少量前端展示逻辑

### 方案 B：直接在 `main.py` 里写 while loop

优点：

- 看起来改动少

缺点：

- 状态、调和逻辑、运行时判断都会散在 `main.py`
- 后续要加 retry / metrics 会很快失控

## 4. 选型

采用方案 A。

## 5. 设计

### 5.1 控制器职责

`ClusterReconcileController` 负责：

- 保存自动调和配置
  - `enabled`
  - `interval_seconds`
- 保存最近状态
  - `running`
  - `tick_count`
  - `last_started_at`
  - `last_finished_at`
  - `last_trigger`
  - `last_summary`
  - `last_error`
  - `last_skip_reason`
- 提供：
  - `start()`
  - `shutdown()`
  - `run_once(trigger=...)`
  - `snapshot()`
  - `configure(...)`

### 5.2 健康感知

本阶段只做最小健康感知：

- 调用 `runtime_status_reader()`
- 当 `status != connected` 时，本轮不执行 `reconcile_and_dispatch`
- 记录：
  - `last_skip_reason = runtime status: <status>`
  - `last_error = ""`
  - `last_summary = {"skipped": true, ...}`

不做节点级 health score，不做按节点剔除。

### 5.3 API

新增：

- `GET /api/cluster/controller`
  - 返回控制器当前快照
- `POST /api/cluster/controller`
  - 更新 `enabled`
  - 更新 `interval_seconds`

修改：

- `POST /api/cluster/reconcile`
  - 不再直接调 `cluster_control.reconcile_and_dispatch`
  - 改为走 `cluster_reconcile_controller.run_once(trigger="manual")`

### 5.4 前端

cluster console 顶部增加轻量控制器状态展示：

- 自动调和：开启 / 关闭
- 调和间隔
- 最近一次运行时间
- 最近一次摘要

工具栏增加一个开关按钮：

- 开启自动调和
- 关闭自动调和

手工“执行队列调和”按钮保留。

## 6. 非目标

本阶段不实现：

- retry policy
- 失败作业自动重入队列
- backend / node 细粒度健康打分
- 按节点隔离的自动调和

## 7. 测试

重点测试：

- 控制器在 runtime 不可用时会跳过并记录原因
- 控制器开启后后台 loop 会自动触发调和
- API 能读写控制器状态
- 前端模型能显示控制器状态摘要
