import os
import sys
import unittest


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.services.runtime_scope import build_realtime_scope  # noqa: E402


class FakeImportContext:
    def filter_gpus(self, gpus):
        return [gpu for gpu in gpus if gpu["index"] == 1]

    def filter_processes(self, processes):
        return [proc for proc in processes if proc["gpu_index"] == 1]


class FakePrivacy:
    def __init__(self):
        self.received = None

    def sanitize_processes(self, processes):
        self.received = list(processes)
        return [{"pid": item["pid"], "command": "masked"} for item in processes]


class RuntimeScopeTests(unittest.TestCase):
    def test_build_realtime_scope_filters_before_sanitizing(self):
        privacy = FakePrivacy()

        payload = build_realtime_scope(
            import_context=FakeImportContext(),
            privacy=privacy,
            system={"cpu_percent": 12},
            gpus=[
                {"index": 0, "name": "GPU0"},
                {"index": 1, "name": "GPU1"},
            ],
            processes=[
                {"pid": 10, "gpu_index": 0, "command": "python a.py"},
                {"pid": 11, "gpu_index": 1, "command": "python b.py"},
            ],
        )

        self.assertEqual([item["index"] for item in payload["gpus"]], [1])
        self.assertEqual([item["pid"] for item in payload["processes"]], [11])
        self.assertEqual(privacy.received, payload["processes"])
        self.assertEqual(payload["public_processes"], [{"pid": 11, "command": "masked"}])


if __name__ == "__main__":
    unittest.main()
