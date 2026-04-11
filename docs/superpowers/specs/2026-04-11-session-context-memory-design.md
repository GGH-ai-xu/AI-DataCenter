# Session Context Memory Design

## Goal

让同一 `session_id` 下的历史对话文本和 runtime 关键事件真正参与后续 LLM 调用，而不是只作为前端展示和事件存档存在。改造后，同一会话中的后续聊天、判路和执行规划都应具备连续上下文记忆。

## Current Problem

当前系统已经会复用同一个 `session_id`，并将 `UserMessageSubmitted`、`AssistantMessageGenerated`、`PlanCreated`、`AwaitingApproval`、`SessionCompleted`、`SessionFailed` 等事件落库。但这些历史事件主要用于：

- 前端按 `round_index` 重建会话展示
- 后端统计当前会话状态
- 审批和执行流程的事件追踪

现有 LLM 调用并不会系统性读取同一会话下的历史内容：

- `dispatch_workbench_message()` 只看当前一句话
- `chat()` / `chat_stream()` 只看当前一句话和当前 GPU 快照
- `build_reasoning_trace()` 只看当前请求和当前 runtime snapshot

结果是 UI 上看起来是一个会话，但模型实际按“多次彼此独立的单轮请求”处理。用户一旦说“继续刚才那个任务”“按前面的限制来”“它失败的原因是什么”，模型上下文并不完整。

## Desired Behavior

同一 `session_id` 下的后续请求应自动携带统一的会话上下文。该上下文至少覆盖：

- 最近若干轮原始用户/助手消息
- 更早轮次的压缩摘要
- runtime 关键状态和最近执行结果
- 当前用户请求

上下文必须同时注入三条调用链：

- AI 工作台判路
- 普通聊天回复
- runtime 规划 / 执行推理

如果会话过长，应保留最近原文，压缩更早历史后继续，而不是直接丢失记忆。若在完成压缩后仍超预算，应显式报错，而不是静默截断。

## Non-Goals

本阶段不做以下事项：

- 不修改数据库 schema
- 不增加新的会话摘要表
- 不使用额外 LLM 生成历史摘要
- 不改变前端会话交互模型
- 不引入 silent fallback 或静默裁剪

## Design Overview

新增一个统一的后端会话上下文构建器，负责从当前 session 记录和事件历史中生成结构化上下文对象。所有需要调用 LLM 的链路都只能通过该构建器获取上下文，不允许各调用点自行拼接 prompt。

建议新增模块：

- `backend/app/services/goal_runtime/session_context.py`

该模块提供一个面向服务层的入口，例如：

```python
async def build_session_context(
    store,
    session_id: str,
    current_message: str,
    *,
    recent_round_limit: int = 3,
    summary_round_limit: int = 12,
) -> dict:
    """Return a normalized session context payload for downstream LLM calls."""
```

## Context Shape

上下文构建器输出统一结构：

```python
{
    "session_id": "abc123",
    "current_request": {
        "message": "继续刚才那个任务",
    },
    "recent_messages": [
        {
            "round_index": 4,
            "messages": [
                {"role": "user", "content": "将 GPU 3 的功耗上限设置为 220W"},
                {"role": "assistant", "content": "计划已生成，等待审批。"},
            ],
        }
    ],
    "historical_summary": {
        "round_count": 3,
        "summary_lines": [
            "用户先查看了主机任务列表。",
            "随后要求对 GPU 3 做功耗治理。",
            "已确认目标 GPU 为 3，功耗上限目标为 220W。",
        ],
        "entities": {
            "gpu_indexes": [3],
            "job_ids": [],
            "pids": [],
            "nodes": [],
            "queues": [],
        },
        "constraints": [
            "保持当前导入范围",
        ],
    },
    "runtime_summary": {
        "latest_plan": "准备将 GPU 3 功耗上限设置为 220W",
        "approval_status": "approved",
        "latest_execution": "set_power_limit GPU 3 -> 220W succeeded",
        "latest_failure": "",
        "live_phase": "completed",
    },
}
```

该结构不是数据库 schema，只是运行时上下文载体。

## Event Extraction Rules

### Raw Conversation Rounds

最近原文只来自以下两类事件：

- `UserMessageSubmitted`
- `AssistantMessageGenerated`

它们按 `round_index` 分组后组成最近 N 轮原始消息。默认保留最近 `3` 轮完整原文。

### Historical Summary

更早轮次不再保留全文，而是转成确定性摘要。摘要不调用新的 LLM，只基于已有事件抽取：

- 历史用户目标
- 历史助手最终答复或状态结论
- 明确出现过的实体
- 反复出现的约束条件
- 关键执行结论

摘要输出是有限条数的字符串列表，不是自由长文本。构建器必须保证顺序稳定，同样的事件输入必须得到同样的摘要。

### Runtime Summary

runtime 摘要从以下事件中抽关键状态：

- `PlanCreated`
- `AwaitingApproval`
- `ApprovalResolved` / `ApprovalRejected`
- 执行动作相关事件
- `SessionCompleted`
- `SessionFailed`
- `LLMCallFailed`

提取逻辑只保留对下一轮理解最重要的信息：

- 最近一次计划摘要
- 当前审批状态
- 最近一次执行成功动作
- 最近一次失败原因
- 当前 live phase

不应把完整 runtime event 列表原样塞入 prompt。

## Compression Strategy

上下文裁剪顺序固定：

1. 保留当前请求
2. 保留最近 `3` 轮原始对话
3. 保留 runtime 关键摘要
4. 压缩更早历史摘要

压缩不是逐字符硬截断，而是按信息层级递减：

- 首先保留实体和最终结论
- 然后保留关键约束
- 最后才删除次要解释性语句

