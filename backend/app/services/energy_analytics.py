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

    @staticmethod
    def _estimate_action_saving(action: dict) -> float:
        if not action:
            return 0.0
        value = action.get("estimated_saving_w")
        if value is None:
            value = action.get("estimated_saving")
        try:
            return max(0.0, float(value or 0.0))
        except (TypeError, ValueError):
            return 0.0

    def _project_total_power(self, current_total_power: float, actions: list[dict]) -> float:
        projected = float(current_total_power or 0.0)
        for action in actions or []:
            projected -= self._estimate_action_saving(action)
        return round(max(0.0, projected), 1)

    @staticmethod
    def _benchmark_scenario(gpus: list[dict], scheduler, current_total_power: float) -> str:
        budget_limit = float(getattr(scheduler, "budget_limit_watts", 0) or 0)
        budget_enabled = bool(getattr(scheduler, "budget_enabled", False))
        if budget_limit > 0 and (budget_enabled or current_total_power > budget_limit):
            return "budget_pressure"
        if any(float(gpu.get("temperature", 0) or 0) >= 85 for gpu in gpus):
            return "thermal_risk"
        if current_total_power <= max(180.0, len(gpus) * 110.0):
            return "low_load"
        return "steady_state"

    async def get_strategy_benchmark(self, scheduler) -> dict:
        """对比观察、规则治理、完整治理三种模式的理论结果。"""
        if not self.agent:
            return {
                "insufficient_data": True,
                "message": "当前未配置 Agent，无法生成治理测算。",
                "scenario": "agent_unavailable",
                "results": [],
                "winner_mode": None,
            }

        gpus = await self.agent.get_all_gpus() or []
        processes = await self.agent.get_processes() or []
        if not gpus:
            return {
                "insufficient_data": True,
                "message": "当前缺少真实 GPU 数据，无法生成治理测算。",
                "scenario": "missing_gpu_data",
                "results": [],
                "winner_mode": None,
            }

        current_total_power = sum(float(gpu.get("power_usage", 0) or 0) for gpu in gpus)
        scenario = self._benchmark_scenario(gpus, scheduler, current_total_power)
        rule_actions = await scheduler.run_rules(gpus, processes)
        budget_actions = await scheduler.run_budget_schedule(gpus, processes)
        ai_strategy = await scheduler.run_ai_schedule(gpus, processes) or {}
        ai_actions = ai_strategy.get("actions", []) or []

        results = [
            {
                "mode": "observe",
                "label": "仅观察",
                "action_count": 0,
                "estimated_saving_w": 0.0,
                "projected_total_power_w": round(current_total_power, 1),
                "actions": [],
            },
            {
                "mode": "rules_only",
                "label": "规则治理",
                "action_count": len(rule_actions),
                "estimated_saving_w": round(sum(self._estimate_action_saving(item) for item in rule_actions), 1),
                "projected_total_power_w": self._project_total_power(current_total_power, rule_actions),
                "actions": rule_actions,
            },
        ]

        full_actions = list(rule_actions) + list(budget_actions) + list(ai_actions)
        results.append(
            {
                "mode": "full_governance",
                "label": "完整治理",
                "action_count": len(full_actions),
                "estimated_saving_w": round(sum(self._estimate_action_saving(item) for item in full_actions), 1),
                "projected_total_power_w": self._project_total_power(current_total_power, full_actions),
                "actions": full_actions,
            }
        )

        winner_mode = min(
            results,
            key=lambda item: (item["projected_total_power_w"], -item["estimated_saving_w"]),
        )["mode"]

        return {
            "insufficient_data": False,
            "scenario": scenario,
            "current_total_power_w": round(current_total_power, 1),
            "winner_mode": winner_mode,
            "results": results,
            "rule_actions": rule_actions,
            "budget_actions": budget_actions,
            "ai_actions": ai_actions,
            "ai_summary": ai_strategy.get("summary"),
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

    def _predict_ewa(self, values: list[float]) -> tuple[float, float]:
        """指数加权平均预测，返回(predicted, std)"""
        if not values:
            return 700.0, 70.0
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

            # 3种算法都跑
            ewa_pred, ewa_std = self._predict_ewa(values)
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
            })

        result = {
            "predictions": predictions,
            "start_hour": now_hour,
            "predict_hours": predict_hours,
            "data_points_used": sum(len(v) for v in hour_history.values()),
            "algorithm_stats": {
                "ewa_count": algo_stats["ewa"],
                "linear_count": algo_stats["linear"],
                "polynomial_count": algo_stats["polynomial"],
                "avg_rmse": round(total_rmse / rmse_count, 2) if rmse_count > 0 else 0,
                "numpy_available": HAS_NUMPY,
            },
        }

        # D3: AI预测解读
        if self.llm and predictions:
            try:
                peak_pred = max(predictions, key=lambda x: x.get("predicted_power", 0))
                valley_pred = min(predictions, key=lambda x: x.get("predicted_power", 0))
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
        live_gpus = await self.agent.get_all_gpus() if self.agent else []
        current_gpus = live_gpus or latest
        if not current_gpus:
            return {
                "insufficient_data": True,
                "low_load": False,
                "message": "当前没有真实 GPU 数据，暂不生成优化结论。",
                "suggestions": [],
                "estimated_saving_w": 0,
                "baseline_power": 0,
                "optimized_power": 0,
                "gpu_count": 0,
                "timestamp": time.time(),
            }

        current_total = sum(g.get("power_usage", 0) for g in current_gpus)

        ai_suggestions = []
        estimated_saving_w = 0

        if self.llm and self.agent:
            try:
                gpus = current_gpus
                processes = await self.agent.get_processes() or []
                llm_processes = (
                    self.privacy.sanitize_processes(processes)
                    if self.privacy
                    else [dict(proc) for proc in processes]
                )
                from app.services.scheduler import get_time_period_label
                time_period = get_time_period_label()
                strategy = await self.llm.generate_schedule(gpus, llm_processes, time_period)
                if strategy:
                    ai_suggestions = strategy.get("actions", [])
                    estimated_saving_w = strategy.get("estimated_power_saving", 0)
            except Exception as e:
                logger.warning(f"AI优化分析调用失败: {e}")

        if not ai_suggestions:
            ai_suggestions = self._generate_rule_based_suggestions(current_gpus)
            estimated_saving_w = sum(s.get("estimated_saving_w", 0) for s in ai_suggestions)

        optimized_power = max(0, current_total - estimated_saving_w)
        saving_pct = (estimated_saving_w / current_total * 100) if current_total > 0 else 0
        co2_saved = estimated_saving_w / 1000 * CARBON_FACTOR
        low_load = current_total <= max(180.0, len(current_gpus) * 110.0)

        result = {
            "insufficient_data": False,
            "low_load": low_load,
            "baseline_power": round(current_total, 1),
            "optimized_power": round(optimized_power, 1),
            "estimated_saving_w": round(estimated_saving_w, 1),
            "saving_pct": round(saving_pct, 1),
            "co2_saved_kg_per_hour": round(co2_saved, 4),
            "cost_saved_per_hour": round(estimated_saving_w / 1000 * ELECTRICITY_PRICE, 4),
            "suggestions": ai_suggestions,
            "gpu_count": len(current_gpus),
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
        suggestions = []
        now_hour = datetime.now().hour
        period = _classify_hour(now_hour)
        period_label = "高峰" if period == "peak" else "低谷" if period == "valley" else "平峰"

        for g in gpus:
            idx = g.get("gpu_index", 0)
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
                "action": "none",
                "target": {},
                "reason": "当前GPU集群运行状态良好，各项指标在最优区间，暂无需调整",
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
        action_logs = [item for item in logs if item.get("action") != "ai_evaluate"]
        evaluation_logs = [item for item in logs if item.get("action") == "ai_evaluate"]

        # 统计
        success_count = sum(1 for l in action_logs if l.get("result") == "success")
        failure_count = sum(1 for l in action_logs if l.get("result") == "failed")
        action_counts = {}
        for l in logs:
            a = l.get("action", "unknown")
            action_counts[a] = action_counts.get(a, 0) + 1

        return {
            "logs": logs[:20],
            "total": len(logs),
            "success_count": success_count,
            "failure_count": failure_count,
            "execution_total": len(action_logs),
            "evaluation_total": len(evaluation_logs),
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
            baseline_power = first_opt.get("baseline_power", 800)

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
| 碳排放因子 | {c.get('carbon_factor', 0.5703)} kgCO₂/kWh |

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
        if preds:
            algo_stats = pred.get("algorithm_stats", {})
            md += f"- 预测时段：未来 {pred.get('predict_hours', 24)} 小时\n"
            md += f"- 平均RMSE：{algo_stats.get('avg_rmse', 'N/A')}\n"
            md += f"- 使用算法：EWA {algo_stats.get('ewa_count', 0)}次 / 线性回归 {algo_stats.get('linear_count', 0)}次 / 多项式 {algo_stats.get('polynomial_count', 0)}次\n"
            peak_pred = max(preds, key=lambda x: x.get("predicted_power", 0))
            valley_pred = min(preds, key=lambda x: x.get("predicted_power", 0))
            md += f"- 预测峰值：{peak_pred.get('predicted_power', 0)}W（{peak_pred.get('hour', 0)}:00）\n"
            md += f"- 预测谷值：{valley_pred.get('predicted_power', 0)}W（{valley_pred.get('hour', 0)}:00）\n"

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
