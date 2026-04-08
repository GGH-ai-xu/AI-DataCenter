from __future__ import annotations

import asyncio
import logging
import time

from app.services.ssh_command_executor import SshCommandExecutor
from app.services.ssh_linux_gpu_collection import (
    GPU_LIST_QUERY,
    collect_gpu_process_output,
    collect_gpu_rows,
    command_error_message,
    parse_gpu_inventory,
)
from app.services.ssh_linux_parsers import (
    build_system_info,
    calculate_cpu_percent,
    merge_process_rows,
    parse_compute_process_rows,
    parse_gpu_rows,
    parse_load_average,
    parse_meminfo,
    parse_ps_rows,
)
from app.services.ssh_linux_system_detail import (
    calculate_cpu_per_core,
    parse_cpuinfo_physical_count,
    parse_disk_rows,
    parse_network_counters,
    parse_proc_stat_snapshot,
    parse_uptime_seconds,
)
from app.services.ssh_linux_training import SshLinuxTrainingCollector


logger = logging.getLogger(__name__)
PROC_STAT_QUERY = "cat /proc/stat"
MEMINFO_QUERY = "cat /proc/meminfo"
LOADAVG_QUERY = "cat /proc/loadavg"
CPU_COUNT_QUERY = "nproc"
CPUINFO_QUERY = "cat /proc/cpuinfo"
UPTIME_QUERY = "cat /proc/uptime"
DISK_QUERY = "df -B1 --output=source,target,fstype,size,used,avail,pcent"
NETDEV_QUERY = "cat /proc/net/dev"
CPU_SAMPLE_INTERVAL_SECONDS = 0.2
PS_QUERY_TEMPLATE = "ps -ww -p {pid_list} -o pid= -o user= -o comm= -o etimes= -o pcpu= -o args="


