"""后端服务主入口 - FastAPI应用 + 数据采集循环 + WebSocket

核心职责：
1. 聚合Agent数据并存储到SQLite
2. 通过WebSocket实时推送给前端
3. 运行告警引擎和调度引擎
4. 提供REST API供前端调用
5. 集成LLM进行智能分析和调度
"""

import os
import asyncio
import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.services.agent_client import AgentClient
from app.services.data_store import DataStore
from app.services.llm import LLMService
from app.services.alert_engine import AlertEngine
from app.services.scheduler import SchedulerEngine
from app.services.energy_analytics import EnergyAnalytics
from app.services.governance import GovernanceService
from app.services.logging_config import configure_application_logging
from app.services.privacy import PrivacyService
from app.services.collection_pipeline import (
    collect_agent_snapshot,
)
from app.services.connection_settings import ConnectionSettingsService
from app.services.credential_cipher import CredentialCipher
from app.services.credential_store import CredentialStore
from app.services.import_context import ImportContextService
from app.services.http_agent_provider import HttpAgentProvider
from app.services.llm_settings import LLMSettingsService
from app.services.platform_auth_service import PlatformAuthService
from app.services.platform_identity_store import PlatformIdentityStore
from app.services.runtime_provider_manager import RuntimeProviderManager
from app.services.runtime_overview import build_health_payload
from app.services.runtime_snapshot import (
    build_runtime_failure_snapshot,
    build_runtime_snapshot,
    empty_runtime_snapshot,
)
from app.services.graph_store import GraphStore
from app.services.local_neo4j import LocalNeo4jService
from app.services.goal_runtime.platform_capabilities import (
    build_platform_capability_registry,
)
from app.services.goal_runtime.service import GoalRuntimeService
from app.services.cluster_control.control_plane import ClusterControlPlaneService
from app.services.control_plane import ControlPlaneService
from app.services.cluster_control.execution_backend import (
    HTTPAgentProcessBackend,
    LocalProcessBackend,
    SSHProcessBackend,
)
from app.services.cluster_control.execution_orchestrator import ExecutionOrchestrator
from app.services.cluster_control.scheduler_core import ClusterSchedulerCore
from app.services.saved_host_service import SavedHostService
from app.services.ssh_linux_provider import SshLinuxProvider
from app.services.user_workspace_service import UserWorkspaceService
from app.services.workspace_context import (
    PUBLIC_WORKSPACE_KEY,
    current_workspace_key,
    workspace_scope,
)
from app.services.workspace_proxies import (
    WorkspaceAgentProxy,
    WorkspaceImportContextProxy,
    WorkspaceRuntimeProxy,
)
from app.ws.realtime import ws_manager

load_dotenv()
configure_application_logging()
logger = logging.getLogger(__name__)
RUNTIME_INVALID_REASON = "当前导入目标不可达，需要重新导入"


class SPAStaticFiles(StaticFiles):
    """为 Vue Router history 模式提供 index.html 回退。"""

    async def get_response(self, path: str, scope):
        try:
            response = await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code != 404:
                raise
            return await super().get_response("index.html", scope)

        if response.status_code == 404:
            return await super().get_response("index.html", scope)
        return response


