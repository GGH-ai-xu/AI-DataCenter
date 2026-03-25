"""训练日志监控 - 检测并解析GPU进程的训练日志

支持的日志格式：
- 通用模式：Epoch X, Loss: Y, Acc: Z
- PyTorch常见输出：train_loss, val_loss, accuracy
- 自动检测进程工作目录下的日志文件
"""

import os
import re
import glob
import logging
from typing import List, Dict, Optional

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

logger = logging.getLogger(__name__)

# 常见训练日志文件名模式
LOG_FILE_PATTERNS = [
    "*.log", "train*.log", "output*.log", "nohup.out",
    "training.log", "train.log", "log.txt", "*.out",
]

# 训练指标提取正则（覆盖常见框架输出格式）
METRIC_PATTERNS = [
    # Epoch 1/100, loss: 0.5234, acc: 0.8912
    re.compile(
        r"[Ee]poch\s*[:\s]?\s*(\d+)(?:\s*/\s*\d+)?"
        r".*?[Ll]oss\s*[:\s=]\s*([\d.]+(?:e[+-]?\d+)?)"
        r"(?:.*?[Aa]cc(?:uracy)?\s*[:\s=]\s*([\d.]+))?"
    ),
    # [Epoch 5] train_loss=0.234 val_loss=0.345 val_acc=0.912
    re.compile(
        r"\[?\s*[Ee]poch\s+(\d+)\s*\]?"
        r".*?(?:train_?)?loss\s*[=:]\s*([\d.]+(?:e[+-]?\d+)?)"
        r"(?:.*?(?:val_?)?(?:acc|accuracy)\s*[=:]\s*([\d.]+))?"
    ),
    # Step/Iter模式：Step 1000, loss 0.234
    re.compile(
        r"(?:[Ss]tep|[Ii]ter(?:ation)?)\s*[:\s]?\s*(\d+)"
        r".*?[Ll]oss\s*[:\s=]\s*([\d.]+(?:e[+-]?\d+)?)"
        r"(?:.*?[Aa]cc(?:uracy)?\s*[:\s=]\s*([\d.]+))?"
    ),
]


def _get_process_cwd(pid: int) -> Optional[str]:
    """获取进程的工作目录"""
    if not PSUTIL_AVAILABLE:
        return None
    try:
        p = psutil.Process(pid)
        return p.cwd()
    except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
        pass
    # 备选：读取 /proc/PID/cwd
    try:
        return os.readlink(f"/proc/{pid}/cwd")
    except OSError:
        return None


def _find_log_files(directory: str, max_files: int = 5) -> List[str]:
    """在目录中查找可能的训练日志文件"""
    if not directory or not os.path.isdir(directory):
        return []

    candidates = []
    for pattern in LOG_FILE_PATTERNS:
        found = glob.glob(os.path.join(directory, pattern))
        candidates.extend(found)
        # 也检查常见子目录
        for subdir in ["logs", "log", "output", "outputs", "results"]:
            sub_path = os.path.join(directory, subdir, pattern)
            candidates.extend(glob.glob(sub_path))

    # 去重并按修改时间排序（最新的优先）
    seen = set()
    unique = []
    for f in candidates:
        real = os.path.realpath(f)
        if real not in seen and os.path.isfile(real):
            seen.add(real)
            unique.append(real)

    unique.sort(key=lambda f: os.path.getmtime(f), reverse=True)
    return unique[:max_files]


def _parse_log_file(filepath: str, max_lines: int = 500) -> List[Dict]:
    """解析日志文件，提取训练指标"""
    metrics = []  # type: List[Dict]
    try:
        # 读取文件末尾（大文件只读最后部分）
        file_size = os.path.getsize(filepath)
        with open(filepath, "r", errors="replace") as f:
            if file_size > 100_000:
                f.seek(max(0, file_size - 100_000))
                f.readline()  # 跳过可能的不完整行
            lines = f.readlines()[-max_lines:]

        seen_epochs = set()
        for line in lines:
            for pattern in METRIC_PATTERNS:
                m = pattern.search(line)
                if m:
                    epoch = int(m.group(1))
                    if epoch in seen_epochs:
                        continue
                    seen_epochs.add(epoch)
                    entry = {"epoch": epoch, "loss": float(m.group(2))}
                    if m.group(3):
                        entry["accuracy"] = float(m.group(3))
                    metrics.append(entry)
                    break

    except Exception as e:
        logger.debug(f"解析日志失败 {filepath}: {e}")

    # 按epoch排序
    metrics.sort(key=lambda x: x["epoch"])
    return metrics


def get_training_logs(processes: List[dict]) -> List[dict]:
    """检测所有GPU进程的训练日志

    Args:
        processes: 来自task_monitor的进程列表

    Returns:
        每个检测到日志的进程的训练数据
    """
    results = []  # type: List[dict]
    seen_pids = set()

    for proc in processes:
        pid = proc.get("pid", 0)
        if pid <= 0 or pid in seen_pids:
            continue
        seen_pids.add(pid)

        cwd = _get_process_cwd(pid)
        if not cwd:
            continue

        log_files = _find_log_files(cwd)
        if not log_files:
            continue

        # 尝试从每个日志文件提取指标
        best_metrics = []  # type: List[Dict]
        best_file = ""
        for lf in log_files:
            metrics = _parse_log_file(lf)
            if len(metrics) > len(best_metrics):
                best_metrics = metrics
                best_file = lf

        results.append({
            "pid": pid,
            "gpu_index": proc.get("gpu_index", -1),
            "username": proc.get("username", "unknown"),
            "command": proc.get("command", ""),
            "working_dir": cwd,
            "log_file": best_file,
            "has_metrics": len(best_metrics) > 0,
            "metrics": best_metrics[-200:],  # 最多返回200个epoch
            "total_epochs": len(best_metrics),
            "latest": best_metrics[-1] if best_metrics else None,
        })

    return results
