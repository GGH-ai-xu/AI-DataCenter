"""LLM集成服务 - 基于OpenAI兼容接口的AI能耗分析与调度建议"""

import json
import asyncio
import logging
from typing import Optional

from openai import AsyncOpenAI
from app.services.goal_runtime.session_context import format_session_context_for_prompt
from app.services.optimization_ontology import (
    build_graph_extract_prompt,
    graph_source_default,
    graph_source_type_default,
    normalize_graph_mode,
)

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

CONTROL_PROMPT = """你是 GPU 治理工作台里的 AI 执行控制台规划器。

你的任务不是直接执行动作，而是把用户的自然语言要求翻译成“可审核、可执行”的结构化动作计划。

你只能使用以下动作：
1. set_power_limit -> {{"gpu_index": 0, "power_limit": 220}}
2. pause_task -> {{"pid": 1234}}
3. resume_task -> {{"pid": 1234}}
4. terminate_task -> {{"pid": 1234}}
5. set_task_priority -> {{"pid": 1234, "priority": "urgent|normal|deferrable"}}
6. configure_budget -> {{"enabled": true, "total_power_budget": 1200}}
7. run_schedule_once -> {{}}

要求：
- 只能引用上下文中真实存在的 GPU 编号和 PID
- 不要臆造 PID、GPU 编号、用户名
- 如果信息不足，就返回空 actions，并在 warnings 中说明需要什么信息
- terminate_task 属于高风险动作，只在用户明确表达“终止/结束进程”等强动作时使用
- 如果用户只是说“优化/处理一下”，优先给出更保守的动作，如 set_power_limit、set_task_priority、run_schedule_once
- 只返回 JSON，不要额外解释

返回格式：
{{
  "summary": "一句话说明 AI 打算怎么做",
  "risk_level": "low|medium|high",
  "requires_confirmation": true,
  "warnings": ["注意事项1", "注意事项2"],
  "actions": [
    {{
      "action": "pause_task",
      "target": {{"pid": 1234}},
      "reason": "为什么这样做"
    }}
  ]
}}"""

WORKBENCH_DISPATCH_PROMPT = """你是 AI 助手统一工作台的判路器。

你的任务是判断用户当前这句话应该进入：
1. chat
2. runtime

约束：
- 只能输出 JSON
- route_kind 只能是 chat 或 runtime
- 如果信息不足，返回 chat，并用 reply_mode=inline 给出追问
- 如果是明确问答，返回 chat，并用 reply_mode=stream
- 如果是明确执行请求且信息足够，返回 runtime
- 不允许输出第三种模式

返回格式：
{
  "route_kind": "chat|runtime",
  "reply_mode": "inline|stream",
  "reply": "仅 chat+inline 时填写",
  "message": "仅 runtime 时填写"
}"""

GRAPH_QA_PROMPT = """你是智算中心优化代码生成系统里的图谱问答助手。

你的目标是基于给定图谱证据回答用户问题。

要求：
- 回答必须引用证据里的真实实体、关系、指标
- 不允许编造论文、参数、实验结论
- 如果证据不足，要明确指出缺失点
- 优先给出结构化结论，方便前端渲染
- 只返回 JSON

返回格式：
{
  "summary": "一句话结论",
  "answer": "详细回答",
  "confidence": "low|medium|high",
  "evidence": [
    {"label": "证据标题", "detail": "证据说明"}
  ],
  "follow_ups": ["后续建议1", "后续建议2"]
}"""

GRAPH_STRATEGY_PROMPT = """你是智算中心优化代码生成系统里的本体 GraphRAG 策略生成助手。

你的目标是结合图谱证据和当前运行态，为用户生成可执行的优化策略与代码模板。

要求：
- 仅使用输入里提供的图谱证据与运行态信息
- 不允许虚构节点、性能收益或上线结果
- 先给出可落地策略，再给出代码模板
- 只返回 JSON

返回格式：
{
  "summary": "一句话策略摘要",
  "strategy": ["步骤1", "步骤2"],
  "code_template": "伪代码或配置模板",
  "risks": ["风险1", "风险2"],
  "evidence": [
    {"label": "图谱证据", "detail": "为何支持该策略"}
  ]
}"""


