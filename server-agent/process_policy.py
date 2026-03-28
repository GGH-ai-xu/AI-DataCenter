"""GPU 进程分类策略 - 区分治理任务与图形陪跑进程"""

from __future__ import annotations


MB = 1024 * 1024

SYSTEM_USER_PREFIXES = (
    "window manager\\",
    "nt authority\\",
    "system",
    "local service",
    "network service",
)

BACKGROUND_PROCESS_NAMES = {
    "amdrssrcext.exe",
    "applicationframehost.exe",
    "chrome.exe",
    "crossdeviceresume.exe",
    "dwm.exe",
    "explorer.exe",
    "flutterplugins.exe",
    "gpugovernanceworkbench.exe",
    "legionzone.exe",
    "lenovoappstore.exe",
    "lockapp.exe",
    "msedge.exe",
    "msedgewebview2.exe",
    "nahimicsvc64.exe",
    "onedrive.exe",
    "phoneexperiencehost.exe",
    "radeonsoftware.exe",
    "searchhost.exe",
    "shellexperiencehost.exe",
    "shellhost.exe",
    "startmenuexperiencehost.exe",
    "systemsettings.exe",
    "textinputhost.exe",
    "wechatappex.exe",
    "windowsterminal.exe",
}

BACKGROUND_COMMAND_KEYWORDS = (
    "--type=gpu-process",
    "--type=utility",
    "--utility-sub-type=",
    "--gpu-preferences=",
    "--disable-gpu-sandbox",
    "--user-data-dir=",
    "edgewebview",
    "searchhost.exe",
    "startmenuexperiencehost",
    "crossdeviceresume.exe",
    "lockapp.exe",
)

COMPUTE_NAME_KEYWORDS = (
    "python",
    "python.exe",
    "torchrun",
    "deepspeed",
    "accelerate",
    "jupyter",
    "ollama",
    "vllm",
    "sglang",
    "comfyui",
    "invokeai",
    "llamafactory",
)

COMPUTE_COMMAND_KEYWORDS = (
    " train",
    " finetune",
    " inference",
    " serving",
    " generate",
    " torchrun",
    " deepspeed",
    " accelerate",
    " jupyter",
    " python ",
    "python.exe",
    "ollama",
    "vllm",
    "sglang",
    "llm",
    "cuda",
)


def _to_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _looks_like_compute_task(name: str, command: str) -> bool:
    if any(keyword in name for keyword in COMPUTE_NAME_KEYWORDS):
        return True
    return any(keyword in command for keyword in COMPUTE_COMMAND_KEYWORDS)


def classify_process(proc: dict) -> dict:
    item = dict(proc or {})
    name = (item.get("name") or "").strip().lower()
    command = (item.get("command") or "").strip().lower()
    username = (item.get("username") or "").strip().lower()
    priority = (item.get("priority") or "normal").strip().lower()
    gpu_memory_used = _to_int(item.get("gpu_memory_used"), 0)

    manageable = True
    category = "governable"
    reason_code = "governable_task"
    summary = "可治理任务"
    reason = "可作为治理任务处理"

    if any(username.startswith(prefix) for prefix in SYSTEM_USER_PREFIXES):
        manageable = False
        category = "system"
        reason_code = "system_graphics"
        summary = "系统图形"
        reason = "系统图形进程，不建议做暂停或终止治理"
    elif name in BACKGROUND_PROCESS_NAMES:
        manageable = False
        category = "background"
        reason_code = "desktop_background"
        summary = "桌面陪跑"
        reason = "桌面或应用图形陪跑进程，不属于重点治理任务"
    elif any(keyword in command for keyword in BACKGROUND_COMMAND_KEYWORDS):
        manageable = False
        category = "background"
        reason_code = "browser_gpu_helper"
        summary = "浏览器子进程"
        reason = "浏览器或 WebView 的 GPU 子进程，不建议直接治理"
    elif gpu_memory_used <= 64 * MB and not _looks_like_compute_task(name, command):
        manageable = False
        category = "background"
        reason_code = "low_usage_background"
        summary = "低占用陪跑"
        reason = "显存占用极低，更像桌面渲染或图形辅助进程"
    elif priority in {"urgent", "deferrable"} or gpu_memory_used >= 256 * MB or _looks_like_compute_task(name, command):
        manageable = True
        category = "governable"
        reason_code = "governable_task"
        summary = "可治理任务"
        reason = "可作为治理任务处理"

    item["manageable"] = manageable
    item["process_category"] = category
    item["manageable_reason_code"] = reason_code
    item["manageable_summary"] = summary
    item["manageable_reason"] = reason
    item["is_background_process"] = not manageable
    return item


def is_manageable_process(proc: dict) -> bool:
    return bool(classify_process(proc).get("manageable"))
