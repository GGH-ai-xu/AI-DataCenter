from __future__ import annotations

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
from report_book_svg_base import PALETTE, arrow, card, chip, esc, svg_frame, text_block


TINTS = {
    "blue": "#E8F1FF",
    "green": "#ECFDF5",
    "amber": "#FFF4E5",
    "red": "#FEECEC",
    "slate": "#F1F5F9",
    "cyan": "#E8FAFD",
}


def remote_budget_experiment_svg(dataset: dict) -> str:
    exp = dataset["real_remote_budget_experiment"]
    plot = PlotArea(64, 170, 760, 324)
    categories = ["基线", "爬升", "治理后"]
    avg_values = [
        exp["baseline"]["avg_power"],
        exp["ramp"]["avg_power"],
        exp["post_action"]["avg_power"],
    ]
    peak_values = [
        exp["baseline"]["peak_power"],
        exp["ramp"]["peak_power"],
        exp["post_action"]["peak_power"],
    ]
    power_domain = pad_domain(0, max(peak_values + [exp["power_alert_threshold"]]), 0.08)
    power_ticks = nice_ticks(power_domain[0], power_domain[1], 6)
    body = [
        '<rect class="card" x="42" y="126" width="812" height="388" rx="24"/>',
        render_grouped_bars(
            plot,
            categories=categories,
            series=[
                ("平均功耗", PALETTE["blue"], avg_values),
                ("峰值功耗", PALETTE["amber"], peak_values),
            ],
            y_domain=power_domain,
            y_ticks=power_ticks,
            x_label="实验阶段",
            y_label="功耗 (W)",
            formatter=lambda value: f"{value:.0f}",
        ),
        render_horizontal_marker(
            plot,
            value=exp["power_alert_threshold"],
            y_domain=power_domain,
            color=PALETTE["red"],
            label=f'告警阈值 {exp["power_alert_threshold"]}W',
        ),
        render_legend(
            86,
            148,
            [
                ("平均功耗", PALETTE["blue"]),
                ("峰值功耗", PALETTE["amber"]),
                ("告警阈值", PALETTE["red"]),
            ],
        ),
        '<text class="h" x="64" y="160">功耗统计图</text>',
        '<text class="s" x="64" y="182">横轴为阶段，纵轴为功耗，所有数值均来自真实采样窗口汇总。</text>',
        card(884, 154, 482, 118, "实测对象", [f'主机 {exp["host"]}', f'GPU {exp["gpu_index"]}，PID {exp["workload_pid"]}', f'原始上限 {exp["original_power_limit"]}W'], PALETTE["blue"]),
        card(884, 290, 482, 118, "治理动作", [f'预算阈值 {exp["budget_limit"]}W', f'功耗上限 {exp["original_power_limit"]}W -> {exp["managed_power_limit"]}W', f'动作执行成功 {exp["action_success"]}'], PALETTE["green"]),
        card(884, 426, 482, 118, "实验结论", [f'峰值 {exp["peak_sample"]["power_usage"]:.2f}W 后回落 {exp["power_drop_watts"]:.2f}W', f'治理后 {exp["post_action"]["sample_count"]} 个样本越阈数 {exp["post_action"]["above_alert_samples"]}', '说明系统动作真实改变了设备侧功耗状态'], PALETTE["cyan"]),
        chip(54, 548, 280, "后窗均值", f'{exp["post_action"]["avg_power"]:.2f}W', PALETTE["green"]),
        chip(356, 548, 280, "功耗降幅", f'{exp["power_drop_watts"]:.2f}W', PALETTE["blue"]),
        chip(658, 548, 280, "总功率回落", f'{exp["total_power_drop_watts"]:.2f}W', PALETTE["amber"]),
        chip(960, 548, 406, "后窗清洁率", f'{exp["post_clean_ratio_pct"]:.1f}%  ({exp["post_action"]["sample_count"]} 个样本)', PALETTE["cyan"]),
    ]
    return svg_frame("图 18  实验 A：真实远端功耗告警治理闭环", "在 10.151.225.108 的空闲 RTX 3090 上制造高功耗负载，再人工触发一次预算治理，观察功耗与告警条件的真实变化。", 1420, 630, "".join(body))


