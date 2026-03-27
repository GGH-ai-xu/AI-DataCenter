"""能耗分析计算引擎 - 纯计算模块，所有数据来自SQLite gpu_history表

核心指标：
- 能耗(kWh)、电费(CNY)、碳排放(kgCO2)
- 峰谷平时段分析、GPU效率评分
- 功耗预测（EWA/线性回归/多项式，自动选优）
- AI优化建议、历史对比、报告导出、调度回放
"""

import json
import math
import time
import logging
from datetime import datetime
from typing import Optional

# numpy可选导入，不可用时降级到纯EWA
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

logger = logging.getLogger(__name__)

# ========== 常量 ==========
ELECTRICITY_PRICE = 0.85        # 商业电价 CNY/kWh
CARBON_FACTOR = 0.5703          # 中国电网碳排放因子 kgCO2/kWh (2023)
TREE_ANNUAL_ABSORPTION = 21.77  # 一棵树年均吸碳 kgCO2

# 时段划分
PEAK_HOURS = set(range(9, 12)) | set(range(14, 18))
VALLEY_HOURS = set(range(22, 24)) | set(range(0, 6))


def _classify_hour(h: int) -> str:
    if h in PEAK_HOURS:
        return "peak"
    elif h in VALLEY_HOURS:
        return "valley"
    return "normal"

