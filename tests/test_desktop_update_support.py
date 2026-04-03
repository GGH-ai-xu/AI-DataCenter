import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DesktopUpdateSupportTests(unittest.TestCase):
    def test_desktop_shell_disables_update_check_in_dev_mode(self):
        text = (ROOT / "desktop-shell" / "main.js").read_text(encoding="utf-8")

        self.assertIn("function updateCheckSupported()", text)
        self.assertIn("return !desktopDevModeEnabled() && Boolean(releaseRepository)", text)
        self.assertIn("updateSupported: updateCheckSupported()", text)
        self.assertIn("if (!updateCheckSupported()) {", text)
        self.assertIn("当前运行模式不提供更新检查", text)

    def test_console_shell_hides_update_entry_when_update_not_supported(self):
        view_text = (ROOT / "frontend/src/views/ConsoleShell.vue").read_text(encoding="utf-8")
        shell_text = (ROOT / "frontend/src/composables/useConsoleShell.js").read_text(encoding="utf-8")

        self.assertIn("updateSupported: false", shell_text)
        self.assertIn("proxyRefs(useConsoleShell())", view_text)
        self.assertIn("if (!appInfo.value.updateSupported || !shellBridge?.checkForUpdates) return", shell_text)
        self.assertIn("if (!appInfo.value.updateSupported) {", shell_text)
        self.assertIn("v-if=\"shell.isDesktop && shell.appInfo.updateSupported\"", view_text)
        self.assertIn("shell.runtimeBanner || (shell.appInfo.updateSupported && shell.updateState)", view_text)
        self.assertIn("v-if=\"shell.appInfo.updateSupported && shell.updateState\"", view_text)


if __name__ == "__main__":
    unittest.main()
