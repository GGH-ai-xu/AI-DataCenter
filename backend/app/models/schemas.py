"""Pydantic数据模型 - 统一的请求/响应Schema"""

from pydantic import BaseModel, Field
from typing import Optional


# ========== GPU相关 ==========

class GPUStatus(BaseModel):
    """单张GPU实时状态"""
    index: int
    name: str
    uuid: str = ""
    pci_bus_id: str = ""
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
    available: bool = True
    status: str = "ok"
    error: str = ""
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
    manageable: bool = True
    process_category: str = "governable"
    manageable_reason_code: str = ""
    manageable_summary: str = ""
    manageable_reason: str = ""
    is_background_process: bool = False


class TaskActionRequest(BaseModel):
    pid: int = Field(gt=0)
    acknowledge_risk: bool = False


class PowerLimitRequest(BaseModel):
    gpu_index: int = Field(ge=0)
    power_limit: int = Field(ge=100, le=350)
    acknowledge_risk: bool = False


# ========== 调度相关 ==========

class PowerBudgetConfigRequest(BaseModel):
    enabled: bool
    total_power_budget: int = Field(ge=400, le=5000)


class ScheduleRunRequest(BaseModel):
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


class AIControlPlanRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class AIGraphStrategyRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    max_nodes: int = Field(default=10, ge=4, le=16)
    max_relationships: int = Field(default=12, ge=4, le=24)


class AIControlAction(BaseModel):
    action: str = Field(
        pattern=r"^(set_power_limit|pause_task|resume_task|terminate_task|set_task_priority|configure_budget|run_schedule_once)$"
    )
    target: dict = Field(default_factory=dict)
    reason: str = Field(default="", max_length=500)


class AIControlExecuteRequest(BaseModel):
    message: str = Field(default="", max_length=2000)
    actions: list[AIControlAction] = Field(default_factory=list)
    acknowledge_risk: bool = False


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


# ========== 接入配置 ==========

class ConnectionConfigRequest(BaseModel):
    mode: str = Field(default="local", pattern=r"^(local|remote)$")
    agent_url: Optional[str] = Field(default=None, max_length=300)
    agent_label: str = Field(default="", max_length=120)


class ProviderConfigRequest(BaseModel):
    provider_type: str = Field(pattern=r"^(http_local|http_remote|ssh_linux)$")
    label: str = Field(default="", max_length=120)
    agent_url: Optional[str] = Field(default=None, max_length=300)
    host: Optional[str] = Field(default=None, max_length=255)
    port: Optional[int] = Field(default=None, ge=1, le=65535)
    username: Optional[str] = Field(default=None, max_length=120)
    auth_type: Optional[str] = Field(default=None, pattern=r"^(password|private_key)$")
    sudo_enabled: bool = False
    host_fingerprint: Optional[str] = Field(default=None, max_length=200)


class CredentialPayloadRequest(BaseModel):
    password: str = Field(default="", max_length=5000)
    private_key: str = Field(default="", max_length=20000)
    private_key_passphrase: str = Field(default="", max_length=5000)
    sudo_password: str = Field(default="", max_length=5000)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=500)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=500)
    new_password: str = Field(min_length=8, max_length=500)


class CreateUserRequest(BaseModel):
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8, max_length=500)
    role: str = Field(default="member", pattern=r"^(admin|member)$")
    must_change_password: bool = True


class ResetPasswordRequest(BaseModel):
    password: str = Field(min_length=8, max_length=500)
    must_change_password: bool = True


class ProviderBackedImportRequest(BaseModel):
    mode: str = Field(default="local", pattern=r"^(local|remote)$")
    agent_url: Optional[str] = Field(default=None, max_length=300)
    agent_label: str = Field(default="", max_length=120)
    saved_host_id: Optional[int] = Field(default=None, ge=1)
    provider: Optional[ProviderConfigRequest] = None
    credentials: CredentialPayloadRequest = Field(default_factory=CredentialPayloadRequest)

    def provider_payload(self) -> dict:
        if self.provider is not None:
            return self.provider.model_dump(exclude_none=True)
        return {
            "provider_type": "http_remote" if self.mode == "remote" else "http_local",
            "agent_url": self.agent_url,
            "label": self.agent_label,
        }

    def credential_payload(self) -> dict:
        return self.credentials.model_dump()


class ImportScanRequest(ProviderBackedImportRequest):
    pass


class ImportCommitRequest(ProviderBackedImportRequest):
    gpu_indexes: list[int] = Field(default_factory=list)


# ========== 图谱导入与知识入图 ==========

class GraphNodeDraft(BaseModel):
    id: str = Field(default="", max_length=120)
    label: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=2000)
    source: str = Field(default="", max_length=120)
    mode: str = Field(default="paper", pattern=r"^(paper|optimization)$")
    source_type: str = Field(default="", max_length=120)
    domain_tag: str = Field(default="", max_length=120)
    scenario: str = Field(default="", max_length=200)
    paper_title: str = Field(default="", max_length=300)


class GraphRelationDraft(BaseModel):
    from_id: str = Field(min_length=1, max_length=120)
    to_id: str = Field(min_length=1, max_length=120)
    type: str = Field(min_length=1, max_length=40)
    description: str = Field(default="", max_length=1000)
    source: str = Field(default="", max_length=120)
    mode: str = Field(default="paper", pattern=r"^(paper|optimization)$")
    source_type: str = Field(default="", max_length=120)
    domain_tag: str = Field(default="", max_length=120)
    scenario: str = Field(default="", max_length=200)
    paper_title: str = Field(default="", max_length=300)


class GraphDraftPayload(BaseModel):
    title: str = Field(default="", max_length=300)
    mode: str = Field(default="paper", pattern=r"^(paper|optimization)$")
    source: str = Field(default="paper", max_length=120)
    source_type: str = Field(default="", max_length=120)
    domain_tag: str = Field(default="", max_length=120)
    scenario: str = Field(default="", max_length=200)
    nodes: list[GraphNodeDraft] = Field(default_factory=list)
    relations: list[GraphRelationDraft] = Field(default_factory=list)


class GraphDraftRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    abstract: str = Field(default="", max_length=8000)
    content: str = Field(default="", max_length=30000)
    mode: str = Field(default="paper", pattern=r"^(paper|optimization)$")
    source: str = Field(default="paper", max_length=120)
    source_type: str = Field(default="", max_length=120)
    domain_tag: str = Field(default="", max_length=120)
    scenario: str = Field(default="", max_length=200)


class GraphExecuteRequest(BaseModel):
    graph: GraphDraftPayload
    cypher: str = Field(default="", max_length=50000)
    source: str = Field(default="", max_length=120)


class GraphQaRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    max_nodes: int = Field(default=8, ge=3, le=16)
    max_relationships: int = Field(default=10, ge=2, le=20)


class GraphSummaryResponse(BaseModel):
    ready: bool = False
    configured: bool = False
    dependency_installed: bool = False
    neo4j_connected: bool = False
    local_start_available: bool = False
    database: str = Field(default="", max_length=120)
    paper_count: int = 0
    node_count: int = 0
    relation_count: int = 0
    local_start_message: str = Field(default="", max_length=500)
    message: str = Field(default="", max_length=500)


# ========== LLM 配置 ==========

class LLMConfigRequest(BaseModel):
    enabled: bool = True
    base_url: str = Field(default="", max_length=500)
    model: str = Field(default="", max_length=200)
    api_key: Optional[str] = Field(default="", max_length=500)
    keep_existing_key: bool = True
