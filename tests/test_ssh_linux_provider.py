import os
import sys
import types
import unittest


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.services.ssh_command_executor import CommandResult  # noqa: E402
from app.services.ssh_linux_provider import SshLinuxProvider  # noqa: E402


class FakeExecutor:
    def __init__(self, results):
        self._results = list(results)
        self.calls = []

    async def run(self, command, use_sudo=False, timeout=10.0):
        self.calls.append(
            {
                "command": command,
                "use_sudo": use_sudo,
                "timeout": timeout,
            }
        )
        return self._results.pop(0)


def build_provider(results):
    provider = SshLinuxProvider(
        types.SimpleNamespace(
            host="gpu-host",
            port=22,
            username="dell",
            sudo_enabled=False,
            host_fingerprint=None,
        )
    )
    provider.executor = FakeExecutor(results)

    async def ensure_connected():
        return None

    provider._ensure_connected = ensure_connected
    return provider


class SshLinuxProviderPowerLimitTests(unittest.IsolatedAsyncioTestCase):
    async def test_set_power_limit_uses_stdout_when_stderr_is_empty(self):
        provider = build_provider(
            [
                CommandResult(
                    code=1,
                    stdout="Insufficient Permissions\n",
                    stderr="",
                )
            ]
        )

        result = await provider.set_power_limit(1, 220)

        self.assertFalse(result["success"])
        self.assertIn("Insufficient Permissions", result["error"])

    async def test_set_power_limit_rejects_scope_unsupported_stdout(self):
        provider = build_provider(
            [
                CommandResult(
                    code=0,
                    stdout=(
                        "Changing power management limit is not supported in current "
                        "scope for GPU: 00000000:65:00.0.\nAll done.\n"
                    ),
                    stderr="",
                )
            ]
        )

        result = await provider.set_power_limit(1, 220)

        self.assertFalse(result["success"])
        self.assertIn("not supported in current scope", result["error"].lower())
        self.assertEqual(len(provider.executor.calls), 1)

    async def test_set_power_limit_rejects_when_readback_does_not_match_target(self):
        provider = build_provider(
            [
                CommandResult(code=0, stdout="All done.\n", stderr=""),
                CommandResult(code=0, stdout="225.0\n", stderr=""),
            ]
        )

        result = await provider.set_power_limit(1, 220)

        self.assertFalse(result["success"])
        self.assertIn("未生效", result["error"])
        self.assertIn("225.0W", result["error"])


if __name__ == "__main__":
    unittest.main()
