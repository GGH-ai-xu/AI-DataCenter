from __future__ import annotations

import re
from typing import Any


PLAN_JOB_KEYWORDS = ("规划作业", "预演作业", "plan job", "放置方案")
RESCHEDULE_KEYWORDS = ("重排作业", "重规划作业", "reschedule job", "reschedule")


def _find_job_id(text: str) -> str | None:
    match = re.search(r"\b(job[-\w.]+)\b", text, flags=re.IGNORECASE)
    if match:
        return match.group(1)
    return None


def _find_gpu_count(text: str) -> int | None:
    match = re.search(r"(\d+)\s*(?:张\s*)?gpu", text, flags=re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def _find_cpu_count(text: str) -> int | None:
    match = re.search(r"(\d+)\s*(?:核|cpu)", text, flags=re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def _plan_target(job_id: str, text: str) -> dict[str, Any]:
    resource_request = {}
    gpu_count = _find_gpu_count(text)
    cpu_count = _find_cpu_count(text)
    if gpu_count is not None:
        resource_request["gpu"] = gpu_count
    if cpu_count is not None:
        resource_request["cpu"] = cpu_count
    return {
        "job_id": job_id,
        "tenant_id": "default",
        "project_id": "interactive",
        "queue_id": "default",
        "submitter_id": "planner",
        "job_type": "batch",
        "entrypoint": "python train.py",
        "resource_request": resource_request,
    }


def build_cluster_planning_actions(text: str) -> list[dict[str, Any]]:
    lowered = (text or "").lower()
    job_id = _find_job_id(lowered)
    if not job_id:
        return []
    if any(keyword in lowered for keyword in RESCHEDULE_KEYWORDS):
        return [
            {
                "action": "plan_reschedule",
                "target": {"job_id": job_id},
                "reason": f"根据用户指令预演作业 {job_id} 的重排结果",
            }
        ]
    if any(keyword in lowered for keyword in PLAN_JOB_KEYWORDS):
        return [
            {
                "action": "plan_job",
                "target": _plan_target(job_id, lowered),
                "reason": f"根据用户指令预演作业 {job_id} 的放置方案",
            }
        ]
    return []
