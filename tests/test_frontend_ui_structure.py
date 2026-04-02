import unittest
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FrontendUIStructureTests(unittest.TestCase):
    def test_frontend_contains_structural_ui_workspace_components(self):
        for rel in [
            "frontend/src/components/app/AppPrimarySidebar.vue",
            "frontend/src/components/tasks/TaskProcessLedger.vue",
            "frontend/src/components/dashboard/DashboardLiveWorkspace.vue",
            "frontend/src/components/alerts/AlertHistoryTable.vue",
        ]:
            self.assertTrue((ROOT / rel).exists(), rel)

    def test_workspace_shell_components_exist(self):
        for rel in [
            "frontend/src/components/workspace/WorkspaceTabs.vue",
            "frontend/src/components/workspace/WorkspaceSummary.vue",
            "frontend/src/components/workspace/WorkspacePaneLayout.vue",
        ]:
            self.assertTrue((ROOT / rel).exists(), rel)

    def test_major_views_use_tab_state(self):
        for rel in [
            "frontend/src/views/Dashboard.vue",
            "frontend/src/views/TaskManager.vue",
            "frontend/src/views/Scheduler.vue",
            "frontend/src/views/EnergyOptimization.vue",
            "frontend/src/views/AIAssistant.vue",
        ]:
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertIn("activeTab", text, rel)
            self.assertIn("WorkspaceTabs", text, rel)

    def test_workspace_tabs_support_vertical_orientation(self):
        text = (ROOT / "frontend/src/components/workspace/WorkspaceTabs.vue").read_text(encoding="utf-8")

        self.assertIn("orientation", text)
        self.assertIn("workspace-tabs--vertical", text)

    def test_workbench_pages_use_top_tab_layout(self):
        for rel in [
            "frontend/src/views/Dashboard.vue",
            "frontend/src/views/Scheduler.vue",
            "frontend/src/views/MonitorCenter.vue",
            "frontend/src/views/TaskManager.vue",
            "frontend/src/views/EnergyOptimization.vue",
            "frontend/src/views/AIAssistant.vue",
        ]:
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertIn("workspace-nav-layout", text, rel)
            self.assertIn("workspace-nav-layout__nav", text, rel)
            self.assertIn("workspace-nav-layout__content", text, rel)
            self.assertNotIn('orientation="vertical"', text, rel)

    def test_shared_style_defines_top_workbench_tab_rail(self):
        text = (ROOT / "frontend/src/style.css").read_text(encoding="utf-8")

        self.assertIn(".workspace-nav-layout", text)
        self.assertIn(".workspace-nav-layout__nav", text)
        self.assertIn("overflow-x: auto", text)
        self.assertIn("position: sticky", text)
        self.assertIn("top: 0", text)

    def test_monitor_and_alert_views_use_shared_shell(self):
        for rel in [
            "frontend/src/views/MonitorCenter.vue",
            "frontend/src/views/AlertCenter.vue",
        ]:
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertIn("WorkspaceSummary", text, rel)

    def test_primary_workspace_headers_use_compact_copy(self):
        for rel in [
            "frontend/src/views/Dashboard.vue",
            "frontend/src/views/TaskManager.vue",
            "frontend/src/views/Scheduler.vue",
            "frontend/src/views/MonitorCenter.vue",
            "frontend/src/views/AIAssistant.vue",
            "frontend/src/views/AlertCenter.vue",
        ]:
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertNotIn("eyebrow=", text, rel)
            self.assertNotIn("description=", text, rel)
            self.assertNotIn(":description=", text, rel)

    def test_vite_build_still_available(self):
        package_json = (ROOT / "frontend/package.json").read_text(encoding="utf-8")
        self.assertIn('"build": "vite build"', package_json)

    def test_frontend_brand_uses_repo_logo_asset(self):
        app_text = (ROOT / "frontend/src/App.vue").read_text(encoding="utf-8")
        favicon_text = (ROOT / "frontend/public/favicon.svg").read_text(encoding="utf-8")
        source_logo = (ROOT / "docs/logo/logo.svg").read_text(encoding="utf-8")

        self.assertIn('src="/logo.svg"', app_text)
        self.assertEqual(favicon_text.strip(), source_logo.strip())

    def test_app_shell_uses_sidebar_primary_navigation(self):
        text = (ROOT / "frontend/src/App.vue").read_text(encoding="utf-8")

        self.assertIn("AppPrimarySidebar", text)
        self.assertIn("app-shell", text)
        self.assertIn("app-sidebar", text)
        self.assertIn("app-mobile-nav", text)

    def test_primary_sidebar_separates_scrollable_nav_and_footer(self):
        text = (ROOT / "frontend/src/components/app/AppPrimarySidebar.vue").read_text(encoding="utf-8")

        self.assertIn("grid-template-rows: auto minmax(0, 1fr) auto;", text)
        self.assertIn("overflow-y: auto", text)
        self.assertIn(".app-primary-sidebar__footer", text)

    def test_desktop_shell_uses_updated_logo_assets(self):
        splash_text = (ROOT / "desktop-shell/splash.html").read_text(encoding="utf-8")
        package_text = (ROOT / "desktop-shell/package.json").read_text(encoding="utf-8")
        main_text = (ROOT / "desktop-shell/main.js").read_text(encoding="utf-8")
        icon_bytes = (ROOT / "desktop-shell/build/icon.ico").read_bytes()

        self.assertIn("brand-logo", splash_text)
        self.assertIn('"build/icon.png"', package_text)
        self.assertIn('"build/icon.ico"', package_text)
        self.assertIn("process.platform === 'win32'", main_text)
        self.assertIn("icon.ico", main_text)
        self.assertIn("icon.png", main_text)
        self.assertGreater(int.from_bytes(icon_bytes[4:6], "little"), 1)

    def test_dashboard_is_summary_only(self):
        text = (ROOT / "frontend/src/views/Dashboard.vue").read_text(encoding="utf-8")

        self.assertNotIn("执行一次真实治理", text)
        self.assertNotIn("先做节能测算", text)
        self.assertNotIn("一键导出综合报告", text)
        self.assertNotIn("executeDispatch", text)
        self.assertNotIn("measureOptimization", text)

    def test_dashboard_live_uses_grouped_live_workspace_component(self):
        text = (ROOT / "frontend/src/views/Dashboard.vue").read_text(encoding="utf-8")

        self.assertIn("DashboardLiveWorkspace", text)
        self.assertIn("workspaceReady && activeTab === 'live'", text)

    def test_dashboard_overview_collapses_actions_into_single_main_card(self):
        text = (ROOT / "frontend/src/views/Dashboard.vue").read_text(encoding="utf-8")

        self.assertIn("overview-layout", text)
        self.assertIn("overviewRoutes", text)
        self.assertNotIn("工作入口", text)
        self.assertNotIn("signal-grid", text)

    def test_dashboard_summary_meta_uses_horizontal_badge_group(self):
        text = (ROOT / "frontend/src/views/Dashboard.vue").read_text(encoding="utf-8")

        self.assertIn("dashboard-summary__meta", text)
        self.assertNotIn("governance-hero__side", text)

    def test_scheduler_no_longer_hosts_energy_report(self):
        text = (ROOT / "frontend/src/views/Scheduler.vue").read_text(encoding="utf-8")

        self.assertNotIn("AI 能耗分析报告", text)
        self.assertNotIn("getScheduleReport", text)

    def test_monitor_center_no_longer_hosts_replay_tab(self):
        text = (ROOT / "frontend/src/views/MonitorCenter.vue").read_text(encoding="utf-8")

        self.assertNotIn("{ key: 'replay'", text)
        self.assertNotIn("activeTab === 'replay'", text)

    def test_ai_assistant_no_longer_allows_real_execution(self):
        text = (ROOT / "frontend/src/views/AIAssistant.vue").read_text(encoding="utf-8")

        self.assertNotIn("执行真实动作", text)
        self.assertNotIn("controlMode === 'real'", text)
        self.assertNotIn("将执行真实治理动作", text)

    def test_monitor_center_cards_define_own_padding(self):
        text = (ROOT / "frontend/src/views/MonitorCenter.vue").read_text(encoding="utf-8")

        for cls in [
            "sys-info-card",
            "disk-card",
            "resource-card",
            "training-card",
            "user-card",
            "timeline-chart-card",
            "timeline-ledger-card",
        ]:
            self.assertRegex(text, rf"\.{cls}\s*\{{[^}}]*padding:", cls)

    def test_views_do_not_use_ellipsis_to_hide_text(self):
        for rel in [
            "frontend/src/views/MonitorCenter.vue",
            "frontend/src/views/TaskManager.vue",
            "frontend/src/views/Dashboard.vue",
        ]:
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertNotIn("text-overflow: ellipsis", text, rel)

    def test_task_manager_uses_responsive_process_ledger_component(self):
        text = (ROOT / "frontend/src/views/TaskManager.vue").read_text(encoding="utf-8")

        self.assertIn("TaskProcessLedger", text)
        self.assertNotIn("<table class=\"task-table\">", text)
        self.assertNotIn("min-width: 1480px", text)
        self.assertNotIn("table-layout: fixed", text)

    def test_energy_page_splits_overview_into_additional_tabs(self):
        text = (ROOT / "frontend/src/views/EnergyOptimization.vue").read_text(encoding="utf-8")

        self.assertIn("{ key: 'analysis'", text)
        self.assertIn("{ key: 'optimize'", text)
        self.assertIn("activeTab === 'analysis'", text)
        self.assertIn("activeTab === 'optimize'", text)

    def test_alert_center_uses_time_workbench_tabs(self):
        text = (ROOT / "frontend/src/views/AlertCenter.vue").read_text(encoding="utf-8")

        self.assertIn("const activeTab = ref('realtime')", text)
        self.assertIn("WorkspaceTabs", text)
        self.assertIn("ALERT_CENTER_TABS", text)
        self.assertIn("activeTab === 'realtime'", text)
        self.assertIn("activeTab === 'today'", text)
        self.assertIn("archiveType", text)
        self.assertIn("AlertRealtimeStream", text)
        self.assertIn("AlertDaybookTimeline", text)
        self.assertIn("AlertArchiveBoard", text)
        self.assertNotIn("AlertHistoryTable", text)

    def test_alert_center_time_workbench_components_exist(self):
        for rel in [
            "frontend/src/components/alerts/AlertRealtimeStream.vue",
            "frontend/src/components/alerts/AlertRealtimeSidebar.vue",
            "frontend/src/components/alerts/AlertDaybookTimeline.vue",
            "frontend/src/components/alerts/AlertArchiveTypeTabs.vue",
            "frontend/src/components/alerts/AlertArchiveBoard.vue",
        ]:
            self.assertTrue((ROOT / rel).exists(), rel)

    def test_alert_realtime_components_use_bucketed_layout(self):
        stream_text = (ROOT / "frontend/src/components/alerts/AlertRealtimeStream.vue").read_text(encoding="utf-8")
        sidebar_text = (ROOT / "frontend/src/components/alerts/AlertRealtimeSidebar.vue").read_text(encoding="utf-8")

        self.assertIn("realtime-bucket", stream_text)
        self.assertIn("realtime-alert-card", stream_text)
        self.assertIn("bucket.items", stream_text)
        self.assertIn("alert-realtime-sidebar", sidebar_text)
        self.assertIn("update:modelValue", sidebar_text)
        self.assertNotIn("text-overflow: ellipsis", stream_text)

    def test_alert_daybook_uses_timeline_sections(self):
        text = (ROOT / "frontend/src/components/alerts/AlertDaybookTimeline.vue").read_text(encoding="utf-8")

        self.assertIn("daybook-section", text)
        self.assertIn("daybook-entry", text)
        self.assertIn("section.items", text)
        self.assertNotIn("grid-template-columns: minmax(88px", text)

    def test_alert_archive_board_groups_history_by_type(self):
        board_text = (ROOT / "frontend/src/components/alerts/AlertArchiveBoard.vue").read_text(encoding="utf-8")
        tabs_text = (ROOT / "frontend/src/components/alerts/AlertArchiveTypeTabs.vue").read_text(encoding="utf-8")
        helper_text = (ROOT / "frontend/src/lib/alertCenterTransforms.js").read_text(encoding="utf-8")

        self.assertIn("AlertArchiveTypeTabs", board_text)
        self.assertIn("AlertHistoryTable", board_text)
        self.assertIn("archive-summary", board_text)
        self.assertIn("update:modelValue", tabs_text)
        self.assertIn("temperature", helper_text)
        self.assertIn("self_check", helper_text)


if __name__ == "__main__":
    unittest.main()
