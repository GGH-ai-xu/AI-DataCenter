import os
import sys
import tempfile
import unittest


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.services.password_hasher import hash_password  # noqa: E402
from app.services.platform_auth_service import DEFAULT_ADMIN_PASSWORD  # noqa: E402
from app.services.platform_auth_service import PlatformAuthService  # noqa: E402
from app.services.platform_identity_store import PlatformIdentityStore  # noqa: E402


class PlatformIdentityFlowTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tempdir.name, "platform.db")
        self.store = PlatformIdentityStore(self.db_path)
        await self.store.init()
        self.auth = PlatformAuthService(self.store)

    async def asyncTearDown(self):
        await self.store.close()
        self.tempdir.cleanup()

    async def test_bootstrap_default_admin_creates_direct_login_user(self):
        notice = await self.auth.ensure_default_admin()
        admin = await self.store.get_user_by_username("admin")

        self.assertEqual(admin["username"], "admin")
        self.assertEqual(admin["role"], "admin")
        self.assertFalse(admin["must_change_password"])
        self.assertEqual(notice["default_password"], DEFAULT_ADMIN_PASSWORD)
        self.assertEqual(notice["status"], "created")

    async def test_login_returns_session_token_and_persists_session_hash(self):
        notice = await self.auth.ensure_default_admin()

        result = await self.auth.login("admin", notice["default_password"])
        session = await self.store.get_session_by_token(result["token"])

        self.assertEqual(result["user"]["username"], "admin")
        self.assertFalse(result["user"]["must_change_password"])
        self.assertIsNotNone(session)
        self.assertEqual(session["user_id"], result["user"]["id"])

    async def test_change_password_allows_subsequent_login_with_new_password(self):
        notice = await self.auth.ensure_default_admin()
        login = await self.auth.login("admin", notice["default_password"])

        await self.auth.change_password(
            user_id=login["user"]["id"],
            current_password=notice["default_password"],
            new_password="NewPassw0rd!",
        )

        relogin = await self.auth.login("admin", "NewPassw0rd!")
        self.assertFalse(relogin["user"]["must_change_password"])

    async def test_logout_revokes_session(self):
        notice = await self.auth.ensure_default_admin()
        login = await self.auth.login("admin", notice["default_password"])

        await self.auth.logout(login["token"])
        current = await self.auth.resolve_session(login["token"])

        self.assertIsNone(current)

    async def test_admin_can_create_user_and_reset_password(self):
        notice = await self.auth.ensure_default_admin()
        await self.auth.login("admin", notice["default_password"])

        created = await self.auth.create_user(
            username="alice",
            password="TempPassw0rd!",
            role="member",
            must_change_password=True,
        )
        await self.auth.reset_password(
            user_id=created["id"],
            password="ResetPassw0rd!",
            must_change_password=True,
        )

        relogin = await self.auth.login("alice", "ResetPassw0rd!")
        self.assertEqual(relogin["user"]["username"], "alice")
        self.assertTrue(relogin["user"]["must_change_password"])

    async def test_bootstrap_resets_untouched_admin_to_default_password(self):
        notice = await self.auth.ensure_default_admin()
        admin = await self.store.get_user_by_username("admin")

        await self.store.update_password(
            admin["id"],
            hash_password("ChangedBeforeFirstLogin!"),
            True,
        )

        reset_notice = await self.auth.ensure_default_admin()
        relogin = await self.auth.login("admin", DEFAULT_ADMIN_PASSWORD)

        self.assertEqual(notice["default_password"], DEFAULT_ADMIN_PASSWORD)
        self.assertEqual(reset_notice["default_password"], DEFAULT_ADMIN_PASSWORD)
        self.assertEqual(reset_notice["status"], "reset_existing")
        self.assertFalse((await self.store.get_user_by_username("admin"))["must_change_password"])
        self.assertEqual(relogin["user"]["username"], "admin")


if __name__ == "__main__":
    unittest.main()