class EnergyAnalytics:
    """能耗分析计算引擎"""

    def __init__(
        self,
        data_store,
        llm_service=None,
        agent_client=None,
        privacy_service=None,
        governance_service=None,
    ):
        self.store = data_store
        self.llm = llm_service
        self.agent = agent_client
        self.privacy = privacy_service
        self.governance = governance_service

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

    @staticmethod
    def _clamp(value: float, lower: float, upper: float) -> float:
        return max(lower, min(upper, value))

    def _simulate_actions(
        self,
        gpus: list[dict],
        processes: list[dict],
        actions: list[dict],
    ) -> tuple[list[dict], list[dict]]:
        sim_gpus = [dict(gpu) for gpu in gpus]
        sim_processes = [dict(proc) for proc in processes]

        def find_gpu(gpu_index: int) -> dict | None:
            return next(
                (
                    gpu for gpu in sim_gpus
                    if int(gpu.get("index", gpu.get("gpu_index", -1))) == gpu_index
                ),
                None,
            )

        def find_process(pid: int) -> dict | None:
            return next((proc for proc in sim_processes if int(proc.get("pid", -1)) == pid), None)

        for action in actions:
            act = action.get("action")
            target = action.get("target", {}) or {}

            if act == "set_power_limit":
                gpu_index = int(target.get("gpu_index", -1))
                gpu = find_gpu(gpu_index)
                if not gpu:
                    continue

                current_limit = float(gpu.get("power_limit", 0) or 0)
                current_power = float(gpu.get("power_usage", 0) or 0)
                target_limit = float(target.get("power_limit", current_limit) or current_limit)
                if current_limit <= 0:
                    gpu["power_limit"] = target_limit
                    continue

                gpu["power_limit"] = round(target_limit, 1)
                if target_limit >= current_limit:
                    continue

                ratio = self._clamp(target_limit / current_limit, 0.35, 1.0)
                new_power = min(current_power, current_power * ratio)
                delta = max(0.0, current_power - new_power)
                gpu["power_usage"] = round(new_power, 1)
                if "temperature" in gpu:
                    gpu["temperature"] = int(max(30, round(float(gpu.get("temperature", 30) or 30) - min(8.0, delta / 12.0))))

            elif act == "pause_task":
                pid = int(target.get("pid", -1))
                proc = find_process(pid)
                if not proc:
                    continue

                gpu_index = int(proc.get("gpu_index", -1))
                gpu = find_gpu(gpu_index)
                same_gpu = [item for item in sim_processes if int(item.get("gpu_index", -1)) == gpu_index]
                total_memory = sum(max(1, int(item.get("gpu_memory_used", 0) or 0)) for item in same_gpu) or max(1, len(same_gpu))
                proc_memory = max(1, int(proc.get("gpu_memory_used", 0) or 0))
                process_share = proc_memory / total_memory if total_memory > 0 else 1 / max(1, len(same_gpu))

                if gpu:
                    current_power = float(gpu.get("power_usage", 0) or 0)
                    estimated = action.get("estimated_saving")
                    if estimated is None:
                        estimated = current_power * self._clamp(process_share * 0.85, 0.18, 0.65)
                    estimated = float(max(0.0, estimated))
                    gpu["power_usage"] = round(max(0.0, current_power - estimated), 1)
                    gpu["gpu_utilization"] = int(max(0, round(float(gpu.get("gpu_utilization", 0) or 0) * max(0.25, 1 - process_share))))
                    memory_used = int(gpu.get("memory_used", 0) or 0)
                    memory_total = int(gpu.get("memory_total", 0) or 0)
                    gpu["memory_used"] = max(0, memory_used - proc_memory)
                    gpu["memory_free"] = max(0, memory_total - gpu["memory_used"])
                    gpu["memory_utilization"] = int(round(gpu["memory_used"] / memory_total * 100)) if memory_total > 0 else 0
                    if "temperature" in gpu:
                        gpu["temperature"] = int(max(30, round(float(gpu.get("temperature", 30) or 30) - min(10.0, estimated / 10.0))))

                sim_processes = [item for item in sim_processes if int(item.get("pid", -1)) != pid]

        return sim_gpus, sim_processes

    def _is_benchmark_action_allowed(
        self,
        action: dict,
        gpus: list[dict],
        processes: list[dict],
    ) -> bool:
        act = action.get("action")
        target = action.get("target", {}) or {}

        if act == "observe":
            return True

        if act == "set_power_limit":
            gpu_index = int(target.get("gpu_index", -1))
            return any(
                int(gpu.get("index", gpu.get("gpu_index", -1))) == gpu_index
                for gpu in gpus
            )

        if act == "pause_task":
            pid = int(target.get("pid", -1))
            process = next(
                (item for item in processes if int(item.get("pid", -1)) == pid),
                None,
            )
            if not process or process.get("priority") == "urgent":
                return False
            if self.governance:
                return self.governance._is_governable_process(process)
            return True

        return False

    def _filter_benchmark_actions(
        self,
        actions: list[dict],
        gpus: list[dict],
        processes: list[dict],
    ) -> list[dict]:
        filtered = []
        seen = set()

        for action in actions or []:
            if not self._is_benchmark_action_allowed(action, gpus, processes):
                continue

            act = action.get("action")
            target = action.get("target", {}) or {}
            if act == "set_power_limit":
                key = (act, int(target.get("gpu_index", -1)))
            elif act == "pause_task":
                key = (act, int(target.get("pid", -1)))
            else:
                key = (act, json.dumps(target, sort_keys=True, ensure_ascii=False))

            if key in seen:
                continue
            seen.add(key)
            filtered.append(action)

        return filtered

    async def _analyze_simulated_fairness(
        self,
        gpus: list[dict],
        processes: list[dict],
    ) -> dict:
        if not self.governance:
            return {
                "overview": {
                    "fairness_index": 0.0,
                    "violation_user_count": 0,
                    "dominant_user": None,
                    "summary": "公平性服务不可用。",
                },
                "users": [],
            }

        history_stats = await self.store.get_user_stats()
        governance_rules = await self.store.get_user_governance_rules()
        history_by_user = {
            row.get("username") or "unknown": row
            for row in history_stats
        }
        governable_processes = [
            proc for proc in processes
            if self.governance._is_governable_process(proc)
        ]
        users = self.governance._build_user_profiles(
            governable_processes,
            gpus,
            history_by_user,
            governance_rules,
        )
        overview = self.governance._build_overview(users, gpus, governable_processes)
        overview["reclaimable_candidates"] = len(
            self.governance._build_yield_candidates(governable_processes, users, overview)
        )
        return {"overview": overview, "users": users}

    def _count_risks(self, gpus: list[dict], overview: dict, budget_status: dict) -> dict:
        hot_gpu_count = sum(1 for gpu in gpus if float(gpu.get("temperature", 0) or 0) >= 85)
        thermal_critical_count = sum(1 for gpu in gpus if float(gpu.get("temperature", 0) or 0) >= 90)
        budget_pressure = bool(budget_status.get("is_exceeded"))
        violation_user_count = int(overview.get("violation_user_count", 0) or 0)
        risk_count = hot_gpu_count + thermal_critical_count + violation_user_count + (1 if budget_pressure else 0)
        return {
            "risk_count": risk_count,
            "hot_gpu_count": hot_gpu_count,
            "thermal_critical_count": thermal_critical_count,
            "budget_pressure": budget_pressure,
            "violation_user_count": violation_user_count,
        }

    def _estimate_urgent_protection_score(
        self,
        processes: list[dict],
        gpus: list[dict],
        budget_status: dict,
    ) -> float:
        urgent_tasks = [proc for proc in processes if proc.get("priority") == "urgent"]
        if not urgent_tasks:
            return 82.0 if not budget_status.get("is_exceeded") else 68.0

        gpu_by_index = {
            int(gpu.get("index", -1)): gpu
            for gpu in gpus
        }
        score = 92.0
        if budget_status.get("is_exceeded"):
            score -= 18.0
        for proc in urgent_tasks:
            gpu = gpu_by_index.get(int(proc.get("gpu_index", -1)))
            if not gpu:
                continue
            if float(gpu.get("temperature", 0) or 0) >= 85:
                score -= 15.0
            if float(gpu.get("gpu_utilization", 0) or 0) < 35:
                score -= 4.0
        return round(self._clamp(score, 0.0, 100.0), 1)

    def _compose_strategy_result(
        self,
        mode: str,
        label: str,
        actions: list[dict],
        sim_gpus: list[dict],
        fairness_report: dict,
        baseline_total_power: float,
        scheduler,
        processes: list[dict],
    ) -> dict:
        total_power = sum(float(gpu.get("power_usage", 0) or 0) for gpu in sim_gpus)
        saving_w = max(0.0, baseline_total_power - total_power)
        saving_pct = saving_w / baseline_total_power * 100 if baseline_total_power > 0 else 0.0
        budget_status = scheduler.get_budget_status(sim_gpus)
        overview = fairness_report.get("overview", {})
        fairness_index = float(overview.get("fairness_index", 0) or 0)
        risk = self._count_risks(sim_gpus, overview, budget_status)
        urgent_protection_score = self._estimate_urgent_protection_score(processes, sim_gpus, budget_status)

        power_component = self._clamp(saving_pct * 4.0, 0.0, 100.0)
        fairness_component = self._clamp(fairness_index, 0.0, 100.0)
        risk_component = self._clamp(100.0 - risk["risk_count"] * 18.0, 0.0, 100.0)
        composite_score = round(
            power_component * 0.35
            + fairness_component * 0.35
            + risk_component * 0.15
            + urgent_protection_score * 0.15,
            1,
        )

        dominant_user = overview.get("dominant_user")
        summary_parts = [
            f"预计总功率 {total_power:.1f}W",
            f"公平指数 {fairness_index:.1f}",
        ]
        if risk["budget_pressure"]:
            summary_parts.append("仍有预算压力")
        elif scheduler.budget_enabled:
            summary_parts.append("预算压力已缓解")
        if dominant_user:
            summary_parts.append(f"主导用户 {dominant_user}")

        return {
            "mode": mode,
            "label": label,
            "projected_total_power_w": round(total_power, 1),
            "estimated_saving_w": round(saving_w, 1),
            "estimated_saving_pct": round(saving_pct, 1),
            "fairness_index": round(fairness_index, 1),
            "violation_user_count": risk["violation_user_count"],
            "risk_count": risk["risk_count"],
            "hot_gpu_count": risk["hot_gpu_count"],
            "thermal_critical_count": risk["thermal_critical_count"],
            "budget_pressure": risk["budget_pressure"],
            "urgent_protection_score": urgent_protection_score,
            "action_count": len(actions),
            "composite_score": composite_score,
            "summary": "，".join(summary_parts),
            "actions": actions[:6],
        }

    async def get_strategy_benchmark(self, scheduler) -> dict:
        """基于当前真实快照，对比无治理、规则治理、完整治理的离线效果。"""
        if not self.agent:
            return {"insufficient_data": True, "message": "Agent 不可用，无法生成策略实验对比。"}

        gpus = await self.agent.get_all_gpus()
        processes = await self.agent.get_processes()
        if not gpus:
            return {"insufficient_data": True, "message": "当前未获取到真实 GPU 数据，无法生成策略实验对比。"}

        processes = await self._attach_priorities(processes)
        base_fairness = await self._analyze_simulated_fairness(gpus, processes)
        baseline_total_power = sum(float(gpu.get("power_usage", 0) or 0) for gpu in gpus)

        rule_actions = self._filter_benchmark_actions(
            await scheduler.run_rules(gpus, processes),
            gpus,
            processes,
        )
        budget_actions = self._filter_benchmark_actions(
            await scheduler.run_budget_schedule(gpus, processes),
            gpus,
            processes,
        )
        ai_strategy = await scheduler.run_ai_schedule(gpus, processes)
        ai_actions = self._filter_benchmark_actions(
            (ai_strategy or {}).get("actions", []) if ai_strategy else [],
            gpus,
            processes,
        )
        if not ai_actions:
            ai_actions = self._filter_benchmark_actions(
                self._generate_rule_based_suggestions(gpus),
                gpus,
                processes,
            )

        observe_result = self._compose_strategy_result(
            "observe",
            "无治理",
            [],
            gpus,
            base_fairness,
            baseline_total_power,
            scheduler,
            processes,
        )

        rule_gpus, rule_processes = self._simulate_actions(gpus, processes, rule_actions)
        rule_fairness = await self._analyze_simulated_fairness(rule_gpus, rule_processes)
        rule_result = self._compose_strategy_result(
            "rules_only",
            "规则治理",
            rule_actions,
            rule_gpus,
            rule_fairness,
            baseline_total_power,
            scheduler,
            rule_processes,
        )

        full_actions = rule_actions + budget_actions + ai_actions
        full_gpus, full_processes = self._simulate_actions(gpus, processes, full_actions)
        full_fairness = await self._analyze_simulated_fairness(full_gpus, full_processes)
        full_result = self._compose_strategy_result(
            "full_governance",
            "完整治理",
            full_actions,
            full_gpus,
            full_fairness,
            baseline_total_power,
            scheduler,
            full_processes,
        )

        results = [observe_result, rule_result, full_result]
        winner = max(results, key=lambda item: item["composite_score"])
        current_fairness = observe_result["fairness_index"]
        scenario = "steady_window"
        scenario_label = "平稳观察窗口"
        if observe_result["budget_pressure"]:
            scenario = "budget_pressure"
            scenario_label = "预算压力窗口"
        elif observe_result["hot_gpu_count"] > 0:
            scenario = "thermal_pressure"
            scenario_label = "热风险窗口"
        elif current_fairness < 65:
            scenario = "fairness_pressure"
            scenario_label = "公平性压力窗口"

        return {
            "generated_at": time.time(),
            "scenario": scenario,
            "scenario_label": scenario_label,
            "baseline_power_w": round(baseline_total_power, 1),
            "budget_enabled": scheduler.budget_enabled,
            "budget_limit_w": scheduler.budget_limit_watts,
            "results": results,
            "winner_mode": winner["mode"],
            "winner_label": winner["label"],
            "winner_summary": winner["summary"],
            "insufficient_data": False,
        }

    async def get_energy_metrics(self, hours: float = 24.0) -> dict:
        """核心KPI指标"""
        summary = await self.store.get_power_summary(hours)
        latest = await self.store.get_all_gpu_latest()
        total_avg_w = summary.get("total_avg_power", 0) or 0
        current_total_w = sum(g.get("power_usage", 0) for g in latest)
        gpu_count = len(latest)
        per_gpu = [dict(g) for g in summary.get("gpus", [])]

        kwh = total_avg_w * hours / 1000
        cost = kwh * ELECTRICITY_PRICE
        co2_kg = kwh * CARBON_FACTOR

        total_power_limit = sum(g.get("power_limit", 350) for g in latest) if latest else 0
        saving_pct = ((total_power_limit - current_total_w) / total_power_limit * 100) if total_power_limit > 0 else 0

        scores = []
        for g in latest:
            util = g.get("gpu_utilization", 0) or 0
            power = g.get("power_usage", 1)
            limit = g.get("power_limit", 350) or 350
            ratio = power / limit if limit > 0 else 1
            score = min(100, util / max(ratio, 0.01))
            if g.get("temperature", 0) >= 85:
                score *= 0.8
            elif g.get("temperature", 0) >= 75:
                score *= 0.9
            scores.append(score)
        avg_efficiency = sum(scores) / len(scores) if scores else 0

        return {
            "current_total_power": round(current_total_w, 1),
            "avg_total_power": round(total_avg_w, 1),
            "kwh": round(kwh, 2),
            "cost_cny": round(cost, 2),
            "co2_kg": round(co2_kg, 3),
            "saving_pct": round(max(0, saving_pct), 1),
            "efficiency_score": round(avg_efficiency, 1),
            "gpu_count": gpu_count,
            "hours": hours,
            "per_gpu": per_gpu,
        }

    async def get_time_period_breakdown(self, hours: float = 24.0) -> dict:
        """峰谷平时段能耗分析"""
        hourly = await self.store.get_hourly_power_aggregation(hours)

        buckets = {
            "peak": {"label": "高峰时段(9-12,14-18)", "hours": [], "total_power": 0, "avg_power": 0, "samples": 0},
            "valley": {"label": "低谷时段(22-6)", "hours": [], "total_power": 0, "avg_power": 0, "samples": 0},
            "normal": {"label": "平峰时段", "hours": [], "total_power": 0, "avg_power": 0, "samples": 0},
        }

        for row in hourly:
            h = row["hour"]
            period = _classify_hour(h)
            bucket = buckets[period]
            bucket["hours"].append(h)
            bucket["total_power"] += row.get("avg_power", 0) * row.get("samples", 1)
            bucket["samples"] += row.get("samples", 0)

        grand_total = sum(b["total_power"] for b in buckets.values())
        for key, bucket in buckets.items():
            bucket["avg_power"] = round(bucket["total_power"] / bucket["samples"], 1) if bucket["samples"] > 0 else 0
            bucket["pct"] = round(bucket["total_power"] / grand_total * 100, 1) if grand_total > 0 else 0
            bucket["kwh"] = round(bucket["total_power"] / bucket["samples"] * len(bucket["hours"]) / 1000, 3) if bucket["samples"] > 0 else 0

        hourly_detail = []
        for row in hourly:
            h = row["hour"]
            hourly_detail.append({
                "hour": h,
                "period": _classify_hour(h),
                "avg_power": round(row.get("avg_power", 0), 1),
                "max_power": round(row.get("max_power", 0), 1),
                "avg_util": round(row.get("avg_util", 0), 1),
                "avg_temp": round(row.get("avg_temp", 0), 1),
            })

        return {
            "breakdown": buckets,
            "hourly": hourly_detail,
        }

    async def get_gpu_efficiency(self) -> list[dict]:
        """每张GPU效率评分 0-100"""
        latest = await self.store.get_all_gpu_latest()

        results = []
        for g in latest:
            util = g.get("gpu_utilization", 0) or 0
            mem_util = g.get("memory_utilization", 0) or 0
            power = g.get("power_usage", 1)
            limit = g.get("power_limit", 350) or 350
            temp = g.get("temperature", 0) or 0

            power_ratio = power / limit if limit > 0 else 1
            score = min(100, util / max(power_ratio, 0.01))
            if temp >= 85:
                score *= 0.8
            elif temp >= 75:
                score *= 0.9

            results.append({
                "gpu_index": g.get("gpu_index", 0),
                "score": round(score, 1),
                "gpu_utilization": util,
                "memory_utilization": mem_util,
                "power_usage": round(power, 1),
                "power_limit": round(limit, 1),
                "temperature": temp,
                "power_efficiency": round(power_ratio * 100, 1),
            })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results

    # ========== F1: 预测算法（3种，自动选优） ==========

    def _predict_ewa(self, values: list[float]) -> tuple[Optional[float], Optional[float]]:
        """指数加权平均预测，返回(predicted, std)；无历史时不再编造预测值"""
        if not values:
            return None, None
        weights = [math.exp(-0.3 * (len(values) - 1 - j)) for j in range(len(values))]
        total_w = sum(weights)
        weighted_avg = sum(v * w for v, w in zip(values, weights)) / total_w
        if len(values) > 1:
            variance = sum(w * (v - weighted_avg) ** 2 for v, w in zip(values, weights)) / total_w
            std = math.sqrt(variance)
        else:
            std = weighted_avg * 0.1
        return weighted_avg, std

    def _predict_linear(self, values: list[float]) -> tuple[float, float, float, float]:
        """线性回归预测，返回(predicted, std, rmse, r_squared)"""
        if not HAS_NUMPY or len(values) < 3:
            return None, None, float('inf'), 0.0
        x = np.arange(len(values), dtype=float)
        y = np.array(values, dtype=float)
        coeffs = np.polyfit(x, y, 1)
        predicted = float(np.polyval(coeffs, len(values)))
        y_pred = np.polyval(coeffs, x)
        residuals = y - y_pred
        rmse = float(np.sqrt(np.mean(residuals ** 2)))
        ss_res = float(np.sum(residuals ** 2))
        ss_tot = float(np.sum((y - np.mean(y)) ** 2))
        r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
        std = rmse
        return predicted, std, rmse, r_squared

    def _predict_polynomial(self, values: list[float]) -> tuple[float, float, float, float]:
        """2次多项式预测，返回(predicted, std, rmse, r_squared)，含外推防发散"""
        if not HAS_NUMPY or len(values) < 5:
            return None, None, float('inf'), 0.0
        x = np.arange(len(values), dtype=float)
        y = np.array(values, dtype=float)
        coeffs = np.polyfit(x, y, 2)
        predicted = float(np.polyval(coeffs, len(values)))
        # 防发散：predicted < 0 或 > max*3 则弃用
        max_val = float(np.max(y))
        if predicted < 0 or predicted > max_val * 3:
            return None, None, float('inf'), 0.0
        y_pred = np.polyval(coeffs, x)
        residuals = y - y_pred
        rmse = float(np.sqrt(np.mean(residuals ** 2)))
        ss_res = float(np.sum(residuals ** 2))
        ss_tot = float(np.sum((y - np.mean(y)) ** 2))
        r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
        std = rmse
        return predicted, std, rmse, r_squared

    async def get_power_prediction(self, predict_hours: int = 24) -> dict:
        """功耗预测 - 3种算法竞争选优"""
        hourly_7d = await self.store.get_hourly_power_aggregation(hours=168)
        hour_history = {}
        for row in hourly_7d:
            h = row["hour"]
            if h not in hour_history:
                hour_history[h] = []
            hour_history[h].append(row.get("avg_power", 0))

        now_hour = datetime.now().hour
        predictions = []
        algo_stats = {"ewa": 0, "linear": 0, "polynomial": 0}
        total_rmse = 0.0
        rmse_count = 0

        for i in range(predict_hours):
            target_hour = (now_hour + i) % 24
            values = hour_history.get(target_hour, [])
            if not values:
                predictions.append({
                    "hour": target_hour,
                    "offset": i,
                    "predicted_power": None,
                    "upper_bound": None,
                    "lower_bound": None,
                    "confidence": 0,
                    "period": _classify_hour(target_hour),
                    "algorithm": None,
                    "rmse": None,
                    "r_squared": None,
                    "available": False,
                })
                continue

            # 3种算法都跑
            ewa_pred, ewa_std = self._predict_ewa(values)
            if ewa_pred is None or ewa_std is None:
                predictions.append({
                    "hour": target_hour,
                    "offset": i,
                    "predicted_power": None,
                    "upper_bound": None,
                    "lower_bound": None,
                    "confidence": 0,
                    "period": _classify_hour(target_hour),
                    "algorithm": None,
                    "rmse": None,
                    "r_squared": None,
                    "available": False,
                })
                continue
            ewa_rmse = ewa_std  # EWA用std近似rmse

            best_pred, best_std, best_rmse, best_r2, best_algo = ewa_pred, ewa_std, ewa_rmse, 0.0, "加权平均"

            lin_pred, lin_std, lin_rmse, lin_r2 = self._predict_linear(values)
            if lin_pred is not None and lin_rmse < best_rmse:
                best_pred, best_std, best_rmse, best_r2, best_algo = lin_pred, lin_std, lin_rmse, lin_r2, "线性回归"

            poly_pred, poly_std, poly_rmse, poly_r2 = self._predict_polynomial(values)
            if poly_pred is not None and poly_rmse < best_rmse:
                best_pred, best_std, best_rmse, best_r2, best_algo = poly_pred, poly_std, poly_rmse, poly_r2, "多项式"

            # 统计
            algo_key = {"加权平均": "ewa", "线性回归": "linear", "多项式": "polynomial"}[best_algo]
            algo_stats[algo_key] += 1
            total_rmse += best_rmse
            rmse_count += 1

            predictions.append({
                "hour": target_hour,
                "offset": i,
                "predicted_power": round(best_pred, 1),
                "upper_bound": round(best_pred + best_std, 1),
                "lower_bound": round(max(0, best_pred - best_std), 1),
                "confidence": round(1 - best_std / max(best_pred, 1), 2) if best_pred > 0 else 0,
                "period": _classify_hour(target_hour),
                "algorithm": best_algo,
                "rmse": round(best_rmse, 2),
                "r_squared": round(best_r2, 4),
                "available": True,
            })

        available_predictions = [item for item in predictions if item.get("available")]
        result = {
            "predictions": predictions,
            "start_hour": now_hour,
            "predict_hours": predict_hours,
            "data_points_used": sum(len(v) for v in hour_history.values()),
            "available_prediction_count": len(available_predictions),
            "insufficient_data": len(available_predictions) == 0,
            "partial_prediction": 0 < len(available_predictions) < predict_hours,
            "algorithm_stats": {
                "ewa_count": algo_stats["ewa"],
                "linear_count": algo_stats["linear"],
                "polynomial_count": algo_stats["polynomial"],
                "avg_rmse": round(total_rmse / rmse_count, 2) if rmse_count > 0 else 0,
                "numpy_available": HAS_NUMPY,
            },
        }

        # D3: AI预测解读
        if self.llm and available_predictions:
            try:
                peak_pred = max(available_predictions, key=lambda x: x.get("predicted_power", 0))
                valley_pred = min(available_predictions, key=lambda x: x.get("predicted_power", 0))
                from app.services.scheduler import get_time_period_label
                from app.services.llm import PREDICTION_INTERPRET_PROMPT
                pred_context = PREDICTION_INTERPRET_PROMPT.format(
                    hours=predict_hours,
                    peak=peak_pred["predicted_power"], peak_hour=peak_pred["hour"],
                    valley=valley_pred["predicted_power"], valley_hour=valley_pred["hour"],
                    ewa=algo_stats["ewa"], linear=algo_stats["linear"], poly=algo_stats["polynomial"],
                    rmse=result["algorithm_stats"]["avg_rmse"],
                    time_period=get_time_period_label(),
                )
                interpretation = await self.llm.interpret_prediction(pred_context)
                if interpretation:
                    result["ai_interpretation"] = interpretation
            except Exception as e:
                logger.warning(f"AI预测解读失败: {e}")

        return result

    async def get_carbon_data(self, hours: float = 24.0) -> dict:
        """碳排放详细数据"""
        metrics = await self.get_energy_metrics(hours)
        co2_kg = metrics["co2_kg"]

        daily_tree_absorption = TREE_ANNUAL_ABSORPTION / 365
        trees_equivalent = co2_kg / daily_tree_absorption if daily_tree_absorption > 0 else 0

        kwh = metrics["kwh"]
        carbon_intensity = co2_kg / kwh if kwh > 0 else 0

        return {
            "co2_kg": round(co2_kg, 3),
            "co2_saved_kg": round(co2_kg * metrics["saving_pct"] / 100, 3),
            "trees_equivalent": round(trees_equivalent, 1),
            "carbon_intensity": round(carbon_intensity, 4),
            "kwh": round(kwh, 2),
            "hours": hours,
            "carbon_factor": CARBON_FACTOR,
            "electricity_price": ELECTRICITY_PRICE,
        }

    async def get_optimization_analysis(self) -> dict:
        """一键AI优化分析"""
        latest = await self.store.get_all_gpu_latest()
        if not latest:
            return {
                "baseline_power": 0,
                "optimized_power": 0,
                "estimated_saving_w": 0,
                "saving_pct": 0,
                "co2_saved_kg_per_hour": 0,
                "cost_saved_per_hour": 0,
                "suggestions": [],
                "gpu_count": 0,
                "timestamp": time.time(),
                "insufficient_data": True,
                "message": "当前缺少足够的真实 GPU 历史数据，暂不生成优化结论。",
            }

        current_total = sum(g.get("power_usage", 0) for g in latest)
        if current_total < 30:
            return {
                "baseline_power": round(current_total, 1),
                "optimized_power": round(current_total, 1),
                "estimated_saving_w": 0,
                "saving_pct": 0,
                "co2_saved_kg_per_hour": 0,
                "cost_saved_per_hour": 0,
                "suggestions": [{
                    "action": "observe",
                    "target": {},
                    "reason": "当前整机功耗很低，暂不存在有意义的节能动作，建议继续观察真实负载窗口。",
                    "estimated_saving_w": 0,
                }],
                "gpu_count": len(latest),
                "timestamp": time.time(),
                "low_load": True,
            }

        ai_suggestions = []
        estimated_saving_w = 0

        if self.llm and self.agent:
            try:
                gpus = await self.agent.get_all_gpus() or latest
                processes = await self.agent.get_processes() or []
                if self.privacy:
                    processes = self.privacy.sanitize_processes(processes)
                from app.services.scheduler import get_time_period_label
                time_period = get_time_period_label()
                strategy = await self.llm.generate_schedule(gpus, processes, time_period)
                if strategy:
                    ai_suggestions = strategy.get("actions", [])
                    estimated_saving_w = strategy.get("estimated_power_saving", 0)
            except Exception as e:
                logger.warning(f"AI优化分析调用失败: {e}")

        if not ai_suggestions:
            ai_suggestions = self._generate_rule_based_suggestions(latest)
            estimated_saving_w = sum(s.get("estimated_saving_w", 0) for s in ai_suggestions)

        estimated_saving_w = min(max(0, estimated_saving_w), current_total)

        optimized_power = max(0, current_total - estimated_saving_w)
        saving_pct = (estimated_saving_w / current_total * 100) if current_total > 0 else 0
        co2_saved = estimated_saving_w / 1000 * CARBON_FACTOR

        result = {
            "baseline_power": round(current_total, 1),
            "optimized_power": round(optimized_power, 1),
            "estimated_saving_w": round(estimated_saving_w, 1),
            "saving_pct": round(saving_pct, 1),
            "co2_saved_kg_per_hour": round(co2_saved, 4),
            "cost_saved_per_hour": round(estimated_saving_w / 1000 * ELECTRICITY_PRICE, 4),
            "suggestions": ai_suggestions,
            "gpu_count": len(latest),
            "timestamp": time.time(),
        }

        try:
            await self.store.save_optimization_snapshot({
                "baseline_power": current_total,
                "optimized_power": optimized_power,
                "saving_pct": saving_pct,
                "co2_saved_kg": co2_saved,
                "actions_json": json.dumps(ai_suggestions, ensure_ascii=False),
            })
        except Exception as e:
            logger.warning(f"保存优化快照失败: {e}")

        return result

    def _generate_rule_based_suggestions(self, gpus: list[dict]) -> list[dict]:
        """规则生成基础优化建议（LLM不可用时降级）"""
        if not gpus:
            return []

        suggestions = []
        now_hour = datetime.now().hour
        period = _classify_hour(now_hour)
        period_label = "高峰" if period == "peak" else "低谷" if period == "valley" else "平峰"

        for g in gpus:
            idx = g.get("index", g.get("gpu_index", 0))
            util = g.get("gpu_utilization", 0) or 0
            power = g.get("power_usage", 0)
            limit = g.get("power_limit", 350) or 350
            temp = g.get("temperature", 0) or 0

            # 低利用率高功耗
            if util < 30 and power > limit * 0.4:
                target = max(150, int(power * 0.55))
                saving = power - target
                suggestions.append({
                    "action": "set_power_limit",
                    "target": {"gpu_index": idx, "power_limit": target},
                    "reason": f"GPU{idx}利用率仅{util}%但功耗{power:.0f}W，存在显著功耗浪费，建议降频至{target}W",
                    "estimated_saving_w": round(saving, 1),
                })

            # 功耗占比过高（利用率不匹配功耗）
            elif power > limit * 0.5 and util < power / limit * 100 * 0.8:
                target = max(180, int(util / 100 * limit * 1.2))
                saving = power - target if power > target else power * 0.12
                suggestions.append({
                    "action": "set_power_limit",
                    "target": {"gpu_index": idx, "power_limit": target},
                    "reason": f"{period_label}时段GPU{idx}利用率{util}%、功耗{power:.0f}W，功耗效率偏低，建议限制至{target}W",
                    "estimated_saving_w": round(max(saving, 0), 1),
                })

            # 高峰期非满载
            elif period == "peak" and util < 80:
                target = max(200, int(limit * 0.7))
                saving = power - target if power > target else power * 0.15
                suggestions.append({
                    "action": "set_power_limit",
                    "target": {"gpu_index": idx, "power_limit": target},
                    "reason": f"高峰时段GPU{idx}利用率{util}%未满载，建议削峰降频至{target}W节约电费",
                    "estimated_saving_w": round(max(saving, 0), 1),
                })

            # 低谷期
            elif period == "valley" and util < 40:
                target = max(150, int(power * 0.6))
                suggestions.append({
                    "action": "set_power_limit",
                    "target": {"gpu_index": idx, "power_limit": target},
                    "reason": f"低谷时段GPU{idx}利用率仅{util}%，建议降至{target}W低功耗运行",
                    "estimated_saving_w": round(max(power - target, 0), 1),
                })

            # 温度偏高
            if temp >= 75:
                target = max(200, int(limit * 0.7))
                saving = power - target if power > target else 0
                if saving > 0:
                    suggestions.append({
                        "action": "set_power_limit",
                        "target": {"gpu_index": idx, "power_limit": target},
                        "reason": f"GPU{idx}温度{temp}°C偏高，建议降频至{target}W以降温保护硬件寿命",
                        "estimated_saving_w": round(saving, 1),
                    })

        # 去重（同一GPU只保留节省最大的建议）
        seen_gpus = {}
        deduped = []
        for s in suggestions:
            gpu_idx = s.get("target", {}).get("gpu_index")
            saving = s.get("estimated_saving_w", 0)
            if gpu_idx is None:
                deduped.append(s)
            elif gpu_idx not in seen_gpus or saving > seen_gpus[gpu_idx]:
                seen_gpus[gpu_idx] = saving
                deduped = [x for x in deduped if x.get("target", {}).get("gpu_index") != gpu_idx]
                deduped.append(s)
        suggestions = deduped

        if not suggestions:
            suggestions.append({
                "action": "observe",
                "target": {},
                "reason": "当前基于真实数据未发现明确的节能动作，建议继续观察并积累更多历史样本。",
                "estimated_saving_w": 0,
            })

        return suggestions

    # ========== D2: AI趋势洞察 ==========

    async def get_ai_insight(self) -> Optional[dict]:
        """AI趋势洞察 - 有LLM时返回结构化洞察，无LLM返回None"""
        if not self.llm:
            return None
        try:
            metrics = await self.get_energy_metrics(24)
            latest = await self.store.get_all_gpu_latest()
            gpu_summary = "; ".join(
                f"GPU{g.get('gpu_index',i)}: {g.get('gpu_utilization',0)}%利用率, {g.get('power_usage',0):.0f}W/{g.get('power_limit',350)}W, {g.get('temperature',0)}°C"
                for i, g in enumerate(latest)
            )
            from app.services.scheduler import get_time_period_label
            from app.services.llm import INSIGHT_PROMPT
            prompt = INSIGHT_PROMPT.format(
                time_period=get_time_period_label(),
                total_power=metrics.get("current_total_power", 0),
                efficiency=metrics.get("efficiency_score", 0),
                saving_pct=metrics.get("saving_pct", 0),
                gpu_summary=gpu_summary,
            )
            return await self.llm.analyze_insight(prompt)
        except Exception as e:
            logger.warning(f"AI洞察生成失败: {e}")
            return None

    # ========== D1: AI异常模式检测 ==========

    async def get_ai_anomaly_analysis(self) -> Optional[dict]:
        """AI异常模式检测 - 有LLM时返回异常列表，无LLM返回None"""
        if not self.llm:
            return None
        try:
            latest = await self.store.get_all_gpu_latest()
            gpu_data_str = json.dumps(latest, indent=2, ensure_ascii=False, default=str)
            from app.services.llm import ANOMALY_PROMPT
            prompt = ANOMALY_PROMPT.format(gpu_data=gpu_data_str)
            return await self.llm.detect_anomalies(prompt)
        except Exception as e:
            logger.warning(f"AI异常检测失败: {e}")
            return None

    async def get_full_report(self, hours: float = 24.0) -> dict:
        """全KPI增强报告"""
        metrics = await self.get_energy_metrics(hours)
        breakdown = await self.get_time_period_breakdown(hours)
        efficiency = await self.get_gpu_efficiency()
        carbon = await self.get_carbon_data(hours)
        prediction = await self.get_power_prediction(24)

        return {
            "metrics": metrics,
            "time_breakdown": breakdown,
            "gpu_efficiency": efficiency,
            "carbon": carbon,
            "prediction": prediction,
            "generated_at": time.time(),
        }

    # ========== F4: 调度历史回放 ==========

    async def get_schedule_history(self, hours: float = 72.0) -> dict:
        """获取调度历史"""
        logs = await self.store.get_schedule_history(hours, limit=50)

        # 统计
        success_count = sum(1 for l in logs if l.get("result") == "success")
        action_counts = {}
        for l in logs:
            a = l.get("action", "unknown")
            action_counts[a] = action_counts.get(a, 0) + 1

        return {
            "logs": logs[:20],
            "total": len(logs),
            "success_count": success_count,
            "action_counts": action_counts,
        }

    # ========== F2: 历史对比 ==========

    async def get_history_comparison(self, hours: float = 72.0) -> dict:
        """优化效果历史对比：基线 vs 实际"""
        opt_history = await self.store.get_optimization_history(hours)
        power_series = await self.store.get_hourly_power_series(hours)

        if opt_history and power_series:
            first_opt = opt_history[-1]  # 最早的一条
            opt_time = first_opt.get("timestamp", time.time())
            baseline_power = first_opt.get("baseline_power")
            if baseline_power is None:
                return {
                    "baseline_series": [],
                    "actual_series": [],
                    "savings_series": [],
                    "total_saved_kwh": 0,
                    "optimization_time": 0,
                    "hours": hours,
                    "insufficient_data": True,
                }

            baseline_series = []
            actual_series = []
            savings_series = []
            total_saved_kwh = 0.0

            for pt in power_series:
                ts = pt["hour_ts"]
                actual = pt["avg_power"]
                if ts >= opt_time:
                    base = baseline_power
                    saved = max(0, base - actual)
                else:
                    base = actual
                    saved = 0
                baseline_series.append({"timestamp": ts, "power": round(base, 1)})
                actual_series.append({"timestamp": ts, "power": round(actual, 1)})
                savings_series.append({"timestamp": ts, "saved": round(saved, 1)})
                total_saved_kwh += saved / 1000

            return {
                "baseline_series": baseline_series,
                "actual_series": actual_series,
                "savings_series": savings_series,
                "total_saved_kwh": round(total_saved_kwh, 3),
                "optimization_time": opt_time,
                "hours": hours,
            }

        return {
            "baseline_series": [],
            "actual_series": [],
            "savings_series": [],
            "total_saved_kwh": 0,
            "optimization_time": 0,
            "hours": hours,
        }

    # ========== F3: 报告导出 ==========

    async def generate_export_report(self, hours: float = 24.0, fmt: str = "markdown") -> str:
        """生成可导出的能耗报告"""
        report = await self.get_full_report(hours)
        m = report["metrics"]
        tb = report["time_breakdown"]
        eff = report["gpu_efficiency"]
        c = report["carbon"]
        pred = report["prediction"]
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        md = f"""# AI数据中心能耗分析报告

> 生成时间：{ts}
> 统计周期：{hours}小时

---

## 一、系统概览

| 指标 | 数值 |
|------|------|
| GPU数量 | {m.get('gpu_count', 0)} 张 |
| 实时总功耗 | {m.get('current_total_power', 0)} W |
| 平均总功耗 | {m.get('avg_total_power', 0)} W |
| 效率评分 | {m.get('efficiency_score', 0)} 分 |

## 二、核心KPI

| 指标 | 数值 |
|------|------|
| 能耗 | {m.get('kwh', 0)} kWh |
| 电费 | ¥{m.get('cost_cny', 0)} |
| 碳排放 | {c.get('co2_kg', 0)} kgCO₂ |
| 节能比例 | {m.get('saving_pct', 0)}% |
| 等效树木 | {c.get('trees_equivalent', 0)} 棵/天 |
| 碳排放因子 | {c.get('carbon_factor', '—')} kgCO₂/kWh |

## 三、峰谷平时段分析

"""
        bk = tb.get("breakdown", {})
        for key, label in [("peak", "高峰"), ("normal", "平峰"), ("valley", "低谷")]:
            b = bk.get(key, {})
            md += f"- **{label}时段**：占比 {b.get('pct', 0)}%，平均功耗 {b.get('avg_power', 0)}W\n"

        md += "\n## 四、GPU效率排名\n\n| GPU | 效率评分 | 利用率 | 功耗 | 温度 |\n|-----|---------|--------|------|------|\n"
        for g in eff:
            md += f"| GPU {g.get('gpu_index', 0)} | {g.get('score', 0)} | {g.get('gpu_utilization', 0)}% | {g.get('power_usage', 0)}W/{g.get('power_limit', 0)}W | {g.get('temperature', 0)}°C |\n"

        md += "\n## 五、碳排放详情\n\n"
        md += f"- 日碳排放：{c.get('co2_kg', 0)} kgCO₂\n"
        md += f"- 已减排：{c.get('co2_saved_kg', 0)} kgCO₂\n"
        md += f"- 碳强度：{c.get('carbon_intensity', 0)} kgCO₂/kWh\n"

        md += "\n## 六、功耗预测摘要\n\n"
        preds = pred.get("predictions", [])
        available_preds = [item for item in preds if item.get("available")]
        if available_preds:
            algo_stats = pred.get("algorithm_stats", {})
            md += f"- 预测时段：未来 {pred.get('predict_hours', 24)} 小时\n"
            md += f"- 可用预测点：{pred.get('available_prediction_count', len(available_preds))} / {pred.get('predict_hours', 24)}\n"
            md += f"- 平均RMSE：{algo_stats.get('avg_rmse', 'N/A')}\n"
            md += f"- 使用算法：EWA {algo_stats.get('ewa_count', 0)}次 / 线性回归 {algo_stats.get('linear_count', 0)}次 / 多项式 {algo_stats.get('polynomial_count', 0)}次\n"
            peak_pred = max(available_preds, key=lambda x: x.get("predicted_power", 0))
            valley_pred = min(available_preds, key=lambda x: x.get("predicted_power", 0))
            md += f"- 预测峰值：{peak_pred.get('predicted_power', 0)}W（{peak_pred.get('hour', 0)}:00）\n"
            md += f"- 预测谷值：{valley_pred.get('predicted_power', 0)}W（{valley_pred.get('hour', 0)}:00）\n"
        else:
            md += "- 当前历史样本不足，暂不生成未来功耗预测。\n"

        md += f"\n---\n\n"

        # D5: AI分析师评语章节
        if self.llm:
            try:
                insight = await self.get_ai_insight()
                if insight:
                    md += "## 七、AI 分析师评语\n\n"
                    md += f"**{insight.get('summary', '')}**\n\n"
                    md += f"{insight.get('detail', '')}\n\n"
                    suggestions = insight.get('suggestions', [])
                    if suggestions:
                        md += "**建议：**\n\n"
                        for s in suggestions:
                            md += f"- {s}\n"
                    risk = insight.get('risk_level', 'low')
                    risk_label = {'low': '低风险', 'medium': '中等风险', 'high': '高风险'}.get(risk, risk)
                    md += f"\n> 风险等级：{risk_label}\n\n---\n\n"
            except Exception as e:
                logger.warning(f"AI报告章节生成失败: {e}")

        md += f"*报告由AI数据中心能耗智能优化管理系统自动生成*\n"

        if fmt == "html":
            return self._markdown_to_simple_html(md)
        return md

    @staticmethod
    def _markdown_to_simple_html(md: str) -> str:
        """简易Markdown转HTML（不依赖外部库）"""
        import re
        lines = md.split("\n")
        html_lines = ['<!DOCTYPE html><html><head><meta charset="utf-8">',
                       '<title>能耗分析报告</title>',
                       '<style>body{font-family:"Microsoft YaHei",sans-serif;max-width:900px;margin:40px auto;padding:0 20px;color:#333;line-height:1.8}',
                       'table{border-collapse:collapse;width:100%;margin:16px 0}th,td{border:1px solid #ddd;padding:8px 12px;text-align:left}',
                       'th{background:#f5f5f5}h1{color:#1a1a1a;border-bottom:2px solid #3A5F4B;padding-bottom:8px}',
                       'h2{color:#3A5F4B;margin-top:32px}blockquote{border-left:3px solid #3A5F4B;padding-left:16px;color:#666;margin:16px 0}',
                       'hr{border:none;border-top:1px solid #eee;margin:24px 0}</style></head><body>']
        in_table = False
        for line in lines:
            stripped = line.strip()
            if not stripped:
                if in_table:
                    html_lines.append("</table>")
                    in_table = False
                html_lines.append("")
                continue
            # 标题
            if stripped.startswith("# "):
                html_lines.append(f"<h1>{stripped[2:]}</h1>")
            elif stripped.startswith("## "):
                html_lines.append(f"<h2>{stripped[3:]}</h2>")
            elif stripped.startswith("> "):
                html_lines.append(f"<blockquote>{stripped[2:]}</blockquote>")
            elif stripped == "---":
                html_lines.append("<hr>")
            elif stripped.startswith("| ") and "---" in stripped:
                continue  # 跳过表格分隔行
            elif stripped.startswith("| "):
                cells = [c.strip() for c in stripped.split("|")[1:-1]]
                if not in_table:
                    html_lines.append("<table>")
                    in_table = True
                    html_lines.append("<tr>" + "".join(f"<th>{c}</th>" for c in cells) + "</tr>")
                else:
                    html_lines.append("<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")
            elif stripped.startswith("- "):
                content = stripped[2:]
                content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', content)
                html_lines.append(f"<p>• {content}</p>")
            elif stripped.startswith("*") and stripped.endswith("*"):
                html_lines.append(f"<p><em>{stripped.strip('*')}</em></p>")
            else:
                html_lines.append(f"<p>{stripped}</p>")
        if in_table:
            html_lines.append("</table>")
        html_lines.append("</body></html>")
        return "\n".join(html_lines)