def remote_budget_timeline_svg(dataset: dict) -> str:
    exp = dataset["real_remote_budget_experiment"]
    samples = exp["samples"]
    power_plot = PlotArea(74, 176, 760, 280)
    total_plot = PlotArea(74, 520, 760, 122)
    elapsed_values = [item["elapsed_s"] for item in samples]
    x_domain = (min(elapsed_values), max(elapsed_values))
    x_ticks = nice_ticks(x_domain[0], x_domain[1], 6)
    power_values = [item["power_usage"] for item in samples] + [item["power_limit"] for item in samples] + [exp["power_alert_threshold"]]
    power_domain = pad_domain(min(power_values), max(power_values), 0.08)
    power_ticks = nice_ticks(power_domain[0], power_domain[1], 6)
    total_values = [item["total_power"] for item in samples]
    total_domain = pad_domain(min(total_values), max(total_values), 0.08)
    total_ticks = nice_ticks(total_domain[0], total_domain[1], 4)
    power_points = [(item["elapsed_s"], item["power_usage"]) for item in samples]
    limit_points = [(item["elapsed_s"], item["power_limit"]) for item in samples]
    total_points = [(item["elapsed_s"], item["total_power"]) for item in samples]
    action_elapsed = next(item["elapsed_s"] for item in samples if item["phase"] == "post_action")
    body = [
        '<rect class="card" x="42" y="126" width="828" height="368" rx="24"/>',
        '<rect class="card" x="42" y="520" width="828" height="178" rx="24"/>',
        '<rect class="card" x="900" y="126" width="478" height="572" rx="24"/>',
        _phase_sections(samples, power_plot, x_domain),
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
        render_line_series(power_points, x_domain=x_domain, y_domain=power_domain, area=power_plot, color=PALETTE["blue"]),
        render_line_series(limit_points, x_domain=x_domain, y_domain=power_domain, area=power_plot, color=PALETTE["green"]),
        render_horizontal_marker(
            power_plot,
            value=exp["power_alert_threshold"],
            y_domain=power_domain,
            color=PALETTE["red"],
            label=f'阈值 {exp["power_alert_threshold"]}W',
        ),
        render_vertical_marker(
            power_plot,
            value=action_elapsed,
            x_domain=x_domain,
            color=PALETTE["amber"],
            label="治理动作",
        ),
        render_legend(
            84,
            148,
            [
                ("实测功耗", PALETTE["blue"]),
                ("功耗上限", PALETTE["green"]),
                ("阈值线", PALETTE["red"]),
                ("动作时刻", PALETTE["amber"]),
            ],
        ),
        '<text class="h" x="74" y="164">GPU3 功耗与功耗上限时间线</text>',
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
        render_line_series(total_points, x_domain=x_domain, y_domain=total_domain, area=total_plot, color=PALETTE["slate"], width=3.0),
        render_vertical_marker(
            total_plot,
            value=action_elapsed,
            x_domain=x_domain,
            color=PALETTE["amber"],
            label="动作",
        ),
        '<text class="h" x="74" y="510">集群总功率变化</text>',
        '<text class="s" x="920" y="176">怎么读这张图</text>',
        '<text class="p" x="920" y="208">1. 蓝线是 GPU3 实测功耗，绿线是当前功耗上限。</text>',
        '<text class="p" x="920" y="236">2. 红虚线是 320W 告警阈值，蓝线穿越后触发一次真实告警。</text>',
        '<text class="p" x="920" y="264">3. 橙虚线是人工调度动作生效时刻，之后绿线从 350W 切到 261W。</text>',
        '<text class="p" x="920" y="292">4. 治理后蓝线稳定贴近 261W，18 个连续采样点全部低于阈值。</text>',
        f'<text class="p" x="920" y="334">峰值功耗：{exp["peak_sample"]["power_usage"]:.2f}W</text>',
        f'<text class="p" x="920" y="362">首次治理后功耗：{exp["first_post_sample"]["power_usage"]:.2f}W</text>',
        f'<text class="p" x="920" y="390">首次治理后总功率：{exp["first_post_sample"]["total_power"]:.2f}W</text>',
        f'<text class="p" x="920" y="418">人工治理动作：set_power_limit GPU {exp["gpu_index"]} -> {exp["managed_power_limit"]}W</text>',
        f'<text class="p" x="920" y="446">治理前后总功率回落：{exp["total_power_drop_watts"]:.2f}W</text>',
        f'<text class="p" x="920" y="474">工作负载 PID：{exp["workload_pid"]}</text>',
        '<text class="s" x="920" y="526">阶段底色</text>',
        '<text class="p" x="920" y="556">蓝色：空闲基线  橙色：负载爬升  绿色：治理后观测窗口</text>',
        chip(920, 604, 188, "基线均值", f'{exp["baseline"]["avg_power"]:.2f}W', PALETTE["blue"]),
        chip(1130, 604, 108, "峰值", f'{exp["peak_sample"]["power_usage"]:.2f}W', PALETTE["red"]),
        chip(1254, 604, 112, "后均值", f'{exp["post_action"]["avg_power"]:.2f}W', PALETTE["green"]),
    ]
    return svg_frame("图 19  实验 A 时间线：功耗越阈到治理回落", "把真实样本按时间展开，直接展示告警阈值、人工调度动作和治理后稳定区间之间的关系。", 1420, 740, "".join(body))


