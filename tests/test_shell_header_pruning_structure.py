import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ShellHeaderPruningStructureTests(unittest.TestCase):
    def test_routes_mark_primary_pages_to_hide_shell_header(self):
        text = (ROOT / "frontend/src/main.js").read_text(encoding="utf-8")

        self.assertRegex(
            text,
            r"(?s)path:\s*'',\s*name:\s*'Dashboard',\s*component:\s*loadDashboardView,\s*meta:\s*\{\s*hideShellHeader:\s*true\s*\}",
        )
        self.assertRegex(
            text,
            r"(?s)path:\s*'governance',\s*component:\s*loadGovernanceLayoutView,\s*meta:\s*\{\s*hideShellHeader:\s*true\s*\}",
        )
        self.assertRegex(
            text,
            r"(?s)path:\s*'monitor',\s*name:\s*'MonitorCenter',\s*component:\s*loadMonitorCenterView,\s*meta:\s*\{\s*hideShellHeader:\s*true\s*\}",
        )
        self.assertRegex(
            text,
            r"(?s)path:\s*'energy',\s*name:\s*'EnergyOptimization',\s*component:\s*loadEnergyOptimizationView,\s*meta:\s*\{\s*hideShellHeader:\s*true\s*\}",
        )
        self.assertRegex(
            text,
            r"(?s)path:\s*'alerts',\s*name:\s*'AlertCenter',\s*component:\s*loadAlertCenterView,\s*meta:\s*\{\s*hideShellHeader:\s*true\s*\}",
        )
        self.assertRegex(
            text,
            r"(?s)path:\s*'ai',\s*component:\s*loadAIWorkspaceLayoutView,\s*meta:\s*\{\s*hideShellHeader:\s*true\s*\}",
        )

    def test_console_shell_hides_shell_header_on_meta_flag(self):
        text = (ROOT / "frontend/src/views/ConsoleShell.vue").read_text(encoding="utf-8")

        self.assertIn('v-if="!shell.route.meta?.hideShellHeader"', text)
        self.assertIn('class="app-chrome tech-card"', text)

    def test_primary_pages_keep_page_local_summary_blocks(self):
        dashboard_text = (ROOT / "frontend/src/views/Dashboard.vue").read_text(encoding="utf-8")
        monitor_text = (ROOT / "frontend/src/views/MonitorCenter.vue").read_text(encoding="utf-8")
        governance_text = (ROOT / "frontend/src/views/GovernanceLayout.vue").read_text(encoding="utf-8")
        energy_text = (ROOT / "frontend/src/views/EnergyOptimization.vue").read_text(encoding="utf-8")
        alert_text = (ROOT / "frontend/src/views/AlertCenter.vue").read_text(encoding="utf-8")
        ai_text = (ROOT / "frontend/src/views/AIAssistant.vue").read_text(encoding="utf-8")

        self.assertIn("WorkspaceSummary", dashboard_text)
        self.assertIn("WorkspaceSummary", monitor_text)
        self.assertIn("WorkspaceSummary", governance_text)
        self.assertIn("WorkspaceSummary", energy_text)
        self.assertIn("WorkspaceSummary", alert_text)
        self.assertIn("WorkspaceSummary", ai_text)


if __name__ == "__main__":
    unittest.main()
