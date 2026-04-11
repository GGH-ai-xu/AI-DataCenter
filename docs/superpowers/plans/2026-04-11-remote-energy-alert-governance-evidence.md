# Remote Energy Alert Governance Evidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 基于真实远端 3090 服务器完成一组“高功耗触发 -> 人工调度治理 -> 功耗回落”的实验，并把真实结果与扩展仿真结果写入网页作品书。

**Architecture:** 复用仓库中已有的 `SshLinuxProvider`、`SchedulerEngine`、`AlertEngine` 与 `DataStore`，通过 SSH 直接连接远端主机而不是另起一套临时逻辑。实验脚本负责远端负载制造、采样、调度执行、数据落盘与恢复收尾，图表脚本和 HTML 页面只消费结构化结果，不直接拼接原始命令输出。

**Tech Stack:** Python 3.10, asyncssh, FastAPI backend services, SQLite, SVG chart scripts, HTML/CSS

---

### Task 1: 固化真实实验脚本

**Files:**
- Create: `testdoc/scripts/real_remote_budget_experiment.py`
- Modify: `testdoc/data/report_book_metrics.json`
- Test: `cmd.exe /c ".venv\Scripts\python.exe testdoc\scripts\real_remote_budget_experiment.py --help"`

- [ ] **Step 1: 写实验脚本骨架**

```python
async def main():
    args = parse_args()
    provider = build_provider(args)
    store = DataStore(args.output_db)
    scheduler = SchedulerEngine(provider, store, import_context=None, budget_enabled=True)
```

- [ ] **Step 2: 连接远端并验证 sudo / GPU 状态**

Run: `cmd.exe /c ".venv\Scripts\python.exe testdoc\scripts\real_remote_budget_experiment.py --check-only"`
Expected: 打印远端 GPU 列表、可用 GPU、sudo 能力与当前功耗上限。

- [ ] **Step 3: 实现负载制造、采样与治理闭环**

```python
before = await collect_window(provider, seconds=20)
workload = await start_remote_cuda_workload(executor, gpu_index)
peak = await wait_for_power_threshold(provider, gpu_index, threshold_watts=250)
actions = await scheduler.run_budget_schedule(gpus, processes)
results = await scheduler.execute_actions(actions)
after = await collect_window(provider, seconds=45)
```

- [ ] **Step 4: 实现收尾恢复逻辑**

```python
await stop_remote_workload(executor, pid)
await restore_power_limit(provider, gpu_index, original_limit)
```

- [ ] **Step 5: 运行脚本产出 JSON / CSV**

Run: `cmd.exe /c ".venv\Scripts\python.exe testdoc\scripts\real_remote_budget_experiment.py --host 10.151.225.108 --port 22 --username dell --password ***** --sudo-password *****"`
Expected: 生成 `testdoc/data/real_remote_budget_experiment.json` 和 `testdoc/data/real_remote_budget_samples.csv`。

### Task 2: 将真实实验结果接入作品书数据层

**Files:**
- Modify: `testdoc/scripts/report_book_dataset.py`
- Modify: `testdoc/data/report_book_metrics.json`
- Test: `cmd.exe /c ".venv\Scripts\python.exe testdoc\scripts\generate_report_book_assets.py"`

- [ ] **Step 1: 读取真实实验 JSON 并整理为页面指标**

```python
with open(real_path, "r", encoding="utf-8") as fh:
    real_exp = json.load(fh)
metrics["real_energy_experiment"] = real_exp
```

- [ ] **Step 2: 为缺少实测覆盖的维度保留扩展仿真字段**

```python
metrics["real_energy_experiment"]["simulated_extensions"] = build_simulated_extensions(real_exp)
```

- [ ] **Step 3: 重新生成图表资产**

Run: `cmd.exe /c ".venv\Scripts\python.exe testdoc\scripts\generate_report_book_assets.py"`
Expected: 生成新的 `book_*.svg`，且不破坏已有图表引用。

### Task 3: 丰富测试分析章节

**Files:**
- Modify: `testdoc/scripts/report_book_charts_experiments.py`
- Modify: `testdoc/作品报告_网页叙事版.html`
- Test: `rg -n "真实实验|扩展仿真|功耗|告警|治理" testdoc/作品报告_网页叙事版.html`

- [ ] **Step 1: 新增能耗治理主题图**

```python
draw_power_curve(...)
draw_alert_clearance(...)
draw_action_timeline(...)
```

- [ ] **Step 2: 在第五章明确区分真实实验与扩展仿真**

```html
<p>真实实验用于证明闭环可运行，扩展仿真用于补齐评审所需的多批次统计维度，两者分开展示。</p>
```

- [ ] **Step 3: 改写文字解释每张图证明的能力**

```html
<p>图中功耗峰值回落、告警状态变化和功耗上限写回，分别对应调度发现异常、执行治理动作和闭环生效三个环节。</p>
```

- [ ] **Step 4: 回归生成最终资产**

Run: `cmd.exe /c ".venv\Scripts\python.exe testdoc\scripts\generate_report_book_assets.py"`
Expected: 图表全部成功生成，HTML 中引用路径存在。

### Task 4: 验证并记录结论

**Files:**
- Modify: `testdoc/README.md`
- Test: `python3 -m unittest discover -s tests -p "test_*.py"`
- Test: `cmd.exe /c ".venv\Scripts\python.exe testdoc\scripts\real_remote_budget_experiment.py --check-only"`

- [ ] **Step 1: 记录真实实验命令与风险边界**

```md
仅在空闲 GPU 上执行负载脚本；测试结束后恢复原始功耗上限并终止负载进程。
```

- [ ] **Step 2: 运行最小回归检查**

Run: `python3 -m unittest discover -s tests -p "test_*.py"`
Expected: 仓库级回归不因测试文档脚本而失败。

- [ ] **Step 3: 整理最终结论**

```md
真实实验结论：系统已有调度规则可通过 SSH provider 对远端 GPU 施加功耗治理并观察回落。
扩展仿真结论：在真实样本基础上补足多轮次统计视角，但不宣称为全部实测。
```
