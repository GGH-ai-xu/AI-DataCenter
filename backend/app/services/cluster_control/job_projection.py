from __future__ import annotations


def _runtime_handles_by_job(allocations: list[dict]) -> dict[str, str]:
    handles: dict[str, str] = {}
    for item in allocations:
        job_id = str(item.get("job_id") or "")
        runtime_job_handle = str(item.get("runtime_job_handle") or "")
        if not job_id or not runtime_job_handle or job_id in handles:
            continue
        handles[job_id] = runtime_job_handle
    return handles


def _releasing_job_ids(allocations: list[dict]) -> set[str]:
    return {
        str(item.get("job_id") or "")
        for item in allocations
        if str(item.get("status") or "") == "releasing"
    }


def attach_runtime_handles_to_jobs(
    jobs: list[dict],
    allocations: list[dict],
) -> list[dict]:
    handles = _runtime_handles_by_job(allocations)
    releasing = _releasing_job_ids(allocations)
    return [
        {
            **item,
            "runtime_job_handle": handles.get(str(item.get("job_id") or ""), ""),
            "has_releasing_allocation": str(item.get("job_id") or "") in releasing,
        }
        for item in jobs
    ]


def attach_runtime_handle_to_job(
    job: dict | None,
    allocations: list[dict],
) -> dict | None:
    if job is None:
        return None
    return attach_runtime_handles_to_jobs([job], allocations)[0]
