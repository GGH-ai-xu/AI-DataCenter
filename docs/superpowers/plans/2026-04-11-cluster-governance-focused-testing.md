# Cluster Governance Focused Testing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将作品书第 5 章重构为只围绕“集群治理动作如何改变集群状态”的证据型章节，删除与 scope/history/Agent/extension 相关的次要实验。

**Architecture:** 保留已经拿到的真实远端功耗治理闭环作为第一个强证据，再新增一个只服务于第 5 章的 `cluster_governance` 数据层，分别产出调度决策矩阵、调和执行状态和治理对象覆盖数据。HTML 只消费这四组治理证据，生成脚本停止输出不再需要的第 5 章实验图，回归测试直接检查第 5 章是否只剩集群治理主线。

**Tech Stack:** Python 3.10, unittest/pytest, HTML/CSS, SVG asset scripts, existing backend cluster-control services

---

## File Structure

**Create:**
- `testdoc/scripts/report_book_cluster_governance_dataset.py`
- `tests/test_report_book_cluster_governance_focus.py`

**Modify:**
- `testdoc/scripts/report_book_dataset.py`
- `testdoc/scripts/report_book_charts_experiments.py`
- `testdoc/scripts/generate_report_book_assets.py`
- `testdoc/作品报告_网页叙事版.html`
- `testdoc/assets/report_book.css`

**Keep As Is But Reuse:**
- `testdoc/data/real_remote_budget_experiment.json`
- `testdoc/data/real_remote_budget_samples.csv`
- `testdoc/data/real_remote_budget_summary.csv`
- `testdoc/assets/book_remote_budget_experiment.svg`
- `testdoc/assets/book_remote_budget_timeline.svg`

---

### Task 1: 建立集群治理数据层与回归测试

**Files:**
- Create: `testdoc/scripts/report_book_cluster_governance_dataset.py`
- Create: `tests/test_report_book_cluster_governance_focus.py`
- Modify: `testdoc/scripts/report_book_dataset.py`

- [ ] **Step 1: 写失败回归测试，锁定第 5 章必须只保留集群治理主线**

```python
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "testdoc" / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from report_book_dataset import build_report_book_dataset


def test_cluster_governance_dataset_exists():
    data = build_report_book_dataset()
    cluster = data["cluster_governance"]
    assert {item["plan_type"] for item in cluster["decision_matrix"]} == {
        "place",
        "wait",
        "reject",
        "hold",
        "preempt_then_place",
    }
    assert "reconcile_flow" in cluster
    assert "governance_coverage" in cluster


def test_chapter5_has_only_cluster_governance_sections():
    text = (ROOT / "testdoc" / "作品报告_网页叙事版.html").read_text(encoding="utf-8")
    assert "实验五：真实远端功耗告警治理闭环" in text
    assert "集群调度决策矩阵" in text
    assert "调和执行与状态回写" in text
    assert "治理对象覆盖与审计证据" in text
    for removed in (
        "实验一：作用域收缩与越界拦截",
        "实验二：历史查询与回放一致性",
        "实验三：Agent 数据链路有效性",
        "实验四：控制平面闭环验证",
        "Agent 有效性分析",
        "扩展能力验证状态",
    ):
        assert removed not in text
```

- [ ] **Step 2: 运行测试，确认当前实现会失败**

Run: `cmd.exe /c ".venv\Scripts\python.exe -m pytest tests\test_report_book_cluster_governance_focus.py -q"`
Expected: FAIL，原因包括 `cluster_governance` 数据不存在，以及 HTML 第 5 章仍包含旧实验标题。

- [ ] **Step 3: 新增集群治理数据整理脚本**

```python
from __future__ import annotations

from app.services.cluster_control.scheduler_core import ClusterSchedulerCore
from app.services.cluster_control.models import JobSpecRecord
from app.services.cluster_control.reconcile_controller import ClusterReconcileController


def build_cluster_governance_dataset() -> dict:
    return {
        "decision_matrix": build_decision_matrix(),
        "reconcile_flow": build_reconcile_flow(),
        "governance_coverage": build_governance_coverage(),
    }
```

