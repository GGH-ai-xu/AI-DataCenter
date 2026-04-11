"""Pydantic数据模型 - 统一的请求/响应Schema"""

from typing import Any, Optional

from pydantic import BaseModel, Field


TASK_KIND_PATTERN = r"^(training|inference_service|interactive_session|batch_compute|maintenance)$"
LIFECYCLE_KIND_PATTERN = r"^(batch|service|session)$"
CHECKPOINT_POLICY_PATTERN = r"^(none|app_managed)$"


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


# ========== 集群控制面 ==========
class ClusterQueueResponse(BaseModel):
    queue_id: str
    name: str
    state: str
    default_priority: int


class ClusterJobResponse(BaseModel):
    job_id: str
    queue_id: str
    tenant_id: str
    project_id: str
    submitter_id: str
    job_type: str
    task_kind: str = Field(default="batch_compute", pattern=TASK_KIND_PATTERN)
    lifecycle_kind: str = Field(default="batch", pattern=LIFECYCLE_KIND_PATTERN)
    entrypoint: str
    status: str
    priority: int
    service_ports: list[int] = Field(default_factory=list)
    checkpoint_policy: str = Field(default="none", pattern=CHECKPOINT_POLICY_PATTERN)
    runtime_profile: dict[str, Any] = Field(default_factory=dict)


class ClusterAllocationResponse(BaseModel):
    allocation_id: str
    job_id: str
    node_id: str
    status: str
    execution_backend: str


class ClusterJobSubmitRequest(BaseModel):
    job_id: str = Field(min_length=1, max_length=120)
    tenant_id: str = Field(min_length=1, max_length=120)
    project_id: str = Field(min_length=1, max_length=120)
    queue_id: str = Field(min_length=1, max_length=120)
    submitter_id: str = Field(min_length=1, max_length=120)
    job_type: str = Field(min_length=1, max_length=80)
    task_kind: str = Field(default="batch_compute", pattern=TASK_KIND_PATTERN)
    lifecycle_kind: str = Field(default="batch", pattern=LIFECYCLE_KIND_PATTERN)
    entrypoint: str = Field(min_length=1, max_length=500)
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    resource_request: dict = Field(default_factory=dict)
    placement_constraints: dict = Field(default_factory=dict)
    priority: int = 50
    preemptible: bool = True
    max_retries: int = Field(default=0, ge=0, le=20)
    timeout_seconds: int = Field(default=0, ge=0)
    service_ports: list[int] = Field(default_factory=list)
    checkpoint_policy: str = Field(default="none", pattern=CHECKPOINT_POLICY_PATTERN)
    runtime_profile: dict[str, Any] = Field(default_factory=dict)


class ClusterJobSubmitResponse(BaseModel):
    job_id: str
    state: str
    plan_type: str


class ClusterControllerConfigRequest(BaseModel):
    enabled: Optional[bool] = None
    interval_seconds: Optional[float] = Field(default=None, ge=1, le=3600)


class ClusterJobCheckpointRequest(BaseModel):
    timeout_seconds: int = Field(default=30, ge=1, le=3600)


class ClusterJobRestoreRequest(BaseModel):
    checkpoint_id: str = Field(default="", max_length=120)


# ========== 统一控制面 ==========

class ControlCommandCreateRequest(BaseModel):
    capability_name: str = Field(min_length=1, max_length=120)
    arguments: dict = Field(default_factory=dict)
    acknowledge_risk: bool = False
    dry_run: bool = False
    reason: str = Field(default="", max_length=500)
    permission_mode: str = Field(default="", max_length=40)
    source_page: str = Field(default="", max_length=120)
    related_session_id: str = Field(default="", max_length=120)


class ControlCommandApprovalRequest(BaseModel):
    approved: bool
    comment: str = Field(default="", max_length=500)


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
    session_id: str = Field(default="", max_length=120)


class ChatResponse(BaseModel):
    reply: str
    suggestions: list[str] = []


class AiWorkbenchDispatchRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    session_id: str = Field(default="", max_length=120)


class AiWorkbenchDispatchResponse(BaseModel):
    route_kind: str = Field(pattern=r"^(chat|runtime)$")
    reply_mode: Optional[str] = Field(default=None, pattern=r"^(inline|stream)$")
    reply: str = ""
    message: str = ""


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


# ========== LLM 配置 ==========

class LLMConfigRequest(BaseModel):
    enabled: bool = True
    base_url: str = Field(default="", max_length=500)
    model: str = Field(default="", max_length=200)
    api_key: Optional[str] = Field(default="", max_length=500)
    keep_existing_key: bool = True


class AgentRuntimeStartRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    permission_mode: str = Field(default="low", pattern=r"^(high|low)$")
    session_id: str = Field(default="", max_length=120)


class AgentRuntimeChatTurnRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    reply: str = Field(min_length=1, max_length=8000)
    permission_mode: str = Field(default="low", pattern=r"^(high|low)$")
    session_id: str = Field(default="", max_length=120)
    reply_mode: str = Field(default="inline", pattern=r"^(inline|stream)$")
    suggestions: list[str] = Field(default_factory=list, max_length=8)


class AgentRuntimeApprovalRequest(BaseModel):
    approved: bool


class AgentRuntimeSessionResponse(BaseModel):
    session_id: str
    status: str
    permission_mode: str = Field(pattern=r"^(high|low)$")
    summary: str = ""
    requires_approval: bool = False
