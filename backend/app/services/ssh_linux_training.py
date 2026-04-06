from __future__ import annotations

import shlex

from app.services.training_log_parser import (
    LOG_FILE_PATTERNS,
    looks_like_training_process,
    parse_training_metrics,
)


LOG_FILE_LIMIT = 5
LOG_TAIL_LINES = 500


class SshLinuxTrainingCollector:
    def __init__(self, get_processes, read_optional_stdout):
        self._get_processes = get_processes
        self._read_optional_stdout = read_optional_stdout

    async def collect(self) -> list[dict]:
        results = []
        for process in await self._get_processes():
            entry = await self._collect_process(process)
            if entry is not None:
                results.append(entry)
        return results

    async def _collect_process(self, process: dict) -> dict | None:
        pid = int(process.get("pid") or 0)
        if pid <= 0:
            return None
        cwd = await self._read_cwd(pid)
        if not cwd:
            return None
        log_files = await self._find_log_files(cwd)
        if not log_files:
            return None
        log_file, metrics = await self._select_best_log(log_files)
        if not metrics and not looks_like_training_process(process, cwd, log_files):
            return None
        return {
            "pid": pid,
            "gpu_index": process.get("gpu_index", -1),
            "username": process.get("username", "unknown"),
            "command": process.get("command", ""),
            "working_dir": cwd,
            "log_file": log_file,
            "has_metrics": bool(metrics),
            "metrics": metrics,
            "total_epochs": len(metrics),
            "latest": metrics[-1] if metrics else None,
        }

    async def _read_cwd(self, pid: int) -> str:
        return await self._read_optional_stdout(
            f"readlink -f /proc/{int(pid)}/cwd 2>/dev/null"
        )

    async def _find_log_files(self, cwd: str) -> list[str]:
        command = self._find_log_command(cwd)
        stdout = await self._read_optional_stdout(command)
        return [line.strip() for line in stdout.splitlines() if line.strip()]

    def _find_log_command(self, cwd: str) -> str:
        quoted_cwd = shlex.quote(cwd)
        pattern_clause = " -o ".join(
            f"-name {shlex.quote(pattern)}"
            for pattern in LOG_FILE_PATTERNS
        )
        return (
            f"find {quoted_cwd} -maxdepth 2 -type f \\( {pattern_clause} \\) "
            "-printf '%T@ %p\\n' 2>/dev/null | sort -nr "
            f"| head -n {LOG_FILE_LIMIT} | cut -d' ' -f2-"
        )

    async def _select_best_log(self, log_files: list[str]) -> tuple[str, list[dict]]:
        best_file = ""
        best_metrics = []
        for log_file in log_files:
            metrics = parse_training_metrics(
                await self._read_optional_stdout(
                    f"tail -n {LOG_TAIL_LINES} {shlex.quote(log_file)} 2>/dev/null"
                )
            )
            if len(metrics) > len(best_metrics):
                best_file = log_file
                best_metrics = metrics
        return best_file, best_metrics