```python
def build_decision_matrix() -> list[dict]:
    core = ClusterSchedulerCore()
    return [
        _plan_place(core),
        _plan_wait(core),
        _plan_reject(core),
        _plan_hold(core),
        _plan_preempt_then_place(core),
    ]
```

```python
def build_reconcile_flow() -> dict:
    return {
        "manual_run": {
            "trigger": "manual",
            "runtime_status": "connected",
            "tick_count_delta": 1,
            "summary_fields": ["placed", "preempted", "restored", "released"],
            "meaning": "一次调和会把计划推进成状态变化摘要",
        },
        "skip_run": {
            "trigger": "background",
            "runtime_status": "reconnecting",
            "skipped": True,
            "meaning": "运行时不可用时不会假装执行成功",
        },
    }
```

```python
def build_governance_coverage() -> list[dict]:
    return [
        {"object": "job", "actions": ["submit", "pause", "resume", "checkpoint", "restore"]},
        {"object": "queue", "actions": ["reconcile"]},
        {"object": "node", "actions": ["drain", "undrain"]},
        {"object": "allocation", "actions": ["release"]},
    ]
```

- [ ] **Step 4: 接入总数据集**

```python
from report_book_cluster_governance_dataset import build_cluster_governance_dataset


def build_report_book_dataset() -> dict:
    return {
        "metadata": build_metadata(),
        "panorama": build_panorama(),
        "workflow": build_workflow(),
        "workspace_map": build_workspace_map(),
        "api_domains": build_api_domains(),
        "persistence": build_persistence_assets(),
        "agent_chain": build_agent_chain(),
        "extensions": build_extensions(),
        "problem_matrix": PROBLEM_MATRIX,
        "kernel_metrics": build_kernel_metrics(),
        "test_domains": build_test_domains(),
        "testing_detail": build_testing_detail(),
        "real_remote_budget_experiment": build_real_remote_budget_experiment(),
        "cluster_governance": build_cluster_governance_dataset(),
    }
```

- [ ] **Step 5: 重跑回归测试，确认数据层可用**

Run: `cmd.exe /c ".venv\Scripts\python.exe -m pytest tests\test_report_book_cluster_governance_focus.py::test_cluster_governance_dataset_exists -q"`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add tests/test_report_book_cluster_governance_focus.py testdoc/scripts/report_book_cluster_governance_dataset.py testdoc/scripts/report_book_dataset.py
git commit -m "test: add cluster governance report data guardrails"
```

### Task 2: 用集群治理图替换旧实验图

**Files:**
- Modify: `testdoc/scripts/report_book_charts_experiments.py`
- Modify: `testdoc/scripts/generate_report_book_assets.py`

- [ ] **Step 1: 删除旧的 scope/history/agent/control_plane 图函数**

```python
from report_book_svg_base import PALETTE, card, chip, svg_frame


# 移除 scope_experiment_svg / history_experiment_svg /
# agent_experiment_svg / control_experiment_svg，
# 保留 remote_budget_experiment_svg 与 remote_budget_timeline_svg。
```

- [ ] **Step 2: 保留真实功耗治理图，并新增集群调度决策矩阵图**

```python
def cluster_decision_matrix_svg(dataset: dict) -> str:
    rows = dataset["cluster_governance"]["decision_matrix"]
    body = []
    for index, item in enumerate(rows):
        y = 154 + index * 96
        body.append(card(
            54, y, 1312, 78,
            item["plan_type"],
            [item["condition"], item["meaning"]],
            PALETTE[item["tone"]],
        ))
    return svg_frame("图 20  实验 B：集群调度决策矩阵", "展示调度器在不同治理条件下如何生成集群级决策。", 1420, 700, "".join(body))
