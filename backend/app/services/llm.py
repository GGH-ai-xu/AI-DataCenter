"""LLM集成服务 - 基于OpenAI兼容接口的AI能耗分析与调度建议"""

import json
import asyncio
import logging
from typing import Optional

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

# 系统提示词 - 能耗优化专家
SYSTEM_PROMPT = """你是一个AI数据中心能耗优化专家。你的职责是：

1. **监控分析**：基于实时GPU状态数据，分析当前能耗情况
2. **优化建议**：给出具体可执行的节能建议
3. **智能调度**：在高峰时段自动生成调度策略（降频、暂停低优先级任务）
4. **风险预警**：识别温度过高、功耗异常等风险

核心原则：
- "削峰填谷"：高峰期降低非紧急负载，低谷期恢复全速
- 安全优先：温度超过85°C必须降频，超过90°C必须紧急降频
- 业务连续性：urgent优先级任务永远不暂停
- 量化表达：给出具体数值（节省XX瓦、降温XX度）

回答要求：
- 简洁专业，重点突出
- 涉及操作建议时，说明预期效果和风险
- 使用中文回答"""

SCHEDULER_PROMPT = """基于以下GPU集群实时状态，生成调度策略JSON。

当前状态：
{gpu_data}

任务列表及优先级：
{task_data}

当前时段：{time_period}（高峰期：9:00-12:00, 14:00-18:00，低谷期：22:00-6:00）

请严格按以下JSON格式返回调度策略：
{{
    "actions": [
        {{
            "action": "set_power_limit",
            "target": {{"gpu_index": 0, "power_limit": 200}},
            "reason": "高峰时段，GPU0负载较低，降低功耗限制节省能耗"
        }},
        {{
            "action": "pause_task",
            "target": {{"pid": 12345}},
            "reason": "该任务为可延迟优先级，高峰期暂停以让出功耗预算"
        }}
    ],
    "summary": "高峰时段调度：预计降低总功耗150W，暂停1个低优先级任务",
    "estimated_power_saving": 150.0
}}

约束：
1. urgent优先级任务不可暂停
2. 功耗限制范围：100W-350W
3. 低谷期应恢复所有任务和功耗限制
4. 只返回JSON，不要额外文字"""


INSIGHT_PROMPT = """基于以下AI数据中心集群实时状态，给出一句话趋势洞察和具体行动建议。
当前时段：{time_period}
集群指标：实时总功耗 {total_power}W，平均效率 {efficiency}分，节能比例 {saving_pct}%
GPU状态：{gpu_summary}

严格按JSON返回：
{{"summary": "一句话洞察(30字内)", "risk_level": "low|medium|high", "detail": "详细分析(100字内)", "suggestions": ["建议1", "建议2"]}}"""

PREDICTION_INTERPRET_PROMPT = """以下是AI数据中心未来{hours}小时的功耗预测结果：
预测峰值：{peak}W（{peak_hour}:00），预测谷值：{valley}W（{valley_hour}:00）
使用算法：EWA {ewa}次 / 线性回归 {linear}次 / 多项式 {poly}次，平均RMSE: {rmse}
当前时段：{time_period}

请用50字内给出趋势判断和操作建议。仅返回纯文本，不要JSON。"""

ANOMALY_PROMPT = """分析以下GPU集群数据，识别阈值检测发现不了的异常模式。
{gpu_data}
可能的异常：功耗持续缓慢上升(散热退化)、利用率周期性骤降(任务异常)、GPU间负载严重不均(调度问题)、功耗-利用率不匹配(效率异常)。
严格按JSON返回：
{{"anomalies": [{{"type": "...", "gpu_index": 0, "description": "...", "severity": "warning|critical", "suggestion": "..."}}], "healthy": true}}
如果一切正常，返回空数组和healthy=true。"""

EVALUATE_PROMPT = """上次调度执行了以下操作：
{actions}
执行前集群状态：{before_state}
执行后集群状态：{after_state}

请评估调度效果，指出哪些操作有效、哪些需要改进。
严格按JSON返回：
{{"score": 0, "verdict": "一句话评价", "effective_actions": [], "ineffective_actions": [], "improvement": "改进建议"}}"""


