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
)
from report_book_svg_base import PALETTE, chip, esc, svg_frame


ROOT = Path(__file__).resolve().parents[1]
INPUT_PATH = ROOT / "data" / "real_remote_checkpoint_restore_experiment.json"
SUMMARY_CSV_PATH = ROOT / "data" / "real_remote_checkpoint_restore_summary.csv"
TIMELINE_PATH = ROOT / "assets" / "checkpoint_restore_timeline.svg"
PROGRESS_PATH = ROOT / "assets" / "checkpoint_restore_progress.svg"
COMPARISON_PATH = ROOT / "assets" / "checkpoint_restore_comparison.svg"


def load_data() -> dict:
    return json.loads(INPUT_PATH.read_text(encoding="utf-8"))


def write_summary_csv(data: dict) -> None:
    SUMMARY_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    with SUMMARY_CSV_PATH.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(data["summary"].keys()))
        writer.writeheader()
        writer.writerow(data["summary"])


def timeline_svg(data: dict) -> str:
    rows = data["samples"]
    power_plot = PlotArea(74, 176, 760, 280)
    process_plot = PlotArea(74, 520, 760, 122)
    elapsed_values = [item["elapsed_s"] for item in rows]
    x_domain = (0.0, max(elapsed_values))
    x_ticks = nice_ticks(x_domain[0], x_domain[1], 6)
    power_values = [item["source_power_w"] for item in rows] + [item["target_power_w"] for item in rows]
    power_domain = pad_domain(min(power_values), max(power_values), 0.08)
    power_ticks = nice_ticks(power_domain[0], power_domain[1], 6)
    process_domain = (-0.05, 1.05)
    source_power = [(item["elapsed_s"], item["source_power_w"]) for item in rows]
    target_power = [(item["elapsed_s"], item["target_power_w"]) for item in rows]
    source_process = [(item["elapsed_s"], item["source_process_count"]) for item in rows]
    target_process = [(item["elapsed_s"], item["target_process_count"]) for item in rows]
    pause_elapsed = _phase_first_elapsed(rows, "paused_window")
    checkpoint_elapsed = float(data["checkpoint"]["ready_elapsed_s"])
    restore_elapsed = float(data["restore_started_at"])
    body = [
        '<rect class="card" x="42" y="126" width="828" height="368" rx="24"/>',
        '<rect class="card" x="42" y="520" width="828" height="178" rx="24"/>',
        '<rect class="card" x="900" y="126" width="478" height="572" rx="24"/>',
        _phase_sections(rows, power_plot, x_domain),
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
        render_line_series(source_power, x_domain=x_domain, y_domain=power_domain, area=power_plot, color=PALETTE["blue"]),
        render_line_series(target_power, x_domain=x_domain, y_domain=power_domain, area=power_plot, color=PALETTE["amber"]),
        render_vertical_marker(power_plot, value=pause_elapsed, x_domain=x_domain, color=PALETTE["red"], label="暂停窗口"),
        render_vertical_marker(power_plot, value=checkpoint_elapsed, x_domain=x_domain, color=PALETTE["cyan"], label="检查点就绪"),
        render_vertical_marker(power_plot, value=restore_elapsed, x_domain=x_domain, color=PALETTE["green"], label="目标卡恢复"),
        render_legend(
            84,
            148,
            [
                ("源卡功耗", PALETTE["blue"]),
                ("目标卡功耗", PALETTE["amber"]),
                ("暂停时刻", PALETTE["red"]),
                ("恢复时刻", PALETTE["green"]),
            ],
        ),
        '<text class="h" x="74" y="164">源卡/目标卡功耗切换时间线</text>',
        _phase_sections(rows, process_plot, x_domain),
        render_plot_shell(
            process_plot,
            x_ticks=x_ticks,
            y_ticks=[0, 1],
            x_domain=x_domain,
            y_domain=process_domain,
            x_label="Elapsed Time (s)",
            y_label="Process Count",
            x_formatter=lambda value: f"{value:.0f}",
            y_formatter=lambda value: f"{int(round(value))}",
        ),
        render_line_series(source_process, x_domain=x_domain, y_domain=process_domain, area=process_plot, color=PALETTE["blue"], width=2.8),
        render_line_series(target_process, x_domain=x_domain, y_domain=process_domain, area=process_plot, color=PALETTE["amber"], width=2.8),
        '<text class="h" x="74" y="510">进程归属变化</text>',
        '<text class="s" x="920" y="176">怎么读这张图</text>',
        '<text class="p" x="920" y="208">1. 上图横轴为采样时间，纵轴为两张 GPU 的功耗。</text>',
        '<text class="p" x="920" y="236">2. 下图横轴同样为采样时间，纵轴为源卡/目标卡上的任务进程数。</text>',
        '<text class="p" x="920" y="264">3. 暂停窗口内源卡功耗下降且进程数仍为 1，证明任务被冻结而非直接退出。</text>',
        '<text class="p" x="920" y="292">4. 恢复启动后目标卡功耗升高、进程数变为 1，而源卡进程数降为 0。</text>',
        f'<text class="p" x="920" y="334">暂停窗口源卡均值：{data["summary"]["source_paused_avg_power_w"]:.2f}W</text>',
        f'<text class="p" x="920" y="362">恢复窗口目标卡均值：{data["summary"]["target_restored_avg_power_w"]:.2f}W</text>',
        f'<text class="p" x="920" y="390">检查点 ready：{data["checkpoint"]["ready_elapsed_s"]:.2f}s</text>',
        f'<text class="p" x="920" y="418">目标卡恢复启动：{data["restore_started_at"]:.2f}s</text>',
        f'<text class="p" x="920" y="446">切换时延：{data["summary"]["switch_latency_s"]:.2f}s</text>',
        f'<text class="p" x="920" y="474">任务路径：GPU{data["source_gpu_index"]} -> GPU{data["target_gpu_index"]}</text>',
        chip(920, 604, 150, "源卡", f'GPU{data["source_gpu_index"]}', PALETTE["blue"]),
        chip(1090, 604, 170, "目标卡", f'GPU{data["target_gpu_index"]}', PALETTE["amber"]),
        chip(1280, 604, 88, "接续", str(data["summary"]["progress_continued"]), PALETTE["green"]),
    ]
    return svg_frame("实验 F：跨 GPU 检查点恢复时间线", "同一任务先在源卡运行，再被暂停、写出检查点，并在目标卡继续执行。", 1420, 740, "".join(body))


