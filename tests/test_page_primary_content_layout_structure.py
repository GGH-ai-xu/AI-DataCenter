import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PagePrimaryContentLayoutStructureTests(unittest.TestCase):
    def test_dashboard_keeps_single_summary_layer(self):
        dashboard_text = (ROOT / 'frontend/src/views/Dashboard.vue').read_text(encoding='utf-8')
        overview_text = (ROOT / 'frontend/src/components/dashboard/DashboardOverviewTab.vue').read_text(encoding='utf-8')

        self.assertIn('WorkspaceSummary', dashboard_text)
        self.assertNotIn('dashboard-summary__quick-grid', dashboard_text)
        self.assertIn('props.model.quickStats', overview_text)
        self.assertIn('overview-quick-strip', overview_text)

    def test_governance_tabs_follow_summary_without_stats_strip(self):
        text = (ROOT / 'frontend/src/views/GovernanceLayout.vue').read_text(encoding='utf-8')

        self.assertIn('WorkspaceSummary', text)
        self.assertNotIn('stats-grid workspace-summary-strip', text)
        self.assertIn('activeSummaryBadge', text)

    def test_monitor_center_uses_single_summary_component(self):
        component_path = ROOT / 'frontend/src/components/monitor/MonitorWorkspaceSummary.vue'
        component_text = component_path.read_text(encoding='utf-8')
        page_text = (ROOT / 'frontend/src/views/MonitorCenter.vue').read_text(encoding='utf-8')

        self.assertIn('WorkspaceSummary', component_text)
        self.assertIn('MonitorWorkspaceSummary', page_text)
        self.assertNotIn('monitor-summary-grid', page_text)

    def test_alert_center_moves_summary_into_content_zone(self):
        text = (ROOT / 'frontend/src/views/AlertCenter.vue').read_text(encoding='utf-8')

        self.assertIn('WorkspaceSummary', text)
        self.assertNotIn('<div class="workspace-summary-strip">', text)
        self.assertIn("activeTab !== 'realtime'", text)

    def test_energy_page_uses_shared_workspace_summary(self):
        page_text = (ROOT / 'frontend/src/views/EnergyOptimization.vue').read_text(encoding='utf-8')

        self.assertIn('WorkspaceSummary', page_text)
        self.assertNotIn('source-strip', page_text)
        self.assertNotIn('绿色计算 · 智慧能源', page_text)

    def test_ai_page_uses_shared_workspace_summary(self):
        page_text = (ROOT / 'frontend/src/views/AIAssistant.vue').read_text(encoding='utf-8')

        self.assertIn('WorkspaceSummary', page_text)
        self.assertIn('WorkspaceTabs', page_text)


if __name__ == '__main__':
    unittest.main()