如果完成这一层压缩后仍超过预算，应抛出显式错误，例如：

```python
raise ValueError("session context exceeds safe prompt budget after compression")
```

系统必须把这个错误暴露到调用链，而不是静默继续。

## Integration Points

### 1. Workbench Dispatch

修改：

- `backend/app/services/llm.py`
- `backend/app/api/ai.py`
- 相关服务层调用点

`dispatch_workbench_message()` 新增 `session_context` 参数，并在 prompt 中引入：

- 会话历史摘要
- 最近几轮原文
- runtime 摘要
- 当前 GPU context
- 当前用户请求

这样判路器才能识别“继续刚才的执行任务”属于 runtime，而不是把它误判为普通聊天。

### 2. Chat / Chat Stream

修改：

- `backend/app/services/llm.py`
- `backend/app/api/ai.py`

`chat()` 和 `chat_stream()` 新增 `session_context` 参数。发送给模型的消息结构统一为：

- `system`: 原有系统提示
- `system`: 当前 GPU context
- `system`: 会话记忆上下文
- `user`: 当前请求

这会让同一会话里的聊天真正具备连续记忆。

### 3. Runtime Planning

修改：

- `backend/app/services/goal_runtime/reasoning_trace.py`
- `backend/app/services/goal_runtime/service.py`

`build_reasoning_trace()` 新增 `session_context` 参数，将其纳入 `request_payload` 和 `LLMRequestPrepared` 事件中。这样 runtime 规划链可以继承上轮确定的实体、约束和失败信息。

### 4. Goal Runtime Service

修改：

- `backend/app/services/goal_runtime/service.py`

在以下场景构建并传递会话上下文：

- 复用旧 `session_id` 发起新的 runtime round
- 同一 session 下追加新的 chat turn
- 工作台判路阶段需要知道当前会话历史

该服务仍然只负责 orchestration，不在这里直接拼 prompt 文本。

## Prompt Formatting

上下文对象进入 LLM 前，需要转换成稳定文本格式，建议新增一个只负责格式化的 helper，例如：

- `format_session_context_for_prompt(session_context: dict) -> str`

输出格式固定分段：

```text
会话历史摘要：
- 用户先查看了主机任务列表。
- 已确认目标 GPU 为 3，目标功耗上限为 220W。

最近对话原文：
第 4 轮
用户：继续刚才那个任务。
助手：计划已生成，等待审批。

运行态摘要：
- 最近计划：准备将 GPU 3 功耗上限设置为 220W。
- 审批状态：approved。
- 最近成功执行：set_power_limit GPU 3 -> 220W succeeded。
- 最近失败原因：无。
```

这样可以避免在不同调用链里各自发明格式。

## Error Handling

必须显式处理以下情况：

- `session_id` 不存在
- session 没有历史事件
- history 只有单侧消息，没有助手回复
- runtime event 缺少预期 payload
- 上下文压缩后仍超过预算

这些情况都应返回明确错误或空结构，不允许静默吞掉。

## Testing Strategy

### Unit Tests

新增：

- `tests/test_goal_runtime_session_context.py`

覆盖：

- 从多轮 chat/runtime 事件中提取最近原文
- 将更早轮次压缩成确定性摘要
- 提取 runtime 关键状态
- 预算压缩顺序正确
- 超预算时显式报错

### LLM Integration Contract Tests

扩充：

- `tests/test_goal_runtime_api.py`
- `tests/test_goal_runtime_planner.py`
- `tests/test_goal_runtime_capabilities.py`
- `tests/test_ai_workbench_dispatch_api.py`
- `tests/test_ai_chat_stream_api.py`
- `tests/test_llm_streaming.py`

覆盖：

- 同一 session 下第二轮聊天调用时，LLM 输入包含历史上下文
- 同一 session 下判路调用时，LLM 输入包含历史上下文
- 同一 session 下 runtime 规划时，`LLMRequestPrepared` 包含上下文

### Regression Focus

必须确认以下现有行为不回退：

- 会话列表和 round 展示仍正常
- 事件持久化格式不变
- 当前前端 transcript 重建逻辑不被破坏
- 无历史 session 时仍能正常首轮对话

## File-Level Change Plan

### New Files

- `backend/app/services/goal_runtime/session_context.py`
- `tests/test_goal_runtime_session_context.py`

### Modified Files

- `backend/app/services/goal_runtime/service.py`
- `backend/app/services/goal_runtime/reasoning_trace.py`
- `backend/app/services/llm.py`
- `backend/app/api/ai.py`
- 相关测试文件

## Risks

### Prompt Overgrowth

即使只保留最近 3 轮原文，某些长回复仍可能迅速膨胀。为避免不可控增长，本阶段摘要必须是确定性、有限条目的结构化文本。

### Summary Drift

确定性摘要不会“理解”语义，只会抽取稳定信号，因此摘要表达可能不如 LLM 摘要自然。但这属于可接受权衡，因为它保证可预测、可测试、无额外成本。

### Inconsistent Context Across Call Paths

如果聊天、判路、runtime 规划没有全部走统一构建器，会重新回到“会话表面连续，模型实际断裂”的状态。因此本设计要求三条路径统一依赖同一个构建器和格式化函数。

## Acceptance Criteria

满足以下条件时，本设计视为完成：

- 同一 `session_id` 下后续请求会自动注入历史上下文
- 历史上下文同时覆盖 chat、dispatch、runtime planning 三条链路
- 最近 3 轮保持原文，更早轮次压缩为确定性摘要
- runtime 关键信息被抽取并参与后续推理
- 历史过长时先压缩，压缩后仍超预算则显式报错
- 不修改数据库 schema
- 现有 session 展示与事件持久化行为不回退