def progress_svg(data: dict) -> str:
    summary = data["summary"]
    step_plot = PlotArea(74, 176, 760, 250)
    delta_plot = PlotArea(884, 176, 430, 250)
    landmarks = [
        ("暂停前", _state_step(data, "pause_state_before")),
        ("暂停后", _state_step(data, "pause_state_after")),
        ("检查点", int(summary["checkpoint_step"])),
        ("恢复起点", int(summary["restored_initial_step"])),
        ("恢复终点", int(summary["restored_final_step"])),
    ]
    step_values = [value for _, value in landmarks]
    x_ticks = list(range(len(landmarks)))
    x_domain = (-0.2, len(landmarks) - 0.8)
    y_domain = (0, max(step_values) + 4)
    y_ticks = nice_ticks(y_domain[0], y_domain[1], 6)
    step_points = [(index, value) for index, (_, value) in enumerate(landmarks)]
    delta_values = [int(summary["pause_freeze_delta_steps"]), int(summary["resume_recovery_delta_steps"])]
    body = [
        '<rect class="card" x="42" y="126" width="1336" height="512" rx="24"/>',
        render_plot_shell(
            step_plot,
            x_ticks=x_ticks,
            y_ticks=y_ticks,
            x_domain=x_domain,
            y_domain=y_domain,
            x_label="关键事件",
            y_label="Step",
            x_formatter=lambda value: landmarks[int(value)][0] if int(value) < len(landmarks) else "",
            y_formatter=lambda value: f"{value:.0f}",
        ),
        render_line_series(step_points, x_domain=x_domain, y_domain=y_domain, area=step_plot, color=PALETTE["blue"]),
        render_horizontal_marker(
            step_plot,
            value=summary["checkpoint_step"],
            y_domain=y_domain,
            color=PALETTE["cyan"],
            label=f'checkpoint = {summary["checkpoint_step"]}',
        ),
        render_vertical_marker(step_plot, value=2, x_domain=x_domain, color=PALETTE["cyan"], label="写出检查点"),
        _point_labels(step_plot, x_domain, y_domain, step_points),
        '<text class="h" x="74" y="164">关键事件上的进度步数</text>',
        render_grouped_bars(
            delta_plot,
            categories=["暂停冻结增量", "恢复后新增"],
            series=[("步数增量", PALETTE["green"], delta_values)],
            y_domain=(0, max(10, max(delta_values) + 2)),
            y_ticks=nice_ticks(0, max(10, max(delta_values) + 2), 6),
            x_label="增量项",
            y_label="Delta Steps",
            formatter=lambda value: f"{value:.0f}",
        ),
        '<text class="h" x="884" y="164">冻结与恢复增量</text>',
        '<text class="p" x="74" y="472">左图横轴是暂停、检查点和恢复过程中的关键事件，纵轴是 progress.json 中记录的 step。</text>',
        '<text class="p" x="74" y="498">如果任务从 0 重跑，恢复起点会接近 0；而真实结果直接从 34 步起跑，并最终推进到 42 步。</text>',
        chip(74, 548, 180, "检查点步数", str(summary["checkpoint_step"]), PALETTE["cyan"]),
        chip(276, 548, 180, "恢复起点", str(summary["restored_initial_step"]), PALETTE["blue"]),
        chip(478, 548, 180, "恢复终点", str(summary["restored_final_step"]), PALETTE["green"]),
        chip(680, 548, 232, "连续接续", str(summary["progress_continued"]), PALETTE["amber"]),
        chip(934, 548, 190, "暂停冻结增量", str(summary["pause_freeze_delta_steps"]), PALETTE["red"]),
        chip(1146, 548, 190, "恢复新增步数", str(summary["resume_recovery_delta_steps"]), PALETTE["green"]),
    ]
    return svg_frame("实验 F：进度连续性与控制效果", "把检查点步数、恢复起点与最终步数放在同一张标准测试图上，证明任务是接续而不是重跑。", 1420, 680, "".join(body))


