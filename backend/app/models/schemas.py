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
    dry_run: bool = False
    acknowledge_risk: bool = False


class PowerLimitRequest(BaseModel):
    gpu_index: int = Field(ge=0)
    power_limit: int = Field(ge=100, le=350)
    dry_run: bool = False
    acknowledge_risk: bool = False


# ========== 调度相关 ==========

class PowerBudgetConfigRequest(BaseModel):
    enabled: bool
    total_power_budget: int = Field(ge=400, le=5000)


class ScheduleRunRequest(BaseModel):
    dry_run: bool = False
    acknowledge_risk: bool = False

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


# ========== 用户治理规则 ==========

class UserGovernanceRuleUpdate(BaseModel):
    username: str = Field(min_length=1, max_length=120)
    role: str = Field(default="member", pattern=r"^(protected|member|restricted)$")
    max_tasks: int = Field(default=4, ge=1, le=64)
    max_gpu_count: int = Field(default=1, ge=1, le=16)
    max_memory_gb: float = Field(default=8.0, ge=1, le=1024)
    allow_preempt: bool = True
    note: str = Field(default="", max_length=200)
