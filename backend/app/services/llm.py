"""LLM集成服务 - 基于OpenAI兼容接口的AI能耗分析与调度建议"""

import json
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


class LLMService:
    """LLM服务 - 支持对话和调度策略生成"""

    def __init__(self, api_key: str, base_url: str, model: str):
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model

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
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=2000,
            )
            reply = response.choices[0].message.content
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
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=2000,
            )
            content = response.choices[0].message.content
            # 解析JSON（兼容markdown代码块包裹）
            content = content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1]
                content = content.rsplit("```", 1)[0]
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
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.5,
                max_tokens=3000,
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"报告生成失败：{str(e)}"

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