def cluster_decision_matrix_svg(dataset: dict) -> str:
    rows = dataset["cluster_governance"]["decision_matrix"]
    body = [
        '<rect class="card" x="42" y="126" width="1336" height="538" rx="24"/>',
        chip(54, 680, 210, "直接放置", "1 类", PALETTE["green"]),
        chip(286, 680, 210, "等待/拒绝", "2 类", PALETTE["amber"]),
        chip(518, 680, 210, "需治理介入", "2 类", PALETTE["blue"]),
        chip(750, 680, 300, "目标结论", "调度输出可分为 5 种状态", PALETTE["cyan"]),
        chip(1072, 680, 294, "证据口径", "真实调度器 plan_job", PALETTE["slate"]),
        '<text class="s" x="72" y="164">计划类型</text>',
        '<text class="s" x="240" y="164">触发条件</text>',
        '<text class="s" x="716" y="164">调度输出</text>',
        '<text class="s" x="1002" y="164">治理含义</text>',
    ]
    for index, item in enumerate(rows):
        y = 184 + index * 94
        tone = item["tone"]
        body.extend(_decision_row(item, y, tone))
    return svg_frame("图 20  实验 B：集群调度决策矩阵", "同一套 ClusterSchedulerCore.plan_job 在五种资源与治理条件下输出五种不同计划，用现象说明调度器具备分流与治理判断能力。", 1420, 770, "".join(body))