class AppState:
    """应用全局状态，存储共享服务实例"""
    agent: object
    store: DataStore
    llm: LLMService | None
    alert_engine: AlertEngine
    scheduler: SchedulerEngine
    energy: EnergyAnalytics
    governance: GovernanceService
    privacy: PrivacyService
    connection: ConnectionSettingsService
    identity: PlatformIdentityStore
    platform_auth: PlatformAuthService
    credentials: CredentialStore
    saved_hosts: SavedHostService
    import_context: ImportContextService
    llm_settings: LLMSettingsService
    runtime: RuntimeProviderManager
    workspaces: UserWorkspaceService
    graph: GraphStore
    local_neo4j: LocalNeo4jService
    goal_runtime: GoalRuntimeService
    control_plane: ControlPlaneService
    cluster_scheduler: ClusterSchedulerCore
    cluster_orchestrator: ExecutionOrchestrator
    cluster_control: ClusterControlPlaneService
    _legacy_runtime_snapshot: dict
    _collect_task: asyncio.Task | None = None
    _cleanup_task: asyncio.Task | None = None

    @property
    def latest_runtime_snapshot(self) -> dict:
        workspaces = getattr(self, "workspaces", None)
        if workspaces is None:
            return getattr(self, "_legacy_runtime_snapshot", empty_runtime_snapshot())
        return workspaces.current_snapshot()

    @latest_runtime_snapshot.setter
    def latest_runtime_snapshot(self, snapshot: dict) -> None:
        workspaces = getattr(self, "workspaces", None)
        if workspaces is None:
            self._legacy_runtime_snapshot = snapshot
            return
        workspaces.set_current_snapshot(snapshot)


app_state = AppState()
app_state.latest_runtime_snapshot = empty_runtime_snapshot()


def resolve_runtime_dir() -> str:
    configured_home = os.getenv("GPU_GOV_HOME", "").strip()
    if configured_home:
        return os.path.join(configured_home, "runtime")
    return os.getenv(
        "RUNTIME_DIR",
        os.path.join(os.path.dirname(__file__), "..", "..", "runtime"),
    )


def bind_llm_service(llm_service: LLMService | None):
    app_state.llm = llm_service
    if getattr(app_state, "scheduler", None):
        app_state.scheduler.llm = llm_service
    if getattr(app_state, "energy", None):
        app_state.energy.llm = llm_service


async def build_runtime_provider(target, secret):
    if target.provider_type in {"http_local", "http_remote"}:
        return HttpAgentProvider(target)
    if target.provider_type == "ssh_linux":
        return SshLinuxProvider(target, secret)
    raise ValueError(f"unsupported provider type: {target.provider_type}")


def assign_active_provider(provider):
    return None


def build_runtime_target_payload(connection_state: dict) -> dict:
    provider_type = connection_state.get("provider_type")
    if provider_type:
        return {
            "provider_type": provider_type,
            "label": connection_state.get("agent_label") or connection_state.get("label"),
            "agent_url": connection_state.get("agent_url"),
            "host": connection_state.get("host"),
            "port": connection_state.get("port"),
            "username": connection_state.get("username"),
            "auth_type": connection_state.get("auth_type"),
            "sudo_enabled": connection_state.get("sudo_enabled", False),
            "host_fingerprint": connection_state.get("host_fingerprint"),
            "credential_id": connection_state.get("credential_id"),
        }
    return {
        "provider_type": "http_remote" if connection_state.get("mode") == "remote" else "http_local",
        "label": connection_state.get("agent_label"),
        "agent_url": connection_state.get("agent_url"),
    }


async def cleanup_loop():
    """定期清理过期历史数据（每24小时）"""
    while True:
        await asyncio.sleep(86400)
        try:
            await app_state.store.cleanup_old_data(days=7)
            logger.info("数据库过期数据清理完成")
        except Exception as e:
            logger.error(f"数据库清理失败: {e}")


async def runtime_status_payload() -> dict:
    return await app_state.runtime.status()


async def broadcast_runtime_state(import_context: dict) -> None:
    await ws_manager.broadcast(current_workspace_key(), {
        "type": "runtime",
        "runtime": await runtime_status_payload(),
        "import_context": import_context,
        "workspace_ready": bool(import_context.get("valid")),
    })