def comparison_svg(data: dict) -> str:
    rows = data["samples"]
    power_plot = PlotArea(74, 176, 360, 240)
    util_plot = PlotArea(474, 176, 360, 240)
    process_plot = PlotArea(874, 176, 440, 240)
    power_series = [
        ("源卡", PALETTE["blue"], [_phase_avg(rows, "paused_window", "source_power_w"), _phase_avg(rows, "restored_window", "source_power_w")]),
        ("目标卡", PALETTE["amber"], [_phase_avg(rows, "paused_window", "target_power_w"), _phase_avg(rows, "restored_window", "target_power_w")]),
    ]
    util_series = [
        ("源卡", PALETTE["blue"], [_phase_avg(rows, "paused_window", "source_util"), _phase_avg(rows, "restored_window", "source_util")]),
        ("目标卡", PALETTE["amber"], [_phase_avg(rows, "paused_window", "target_util"), _phase_avg(rows, "restored_window", "target_util")]),
    ]
    process_series = [
        ("源卡", PALETTE["blue"], [_phase_avg(rows, "paused_window", "source_process_count"), _phase_avg(rows, "restored_window", "source_process_count")]),
        ("目标卡", PALETTE["amber"], [_phase_avg(rows, "paused_window", "target_process_count"), _phase_avg(rows, "restored_window", "target_process_count")]),
    ]
    body = [
        '<rect class="card" x="42" y="126" width="1336" height="498" rx="24"/>',
        render_grouped_bars(
            power_plot,
            categories=["暂停窗口", "恢复窗口"],
            series=power_series,
            y_domain=(0, 320),
            y_ticks=[0, 80, 160, 240, 320],
            x_label="阶段窗口",
            y_label="Power (W)",
            formatter=lambda value: f"{value:.0f}",
        ),
        render_grouped_bars(
            util_plot,
            categories=["暂停窗口", "恢复窗口"],
            series=util_series,
            y_domain=(0, 100),
            y_ticks=[0, 25, 50, 75, 100],
            x_label="阶段窗口",
            y_label="Utilization (%)",
            formatter=lambda value: f"{value:.0f}",
        ),
        render_grouped_bars(
            process_plot,
            categories=["暂停窗口", "恢复窗口"],
            series=process_series,
            y_domain=(0, 1),
            y_ticks=[0, 1],
            x_label="阶段窗口",
            y_label="Process Count",
            formatter=lambda value: f"{value:.0f}",
        ),
        render_legend(
            84,
            148,
            [
                ("源卡", PALETTE["blue"]),
                ("目标卡", PALETTE["amber"]),
            ],
        ),
        '<text class="h" x="68" y="164">冻结、接手与进程归属对比</text>',
        chip(74, 548, 220, "源卡运行均值", f'{_running_avg(rows):.2f}W', PALETTE["blue"]),
        chip(316, 548, 220, "暂停期源卡均值", f'{data["summary"]["source_paused_avg_power_w"]:.2f}W', PALETTE["red"]),
        chip(558, 548, 220, "恢复期目标卡均值", f'{data["summary"]["target_restored_avg_power_w"]:.2f}W', PALETTE["amber"]),
        chip(800, 548, 220, "切换时延", f'{data["summary"]["switch_latency_s"]:.2f}s', PALETTE["cyan"]),
        chip(1042, 548, 324, "恢复进度", f'{data["summary"]["checkpoint_step"]} -> {data["summary"]["restored_initial_step"]} -> {data["summary"]["restored_final_step"]}', PALETTE["green"]),
    ]
    return svg_frame("实验 F：暂停、恢复与跨卡切换压缩图", "把功耗、利用率与进程归属三组指标放在一起，直接展示任务冻结和目标卡接手的现象。", 1420, 660, "".join(body))


