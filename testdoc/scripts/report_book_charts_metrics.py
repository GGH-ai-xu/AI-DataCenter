from __future__ import annotations

from report_book_svg_base import PALETTE, arrow, bar, card, chip, svg_frame, text_block


def platform_scale_svg(dataset: dict) -> str:
    body = [
        chip(56, 154, 248, "命名视图", str(len(dataset["workspace_map"]["named_views"])), PALETTE["blue"]),
        chip(326, 154, 248, "后端端点", str(dataset["api_domains"]["total"]), PALETTE["green"]),
        chip(596, 154, 248, "持久化表", str(dataset["persistence"]["total"]), PALETTE["amber"]),
        chip(866, 154, 248, "控制能力", str(dataset["extensions"]["total_capabilities"]), PALETTE["cyan"]),
        chip(1136, 154, 228, "测试资产", str(dataset["test_domains"]["total"]), PALETTE["red"]),
        card(56, 274, 1310, 174, "规模解读", [
            "14 个命名视图说明前端已形成导入、治理、分析、智能四大叙事面。",
            "110 个后端端点说明系统并非单页工具，而是多能力域平台。",
            "22 张持久化表与 29 个控制能力前缀共同支撑历史回放、审计闭环与扩展控制。",
            "260 个相关测试用例为作品书中的功能宣称提供了工程证据背景。"
        ], PALETTE["slate"]),
    ]
    return svg_frame("图 8  平台总体规模指标", "用于封面和第 1 章摘要页，快速向评审展示项目的实际工程体量。", 1420, 500, "".join(body))


def api_domains_svg(dataset: dict) -> str:
    domains = dataset["api_domains"]["domains"]
    max_value = max(item["value"] for item in domains)
    body = ['<rect class="card" x="42" y="126" width="1336" height="540" rx="24"/>']
    for index, item in enumerate(domains):
        body.append(bar(86 + index * 214, 560, 92, 280, item["value"], max_value, list(PALETTE.values())[index + 4], item["name"]))
    body.extend([
        chip(56, 686, 260, "后端端点总数", str(dataset["api_domains"]["total"]), PALETTE["blue"]),
        chip(336, 686, 460, "最大域", max(domains, key=lambda item: item["value"])["name"], PALETTE["green"]),
        chip(816, 686, 548, "章节作用", "第 4 章用真实路由规模证明项目是多能力域平台，而非单页 Demo", PALETTE["amber"]),
    ])
    return svg_frame("图 8  后端 API 能力域分布", "端点数量直接由 backend/app/api 下的 @router 装饰器统计得到，当前总数为 110。", 1420, 786, "".join(body))


def capability_prefix_svg(dataset: dict) -> str:
    items = dataset["extensions"]["capabilities"]
    max_value = max(item["value"] for item in items)
    colors = [PALETTE["blue"], PALETTE["green"], PALETTE["amber"], PALETTE["cyan"], PALETTE["slate"], PALETTE["red"], "#7C3AED", "#0F766E", "#92400E"]
    body = ['<rect class="card" x="42" y="126" width="1336" height="540" rx="24"/>']
    for index, item in enumerate(items):
        body.append(bar(62 + index * 150, 560, 72, 260, item["value"], max_value, colors[index], item["name"]))
    body.extend([
        chip(56, 686, 280, "能力前缀数", str(len(items)), PALETTE["blue"]),
        chip(356, 686, 310, "能力总量", str(dataset["extensions"]["total_capabilities"]), PALETTE["green"]),
        chip(686, 686, 678, "说明", "图中分布来自 goal_runtime 下所有 CapabilityDefinition，反映系统支持的对象级控制广度。", PALETTE["amber"]),
    ])
    return svg_frame("图 10  控制能力前缀分布", "这张图补充说明控制平面并不只覆盖任务暂停/恢复，还覆盖调度、策略、队列、节点和分配对象。", 1420, 786, "".join(body))


