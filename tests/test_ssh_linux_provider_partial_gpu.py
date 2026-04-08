import os
import sys
import types
import unittest
from unittest import mock


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))
sys.modules.setdefault(
    "asyncssh",
    types.SimpleNamespace(import_private_key=lambda *args, **kwargs: None),
)

from app.services.runtime_provider import RuntimeTarget  # noqa: E402
from app.services.ssh_command_executor import CommandResult  # noqa: E402
from app.services.ssh_linux_gpu_collection import (  # noqa: E402
    GPU_LIST_QUERY,
    build_gpu_process_query,
    build_gpu_metrics_query,
)
from app.services.ssh_linux_parsers import parse_gpu_list_rows  # noqa: E402
from app.services.ssh_linux_provider import SshLinuxProvider  # noqa: E402


class FakeScriptedExecutor:
    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    async def connect(self):
        return None

    async def run(self, command, use_sudo=False, timeout=10.0):
        self.calls.append(
            {
                "command": command,
                "use_sudo": use_sudo,
                "timeout": timeout,
            }
        )
        if not self.script:
            raise AssertionError(f"unexpected command: {command}")
        matcher, result = self.script.pop(0)
        if callable(matcher):
            matched = matcher(command, list(self.calls))
        else:
            matched = command == matcher
        if not matched:
            raise AssertionError(f"unexpected command: {command}")
        return result

    async def close(self):
        return None


