"""公平治理分析服务 - 面向多用户共享GPU场景的资源公平度与让路建议"""

from __future__ import annotations

import time
from collections import defaultdict
from datetime import datetime

from app.services.scheduler import get_time_period


BACKGROUND_PROCESS_NAMES = {
    "applicationframehost.exe",
    "crossdeviceresume.exe",
    "dwm.exe",
    "explorer.exe",
    "lockapp.exe",
    "msedge.exe",
    "msedgewebview2.exe",
    "onedrive.exe",
    "phoneexperiencehost.exe",
    "searchhost.exe",
    "shellexperiencehost.exe",
    "shellhost.exe",
    "startmenuexperiencehost.exe",
    "systemsettings.exe",
    "textinputhost.exe",
    "wechatappex.exe",
    "windowsterminal.exe",
    "chrome.exe",
}

BACKGROUND_COMMAND_KEYWORDS = (
    "--type=gpu-process",
    "--type=utility",
    "shell experiencehost",
    "startmenuexperiencehost",
    "searchhost.exe",
    "systemsettings.exe",
    "crossdeviceresume.exe",
    "lockapp.exe",
)


class GovernanceService:
    """计算用户公平度、占用集中度与建议让路任务"""

    def __init__(self, store, agent):
        self.store = store
        self.agent = agent

    def _to_int(self, value, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _level_label(level: str | None) -> str:
        return {
            "balanced": "均衡",
            "watch": "关注",
            "critical": "风险",
            "dominant": "主导",
        }.get(level or "", level or "未知")

    @staticmethod
    def _role_label(role: str | None) -> str:
        return {
            "protected": "保护用户",
            "member": "普通用户",
            "restricted": "受限用户",
        }.get(role or "", role or "未设置")

    async def get_fairness_report(self) -> dict:
        gpus = await self.agent.get_all_gpus() or []
        processes = await self.agent.get_processes() or []
        priorities = await self.store.get_all_task_priorities()
        history_stats = await self.store.get_user_stats()
        governance_rules = await self.store.get_user_governance_rules()
        history_by_user = {
            row.get("username") or "unknown": row
            for row in history_stats
        }

        enriched_processes = []
        for proc in processes:
            cloned = dict(proc)
            cloned["priority"] = priorities.get(
                cloned.get("pid"),
                cloned.get("priority", "normal"),
            )
            enriched_processes.append(cloned)

        governable_processes = [
            proc for proc in enriched_processes
            if self._is_governable_process(proc)
        ]

        users = self._build_user_profiles(
            governable_processes,
            gpus,
            history_by_user,
            governance_rules,
        )
        overview = self._build_overview(users, gpus, governable_processes)
        overview["raw_process_count"] = len(enriched_processes)
        overview["governable_process_count"] = len(governable_processes)
        yield_candidates = self._build_yield_candidates(governable_processes, users, overview)
        overview["reclaimable_candidates"] = len(yield_candidates)

        return {
            "overview": overview,
            "users": users,
            "yield_candidates": yield_candidates,
            "recommendations": self._build_recommendations(users, overview, yield_candidates),
        }

    async def generate_export_report(self, fmt: str = "markdown") -> str:
        """导出公平治理与额度规则报告"""
        report = await self.get_fairness_report()
        overview = report["overview"]
        users = report["users"]
        yield_candidates = report["yield_candidates"]
        recommendations = report["recommendations"]
        stored_rules = await self.store.get_user_governance_rules()
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        level_label = self._level_label(overview.get("level"))

        md = f"""# GPU 共享治理报告

> 生成时间：{ts}
> 数据来源：本机实时采集
> 治理等级：{level_label}

---

## 一、治理总览

| 指标 | 数值 |
|------|------|
| 公平治理指数 | {overview.get('fairness_index', 0)} |
| 风险级别 | {level_label} |
| 活跃用户数 | {overview.get('active_users', 0)} |
| GPU 数量 | {overview.get('gpu_count', 0)} |
| 可治理任务数 | {overview.get('total_tasks', 0)} |
| 原始 GPU 进程数 | {overview.get('raw_process_count', 0)} |
| 可治理进程数 | {overview.get('governable_process_count', 0)} |
| 主导用户 | {overview.get('dominant_user') or '无明显集中'} |
| 规则违规用户数 | {overview.get('violation_user_count', 0)} |
| 规则违规总条数 | {overview.get('violation_count', 0)} |
| 建议让路任务数 | {overview.get('reclaimable_candidates', 0)} |

## 二、平台判断

- {overview.get('summary', '当前暂无治理结论')}
"""

        if recommendations:
            for item in recommendations:
                md += f"- {item}\n"

        md += "\n## 三、活跃用户画像\n\n"
        md += "| 用户 | 角色 | 任务数 | GPU数 | 显存占比 | 功率占比 | 公平分 | 违规数 | 允许让路 |\n"
        md += "|------|------|--------|-------|----------|----------|--------|--------|----------|\n"
        for user in users:
            rule = user.get("governance_rule") or {}
            md += (
                f"| {user.get('username', 'unknown')} "
                f"| {self._role_label(rule.get('role'))} "
                f"| {user.get('task_count', 0)} "
                f"| {user.get('gpu_count', 0)} "
                f"| {user.get('memory_share_pct', 0)}% "
                f"| {user.get('power_share_pct', 0)}% "
                f"| {user.get('fairness_score', 0)} "
                f"| {user.get('violation_count', 0)} "
                f"| {'允许' if rule.get('allow_preempt', True) else '保护'} |\n"
            )

        violated_users = [user for user in users if user.get("violations")]
        if violated_users:
            md += "\n## 四、违规明细\n\n"
            for user in violated_users:
                md += f"- **{user.get('username', 'unknown')}**："
                md += "；".join(user.get("violations", []))
                md += "\n"

        md += "\n## 五、已配置额度规则\n\n"
        if stored_rules:
            md += "| 用户 | 角色 | 任务额度 | GPU额度 | 显存额度 | 允许让路 | 备注 |\n"
            md += "|------|------|----------|---------|----------|----------|------|\n"
            for username, rule in sorted(stored_rules.items()):
                md += (
                    f"| {username} "
                    f"| {self._role_label(rule.get('role'))} "
                    f"| {rule.get('max_tasks', 4)} "
                    f"| {rule.get('max_gpu_count', 1)} "
                    f"| {rule.get('max_memory_gb', 8)}GB "
                    f"| {'允许' if rule.get('allow_preempt', True) else '保护'} "
                    f"| {rule.get('note') or '-'} |\n"
                )
        else:
            md += "- 当前尚未配置持久化额度规则，平台使用默认治理阈值。\n"

        md += "\n## 六、建议让路任务\n\n"
        if yield_candidates:
            md += "| PID | 用户 | GPU | 优先级 | 让路分 | 原因 |\n"
            md += "|-----|------|-----|--------|--------|------|\n"
            for item in yield_candidates:
                md += (
                    f"| {item.get('pid', '-')} "
                    f"| {item.get('username', 'unknown')} "
                    f"| {item.get('gpu_index', '-')} "
                    f"| {item.get('priority', 'normal')} "
                    f"| {item.get('yield_score', 0)} "
                    f"| {item.get('yield_reason', '-')} |\n"
                )
        else:
            md += "- 当前没有需要优先让路的任务。\n"

        md += "\n---\n\n"
        md += "*报告由 GPU 共享治理平台自动生成，可用于汇报、答辩与治理复盘。*\n"

        if fmt == "html":
            return self._markdown_to_simple_html(md, title="GPU 共享治理报告")
        return md

    def _is_governable_process(self, proc: dict) -> bool:
        priority = proc.get("priority", "normal")
        if priority in {"urgent", "deferrable"}:
            return True

        gpu_memory_used = self._to_int(proc.get("gpu_memory_used"), 0)
        if gpu_memory_used >= 256 * 1024 * 1024:
            return True

        username = (proc.get("username") or "").lower()
        if username.startswith("window manager\\"):
            return False

        name = (proc.get("name") or "").lower()
        command = (proc.get("command") or "").lower()
        if name in BACKGROUND_PROCESS_NAMES:
            return False
        if any(keyword in command for keyword in BACKGROUND_COMMAND_KEYWORDS):
            return False

        return True

    def _build_user_profiles(
        self,
        processes: list[dict],
        gpus: list[dict],
        history_by_user: dict[str, dict],
        governance_rules: dict[str, dict],
    ) -> list[dict]:
        now = time.time()
        grouped: dict[str, dict] = {}
        gpu_process_map: dict[int, list[dict]] = defaultdict(list)

        for proc in processes:
            gpu_index = self._to_int(proc.get("gpu_index"), -1)
            if gpu_index >= 0:
                gpu_process_map[gpu_index].append(proc)

            username = proc.get("username") or "unknown"
            if username not in grouped:
                grouped[username] = {
                    "username": username,
                    "task_count": 0,
                    "gpu_indices": set(),
                    "total_memory": 0,
                    "estimated_power": 0.0,
                    "urgent_count": 0,
                    "normal_count": 0,
                    "deferrable_count": 0,
                    "earliest_start": history_by_user.get(username, {}).get(
                        "earliest_start",
                        proc.get("create_time", now),
                    ) or now,
                }

            item = grouped[username]
            item["task_count"] += 1
            item["gpu_indices"].add(gpu_index)
            item["total_memory"] += int(proc.get("gpu_memory_used", 0) or 0)
            priority = proc.get("priority", "normal")
            if priority == "urgent":
                item["urgent_count"] += 1
            elif priority == "deferrable":
                item["deferrable_count"] += 1
            else:
                item["normal_count"] += 1
            item["earliest_start"] = min(
                item["earliest_start"],
                history_by_user.get(username, {}).get("earliest_start", now) or now,
                proc.get("create_time", now) or now,
            )

        for gpu in gpus:
            gpu_index = self._to_int(gpu.get("index"), -1)
            gpu_processes = gpu_process_map.get(gpu_index, [])
            if not gpu_processes:
                continue

            total_gpu_memory = sum(
                max(1, int(proc.get("gpu_memory_used", 0) or 0))
                for proc in gpu_processes
            )
            if total_gpu_memory <= 0:
                total_gpu_memory = len(gpu_processes)

            gpu_power = float(gpu.get("power_usage", 0) or 0)
            for proc in gpu_processes:
                username = proc.get("username") or "unknown"
                memory_weight = max(1, int(proc.get("gpu_memory_used", 0) or 0))
                grouped[username]["estimated_power"] += gpu_power * (memory_weight / total_gpu_memory)

        raw_total_memory = sum(item["total_memory"] for item in grouped.values())
        total_memory = raw_total_memory or sum(max(1, item["task_count"]) for item in grouped.values()) or 1
        total_tasks = sum(item["task_count"] for item in grouped.values()) or 1
        total_power = sum(item["estimated_power"] for item in grouped.values()) or 1.0
        user_count = max(1, len(grouped))
        ideal_share_pct = 100 / user_count

        users = []
        for item in grouped.values():
            memory_basis = item["total_memory"] if raw_total_memory > 0 else max(1, item["task_count"])
            memory_share_pct = memory_basis / total_memory * 100
            power_share_pct = item["estimated_power"] / total_power * 100
            task_share_pct = item["task_count"] / total_tasks * 100
            runtime_hours = max(0.0, (now - item["earliest_start"]) / 3600)
            effective_share_pct = max(memory_share_pct, power_share_pct, task_share_pct)

            share_overuse = max(0.0, memory_share_pct - ideal_share_pct)
            power_overuse = max(0.0, power_share_pct - ideal_share_pct)
            task_overuse = max(0.0, task_share_pct - ideal_share_pct)
            runtime_penalty = min(18.0, runtime_hours * (0.9 if item["urgent_count"] else 1.2))
            deferrable_penalty = item["deferrable_count"] * 4.0 if share_overuse > 0 else item["deferrable_count"] * 2.0
            urgent_credit = min(15.0, item["urgent_count"] * 5.0)

            fairness_score = max(
                0.0,
                100.0
                - share_overuse * 1.5
                - power_overuse * 1.1
                - task_overuse * 0.8
                - runtime_penalty
                - deferrable_penalty
                + urgent_credit,
            )

            if fairness_score >= 80:
                level = "balanced"
                action = "维持现状，继续观测"
            elif fairness_score >= 60:
                level = "watch"
                action = "限制新增可延迟任务，关注让路窗口"
            else:
                level = "dominant"
                action = "优先收缩可延迟任务，并考虑暂停部分普通任务"

            rule = governance_rules.get(item["username"])
            violations = []
            gpu_count = len([idx for idx in item["gpu_indices"] if idx >= 0])
            total_memory_gb = item["total_memory"] / 1073741824 if item["total_memory"] else 0.0
            if rule:
                if item["task_count"] > rule.get("max_tasks", 4):
                    violations.append(
                        f"任务数 {item['task_count']} 超过额度 {rule.get('max_tasks', 4)}"
                    )
                if gpu_count > rule.get("max_gpu_count", 1):
                    violations.append(
                        f"占用 GPU 数 {gpu_count} 超过额度 {rule.get('max_gpu_count', 1)}"
                    )
                if total_memory_gb > float(rule.get("max_memory_gb", 8)):
                    violations.append(
                        f"显存占用 {total_memory_gb:.1f}GB 超过额度 {float(rule.get('max_memory_gb', 8)):.1f}GB"
                    )
                if violations:
                    level = "critical" if level == "balanced" else level
                    action = "已触发用户额度规则，建议优先约束该用户的可延迟/普通任务"

            users.append({
                "username": item["username"],
                "gpu_count": gpu_count,
                "gpu_indices": sorted(idx for idx in item["gpu_indices"] if idx >= 0),
                "task_count": item["task_count"],
                "total_memory": item["total_memory"],
                "estimated_power": round(item["estimated_power"], 1),
                "memory_share_pct": round(memory_share_pct, 1),
                "power_share_pct": round(power_share_pct, 1),
                "task_share_pct": round(task_share_pct, 1),
                "effective_share_pct": round(effective_share_pct, 1),
                "runtime_hours": round(runtime_hours, 1),
                "urgent_count": item["urgent_count"],
                "normal_count": item["normal_count"],
                "deferrable_count": item["deferrable_count"],
                "fairness_score": round(fairness_score, 1),
                "level": level,
                "recommended_action": action,
                "share_overuse_pct": round(share_overuse, 1),
                "governance_rule": rule,
                "violations": violations,
                "violation_count": len(violations),
            })

        users.sort(
            key=lambda item: (
                item["fairness_score"],
                -item["memory_share_pct"],
                -item["task_count"],
            )
        )
        return users

    def _distribution_gap(self, values: list[float], ideal_share_pct: float) -> float:
        if not values:
            return 0.0
        return sum(abs(value - ideal_share_pct) for value in values) / 200

    def _build_overview(
        self,
        users: list[dict],
        gpus: list[dict],
        processes: list[dict],
    ) -> dict:
        active_users = len(users)
        if not users:
            return {
                "fairness_index": 100.0,
                "level": "balanced",
                "summary": "当前没有可治理的训练型 GPU 任务，系统以监测和预算观察为主。",
                "active_users": 0,
                "total_tasks": len(processes),
                "gpu_count": len(gpus),
                "ideal_share_pct": 0.0,
                "highest_share_pct": 0.0,
                "dominant_user": None,
                "watch_users": 0,
                "time_period": get_time_period(),
            }

        ideal_share_pct = round(100 / active_users, 1) if active_users else 0.0
        memory_gap = self._distribution_gap(
            [user["memory_share_pct"] for user in users],
            ideal_share_pct,
        )
        power_gap = self._distribution_gap(
            [user["power_share_pct"] for user in users],
            ideal_share_pct,
        )
        task_gap = self._distribution_gap(
            [user["task_share_pct"] for user in users],
            ideal_share_pct,
        )

        highest_share_pct = round(
            max((user["effective_share_pct"] for user in users), default=0.0),
            1,
        )
        fairness_index = max(
            0.0,
            100.0
            - (memory_gap * 35 + power_gap * 25 + task_gap * 35)
            - max(0.0, highest_share_pct - ideal_share_pct) * 0.55,
        )
        fairness_index = round(fairness_index, 1)
        dominant_user = next(
            (
                user["username"]
                for user in sorted(users, key=lambda item: item["effective_share_pct"], reverse=True)
                if user["effective_share_pct"] > ideal_share_pct + 12
            ),
            None,
        )

        violation_user_count = sum(1 for user in users if user["violation_count"] > 0)
        violation_count = sum(user["violation_count"] for user in users)

        if violation_user_count > 0:
            level = "critical"
            summary = f"已有 {violation_user_count} 个用户触发额度规则，建议优先执行治理。"
        elif fairness_index >= 85:
            level = "balanced"
            summary = "当前共享较均衡，平台以监测和轻度约束为主。"
        elif fairness_index >= 65:
            level = "watch"
            summary = "部分用户已出现占用偏高，建议限制可延迟任务继续扩张。"
        else:
            level = "critical"
            summary = "资源集中度偏高，建议立即执行让路治理与优先级约束。"

        return {
            "fairness_index": fairness_index,
            "level": level,
            "summary": summary,
            "active_users": active_users,
            "total_tasks": len(processes),
            "gpu_count": len(gpus),
            "ideal_share_pct": ideal_share_pct,
            "highest_share_pct": highest_share_pct,
            "dominant_user": dominant_user,
            "watch_users": sum(1 for user in users if user["level"] != "balanced"),
            "violation_user_count": violation_user_count,
            "violation_count": violation_count,
            "time_period": get_time_period(),
        }

    def _build_recommendations(
        self,
        users: list[dict],
        overview: dict,
        yield_candidates: list[dict],
    ) -> list[str]:
        recommendations: list[str] = []

        if not users:
            return ["当前没有可治理的训练型 GPU 任务，平台以监测、预算观察和等待真实负载为主。"]

        dominant_user = overview.get("dominant_user")
        highest_share_pct = overview.get("highest_share_pct", 0)
        if dominant_user:
            recommendations.append(
                f"用户 {dominant_user} 当前显存占用最高，约 {highest_share_pct:.1f}%，建议优先约束其可延迟任务。"
            )

        users_with_rule_violation = [user for user in users if user["violation_count"] > 0]
        if users_with_rule_violation:
            top_user = users_with_rule_violation[0]
            recommendations.append(
                f"用户 {top_user['username']} 已触发 {top_user['violation_count']} 条额度规则，需要优先治理。"
            )

        if overview.get("level") == "critical":
            recommendations.append("公平指数已进入风险区，建议在任务页优先处理让路候选任务。")
        elif overview.get("level") == "watch":
            recommendations.append("当前资源开始向少数用户集中，可通过额度提醒和优先级治理提前干预。")
        else:
            recommendations.append("当前共享状态较稳定，可继续积累用户治理数据与策略回放记录。")

        if yield_candidates:
            top_candidate = yield_candidates[0]
            recommendations.append(
                f"首个建议让路任务为 PID {top_candidate['pid']}（{top_candidate['username']}），原因：{top_candidate['yield_reason']}"
            )

        return recommendations[:3]

    def _build_yield_candidates(
        self,
        processes: list[dict],
        users: list[dict],
        overview: dict,
    ) -> list[dict]:
        if not processes or not users:
            return []

        users_by_name = {user["username"]: user for user in users}
        candidates = []
        for proc in processes:
            priority = proc.get("priority", "normal")
            if priority == "urgent":
                continue

            user = users_by_name.get(proc.get("username") or "unknown")
            if not user:
                continue
            if user["level"] == "balanced" and overview.get("level") == "balanced":
                continue
            if user.get("governance_rule") and not user["governance_rule"].get("allow_preempt", True):
                continue

            priority_score = {
                "deferrable": 100,
                "normal": 55,
                "urgent": 0,
            }.get(priority, 40)
            share_score = user["share_overuse_pct"] * 2.2
            memory_score = min(30.0, (proc.get("gpu_memory_used", 0) or 0) / 1073741824 * 4.0)
            runtime_score = min(20.0, user["runtime_hours"])
            quota_score = user.get("violation_count", 0) * 28.0
            yield_score = round(priority_score + share_score + memory_score + runtime_score + quota_score, 1)

            reason_parts = []
            reason_parts.append("可延迟任务" if priority == "deferrable" else "普通任务")
            if user["share_overuse_pct"] > 0:
                reason_parts.append(f"用户占用超出理想份额 {user['share_overuse_pct']:.1f}%")
            if user.get("violations"):
                reason_parts.append("触发用户额度规则")
            if (proc.get("gpu_memory_used", 0) or 0) > 0:
                reason_parts.append(f"显存占用约 {(proc.get('gpu_memory_used', 0) or 0) / 1073741824:.1f}GB")

            candidates.append({
                "pid": proc.get("pid"),
                "username": proc.get("username", "unknown"),
                "gpu_index": proc.get("gpu_index"),
                "name": proc.get("name", ""),
                "priority": priority,
                "gpu_memory_used": proc.get("gpu_memory_used", 0),
                "yield_score": yield_score,
                "yield_reason": "，".join(reason_parts),
                "command": proc.get("command", ""),
            })

        candidates.sort(key=lambda item: (-item["yield_score"], item["pid"] or 0))
        return candidates[:5]

    @staticmethod
    def _markdown_to_simple_html(md: str, title: str = "治理报告") -> str:
        """简易 Markdown 转 HTML，避免增加额外依赖"""
        import html
        import re

        lines = md.split("\n")
        html_lines = [
            "<!DOCTYPE html><html><head><meta charset=\"utf-8\">",
            f"<title>{html.escape(title)}</title>",
            "<style>body{font-family:\"Microsoft YaHei\",sans-serif;max-width:980px;margin:40px auto;padding:0 20px;color:#333;line-height:1.8}",
            "table{border-collapse:collapse;width:100%;margin:16px 0}th,td{border:1px solid #ddd;padding:8px 12px;text-align:left;vertical-align:top}",
            "th{background:#f6f7f9}h1{color:#1f2937;border-bottom:2px solid #3A5F4B;padding-bottom:8px}",
            "h2{color:#3A5F4B;margin-top:32px}blockquote{border-left:3px solid #3A5F4B;padding-left:16px;color:#666;margin:16px 0}",
            "hr{border:none;border-top:1px solid #eee;margin:24px 0}</style></head><body>",
        ]
        in_table = False
        for line in lines:
            stripped = line.strip()
            if not stripped:
                if in_table:
                    html_lines.append("</table>")
                    in_table = False
                html_lines.append("")
                continue

            if stripped.startswith("# "):
                html_lines.append(f"<h1>{html.escape(stripped[2:])}</h1>")
            elif stripped.startswith("## "):
                html_lines.append(f"<h2>{html.escape(stripped[3:])}</h2>")
            elif stripped.startswith("> "):
                html_lines.append(f"<blockquote>{html.escape(stripped[2:])}</blockquote>")
            elif stripped == "---":
                html_lines.append("<hr>")
            elif stripped.startswith("| ") and "---" in stripped:
                continue
            elif stripped.startswith("| "):
                cells = [html.escape(c.strip()) for c in stripped.split("|")[1:-1]]
                if not in_table:
                    html_lines.append("<table>")
                    in_table = True
                    html_lines.append("<tr>" + "".join(f"<th>{cell}</th>" for cell in cells) + "</tr>")
                else:
                    html_lines.append("<tr>" + "".join(f"<td>{cell}</td>" for cell in cells) + "</tr>")
            elif stripped.startswith("- "):
                content = html.escape(stripped[2:])
                content = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", content)
                html_lines.append(f"<p>• {content}</p>")
            elif stripped.startswith("*") and stripped.endswith("*"):
                html_lines.append(f"<p><em>{html.escape(stripped.strip('*'))}</em></p>")
            else:
                html_lines.append(f"<p>{html.escape(stripped)}</p>")
        if in_table:
            html_lines.append("</table>")
        html_lines.append("</body></html>")
        return "\n".join(html_lines)