def _normalize_workbench_dispatch_result(parsed: dict, fallback_message: str) -> dict:
    route_kind = str(parsed.get("route_kind") or "").strip()
    reply_mode = str(parsed.get("reply_mode") or "").strip()
    reply = str(parsed.get("reply") or "").strip()
    message = str(parsed.get("message") or fallback_message).strip()

    if route_kind not in {"chat", "runtime"}:
        raise ValueError("AI 工作台判路结果缺少合法的 route_kind")
    if route_kind == "chat" and reply_mode not in {"inline", "stream"}:
        raise ValueError("AI 工作台判路结果缺少合法的 reply_mode")
    if route_kind == "chat" and reply_mode == "inline" and not reply:
        raise ValueError("AI 工作台判路结果缺少 inline reply")
    if route_kind == "runtime" and not message:
        raise ValueError("AI 工作台判路结果缺少 runtime message")

    return {
        "route_kind": route_kind,
        "reply_mode": reply_mode or None,
        "reply": reply,
        "message": message if route_kind == "runtime" else "",
    }


class LLMService:
    """LLM服务 - 支持对话和调度策略生成"""

    def __init__(self, api_key: str, base_url: str, model: str):
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    @staticmethod
    def _chunk_text(chunk) -> str:
        choices = getattr(chunk, "choices", []) or []
        if not choices:
            return ""
        delta = getattr(choices[0], "delta", None)
        return getattr(delta, "content", "") or ""

    @staticmethod
    def _strip_markdown_code_fence(content: str) -> str:
        text = (content or "").strip()
        fence_start = text.find("```")
        if fence_start < 0:
            return text
        first_nl = text.find("\n", fence_start)
        if first_nl == -1:
            return ""
        body = text[first_nl + 1:]
        fence_end = body.rfind("```")
        if fence_end >= 0:
            body = body[:fence_end]
        body = body.strip()
        return body

    @classmethod
    def parse_structured_json(cls, content: str, *, label: str) -> dict:
        text = cls._strip_markdown_code_fence(content)
        if not text:
            raise ValueError(f"{label}为空")

        decoder = json.JSONDecoder()
        start_indexes = [idx for idx in (text.find("{"), text.find("[")) if idx >= 0]
        candidates = [text]
        if start_indexes:
            first_json_index = min(start_indexes)
            if first_json_index > 0:
                candidates.append(text[first_json_index:])

        last_error = None
        seen = set()
        for candidate in candidates:
            if candidate in seen:
                continue
            seen.add(candidate)
            try:
                parsed, end = decoder.raw_decode(candidate)
            except json.JSONDecodeError as exc:
                last_error = exc
                continue
            trailing = candidate[end:].strip()
            if trailing:
                raise ValueError(f"{label}在 JSON 之后仍包含额外文本")
            if not isinstance(parsed, dict):
                raise ValueError(f"{label}必须是 JSON 对象")
            return parsed

        raise ValueError(f"{label}不是合法 JSON") from last_error

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

    async def _stream_with_retry(self, max_retries: int = 2, **kwargs):
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                response = await self.client.chat.completions.create(
                    stream=True,
                    **kwargs,
                )
                async for chunk in response:
                    text = self._chunk_text(chunk)
                    if text:
                        yield text
                return
            except Exception as e:
                last_error = e
                err_str = str(e).lower()
                if any(k in err_str for k in ("401", "403", "invalid_api_key", "quota")):
                    raise
                if attempt < max_retries:
                    wait = 2 ** attempt
                    logger.warning(f"LLM流式调用失败(第{attempt+1}次)，{wait}s后重试: {e}")
                    await asyncio.sleep(wait)
        raise last_error

    def supports_chat_stream(self) -> bool:
        return True

    def supports_control_plan_stream(self) -> bool:
        return True

    @staticmethod
    def _append_session_context(messages: list[dict], session_context: dict | None) -> None:
        if not session_context:
            return
        messages.append({
            "role": "system",
            "content": f"当前会话记忆上下文：\n{format_session_context_for_prompt(session_context)}",
        })

    async def chat(
        self,
        user_message: str,
        gpu_context: str = "",
        session_context: dict | None = None,
    ) -> dict:
        """AI对话 - 基于实时数据回答用户问题"""
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
        ]
        if gpu_context:
            messages.append({
                "role": "system",
                "content": f"当前GPU集群实时状态：\n{gpu_context}",
            })
        self._append_session_context(messages, session_context)
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

    async def chat_stream(
        self,
        user_message: str,
        gpu_context: str = "",
        session_context: dict | None = None,
    ):
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        if gpu_context:
            messages.append({
                "role": "system",
                "content": f"当前GPU集群实时状态：\n{gpu_context}",
            })
        self._append_session_context(messages, session_context)
        messages.append({"role": "user", "content": user_message})
        async for item in self._stream_with_retry(
            model=self.model,
            messages=messages,
            temperature=0.7,
            max_tokens=2000,
        ):
            yield item

    async def dispatch_workbench_message(
        self,
        user_message: str,
        gpu_context: str = "",
        session_context: dict | None = None,
    ) -> dict:
        messages = [{"role": "system", "content": WORKBENCH_DISPATCH_PROMPT}]
        if gpu_context:
            messages.append({
                "role": "system",
                "content": f"当前GPU集群实时状态：\n{gpu_context}",
            })
        self._append_session_context(messages, session_context)
        messages.append({"role": "user", "content": user_message})

        content = await self._call_with_retry(
            model=self.model,
            messages=messages,
            temperature=0.1,
            max_tokens=400,
        )
        parsed = self.parse_structured_json(content, label="AI 工作台判路结果")
        return _normalize_workbench_dispatch_result(parsed, user_message)

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
        try:
            return self.parse_structured_json(content, label="LLM 返回的 JSON")
        except ValueError as e:
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

    async def generate_control_plan(
        self, user_message: str, control_context: str
    ) -> Optional[dict]:
        """AI执行控制台 - 生成结构化动作计划"""
        prompt = (
            f"用户指令：{user_message}\n\n"
            f"当前工作台上下文：\n{control_context}\n\n"
            "请输出结构化动作计划 JSON。"
        )
        content = await self._call_with_retry(
            model=self.model,
            messages=[
                {"role": "system", "content": CONTROL_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=1500,
        )
        return self.parse_structured_json(
            content,
            label="LLM 返回的控制计划",
        )

    async def generate_control_plan_stream(
        self,
        user_message: str,
        control_context: str,
    ):
        prompt = (
            f"用户指令：{user_message}\n\n"
            f"当前工作台上下文：\n{control_context}\n\n"
            "请输出结构化动作计划 JSON。"
        )
        async for item in self._stream_with_retry(
            model=self.model,
            messages=[
                {"role": "system", "content": CONTROL_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=1500,
        ):
            yield item

    async def generate_graph_draft(
        self,
        title: str,
        abstract: str = "",
        content: str = "",
        mode: str = "paper",
        source: str = "paper",
        source_type: str = "",
        domain_tag: str = "",
        scenario: str = "",
    ) -> Optional[dict]:
        normalized_mode = normalize_graph_mode(mode)
        normalized_source = str(source or "").strip() or graph_source_default(normalized_mode)
        normalized_source_type = (
            str(source_type or "").strip()
            or graph_source_type_default(normalized_mode)
        )
        excerpt = (content or "").strip()
        if len(excerpt) > 12000:
            excerpt = excerpt[:12000].strip() + "\n...(已截断)"
        prompt = (
            f"模式：{normalized_mode}\n"
            f"来源：{normalized_source}\n"
            f"来源类型：{normalized_source_type}\n"
            f"领域标签：{(domain_tag or '').strip()}\n"
            f"适用场景：{(scenario or '').strip()}\n"
            f"标题：{title.strip()}\n\n"
            f"摘要：\n{(abstract or '').strip()}\n\n"
            f"正文片段：\n{excerpt}\n\n"
            "请严格输出固定 JSON。"
        )
        try:
            content = await self._call_with_retry(
                model=self.model,
                messages=[
                    {"role": "system", "content": build_graph_extract_prompt(normalized_mode)},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=2000,
            )
            return self._parse_json_response(content)
        except Exception as e:
            logger.error(f"知识图谱草稿生成失败: {e}")
            return None

    async def answer_graph_question(
        self,
        question: str,
        context_text: str,
    ) -> Optional[dict]:
        prompt = (
            f"用户问题：{question.strip()}\n\n"
            f"图谱证据：\n{context_text.strip()}\n\n"
            "请严格输出 JSON。"
        )
        try:
            content = await self._call_with_retry(
                model=self.model,
                messages=[
                    {"role": "system", "content": GRAPH_QA_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=1500,
            )
            parsed = self._parse_json_response(content)
            if parsed is not None:
                return parsed
            return {
                "summary": "图谱问答已生成",
                "answer": content.strip(),
                "confidence": "medium",
                "evidence": [],
                "follow_ups": [],
            }
        except Exception as e:
            logger.error(f"图谱问答生成失败: {e}")
            return None

    async def generate_graph_strategy_plan(
        self,
        goal: str,
        graph_context_text: str,
        runtime_context_text: str,
    ) -> Optional[dict]:
        prompt = (
            f"优化目标：{goal.strip()}\n\n"
            f"图谱证据：\n{graph_context_text.strip()}\n\n"
            f"当前运行态：\n{runtime_context_text.strip()}\n\n"
            "请严格输出 JSON。"
        )
        try:
            content = await self._call_with_retry(
                model=self.model,
                messages=[
                    {"role": "system", "content": GRAPH_STRATEGY_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=2000,
            )
            return self._parse_json_response(content)
        except Exception as e:
            logger.error(f"图谱策略生成失败: {e}")
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