async def handle_runtime_failure(reason: str) -> tuple[dict, dict]:
    logger.warning("运行时故障，准备重连: %s", reason)
    runtime_status = await app_state.runtime.reconnect()
    if runtime_status["status"] == "connected":
        assign_active_provider(await app_state.runtime.current_provider())
        logger.warning("运行时已恢复连接，provider=%s", runtime_status.get("provider_type") or "unknown")
        import_context = app_state.import_context.snapshot()
        app_state.latest_runtime_snapshot = build_runtime_failure_snapshot(
            runtime_status=runtime_status,
            import_context_state=import_context,
        )
        await broadcast_runtime_state(import_context)
        return runtime_status, import_context

    if runtime_status["status"] == "invalid":
        import_context = app_state.import_context.mark_invalid(RUNTIME_INVALID_REASON)
    else:
        import_context = app_state.import_context.snapshot()
    app_state.latest_runtime_snapshot = build_runtime_failure_snapshot(
        runtime_status=runtime_status,
        import_context_state=import_context,
    )
    await broadcast_runtime_state(import_context)
    return runtime_status, import_context


def resolve_import_context_snapshot(
    runtime_status: dict,
    agent_health: dict | None,
    gpus: list[dict],
) -> dict:
    status = runtime_status.get("status")
    if status == "connected":
        return app_state.import_context.validate_runtime(agent_health, gpus)
    if status == "invalid":
        return app_state.import_context.mark_invalid(RUNTIME_INVALID_REASON)
    return app_state.import_context.snapshot()


async def _load_health_runtime_state(runtime_status: dict) -> tuple[dict | None, dict]:
    try:
        agent_health = await app_state.agent.health_check()
        gpus = await app_state.agent.get_all_gpus() if agent_health else []
        import_context = resolve_import_context_snapshot(runtime_status, agent_health, gpus)
        return agent_health, import_context
    except Exception as exc:
        logger.warning("健康检查读取运行时失败: %s", exc)
        if runtime_status.get("status") == "invalid":
            return None, app_state.import_context.mark_invalid(RUNTIME_INVALID_REASON)
        return None, app_state.import_context.snapshot()


async def collect_loop():
    """数据采集循环 - 定时从Agent拉数据、存储、推送、检测告警"""
    interval = float(os.getenv("COLLECT_INTERVAL", "2"))
    logger.info(f"数据采集循环启动，间隔 {interval}s")

    while True:
        workspaces = app_state.workspaces.all_workspaces()
        await asyncio.gather(
            *(_collect_workspace_cycle(workspace.key) for workspace in workspaces),
            return_exceptions=True,
        )
        await asyncio.sleep(interval)


async def _collect_workspace_cycle(workspace_key: str) -> None:
    with workspace_scope(workspace_key):
        try:
            snapshot, priorities = await asyncio.gather(
                collect_agent_snapshot(app_state.agent),
                app_state.store.get_all_task_priorities(),
            )
            gpus = snapshot["gpus"]
            system = snapshot["system"]
            processes = snapshot["processes"]
            runtime_online = bool(gpus) or bool(processes) or system is not None
            import_context = app_state.import_context.validate_runtime(
                {"status": "ok"} if runtime_online else None,
                gpus,
            )
            if not runtime_online:
                await _log_runtime_failure("runtime returned no data")
                return
            runtime_status = await app_state.runtime.record_success()
            runtime_snapshot = build_runtime_snapshot(
                import_context=app_state.import_context,
                privacy=app_state.privacy,
                system=system,
                gpus=gpus,
                processes=processes,
                priorities=priorities,
                agent_health={"status": "ok"},
                runtime_status=runtime_status,
                import_context_state=import_context,
            )
            app_state.latest_runtime_snapshot = runtime_snapshot
            scoped = runtime_snapshot["scoped"]
            alerts = app_state.alert_engine.check_all_gpus(scoped["gpus"])
            await app_state.store.save_collection_cycle(scoped["gpus"], scoped["processes"], alerts)
            await asyncio.gather(
                app_state.scheduler.tick(scoped["gpus"], scoped["processes"]),
                ws_manager.broadcast(
                    workspace_key,
                    {
                        "type": "realtime",
                        "gpus": scoped["gpus"],
                        "system": scoped["system"],
                        "processes": scoped["public_processes"],
                        "alerts": alerts,
                        "runtime": runtime_status,
                        "import_context": import_context,
                        "workspace_ready": bool(import_context.get("valid")),
                    },
                ),
            )
        except Exception as exc:
            logger.exception("数据采集异常: %s", exc)
            await _log_runtime_failure(str(exc))


