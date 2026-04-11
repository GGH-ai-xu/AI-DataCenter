from __future__ import annotations

import csv
import json
from pathlib import Path

from report_book_svg_base import PALETTE, bar, card, chip, esc, svg_frame


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
    x = lambda idx: 84 + idx * (720 / max(len(rows) - 1, 1))
    y = lambda value: 438 - value / 360 * 220
    source = " ".join(f"{x(i):.1f},{y(float(r['source_power_w'])):.1f}" for i, r in enumerate(rows))
    target = " ".join(f"{x(i):.1f},{y(float(r['target_power_w'])):.1f}" for i, r in enumerate(rows))
    body = [
        '<rect class="card" x="42" y="126" width="820" height="352" rx="24"/>',
        '<rect class="card" x="900" y="126" width="478" height="352" rx="24"/>',
        f'<polyline points="{esc(source)}" fill="none" stroke="{PALETTE["blue"]}" stroke-width="4" stroke-linecap="round"/>',
        f'<polyline points="{esc(target)}" fill="none" stroke="{PALETTE["amber"]}" stroke-width="4" stroke-linecap="round"/>',
        '<text class="h" x="74" y="164">源卡与目标卡功耗切换时间线</text>',
        '<text class="p" x="920" y="178">蓝线是源 GPU，橙线是目标 GPU。</text>',
        '<text class="p" x="920" y="206">暂停阶段蓝线明显跌落；恢复后橙线抬升。</text>',
        '<text class="p" x="920" y="234">这说明负载从源卡退出后，重新落到了目标卡。</text>',
        chip(920, 314, 190, "源卡", f'GPU{data["source_gpu_index"]}', PALETTE["blue"]),
        chip(1128, 314, 190, "目标卡", f'GPU{data["target_gpu_index"]}', PALETTE["amber"]),
        chip(920, 392, 220, "切换时延", f'{data["summary"]["switch_latency_s"]:.2f}s', PALETTE["cyan"]),
        chip(1160, 392, 182, "连续恢复", str(data["summary"]["progress_continued"]), PALETTE["green"]),
    ]
    return svg_frame("实验 F：跨 GPU 检查点恢复时间线", "观察源卡负载退出与目标卡负载接手是否在同一条事件链上发生。", 1420, 540, "".join(body))


def progress_svg(data: dict) -> str:
    summary = data["summary"]
    body = [
        '<rect class="card" x="42" y="126" width="1336" height="444" rx="24"/>',
        '<text class="h" x="68" y="164">进度连续性与控制效果</text>',
        bar(118, 438, 150, 220, int(summary["checkpoint_step"]), max(int(summary["restored_final_step"]), 1), PALETTE["cyan"], "检查点步数"),
        bar(326, 438, 150, 220, int(summary["restored_initial_step"]), max(int(summary["restored_final_step"]), 1), PALETTE["blue"], "恢复起点"),
        bar(534, 438, 150, 220, int(summary["restored_final_step"]), max(int(summary["restored_final_step"]), 1), PALETTE["green"], "恢复后步数"),
        bar(742, 438, 150, 220, int(summary["pause_freeze_delta_steps"]), 10, PALETTE["red"], "暂停冻结增量"),
        bar(950, 438, 150, 220, int(summary["resume_recovery_delta_steps"]), 10, PALETTE["amber"], "恢复增量"),
        card(1122, 208, 220, 180, "怎么读", [
            f'检查点步数 {summary["checkpoint_step"]}',
            f'恢复起点 {summary["restored_initial_step"]}',
            f'暂停阶段步数增量 {summary["pause_freeze_delta_steps"]}',
            f'恢复后新增 {summary["resume_recovery_delta_steps"]} 步',
        ], PALETTE["blue"]),
    ]
    return svg_frame("实验 F：进度连续性证据", "重点不是功耗本身，而是任务是否从检查点接续，而不是从 0 重跑。", 1420, 640, "".join(body))


def comparison_svg(data: dict) -> str:
    summary = data["summary"]
    body = [
        '<rect class="card" x="42" y="126" width="1336" height="420" rx="24"/>',
        '<text class="h" x="68" y="164">暂停、恢复与跨卡切换效果对比</text>',
        bar(128, 430, 160, 220, int(round(summary["source_paused_avg_power_w"])), 360, PALETTE["blue"], "暂停期源卡功耗"),
        bar(386, 430, 160, 220, int(round(summary["target_restored_avg_power_w"])), 360, PALETTE["amber"], "恢复期目标卡功耗"),
        bar(644, 430, 160, 220, int(summary["checkpoint_step"]), max(int(summary["restored_final_step"]), 1), PALETTE["cyan"], "检查点步数"),
        bar(902, 430, 160, 220, int(summary["restored_final_step"]), max(int(summary["restored_final_step"]), 1), PALETTE["green"], "最终步数"),
        card(1100, 206, 240, 196, "关键结论", [
            f'源 GPU{summary["source_gpu_index"]} 在暂停窗口降到 {summary["source_paused_avg_power_w"]:.2f}W',
            f'目标 GPU{summary["target_gpu_index"]} 恢复后升到 {summary["target_restored_avg_power_w"]:.2f}W',
            "说明负载位置发生了真实切换",
        ], PALETTE["green"]),
    ]
    return svg_frame("实验 F：多维指标压缩图", "把评审最关心的三件事放在一起看：冻结、切换、接续执行。", 1420, 600, "".join(body))


def main() -> None:
    data = load_data()
    write_summary_csv(data)
    TIMELINE_PATH.write_text(timeline_svg(data), encoding="utf-8")
    PROGRESS_PATH.write_text(progress_svg(data), encoding="utf-8")
    COMPARISON_PATH.write_text(comparison_svg(data), encoding="utf-8")
    print(json.dumps({"timeline": str(TIMELINE_PATH), "progress": str(PROGRESS_PATH), "comparison": str(COMPARISON_PATH)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