def cluster_reconcile_flow_svg(dataset: dict) -> str:
    info = dataset["cluster_governance"]["reconcile_flow"]
    manual = info["manual_run"]
    skipped = info["skip_run"]
    body = [
        card(54, 154, 268, 132, "人工触发", [f'trigger = {manual["trigger"]}', "入口：/api/cluster/reconcile", f'tick 增量 {manual["tick_count_delta"]}'], PALETTE["blue"]),
        card(368, 154, 268, 132, "运行时检查", [f'status = {manual["runtime_status"]}', "允许进入 nodes_loader", "开始形成调和摘要"], PALETTE["green"]),
        card(682, 154, 332, 132, "摘要回写", [f'placed={manual["summary"].get("placed", 0)} / preempted={manual["summary"].get("preempted", 0)}', f'restored={manual["summary"].get("restored", 0)} / released={manual["summary"].get("released", 0)}', "结果写入 last_summary"], PALETTE["cyan"]),
        card(1060, 154, 306, 132, "控制器快照", [f'last_summary keys {", ".join(manual["last_summary_keys"])}', "供前端控制台和审计视图消费", manual["meaning"]], PALETTE["slate"]),
        arrow(322, 220, 368, 220, PALETTE["blue"]),
        arrow(636, 220, 682, 220, PALETTE["green"]),
        arrow(1014, 220, 1060, 220, PALETTE["cyan"]),
        '<rect class="card" x="42" y="340" width="1336" height="222" rx="24"/>',
        '<rect x="62" y="372" width="240" height="94" rx="18" fill="#FFF4E5" stroke="#D7E1EC"/>',
        '<rect x="340" y="372" width="260" height="94" rx="18" fill="#FEECEC" stroke="#D7E1EC"/>',
        '<rect x="638" y="372" width="332" height="94" rx="18" fill="#F1F5F9" stroke="#D7E1EC"/>',
        '<rect x="1008" y="372" width="338" height="94" rx="18" fill="#E8F1FF" stroke="#D7E1EC"/>',
        '<text class="h" x="62" y="360">跳过场景</text>',
        '<text class="h" x="84" y="406">后台触发</text>',
        f'<text class="p" x="84" y="432">trigger = {esc(skipped["trigger"])}</text>',
        '<text class="h" x="362" y="406">运行时未连通</text>',
        f'<text class="p" x="362" y="432">status = {esc(skipped["runtime_status"])}</text>',
        '<text class="h" x="660" y="406">明确返回 skipped</text>',
        f'<text class="p" x="660" y="432">skipped = {esc(skipped["skipped"])}</text>',
        f'<text class="p" x="660" y="454">tick 增量 = {esc(skipped["tick_count_delta"])}</text>',
        '<text class="h" x="1030" y="406">不给假成功</text>',
        f'{text_block(1030, 432, _wrap_text(skipped["skip_reason"], 18), "p", 20)}',
        arrow(302, 419, 340, 419, PALETTE["amber"]),
        arrow(600, 419, 638, 419, PALETTE["red"]),
        arrow(970, 419, 1008, 419, PALETTE["slate"]),
        chip(54, 590, 320, "执行路径证明", "manual_run 可形成 last_summary", PALETTE["green"]),
        chip(396, 590, 320, "跳过路径证明", "skip_run 显式返回 skipped", PALETTE["amber"]),
        chip(738, 590, 628, "核心结论", "调和控制器不是定时器包装，而是会根据 runtime_status 决定执行还是跳过，并把结果回写给控制台。", PALETTE["blue"]),
    ]
    return svg_frame("图 21  实验 C：调和执行与状态回写", "围绕 ClusterReconcileController.run_once 构造执行与跳过两类场景，观察调和动作是否真正回写到控制器快照。", 1420, 690, "".join(body))


def cluster_governance_coverage_svg(dataset: dict) -> str:
    coverage = dataset["cluster_governance"]["governance_coverage"]
    action_total = sum(item["action_count"] for item in coverage)
    body = [
        card(54, 154, 620, 182, coverage[0]["label"], _coverage_lines(coverage[0]), PALETTE["blue"]),
        card(706, 154, 660, 182, coverage[1]["label"], _coverage_lines(coverage[1]), PALETTE["green"]),
        card(54, 370, 620, 182, coverage[2]["label"], _coverage_lines(coverage[2]), PALETTE["amber"]),
        card(706, 370, 660, 182, coverage[3]["label"], _coverage_lines(coverage[3]), PALETTE["cyan"]),
        chip(54, 580, 220, "治理对象", str(len(coverage)), PALETTE["blue"]),
        chip(296, 580, 220, "前端暴露能力", str(action_total), PALETTE["green"]),
        chip(538, 580, 350, "读取口径", "ClusterJobs.vue + clusterConsoleActions.js", PALETTE["amber"]),
        chip(910, 580, 456, "审计结论", "治理动作不是抽象概念，而是已进入当前控制台的对象级命令面。", PALETTE["cyan"]),
    ]
    return svg_frame("图 22  实验 D：治理对象覆盖与审计证据", "从当前集群控制台界面反推可操作对象，展示系统已经把哪些治理动作真正挂到作业、队列、节点与 allocation 上。", 1420, 670, "".join(body))


