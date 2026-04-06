# 测试报告

> 生成时间：2026-04-02 | 执行者：Claude Code 自动化

## 测试总览

| 指标 | 值 |
|------|-----|
| 测试文件 | 16 |
| 测试用例 | 213 |
| 通过 | 213 |
| 失败 | 0 |
| 执行时间 | ~6 秒 |
| 运行命令 | `python -m pytest tests/ -v` |

## 测试分类

### 核心算法基准测试（`test_algorithm_benchmarks.py`）— 35 项

覆盖预测算法（EWA/线性/多项式）精度对比、公平性评分边界、让路评分单调性、碳排放计算、效率评分公式与分布差距量化。

| 测试类 | 用例数 | 覆盖内容 |
|--------|--------|----------|
| TestPredictionAlgorithms | 11 | EWA 趋势跟踪、线性外推、多项式防发散、自动择优一致性、正弦噪声 RMSE |
| TestFairnessScoring | 6 | 单用户满分、均等高分、垄断低分、可延迟惩罚、紧急加分、规则违规 |
| TestYieldScoring | 4 | 让路排序单调性、紧急进程排除、建议上限 |
| TestCarbonCalculation | 5 | 碳因子 0.5703、电价、kWh 转换、日投影、时段分类 |
| TestEfficiencyScoring | 5 | 利用率-功率比公式、温度惩罚 |
| TestDistributionGap | 3 | 均等/极端/三用户差距 |
| TestRuleBasedSuggestions | 2 | 去重策略、健康状态无建议 |

### 调度引擎测试（`test_scheduler.py`）— 22 项

覆盖温度规则引擎、功率预算分配、碳预算核算、tick 编排序列、执行参数校验。

| 测试类 | 用例数 | 覆盖内容 |
|--------|--------|----------|
| SchedulerEngineTests | 6 | 报告生成、AI 调度脱敏、演练/真实执行 |
| SchedulerRulesTests | 4 | 90°C 紧急/85°C 告警/正常无动作/多 GPU |
| SchedulerBudgetTests | 4 | 超预算限功率、暂停优先级顺序、低预算恢复 |
| SchedulerCarbonTests | 2 | 碳预算状态、碳预算超标 |
| SchedulerExecuteValidationTests | 4 | PID 无效/功率越界/未知动作/限值跟踪 |
| SchedulerTickTests | 2 | tick 规则执行、碳 Wh 累积 |

### 公平治理测试（`test_governance.py`）— 33 项

覆盖公平性评分 6 因子、系统公平指数、分布差距、规则违规检测、让路候选排序、可治理判定、建议生成。

| 测试类 | 用例数 | 覆盖内容 |
|--------|--------|----------|
| FairnessScoreTests | 6 | 单用户/均等/垄断/可延迟惩罚/紧急加分/加分上限 |
| SystemFairnessIndexTests | 3 | 空/均等/倾斜 |
| DistributionGapTests | 4 | 空/均等/极端/三用户 |
| RuleViolationTests | 4 | 任务数/GPU 数/显存/无违规 |
| YieldCandidateTests | 6 | 紧急排除/排序/优先级/违规/保护用户/上限 |
| GovernableFilterTests | 8 | 系统进程/背景命令/大显存例外/优先级覆盖 |
| RecommendationTests | 2 | 空用户/上限 |

### 能耗预测测试（`test_energy_prediction.py`）— 30 项

覆盖三种预测算法内部行为、效率评分、规则建议生成、时段分类与常量。

| 测试类 | 用例数 | 覆盖内容 |
|--------|--------|----------|
| EWAPredictionTests | 6 | 空默认/单值/上行/下行/alpha 权重/常数零方差 |
| LinearPredictionTests | 4 | 完美线性/不足数据/噪声 R²/外推方向 |
| PolynomialPredictionTests | 4 | 完美二次/不足数据/正发散/负发散 |
| EfficiencyScoreTests | 5 | 高效/低效/上限/75°C 惩罚/85°C 惩罚 |
| RuleBasedSuggestionTests | 5 | 健康无建议/低利用率/高温/多 GPU/去重 |
| TimePeriodTests | 3 | 高峰/平峰/低谷 |
| ConstantsTests | 3 | 碳因子/电价/碳计算 |

### 数据统计测试（`test_data_statistics.py`）— 9 项

覆盖 `DataStore.get_data_statistics()` 的聚合查询逻辑。

| 测试 | 覆盖内容 |
|------|----------|
| test_empty_db_returns_zero_totals | 空库返回零值 |
| test_empty_db_has_all_table_keys | 空库包含全部 6 张表键 |
| test_single_table_count | 单表插入后计数正确 |
| test_multiple_tables_sum | 多表总和正确 |
| test_collection_start_is_earliest_timestamp | 最早时间戳 |
| test_duration_hours_positive | 采集时长 > 0 |
| test_avg_records_per_hour | 吞吐率计算 |
| test_table_labels_are_chinese | 表标签为中文 |
| test_uninitialized_store_returns_empty | 未初始化安全返回 |

### 其他工程测试 — 84 项

| 文件 | 用例数 | 覆盖内容 |
|------|--------|----------|
| test_frontend_ui_structure.py | 30 | 前端视图结构、组件存在性、Tab 布局、响应式 |
| test_start_dev_scripts.py | 17 | 启动脚本、桌面壳、UTF-8、运行时配置 |
| test_frontend_performance_structure.py | 8 | 性能热路径、modular imports、chart 更新 |
| test_install_scripts.py | 6 | 安装脚本、依赖配置、rolldown 修复 |
| test_performance_hotpaths.py | 5 | 后端并发采集、批写入、SQLite pragma |
| test_connection_settings.py | 4 | 接入配置持久化、URL 解析 |
| test_agent_sampling_structure.py | 3 | Agent 采样缓存、非阻塞 CPU |
| test_llm_settings.py | 3 | LLM 配置快照、密钥脱敏 |
| test_energy_benchmark.py | 3 | 策略基准、调度历史统计 |
| test_privacy.py | 3 | 用户名脱敏、别名解析 |

## 关键基准结果

### 预测算法 RMSE 对比（合成正弦 + 10% 噪声数据）

EWA、线性回归、二次多项式三种算法均可在合成时序数据上产生合理预测；自动择优机制选择的算法与最低 RMSE 算法一致。

### 公平性评分边界

- 单用户 → 100 分（满分）
- 两用户均等 → ≥ 85 分
- 单用户占 80% 显存 → < 60 分
- 紧急任务加分上限 15 分

### 让路评分单调性

- 可延迟 > 普通（同等条件）
- 违规用户 > 非违规用户
- 紧急任务永远不出现在让路候选列表
