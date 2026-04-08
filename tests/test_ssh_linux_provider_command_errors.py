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
from app.services.ssh_linux_gpu_collection import GPU_LIST_QUERY  # noqa: E402
from app.services.ssh_linux_provider import SshLinuxProvider  # noqa: E402


class FakeScriptedExecutor:
    def __init__(self, script):
        self.script = list(script)

    async def connect(self):
        return None

    async def run(self, command, use_sudo=False, timeout=10.0):
        if not self.script:
            raise AssertionError(f"unexpected command: {command}")
        expected, result = self.script.pop(0)
        if command != expected:
            raise AssertionError(f"unexpected command: {command}")
        return result

    async def close(self):
        return None


class SshLinuxProviderCommandErrorTests(unittest.IsolatedAsyncioTestCase):
    async def test_get_all_gpus_uses_stdout_when_stderr_is_empty(self):
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
                        code=1,
                        stdout='Field "clocks.current.sm" is not a valid field to query.\n',
                        stderr="",
                    ),
                )
            ]
        )

        with self.assertRaisesRegex(RuntimeError, "not a valid field to query"):
            await provider.get_all_gpus()

    async def test_get_all_gpus_logs_failed_command_outputs(self):
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
                        stdout="driver/library version mismatch\n",
                        stderr="",
                    ),
                )
            ]
        )

        with mock.patch("app.services.ssh_linux_provider.logger") as logger:
            with self.assertRaises(RuntimeError):
                await provider.get_all_gpus()

        logger.warning.assert_called_once()
        self.assertEqual(logger.warning.call_args.args[1], 255)
        self.assertEqual(logger.warning.call_args.args[2], GPU_LIST_QUERY)
        self.assertEqual(logger.warning.call_args.args[3], "driver/library version mismatch")
        self.assertEqual(logger.warning.call_args.args[4], "")


if __name__ == "__main__":
    unittest.main()
