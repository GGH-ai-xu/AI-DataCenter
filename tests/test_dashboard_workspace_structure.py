import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DashboardWorkspaceStructureTests(unittest.TestCase):
    def test_dashboard_uses_new_tab_components_and_labels(self):
        dashboard = (ROOT / 'frontend/src/views/Dashboard.vue').read_text(encoding='utf-8')
        self.assertIn('DashboardOverviewTab', dashboard)
        self.assertIn('DashboardHealthTab', dashboard)
        self.assertIn("label: '首页'", dashboard)
        self.assertIn("label: '实时'", dashboard)
        self.assertIn("label: '巡检'", dashboard)
        self.assertNotIn('DataStatisticsCard', dashboard)

    def test_dashboard_view_uses_split_refresh_keys(self):
        composable = (ROOT / 'frontend/src/composables/useDashboardData.js').read_text(encoding='utf-8')
        self.assertIn("key: 'overview'", composable)
        self.assertIn("key: 'health'", composable)
        self.assertNotIn("key: 'governance'", composable)


if __name__ == '__main__':
    unittest.main()