```

```python
body.append(card(
    54, 154, 620, 126,
    "place",
    ["资源满足、队列 active、节点可调度", "结果：作业进入运行放置路径"],
    PALETTE["green"],
))
```

- [ ] **Step 3: 新增调和执行与状态回写图**

```python
def cluster_reconcile_flow_svg(dataset: dict) -> str:
    info = dataset["cluster_governance"]["reconcile_flow"]
    return svg_frame(
        "图 21  实验 C：调和执行与状态回写",
        "展示 reconcile controller 在执行和跳过两种场景下如何回写状态。",
        1420,
        560,
        "".join([
            card(54, 154, 620, 150, "manual_run", [
                f"runtime_status: {info['manual_run']['runtime_status']}",
                f"tick_count_delta: {info['manual_run']['tick_count_delta']}",
                "summary: placed / preempted / restored / released",
            ], PALETTE["green"]),
            card(706, 154, 660, 150, "skip_run", [
                f"runtime_status: {info['skip_run']['runtime_status']}",
                "skipped: True",
                info["skip_run"]["meaning"],
            ], PALETTE["amber"]),
        ]),
    )
```

- [ ] **Step 4: 新增治理对象覆盖与审计证据图**

```python
def cluster_governance_coverage_svg(dataset: dict) -> str:
    coverage = dataset["cluster_governance"]["governance_coverage"]
    body = []
    for index, item in enumerate(coverage):
        y = 154 + index * 100
        body.append(card(
            54, y, 1312, 82,
            item["object"],
            [", ".join(item["actions"]), item["meaning"]],
            PALETTE[item["tone"]],
        ))
    return svg_frame("图 22  实验 D：治理对象覆盖与审计证据", "展示第 5 章保留的集群治理对象与动作覆盖。", 1420, 620, "".join(body))
```

- [ ] **Step 5: 更新图表生成清单，只保留治理主线需要的第 5 章图**

```python
charts = {
    "book_remote_budget_experiment.svg": remote_budget_experiment_svg(data),
    "book_remote_budget_timeline.svg": remote_budget_timeline_svg(data),
    "book_cluster_decision_matrix.svg": cluster_decision_matrix_svg(data),
    "book_cluster_reconcile_flow.svg": cluster_reconcile_flow_svg(data),
    "book_cluster_governance_coverage.svg": cluster_governance_coverage_svg(data),
}
```

- [ ] **Step 6: 生成资产并检查新增图存在**

Run: `cmd.exe /c ".venv\Scripts\python.exe testdoc\scripts\generate_report_book_assets.py"`
Expected: 生成 `book_cluster_decision_matrix.svg`、`book_cluster_reconcile_flow.svg`、`book_cluster_governance_coverage.svg`，且不再依赖旧实验图。

- [ ] **Step 7: Commit**

```bash
git add testdoc/scripts/report_book_charts_experiments.py testdoc/scripts/generate_report_book_assets.py testdoc/assets/book_cluster_decision_matrix.svg testdoc/assets/book_cluster_reconcile_flow.svg testdoc/assets/book_cluster_governance_coverage.svg
git commit -m "feat: refocus report charts on cluster governance"
```

### Task 3: 重写第 5 章 HTML，只保留集群治理叙事

**Files:**
- Modify: `testdoc/作品报告_网页叙事版.html`
- Modify: `testdoc/assets/report_book.css`

- [ ] **Step 1: 先用回归测试锁定旧实验标题必须消失**

Run: `cmd.exe /c ".venv\Scripts\python.exe -m pytest tests\test_report_book_cluster_governance_focus.py::test_chapter5_has_only_cluster_governance_sections -q"`
Expected: FAIL，原因是 HTML 还保留旧实验标题。

- [ ] **Step 2: 重写第 5 章导语和结构**

```html
<p class="chapter__lead">
  本章只回答一个问题：系统的治理动作能否改变真实集群状态。
  因此所有证据只保留功耗告警治理、调度决策、调和执行和对象覆盖四个方面。