class SshLinuxProviderPartialGpuTests(unittest.IsolatedAsyncioTestCase):
    def test_parse_gpu_list_rows_extracts_index_name_and_uuid(self):
        raw = "GPU 0: NVIDIA GeForce RTX 4090 (UUID: GPU-aaa)\nGPU 2: NVIDIA A800 (UUID: GPU-bbb)\n"

        parsed = parse_gpu_list_rows(raw)

        self.assertEqual(
            parsed,
            [
                {"index": 0, "name": "NVIDIA GeForce RTX 4090", "uuid": "GPU-aaa", "pci_bus_id": ""},
                {"index": 2, "name": "NVIDIA A800", "uuid": "GPU-bbb", "pci_bus_id": ""},
            ],
        )

    async def test_get_all_gpus_returns_available_and_unavailable_rows(self):
        target = RuntimeTarget(
            provider_type="ssh_linux",
            label="训练机 A",
            host="10.0.0.8",
            port=22,
            username="gpuops",
            auth_type="password",
        )
        provider = SshLinuxProvider(target, {"password": "pw"})
        provider.executor = FakeScriptedExecutor(
            [
                (
                    GPU_LIST_QUERY,
                    CommandResult(
                        code=0,
                        stdout=(
                            "GPU 0: NVIDIA GeForce RTX 4090 (UUID: GPU-aaa)\n"
                            "GPU 1: NVIDIA GeForce RTX 4090 (UUID: GPU-bbb)\n"
                        ),
                        stderr="",
                    ),
                ),
                (
                    build_gpu_metrics_query(0),
                    CommandResult(
                        code=0,
                        stdout=(
                            "0, GPU-aaa, NVIDIA GeForce RTX 4090, 00000000:17:00.0, 61, 280.5, "
                            "320.0, 87, 40, 8192, 24564, 16372, 35, 2100, 10500\n"
                        ),
                        stderr="",
                    ),
                ),
                (
                    build_gpu_metrics_query(1),
                    CommandResult(
                        code=255,
                        stdout="Unable to determine the device handle for GPU0000:65:00.0: Unknown Error\n",
                        stderr="",
                    ),
                ),
            ]
        )

        with mock.patch.object(provider, "_log_failed_command") as log_failed_command:
            with mock.patch("app.services.ssh_linux_provider.time.time", return_value=1000.0):
                rows = await provider.get_all_gpus()

        log_failed_command.assert_not_called()
        self.assertEqual([row["index"] for row in rows], [0, 1])
        self.assertEqual(rows[0]["available"], True)
        self.assertEqual(rows[0]["status"], "ok")
        self.assertEqual(rows[1]["available"], False)
        self.assertEqual(rows[1]["status"], "error")
        self.assertIn("Unknown Error", rows[1]["error"])
        self.assertIn("65:00.0", rows[1]["pci_bus_id"])

    async def test_get_all_gpus_uses_partial_gpu_inventory_when_list_command_fails(self):
        target = RuntimeTarget(
            provider_type="ssh_linux",
            label="训练机 A",
            host="10.0.0.8",
            port=22,
            username="gpuops",
            auth_type="password",
        )
        provider = SshLinuxProvider(target, {"password": "pw"})
        provider.executor = FakeScriptedExecutor(
            [
                (
                    GPU_LIST_QUERY,
                    CommandResult(
                        code=255,
                        stdout=(
                            "Unable to determine the device handle for GPU0000:17:00.0: Unknown Error\n"
                            "GPU 1: NVIDIA GeForce RTX 3090 (UUID: GPU-bbb)\n"
                            "GPU 2: NVIDIA GeForce RTX 3090 (UUID: GPU-ccc)\n"
                        ),
                        stderr="",
                    ),
                ),
                (
                    build_gpu_metrics_query(1),
                    CommandResult(
                        code=0,
                        stdout=(
                            "1, GPU-bbb, NVIDIA GeForce RTX 3090, 00000000:65:00.0, 54, 265.0, "
                            "350.0, 75, 35, 4096, 24564, 20468, 30, 1890, 9751\n"
                        ),
                        stderr="",
                    ),
                ),
                (
                    build_gpu_metrics_query(2),
                    CommandResult(
                        code=0,
                        stdout=(
                            "2, GPU-ccc, NVIDIA GeForce RTX 3090, 00000000:B3:00.0, 48, 240.0, "
                            "350.0, 62, 28, 2048, 24564, 22516, 28, 1800, 9501\n"
                        ),
                        stderr="",
                    ),
                ),
            ]
        )

        with mock.patch.object(provider, "_log_failed_command") as log_failed_command:
            with mock.patch("app.services.ssh_linux_provider.time.time", return_value=1000.0):
                rows = await provider.get_all_gpus()

        log_failed_command.assert_not_called()
        self.assertEqual([row["index"] for row in rows], [0, 1, 2])
        self.assertEqual(rows[0]["available"], False)
        self.assertEqual(rows[0]["status"], "error")
        self.assertEqual(rows[0]["name"], "Unknown GPU")
        self.assertIn("17:00.0", rows[0]["pci_bus_id"])
        self.assertEqual(rows[1]["available"], True)
        self.assertEqual(rows[2]["available"], True)

    async def test_get_all_gpus_raises_when_all_gpus_are_unavailable(self):
        target = RuntimeTarget(
            provider_type="ssh_linux",
            label="训练机 A",
            host="10.0.0.8",
            port=22,
            username="gpuops",
            auth_type="password",
        )
        provider = SshLinuxProvider(target, {"password": "pw"})
        provider.executor = FakeScriptedExecutor(
            [
                (
                    GPU_LIST_QUERY,
                    CommandResult(
                        code=0,
                        stdout="GPU 0: NVIDIA GeForce RTX 4090 (UUID: GPU-aaa)\n",
                        stderr="",
                    ),
                ),
                (
                    build_gpu_metrics_query(0),
                    CommandResult(
                        code=255,
                        stdout="Unable to determine the device handle for GPU0000:17:00.0: Unknown Error\n",
                        stderr="",
                    ),
                ),
            ]
        )

        with self.assertRaisesRegex(RuntimeError, "GPU 0"):
            await provider.get_all_gpus()

    async def test_get_processes_uses_gpu_list_mapping(self):
        target = RuntimeTarget(
            provider_type="ssh_linux",
            label="训练机 A",
            host="10.0.0.8",
            port=22,
            username="gpuops",
            auth_type="password",
        )
        provider = SshLinuxProvider(target, {"password": "pw"})
        provider.executor = FakeScriptedExecutor(
            [
                (
                    GPU_LIST_QUERY,
                    CommandResult(
                        code=0,
                        stdout=(
                            "GPU 0: NVIDIA GeForce RTX 4090 (UUID: GPU-aaa)\n"
                            "GPU 1: NVIDIA GeForce RTX 4090 (UUID: GPU-bbb)\n"
                        ),
                        stderr="",
                    ),
                ),
                (
                    build_gpu_process_query(0),
                    CommandResult(
                        code=0,
                        stdout="1234, GPU-aaa, 4096\n",
                        stderr="",
                    ),
                ),
                (
                    build_gpu_process_query(1),
                    CommandResult(
                        code=0,
                        stdout="",
                        stderr="",
                    ),
                ),
                (
                    lambda command, calls: command.startswith("ps -ww -p 1234 "),
                    CommandResult(
                        code=0,
                        stdout="1234 alice python 3600 12.5 python train.py\n",
                        stderr="",
                    ),
                ),
            ]
        )

        with mock.patch("app.services.ssh_linux_provider.time.time", return_value=1000.0):
            rows = await provider.get_processes()

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["gpu_index"], 0)
        self.assertEqual(rows[0]["pid"], 1234)

    async def test_get_processes_uses_partial_gpu_inventory_when_list_command_fails(self):
        target = RuntimeTarget(
            provider_type="ssh_linux",
            label="训练机 A",
            host="10.0.0.8",
            port=22,
            username="gpuops",
            auth_type="password",
        )
        provider = SshLinuxProvider(target, {"password": "pw"})
        provider.executor = FakeScriptedExecutor(
            [
                (
                    GPU_LIST_QUERY,
                    CommandResult(
                        code=255,
                        stdout=(
                            "Unable to determine the device handle for GPU0000:17:00.0: Unknown Error\n"
                            "GPU 1: NVIDIA GeForce RTX 3090 (UUID: GPU-bbb)\n"
                            "GPU 2: NVIDIA GeForce RTX 3090 (UUID: GPU-ccc)\n"
                        ),
                        stderr="",
                    ),
                ),
                (
                    build_gpu_process_query(1),
                    CommandResult(
                        code=0,
                        stdout="1234, GPU-bbb, 4096\n",
                        stderr="",
                    ),
                ),
                (
                    build_gpu_process_query(2),
                    CommandResult(
                        code=0,
                        stdout="",
                        stderr="",
                    ),
                ),
                (
                    lambda command, calls: command.startswith("ps -ww -p 1234 "),
                    CommandResult(
                        code=0,
                        stdout="1234 alice python 3600 12.5 python train.py\n",
                        stderr="",
                    ),
                ),
            ]
        )

        with mock.patch.object(provider, "_log_failed_command") as log_failed_command:
            with mock.patch("app.services.ssh_linux_provider.time.time", return_value=1000.0):
                rows = await provider.get_processes()

        log_failed_command.assert_not_called()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["gpu_index"], 1)
        self.assertEqual(rows[0]["pid"], 1234)

    async def test_get_processes_keeps_partial_rows_when_one_gpu_process_query_fails(self):
        target = RuntimeTarget(
            provider_type="ssh_linux",
            label="训练机 A",
            host="10.0.0.8",
            port=22,
            username="gpuops",
            auth_type="password",
        )
        provider = SshLinuxProvider(target, {"password": "pw"})
        provider.executor = FakeScriptedExecutor(
            [
                (
                    GPU_LIST_QUERY,
                    CommandResult(
                        code=255,
                        stdout=(
                            "Unable to determine the device handle for GPU0000:17:00.0: Unknown Error\n"
                            "GPU 1: NVIDIA GeForce RTX 3090 (UUID: GPU-bbb)\n"
                            "GPU 2: NVIDIA GeForce RTX 3090 (UUID: GPU-ccc)\n"
                        ),
                        stderr="",
                    ),
                ),
                (
                    build_gpu_process_query(1),
                    CommandResult(
                        code=0,
                        stdout="1234, GPU-bbb, 4096\n",
                        stderr="",
                    ),
                ),
                (
                    build_gpu_process_query(2),
                    CommandResult(
                        code=255,
                        stdout="Unable to determine the device handle for GPU0000:17:00.0: Unknown Error\n",
                        stderr="",
                    ),
                ),
                (
                    lambda command, calls: command.startswith("ps -ww -p 1234 "),
                    CommandResult(
                        code=0,
                        stdout="1234 alice python 3600 12.5 python train.py\n",
                        stderr="",
                    ),
                ),
            ]
        )

        with mock.patch.object(provider, "_log_failed_command") as log_failed_command:
            with mock.patch("app.services.ssh_linux_provider.time.time", return_value=1000.0):
                rows = await provider.get_processes()

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["gpu_index"], 1)
        self.assertEqual(rows[0]["pid"], 1234)
        log_failed_command.assert_not_called()


if __name__ == "__main__":
    unittest.main()
