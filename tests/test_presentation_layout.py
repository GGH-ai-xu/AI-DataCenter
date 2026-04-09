import unittest
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = (
    Path(__file__).resolve().parents[1]
    / "docs/presentations/ai_datacenter_showcase_ppt169_20260406/svg_output"
)
SVG_NS = "{http://www.w3.org/2000/svg}"


def estimate_text_width(text: str, size: float) -> float:
    width = 0.0
    for ch in text:
        code = ord(ch)
        if ch == " ":
            width += size * 0.32
        elif ch in "/|:.-_+()[]":
            width += size * 0.38
        elif 0x4E00 <= code <= 0x9FFF:
            width += size * 0.95
        elif ch.isupper():
            width += size * 0.68
        else:
            width += size * 0.56
    return width


def iter_text_nodes(path: Path):
    tree = ET.parse(path)
    for node in tree.getroot().iter():
        if node.tag != f"{SVG_NS}text":
            continue
        size = float(node.attrib.get("font-size", 16))
        tspans = [child for child in node if child.tag == f"{SVG_NS}tspan"]
        if tspans:
            lines = ["".join(child.itertext()).strip() for child in tspans]
        else:
            lines = ["".join(node.itertext()).strip()]
        yield {
            "text": " / ".join(lines),
            "lines": lines,
            "size": size,
        }


def find_text_node(path: Path, fragment: str):
    for item in iter_text_nodes(path):
        if fragment in item["text"]:
            return item
    raise AssertionError(f"Text fragment not found in {path.name}: {fragment}")


class PresentationLayoutTest(unittest.TestCase):
    def assert_line_width(self, slide_name: str, fragment: str, max_width: float):
        node = find_text_node(ROOT / slide_name, fragment)
        widest = max(estimate_text_width(line, node["size"]) for line in node["lines"])
        self.assertLessEqual(
            widest,
            max_width,
            f"{slide_name} text overflow risk: {fragment} widest={widest:.1f} max={max_width}",
        )

    def test_cover_and_scope_summary_texts_fit_cards(self):
        self.assert_line_width("slide_01_cover.svg", "把“资源可见”升级为", 520)
        self.assert_line_width("slide_01_cover.svg", "本机 Agent", 168)
        self.assert_line_width("slide_01_cover.svg", "已保存主机、连接来源", 168)
        self.assert_line_width("slide_01_cover.svg", "控制台只治理本次导入选中的卡", 168)

    def test_pain_point_cards_wrap_descriptions(self):
        self.assert_line_width("slide_04_pain_points.svg", "看监控、连主机、管任务", 170)
        self.assert_line_width("slide_04_pain_points.svg", "控制台容易混入", 170)
        self.assert_line_width("slide_04_pain_points.svg", "凭据复用、用户隔离", 170)
        self.assert_line_width("slide_04_pain_points.svg", "告警、任务和调度", 170)

    def test_login_scan_and_saved_host_side_notes_fit(self):
        self.assert_line_width("slide_08_login.svg", "因为“已保存主机”", 406)
        self.assert_line_width("slide_11_scan_select.svg", "先确认 CPU / GPU 当前状态", 150)
        self.assert_line_width("slide_11_scan_select.svg", "控制台后续只显示和治理这里选中的卡", 170)
        self.assert_line_width("slide_13_saved_hosts.svg", "SSH Linux", 72)

    def test_desktop_and_architecture_labels_are_not_cramped(self):
        self.assert_line_width("slide_17_desktop_delivery.svg", "可用统一入口启动前后端与 Agent", 170)
        self.assert_line_width("slide_18_architecture.svg", "Electron Desktop Shell", 110)
        self.assert_line_width("slide_18_architecture.svg", "Runtime Provider Manager", 118)
        self.assert_line_width("slide_18_architecture.svg", "SQLite / Runtime State", 118)

    def test_runtime_security_and_roadmap_annotations_fit(self):
        self.assert_line_width("slide_19_runtime_scope.svg", "提交 import context", 138)
        self.assert_line_width("slide_20_dual_provider.svg", "两种模式在前端都被抽象成同一套导入语义", 430)
        self.assert_line_width("slide_21_auth_boundary.svg", "平台登录负责“谁在使用平台”", 430)
        self.assert_line_width("slide_23_engineering.svg", "重新拉起 agent/backend/frontend", 162)
        self.assert_line_width("slide_25_roadmap.svg", "完成登录、导入层、SSH Linux 接入与控制台治理闭环", 250)
        self.assert_line_width("slide_25_roadmap.svg", "引入智能调度、策略推荐和组织级运营能力", 230)


if __name__ == "__main__":
    unittest.main()