class SshLinuxProvider:
    def __init__(self, target, secret: dict | None = None):
        self.target = target
        self.executor = SshCommandExecutor(target, secret)
        self._host_fingerprint = target.host_fingerprint
        self._last_cpu_sample = None
        self._sudo_ready = False

    def capabilities_snapshot(self) -> dict:
        return {
            "host_fingerprint": self._host_fingerprint,
            "sudo_ready": self._sudo_ready,
        }

    async def health_check(self) -> dict | None:
        await self._ensure_connected()
        result = await self.executor.run("true")
        if result.code != 0:
            return None
        self._sudo_ready = await self._probe_sudo_ready()
        return {"status": "ok"}

    async def get_all_gpus(self) -> list[dict]:
        return await collect_gpu_rows(
            run_command=self._run_command,
            log_failed_command=self._log_failed_command,
            timestamp=time.time(),
        )

    async def get_system_info(self) -> dict | None:
        cpu_percent, _ = await self._read_cpu_metrics()
        meminfo, load_average, cpu_count = await self._read_system_basics()
        return build_system_info(
            cpu_count=cpu_count,
            cpu_percent=cpu_percent,
            meminfo=meminfo,
            load_average=load_average,
            timestamp=time.time(),
        )

    async def get_system_detail(self) -> dict | None:
        cpu_percent, cpu_per_core = await self._read_cpu_metrics(include_per_core=True)
        meminfo, load_average, cpu_count = await self._read_system_basics()
        cpuinfo_raw, uptime_raw, disk_raw, netdev_raw = await asyncio.gather(
            self._read_stdout(CPUINFO_QUERY),
            self._read_stdout(UPTIME_QUERY),
            self._read_stdout(DISK_QUERY),
            self._read_stdout(NETDEV_QUERY),
        )
        timestamp = time.time()
        detail = build_system_info(
            cpu_count=cpu_count,
            cpu_percent=cpu_percent,
            meminfo=meminfo,
            load_average=load_average,
            timestamp=timestamp,
        )
        swap_total = meminfo.get("SwapTotal", 0)
        swap_used = max(0, swap_total - meminfo.get("SwapFree", 0))
        detail.update(
            {
                "cpu_count_physical": parse_cpuinfo_physical_count(cpuinfo_raw, cpu_count),
                "cpu_per_core": cpu_per_core,
                "memory_available": meminfo.get("MemAvailable", meminfo.get("MemFree", 0)),
                "swap_total": swap_total,
                "swap_used": swap_used,
                "swap_percent": round(swap_used / swap_total * 100.0, 1) if swap_total else 0.0,
                "disks": parse_disk_rows(disk_raw),
                "network": parse_network_counters(netdev_raw),
                "boot_time": timestamp - parse_uptime_seconds(uptime_raw),
            }
        )
        return detail

    async def get_training_logs(self) -> list[dict]:
        collector = SshLinuxTrainingCollector(
            get_processes=self.get_processes,
            read_optional_stdout=self._read_optional_stdout,
        )
        return await collector.collect()

    async def get_processes(self) -> list[dict]:
        inventory_result = await self._run_command(GPU_LIST_QUERY)
        identities, _, _ = parse_gpu_inventory(inventory_result, time.time())
        if inventory_result.code != 0:
            if not identities:
                self._log_failed_command(inventory_result, GPU_LIST_QUERY)
                raise RuntimeError(command_error_message(inventory_result, GPU_LIST_QUERY))
        gpu_map = {
            item["uuid"]: int(item["index"])
            for item in identities
            if item.get("uuid")
        }
        compute_output = await collect_gpu_process_output(
            run_command=self._run_command,
            log_failed_command=self._log_failed_command,
            identities=identities,
        )
        compute_rows = parse_compute_process_rows(
            compute_output,
            gpu_map,
        )
        if not compute_rows:
            return []
        process_details = parse_ps_rows(
            (await self._run_checked(self._ps_query(compute_rows))).stdout,
            time.time(),
        )
        return merge_process_rows(compute_rows, process_details)

    async def set_power_limit(self, gpu_index: int, power_limit: int) -> dict:
        await self._ensure_connected()
        result = await self.executor.run(
            f"nvidia-smi -i {int(gpu_index)} -pl {int(power_limit)}",
            use_sudo=self.target.sudo_enabled,
        )
        return {
            "success": result.code == 0,
            "gpu_index": int(gpu_index),
            "power_limit": int(power_limit),
            "error": result.stderr.strip(),
        }

    async def pause_task(self, pid: int) -> dict:
        return await self._run_signal(pid, "STOP")

    async def resume_task(self, pid: int) -> dict:
        return await self._run_signal(pid, "CONT")

    async def terminate_task(self, pid: int) -> dict:
        return await self._run_signal(pid, "TERM")

    async def close(self) -> None:
        await self.executor.close()

    async def _ensure_connected(self) -> None:
        await self.executor.connect()
        self._host_fingerprint = (
            getattr(self.executor, "server_fingerprint", None)
            or self._host_fingerprint
        )

    async def _run_command(self, command: str, use_sudo: bool = False):
        await self._ensure_connected()
        return await self.executor.run(command, use_sudo=use_sudo)

    async def _run_checked(self, command: str, use_sudo: bool = False):
        result = await self._run_command(command, use_sudo=use_sudo)
        if result.code == 0:
            return result
        self._log_failed_command(result, command)
        raise RuntimeError(command_error_message(result, command))

    async def _probe_sudo_ready(self) -> bool:
        if not self.target.sudo_enabled:
            return False
        result = await self.executor.run("true", use_sudo=True)
        return result.code == 0

    async def _read_cpu_metrics(
        self,
        include_per_core: bool = False,
    ) -> tuple[float, list[float]]:
        previous, current = await self._read_cpu_snapshot_pair()
        cpu_percent = calculate_cpu_percent(previous[0], current[0])
        if not include_per_core:
            return cpu_percent, []
        return cpu_percent, calculate_cpu_per_core(previous[1], current[1])

    async def _read_cpu_snapshot_pair(
        self,
    ) -> tuple[tuple[tuple[int, int], list[tuple[int, int]]], tuple[tuple[int, int], list[tuple[int, int]]]]:
        current = parse_proc_stat_snapshot(await self._read_stdout(PROC_STAT_QUERY))
        if self._last_cpu_sample is None:
            await asyncio.sleep(CPU_SAMPLE_INTERVAL_SECONDS)
            follow_up = parse_proc_stat_snapshot(await self._read_stdout(PROC_STAT_QUERY))
            self._last_cpu_sample = follow_up
            return current, follow_up
        previous = self._last_cpu_sample
        self._last_cpu_sample = current
        return previous, current

    async def _read_system_basics(self) -> tuple[dict[str, int], list[float], int]:
        meminfo_raw, loadavg_raw, cpu_count_raw = await asyncio.gather(
            self._read_stdout(MEMINFO_QUERY),
            self._read_stdout(LOADAVG_QUERY),
            self._read_stdout(CPU_COUNT_QUERY),
        )
        return (
            parse_meminfo(meminfo_raw),
            parse_load_average(loadavg_raw),
            int(cpu_count_raw.strip() or 0),
        )

    async def _read_stdout(self, command: str) -> str:
        return (await self._run_checked(command)).stdout

    async def _read_optional_stdout(self, command: str) -> str:
        result = await self._run_command(command)
        if result.code != 0:
            return ""
        return result.stdout.strip()

    def _ps_query(self, compute_rows: list[dict]) -> str:
        pid_list = ",".join(
            str(item["pid"])
            for item in compute_rows
        )
        return PS_QUERY_TEMPLATE.format(pid_list=pid_list)

    def _log_failed_command(self, result, command: str) -> None:
        logger.warning(
            "SSH command failed: code=%s command=%s stdout=%s stderr=%s",
            result.code,
            command,
            result.stdout.strip(),
            result.stderr.strip(),
        )

    async def _run_signal(self, pid: int, signal: str) -> dict:
        await self._ensure_connected()
        normalized_pid = int(pid)
        result = await self.executor.run(
            f"kill -{signal} {normalized_pid}",
            use_sudo=self.target.sudo_enabled,
        )
        return {
            "success": result.code == 0,
            "pid": normalized_pid,
            "signal": signal,
            "error": result.stderr.strip(),
        }
