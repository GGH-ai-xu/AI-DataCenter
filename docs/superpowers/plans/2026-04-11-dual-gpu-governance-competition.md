# Dual GPU Governance Competition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在真实远端 3090 主机上完成一组“双 GPU 并发负载 + 单 GPU 治理 + 单 GPU 对照”的实验，产出可直接支撑作品书的多维数据与图表。

**Architecture:** 复用现有 `SshLinuxProvider`、`SchedulerEngine`、`AlertEngine` 和真实预算治理实验脚本的公共逻辑，新增一套双 GPU 实验脚本来负责候选 GPU 探测、双工作负载启动、针对性预算治理、同步采样与收尾恢复。图表生成与结论文档只消费结构化 JSON/CSV 结果，不直接读取命令输出。

**Tech Stack:** Python 3.10, asyncssh, existing backend services, SVG chart scripts, CSV/JSON artifacts

---

## File Structure

**Create:**
- `testdoc/scripts/real_remote_dual_gpu_competition.py`
- `testdoc/scripts/real_remote_dual_gpu_competition_charts.py`
- `testdoc/data/real_remote_dual_gpu_competition.json`
- `testdoc/data/real_remote_dual_gpu_competition_samples.csv`
- `testdoc/data/real_remote_dual_gpu_competition_summary.csv`
- `testdoc/assets/dual_gpu_competition_timeline.svg`
- `testdoc/assets/dual_gpu_competition_comparison.svg`
- `testdoc/assets/dual_gpu_competition_latency.svg`

**Modify:**
- `testdoc/scripts/real_remote_budget_experiment_common.py`
- `testdoc/README.md`

**Reuse:**
- `testdoc/scripts/real_remote_budget_experiment.py`
- `backend/app/services/scheduler.py`
- `backend/app/services/ssh_linux_provider.py`
- `testdoc/scripts/report_book_svg_base.py`

---

### Task 1: 补齐双 GPU 实验的公共能力

**Files:**
- Modify: `testdoc/scripts/real_remote_budget_experiment_common.py`
- Test: `cmd.exe /c ".venv\Scripts\python.exe -m py_compile testdoc\scripts\real_remote_budget_experiment_common.py"`

- [ ] **Step 1: 增加双卡候选筛选与角色选择辅助函数**

```python
def find_idle_gpu_candidates(gpus: list[dict], minimum_count: int = 2) -> list[dict]:
    return [
        gpu for gpu in gpus
        if float(gpu.get("power_usage", 0) or 0) <= SAFE_IDLE_POWER_WATTS
        and int(gpu.get("gpu_utilization", 0) or 0) <= 10
    ][:minimum_count]


def choose_governance_pair(gpus: list[dict]) -> tuple[dict, dict]:
    candidates = find_idle_gpu_candidates(gpus, minimum_count=2)
    if len(candidates) < 2:
        raise RuntimeError("空闲 GPU 少于 2 张，无法执行双 GPU 实验")
    return candidates[0], candidates[1]
```

- [ ] **Step 2: 增加双卡窗口汇总与延迟统计辅助函数**

```python
def summarize_role_window(samples: list[dict], role: str, phase: str) -> dict:
    role_samples = [
        item for item in samples
        if item["gpu_role"] == role and item["phase"] == phase
    ]
    return summarize_window(role_samples)
```

```python
def compute_transition_latency(samples: list[dict], role: str, threshold: float) -> dict:
    role_samples = [item for item in samples if item["gpu_role"] == role]
    first_alert = next((item for item in role_samples if item["above_power_alert"]), None)
    first_safe = next(
        (item for item in role_samples if item["phase"] == "post_action" and item["power_usage"] < threshold),
        None,
    )
    return {
        "first_alert_elapsed_s": first_alert["elapsed_s"] if first_alert else None,
        "first_safe_elapsed_s": first_safe["elapsed_s"] if first_safe else None,
    }
```

- [ ] **Step 3: 运行语法校验**

Run: `cmd.exe /c ".venv\Scripts\python.exe -m py_compile testdoc\scripts\real_remote_budget_experiment_common.py"`
Expected: 退出码 0

### Task 2: 实现双 GPU 真实实验脚本

