from __future__ import annotations

import time


def build_checkpoint_record(
    job_id: str,
    allocation: dict,
    runtime_job: dict,
    *,
    checkpoint_id: str = "",
    updated_at: float = 0,
) -> dict:
    resolved_id = checkpoint_id or str(runtime_job.get("checkpoint_id") or "")
    if not resolved_id:
        raise ValueError("runtime checkpoint state missing checkpoint_id")
    checkpoint_time = float(updated_at) or float(runtime_job.get("finished_at") or 0) or time.time()
    return {
        "checkpoint_id": resolved_id,
        "job_id": job_id,
        "allocation_id": str(allocation.get("allocation_id") or ""),
        "node_id": str(allocation.get("node_id") or ""),
        "runtime_job_handle": str(
            allocation.get("runtime_job_handle") or runtime_job.get("job_handle") or ""
        ),
        "status": str(runtime_job.get("checkpoint_state") or "checkpoint_requested"),
        "manifest_path": str(runtime_job.get("checkpoint_manifest_path") or ""),
        "error": str(runtime_job.get("checkpoint_error") or ""),
        "created_at": checkpoint_time,
        "updated_at": checkpoint_time,
    }


def build_job_checkpoint_pointer(record: dict) -> dict:
    return {
        "checkpoint_id": str(record.get("checkpoint_id") or ""),
        "checkpoint_status": str(record.get("status") or ""),
        "checkpoint_manifest_path": str(record.get("manifest_path") or ""),
        "checkpoint_error": str(record.get("error") or ""),
        "checkpoint_updated_at": float(record.get("updated_at") or 0),
    }


async def load_restore_checkpoint(store, job_id: str, checkpoint_id: str) -> dict:
    checkpoint = await _resolve_restore_checkpoint(store, job_id, checkpoint_id)
    if str(checkpoint.get("status") or "") != "checkpoint_ready":
        raise ValueError("checkpoint is not ready to restore")
    if not str(checkpoint.get("manifest_path") or ""):
        raise ValueError("checkpoint does not have a manifest to restore")
    return checkpoint


async def _resolve_restore_checkpoint(store, job_id: str, checkpoint_id: str) -> dict:
    if checkpoint_id:
        checkpoint = await store.get_cluster_checkpoint(checkpoint_id)
        if checkpoint is None:
            raise LookupError(f"cluster checkpoint not found: {checkpoint_id}")
        if str(checkpoint.get("job_id") or "") != job_id:
            raise ValueError(f"checkpoint {checkpoint_id} does not belong to job {job_id}")
        return checkpoint
    checkpoint = await store.get_latest_ready_cluster_checkpoint(job_id)
    if checkpoint is None:
        raise ValueError("job does not have a ready checkpoint to restore")
    return checkpoint
