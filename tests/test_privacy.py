import os
import sys
import unittest


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.services.privacy import PrivacyService  # noqa: E402


class PrivacyServiceTests(unittest.TestCase):
    def setUp(self):
        self.privacy = PrivacyService()

    def test_mask_username_is_stable(self):
        alias = self.privacy.mask_username("alice")
        self.assertEqual(alias, self.privacy.mask_username("alice"))
        self.assertNotEqual(alias, "alice")
        self.assertTrue(alias.startswith("user-"))

    def test_sanitize_process_masks_username_and_path(self):
        process = {
            "pid": 1234,
            "username": "alice",
            "command": r"C:\Users\alice\miniconda3\python.exe train.py --data C:\Users\alice\data",
        }

        sanitized = self.privacy.sanitize_process(process)

        self.assertNotEqual(sanitized["username"], "alice")
        self.assertNotIn(r"C:\Users\alice", sanitized["command"])
        self.assertIn("[path]", sanitized["command"])

    def test_resolve_username_from_alias(self):
        alias = self.privacy.mask_username("alice")
        resolved = self.privacy.resolve_username(alias, ["alice", "bob"])
        self.assertEqual(resolved, "alice")


if __name__ == "__main__":
    unittest.main()