def validation_summary_svg(dataset: dict) -> str:
    rv = dataset["metadata"]["real_validation"]
    body = [
        card(54, 154, 320, 172, "真实验证结果", [f'通过 {rv["passed"]}', f'失败 {rv["failed"]}', f'耗时 {rv["duration_sec"]} s'], PALETTE["blue"]),
        card(410, 154, 450, 172, "命令口径", ["本作品书只把实际跑出的单测写成真实结果。", "其余批量图表如需示意，会明确标注为示例模拟数据。"], PALETTE["green"]),
        card(896, 154, 470, 172, "已覆盖链路", ["导入作用域刷新", "实时/历史 scope 过滤", "控制命令状态机", "治理工作台主结构"], PALETTE["amber"]),
        chip(54, 378, 300, "真实性原则", "代码能证实才写", PALETTE["blue"]),
        chip(376, 378, 300, "模板要求响应", "宣称必须有结果支撑", PALETTE["green"]),
        chip(698, 378, 300, "当前适用", "作品书初版答辩", PALETTE["amber"]),
        chip(1020, 378, 346, "待继续补测", "多机长期稳定性 / 更大规模压力", PALETTE["red"]),
        text_block(54, 492, [rv["command"]], "s", 16),
    ]
    return svg_frame("图 9  真实验证结果摘要", "第 5 章会把真实测试与示例图表严格分栏，避免把示意数据写成真实跑数。", 1420, 600, "".join(body))


def import_scope_svg(dataset: dict) -> str:
    metric = dataset["kernel_metrics"]["import_scope"]
    body = [
        card(54, 154, 286, 162, "导入前 raw", [f'GPU {metric["raw_gpu"]}', f'进程 {metric["raw_proc"]}'], PALETTE["slate"]),
        card(392, 154, 286, 162, "提交 import context", ["保存 imported_gpu_indexes", "触发 refresh_runtime_snapshot_scope"], PALETTE["blue"]),
        card(730, 154, 286, 162, "导入后 scoped", [f'GPU {metric["scoped_gpu"]}', f'进程 {metric["scoped_proc"]}'], PALETTE["green"]),
        card(1068, 154, 298, 162, "越界可见数", [str(metric["out_scope_visible"]), "非作用域资源不再进入下游页面"], PALETTE["amber"]),
        arrow(340, 236, 392, 236, PALETTE["blue"]),
        arrow(678, 236, 730, 236, PALETTE["green"]),
        arrow(1016, 236, 1068, 236, PALETTE["amber"]),
        chip(54, 378, 430, "代码依据", "system_import.commit_import_context -> refresh_runtime_snapshot_scope", PALETTE["blue"]),
        chip(508, 378, 406, "能力结论", "边界建立发生在后端快照层", PALETTE["green"]),
        chip(938, 378, 428, "评审回答", "不是前端把别的 GPU 隐藏起来，而是系统级 scope 已被改写", PALETTE["amber"]),
    ]
    return svg_frame("图 10  导入作用域建立链路", "该图用最小指标集说明导入动作为何是整个平台的起点。", 1420, 500, "".join(body))


def scope_matrix_svg(dataset: dict) -> str:
    rows = dataset["kernel_metrics"]["scope_rows"]
    body = ['<rect class="card" x="42" y="126" width="1336" height="632" rx="24"/>']
    body.append('<text class="s" x="64" y="154">验证项</text><text class="s" x="408" y="154">类型</text><text class="s" x="586" y="154">作用域内</text><text class="s" x="760" y="154">作用域外</text><text class="s" x="934" y="154">越界拦截率</text>')
    for index, row in enumerate(rows):
        y = 172 + index * 50
        block = "--" if row[4] is None else f"{row[4]}%"
        body.append(f'<rect x="56" y="{y}" width="1308" height="42" rx="12" fill="#FBFDFF" stroke="{PALETTE["line"]}" stroke-width="1"/>')
        body.append(f'<text class="p" x="74" y="{y + 26}">{row[0]}</text><text class="s" x="408" y="{y + 26}">{row[1]}</text>')
        body.append(f'<text class="k" x="586" y="{y + 26}" fill="{PALETTE["blue"]}">{row[2]}</text><text class="k" x="760" y="{y + 26}" fill="{PALETTE["red"]}">{row[3]}</text>')
        body.append(f'<text class="k" x="934" y="{y + 26}" fill="{PALETTE["green"] if row[4] else PALETTE["slate"]}">{block}</text>')
    body.extend([
        chip(56, 778, 290, "读路径结论", "实时与历史都继承 scope", PALETTE["blue"]),
        chip(366, 778, 290, "写路径结论", "越界动作被显式拒绝", PALETTE["green"]),
        chip(676, 778, 320, "空作用域处理", "run_once 直接报错", PALETTE["amber"]),
        chip(1016, 778, 348, "章节价值", "这是证明系统内核最强的一张图", PALETTE["red"]),
    ])
    return svg_frame("图 11  作用域一致性覆盖矩阵", "矩阵条目依据现有测试断言整理，用于展示 scope 在读路径、历史路径与写路径上的一致性。", 1420, 878, "".join(body))