async def _log_runtime_failure(reason: str) -> None:
    runtime_status, _ = await handle_runtime_failure(reason)
    if runtime_status["status"] == "connected":
        return
    logger.warning(
        "运行时当前不可用，status=%s failures=%s",
        runtime_status["status"],
        runtime_status["reconnect_failures"],
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    # 初始化服务
    default_agent_url = os.getenv("AGENT_URL", "http://127.0.0.1:8001")
    db_path = os.getenv("DB_PATH", "./data/history.db")
    runtime_dir = resolve_runtime_dir()
    connection_config_path = os.getenv(
        "CONNECTION_CONFIG_PATH",
        os.path.join(runtime_dir, "connection.json"),
    )
    llm_config_path = os.getenv(
        "LLM_CONFIG_PATH",
        os.path.join(runtime_dir, "llm.json"),
    )
    graph_uri = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687")
    graph_username = os.getenv("NEO4J_USER", "neo4j")
    graph_password = os.getenv("NEO4J_PASSWORD", "")
    graph_database = os.getenv("NEO4J_DATABASE", "neo4j")
    import_config_path = os.getenv(
        "IMPORT_CONTEXT_PATH",
        os.path.join(runtime_dir, "import-context.json"),
    )
    credential_config_path = os.getenv(
        "CREDENTIAL_STORE_PATH",
        os.path.join(runtime_dir, "credentials.json"),
    )
    identity_db_path = os.getenv(
        "PLATFORM_IDENTITY_DB_PATH",
        os.path.join(runtime_dir, "platform_identity.db"),
    )
    master_key = os.getenv("GPU_GOV_MASTER_KEY", "").strip()

    app_state.connection = ConnectionSettingsService(connection_config_path, default_agent_url)
    app_state.llm_settings = LLMSettingsService(llm_config_path)
    connection_settings = app_state.connection.load()
    app_state.llm_settings.load()
    cipher = CredentialCipher(master_key) if master_key else None
    app_state.identity = PlatformIdentityStore(identity_db_path)
    await app_state.identity.init()
    app_state.platform_auth = PlatformAuthService(app_state.identity)
    bootstrap_notice = await app_state.platform_auth.ensure_default_admin()
    if bootstrap_notice:
        logger.warning(
            "默认管理员已初始化: username=%s default_password=%s status=%s",
            bootstrap_notice["username"],
            bootstrap_notice["default_password"],
            bootstrap_notice["status"],
        )
    app_state.credentials = CredentialStore(credential_config_path, cipher)
    app_state.saved_hosts = SavedHostService(app_state.identity, app_state.credentials)
    app_state.workspaces = UserWorkspaceService(
        runtime_root=runtime_dir,
        default_local_url=app_state.connection.default_local_url,
        default_target_reader=lambda: app_state.connection.normalize_payload(
            build_runtime_target_payload(app_state.connection.load())
        ),
        default_secret_reader=lambda target: (
            app_state.credentials.read(target.credential_id)
            if target.credential_id
            else {}
        ),
        provider_factory=build_runtime_provider,
    )
    await app_state.workspaces.ensure_workspace(PUBLIC_WORKSPACE_KEY)
    app_state.import_context = WorkspaceImportContextProxy(app_state.workspaces)
    app_state.runtime = WorkspaceRuntimeProxy(app_state.workspaces)
    app_state.agent = WorkspaceAgentProxy(app_state.workspaces)
    app_state.graph = GraphStore(
        uri=graph_uri,
        username=graph_username,
        password=graph_password,
        database=graph_database,
    )
    app_state.local_neo4j = LocalNeo4jService()
    app_state.store = DataStore(db_path)
    await app_state.store.init()
    await app_state.store.upsert_cluster_queue(
        {
            "queue_id": "default",
            "name": "Default",
            "state": "active",
            "default_priority": 50,
        }
    )
    app_state.privacy = PrivacyService()
    removed_snapshots = await app_state.store.cleanup_untrusted_optimization_history()
    if removed_snapshots:
        logger.warning(f"已清理 {removed_snapshots} 条不可信的优化历史快照")

    # 告警引擎
    app_state.alert_engine = AlertEngine(
        temp_threshold=int(os.getenv("ALERT_TEMP_THRESHOLD", "85")),
        power_threshold=int(os.getenv("ALERT_POWER_THRESHOLD", "320")),
        memory_threshold=int(os.getenv("ALERT_MEMORY_THRESHOLD", "90")),
    )

    bind_llm_service(app_state.llm_settings.build_service())
    if app_state.llm:
        llm_snapshot = app_state.llm_settings.snapshot(True)
        logger.info(
            "LLM服务已初始化，来源=%s，模型=%s",
            llm_snapshot["source"],
            llm_snapshot["model"],
        )
    else:
        logger.warning("LLM 未配置或未启用，AI功能不可用")

    # 调度引擎
    app_state.scheduler = SchedulerEngine(
        app_state.agent,
        app_state.store,
        app_state.llm,
        app_state.privacy,
        app_state.import_context,
        budget_limit_watts=int(os.getenv("POWER_BUDGET_WATTS", "1200")),
        budget_enabled=os.getenv("POWER_BUDGET_ENABLED", "false").lower() in {"1", "true", "yes", "on"},
    )

    app_state.governance = GovernanceService(
        app_state.store, app_state.agent
    )
    # 能耗分析引擎
    app_state.energy = EnergyAnalytics(
        app_state.store,
        app_state.llm,
        app_state.agent,
        app_state.privacy,
        app_state.governance,
    )
    platform_registry = build_platform_capability_registry(app_state)
    app_state.goal_runtime = GoalRuntimeService(
        store=app_state.store,
        registry=platform_registry,
        import_context=app_state.import_context,
        runtime_status_reader=runtime_status_payload,
        llm_service_reader=lambda: app_state.llm,
    )
    app_state.control_plane = ControlPlaneService(
        app_state.store,
        platform_registry,
    )
    app_state.cluster_scheduler = ClusterSchedulerCore()
    app_state.cluster_orchestrator = ExecutionOrchestrator(
        app_state.store,
        {
            "http_agent": HTTPAgentProcessBackend(),
            "local_process": LocalProcessBackend(),
            "ssh_process": SSHProcessBackend(),
        },
    )
    app_state.cluster_control = ClusterControlPlaneService(
        app_state.store,
        app_state.cluster_scheduler,
        app_state.cluster_orchestrator,
    )
    bind_llm_service(app_state.llm)
    graph_summary = await app_state.graph.summary()
    if graph_summary["ready"]:
        logger.info(
            "Neo4j 图谱服务已连接，database=%s nodes=%s relations=%s",
            graph_summary["database"],
            graph_summary["node_count"],
            graph_summary["relation_count"],
        )
    else:
        logger.warning("Neo4j 图谱服务未就绪: %s", graph_summary["message"])

    # 启动采集循环
    app_state._collect_task = asyncio.create_task(collect_loop())
    app_state._cleanup_task = asyncio.create_task(cleanup_loop())
    logger.info("后端服务启动完成")

    yield

    # 关闭
    if app_state._collect_task:
        app_state._collect_task.cancel()
    if app_state._cleanup_task:
        app_state._cleanup_task.cancel()
    await app_state.graph.close()
    await app_state.workspaces.close_all()
    await app_state.store.close()
    await app_state.identity.close()
    logger.info("后端服务已关闭")


# 创建FastAPI应用
app = FastAPI(
    title="智算中心优化代码生成系统",
    description="面向智算中心的优化治理、知识图谱分析与代码生成系统",
    version="1.1.7",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Token 认证中间件
from app.middleware.auth import TokenAuthMiddleware
app.add_middleware(TokenAuthMiddleware)

# 注册API路由
from app.api.gpu import router as gpu_router
from app.api.tasks import router as tasks_router
from app.api.scheduler import router as scheduler_router
from app.api.ai import router as ai_router
from app.api.alerts import router as alerts_router
from app.api.monitor import router as monitor_router
from app.api.energy import router as energy_router
from app.api.governance import router as governance_router
from app.api.system import router as system_router
from app.api.system_diagnostics import router as system_diagnostics_router
from app.api.system_import import router as system_import_router
from app.api.audit import router as audit_router
from app.api.auth import router as auth_router
from app.api.admin_users import router as admin_users_router
from app.api.hosts import router as hosts_router
from app.api.agent_runtime import router as agent_runtime_router
from app.api.cluster_jobs import router as cluster_jobs_router
from app.api.cluster_queues import router as cluster_queues_router
from app.api.control import router as control_router
from app.api.graph import router as graph_router

app.include_router(gpu_router)
app.include_router(tasks_router)
app.include_router(scheduler_router)
app.include_router(ai_router)
app.include_router(alerts_router)
app.include_router(monitor_router)
app.include_router(energy_router)
app.include_router(governance_router)
app.include_router(system_router)
app.include_router(system_diagnostics_router)
app.include_router(system_import_router)
app.include_router(audit_router)
app.include_router(auth_router)
app.include_router(admin_users_router)
app.include_router(hosts_router)
app.include_router(agent_runtime_router)
app.include_router(cluster_jobs_router)
app.include_router(cluster_queues_router)
app.include_router(control_router)
app.include_router(graph_router)


@app.get("/api/health")
async def health():
    """健康检查"""
    runtime_status = await runtime_status_payload()
    workspace_key = current_workspace_key()
    return await build_health_payload(
        runtime_status=runtime_status,
        snapshot=app_state.latest_runtime_snapshot,
        connection_factory=app_state.workspaces.current_connection_snapshot,
        llm_available=app_state.llm is not None,
        llm_snapshot=app_state.llm_settings.snapshot(app_state.llm is not None),
        ws_connections=ws_manager.connection_count_for(workspace_key),
        fallback_loader=lambda: _load_health_runtime_state(runtime_status),
    )


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """WebSocket连接端点 - 实时数据推送"""
    token = ws.query_params.get("token", "")
    user = await app_state.platform_auth.resolve_session(token)
    if not user:
        await ws.close(code=4401, reason="UNAUTHORIZED")
        return
    if user["must_change_password"]:
        await ws.close(code=4403, reason="PASSWORD_CHANGE_REQUIRED")
        return
    workspace_key = f"user:{int(user['id'])}"
    await app_state.workspaces.ensure_workspace(workspace_key)
    await ws_manager.connect(ws, workspace_key)
    try:
        while True:
            # 保持连接，接收客户端心跳
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(ws, workspace_key)


# 尝试挂载前端静态文件
_frontend_dist = os.getenv("FRONTEND_DIST_DIR", "")
if not _frontend_dist:
    if getattr(sys, "frozen", False):
        _frontend_dist = os.path.join(os.path.dirname(sys.executable), "frontend", "dist")
        if not os.path.isdir(_frontend_dist):
            _frontend_dist = os.path.join(os.path.dirname(sys.executable), "_internal", "frontend", "dist")
    else:
        _frontend_dist = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
if os.path.isdir(_frontend_dist):
    app.mount("/", SPAStaticFiles(directory=_frontend_dist, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        reload=True,
    )
