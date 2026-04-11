from __future__ import annotations

import csv
import json
from pathlib import Path

from report_book_svg_base import PALETTE, bar, card, chip, esc, svg_frame


ROOT = Path(__file__).resolve().parents[1]
INPUT_PATH = ROOT / "data" / "real_remote_dual_gpu_competition.json"
SUMMARY_CSV_PATH = ROOT / "data" / "real_remote_dual_gpu_competition_summary.csv"
TIMELINE_PATH = ROOT / "assets" / "dual_gpu_competition_timeline.svg"
COMPARISON_PATH = ROOT / "assets" / "dual_gpu_competition_comparison.svg"
LATENCY_PATH = ROOT / "assets" / "dual_gpu_competition_latency.svg"


def load_data() -> dict:
    return json.loads(INPUT_PATH.read_text(encoding="utf-8"))


def summary_rows(data: dict) -> list[dict]:
    rows = []
    for role in ("governance", "control"):
        for phase in ("baseline", "ramp", "post_action"):
            summary = data["summary"][role][phase]
            clean_ratio = round(
                (summary["sample_count"] - summary["above_alert_samples"])
                / summary["sample_count"]
                * 100.0,
                1,
            )
            rows.append(
                {
                    "role": role,
                    "phase": phase,
                    "sample_count": summary["sample_count"],
                    "avg_power": summary["avg_power"],
                    "peak_power": summary["peak_power"],
                    "avg_temperature": summary["avg_temperature"],
                    "above_alert_samples": summary["above_alert_samples"],
                    "clean_ratio_pct": clean_ratio,
                }
            )
    return rows


def write_summary_csv(rows: list[dict]) -> None:
    SUMMARY_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    with SUMMARY_CSV_PATH.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def timeline_svg(data: dict) -> str:
    governance = _role_samples(data, "governance")
    control = _role_samples(data, "control")
    total_points = governance
    action_elapsed = data["summary"]["latency"]["governance"]["action_elapsed_s"]
    plot_x = lambda index: 74 + index * (760 / max(len(governance) - 1, 1))
    plot_y = lambda value: 468 - value / 360 * 260
    total_y = lambda value: 654 - (value - 200) / 720 * 150
    governance_line = _polyline(governance, plot_x, plot_y, "power_usage", PALETTE["blue"], 4)
    control_line = _polyline(control, plot_x, plot_y, "power_usage", PALETTE["amber"], 4)
    limit_line = _polyline(governance, plot_x, plot_y, "power_limit", PALETTE["green"], 3)
    total_line = _polyline(total_points, plot_x, total_y, "total_power", PALETTE["slate"], 3)
    action_index = _action_index(governance, action_elapsed)
    marker_x = plot_x(action_index)
    body = [
        '<rect class="card" x="42" y="126" width="828" height="368" rx="24"/>',
        '<rect class="card" x="42" y="520" width="828" height="178" rx="24"/>',
        '<rect class="card" x="900" y="126" width="478" height="572" rx="24"/>',
        f'<rect x="74" y="180" width="{plot_x(3) - 74:.1f}" height="288" fill="#E8F1FF"/>',
        f'<rect x="{plot_x(3):.1f}" y="180" width="{plot_x(9) - plot_x(3):.1f}" height="288" fill="#FFF4E5"/>',
        f'<rect x="{plot_x(9):.1f}" y="180" width="{834 - plot_x(9):.1f}" height="288" fill="#ECFDF5"/>',
        f'<line x1="74" y1="{plot_y(320):.1f}" x2="834" y2="{plot_y(320):.1f}" stroke="{PALETTE["red"]}" stroke-width="2.5" stroke-dasharray="8 8"/>',
        governance_line,
        control_line,
        limit_line,
        f'<line x1="{marker_x:.1f}" y1="180" x2="{marker_x:.1f}" y2="468" stroke="{PALETTE["cyan"]}" stroke-width="3" stroke-dasharray="10 8"/>',
        '<text class="h" x="74" y="166">治理卡 vs 对照卡功耗时间线</text>',
        f'<text class="s" x="74" y="{plot_y(320) - 8:.1f}">告警阈值 320W</text>',
        total_line,
        f'<line x1="{marker_x:.1f}" y1="548" x2="{marker_x:.1f}" y2="654" stroke="{PALETTE["cyan"]}" stroke-width="3" stroke-dasharray="10 8"/>',
        '<text class="h" x="74" y="540">整机总功率变化</text>',
        '<text class="s" x="920" y="176">怎么读这张图</text>',
        '<text class="p" x="920" y="208">1. 蓝线是治理 GPU1 的实测功耗，橙线是对照 GPU3 的实测功耗。</text>',
        '<text class="p" x="920" y="236">2. 绿线是治理卡的功耗上限，青虚线是治理动作生效时刻。</text>',
        '<text class="p" x="920" y="264">3. 动作后蓝线从 348W 峰值回落到约 268W，而橙线继续维持 328W 高位。</text>',
        '<text class="p" x="920" y="292">4. 下方灰线是整机总功率，治理后出现同步回落。</text>',
        f'<text class="p" x="920" y="334">治理卡后窗均值：{data["summary"]["governance"]["post_action"]["avg_power"]:.2f}W</text>',
        f'<text class="p" x="920" y="362">对照卡后窗均值：{data["summary"]["control"]["post_action"]["avg_power"]:.2f}W</text>',
        f'<text class="p" x="920" y="390">功耗均值差：{data["summary"]["contrast"]["post_avg_power_gap_w"]:.2f}W</text>',
        f'<text class="p" x="920" y="418">整机总功率回落：{data["summary"]["contrast"]["total_power_drop_after_action_w"]:.2f}W</text>',
        f'<text class="p" x="920" y="446">治理动作：GPU{data["governance_gpu_index"]} -> {data["scheduler_run"]["selected_action"]["target"]["power_limit"]}W</text>',
        f'<text class="p" x="920" y="474">预算阈值：{data["scheduler_run"]["budget_limit"]}W</text>',
        chip(920, 604, 150, "治理卡峰值", f'{data["summary"]["governance"]["ramp"]["peak_power"]:.1f}W', PALETTE["blue"]),
        chip(1090, 604, 150, "对照卡峰值", f'{data["summary"]["control"]["ramp"]["peak_power"]:.1f}W', PALETTE["amber"]),
        chip(1260, 604, 108, "有效", str(data["summary"]["effective"]), PALETTE["green"]),
    ]
    return svg_frame("双 GPU 并发竞争治理时间线", "同机双卡同时拉高负载，只对治理卡执行系统治理动作，观察两条曲线如何分离。", 1420, 740, "".join(body))