def command_lifecycle_svg(dataset: dict) -> str:
    life = dataset["kernel_metrics"]["command_lifecycle"]
    body = [
        card(52, 154, 218, 118, "命令总量", [str(life["total"])], PALETTE["blue"]),
        card(316, 154, 242, 118, "待审批", [str(life["approval"])], PALETTE["amber"]),
        card(604, 154, 242, 118, "直接入队", [str(life["queue"])], PALETTE["green"]),
        card(892, 154, 218, 118, "执行成功", [str(life["success"])], PALETTE["cyan"]),
        card(1156, 154, 210, 118, "失败 / 拒绝", [f'{life["failed"]} / {life["rejected"]}'], PALETTE["red"]),
        arrow(270, 214, 316, 214, PALETTE["blue"]),
        arrow(558, 214, 604, 214, PALETTE["amber"]),
        arrow(846, 214, 892, 214, PALETTE["green"]),
        arrow(1110, 214, 1156, 214, PALETTE["cyan"]),
        card(52, 344, 1314, 172, "状态机解释", [
            "create_command 先创建命令记录，再按 permission_mode 分流为 not_required / confirm_required / approval_required。",
            "approve_command 负责待审批命令的批准或拒绝；_execute_command 负责真实执行与结果回写。",
            "GovernanceReviewView 最终消费同一批 commandRecords 并支持 full-report 导出。"
        ], PALETTE["slate"]),
    ]
    return svg_frame("图 12  治理命令生命周期", "状态字段与流转节点来自代码和测试，图中命令数量为答辩示意值，用于解释统一控制闭环。", 1420, 560, "".join(body))


def policy_linkage_svg(dataset: dict) -> str:
    link = dataset["kernel_metrics"]["policy_linkage"]
    body = [
        card(54, 154, 300, 132, "策略写入", [f'总次数 {link["writes"]}', "budget / carbon / auto / power / run_once / user_rule"], PALETTE["blue"]),
        card(404, 154, 300, 132, "Review 可见", [str(link["review_visible"]), "Policies 写入后立即 refreshReview"], PALETTE["green"]),
        card(754, 154, 300, 132, "导出覆盖", [str(link["exported"]), "full-report 聚合综合治理结果"], PALETTE["amber"]),
        card(1104, 154, 262, 132, "平均联动", [f'{link["avg_sync_sec"]} s', "用于示意多轮策略操作的闭环时延"], PALETTE["cyan"]),
        arrow(354, 220, 404, 220, PALETTE["blue"]),
        arrow(704, 220, 754, 220, PALETTE["green"]),
        arrow(1054, 220, 1104, 220, PALETTE["amber"]),
        chip(54, 340, 430, "代码依据", "GovernancePoliciesView 中每次写入后都会 refreshPolicies 与 refreshReview", PALETTE["blue"]),
        chip(508, 340, 398, "闭环结论", "策略页不是孤立配置页，而是可复盘、可导出的治理入口", PALETTE["green"]),
        chip(930, 340, 436, "作品书作用", "用于支撑模板第 5 章“有效性与稳定性应由结果支持”这一要求", PALETTE["amber"]),
    ]
    return svg_frame("图 13  策略写入到复盘导出联动", "联动路径来自前后端代码，写入次数与联动时延为答辩示意值，用于说明治理闭环而非线上报表。", 1420, 480, "".join(body))