**Files:**
- Create: `testdoc/scripts/real_remote_dual_gpu_competition.py`
- Test: `cmd.exe /c ".venv\Scripts\python.exe testdoc\scripts\real_remote_dual_gpu_competition.py --check-only --host 10.151.225.108 --port 22 --username dell --password ***** --sudo-password *****"`

- [ ] **Step 1: 写脚本骨架与参数解析**

```python
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="双 GPU 并发竞争治理实验")
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=22)
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--sudo-password", default="")
    parser.add_argument("--check-only", action="store_true")
    return parser.parse_args()
```

- [ ] **Step 2: 实现 check-only 探测，两张空闲 GPU 不足时显式失败**

```python
gpus = await provider.get_all_gpus()
governance_gpu, control_gpu = choose_governance_pair(gpus)
return {
    "check_only": True,
    "governance_gpu": governance_gpu,
    "control_gpu": control_gpu,
}
```

- [ ] **Step 3: 实现双工作负载启动、双角色优先级设置与同步采样**

```python
governance_pid, governance_script, governance_log = await start_workload(provider, governance_gpu_index, python_bin)
control_pid, control_script, control_log = await start_workload(provider, control_gpu_index, python_bin)
await store.set_task_priority(governance_pid, "deferrable")
await store.set_task_priority(control_pid, "urgent")
```

```python
def sample_roles(gpus: list[dict], role_map: dict[int, str], phase: str, started_at: float) -> list[dict]:
    rows = []
    total_power = sum(float(item.get("power_usage", 0) or 0) for item in gpus)
    timestamp = time.time()
    for gpu in gpus:
        index = int(gpu.get("index", -1))
        if index not in role_map:
            continue
        rows.append({
            "timestamp": round(timestamp, 3),
            "elapsed_s": round(timestamp - started_at, 2),
            "phase": phase,
            "gpu_index": index,
            "gpu_role": role_map[index],
            "power_usage": round(float(gpu.get("power_usage", 0) or 0), 2),
            "power_limit": round(float(gpu.get("power_limit", 0) or 0), 2),
            "temperature": int(gpu.get("temperature", 0) or 0),
            "gpu_utilization": int(gpu.get("gpu_utilization", 0) or 0),
            "total_power": round(total_power, 2),
            "above_power_alert": float(gpu.get("power_usage", 0) or 0) >= POWER_ALERT_THRESHOLD,
        })
    return rows
```

- [ ] **Step 4: 实现针对治理 GPU 的预算治理**

```python
current_total = sum(float(gpu.get("power_usage", 0) or 0) for gpu in gpus)
governance_power = float(next(gpu for gpu in gpus if int(gpu["index"]) == governance_gpu_index)["power_usage"])
budget_limit = int(round(current_total - max(45, min(70, governance_power * 0.18))))
scheduler.configure_budget(True, budget_limit)
budget_actions = await scheduler.run_budget_schedule(gpus, processes)
```

```python
governance_actions = [
    item for item in budget_actions
    if int(item.get("target", {}).get("gpu_index", -1)) == governance_gpu_index
]
if not governance_actions:
    raise RuntimeError("预算调度未选中治理 GPU，实验不成立")
if any(int(item.get("target", {}).get("gpu_index", -1)) == control_gpu_index for item in budget_actions):
    raise RuntimeError("预算调度同时选中了对照 GPU，实验不成立")
```

- [ ] **Step 5: 实现收尾、结果落盘与恢复原始功耗上限**

```python
await stop_workload(provider, governance_pid, governance_script)
await stop_workload(provider, control_pid, control_script)
if managed_limit:
    await provider.set_power_limit(governance_gpu_index, original_governance_limit)
```

```python
output = {
    "host": args.host,
    "governance_gpu_index": governance_gpu_index,
    "control_gpu_index": control_gpu_index,
    "samples": all_samples,
    "latency": latency,
    "scheduler_run": scheduler_run,
    "summary": summary,
}
```

- [ ] **Step 6: 运行 check-only 探测**

Run: `cmd.exe /c ".venv\Scripts\python.exe testdoc\scripts\real_remote_dual_gpu_competition.py --check-only --host 10.151.225.108 --port 22 --username dell --password admin-123456 --sudo-password admin-123456"`
Expected: 输出两张空闲 GPU 候选；若不足两张则 FAIL 并停止

- [ ] **Step 7: 运行真实实验**