def comparison_svg(data: dict) -> str:
    governance = data["summary"]["governance"]
    control = data["summary"]["control"]
    body = [
        '<rect class="card" x="42" y="126" width="1336" height="458" rx="24"/>',
        '<text class="h" x="68" y="164">功耗、温度与清洁率对比</text>',
        bar(96, 470, 110, 220, int(round(governance["ramp"]["peak_power"])), 360, PALETTE["blue"], "治理峰值"),
        bar(230, 470, 110, 220, int(round(control["ramp"]["peak_power"])), 360, PALETTE["amber"], "对照峰值"),
        bar(406, 470, 110, 220, int(round(governance["post_action"]["avg_power"])), 360, PALETTE["blue"], "治理后均值"),
        bar(540, 470, 110, 220, int(round(control["post_action"]["avg_power"])), 360, PALETTE["amber"], "对照后均值"),
        bar(716, 470, 110, 220, int(round(governance["post_action"]["avg_temperature"])), 120, PALETTE["blue"], "治理后温度"),
        bar(850, 470, 110, 220, int(round(control["post_action"]["avg_temperature"])), 120, PALETTE["amber"], "对照后温度"),
        bar(1026, 470, 110, 220, int(round(data["summary"]["contrast"]["governance_clean_ratio_pct"])), 100, PALETTE["green"], "治理清洁率"),
        bar(1160, 470, 110, 220, int(round(data["summary"]["contrast"]["control_clean_ratio_pct"])), 100, PALETTE["red"], "对照清洁率"),
        card(54, 610, 408, 120, "治理卡", [
            f'峰值 {governance["ramp"]["peak_power"]:.2f}W -> 后窗均值 {governance["post_action"]["avg_power"]:.2f}W',
            f'后窗越阈样本 {governance["post_action"]["above_alert_samples"]} / {governance["post_action"]["sample_count"]}',
        ], PALETTE["blue"]),
        card(506, 610, 408, 120, "对照卡", [
            f'峰值 {control["ramp"]["peak_power"]:.2f}W -> 后窗均值 {control["post_action"]["avg_power"]:.2f}W',
            f'后窗越阈样本 {control["post_action"]["above_alert_samples"]} / {control["post_action"]["sample_count"]}',
        ], PALETTE["amber"]),
        card(958, 610, 408, 120, "核心差异", [
            f'后窗功耗差 {data["summary"]["contrast"]["post_avg_power_gap_w"]:.2f}W',
            f'治理卡清洁率 100%，对照卡清洁率 0%',
        ], PALETTE["green"]),
    ]
    return svg_frame("治理卡与对照卡效果对比", "把双卡实验压缩成评审最关心的 4 组指标：峰值、治理后均值、温度、后窗清洁率。", 1420, 760, "".join(body))


