from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "testdoc" / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from report_book_dataset import build_report_book_dataset


REMOVED_SECTIONS = (
    "实验一：作用域收缩与越界拦截",
    "实验二：历史查询与回放一致性",
    "实验三：Agent 数据链路有效性",
    "实验四：控制平面闭环验证",
    "Agent 有效性分析",
    "扩展能力验证状态",
)


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
    assert "manual_run" in cluster["reconcile_flow"]
    assert "skip_run" in cluster["reconcile_flow"]
    assert [item["object"] for item in cluster["governance_coverage"]] == [
        "job",
        "queue",
        "node",
        "allocation",
    ]


def test_chapter5_has_only_cluster_governance_sections():
    text = (ROOT / "testdoc" / "作品报告_网页叙事版.html").read_text(encoding="utf-8")
    assert "实验五：真实远端功耗告警治理闭环" in text
    assert "集群调度决策矩阵" in text
    assert "调和执行与状态回写" in text
    assert "治理对象覆盖与审计证据" in text
    for removed in REMOVED_SECTIONS:
        assert removed not in text
