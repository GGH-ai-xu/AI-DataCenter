import asyncio
import json
import os
import sys
import tempfile
import unittest


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.services.llm_settings import LLMSettingsService  # noqa: E402


class LLMSettingsServiceTests(unittest.TestCase):
    def test_snapshot_masks_api_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = LLMSettingsService(os.path.join(tmp, "llm.json"))
            service._state = {
                "enabled": True,
                "base_url": "https://api.example.com/v1",
                "model": "demo-model",
                "api_key": "sk-1234567890",
                "updated_at": 1.0,
                "source": "runtime",
            }

            snapshot = service.snapshot(True)

            self.assertTrue(snapshot["has_api_key"])
            self.assertEqual(snapshot["api_key_masked"], "sk-123***7890")
            self.assertNotIn("api_key", snapshot)

    def test_resolve_candidate_leaves_model_blank_for_first_time_auto_detect(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = LLMSettingsService(os.path.join(tmp, "llm.json"))
            service._state = {
                "enabled": False,
                "base_url": "https://api.example.com/v1",
                "model": "deepseek-chat",
                "api_key": "",
                "updated_at": None,
                "source": "default",
            }

            candidate = service.resolve_candidate(
                "https://api.openai-compatible.com/v1",
                "",
                "sk-new-key",
                keep_existing_key=False,
            )

            self.assertEqual(candidate["base_url"], "https://api.openai-compatible.com/v1")
            self.assertEqual(candidate["model"], "")
            self.assertEqual(candidate["api_key"], "sk-new-key")

    def test_update_disabled_persists_runtime_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = os.path.join(tmp, "llm.json")
            service = LLMSettingsService(config_path)

            snapshot, llm_service = asyncio.run(
                service.update(
                    enabled=False,
                    base_url="https://api.deepseek.com/v1",
                    model="",
                    api_key="",
                    keep_existing_key=False,
                )
            )

            self.assertIsNone(llm_service)
            self.assertFalse(snapshot["enabled"])
            self.assertFalse(snapshot["has_api_key"])
            self.assertTrue(os.path.exists(config_path))

            with open(config_path, "r", encoding="utf-8") as f:
                payload = json.load(f)

            self.assertFalse(payload["enabled"])
            self.assertEqual(payload["base_url"], "https://api.deepseek.com/v1")


if __name__ == "__main__":
    unittest.main()
