# 人工 Capability 控制面设计
日期：2026-04-10
## 1. 背景
当前平台已经具备两类控制能力：
- 面向人工的零散控制 API，例如任务暂停/恢复/终止、任务优先级调整、预算配置、手动限功率、执行一次调度、作业提交与查询。
- 面向 Agent runtime 的 capability registry，由 `goal_runtime/platform_capabilities.py` 注册系统可执行能力。
这两条路径目前仍是分裂的：
- 人工控制和 Agent 控制没有共用统一的 command 服务。
- 同一动作经常有两份实现，权限、作用域和审计逻辑容易漂移。
- 低频和长尾能力没有稳定的人工入口。
- 集群调度能力已经开始落地，但作业、队列、allocation、节点类操作还缺少完整的人工控制面。
目标是补一套与现有设计兼容的“人工 Capability 控制面”，让人工和 Agent 共用同一个控制底座，同时不破坏现有治理页信息架构。
## 2. 目标与非目标
### 2.1 目标
- 为已注册 capability 提供统一的人工可调用接口。
- 保持当前一级导航和治理域结构不变。
- 让人工和 Agent 共享同一套 capability 定义、权限判定、审批流程和审计记录。
- 在治理页内形成“高频显式操作 + 长尾能力抽屉”的交互模式。
- 为后续扩展 `job.cancel`、`allocation.release`、`node.drain`、`queue` 策略操作预留接口和 UI 容器。
### 2.2 非目标
- 本轮不新增新的一级页面。
- 本轮不把 AI 助手页改造成完整手工控制台。
- 本轮不一次性删除现有 `/api/tasks/*`、`/api/scheduler/*`、`/api/cluster/*` 入口。
- 本轮不实现尚未落地的 capability 本体，例如 `job.pause`、`job.resume`、`job.cancel`。
## 3. 兼容性优先策略
采用“治理域承载人工控制，后端新增统一 control plane，旧 API 逐步收口”的方案。
- 顶层导航保持不变。
- `治理` 继续作为人工控制主入口。
- `AI 助手` 保持为自然语言入口和执行轨迹页，不直接承载大规模手工控制。
- 旧的人工 API 先保留，但逐步改成调用统一 control plane。
这是与当前设计兼容性最高的方案，因为现有前端路由已经把任务、调度、集群能力向治理域收口，继续沿这个方向演进可以避免重复导航和语义冲突。
## 4. 总体架构
系统增加一层统一控制面，形成以下链路：
`治理页 / AI 助手 -> Control API -> Control Plane -> Capability Registry -> 实际执行器`
边界定义：
- `Capability Registry`
  定义系统有哪些能力。
- `Control Plane`
  决定用户是否能调、是否需要审批、如何执行、如何审计。
- `Control API`
  为人工与前端提供统一 HTTP 接口。
- `Domain UI`
  以治理页为宿主，把高频动作做成显式控件，把低频动作放进能力抽屉。
原则：
- 不允许人工入口直接绕过 capability registry 操作底层 agent。
- 不允许高风险动作绕过统一审计和审批。
- 不允许每个页面自行发明一套风险确认逻辑。
## 5. 后端设计
### 5.1 新增 API
新增 `backend/app/api/control.py`，第一版提供以下接口：
- `GET /api/control/capabilities`
  返回当前用户、当前 workspace 下可人工调用的 capability 列表。
- `GET /api/control/catalog`
  返回按 domain 分组后的能力目录，供治理页构建操作抽屉。
- `POST /api/control/commands`
  统一执行入口，接收 `capability_name + arguments + permission_mode + acknowledge_risk + dry_run + reason + source_page`。
- `GET /api/control/commands`
  查询最近命令记录。
- `GET /api/control/commands/{command_id}`
  查询单条命令详情。
- `POST /api/control/commands/{command_id}/approve`
  审批待确认命令。
### 5.2 新增服务层
新增 `backend/app/services/control_plane/`，建议拆成以下模块：
- `catalog.py`
  读取 capability registry，并补齐人工展示所需元数据。
- `policy.py`
  根据用户角色、workspace、risk level、permission mode 判断是否允许执行。
- `executor.py`
  调用 capability handler，统一处理 dry-run、错误包装和结果结构。
- `audit.py`
  写入命令账本、审批账本和失败账本。
- `models.py`
  定义 `ControlCommandRecord`、`ApprovalRecord`、`CapabilityCatalogItem`。
