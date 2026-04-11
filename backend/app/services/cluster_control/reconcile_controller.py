from __future__ import annotations

import asyncio
import time


DISABLED_WAIT_SECONDS = 3600.0


class ClusterReconcileController:
    def __init__(
        self,
        *,
        nodes_loader,
        reconcile_runner,
        runtime_status_reader,
        interval_seconds: float = 15.0,
        enabled: bool = False,
        task_spawner=asyncio.create_task,
    ):
        self._nodes_loader = nodes_loader
        self._reconcile_runner = reconcile_runner
        self._runtime_status_reader = runtime_status_reader
        self._interval_seconds = float(interval_seconds)
        self._enabled = bool(enabled)
        self._task_spawner = task_spawner
        self._task: asyncio.Task | None = None
        self._wake_event = asyncio.Event()
        self._closed = False
        self._run_lock = asyncio.Lock()
        self._running = False
        self._tick_count = 0
        self._last_trigger = ""
        self._last_started_at = 0.0
        self._last_finished_at = 0.0
        self._last_error = ""
        self._last_skip_reason = ""
        self._last_summary: dict = {}

    def start(self) -> None:
        if self._task is not None:
            return
        self._task = self._task_spawner(self._run_loop())

    async def shutdown(self) -> None:
        self._closed = True
        self._wake_event.set()
        if self._task is None:
            return
        await self._task
        self._task = None

    def snapshot(self) -> dict:
        return {
            "enabled": self._enabled,
            "running": self._running,
            "interval_seconds": self._interval_seconds,
            "tick_count": self._tick_count,
            "last_trigger": self._last_trigger,
            "last_started_at": self._last_started_at,
            "last_finished_at": self._last_finished_at,
            "last_error": self._last_error,
            "last_skip_reason": self._last_skip_reason,
            "last_summary": dict(self._last_summary),
        }

    def configure(
        self,
        *,
        enabled: bool | None = None,
        interval_seconds: float | None = None,
    ) -> dict:
        if enabled is not None:
            self._enabled = bool(enabled)
        if interval_seconds is not None:
            self._interval_seconds = float(interval_seconds)
        self._wake_event.set()
        return self.snapshot()

    async def run_once(self, *, trigger: str) -> dict:
        async with self._run_lock:
            self._running = True
            self._last_trigger = trigger
            self._last_started_at = time.time()
            try:
                summary = await self._run_once_inner()
                self._tick_count += 1
                self._last_summary = dict(summary)
                self._last_error = ""
                return dict(summary)
            except Exception as exc:
                self._last_error = str(exc)
                self._last_skip_reason = ""
                self._last_summary = {
                    "skipped": False,
                    "error": str(exc),
                    "trigger": trigger,
                }
                raise
            finally:
                self._running = False
                self._last_finished_at = time.time()

    async def _run_once_inner(self) -> dict:
        runtime_status = await self._runtime_status_reader()
        status = str((runtime_status or {}).get("status") or "")
        if status != "connected":
            self._last_skip_reason = f"runtime status: {status or 'unknown'}"
            return {
                "skipped": True,
                "skip_reason": self._last_skip_reason,
                "runtime_status": status or "unknown",
            }
        self._last_skip_reason = ""
        nodes = await self._nodes_loader()
        summary = await self._reconcile_runner(nodes)
        return {
            **dict(summary),
            "skipped": False,
            "runtime_status": status,
        }

    async def _run_loop(self) -> None:
        while not self._closed:
            if self._enabled:
                try:
                    await self.run_once(trigger="background")
                except Exception:
                    pass
            await self._wait_next_tick()

    async def _wait_next_tick(self) -> None:
        timeout = self._interval_seconds if self._enabled else DISABLED_WAIT_SECONDS
        self._wake_event.clear()
        try:
            await asyncio.wait_for(self._wake_event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            return
