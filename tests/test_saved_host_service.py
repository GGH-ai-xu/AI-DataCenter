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
from app.services.platform_auth_service import DEFAULT_ADMIN_PASSWORD  # noqa: E402
from app.services.platform_auth_service import PlatformAuthService  # noqa: E402
from app.services.platform_identity_store import PlatformIdentityStore  # noqa: E402
from app.services.runtime_provider import RuntimeTarget  # noqa: E402
from app.services.saved_host_service import SavedHostService  # noqa: E402


class SavedHostServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tempdir.name, "platform.db")
        self.secret_path = os.path.join(self.tempdir.name, "credentials.json")
        self.identity = PlatformIdentityStore(self.db_path)
        await self.identity.init()
        self.auth = PlatformAuthService(self.identity)
        notice = await self.auth.ensure_default_admin()
        self.assertEqual(notice["default_password"], DEFAULT_ADMIN_PASSWORD)
        self.admin_login = await self.auth.login("admin", notice["default_password"])
        self.cipher = CredentialCipher("unit-test-master-key")
        self.credentials = CredentialStore(self.secret_path, self.cipher)
        self.service = SavedHostService(self.identity, self.credentials)
        self.member = await self.identity.create_user(
            username="alice",
            password_hash="unused-for-this-test",
            role="member",
            must_change_password=False,
        )

    async def asyncTearDown(self):
        await self.identity.close()
        self.tempdir.cleanup()

    async def test_member_only_lists_owned_hosts(self):
        target = RuntimeTarget(
            provider_type="ssh_linux",
            label="训练机 A",
            host="10.0.0.8",
            port=22,
            username="alice",
            auth_type="password",
        )
        credential_id = self.credentials.save({"password": "secret"})

        await self.service.upsert_host(self.member, target, credential_id)
        hosts = await self.service.list_hosts(self.member)

        self.assertEqual(len(hosts), 1)
        self.assertEqual(hosts[0]["owner_user_id"], self.member["id"])

    async def test_admin_can_list_all_hosts(self):
        target = RuntimeTarget(
            provider_type="ssh_linux",
            label="训练机 A",
            host="10.0.0.8",
            port=22,
            username="alice",
            auth_type="password",
        )
        credential_id = self.credentials.save({"password": "secret"})
        await self.service.upsert_host(self.member, target, credential_id)

        hosts = await self.service.list_hosts(
            {
                "id": self.admin_login["user"]["id"],
                "username": "admin",
                "role": "admin",
                "must_change_password": False,
            },
            scope="all",
        )

        self.assertEqual(len(hosts), 1)
        self.assertEqual(hosts[0]["owner_username"], "alice")

    async def test_resolve_host_returns_target_and_credentials(self):
        target = RuntimeTarget(
            provider_type="ssh_linux",
            label="训练机 A",
            host="10.0.0.8",
            port=22,
            username="alice",
            auth_type="password",
        )
        credential_id = self.credentials.save({"password": "secret"})
        record = await self.service.upsert_host(self.member, target, credential_id)

        resolved_target, credentials, owner = await self.service.resolve_for_import(
            self.member,
            record["id"],
        )

        self.assertEqual(resolved_target.host, "10.0.0.8")
        self.assertEqual(credentials["password"], "secret")
        self.assertEqual(owner["username"], "alice")

    async def test_list_hosts_marks_unreadable_credentials(self):
        target = RuntimeTarget(
            provider_type="ssh_linux",
            label="training-a",
            host="10.0.0.8",
            port=22,
            username="alice",
            auth_type="password",
        )
        credential_id = self.credentials.save({"password": "secret"})
        await self.service.upsert_host(self.member, target, credential_id)

        broken_credentials = CredentialStore(
            self.secret_path,
            CredentialCipher("different-master-key"),
        )
        broken_service = SavedHostService(self.identity, broken_credentials)

        hosts = await broken_service.list_hosts(self.member)

        self.assertEqual(len(hosts), 1)
        self.assertEqual(hosts[0]["credential_status"], "unreadable")
        self.assertTrue(hosts[0]["has_credentials"])
        self.assertIn("当前主密钥", hosts[0]["credential_error"])

    async def test_member_cannot_access_other_users_host_record(self):
        other = await self.identity.create_user(
            username="bob",
            password_hash="unused-for-this-test",
            role="member",
            must_change_password=False,
        )
        target = RuntimeTarget(
            provider_type="ssh_linux",
            label="训练机 B",
            host="10.0.0.9",
            port=22,
            username="bob",
            auth_type="password",
        )
        credential_id = self.credentials.save({"password": "secret"})
        record = await self.service.upsert_host(other, target, credential_id)

        with self.assertRaises(PermissionError):
            await self.service.resolve_for_import(self.member, record["id"])


if __name__ == "__main__":
    unittest.main()