def test_domains_svg(dataset: dict) -> str:
    domains = dataset["test_domains"]["domains"]
    max_value = max(item["value"] for item in domains)
    body = ['<rect class="card" x="42" y="126" width="1336" height="540" rx="24"/>']
    for index, item in enumerate(domains):
        body.append(bar(86 + index * 214, 560, 92, 280, item["value"], max_value, [PALETTE["blue"], PALETTE["green"], PALETTE["amber"], PALETTE["cyan"], PALETTE["slate"], PALETTE["red"]][index], item["name"]))
    body.extend([
        chip(56, 686, 260, "测试总量", str(dataset["test_domains"]["total"]), PALETTE["blue"]),
        chip(336, 686, 452, "图表含义", "按功能域统计现有测试数量，展示项目不是单模块代码仓库", PALETTE["green"]),
        chip(808, 686, 556, "章节作用", "第 5 章既写真实运行结果，也写现有测试资产分布，增强评审对工程完整性的感知", PALETTE["amber"]),
    ])
    return svg_frame("图 14  测试资产按功能域分布", "计数来自 tests/ 与 backend/tests/ 中与各能力域对应的测试文件。", 1420, 786, "".join(body))


def agent_effectiveness_svg(dataset: dict) -> str:
    info = dataset["testing_detail"]["agent_effectiveness"]
    groups = info["endpoint_groups"]
    max_value = max(item["value"] for item in groups)
    colors = [PALETTE["blue"], PALETTE["green"], PALETTE["amber"]]
    body = ['<rect class="card" x="42" y="126" width="1336" height="566" rx="24"/>']
    for index, item in enumerate(groups):
        body.append(bar(90 + index * 180, 454, 88, 220, item["value"], max_value, colors[index], item["name"]))
    body.extend([
        chip(650, 162, 250, "遥测字段数", str(len(info["telemetry_fields"])), PALETTE["cyan"]),
        chip(920, 162, 250, "真实通过", str(info["real_checks"]["passed"]), PALETTE["green"]),
        chip(1190, 162, 160, "耗时", f'{info["real_checks"]["duration_sec"]} s', PALETTE["amber"]),
        card(430, 260, 920, 172, "有效性解释", [
            f'Agent 当前共暴露 {sum(item["value"] for item in groups)} 个接口，其中采集 7 个、控制 4 个、运行时 10 个。',
            f'GPU 采样至少覆盖 {len(info["telemetry_fields"])} 个核心字段，且 system_monitor 使用 {info["sampling"]["cpu_sampling"]} 的非阻塞 CPU 采样方式。',
            f'进程缓存测试场景中 {info["sampling"]["cached_accesses"]} 次读取仅触发 {info["sampling"]["real_scans"]} 次真实扫描，说明 Agent 不是高频全量阻塞拉取。'
        ], PALETTE["slate"]),
        chip(56, 522, 360, "为什么这张图重要", "它把 Agent 从“存在一个服务”提升为“具备采集、控制、运行时三层能力”的可视化证据", PALETTE["blue"]),
        chip(436, 522, 430, "评审视角", "Agent 的有效性不应只看能否启动，而要看能否形成稳定可用的数据与动作接口", PALETTE["green"]),
        chip(886, 522, 464, "章节定位", "用于第 5 章回答“Agent 到底支撑了平台哪些真实能力”", PALETTE["amber"]),
    ])
    return svg_frame("图 15  Agent 有效性与能力覆盖", "这张图把 Agent 的接口层、遥测层、采样策略和真实验证结果放到同一张证据图上。", 1420, 726, "".join(body))