### 5.3 Capability 来源
继续以 `backend/app/services/goal_runtime/platform_capabilities.py` 为能力注册源。
第一批纳入统一控制层的能力：
- `runtime.snapshot.read`
- `tasks.pause`
- `tasks.resume`
- `tasks.terminate`
- `tasks.priority.set`
- `scheduler.power_limit.set`
- `scheduler.budget.configure`
- `scheduler.run_once`
- `job.submit`
- `job.list`
- `job.get`
- `queue.status.read`
以下 capability 先不进入可执行人工目录，因为当前未实现：
- `job.pause`
- `job.resume`
- `job.cancel`
### 5.4 旧 API 的过渡策略
现有 API 暂不删除：
- `/api/tasks/*`
- `/api/scheduler/*`
- `/api/cluster/*`
过渡期处理方式：
- 第一阶段保留旧入口，对外行为不变。
- 第二阶段逐步把旧入口内部改造成薄代理，转发到 control plane。
- 第三阶段当前端全面切到 `/api/control/*` 后，再决定是否下线旧入口。
## 6. 前端设计
### 6.1 顶层结构
不新增一级导航，继续使用现有治理域：
- `治理 / 动作`
- `治理 / 策略`
- `治理 / 集群`
- `治理 / 审计`
### 6.2 治理 / 动作
承载当前导入 scope 下的高频运行时直接动作：
- 任务暂停、恢复、终止
- 任务优先级调整
- GPU 手动限功率
- 执行一次调度
- 当前 scope 摘要
该页右上角新增：
- `执行一次调度`
- `高级操作`
`高级操作` 打开统一能力抽屉，仅显示 `tasks` 与 `scheduler` 域的低频能力。
### 6.3 治理 / 策略
承载规则与治理参数配置：
- 总功率预算
- 碳预算
- 公平治理规则
- 抢占/优先级/审批相关策略参数
该页右上角新增：
- `新增策略`
- `高级能力`
能力抽屉只显示 `scheduler`、`policy`、`queues` 域能力。
### 6.4 治理 / 集群
承载集群级人工控制：
- 作业列表
- 作业提交
- 队列状态
- allocation 概览
- 作业详情抽屉
第二批扩展目标：
- 作业取消
- 作业暂停/恢复
- allocation release
- 节点 drain / undrain
- reservation 相关操作
该页右上角新增：
- `提交作业`
- `高级集群操作`
高级集群操作通过统一能力抽屉承载低频 cluster capability，避免页面被大量卡片填满。
### 6.5 治理 / 审计
从“看日志”升级为“看控制历史”，展示三类记录：
- 命令账本
- 审批账本
- 失败账本
每条记录展示：
- 时间
- 发起者
- 来源
- capability
- 目标摘要
- 状态
- 审批状态
- 结果摘要
详情抽屉展示：
- 输入参数
- 执行返回
- 错误信息
- 审批链路
- 关联 session 或 command
### 6.6 通用能力抽屉
新增统一组件 `CapabilityCommandDrawer`，作为治理页公共基础设施。
职责：
- 读取 capability catalog
- 按当前子页过滤能力
- 生成参数表单
- 显示作用域、风险等级、是否需要审批
- 支持 `dry_run`
- 执行命令并展示结果
- 跳转到审计详情
高频能力继续保留专门 UI，低频与长尾能力统一进入该抽屉。
## 7. 权限、审批与审计
### 7.1 角色层
当前支持的身份：
- `admin`
- `member`
- `observer`
角色只决定上限，不直接替代 capability 自身权限要求。
### 7.2 能力权限层
每个 capability 增加人工控制所需元数据：
- `required_role`
- `risk_level`
- `requires_scope`
- `approval_policy`
- `ui_hints`
风险等级分为：
- `observe`
- `operate`
- `control`
- `dangerous`
### 7.3 推荐角色策略
- `observer`
  只能读，不能创建 command。
- `member`
  可读当前可见 scope，可做低风险与部分中风险动作，默认不能执行危险动作。
- `admin`
  可执行全部 capability，但危险动作仍必须进入统一确认或审批，不允许绕过审计。
### 7.4 审批策略
统一三种执行模式：
- `direct`
  直接执行。
- `confirm_required`
  用户本人确认后执行。
- `approval_required`
  创建命令后进入待审批，再执行。
规则：
- 只读能力走 `direct`。
- 中风险运行时动作默认走 `confirm_required`。
- 危险动作默认走 `approval_required`。
### 7.5 审计模型
每次人工或 Agent 的正式操作都生成一条 `ControlCommandRecord`，至少包含：
- `command_id`
- `created_at`
- `operator_type`
- `operator_id`
- `workspace_key`
- `capability_name`
- `arguments`
- `risk_level`
- `permission_mode`
- `approval_state`
- `execution_state`
- `result_summary`
- `error_message`
- `related_session_id`
- `source_page`
审计页和 AI 页都从这套命令账本读取，不再维护各自独立的半结构化结果视图。
## 8. 与 AI 助手的关系
AI 助手保留“自然语言入口 + 运行轨迹”职责，不承担完整手工控制台职责。
协同关系：
- AI 助手负责理解目标、触发 control command、展示执行轨迹。
- 治理页负责显式人工操作和人工接管。
- 两者共享同一 control plane、审批逻辑和审计账本。
当 AI 执行失败或等待确认时，用户应能够跳转到治理审计页或对应治理子页继续人工处理。
## 9. 分阶段落地
### 阶段一
- 新增 `/api/control/capabilities`、`/api/control/commands`、`/api/control/commands/{id}`。
- 将已有稳定 capability 纳入 catalog。
- 治理页先接入统一能力抽屉。
- 审计页先读取 command 账本。
### 阶段二
- 让 `/api/tasks/*`、`/api/scheduler/*`、`/api/cluster/*` 逐步改为调用 control plane。
- 将集群页高频操作迁入统一命令链路。
- 接入审批流与统一失败记录。
### 阶段三
- 补齐 cluster capability，例如 `job.cancel`、`allocation.release`、`node.drain`。
- 统一 AI 助手与治理页的 command 跳转和回看能力。
- 根据实际使用情况决定是否下线旧人工控制 API。
## 10. 验收标准
- 人工和 Agent 至少在第一批 capability 上共用同一 command 执行链。
- 治理页不新增一级导航且不破坏现有结构。
- 新增 capability 无需新建页面即可通过能力抽屉进入人工控制面。
- 风险确认、审批和审计不再由各页面自行实现。
- `member` 无法执行超出其角色和 workspace 范围的控制动作。
- AI 助手发起的能力执行与人工手动执行能在同一审计模型中被追踪。
