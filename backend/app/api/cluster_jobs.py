from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.schemas import (
    ClusterControllerConfigRequest,
    ClusterJobCheckpointRequest,
    ClusterJobRestoreRequest,
    ClusterJobSubmitRequest,
    ClusterJobSubmitResponse,
)
from app.services.cluster_control.models import JobSpecRecord


router = APIRouter(prefix="/api/cluster", tags=["Cluster"])


@router.post("/jobs", response_model=ClusterJobSubmitResponse)
async def submit_cluster_job(req: ClusterJobSubmitRequest):
    from app.main import app_state

    job_record = _build_job_record(req)
    nodes = await _load_cluster_nodes(app_state)
    plan = await app_state.cluster_control.submit_job(job_record, nodes=nodes)
    job = await app_state.store.get_cluster_job(job_record.job_id)
    if job is None:
        raise HTTPException(status_code=500, detail="cluster job was not persisted")
    return {
        "job_id": job_record.job_id,
        "state": job["status"],
        "plan_type": plan.plan_type,
    }


@router.get("/jobs")
async def list_cluster_jobs():
    from app.main import app_state

    return {"jobs": await app_state.cluster_control.list_jobs()}


@router.post("/reconcile")
async def reconcile_cluster_jobs():
    from app.main import app_state

    controller = getattr(app_state, "cluster_reconcile_controller", None)
    if controller is not None:
        return await controller.run_once(trigger="manual")
    nodes = await _load_cluster_nodes(app_state)
    return await app_state.cluster_control.reconcile_and_dispatch(nodes=nodes)


@router.get("/controller")
async def get_cluster_controller_status():
    from app.main import app_state

    controller = getattr(app_state, "cluster_reconcile_controller", None)
    if controller is None:
        return {
            "enabled": False,
            "running": False,
            "interval_seconds": 0,
            "tick_count": 0,
            "last_trigger": "",
            "last_started_at": 0,
            "last_finished_at": 0,
            "last_error": "",
            "last_skip_reason": "",
            "last_summary": {},
        }
    return controller.snapshot()


@router.post("/controller")
async def update_cluster_controller(req: ClusterControllerConfigRequest):
    from app.main import app_state

    controller = getattr(app_state, "cluster_reconcile_controller", None)
    if controller is None:
        raise HTTPException(status_code=503, detail="cluster reconcile controller unavailable")
    return controller.configure(
        enabled=req.enabled,
        interval_seconds=req.interval_seconds,
    )


@router.get("/jobs/{job_id}")
async def get_cluster_job(job_id: str):
    from app.main import app_state

    job = await app_state.cluster_control.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="cluster job not found")
    return job


@router.get("/jobs/{job_id}/checkpoints")
async def list_cluster_job_checkpoints(job_id: str):
    from app.main import app_state

    try:
        checkpoints = await app_state.cluster_control.list_job_checkpoints(job_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"checkpoints": checkpoints}


@router.get("/checkpoints/{checkpoint_id}")
async def get_cluster_checkpoint(checkpoint_id: str):
    from app.main import app_state

    checkpoint = await app_state.cluster_control.get_checkpoint(checkpoint_id)
    if checkpoint is None:
        raise HTTPException(status_code=404, detail="cluster checkpoint not found")
    return checkpoint


@router.post("/jobs/{job_id}/pause")
async def pause_cluster_job(job_id: str):
    from app.main import app_state

    return await app_state.cluster_control.pause_job(job_id)


@router.post("/jobs/{job_id}/resume")
async def resume_cluster_job(job_id: str):
    from app.main import app_state

    return await app_state.cluster_control.resume_job(job_id)


@router.post("/jobs/{job_id}/checkpoint")
async def checkpoint_cluster_job(job_id: str, req: ClusterJobCheckpointRequest):
    from app.main import app_state

    return await app_state.cluster_control.checkpoint_job(
        job_id,
        timeout_seconds=req.timeout_seconds,
    )


@router.post("/jobs/{job_id}/restore")
async def restore_cluster_job(job_id: str, req: ClusterJobRestoreRequest):
    from app.main import app_state

    return await app_state.cluster_control.restore_job(
        job_id,
        checkpoint_id=req.checkpoint_id,
    )