class LLMService:
    """LLM服务 - 支持对话和调度策略生成"""

    def __init__(self, api_key: str, base_url: str, model: str):
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    async def _call_with_retry(self, max_retries: int = 2, **kwargs) -> str:
        """带重试的LLM调用，区分暂时性和永久性错误"""
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                response = await self.client.chat.completions.create(**kwargs)
                return response.choices[0].message.content
            except Exception as e:
                last_error = e
                err_str = str(e).lower()
                # 认证/配额错误不重试
                if any(k in err_str for k in ("401", "403", "invalid_api_key", "quota")):
                    raise
                if attempt < max_retries:
                    wait = 2 ** attempt
                    logger.warning(f"LLM调用失败(第{attempt+1}次)，{wait}s后重试: {e}")
                    await asyncio.sleep(wait)
        raise last_error

    async def chat(self, user_message: str, gpu_context: str = "") -> dict:
        """AI对话 - 基于实时数据回答用户问题"""
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
        ]
        if gpu_context:
            messages.append({
                "role": "system",
                "content": f"当前GPU集群实时状态：\n{gpu_context}",
            })
        messages.append({"role": "user", "content": user_message})

        try:
            reply = await self._call_with_retry(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=2000,
            )
            return {
                "reply": reply,
                "suggestions": self._extract_suggestions(reply),
            }
        except Exception as e:
            logger.error(f"LLM调用失败: {e}")
            return {
                "reply": f"AI服务暂时不可用：{str(e)}",
                "suggestions": [],
            }

    async def generate_schedule(
        self, gpu_data: list[dict], task_data: list[dict], time_period: str
    ) -> Optional[dict]:
        """生成智能调度策略"""
        prompt = SCHEDULER_PROMPT.format(
            gpu_data=json.dumps(gpu_data, indent=2, ensure_ascii=False),
            task_data=json.dumps(task_data, indent=2, ensure_ascii=False),
            time_period=time_period,
        )

        try:
            content = await self._call_with_retry(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=2000,
            )
            # 解析JSON（兼容markdown代码块包裹，如 ```json ... ```）
            content = content.strip()
            if content.startswith("```"):
                # 移除首行（可能是 ``` 或 ```json）
                first_nl = content.find("\n")
                if first_nl != -1:
                    content = content[first_nl + 1:]
                # 移除末尾 ```
                if content.rstrip().endswith("```"):
                    content = content.rstrip()[:-3].rstrip()
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"LLM返回的JSON解析失败: {e}")
            return None
        except Exception as e:
            logger.error(f"调度策略生成失败: {e}")
            return None

    async def generate_report(self, power_summary: dict, alerts: list[dict]) -> str:
        """生成能耗分析报告"""
        prompt = f"""请基于以下数据生成一份简洁的能耗分析报告（Markdown格式）：

功耗统计（过去24小时）：
{json.dumps(power_summary, indent=2, ensure_ascii=False)}

近期告警：
{json.dumps(alerts[:10], indent=2, ensure_ascii=False)}

报告要求：
1. 整体能耗概览（总功耗、平均功耗、峰值）
2. 各GPU负载分布分析
3. 异常与风险点
4. 优化建议（具体可执行）
5. 预估节能潜力（瓦特和百分比）"""

        try:
            return await self._call_with_retry(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.5,
                max_tokens=3000,
            )
        except Exception as e:
            return f"报告生成失败：{str(e)}"

    def _parse_json_response(self, content: str) -> Optional[dict]:
        """解析LLM返回的JSON（兼容markdown代码块包裹）"""
        content = content.strip()
        if content.startswith("```"):
            first_nl = content.find("\n")
            if first_nl != -1:
                content = content[first_nl + 1:]
            if content.rstrip().endswith("```"):
                content = content.rstrip()[:-3].rstrip()
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {e}")
            return None

    async def analyze_insight(self, metrics_context: str) -> Optional[dict]:
        """D2: AI趋势洞察 - 基于集群状态生成结构化洞察"""
        try:
            content = await self._call_with_retry(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": metrics_context},
                ],
                temperature=0.5,
                max_tokens=500,
            )
            return self._parse_json_response(content)
        except Exception as e:
            logger.error(f"AI洞察分析失败: {e}")
            return None

    async def interpret_prediction(self, pred_context: str) -> Optional[str]:
        """D3: AI预测解读 - 返回纯文本趋势判断"""
        try:
            content = await self._call_with_retry(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": pred_context},
                ],
                temperature=0.5,
                max_tokens=200,
            )
            return content.strip()
        except Exception as e:
            logger.error(f"AI预测解读失败: {e}")
            return None

    async def detect_anomalies(self, gpu_data_str: str) -> Optional[dict]:
        """D1: AI异常模式检测 - 识别阈值检测发现不了的异常"""
        try:
            content = await self._call_with_retry(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": gpu_data_str},
                ],
                temperature=0.3,
                max_tokens=800,
            )
            return self._parse_json_response(content)
        except Exception as e:
            logger.error(f"AI异常检测失败: {e}")
            return None

    async def evaluate_schedule(self, context: str) -> Optional[dict]:
        """D4: AI调度闭环反思 - 评估上次调度效果"""
        try:
            content = await self._call_with_retry(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": context},
                ],
                temperature=0.3,
                max_tokens=600,
            )
            return self._parse_json_response(content)
        except Exception as e:
            logger.error(f"AI调度评估失败: {e}")
            return None

    @staticmethod
    def _extract_suggestions(text: str) -> list[str]:
        """从回复中提取建议列表"""
        suggestions = []
        for line in text.split("\n"):
            line = line.strip()
            if line and (line.startswith("- ") or line.startswith("* ") or
                         (len(line) > 2 and line[0].isdigit() and line[1] in ".、")):
                suggestions.append(line.lstrip("-*0123456789.、 "))
        return suggestions[:5]