</p>
```

```html
<li>真实数据来源：10.151.225.108 单机 4×RTX 3090 的功耗闭环实测。</li>
<li>受控实验来源：ClusterSchedulerCore 与 ClusterReconcileController 的受控决策场景。</li>
```

- [ ] **Step 3: 保留实验 A 的图和数据表，删除所有旧实验块**

```html
<article class="figure">
  <h3 class="figure__title">实验 A：真实远端功耗告警治理闭环</h3>
  <img src="assets/book_remote_budget_experiment.svg" alt="真实远端功耗告警治理闭环">
</article>
```

```html
<!-- 删除以下整块 -->
<!-- 实验一：作用域收缩与越界拦截 -->
<!-- 实验二：历史查询与回放一致性 -->
<!-- 实验三：Agent 数据链路有效性 -->
<!-- 实验四：控制平面闭环验证 -->
```

- [ ] **Step 4: 插入实验 B/C/D 的图和解释**

```html
<article class="figure">
  <h3 class="figure__title">实验 B：集群调度决策矩阵</h3>
  <img src="assets/book_cluster_decision_matrix.svg" alt="集群调度决策矩阵">
  <p class="caption">这张图回答“调度器在不同治理条件下会给出什么决策”。</p>
</article>
```

```html
<article class="figure">
  <h3 class="figure__title">实验 C：调和执行与状态回写</h3>
  <img src="assets/book_cluster_reconcile_flow.svg" alt="调和执行与状态回写">
  <p class="caption">这张图回答“系统是否会把计划推进成实际状态变化并写回 summary”。</p>
</article>
```

```html
<article class="figure">
  <h3 class="figure__title">实验 D：治理对象覆盖与审计证据</h3>
  <img src="assets/book_cluster_governance_coverage.svg" alt="治理对象覆盖与审计证据">
  <p class="caption">这张图回答“平台到底能治理哪些集群对象”。</p>
</article>
```

- [ ] **Step 5: 为长表格增加横向滚动支持**

```css
.table-wrap {
  overflow-x: auto;
}
```

- [ ] **Step 6: 重跑 HTML 回归测试**

Run: `cmd.exe /c ".venv\Scripts\python.exe -m pytest tests\test_report_book_cluster_governance_focus.py::test_chapter5_has_only_cluster_governance_sections -q"`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add testdoc/作品报告_网页叙事版.html testdoc/assets/report_book.css
git commit -m "feat: rewrite chapter five around cluster governance"
```

### Task 4: 生成最终资产并做收尾验证

**Files:**
- Modify: `testdoc/data/report_book_metrics.json`
- Verify: `testdoc/assets/*.svg`

- [ ] **Step 1: 重新生成作品书所有数据与图**

Run: `cmd.exe /c ".venv\Scripts\python.exe testdoc\scripts\generate_report_book_assets.py"`
Expected: `report_book_metrics.json` 更新，且新 cluster governance 图全部落盘。

- [ ] **Step 2: 检查 HTML 只引用新的治理图**

Run: `rg -n "book_scope_experiment|book_history_experiment|book_agent_experiment|book_control_experiment" testdoc/作品报告_网页叙事版.html`
Expected: 无输出

Run: `rg -n "book_remote_budget_experiment|book_remote_budget_timeline|book_cluster_decision_matrix|book_cluster_reconcile_flow|book_cluster_governance_coverage" testdoc/作品报告_网页叙事版.html`
Expected: 命中 5 条引用

- [ ] **Step 3: 运行完整回归检查**

Run: `cmd.exe /c ".venv\Scripts\python.exe -m pytest tests\test_report_book_cluster_governance_focus.py -q"`
Expected: PASS

Run: `cmd.exe /c ".venv\Scripts\python.exe -m py_compile testdoc\scripts\report_book_cluster_governance_dataset.py testdoc\scripts\report_book_dataset.py testdoc\scripts\report_book_charts_experiments.py testdoc\scripts\generate_report_book_assets.py"`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add testdoc/data/report_book_metrics.json testdoc/assets testdoc/data/real_remote_budget_summary.csv
git commit -m "chore: regenerate cluster governance report assets"
```
