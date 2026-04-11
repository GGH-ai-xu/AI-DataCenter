from __future__ import annotations

from report_book_svg_base import PALETTE, arrow, card, chip, esc, svg_frame, text_block


def system_panorama_svg(dataset: dict) -> str:
    colors = [PALETTE["blue"], PALETTE["green"], PALETTE["amber"], PALETTE["cyan"], PALETTE["slate"]]
    body = []
    for index, layer in enumerate(dataset["panorama"]["layers"]):
        y = 132 + index * 104
        body.append(card(48, y, 1324, 84, layer["name"], [" / ".join(layer["items"])], colors[index]))
        if index < len(dataset["panorama"]["layers"]) - 1:
            body.append(arrow(710, y + 84, 710, y + 104, colors[index]))
    body.append(text_block(48, 676, [
        "作品书的系统主轴：导入层先建立治理边界，随后进入治理、分析与智能工作区，再由 server-agent、Provider 与存储层支撑历史回放和扩展能力。",
        "该分层直接对应 frontend/src/main.js、useConsoleShell.js、backend/app/main.py 和 server-agent/main.py。"
    ], "p", 24))
    return svg_frame("图 1  系统全景能力架构", "从前端工作区到后端执行与采集层，展示项目在当前代码中的完整能力面。", 1420, 740, "".join(body))


def user_workflow_svg(dataset: dict) -> str:
    steps = dataset["workflow"]["steps"]
    colors = [PALETTE["blue"], PALETTE["cyan"], PALETTE["green"], PALETTE["amber"]]
    body = []
    coords = [(54, 164), (384, 164), (714, 164), (1044, 164), (219, 372), (549, 372), (879, 372), (1044, 544)]
    for index, step in enumerate(steps):
        x, y = coords[index]
        accent = colors[index % len(colors)]
        body.append(card(x, y, 286 if index < 7 else 328, 120, f"步骤 {index + 1}", [step], accent))
    for pair in [(0, 1), (1, 2), (2, 3), (4, 5), (5, 6)]:
        x1, y1 = coords[pair[0]]
        x2, y2 = coords[pair[1]]
        body.append(arrow(x1 + 286, y1 + 58, x2, y2 + 58, PALETTE["blue"]))
    body.append(arrow(1190, 284, 1190, 372, PALETTE["green"]))
    body.append(arrow(1165, 492, 1208, 544, PALETTE["amber"]))
    body.append(arrow(197, 284, 340, 372, PALETTE["cyan"]))
    return svg_frame("图 2  用户工作流与控制台叙事", "网页作品书将按这条真实使用链路组织章节内容，而不是按孤立功能堆叠。", 1420, 720, "".join(body))


def problem_matrix_svg(dataset: dict) -> str:
    rows = dataset["problem_matrix"]
    body = ['<rect class="card" x="42" y="124" width="1334" height="504" rx="24"/>']
    body.append('<text class="s" x="66" y="154">痛点问题</text><text class="s" x="400" y="154">对应模块</text><text class="s" x="952" y="154">代码证据</text>')
    for index, item in enumerate(rows):
        y = 170 + index * 88
        body.append(f'<rect x="56" y="{y}" width="1306" height="70" rx="16" fill="#FBFDFF" stroke="{PALETTE["line"]}" stroke-width="1"/>')
        body.append(text_block(74, y + 26, [item["pain"]], "h"))
        body.append(text_block(400, y + 24, item["modules"], "p", 18))
        body.append(text_block(952, y + 24, [item["proof"]], "p"))
    body.append(chip(56, 648, 408, "章节作用", "第 2 章把问题与模块一一对上", PALETTE["blue"]))
    body.append(chip(496, 648, 408, "真实性策略", "只写代码里存在的机制，不沿用旧示例稿口径", PALETTE["green"]))
    body.append(chip(936, 648, 426, "评审价值", "先证明为什么需要这套系统，再谈创新", PALETTE["amber"]))
    return svg_frame("图 3  痛点问题到模块能力映射", "用矩阵方式把第 2 章的‘问题分析’和第 3-4 章的‘技术方案/系统实现’对接起来。", 1420, 742, "".join(body))


def workspace_map_svg(dataset: dict) -> str:
    body = [
        card(56, 154, 240, 112, "导入层", dataset["workspace_map"]["import_stages"], PALETTE["blue"]),
        card(338, 154, 220, 112, "主导航", dataset["workspace_map"]["primary_nav"], PALETTE["green"]),
        card(602, 154, 228, 112, "治理二级", dataset["workspace_map"]["governance_tabs"], PALETTE["amber"]),
        card(872, 154, 220, 112, "智能二级", dataset["workspace_map"]["ai_tabs"], PALETTE["cyan"]),
        card(1134, 154, 236, 112, "命名视图", dataset["workspace_map"]["named_views"][:6], PALETTE["slate"]),
        card(1134, 304, 236, 162, "其余视图", dataset["workspace_map"]["named_views"][6:], PALETTE["slate"]),
    ]
    body.extend([
        arrow(296, 210, 338, 210, PALETTE["blue"]),
        arrow(558, 210, 602, 210, PALETTE["green"]),
        arrow(558, 230, 872, 230, PALETTE["green"]),
        arrow(1092, 210, 1134, 210, PALETTE["cyan"]),
        arrow(1252, 266, 1252, 304, PALETTE["slate"]),
        chip(56, 520, 300, "导入阶段", "4 个阶段", PALETTE["blue"]),
        chip(378, 520, 300, "一级导航", "6 个主工作区入口", PALETTE["green"]),
        chip(700, 520, 300, "治理子页", "4 个二级工作台", PALETTE["amber"]),
        chip(1022, 520, 348, "命名视图", f'{len(dataset["workspace_map"]["named_views"])} 个命名路由视图', PALETTE["cyan"]),
    ])
    return svg_frame("图 4  前端工作区层级结构", "图中结构来自 frontend/src/main.js、useConsoleShell.js、importWorkbench.js 与 governancePageModels.js。", 1420, 620, "".join(body))


