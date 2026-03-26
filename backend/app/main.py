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
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from app.services.agent_client import AgentClient
from app.services.data_store import DataStore
from app.services.llm import LLMService
from app.services.alert_engine import AlertEngine
from app.services.scheduler import SchedulerEngine
from app.services.energy_analytics import EnergyAnalytics
from app.services.governance import GovernanceService
from app.services.privacy import PrivacyService
from app.ws.realtime import ws_manager

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AppState:
    """应用全局状态，存储共享服务实例"""
    agent: AgentClient
    store: DataStore
    llm: LLMService | None
    alert_engine: AlertEngine
    scheduler: SchedulerEngine
    energy: EnergyAnalytics
    governance: GovernanceService
    privacy: PrivacyService
    _collect_task: asyncio.Task | None = None
    _cleanup_task: asyncio.Task | None = None
    _agent_fail_count: int = 0


app_state = AppState()


async def cleanup_loop():
    """定期清理过期历史数据（每24小时）"""
    while True:
        await asyncio.sleep(86400)
        try:
            await app_state.store.cleanup_old_data(days=7)
            logger.info("数据库过期数据清理完成")
        except Exception as e:
            logger.error(f"数据库清理失败: {e}")


async def collect_loop():
    """数据采集循环 - 定时从Agent拉数据、存储、推送、检测告警"""
    interval = float(os.getenv("COLLECT_INTERVAL", "2"))
    logger.info(f"数据采集循环启动，间隔 {interval}s")

    while True:
        try:
            # 从Agent获取实时数据
            gpus = await app_state.agent.get_all_gpus()
            system = await app_state.agent.get_system_info()
            processes = await app_state.agent.get_processes()

            if gpus:
                app_state._agent_fail_count = 0
                priorities = await app_state.store.get_all_task_priorities()
                enriched_processes = []
                for proc in processes:
                    cloned = dict(proc)
                    cloned["priority"] = priorities.get(
                        cloned.get("pid"),
                        cloned.get("priority", "normal"),
                    )
                    enriched_processes.append(cloned)

                # 存储历史数据
                await app_state.store.save_gpu_snapshot(gpus)

                # 追踪进程生命周期
                await app_state.store.track_processes(enriched_processes)

                # 告警检测
                alerts = app_state.alert_engine.check_all_gpus(gpus)
                for alert in alerts:
                    await app_state.store.save_alert(alert)

                # 调度引擎tick
                await app_state.scheduler.tick(gpus, enriched_processes)

                # WebSocket推送
                public_processes = app_state.privacy.sanitize_processes(enriched_processes)
                await ws_manager.broadcast({
                    "type": "realtime",
                    "gpus": gpus,
                    "system": system,
                    "processes": public_processes,
                    "alerts": alerts,
                })
            else:
                app_state._agent_fail_count += 1
                if app_state._agent_fail_count == 10:
                    logger.critical("Agent连续10次无数据，可能已断开连接")
                elif app_state._agent_fail_count % 50 == 0:
                    logger.critical(f"Agent持续不可用，已连续{app_state._agent_fail_count}次失败")

        except Exception as e:
            logger.error(f"数据采集异常: {e}")

        await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    # 初始化服务
    agent_url = os.getenv("AGENT_URL", "http://localhost:8001")
    db_path = os.getenv("DB_PATH", "./data/history.db")

    app_state.agent = AgentClient(agent_url)
    app_state.store = DataStore(db_path)
    await app_state.store.init()
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

    # LLM服务（可选）
    llm_key = os.getenv("LLM_API_KEY", "")
    if llm_key and llm_key != "sk-your-key-here":
        app_state.llm = LLMService(
            api_key=llm_key,
            base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1"),
            model=os.getenv("LLM_MODEL", "deepseek-chat"),
        )
        logger.info("LLM服务已初始化")
    else:
        app_state.llm = None
        logger.warning("LLM_API_KEY未配置，AI功能不可用")

    # 调度引擎
    app_state.scheduler = SchedulerEngine(
        app_state.agent,
        app_state.store,
        app_state.llm,
        app_state.privacy,
        budget_limit_watts=int(os.getenv("POWER_BUDGET_WATTS", "1200")),
        budget_enabled=os.getenv("POWER_BUDGET_ENABLED", "false").lower() in {"1", "true", "yes", "on"},
    )

    # 能耗分析引擎
    app_state.energy = EnergyAnalytics(
        app_state.store, app_state.llm, app_state.agent, app_state.privacy
    )
    app_state.governance = GovernanceService(
        app_state.store, app_state.agent
    )

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
    await app_state.agent.close()
    await app_state.store.close()
    logger.info("后端服务已关闭")


# 创建FastAPI应用
app = FastAPI(
    title="GPU集群治理平台",
    description="高校实验室GPU服务器智能运维与功率预算治理平台",
    version="1.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册API路由
from app.api.gpu import router as gpu_router
from app.api.tasks import router as tasks_router
from app.api.scheduler import router as scheduler_router
from app.api.ai import router as ai_router
from app.api.alerts import router as alerts_router
from app.api.monitor import router as monitor_router
from app.api.energy import router as energy_router
from app.api.governance import router as governance_router

app.include_router(gpu_router)
app.include_router(tasks_router)
app.include_router(scheduler_router)
app.include_router(ai_router)
app.include_router(alerts_router)
app.include_router(monitor_router)
app.include_router(energy_router)
app.include_router(governance_router)


@app.get("/api/health")
async def health():
    """健康检查"""
    agent_health = await app_state.agent.health_check()
    return {
        "status": "ok",
        "agent_connected": agent_health is not None,
        "agent_info": agent_health,
        "ws_connections": ws_manager.connection_count,
        "llm_available": app_state.llm is not None,
    }


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """WebSocket连接端点 - 实时数据推送"""
    await ws_manager.connect(ws)
    try:
        while True:
            # 保持连接，接收客户端心跳
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)


# 尝试挂载前端静态文件
_frontend_dist = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
if os.path.isdir(_frontend_dist):
    app.mount("/", StaticFiles(directory=_frontend_dist, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        reload=True,
    )
