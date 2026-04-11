# Cluster Governance Focused Testing Design

**背景**

当前 `testdoc/作品报告_网页叙事版.html` 的第 5 章混入了多条次要叙事，包括导入边界、作用域过滤、Agent 接入、历史一致性与扩展能力状态。它们虽然都来自代码或实验，但会分散评审对“系统是否具备真实集群治理能力”的注意力。用户要求删除这些不重要的信息，把第 5 章收敛为“治理动作如何改变集群状态”的单一主线。

**目标**

把第 5 章重构为围绕集群治理闭环的证据型叙事，只保留能直接证明以下能力的内容：

1. 系统能发现功耗/告警风险，并通过治理动作改变真实设备状态。
2. 系统能针对队列、作业、节点、allocation 做集群级治理决策，而不是只展示监控数据。
3. 系统能把调和执行结果和治理状态写回控制台与复盘链路，形成可审计证据。

**非目标**

以下内容不再作为第 5 章重点，除非在其他章节另有承载：

1. 导入边界是否正确建立。
2. 历史查询是否严格遵守 scope。
3. Agent 采样、缓存、透传、启动提示等接入质量。
4. Graph、AI Runtime、扩展层漂移状态。

**代码依据**

本次重构后的第 5 章必须只围绕以下真实治理链路组织：

1. 功耗与告警治理：
   - `backend/app/services/alert_engine.py`
   - `backend/app/services/scheduler.py`
   - `backend/app/services/ssh_linux_provider.py`
   - `server-agent/controllers/power_control.py`
2. 集群调度与决策：
   - `backend/app/api/cluster_jobs.py`
   - `backend/app/services/cluster_control/scheduler_core.py`
   - `backend/app/services/cluster_control/reconcile_controller.py`
   - `backend/app/services/cluster_control/reconcile_execution.py`
   - `backend/app/services/cluster_control/runtime_feedback.py`
3. 集群治理控制台消费：
   - `frontend/src/views/ClusterJobs.vue`
   - `frontend/src/components/cluster/ClusterQueueBoard.vue`
   - `frontend/src/components/cluster/ClusterAllocationPanel.vue`
   - `frontend/src/components/cluster/ClusterJobLedger.vue`

**保留内容**

第 5 章仅保留四组证据：

1. `实验 A：真实功耗/告警治理闭环`
   - 保留已完成的远端 3090 实测。
   - 保留两张现有图：
     - `book_remote_budget_experiment.svg`
     - `book_remote_budget_timeline.svg`
   - 保留阶段汇总表、原始 25 个采样点表、JSON/CSV 文件说明。
   - 结论只聚焦“越阈 -> 下发 -> 回落 -> 复位”。

2. `实验 B：集群调度决策矩阵`
   - 新增围绕 `ClusterSchedulerCore.plan_job()` 的治理图。
   - 只展示与治理相关的 5 种决策：
     - `place`
     - `wait`
     - `reject`
     - `hold`
     - `preempt_then_place`
   - 每个决策都必须给出：
     - 输入条件
     - 调度输出
     - 对集群状态的直接含义

3. `实验 C：调和执行与状态回写`
   - 新增围绕 `ClusterReconcileController.run_once()` 与 `/api/cluster/reconcile` 的图表。
   - 重点展示：
     - `runtime_status`
     - `tick_count`
     - `last_summary`
     - `skipped / executed`
   - 目标是证明系统不是只会“计划”，还会推动集群状态变化并产出复盘摘要。

4. `实验 D：治理对象覆盖与审计证据`
   - 新增小图或小表。
   - 只保留以下动作对象：
     - `job.submit`
     - `job.pause / resume / checkpoint / restore`
     - `queue.reconcile`
     - `node.drain / undrain`
     - `allocation.release`
   - 目标是证明平台治理对象覆盖 job、queue、node、allocation 四类核心集群对象。

**删除内容**

第 5 章删除以下内容与相应图表引用：

1. `实验一：作用域收缩与越界拦截`
2. `实验二：历史查询与回放一致性`
3. `实验三：Agent 数据链路有效性`
4. `实验四：控制平面闭环验证`
5. `Agent 运行模式与平台适配`
6. `Agent 有效性分析`
7. `平台消费 Agent 数据的有效性分析`
8. `扩展能力验证状态`
9. 任何与“平台规模”“测试资产分布”“扩展层状态”相关，但不能直接支撑集群治理能力的第 5 章描述

说明：这些内容不要求全仓删除，只要求从第 5 章删除，不再干扰评审对治理主线的理解。

**新的第 5 章结构**

第 5 章改为以下顺序：

1. `5.1 集群治理测试目标与数据来源`
   - 只写两类数据来源：
     - 真实远端能耗闭环实测
     - 集群调度/调和代码链与受控决策实验
   - 删除与 Agent/scope 相关的背景描述。

2. `5.2 实验 A：真实功耗告警治理闭环`
   - 图 1：摘要图
   - 图 2：时间线图
   - 表 1：阶段关键数据
   - 表 2：原始采样点

3. `5.3 实验 B：集群调度决策矩阵`
   - 一张图解释调度如何把输入资源状态映射为治理决策。

4. `5.4 实验 C：调和执行与状态回写`
   - 一张图解释 reconcile controller 如何将手动/后台调和推进为状态变化与 summary。

5. `5.5 实验 D：治理对象覆盖与审计证据`
   - 一张图或表解释集群控制台实际可治理的对象与对应动作。

6. `5.6 集群治理能力结论`
   - 只得出和治理相关的结论：
     - 风险治理能力
     - 资源调度能力
     - 调和执行能力
     - 审计复盘能力

**图表设计原则**

新的第 5 章图表必须满足以下约束：

1. 每张图必须直接回答一个治理问题，而不是做模块说明。
2. 每张图必须带“数据代表什么 / 证明什么能力”的文字说明。
3. 真实实测与受控决策实验必须明确区分，不能混写成同一种证据。
4. 图表标题和编号允许重排，以适应治理主线。

**实现影响**

将修改以下文件：

1. `testdoc/作品报告_网页叙事版.html`
   - 重写第 5 章结构与文案。
2. `testdoc/scripts/report_book_charts_experiments.py`
   - 删除与 scope/history/agent/control_plane 相关的第 5 章图。
   - 新增 cluster governance 专题图。
3. `testdoc/scripts/generate_report_book_assets.py`
   - 调整图表生成清单。
4. `testdoc/scripts/report_book_cluster_governance_dataset.py`
   - 新增集群治理数据整理脚本，为 cluster governance 图提供结构化输入。

**风险与约束**

1. 已有真实数据里最强的是功耗治理闭环，因此该部分必须保留并放在第 5 章最前。
2. 集群作业/调和部分当前更适合做“受控决策实验”，不应伪装成已在多节点生产环境完整实跑。
3. 删除图表时要避免破坏其他章节引用。

**验收标准**

当以下条件同时满足时，视为本次重构完成：

1. 第 5 章不再出现 Agent/scope/history/extension 作为主实验。
2. 第 5 章所有图、表、段落都直接围绕集群治理能力展开。
3. 至少保留 1 组真实实测证据和 2 组集群治理受控实验/决策证据。
4. 裁判只看第 5 章，也能明确理解系统的治理对象、治理动作、状态变化与结论。
