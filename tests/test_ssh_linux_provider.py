import os
import sys
import types
import unittest
from unittest import mock


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))
sys.modules.setdefault(
    "asyncssh",
    types.SimpleNamespace(
        import_private_key=lambda *args, **kwargs: None,
        connect=lambda *args, **kwargs: None,
    ),
)

from app.services.runtime_provider import RuntimeTarget  # noqa: E402
from app.services.ssh_command_executor import CommandResult, SshCommandExecutor  # noqa: E402
from app.services.ssh_linux_parsers import parse_gpu_rows  # noqa: E402
from app.services.ssh_linux_gpu_collection import build_gpu_process_query  # noqa: E402
from app.services.ssh_linux_provider import SshLinuxProvider  # noqa: E402


class FakeHostKey:
    def __init__(self, fingerprint: str):
        self._fingerprint = fingerprint

    def get_fingerprint(self):
        return self._fingerprint


class FakeConnection:
    def __init__(self, fingerprint: str = "SHA256:actual"):
        self._fingerprint = fingerprint
        self.calls = []

    def get_server_host_key(self):
        return FakeHostKey(self._fingerprint)

    async def run(self, command, input=None, check=False, timeout=10.0):
        self.calls.append(
            {
                "command": command,
                "input": input,
                "check": check,
                "timeout": timeout,
            }
        )
        return mock.Mock(exit_status=0, stdout="ok", stderr="")


class FakeScriptedExecutor:
    def __init__(self, script):
        self.script = list(script)
        self.calls = []
        self.connected = False

    async def connect(self):
        self.connected = True

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
            self_calls = list(self.calls)
            matched = matcher(command, self_calls)
        elif isinstance(matcher, tuple) and matcher[0] == "startswith":
            matched = command.startswith(matcher[1])
        else:
            matched = command == matcher
        if not matched:
            raise AssertionError(f"unexpected command: {command}")
        return result

    async def close(self):
        self.connected = False


