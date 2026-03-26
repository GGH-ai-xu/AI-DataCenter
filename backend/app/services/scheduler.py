"""调度引擎 - 规则引擎 + LLM混合调度"""

import json
import time
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

PRIORITY_ORDER = {
    "deferrable": 0,
    "normal": 1,
    "urgent": 2,
}


def get_time_period() -> str:
    """获取当前时段分类"""
    hour = datetime.now().hour
    if 9 <= hour < 12 or 14 <= hour < 18:
        return "peak"  # 高峰期
    elif 22 <= hour or hour < 6:
        return "valley"  # 低谷期
    else:
        return "normal"  # 平峰期


def get_time_period_label() -> str:
    labels = {"peak": "用电高峰期", "valley": "用电低谷期", "normal": "平峰期"}
    return labels.get(get_time_period(), "平峰期")


class SchedulerEngine:
    """调度引擎 - 负责生成和执行调度策略"""

    def __init__(
        self,
        agent_client,
        data_store,
        llm_service=None,
        budget_limit_watts: int = 1200,
        budget_enabled: bool = False,
    ):
        self.agent = agent_client
        self.store = data_store
        self.llm = llm_service
        self._last_schedule_time = 0
        self._schedule_interval = 300  # 5分钟调度一次
        self._auto_enabled = False
        self._last_actions = None       # D4: 上次调度动作
        self._last_gpu_state = None     # D4: 上次调度前GPU状态
        self._last_evaluation = None    # D4: 最近一次AI评估结果
        self._budget_limit_watts = max(400, int(budget_limit_watts))
        self._budget_enabled = budget_enabled
        self._budget_managed_limits: dict[int, int] = {}
        self._last_budget_actions: list[dict] = []

    @property
    def auto_enabled(self) -> bool:
        return self._auto_enabled

    @property
    def budget_enabled(self) -> bool:
        return self._budget_enabled

    @property
    def budget_limit_watts(self) -> int:
        return self._budget_limit_watts

    def set_auto(self, enabled: bool):
        self._auto_enabled = enabled
        logger.info(f"自动调度已{'启用' if enabled else '禁用'}")

    def configure_budget(self, enabled: bool, total_power_budget: int):
        self._budget_enabled = enabled
        self._budget_limit_watts = max(400, int(total_power_budget))
        logger.info(
            "总功率预算已%s，预算值=%sW",
            "启用" if enabled else "禁用",
            self._budget_limit_watts,
        )

    def clear_managed_gpu(self, gpu_index: int):
        self._budget_managed_limits.pop(gpu_index, None)

    async def _attach_priorities(self, processes: list[dict]) -> list[dict]:
        priorities = await self.store.get_all_task_priorities()
        enriched = []
        for proc in processes:
            cloned = dict(proc)
            cloned["priority"] = priorities.get(
                cloned.get("pid"),
                cloned.get("priority", "normal"),
            )
            enriched.append(cloned)
        return enriched

    def _priority_rank(self, priority: str) -> int:
        return PRIORITY_ORDER.get(priority or "normal", PRIORITY_ORDER["normal"])

    def _build_budget_profiles(
        self, gpus: list[dict], processes: list[dict]
    ) -> list[dict]:
        process_by_gpu: dict[int, list[dict]] = {}
        for proc in processes:
            gpu_index = proc.get("gpu_index", -1)
            if gpu_index < 0:
                continue
            process_by_gpu.setdefault(gpu_index, []).append(proc)

        profiles = []
        for gpu in gpus:
            idx = gpu.get("index", 0)
            gpu_processes = process_by_gpu.get(idx, [])
            priorities = [p.get("priority", "normal") for p in gpu_processes]
            lowest_priority = min(
                priorities,
                key=self._priority_rank,
            ) if priorities else "normal"
            highest_priority = max(
                priorities,
                key=self._priority_rank,
            ) if priorities else "normal"

            profiles.append({
                "index": idx,
                "power_usage": float(gpu.get("power_usage", 0) or 0),
                "power_limit": int(round(gpu.get("power_limit", 350) or 350)),
                "gpu_utilization": int(gpu.get("gpu_utilization", 0) or 0),
                "processes": gpu_processes,
                "process_count": len(gpu_processes),
                "lowest_priority": lowest_priority,
                "highest_priority": highest_priority,
            })
        return profiles

    def _suggest_budget_limit(self, profile: dict) -> Optional[int]:
        current_limit = int(profile["power_limit"])
        current_power = float(profile["power_usage"])
        util = int(profile["gpu_utilization"])
        lowest_priority = profile["lowest_priority"]
        has_urgent = self._priority_rank(profile["highest_priority"]) >= PRIORITY_ORDER["urgent"]

        if has_urgent and util >= 85:
            return None

        if lowest_priority == "deferrable":
            floor = 150
            ratio = 0.72 if util < 50 else 0.80
        elif lowest_priority == "normal":
            floor = 180
            ratio = 0.82 if util < 65 else 0.88
        else:
            floor = 220
            ratio = 0.90 if util < 70 else 0.94

        target = int(max(floor, min(current_limit, current_power * ratio)))
        if target >= current_limit - 5:
            return None
        return min(current_limit, max(100, target))

    def _estimate_pause_saving(self, profile: dict, priority: str) -> float:
        base = float(profile.get("power_usage", 0))
        if priority == "deferrable":
            return max(40.0, base * 0.35)
        return max(25.0, base * 0.2)

    def _build_restore_actions(self, gpus: list[dict]) -> list[dict]:
        actions = []
        for gpu in gpus:
            idx = gpu.get("index", 0)
            if idx not in self._budget_managed_limits:
                continue
            original = int(self._budget_managed_limits[idx])
            current_limit = int(round(gpu.get("power_limit", original) or original))
            if current_limit >= original:
                self._budget_managed_limits.pop(idx, None)
                continue
            actions.append({
                "action": "set_power_limit",
                "target": {"gpu_index": idx, "power_limit": original},
                "reason": (
                    f"集群总功率已回落到预算安全区间，恢复GPU{idx}功耗上限到"
                    f"{original}W"
                ),
                "rule": "restore_budget_cap",
            })
        return actions

    async def run_budget_schedule(
        self, gpus: list[dict], processes: list[dict]
    ) -> list[dict]:
        if not gpus:
            return []

        current_total_power = sum(float(g.get("power_usage", 0) or 0) for g in gpus)
        restore_margin = max(60, int(self._budget_limit_watts * 0.08))

        if not self._budget_enabled:
            actions = self._build_restore_actions(gpus)
            self._last_budget_actions = actions
            return actions

        if current_total_power <= self._budget_limit_watts - restore_margin:
            actions = self._build_restore_actions(gpus)
            self._last_budget_actions = actions
            return actions

        excess = current_total_power - self._budget_limit_watts
        if excess <= 0:
            self._last_budget_actions = []
            return []

        enriched_processes = await self._attach_priorities(processes)
        profiles = self._build_budget_profiles(gpus, enriched_processes)

        actions: list[dict] = []
        for profile in sorted(
            profiles,
            key=lambda item: (
                self._priority_rank(item["lowest_priority"]),
                item["gpu_utilization"],
                -item["power_usage"],
            ),
        ):
            target = self._suggest_budget_limit(profile)
            if target is None:
                continue

            saving = profile["power_usage"] - target
            if saving < 10:
                continue

            actions.append({
                "action": "set_power_limit",
                "target": {"gpu_index": profile["index"], "power_limit": target},
                "reason": (
                    f"集群总功率{current_total_power:.0f}W已超出预算"
                    f"{self._budget_limit_watts}W，优先压缩GPU{profile['index']} "
                    f"到{target}W以保障总功率预算"
                ),
                "rule": "power_budget_cap",
                "original_power_limit": profile["power_limit"],
                "estimated_saving": round(saving, 1),
            })
            excess -= saving
            if excess <= 0:
                break

        if excess > 0:
            gpu_profiles = {profile["index"]: profile for profile in profiles}
            paused_pids: set[int] = set()
            pause_candidates = sorted(
                (
                    proc for proc in enriched_processes
                    if self._priority_rank(proc.get("priority", "normal")) < PRIORITY_ORDER["urgent"]
                ),
                key=lambda proc: (
                    self._priority_rank(proc.get("priority", "normal")),
                    gpu_profiles.get(proc.get("gpu_index", -1), {}).get("gpu_utilization", 100),
                    -gpu_profiles.get(proc.get("gpu_index", -1), {}).get("power_usage", 0),
                ),
            )
            for proc in pause_candidates:
                pid = proc.get("pid", 0)
                if pid <= 0 or pid in paused_pids:
                    continue
                paused_pids.add(pid)
                gpu_index = proc.get("gpu_index", -1)
                priority = proc.get("priority", "normal")
                profile = gpu_profiles.get(gpu_index, {})
                estimated_saving = self._estimate_pause_saving(profile, priority)
                actions.append({
                    "action": "pause_task",
                    "target": {"pid": pid},
                    "reason": (
                        f"集群总功率仍超预算，暂停{priority}优先级任务 {pid} "
                        f"以释放GPU{gpu_index}负载"
                    ),
                    "rule": "power_budget_pause",
                    "estimated_saving": round(estimated_saving, 1),
                })
                excess -= estimated_saving
                if excess <= 0:
                    break

        self._last_budget_actions = actions
        return actions

    def get_budget_status(self, gpus: list[dict]) -> dict:
        current_total = sum(float(g.get("power_usage", 0) or 0) for g in gpus)
        remaining = self._budget_limit_watts - current_total
        usage_pct = (
            current_total / self._budget_limit_watts * 100
            if self._budget_limit_watts > 0 else 0
        )
        return {
            "enabled": self._budget_enabled,
            "total_power_budget": self._budget_limit_watts,
            "current_total_power": round(current_total, 1),
            "remaining_power": round(remaining, 1),
            "usage_pct": round(usage_pct, 1),
            "is_exceeded": current_total > self._budget_limit_watts,
            "managed_gpu_count": len(self._budget_managed_limits),
            "last_actions": self._last_budget_actions[:5],
        }

    async def run_rules(self, gpus: list[dict], processes: list[dict]) -> list[dict]:
        """规则引擎 - 硬性规则，立即执行"""
        actions = []
        for gpu in gpus:
            idx = gpu.get("index", 0)
            temp = gpu.get("temperature", 0)

            # 规则1：温度超90°C，紧急降频到200W
            if temp >= 90:
                actions.append({
                    "action": "set_power_limit",
                    "target": {"gpu_index": idx, "power_limit": 200},
                    "reason": f"GPU{idx}温度{temp}°C超过90°C临界值，紧急降频",
                    "rule": "emergency_thermal",
                })

            # 规则2：温度超85°C，降频到250W
            elif temp >= 85:
                actions.append({
                    "action": "set_power_limit",
                    "target": {"gpu_index": idx, "power_limit": 250},
                    "reason": f"GPU{idx}温度{temp}°C偏高，预防性降频",
                    "rule": "thermal_warning",
                })

        return actions

    async def run_ai_schedule(
        self, gpus: list[dict], processes: list[dict]
    ) -> Optional[dict]:
        """AI调度 - LLM生成优化策略"""
        if not self.llm:
            return None

        # 补充任务优先级信息
        processes = await self._attach_priorities(processes)

        time_period = get_time_period_label()
        strategy = await self.llm.generate_schedule(gpus, processes, time_period)
        return strategy

    async def execute_actions(self, actions: list[dict]) -> list[dict]:
        """执行调度动作列表"""
        results = []
        for action in actions:
            act = action.get("action")
            target = action.get("target", {})
            reason = action.get("reason", "")
            result = {"action": act, "reason": reason, "success": False}

            # 校验动作参数合法性
            if act == "set_power_limit":
                gpu_idx = target.get("gpu_index")
                power = target.get("power_limit")
                if not isinstance(gpu_idx, int) or gpu_idx < 0:
                    result["error"] = f"无效GPU索引: {gpu_idx}"
                    results.append(result)
                    continue
                if not isinstance(power, (int, float)) or not (100 <= power <= 350):
                    result["error"] = f"功耗限制超出安全范围(100-350W): {power}"
                    results.append(result)
                    continue
            elif act in ("pause_task", "resume_task"):
                pid = target.get("pid")
                if not isinstance(pid, int) or pid <= 0:
                    result["error"] = f"无效PID: {pid}"
                    results.append(result)
                    continue
            else:
                result["error"] = f"未知动作类型: {act}"
                results.append(result)
                continue

            try:
                if act == "set_power_limit":
                    resp = await self.agent.set_power_limit(
                        target["gpu_index"], target["power_limit"]
                    )
                    result["success"] = resp.get("success", False)
                elif act == "pause_task":
                    resp = await self.agent.pause_task(target["pid"])
                    result["success"] = resp.get("success", False)
                elif act == "resume_task":
                    resp = await self.agent.resume_task(target["pid"])
                    result["success"] = resp.get("success", False)

                # 记录日志
                await self.store.save_schedule_log(
                    act, json.dumps(target), reason,
                    "success" if result["success"] else "failed"
                )

                if result["success"] and act == "set_power_limit":
                    rule = action.get("rule")
                    gpu_index = target["gpu_index"]
                    if rule == "power_budget_cap":
                        original = action.get("original_power_limit")
                        if isinstance(original, (int, float)):
                            self._budget_managed_limits[gpu_index] = int(round(original))
                    elif rule == "restore_budget_cap":
                        self._budget_managed_limits.pop(gpu_index, None)
            except Exception as e:
                result["error"] = str(e)
                logger.error(f"执行调度动作失败: {act} - {e}")

            results.append(result)
        return results

    async def evaluate_last_schedule(self, current_gpus: list[dict]) -> Optional[dict]:
        """D4: 评估上次调度效果"""
        if not self.llm or not self._last_actions or not self._last_gpu_state:
            return None
        try:
            from app.services.llm import EVALUATE_PROMPT
            context = EVALUATE_PROMPT.format(
                actions=json.dumps(self._last_actions, indent=2, ensure_ascii=False),
                before_state=json.dumps(self._last_gpu_state, indent=2, ensure_ascii=False),
                after_state=json.dumps(current_gpus, indent=2, ensure_ascii=False),
            )
            result = await self.llm.evaluate_schedule(context)
            if result:
                self._last_evaluation = result
                # 记录评估到调度日志
                await self.store.save_schedule_log(
                    "ai_evaluate", json.dumps({"evaluation": result}),
                    result.get("verdict", ""), "success"
                )
            return result
        except Exception as e:
            logger.warning(f"AI调度评估失败: {e}")
            return None

    async def tick(self, gpus: list[dict], processes: list[dict]) -> dict:
        """定期调度tick - 被数据采集循环调用"""
        result = {"rule_actions": [], "budget_actions": [], "ai_actions": [], "executed": []}

        # D4: 评估上次调度（在新调度前执行）
        if self._last_actions and self.llm:
            evaluation = await self.evaluate_last_schedule(gpus)
            if evaluation:
                result["evaluation"] = evaluation

        # 始终执行规则引擎
        rule_actions = await self.run_rules(gpus, processes)
        if rule_actions:
            result["rule_actions"] = rule_actions
            executed = await self.execute_actions(rule_actions)
            result["executed"].extend(executed)

        budget_actions = await self.run_budget_schedule(gpus, processes)
        if budget_actions:
            result["budget_actions"] = budget_actions
            executed = await self.execute_actions(budget_actions)
            result["executed"].extend(executed)

        # AI调度（有间隔控制）
        now = time.time()
        if (self._auto_enabled and self.llm and
                now - self._last_schedule_time >= self._schedule_interval):
            self._last_schedule_time = now
            # D4: 保存调度前状态
            self._last_gpu_state = [dict(g) for g in gpus]
            strategy = await self.run_ai_schedule(gpus, processes)
            if strategy and "actions" in strategy:
                result["ai_actions"] = strategy["actions"]
                self._last_actions = strategy["actions"]
                executed = await self.execute_actions(strategy["actions"])
                result["executed"].extend(executed)

        return result
