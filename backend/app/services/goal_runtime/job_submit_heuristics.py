from __future__ import annotations

import re

from app.services.goal_runtime.control_heuristic_support import find_job_id


SUBMIT_KEYWORDS = ("提交", "启动", "创建", "运行", "launch", "submit", "start")
TASK_DEFAULTS = {
    "training": {
        "job_type": "batch",
        "lifecycle_kind": "batch",
        "checkpoint_policy": "app_managed",
        "preemptible": True,
        "runtime_profile": {"restartable": True, "latency_sensitive": False, "exclusive_gpu": True},
        "entrypoint": "python train.py",
    },
    "inference_service": {
        "job_type": "service",
        "lifecycle_kind": "service",
        "checkpoint_policy": "none",
        "preemptible": False,
        "runtime_profile": {"restartable": False, "latency_sensitive": True, "exclusive_gpu": True},
        "entrypoint": "python serve.py",
    },
    "interactive_session": {
        "job_type": "session",
        "lifecycle_kind": "session",
        "checkpoint_policy": "none",
        "preemptible": False,
        "runtime_profile": {"restartable": False, "latency_sensitive": False, "exclusive_gpu": True},
        "entrypoint": "python -m jupyter lab",
    },
    "batch_compute": {
        "job_type": "batch",
        "lifecycle_kind": "batch",
        "checkpoint_policy": "none",
        "preemptible": True,
        "runtime_profile": {"restartable": True, "latency_sensitive": False, "exclusive_gpu": False},
        "entrypoint": "python main.py",
    },
    "maintenance": {
        "job_type": "batch",
        "lifecycle_kind": "batch",
        "checkpoint_policy": "none",
        "preemptible": True,
        "runtime_profile": {"restartable": False, "latency_sensitive": False, "exclusive_gpu": False},
        "entrypoint": "python maintain.py",
    },
}


def _find_command(text: str) -> str | None:
    match = re.search(r"(?:命令|command)\s*[:：]?\s*(.+)$", text, flags=re.IGNORECASE)
    return match.group(1).strip() if match else None


def _find_resource(text: str, unit_pattern: str) -> int | None:
    match = re.search(unit_pattern, text, flags=re.IGNORECASE)
    return int(match.group(1)) if match else None


def _find_service_ports(text: str, command: str) -> list[int]:
    explicit = re.findall(r"(?:监听|端口|port)\s*[:：]?\s*(\d{2,5})", text, flags=re.IGNORECASE)
    command_ports = re.findall(r"--port(?:=|\s+)(\d{2,5})", command, flags=re.IGNORECASE)
    return [int(item) for item in (*explicit, *command_ports)]


def _detect_task_kind(text: str) -> str | None:
    if any(word in text for word in ("交互式会话", "交互会话", "jupyter", "notebook")):
        return "interactive_session"
    if any(word in text for word in ("推理服务", "在线服务", "serving", "inference service")):
        return "inference_service"
    if any(word in text for word in ("训练任务", "训练作业", "训练", "training")):
        return "training"
    if any(word in text for word in ("维护任务", "环境检查", "清理任务", "maintenance")):
        return "maintenance"
    if any(word in text for word in ("批处理", "离线计算", "batch compute")):
        return "batch_compute"
    return None


def build_submit_job_actions(text: str) -> list[dict]:
    normalized = (text or "").lower()
    if not any(keyword in normalized for keyword in SUBMIT_KEYWORDS):
        return []
    job_id = find_job_id(normalized)
    task_kind = _detect_task_kind(normalized)
    if not job_id or task_kind is None:
        return []
    defaults = TASK_DEFAULTS[task_kind]
    command = _find_command(text) or defaults["entrypoint"]
    resource_request = {}
    gpu_count = _find_resource(normalized, r"(\d+)\s*(?:张\s*)?gpu")
    cpu_count = _find_resource(normalized, r"(\d+)\s*(?:核|cpu)")
    if gpu_count is not None:
        resource_request["gpu"] = gpu_count
    if cpu_count is not None:
        resource_request["cpu"] = cpu_count
    return [
        {
            "action": "submit_job",
            "target": {
                "job_id": job_id,
                "tenant_id": "default",
                "project_id": "interactive",
                "queue_id": "default",
                "submitter_id": "planner",
                "job_type": defaults["job_type"],
                "task_kind": task_kind,
                "lifecycle_kind": defaults["lifecycle_kind"],
                "entrypoint": command,
                "args": [],
                "env": {},
                "resource_request": resource_request,
                "placement_constraints": {},
                "priority": 50,
                "preemptible": defaults["preemptible"],
                "max_retries": 0,
                "timeout_seconds": 0,
                "service_ports": _find_service_ports(text, command),
                "checkpoint_policy": defaults["checkpoint_policy"],
                "runtime_profile": {
                    **defaults["runtime_profile"],
                    "expected_duration_seconds": 0,
                },
            },
            "reason": f"根据用户指令提交任务 {job_id}",
        }
    ]