def _phase_first_elapsed(rows: list[dict], phase: str) -> float:
    return next(item["elapsed_s"] for item in rows if item["phase"] == phase)


def _phase_avg(rows: list[dict], phase: str, key: str) -> float:
    phase_rows = [item for item in rows if item["phase"] == phase]
    return round(sum(float(item[key]) for item in phase_rows) / len(phase_rows), 2)


def _running_avg(rows: list[dict]) -> float:
    running_rows = [item for item in rows if item["phase"] in {"source_running", "source_resumed"}]
    return round(sum(float(item["source_power_w"]) for item in running_rows) / len(running_rows), 2)


def _phase_sections(rows: list[dict], area: PlotArea, x_domain: tuple[float, float]) -> str:
    order = ["source_running", "paused_window", "source_resumed", "checkpoint_ready", "restored_window"]
    labels = {
        "source_running": ("源卡运行", "#E8F1FF"),
        "paused_window": ("暂停窗口", "#FFF4E5"),
        "source_resumed": ("源卡恢复", "#E8FAFD"),
        "checkpoint_ready": ("检查点", "#FEECEC"),
        "restored_window": ("目标卡接续", "#ECFDF5"),
    }
    parts = []
    for index, phase in enumerate(order):
        phase_rows = [item for item in rows if item["phase"] == phase]
        if not phase_rows:
            continue
        start = phase_rows[0]["elapsed_s"]
        end = phase_rows[-1]["elapsed_s"]
        if start == end and index + 1 < len(order):
            next_rows = [item for item in rows if item["phase"] == order[index + 1]]
            if next_rows:
                end = next_rows[0]["elapsed_s"]
        label, fill = labels[phase]
        parts.append(render_phase_band(area, start=start, end=end, x_domain=x_domain, fill=fill, label=label))
    return "".join(parts)


def _point_labels(
    area: PlotArea,
    x_domain: tuple[float, float],
    y_domain: tuple[float, float],
    points: list[tuple[float, float]],
) -> str:
    labels = []
    for x_value, y_value in points:
        x = area.x + area.width * ((x_value - x_domain[0]) / (x_domain[1] - x_domain[0]))
        y = area.y2 - area.height * ((y_value - y_domain[0]) / (y_domain[1] - y_domain[0]))
        labels.append(f'<text class="s" x="{x:.1f}" y="{y - 10:.1f}" text-anchor="middle">{esc(int(y_value))}</text>')
    return "".join(labels)


def _state_step(data: dict, key: str) -> int:
    return int(data[key]["step"])


def main() -> None:
    data = load_data()
    write_summary_csv(data)
    TIMELINE_PATH.write_text(timeline_svg(data), encoding="utf-8")
    PROGRESS_PATH.write_text(progress_svg(data), encoding="utf-8")
    COMPARISON_PATH.write_text(comparison_svg(data), encoding="utf-8")
    print(json.dumps({"timeline": str(TIMELINE_PATH), "progress": str(PROGRESS_PATH), "comparison": str(COMPARISON_PATH)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