def _build_job_record(req: ClusterJobSubmitRequest) -> JobSpecRecord:
    return JobSpecRecord(
        job_id=req.job_id,
        tenant_id=req.tenant_id,
        project_id=req.project_id,
        queue_id=req.queue_id,
        submitter_id=req.submitter_id,
        job_type=req.job_type,
        entrypoint=req.entrypoint,
        args=tuple(req.args),
        env=dict(req.env),
        resource_request=dict(req.resource_request),
        placement_constraints=dict(req.placement_constraints),
        priority=req.priority,
        preemptible=req.preemptible,
        max_retries=req.max_retries,
        timeout_seconds=req.timeout_seconds,
        task_kind=req.task_kind,
        lifecycle_kind=req.lifecycle_kind,
        service_ports=tuple(req.service_ports),
        checkpoint_policy=req.checkpoint_policy,
        runtime_profile=dict(req.runtime_profile),
    )


async def _load_cluster_nodes(app_state) -> list[dict]:
    return await sync_cluster_nodes(app_state)


async def sync_cluster_nodes(app_state) -> list[dict]:
    preset_nodes = getattr(app_state, "cluster_nodes", None)
    if preset_nodes is not None:
        nodes = list(preset_nodes)
    else:
        snapshot = getattr(app_state, "latest_runtime_snapshot", {}) or {}
        scoped = snapshot.get("scoped", {}) if isinstance(snapshot, dict) else {}
        gpus = list(scoped.get("gpus") or [])
        system = scoped.get("system") or {}
        available_gpus = [gpu for gpu in gpus if gpu.get("available", True)]
        cpu_free = int(system.get("cpu_count") or 0)
        memory_free = int(system.get("memory_available") or 0)
        provider_type = _provider_type(app_state)
        execution_backend = _execution_backend(provider_type)
        base_url = getattr(getattr(app_state, "agent", None), "base_url", "") or ""
        if not base_url and getattr(app_state, "connection", None):
            base_url = app_state.connection.default_local_url
        nodes = [
            {
                "node_id": "active-node",
                "cluster_id": "default-cluster",
                "label": "当前节点",
                "state": "ready",
                "drain_state": "active",
                "schedulable": True,
                "gpu_free": len(available_gpus),
                "cpu_free": cpu_free,
                "memory_bytes_free": memory_free,
                "device_ids": tuple(f"gpu-{gpu['index']}" for gpu in available_gpus),
                "execution_backend": execution_backend,
                "base_url": base_url if execution_backend == "http_agent" else "",
                "metadata": {},
            }
        ]
    merged = []
    for node in nodes:
        merged.append(await _merge_cluster_node_state(app_state, node))
    return merged


async def _merge_cluster_node_state(app_state, node: dict) -> dict:
    node_id = str(node["node_id"])
    existing = await app_state.store.get_cluster_node(node_id)
    merged = {
        "node_id": node_id,
        "cluster_id": str(node.get("cluster_id") or "default-cluster"),
        "label": str(node.get("label") or node_id),
        "state": str(node.get("state") or "ready"),
        "drain_state": str((existing or {}).get("drain_state") or node.get("drain_state") or "active"),
        "execution_backend": str(node.get("execution_backend") or "http_agent"),
        "metadata": dict(node.get("metadata") or {}),
        "schedulable": bool(node.get("schedulable", True)),
        "gpu_free": int(node.get("gpu_free") or 0),
        "cpu_free": int(node.get("cpu_free") or 0),
        "memory_bytes_free": int(node.get("memory_bytes_free") or 0),
        "device_ids": tuple(node.get("device_ids") or ()),
        "base_url": str(node.get("base_url") or ""),
    }
    await app_state.store.upsert_cluster_node(
        {
            "node_id": merged["node_id"],
            "cluster_id": merged["cluster_id"],
            "label": merged["label"],
            "state": merged["state"],
            "drain_state": merged["drain_state"],
            "execution_backend": merged["execution_backend"],
            "metadata": merged["metadata"],
        }
    )
    return merged


def _provider_type(app_state) -> str:
    connection = getattr(app_state, "connection", None)
    if connection is None or not hasattr(connection, "snapshot"):
        return ""
    snapshot = connection.snapshot(None)
    return str(snapshot.get("provider_type") or "")


def _execution_backend(provider_type: str) -> str:
    if provider_type == "ssh_linux":
        return "ssh_process"
    if provider_type in {"http_local", "http_remote", ""}:
        return "http_agent"
    return "local_process"
