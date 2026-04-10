from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.schemas import (
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


@router.get("/jobs/{job_id}")
async def get_cluster_job(job_id: str):
    from app.main import app_state

    job = await app_state.cluster_control.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="cluster job not found")
    return job


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
    )


async def _load_cluster_nodes(app_state) -> list[dict]:
    preset_nodes = getattr(app_state, "cluster_nodes", None)
    if preset_nodes is not None:
        return list(preset_nodes)
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
    return [
        {
            "node_id": "active-node",
            "schedulable": True,
            "gpu_free": len(available_gpus),
            "cpu_free": cpu_free,
            "memory_bytes_free": memory_free,
            "device_ids": tuple(f"gpu-{gpu['index']}" for gpu in available_gpus),
            "execution_backend": execution_backend,
            "base_url": base_url if execution_backend == "http_agent" else "",
        }
    ]


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
