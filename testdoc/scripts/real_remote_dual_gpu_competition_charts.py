from __future__ import annotations

import csv
import json
from pathlib import Path

from report_book_plot_utils import (
    PlotArea,
    nice_ticks,
    pad_domain,
    render_grouped_bars,
    render_horizontal_marker,
    render_legend,
    render_line_series,
    render_phase_band,
    render_plot_shell,
    render_vertical_marker,
    scale_x,
    scale_y,
)
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
    power_plot = PlotArea(74, 176, 760, 280)
    total_plot = PlotArea(74, 520, 760, 122)
    elapsed_values = [item["elapsed_s"] for item in governance]
    x_domain = (min(elapsed_values), max(elapsed_values))
    x_ticks = nice_ticks(x_domain[0], x_domain[1], 6)
    power_values = [item["power_usage"] for item in governance + control] + [item["power_limit"] for item in governance] + [320]
    power_domain = pad_domain(min(power_values), max(power_values), 0.08)
    power_ticks = nice_ticks(power_domain[0], power_domain[1], 6)
    total_values = [item["total_power"] for item in total_points]
    total_domain = pad_domain(min(total_values), max(total_values), 0.08)
    total_ticks = nice_ticks(total_domain[0], total_domain[1], 4)
    governance_points = [(item["elapsed_s"], item["power_usage"]) for item in governance]
    control_points = [(item["elapsed_s"], item["power_usage"]) for item in control]
    limit_points = [(item["elapsed_s"], item["power_limit"]) for item in governance]
    total_series = [(item["elapsed_s"], item["total_power"]) for item in total_points]
    body = [
        '<rect class="card" x="42" y="126" width="828" height="368" rx="24"/>',
        '<rect class="card" x="42" y="520" width="828" height="178" rx="24"/>',
        '<rect class="card" x="900" y="126" width="478" height="572" rx="24"/>',
        _phase_sections(governance, power_plot, x_domain),
        render_plot_shell(
            power_plot,
            x_ticks=x_ticks,
            y_ticks=power_ticks,
            x_domain=x_domain,
            y_domain=power_domain,
            x_label="Elapsed Time (s)",
            y_label="Power (W)",
            x_formatter=lambda value: f"{value:.0f}",
            y_formatter=lambda value: f"{value:.0f}",
        ),
        render_line_series(governance_points, x_domain=x_domain, y_domain=power_domain, area=power_plot, color=PALETTE["blue"]),
        render_line_series(control_points, x_domain=x_domain, y_domain=power_domain, area=power_plot, color=PALETTE["amber"]),
        render_line_series(limit_points, x_domain=x_domain, y_domain=power_domain, area=power_plot, color=PALETTE["green"], width=2.8),
        render_horizontal_marker(
            power_plot,
            value=320,
            y_domain=power_domain,
            color=PALETTE["red"],
            label="阈值 320W",
        ),
        render_vertical_marker(
            power_plot,
            value=action_elapsed,
            x_domain=x_domain,
            color=PALETTE["cyan"],
            label="治理动作",
        ),
        render_legend(
            84,
            148,
            [
                ("治理卡功耗", PALETTE["blue"]),
                ("对照卡功耗", PALETTE["amber"]),
                ("治理卡上限", PALETTE["green"]),
                ("阈值线", PALETTE["red"]),
            ],
        ),
        '<text class="h" x="74" y="164">治理卡 vs 对照卡功耗时间线</text>',
        render_plot_shell(
            total_plot,
            x_ticks=x_ticks,
            y_ticks=total_ticks,
            x_domain=x_domain,
            y_domain=total_domain,
            x_label="Elapsed Time (s)",
            y_label="Total Power (W)",
            x_formatter=lambda value: f"{value:.0f}",
            y_formatter=lambda value: f"{value:.0f}",
        ),
        render_line_series(total_series, x_domain=x_domain, y_domain=total_domain, area=total_plot, color=PALETTE["slate"], width=3.0),
        render_vertical_marker(
            total_plot,
            value=action_elapsed,
            x_domain=x_domain,
            color=PALETTE["cyan"],
            label="动作",
        ),
        '<text class="h" x="74" y="510">整机总功率变化</text>',
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
    power_plot = PlotArea(74, 170, 390, 240)
    temp_plot = PlotArea(514, 170, 320, 240)
    ratio_plot = PlotArea(884, 170, 430, 240)
    power_categories = ["峰值功耗", "治理后均值"]
    power_series = [
        ("治理卡", PALETTE["blue"], [governance["ramp"]["peak_power"], governance["post_action"]["avg_power"]]),
        ("对照卡", PALETTE["amber"], [control["ramp"]["peak_power"], control["post_action"]["avg_power"]]),
    ]
    power_domain = pad_domain(0, max(governance["ramp"]["peak_power"], control["ramp"]["peak_power"]), 0.08)
    power_ticks = nice_ticks(power_domain[0], power_domain[1], 5)
    temp_categories = ["治理后温度"]
    temp_series = [
        ("治理卡", PALETTE["blue"], [governance["post_action"]["avg_temperature"]]),
        ("对照卡", PALETTE["amber"], [control["post_action"]["avg_temperature"]]),
    ]
    temp_domain = pad_domain(0, max(governance["post_action"]["avg_temperature"], control["post_action"]["avg_temperature"]), 0.1)
    temp_ticks = nice_ticks(temp_domain[0], temp_domain[1], 5)
    gov_alert_ratio = governance["post_action"]["above_alert_samples"] / governance["post_action"]["sample_count"] * 100.0
    ctl_alert_ratio = control["post_action"]["above_alert_samples"] / control["post_action"]["sample_count"] * 100.0
    ratio_categories = ["清洁率", "告警样本率"]
    ratio_series = [
        ("治理卡", PALETTE["blue"], [data["summary"]["contrast"]["governance_clean_ratio_pct"], gov_alert_ratio]),
        ("对照卡", PALETTE["amber"], [data["summary"]["contrast"]["control_clean_ratio_pct"], ctl_alert_ratio]),
    ]
    body = [
        '<rect class="card" x="42" y="126" width="1336" height="458" rx="24"/>',
        render_grouped_bars(
            power_plot,
            categories=power_categories,
            series=power_series,
            y_domain=power_domain,
            y_ticks=power_ticks,
            x_label="功耗指标",
            y_label="Power (W)",
            formatter=lambda value: f"{value:.0f}",
        ),
        render_grouped_bars(
            temp_plot,
            categories=temp_categories,
            series=temp_series,
            y_domain=temp_domain,
            y_ticks=temp_ticks,
            x_label="温度指标",
            y_label="Temperature (°C)",
            formatter=lambda value: f"{value:.0f}",
        ),
        render_grouped_bars(
            ratio_plot,
            categories=ratio_categories,
            series=ratio_series,
            y_domain=(0, 100),
            y_ticks=[0, 25, 50, 75, 100],
            x_label="治理结果",
            y_label="Ratio (%)",
            formatter=lambda value: f"{value:.0f}%",
        ),
        render_legend(
            86,
            146,
            [
                ("治理卡", PALETTE["blue"]),
                ("对照卡", PALETTE["amber"]),
            ],
        ),
        '<text class="h" x="68" y="160">功耗、温度与清洁率对比</text>',
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
    end_elapsed = max(item["elapsed_s"] for item in data["samples"])
    timeline_plot = PlotArea(94, 372, 1232, 180)
    x_domain = (0.0, end_elapsed)
    x_ticks = nice_ticks(0.0, end_elapsed, 6)
    y_domain = (-0.4, 1.4)
    gov_y = 1.0
    ctl_y = 0.0
    gov_alert_x = float(governance["first_alert_elapsed_s"] or 0)
    ctl_alert_x = float(control["first_alert_elapsed_s"] or 0)
    action_x = float(governance["action_elapsed_s"] or 0)
    safe_x = float(governance["first_safe_elapsed_s"] or 0)
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
        render_plot_shell(
            timeline_plot,
            x_ticks=x_ticks,
            y_ticks=[0, 1],
            x_domain=x_domain,
            y_domain=y_domain,
            x_label="Elapsed Time (s)",
            y_label="对象",
            x_formatter=lambda value: f"{value:.0f}",
            y_formatter=lambda value: "治理卡" if value >= 0.5 else "对照卡",
        ),
        f'<text class="h" x="68" y="382">治理事件链</text>',
        _event_line(timeline_plot, x_domain, y_domain, gov_alert_x, safe_x, gov_y, PALETTE["blue"]),
        _event_line(timeline_plot, x_domain, y_domain, ctl_alert_x, end_elapsed, ctl_y, PALETTE["amber"]),
        render_vertical_marker(
            timeline_plot,
            value=action_x,
            x_domain=x_domain,
            color=PALETTE["cyan"],
            label="治理动作",
        ),
        _event_point(timeline_plot, x_domain, y_domain, gov_alert_x, gov_y, PALETTE["red"], "首次越阈"),
        _event_point(timeline_plot, x_domain, y_domain, safe_x, gov_y, PALETTE["green"], "首次回落"),
        _event_point(timeline_plot, x_domain, y_domain, ctl_alert_x, ctl_y, PALETTE["red"], "首次越阈"),
        _event_point(timeline_plot, x_domain, y_domain, end_elapsed, ctl_y, PALETTE["amber"], "窗口结束"),
        render_legend(
            96,
            356,
            [
                ("治理卡事件链", PALETTE["blue"]),
                ("对照卡事件链", PALETTE["amber"]),
                ("动作时刻", PALETTE["cyan"]),
            ],
        ),
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


def _phase_sections(rows: list[dict], area: PlotArea, x_domain: tuple[float, float]) -> str:
    fill_by_phase = {
        "baseline": ("基线", "#E8F1FF"),
        "load_ramp": ("爬升", "#FFF4E5"),
        "post_action": ("治理后", "#ECFDF5"),
    }
    bands = []
    for phase in ("baseline", "load_ramp", "post_action"):
        phase_rows = [item for item in rows if item["phase"] == phase]
        if not phase_rows:
            continue
        label, fill = fill_by_phase[phase]
        bands.append(
            render_phase_band(
                area,
                start=phase_rows[0]["elapsed_s"],
                end=phase_rows[-1]["elapsed_s"],
                x_domain=x_domain,
                fill=fill,
                label=label,
            )
        )
    return "".join(bands)


def _event_line(
    area: PlotArea,
    x_domain: tuple[float, float],
    y_domain: tuple[float, float],
    start: float,
    end: float,
    y_value: float,
    color: str,
) -> str:
    x1 = scale_x(start, x_domain, area)
    x2 = scale_x(end, x_domain, area)
    y = scale_y(y_value, y_domain, area)
    return f'<line x1="{x1:.1f}" y1="{y:.1f}" x2="{x2:.1f}" y2="{y:.1f}" stroke="{color}" stroke-width="4" stroke-linecap="round"/>'


def _event_point(
    area: PlotArea,
    x_domain: tuple[float, float],
    y_domain: tuple[float, float],
    x_value: float,
    y_value: float,
    color: str,
    label: str,
) -> str:
    x = scale_x(x_value, x_domain, area)
    y = scale_y(y_value, y_domain, area)
    return (
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="7" fill="{color}" stroke="#FFFFFF" stroke-width="1.4"/>'
        f'<text class="s" x="{x + 8:.1f}" y="{y - 10:.1f}">{esc(label)}</text>'
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
