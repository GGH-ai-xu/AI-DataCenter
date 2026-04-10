import os
import sys
import tempfile
import unittest

from repo_test_bootstrap import prepare_backend_test_env


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
missing_deps = prepare_backend_test_env("cryptography")
if missing_deps:
    raise unittest.SkipTest(f"missing backend test dependencies: {', '.join(missing_deps)}; run install-deps.bat")

from app.services.credential_cipher import CredentialCipher  # noqa: E402
from app.services.credential_store import CredentialStore  # noqa: E402


class EncryptedCredentialStoreTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.secret_path = os.path.join(self.tempdir.name, "credentials.json")
        self.cipher = CredentialCipher("unit-test-master-key")
        self.store = CredentialStore(self.secret_path, self.cipher)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_persisted_json_does_not_store_plaintext_passwords(self):
        credential_id = self.store.save({
            "password": "secret",
            "sudo_password": "rootpw",
        })

        with open(self.secret_path, "r", encoding="utf-8") as handle:
            raw_text = handle.read()
        restored = self.store.read(credential_id)

        self.assertNotIn("secret", raw_text)
        self.assertNotIn("rootpw", raw_text)
        self.assertEqual(restored["password"], "secret")
        self.assertEqual(restored["sudo_password"], "rootpw")

    def test_missing_cipher_raises_explicit_error(self):
        store = CredentialStore(self.secret_path, None)

        with self.assertRaisesRegex(ValueError, "GPU_GOV_MASTER_KEY"):
            store.save({"password": "secret"})


if __name__ == "__main__":
    unittest.main()
