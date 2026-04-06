import os
import sys
import unittest


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.services.runtime_provider import RuntimeTarget  # noqa: E402
from app.services.runtime_provider_manager import RuntimeProviderManager  # noqa: E402


class FakeProvider:
    def __init__(self, label: str):
        self.label = label
        self.closed = False

    async def health_check(self):
        return {"status": "ok"}

    async def close(self):
        self.closed = True


class ExplodingProvider(FakeProvider):
    async def health_check(self):
        raise OSError("ssh connect timeout")


class RuntimeProviderManagerTests(unittest.IsolatedAsyncioTestCase):
    async def test_switch_closes_previous_provider(self):
        async def factory(target, _secret):
            return FakeProvider(target.label)

        manager = RuntimeProviderManager(factory)
        first = await manager.switch(
            RuntimeTarget(provider_type="http_remote", label="A", agent_url="http://10.0.0.8:8001"),
            None,
        )
        second = await manager.switch(
            RuntimeTarget(provider_type="http_remote", label="B", agent_url="http://10.0.0.9:8001"),
            None,
        )

        self.assertTrue(first.closed)
        self.assertEqual(second.label, "B")

    async def test_mark_failure_transitions_to_invalid_after_limit(self):
        async def factory(target, _secret):
            return FakeProvider(target.label)

        manager = RuntimeProviderManager(factory, reconnect_limit=2)
        await manager.switch(
            RuntimeTarget(provider_type="http_remote", label="A", agent_url="http://10.0.0.8:8001"),
            None,
        )

        first = await manager.mark_failure("dial tcp timeout")
        second = await manager.mark_failure("dial tcp timeout")

        self.assertEqual(first["status"], "reconnecting")
        self.assertEqual(second["status"], "invalid")

    async def test_reconnect_rebuilds_provider_from_saved_target(self):
        created = []

        async def factory(target, _secret):
            provider = FakeProvider(target.label)
            created.append(provider)
            return provider

        manager = RuntimeProviderManager(factory, reconnect_limit=3)
        target = RuntimeTarget(
            provider_type="ssh_linux",
            label="训练机 A",
            host="10.0.0.8",
            port=22,
            username="gpuops",
            auth_type="password",
        )
        first = await manager.switch(target, {"password": "secret"})

        await manager.mark_failure("connection reset")
        status = await manager.reconnect()
        current = await manager.current_provider()

        self.assertEqual(status["status"], "connected")
        self.assertIs(current, created[-1])
        self.assertIsNot(current, first)
        self.assertTrue(first.closed)
        self.assertEqual(status["provider_type"], "ssh_linux")
        self.assertEqual(status["reconnect_failures"], 0)

    async def test_status_exposes_public_target_metadata(self):
        async def factory(target, _secret):
            return FakeProvider(target.label)

        manager = RuntimeProviderManager(factory)
        await manager.switch(
            RuntimeTarget(
                provider_type="ssh_linux",
                label="训练机 A",
                host="10.0.0.8",
                port=22,
                username="gpuops",
                auth_type="password",
            ),
            {"password": "secret"},
        )

        status = await manager.status()

        self.assertTrue(status["connected"])
        self.assertEqual(status["provider_type"], "ssh_linux")
        self.assertEqual(status["target"]["host"], "10.0.0.8")
        self.assertEqual(status["target"]["username"], "gpuops")

    async def test_probe_target_wraps_provider_exception_as_offline_error(self):
        async def factory(target, _secret):
            return ExplodingProvider(target.label)

        manager = RuntimeProviderManager(factory)
        probe = await manager.probe_target(
            RuntimeTarget(
                provider_type="ssh_linux",
                label="训练机 A",
                host="10.0.0.8",
                port=22,
                username="gpuops",
                auth_type="password",
            ),
            {"password": "bad"},
        )

        self.assertEqual(probe["status"], "offline")
        self.assertIsNone(probe["health"])
        self.assertIn("ssh connect timeout", probe["error"])


if __name__ == "__main__":
    unittest.main()