def _decision_row(item: dict, y: int, tone: str) -> list[str]:
    fill = TINTS[tone]
    detail = _decision_detail(item)
    return [
        f'<rect x="58" y="{y}" width="1292" height="74" rx="18" fill="{fill}" stroke="{PALETTE["line"]}" stroke-width="1"/>',
        f'<rect x="72" y="{y + 14}" width="116" height="46" rx="14" fill="{PALETTE[tone]}"/>',
        f'<text class="k" x="92" y="{y + 42}" fill="#FFFFFF">{esc(item["plan_type"])}</text>',
        text_block(240, y + 30, _wrap_text(item["condition"], 24), "p", 18),
        text_block(716, y + 30, _wrap_text(detail, 20), "p", 18),
        text_block(1002, y + 30, _wrap_text(item["meaning"], 16), "p", 18),
    ]


def _decision_detail(item: dict) -> str:
    if item["victim_job_ids"]:
        actions = ", ".join(action["action"] for action in item["required_actions"])
        return f'输出 {item["reason"]}；治理动作 {actions}'
    if item["selected_node"] != "无":
        devices = ", ".join(item["selected_devices"]) or "none"
        return f'放置到 {item["selected_node"]}；设备 {devices}'
    return f'输出 {item["reason"]}；当前不产生放置节点'


def _coverage_lines(item: dict) -> list[str]:
    actions = _wrap_actions(item["actions"])
    lines = [f'能力 {item["action_count"]} 项：{actions[0]}']
    lines.extend(f"动作续：{group}" for group in actions[1:])
    lines.append(f'入口：{item["surface"]}')
    lines.append(f'证据：{item["evidence"]}')
    return lines


def _wrap_actions(actions: list[str]) -> list[str]:
    groups = []
    for index in range(0, len(actions), 3):
        groups.append(", ".join(actions[index:index + 3]))
    return groups or ["无"]


def _wrap_text(text: str, width: int) -> list[str]:
    if len(text) <= width:
        return [text]
    lines = []
    start = 0
    while start < len(text):
        lines.append(text[start:start + width])
        start += width
    return lines


def _polyline(samples: list[dict], x_fn, y_fn, key: str, color: str, width: int) -> str:
    points = " ".join(f"{x_fn(index):.1f},{y_fn(sample[key]):.1f}" for index, sample in enumerate(samples))
    return f'<polyline points="{esc(points)}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linejoin="round" stroke-linecap="round"/>'


def _phase_sections(samples: list[dict], area: PlotArea, x_domain: tuple[float, float]) -> str:
    bands = []
    phase_ranges = []
    for phase in ("baseline", "load_ramp", "post_action"):
        rows = [item for item in samples if item["phase"] == phase]
        if not rows:
            continue
        phase_ranges.append((phase, rows[0]["elapsed_s"], rows[-1]["elapsed_s"]))
    labels = {
        "baseline": ("空闲基线", "#E8F1FF"),
        "load_ramp": ("负载爬升", "#FFF4E5"),
        "post_action": ("治理后观测", "#ECFDF5"),
    }
    for phase, start, end in phase_ranges:
        label, fill = labels[phase]
        bands.append(
            render_phase_band(
                area,
                start=start,
                end=end,
                x_domain=x_domain,
                fill=fill,
                label=label,
            )
        )
    return "".join(bands)