def agent_integration_svg(dataset: dict) -> str:
    items = dataset["testing_detail"]["agent_effectiveness"]["integration_points"]
    body = ['<rect class="card" x="42" y="126" width="1336" height="574" rx="24"/>']
    for index, item in enumerate(items):
        y = 158 + index * 106
        color = PALETTE["green"] if item["state"] == "passed" else PALETTE["amber"]
        body.append(card(58, y, 1304, 86, item["name"], [item["detail"]], color))
    body.extend([
        chip(58, 610, 330, "核心结论", "Agent 数据进入平台后还会再经过 Provider、import scope 与 privacy 处理", PALETTE["blue"]),
        chip(408, 610, 402, "不是原样透传", "系统详情、训练日志和 GPU 进程并非直接裸转发，而是会按导入边界做二次约束", PALETTE["green"]),
        chip(830, 610, 532, "测试意义", "这张图把 Agent 的“可接入性”“可过滤性”“可解释性”一起展现出来", PALETTE["amber"]),
    ])
    return svg_frame("图 16  Agent 运行模式与平台适配", "平台不是简单调用 Agent，而是把 Agent 输出经过 Provider、导入边界与页面模型进一步整合。", 1420, 716, "".join(body))


def agent_dimensions_svg(dataset: dict) -> str:
    info = dataset["testing_detail"]["agent_effectiveness"]
    total_endpoints = sum(item["value"] for item in info["endpoint_groups"])
    body = [
        card(54, 154, 292, 126, "接口完整度", [f"{total_endpoints} 个接口", "采集 / 控制 / 运行时 三层"], PALETTE["blue"]),
        card(374, 154, 292, 126, "遥测丰富度", [f'{len(info["telemetry_fields"])} 个核心字段', "温度 / 功耗 / 显存 / 时钟"], PALETTE["green"]),
        card(694, 154, 292, 126, "运行效率", [f'{info["sampling"]["cached_accesses"]} 次读取 / {info["sampling"]["real_scans"]} 次扫描', "缓存降低高频拉取阻塞"], PALETTE["amber"]),
        card(1014, 154, 352, 126, "平台适配度", [f'{len(info["integration_points"])} 个已验证接入点', "Provider / import scope / training filter"], PALETTE["cyan"]),
        card(54, 320, 620, 150, "失败可解释性", ["缺失 NVML 时不会伪造 GPU 数据。", "启动阶段会明确提示改用 SSH Linux 或远程 Agent。"], PALETTE["slate"]),
        card(714, 320, 652, 150, "真实测试支撑", [f'相关真实通过 {info["real_checks"]["passed"]} 项，覆盖采样、缓存、远程读取与启动提示。', f'耗时 {info["real_checks"]["duration_sec"]} s，整张图不使用主观评分。'], PALETTE["red"]),
        chip(54, 506, 400, "图表口径", "全部指标来自代码统计或已运行测试", PALETTE["blue"]),
        chip(478, 506, 404, "评审价值", "把 Agent 的“有效”拆成可核查的五个维度", PALETTE["green"]),
        chip(906, 506, 460, "核心结论", "Agent 不只是采样器，而是平台的接入、过滤与动作执行底座", PALETTE["amber"]),
    ]
    return svg_frame("图 17  Agent 多维有效性拆解", "这张图不用主观评分，而是把 Agent 的有效性拆成接口、遥测、效率、适配与可解释性五个维度。", 1420, 620, "".join(body))


def extension_status_svg(dataset: dict) -> str:
    info = dataset["testing_detail"]["extension_validation"]
    stable = info["stable"]
    drift = info["drift"]
    body = []
    for index, item in enumerate(stable):
        y = 154 + index * 112
        body.append(card(54, y, 620, 88, item["name"], [f'真实通过 {item["passed"]} 项', f'耗时 {item["duration_sec"]} s'], PALETTE["green"]))
    for index, item in enumerate(drift):
        y = 154 + index * 132
        body.append(card(744, y, 622, 108, item["name"], [item["kind"], item["reason"]], PALETTE["red"]))
    body.extend([
        chip(54, 432, 412, "写作策略", "对扩展层不做“全绿化”包装，稳定项与漂移项分开呈现", PALETTE["blue"]),
        chip(488, 432, 412, "评审收益", "这样更能体现项目处于真实迭代，而不是把所有模块都写成完美完成态", PALETTE["green"]),
        chip(922, 432, 444, "章节结论", "扩展层已有稳定可验证部分，同时存在接口演进中的测试漂移，需要后续同步", PALETTE["amber"]),
    ])
    return svg_frame("图 20  扩展能力验证状态", "第 5 章既要展示已稳定能力，也要如实说明 AI 扩展层目前存在的测试漂移。", 1420, 560, "".join(body))