class SshLinuxProviderTests(unittest.IsolatedAsyncioTestCase):
    def test_parse_gpu_query_output(self):
        rows = (
            "0, GPU-aaa, RTX 4090, 61, 280.5, 320.0, 87, 40, 8192, "
            "24564, 16372, 35, 2100, 10500\n"
        )

        parsed = parse_gpu_rows(rows, timestamp=1.0)

        self.assertEqual(parsed[0]["index"], 0)
        self.assertEqual(parsed[0]["uuid"], "GPU-aaa")
        self.assertEqual(parsed[0]["name"], "RTX 4090")
        self.assertEqual(parsed[0]["power_limit"], 320.0)
        self.assertEqual(parsed[0]["timestamp"], 1.0)

    async def test_executor_rejects_host_fingerprint_mismatch(self):
        target = RuntimeTarget(
            provider_type="ssh_linux",
            label="训练机 A",
            host="10.0.0.8",
            port=22,
            username="gpuops",
            auth_type="password",
            host_fingerprint="SHA256:expected",
        )
        executor = SshCommandExecutor(
            target,
            {"password": "pw", "sudo_password": "rootpw"},
        )

        with mock.patch(
            "app.services.ssh_command_executor.asyncssh.connect",
            new=mock.AsyncMock(return_value=FakeConnection()),
        ):
            with self.assertRaisesRegex(ValueError, "host fingerprint"):
                await executor.connect()

    async def test_executor_wraps_sudo_command(self):
        target = RuntimeTarget(
            provider_type="ssh_linux",
            label="训练机 A",
            host="10.0.0.8",
            port=22,
            username="gpuops",
            auth_type="password",
        )
        executor = SshCommandExecutor(
            target,
            {"password": "pw", "sudo_password": "rootpw"},
        )
        executor._connection = FakeConnection("SHA256:expected")

        result = await executor.run("nvidia-smi -i 0 -pl 250", use_sudo=True)

        self.assertEqual(result.code, 0)
        self.assertEqual(
            executor._connection.calls[0]["command"],
            "sudo -S -p '' nvidia-smi -i 0 -pl 250",
        )
        self.assertEqual(executor._connection.calls[0]["input"], "rootpw\n")

    async def test_executor_formats_permission_denied_as_auth_error(self):
        target = RuntimeTarget(
            provider_type="ssh_linux",
            label="训练机 A",
            host="10.151.225.108",
            port=22,
            username="DELL",
            auth_type="password",
        )
        executor = SshCommandExecutor(
            target,
            {"password": "bad"},
        )

        with mock.patch(
            "app.services.ssh_command_executor.asyncssh.connect",
            new=mock.AsyncMock(
                side_effect=OSError("Permission denied for user DELL on host 10.151.225.108")
            ),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "SSH 认证失败：目标主机拒绝用户 DELL 登录",
            ):
                await executor.connect()

    async def test_get_system_info_parses_proc_snapshots(self):
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
                    "cat /proc/stat",
                    CommandResult(
                        code=0,
                        stdout="cpu  100 0 50 400 0 0 0 0 0 0\n",
                        stderr="",
                    ),
                ),
                (
                    "cat /proc/stat",
                    CommandResult(
                        code=0,
                        stdout="cpu  140 0 70 420 0 0 0 0 0 0\n",
                        stderr="",
                    ),
                ),
                (
                    "cat /proc/meminfo",
                    CommandResult(
                        code=0,
                        stdout=(
                            "MemTotal:       32768000 kB\n"
                            "MemAvailable:   16384000 kB\n"
                            "MemFree:        12000000 kB\n"
                        ),
                        stderr="",
                    ),
                ),
                (
                    "cat /proc/loadavg",
                    CommandResult(code=0, stdout="1.25 0.50 0.25 2/200 1234\n", stderr=""),
                ),
                (
                    "nproc",
                    CommandResult(code=0, stdout="32\n", stderr=""),
                ),
            ]
        )

        with mock.patch(
            "app.services.ssh_linux_provider.asyncio.sleep",
            new=mock.AsyncMock(),
        ):
            with mock.patch("app.services.ssh_linux_provider.time.time", return_value=1000.0):
                system = await provider.get_system_info()

        self.assertEqual(system["cpu_percent"], 75.0)
        self.assertEqual(system["cpu_count"], 32)
        self.assertEqual(system["memory_total"], 32768000 * 1024)
        self.assertEqual(system["memory_used"], 16384000 * 1024)
        self.assertEqual(system["memory_percent"], 50.0)
        self.assertEqual(system["load_avg"], [1.25, 0.5, 0.25])
        self.assertEqual(system["timestamp"], 1000.0)

    async def test_get_system_detail_parses_linux_snapshots(self):
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
                    "cat /proc/stat",
                    CommandResult(
                        code=0,
                        stdout=(
                            "cpu  100 0 50 400 0 0 0 0 0 0\n"
                            "cpu0 50 0 25 200 0 0 0 0 0 0\n"
                            "cpu1 50 0 25 200 0 0 0 0 0 0\n"
                        ),
                        stderr="",
                    ),
                ),
                (
                    "cat /proc/stat",
                    CommandResult(
                        code=0,
                        stdout=(
                            "cpu  140 0 70 420 0 0 0 0 0 0\n"
                            "cpu0 80 0 35 210 0 0 0 0 0 0\n"
                            "cpu1 60 0 35 210 0 0 0 0 0 0\n"
                        ),
                        stderr="",
                    ),
                ),
                (
                    "cat /proc/meminfo",
                    CommandResult(
                        code=0,
                        stdout=(
                            "MemTotal:       32768000 kB\n"
                            "MemAvailable:   16384000 kB\n"
                            "MemFree:        12000000 kB\n"
                            "SwapTotal:       8192000 kB\n"
                            "SwapFree:        4096000 kB\n"
                        ),
                        stderr="",
                    ),
                ),
                (
                    "cat /proc/loadavg",
                    CommandResult(code=0, stdout="1.25 0.50 0.25 2/200 1234\n", stderr=""),
                ),
                (
                    "nproc",
                    CommandResult(code=0, stdout="32\n", stderr=""),
                ),
                (
                    "cat /proc/cpuinfo",
                    CommandResult(
                        code=0,
                        stdout=(
                            "processor\t: 0\nphysical id\t: 0\ncore id\t\t: 0\n\n"
                            "processor\t: 1\nphysical id\t: 0\ncore id\t\t: 1\n"
                        ),
                        stderr="",
                    ),
                ),
                (
                    "cat /proc/uptime",
                    CommandResult(code=0, stdout="3600.00 0.00\n", stderr=""),
                ),
                (
                    "df -B1 --output=source,target,fstype,size,used,avail,pcent",
                    CommandResult(
                        code=0,
                        stdout=(
                            "Filesystem     Mounted on Type       1B-blocks        Used       Avail Use%\n"
                            "/dev/nvme0n1p1 /          ext4     1000000000   400000000   600000000  40%\n"
                        ),
                        stderr="",
                    ),
                ),
                (
                    "cat /proc/net/dev",
                    CommandResult(
                        code=0,
                        stdout=(
                            "Inter-|   Receive                                                |  Transmit\n"
                            " face |bytes    packets errs drop fifo frame compressed multicast|bytes    packets errs drop fifo colls carrier compressed\n"
                            "  eth0: 1000 10 0 0 0 0 0 0 2000 20 0 0 0 0 0 0\n"
                        ),
                        stderr="",
                    ),
                ),
            ]
        )

        with mock.patch(
            "app.services.ssh_linux_provider.asyncio.sleep",
            new=mock.AsyncMock(),
        ):
            with mock.patch("app.services.ssh_linux_provider.time.time", return_value=1000.0):
                detail = await provider.get_system_detail()

        self.assertEqual(detail["cpu_percent"], 75.0)
        self.assertEqual(detail["cpu_count"], 32)
        self.assertEqual(detail["cpu_count_physical"], 2)
        self.assertEqual(detail["cpu_per_core"], [80.0, 66.7])
        self.assertEqual(detail["swap_total"], 8192000 * 1024)
        self.assertEqual(detail["swap_used"], 4096000 * 1024)
        self.assertEqual(detail["network"]["bytes_sent"], 2000)
        self.assertEqual(detail["network"]["bytes_recv"], 1000)
        self.assertEqual(detail["boot_time"], -2600.0)
        self.assertEqual(detail["disks"][0]["mountpoint"], "/")

    async def test_get_training_logs_reads_remote_log_metrics(self):
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
                    "nvidia-smi -L",
                    CommandResult(
                        code=0,
                        stdout="GPU 0: NVIDIA GeForce RTX 4090 (UUID: GPU-aaa)\n",
                        stderr="",
                    ),
                ),
                (
                    build_gpu_process_query(0),
                    CommandResult(code=0, stdout="1234, GPU-aaa, 4096\n", stderr=""),
                ),
                (
                    lambda command, calls: command.startswith("ps -ww -p 1234 "),
                    CommandResult(
                        code=0,
                        stdout="1234 alice python 3600 12.5 python train.py --epochs 3\n",
                        stderr="",
                    ),
                ),
                (
                    "readlink -f /proc/1234/cwd 2>/dev/null",
                    CommandResult(code=0, stdout="/workspace/project\n", stderr=""),
                ),
                (
                    ("startswith", "find /workspace/project "),
                    CommandResult(code=0, stdout="/workspace/project/train.log\n", stderr=""),
                ),
                (
                    "tail -n 500 /workspace/project/train.log 2>/dev/null",
                    CommandResult(
                        code=0,
                        stdout=(
                            "Epoch 1/3, loss: 0.5234, acc: 0.8912\n"
                            "Epoch 2/3, loss: 0.4234, acc: 0.9012\n"
                        ),
                        stderr="",
                    ),
                ),
            ]
        )

        logs = await provider.get_training_logs()

        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["pid"], 1234)
        self.assertEqual(logs[0]["gpu_index"], 0)
        self.assertTrue(logs[0]["has_metrics"])
        self.assertEqual(logs[0]["working_dir"], "/workspace/project")
        self.assertEqual(logs[0]["log_file"], "/workspace/project/train.log")
        self.assertEqual(logs[0]["total_epochs"], 2)
        self.assertEqual(logs[0]["latest"]["epoch"], 2)
        self.assertEqual(logs[0]["latest"]["loss"], 0.4234)
        self.assertEqual(logs[0]["latest"]["accuracy"], 0.9012)

    async def test_get_processes_merges_compute_apps_with_ps_rows(self):
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
                    "nvidia-smi -L",
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
                    CommandResult(code=0, stdout="1234, GPU-aaa, 4096\n", stderr=""),
                ),
                (
                    build_gpu_process_query(1),
                    CommandResult(code=0, stdout="2345, GPU-bbb, 2048\n", stderr=""),
                ),
                (
                    lambda command, calls: command.startswith("ps -ww -p 1234,2345 "),
                    CommandResult(
                        code=0,
                        stdout=(
                            "1234 alice python 3600 12.5 python train.py --epochs 3\n"
                            "2345 bob torchrun 1800 22.0 torchrun --nproc_per_node 2 app.py\n"
                        ),
                        stderr="",
                    ),
                ),
            ]
        )

        with mock.patch("app.services.ssh_linux_provider.time.time", return_value=10000.0):
            processes = await provider.get_processes()

        self.assertEqual([item["gpu_index"] for item in processes], [0, 1])
        self.assertEqual(processes[0]["pid"], 1234)
        self.assertEqual(processes[0]["username"], "alice")
        self.assertEqual(processes[0]["name"], "python")
        self.assertEqual(processes[0]["command"], "python train.py --epochs 3")
        self.assertEqual(processes[0]["cpu_percent"], 12.5)
        self.assertEqual(processes[0]["create_time"], 6400.0)
        self.assertEqual(processes[0]["gpu_memory_used"], 4096 * 1024 * 1024)
        self.assertTrue(processes[0]["manageable"])
        self.assertEqual(processes[0]["process_category"], "governable")
        self.assertEqual(processes[1]["gpu_memory_used"], 2048 * 1024 * 1024)

    async def test_pause_resume_terminate_send_control_signals(self):
        target = RuntimeTarget(
            provider_type="ssh_linux",
            label="训练机 A",
            host="10.0.0.8",
            port=22,
            username="gpuops",
            auth_type="password",
            sudo_enabled=True,
        )
        provider = SshLinuxProvider(target, {"password": "pw", "sudo_password": "rootpw"})
        provider.executor = FakeScriptedExecutor(
            [
                ("kill -STOP 321", CommandResult(code=0, stdout="", stderr="")),
                ("kill -CONT 321", CommandResult(code=0, stdout="", stderr="")),
                ("kill -TERM 321", CommandResult(code=0, stdout="", stderr="")),
            ]
        )

        paused = await provider.pause_task(321)
        resumed = await provider.resume_task(321)
        terminated = await provider.terminate_task(321)

        self.assertTrue(paused["success"])
        self.assertTrue(resumed["success"])
        self.assertTrue(terminated["success"])
        self.assertEqual(
            [item["command"] for item in provider.executor.calls],
            ["kill -STOP 321", "kill -CONT 321", "kill -TERM 321"],
        )
        self.assertEqual(
            [item["use_sudo"] for item in provider.executor.calls],
            [True, True, True],
        )


if __name__ == "__main__":
    unittest.main()