Run: `cmd.exe /c ".venv\Scripts\python.exe testdoc\scripts\real_remote_dual_gpu_competition.py --host 10.151.225.108 --port 22 --username dell --password admin-123456 --sudo-password admin-123456"`
Expected: 生成 `testdoc/data/real_remote_dual_gpu_competition.json` 与 `testdoc/data/real_remote_dual_gpu_competition_samples.csv`

### Task 3: 生成多维图表与摘要表

**Files:**
- Create: `testdoc/scripts/real_remote_dual_gpu_competition_charts.py`
- Create: `testdoc/data/real_remote_dual_gpu_competition_summary.csv`
- Create: `testdoc/assets/dual_gpu_competition_timeline.svg`
- Create: `testdoc/assets/dual_gpu_competition_comparison.svg`
- Create: `testdoc/assets/dual_gpu_competition_latency.svg`
- Test: `cmd.exe /c ".venv\Scripts\python.exe testdoc\scripts\real_remote_dual_gpu_competition_charts.py"`

- [ ] **Step 1: 读取 JSON 并导出汇总 CSV**

```python
data = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
summary_rows = [
    {"role": "governance", "phase": "baseline", **data["summary"]["governance"]["baseline"]},
    {"role": "governance", "phase": "post_action", **data["summary"]["governance"]["post_action"]},
    {"role": "control", "phase": "baseline", **data["summary"]["control"]["baseline"]},
    {"role": "control", "phase": "post_action", **data["summary"]["control"]["post_action"]},
]
```

- [ ] **Step 2: 生成双卡时间线图**

```python
def timeline_svg(data: dict) -> str:
    return svg_frame(
        "双 GPU 并发竞争治理时间线",
        "同时显示治理 GPU 与对照 GPU 的功耗、功耗上限和治理时刻",
        1420,
        760,
        body,
    )
```

- [ ] **Step 3: 生成治理卡 vs 对照卡对比图**

```python
def comparison_svg(data: dict) -> str:
    return svg_frame(
        "治理卡与对照卡效果对比",
        "比较峰值功耗、后窗均值、温度均值和越阈样本",
        1420,
        620,
        body,
    )
```

- [ ] **Step 4: 生成延迟与清洁率图**

```python
def latency_svg(data: dict) -> str:
    return svg_frame(
        "治理时延与清洁率",
        "展示首次越阈、治理动作、首次回落与后窗清洁率",
        1420,
        560,
        body,
    )
```

- [ ] **Step 5: 运行图表脚本**

Run: `cmd.exe /c ".venv\Scripts\python.exe testdoc\scripts\real_remote_dual_gpu_competition_charts.py"`
Expected: 生成 3 张 SVG 与 1 个 summary CSV

### Task 4: 记录实验口径并做最小验证

**Files:**
- Modify: `testdoc/README.md`
- Test: `cmd.exe /c ".venv\Scripts\python.exe -m py_compile testdoc\scripts\real_remote_dual_gpu_competition.py testdoc\scripts\real_remote_dual_gpu_competition_charts.py"`

- [ ] **Step 1: 在 README 中记录实验产物与口径**

```md
## 双 GPU 并发竞争治理实验

- 原始数据：`testdoc/data/real_remote_dual_gpu_competition.json`
- 原始样本：`testdoc/data/real_remote_dual_gpu_competition_samples.csv`
- 摘要图：`testdoc/assets/dual_gpu_competition_*.svg`
```

- [ ] **Step 2: 运行语法校验**

Run: `cmd.exe /c ".venv\Scripts\python.exe -m py_compile testdoc\scripts\real_remote_dual_gpu_competition.py testdoc\scripts\real_remote_dual_gpu_competition_charts.py"`
Expected: 退出码 0

- [ ] **Step 3: 手工核对关键结果字段**

Run: `python3 - <<'PY'
import json
from pathlib import Path
data = json.loads(Path("testdoc/data/real_remote_dual_gpu_competition.json").read_text(encoding="utf-8"))
print(data["governance_gpu_index"], data["control_gpu_index"])
print(data["summary"]["governance"]["post_action"]["above_alert_samples"])
print(data["scheduler_run"]["budget_actions"])
PY`
Expected: 打印治理卡 / 对照卡编号、治理后越阈样本数和预算动作清单