def persistence_map_svg(dataset: dict) -> str:
    colors = [PALETTE["blue"], PALETTE["green"], PALETTE["amber"], PALETTE["cyan"], PALETTE["slate"], PALETTE["red"]]
    body = []
    positions = [(52, 148), (500, 148), (948, 148), (52, 382), (500, 382), (948, 382)]
    for index, group in enumerate(dataset["persistence"]["groups"]):
        x, y = positions[index]
        body.append(card(x, y, 420, 170, group["name"], group["tables"], colors[index]))
        body.append(chip(x + 264, y + 16, 136, "数量", str(group["count"]), colors[index]))
    body.append(chip(52, 596, 320, "持久化表总数", str(dataset["persistence"]["total"]), PALETTE["blue"]))
    body.append(chip(392, 596, 452, "为什么重要", "系统不是只做实时展示，还具备历史、规则、命令、会话、集群回放能力", PALETTE["green"]))
    body.append(chip(864, 596, 504, "代码来源", "DataStore / platform identity / control plane / goal runtime / cluster sqlite support", PALETTE["amber"]))
    return svg_frame("图 5  持久化数据资产分布", "从 SQLite 结构证明平台具备历史分析、治理审计、AI 会话和集群状态保存，而不是无状态 Demo。", 1420, 698, "".join(body))


def agent_chain_svg(dataset: dict) -> str:
    body = [
        card(54, 170, 248, 150, "server-agent", [f'Collectors {dataset["agent_chain"]["collectors"]}', f'Controllers {dataset["agent_chain"]["controllers"]}', "JobRuntime / RuntimeStore"], PALETTE["blue"]),
        card(356, 170, 252, 150, "Provider / AgentClient", ["HTTP local / remote", "SSH Linux", "current_provider / reconnect"], PALETTE["green"]),
        card(662, 170, 252, 150, "backend main loop", ["collect_agent_snapshot", "alert_engine", "scheduler", "ws broadcast"], PALETTE["amber"]),
        card(968, 170, 398, 150, "前端工作区", ["Dashboard / Governance / Energy", "Monitor / Alerts / AI", "按 scoped 数据消费"], PALETTE["cyan"]),
        arrow(302, 245, 356, 245, PALETTE["blue"]),
        arrow(608, 245, 662, 245, PALETTE["green"]),
        arrow(914, 245, 968, 245, PALETTE["amber"]),
        chip(54, 390, 270, "采集输出", "gpus / system / processes / training", PALETTE["blue"]),
        chip(344, 390, 270, "控制输出", "power-limit / task pause-resume-terminate", PALETTE["green"]),
        chip(634, 390, 350, "回传方式", "REST + WebSocket + scoped snapshot", PALETTE["amber"]),
        chip(1004, 390, 362, "部署含义", "支持本机 Agent、远程 Agent 和 SSH Linux 三类接入", PALETTE["cyan"]),
    ]
    return svg_frame("图 6  Agent 采集与回传链路", "第 4 章用这张图说明系统为什么能同时做实时采集、控制动作和多接入源导入。", 1420, 500, "".join(body))


def extension_map_svg(dataset: dict) -> str:
    modules = dataset["extensions"]["modules"]
    body = []
    for index, module in enumerate(modules):
        x = 56 + index * 448
        color = [PALETTE["blue"], PALETTE["green"], PALETTE["amber"]][index]
        body.append(card(x, 164, 392, 132, module["name"], [f'路由 {module["routes"]}', module["focus"]], color))
    body.append(card(56, 352, 620, 206, "控制能力前缀分布", [f'{item["name"]}: {item["value"]}' for item in dataset["extensions"]["capabilities"]], PALETTE["cyan"]))
    body.append(chip(714, 352, 280, "能力总数", str(dataset["extensions"]["total_capabilities"]), PALETTE["blue"]))
    body.append(chip(1014, 352, 350, "章节含义", "AI、Graph、Cluster 不是孤立 Demo，而是挂在统一平台能力目录上的扩展层", PALETTE["green"]))
    return svg_frame("图 7  智能、图谱与集群扩展能力", "用路由数与控制能力前缀证明项目并非单一治理页，而是主平台 + 扩展能力的复合系统。", 1420, 620, "".join(body))
