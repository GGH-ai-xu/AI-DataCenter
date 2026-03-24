"""Pydantic数据模型 - 统一的请求/响应Schema"""

from pydantic import BaseModel, Field
from typing import Optional


# ========== GPU相关 ==========

class GPUStatus(BaseModel):
    """单张GPU实时状态"""
    index: int
    name: str
    temperature: int
    power_usage: float
    power_limit: float
    gpu_utilization: int
    memory_utilization: int
    memory_used: int
    memory_total: int
    memory_free: int
    fan_speed: int
    clock_sm: int
    clock_mem: int
    timestamp: float


class GPUListResponse(BaseModel):
    gpus: list[GPUStatus]


# ========== 进程/任务相关 ==========

class ProcessInfo(BaseModel):
    pid: int
    gpu_index: int
    gpu_memory_used: int
    name: str
    username: str
    command: str
    cpu_percent: float
    create_time: float
    priority: str = "normal"  # urgent / normal / deferrable


class TaskActionRequest(BaseModel):
    pid: int = Field(gt=0)


class PowerLimitRequest(BaseModel):
    gpu_index: int = Field(ge=0)
    power_limit: int = Field(ge=100, le=350)


# ========== 调度相关 ==========

class ScheduleAction(BaseModel):
    """单条调度动作"""
    action: str  # set_power_limit / pause_task / resume_task
    target: dict  # 动作参数
    reason: str  # 可解释原因


class ScheduleStrategy(BaseModel):
    """调度策略（可由LLM生成）"""
    actions: list[ScheduleAction]
    summary: str
    estimated_power_saving: Optional[float] = None


# ========== 告警相关 ==========

class Alert(BaseModel):
    id: Optional[int] = None
    gpu_index: int
    alert_type: str  # temperature / power / memory
    severity: str  # warning / critical
    message: str
    value: float
    threshold: float
    timestamp: float
    acknowledged: bool = False


# ========== AI对话 ==========

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class ChatResponse(BaseModel):
    reply: str
    suggestions: list[str] = []


# ========== 任务优先级 ==========

class TaskPriorityUpdate(BaseModel):
    pid: int
    priority: str = Field(pattern=r"^(urgent|normal|deferrable)$")
