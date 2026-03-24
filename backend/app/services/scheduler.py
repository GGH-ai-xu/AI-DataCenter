"""调度引擎 - 规则引擎 + LLM混合调度"""

import json
import time
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


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

    def __init__(self, agent_client, data_store, llm_service=None):
        self.agent = agent_client
        self.store = data_store
        self.llm = llm_service
        self._last_schedule_time = 0
        self._schedule_interval = 300  # 5分钟调度一次
        self._auto_enabled = False

    @property
    def auto_enabled(self) -> bool:
        return self._auto_enabled

    def set_auto(self, enabled: bool):
        self._auto_enabled = enabled
        logger.info(f"自动调度已{'启用' if enabled else '禁用'}")

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
        priorities = await self.store.get_all_task_priorities()
        for proc in processes:
            proc["priority"] = priorities.get(proc["pid"], "normal")

        time_period = get_time_period_label()
        strategy = await self.llm.generate_schedule(gpus, processes, time_period)
        return strategy

    async def execute_actions(self, actions: list[dict]) -> list[dict]:
        """执行调度动作列表"""
        results = []
        for action in actions:
            act = action["action"]
            target = action["target"]
            reason = action["reason"]
            result = {"action": act, "reason": reason, "success": False}

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
            except Exception as e:
                result["error"] = str(e)
                logger.error(f"执行调度动作失败: {act} - {e}")

            results.append(result)
        return results

    async def tick(self, gpus: list[dict], processes: list[dict]) -> dict:
        """定期调度tick - 被数据采集循环调用"""
        result = {"rule_actions": [], "ai_actions": [], "executed": []}

        # 始终执行规则引擎
        rule_actions = await self.run_rules(gpus, processes)
        if rule_actions:
            result["rule_actions"] = rule_actions
            executed = await self.execute_actions(rule_actions)
            result["executed"].extend(executed)

        # AI调度（有间隔控制）
        now = time.time()
        if (self._auto_enabled and self.llm and
                now - self._last_schedule_time >= self._schedule_interval):
            self._last_schedule_time = now
            strategy = await self.run_ai_schedule(gpus, processes)
            if strategy and "actions" in strategy:
                result["ai_actions"] = strategy["actions"]
                executed = await self.execute_actions(strategy["actions"])
                result["executed"].extend(executed)

        return result