def latency_svg(data: dict) -> str:
    governance = data["summary"]["latency"]["governance"]
    control = data["summary"]["latency"]["control"]
    body = [
        card(54, 154, 274, 148, "首次越阈", [
            f'治理卡 {governance["first_alert_elapsed_s"]:.2f}s',
            f'对照卡 {control["first_alert_elapsed_s"]:.2f}s',
        ], PALETTE["red"]),
        card(366, 154, 274, 148, "治理动作", [
            f'动作开始 {governance["action_elapsed_s"]:.2f}s',
            f'预算 {data["scheduler_run"]["budget_limit"]}W',
        ], PALETTE["cyan"]),
        card(678, 154, 274, 148, "首次回落", [
            f'治理卡 {governance["first_safe_elapsed_s"]:.2f}s',
            '对照卡 未回落',
        ], PALETTE["green"]),
        card(990, 154, 376, 148, "恢复延迟", [
            f'治理卡 recovery_latency = {governance["recovery_latency_s"]:.2f}s',
            '对照卡在观测窗口内始终高于阈值',
        ], PALETTE["blue"]),
        '<rect class="card" x="42" y="344" width="1336" height="250" rx="24"/>',
        '<text class="h" x="68" y="382">治理事件链</text>',
        '<line x1="108" y1="472" x2="1308" y2="472" stroke="#D7E1EC" stroke-width="8" stroke-linecap="round"/>',
        _event_marker(160, "22.09s", "双卡同时越阈", PALETTE["red"]),
        _event_marker(536, "23.18s", "系统对 GPU1 下发限功率", PALETTE["cyan"]),
        _event_marker(912, "23.18s", "治理卡首次回到阈值下方", PALETTE["green"]),
        _event_marker(1248, "后窗结束", "对照卡仍 18/18 越阈", PALETTE["amber"]),
        chip(54, 624, 250, "治理卡清洁率", f'{data["summary"]["contrast"]["governance_clean_ratio_pct"]:.1f}%', PALETTE["green"]),
        chip(328, 624, 250, "对照卡清洁率", f'{data["summary"]["contrast"]["control_clean_ratio_pct"]:.1f}%', PALETTE["red"]),
        chip(602, 624, 346, "治理卡功耗回落", f'{data["summary"]["contrast"]["governance_drop_from_peak_w"]:.2f}W', PALETTE["blue"]),
        chip(972, 624, 394, "对照卡未治理表现", f'后窗均值 {data["summary"]["control"]["post_action"]["avg_power"]:.2f}W', PALETTE["amber"]),
    ]
    return svg_frame("治理时延与清洁率", "把实验拆成事件链，直接展示从双卡越阈到治理卡回落、对照卡持续越阈的时间顺序。", 1420, 720, "".join(body))


def _role_samples(data: dict, role: str) -> list[dict]:
    rows = [
        item for item in data["samples"]
        if str(item.get("gpu_role") or "") == role
    ]
    return sorted(rows, key=lambda item: float(item.get("elapsed_s", 0) or 0))


def _action_index(rows: list[dict], action_elapsed: float | None) -> int:
    if action_elapsed is None:
        return max(len(rows) - 1, 0)
    for index, item in enumerate(rows):
        if float(item.get("elapsed_s", 0) or 0) >= action_elapsed:
            return index
    return max(len(rows) - 1, 0)


def _polyline(samples: list[dict], x_fn, y_fn, key: str, color: str, width: int) -> str:
    points = " ".join(
        f"{x_fn(index):.1f},{y_fn(float(sample[key])):.1f}"
        for index, sample in enumerate(samples)
    )
    return (
        f'<polyline points="{esc(points)}" fill="none" stroke="{color}" '
        f'stroke-width="{width}" stroke-linejoin="round" stroke-linecap="round"/>'
    )


def _event_marker(x: int, label: str, text: str, color: str) -> str:
    return (
        f'<circle cx="{x}" cy="472" r="14" fill="{color}"/>'
        f'<text class="k" x="{x - 20}" y="438">{esc(label)}</text>'
        f'<text class="p" x="{x - 72}" y="518">{esc(text)}</text>'
    )


def main() -> None:
    data = load_data()
    rows = summary_rows(data)
    write_summary_csv(rows)
    TIMELINE_PATH.write_text(timeline_svg(data), encoding="utf-8")
    COMPARISON_PATH.write_text(comparison_svg(data), encoding="utf-8")
    LATENCY_PATH.write_text(latency_svg(data), encoding="utf-8")
    print(
        json.dumps(
            {
                "summary_csv": str(SUMMARY_CSV_PATH),
                "timeline_svg": str(TIMELINE_PATH),
                "comparison_svg": str(COMPARISON_PATH),
                "latency_svg": str(LATENCY_PATH),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
