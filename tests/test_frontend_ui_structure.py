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
            "frontend/src/views/EnergyOptimization.vue",
            "frontend/src/views/AIAssistant.vue",
        ]:
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertIn("activeTab", text, rel)
            self.assertIn("WorkspaceTabs", text, rel)

        governance_text = (ROOT / "frontend/src/views/GovernanceLayout.vue").read_text(encoding="utf-8")
        self.assertIn("activeSection", governance_text)
        self.assertIn("WorkspaceTabs", governance_text)

    def test_workspace_tabs_support_vertical_orientation(self):
        text = (ROOT / "frontend/src/components/workspace/WorkspaceTabs.vue").read_text(encoding="utf-8")
        self.assertIn("orientation", text)
        self.assertIn("workspace-tabs--vertical", text)

    def test_governance_layout_uses_top_tab_layout(self):
        for rel in [
            "frontend/src/views/Dashboard.vue",
            "frontend/src/views/GovernanceLayout.vue",
            "frontend/src/views/MonitorCenter.vue",
            "frontend/src/views/EnergyOptimization.vue",
            "frontend/src/views/AIAssistant.vue",
        ]:
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertIn("workspace-nav-layout", text, rel)
            self.assertIn("workspace-nav-layout__nav", text, rel)
            self.assertIn("workspace-nav-layout__content", text, rel)
            self.assertNotIn('orientation="vertical"', text, rel)

    def test_legacy_task_and_scheduler_views_are_redirect_shims(self):
        task_text = (ROOT / "frontend/src/views/TaskManager.vue").read_text(encoding="utf-8")
        scheduler_text = (ROOT / "frontend/src/views/Scheduler.vue").read_text(encoding="utf-8")
        self.assertIn("router.replace('/governance/actions')", task_text)
        self.assertIn("router.replace('/governance/policies')", scheduler_text)

    def test_shared_style_defines_top_workbench_tab_rail(self):
        text = (ROOT / "frontend/src/style.css").read_text(encoding="utf-8")
        self.assertIn(".workspace-nav-layout", text)
        self.assertIn(".workspace-nav-layout__nav", text)
        self.assertIn("overflow-x: auto", text)
        self.assertIn("position: sticky", text)
        self.assertIn("top: 0", text)

    def test_monitor_and_alert_views_use_shared_shell(self):
        monitor_text = (ROOT / "frontend/src/views/MonitorCenter.vue").read_text(encoding="utf-8")
        alert_text = (ROOT / "frontend/src/views/AlertCenter.vue").read_text(encoding="utf-8")

        self.assertIn("MonitorWorkspaceSummary", monitor_text)
        self.assertIn("WorkspaceSummary", alert_text)

    def test_primary_workspace_headers_use_compact_copy(self):
        for rel in [
            "frontend/src/views/Dashboard.vue",
            "frontend/src/views/TaskManager.vue",
            "frontend/src/views/Scheduler.vue",
            "frontend/src/views/MonitorCenter.vue",
        ]:
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertNotIn("eyebrow=", text, rel)
            self.assertNotIn("description=", text, rel)
            self.assertNotIn(":description=", text, rel)

    def test_energy_ai_and_alert_pages_use_shared_workspace_summary(self):
        energy_text = (ROOT / "frontend/src/views/EnergyOptimization.vue").read_text(encoding="utf-8")
        ai_text = (ROOT / "frontend/src/views/AIAssistant.vue").read_text(encoding="utf-8")
        alert_text = (ROOT / "frontend/src/views/AlertCenter.vue").read_text(encoding="utf-8")

        self.assertIn("WorkspaceSummary", energy_text)
        self.assertIn("WorkspaceSummary", ai_text)
        self.assertIn("WorkspaceSummary", alert_text)

    def test_vite_build_still_available(self):
        package_json = (ROOT / "frontend/package.json").read_text(encoding="utf-8")
        self.assertIn('"build": "node ./scripts/ensure-rolldown-binding.mjs && vite build"', package_json)

    def test_frontend_brand_uses_repo_logo_asset(self):
        brand_text = (ROOT / "frontend/src/components/app/SidebarBrandCard.vue").read_text(encoding="utf-8")
        favicon_text = (ROOT / "frontend/public/favicon.svg").read_text(encoding="utf-8")
        source_logo = (ROOT / "docs/logo/logo.svg").read_text(encoding="utf-8")
        self.assertIn('src="/logo.svg"', brand_text)
        self.assertEqual(favicon_text.strip(), source_logo.strip())

    def test_app_shell_uses_sidebar_primary_navigation(self):
        text = (ROOT / "frontend/src/views/ConsoleShell.vue").read_text(encoding="utf-8")
        self.assertIn("AppPrimarySidebar", text)
        self.assertIn("app-shell", text)
        self.assertIn("app-sidebar", text)
        self.assertIn("app-mobile-nav", text)

    def test_app_is_minimal_shell_and_auth_artifacts_exist(self):
        app_text = (ROOT / "frontend/src/App.vue").read_text(encoding="utf-8")
        main_text = (ROOT / "frontend/src/main.js").read_text(encoding="utf-8")

        for rel in [
            "frontend/src/views/ConsoleShell.vue",
            "frontend/src/views/LoginView.vue",
            "frontend/src/views/ChangePasswordView.vue",
            "frontend/src/stores/auth.js",
            "frontend/src/stores/auth.test.js",
            "frontend/src/lib/authSession.js",
            "frontend/src/lib/authSession.test.js",
            "frontend/src/lib/routeAccess.js",
            "frontend/src/lib/routeAccess.test.js",
        ]:
            self.assertTrue((ROOT / rel).exists(), rel)

        self.assertIn("GlobalToast", app_text)
        self.assertIn("router-view", app_text)
        self.assertNotIn("AppPrimarySidebar", app_text)
        self.assertIn("path: '/login'", main_text)
        self.assertIn("path: '/change-password'", main_text)
        self.assertIn("router.beforeEach", main_text)

    def test_app_bootstraps_theme_mode_sync(self):
        app_text = (ROOT / "frontend/src/App.vue").read_text(encoding="utf-8")

        self.assertIn("hydrateThemePreference", app_text)
        self.assertIn("applyResolvedThemeToDocument", app_text)
        self.assertIn("watchSystemTheme", app_text)

    def test_global_styles_define_dark_and_light_theme_token_roots(self):
        style_text = (ROOT / "frontend/src/style.css").read_text(encoding="utf-8")

        self.assertIn(":root[data-theme='dark']", style_text)
        self.assertIn(":root[data-theme='light']", style_text)
        self.assertIn("--app-body-background", style_text)
        self.assertIn("--state-ok-bg", style_text)
        self.assertIn("--selection-bg", style_text)
        self.assertIn("--scrollbar-thumb", style_text)

    def test_console_shell_uses_theme_mode_switch_in_sidebar_and_mobile_actions(self):
        sidebar_text = (ROOT / "frontend/src/components/app/AppPrimarySidebar.vue").read_text(encoding="utf-8")
        console_text = (ROOT / "frontend/src/views/ConsoleShell.vue").read_text(encoding="utf-8")

        self.assertTrue((ROOT / "frontend/src/components/app/ThemeModeSwitch.vue").exists())
        self.assertIn("ThemeModeSwitch", sidebar_text)
        self.assertIn("theme-preference", sidebar_text)
        self.assertIn("ThemeModeSwitch", console_text)

    def test_theme_mode_switch_uses_single_row_inline_layout_when_expanded(self):
        text = (ROOT / "frontend/src/components/app/ThemeModeSwitch.vue").read_text(encoding="utf-8")

        self.assertIn("theme-mode-switch__group--inline", text)
        self.assertIn("grid-template-columns: repeat(3, minmax(0, 1fr));", text)
        self.assertIn("theme-mode-switch__option-label", text)

    def test_shell_and_import_workspaces_map_local_theme_tokens_to_semantic_tokens(self):
        console_text = (ROOT / "frontend/src/views/ConsoleShell.vue").read_text(encoding="utf-8")
        import_text = (ROOT / "frontend/src/views/ImportWorkspace.vue").read_text(encoding="utf-8")

        self.assertIn("--console-text: var(--text-primary);", console_text)
        self.assertIn("--console-panel: var(--bg-card);", console_text)
        self.assertIn("--import-text: var(--text-primary);", import_text)
        self.assertIn("--import-panel-bg: var(--bg-card);", import_text)

    def test_auth_and_primary_views_use_theme_aware_surface_variables(self):
        login_text = (ROOT / "frontend/src/views/LoginView.vue").read_text(encoding="utf-8")
        change_password_text = (ROOT / "frontend/src/views/ChangePasswordView.vue").read_text(encoding="utf-8")
        dashboard_text = (ROOT / "frontend/src/views/Dashboard.vue").read_text(encoding="utf-8")
        governance_text = (ROOT / "frontend/src/views/GovernanceLayout.vue").read_text(encoding="utf-8")
        alert_text = (ROOT / "frontend/src/views/AlertCenter.vue").read_text(encoding="utf-8")
        monitor_text = (ROOT / "frontend/src/views/MonitorCenter.vue").read_text(encoding="utf-8")
        energy_text = (ROOT / "frontend/src/views/EnergyOptimization.vue").read_text(encoding="utf-8")
        ai_text = (ROOT / "frontend/src/views/AIAssistant.vue").read_text(encoding="utf-8")

        self.assertIn("var(--auth-hero-title-gradient", login_text)
        self.assertIn("var(--auth-hero-title-gradient", change_password_text)
        self.assertNotIn("background: linear-gradient(180deg, #ffffff 0%", login_text)
        self.assertNotIn("background: linear-gradient(180deg, #ffffff 0%", change_password_text)
        self.assertIn("var(--state-ok-bg)", dashboard_text)
        self.assertIn("var(--state-ok-bg)", governance_text)
        self.assertIn("const severityConfig = computed(() => ({", alert_text)
        self.assertIn("const monitorPalette = computed(() => ({", monitor_text)
        self.assertIn("const energyPalette = computed(() => ({", energy_text)
        self.assertIn("var(--state-warning-bg)", ai_text)
        self.assertIn("var(--state-danger-bg)", ai_text)

    def test_governance_toolbar_dashboard_health_and_energy_use_theme_tokens(self):
        governance_text = (ROOT / "frontend/src/components/governance/GovernanceActionsMainPane.vue").read_text(encoding="utf-8")
        health_text = (ROOT / "frontend/src/components/dashboard/DashboardHealthTab.vue").read_text(encoding="utf-8")
        energy_text = (ROOT / "frontend/src/views/EnergyOptimization.vue").read_text(encoding="utf-8")

        self.assertIn("var(--bg-card)", governance_text)
        self.assertIn("var(--field-background)", governance_text)
        self.assertIn("var(--state-ok-bg)", governance_text)
        self.assertNotIn("rgba(17, 25, 43, 0.86)", governance_text)

        self.assertIn("var(--bg-strong)", health_text)
        self.assertIn("var(--state-warning-bg)", health_text)
        self.assertIn("var(--state-ok-bg)", health_text)
        self.assertNotIn("linear-gradient(145deg, rgba(14, 20, 29, 0.94)", health_text)

        self.assertIn("--energy-card: var(--bg-card);", energy_text)
        self.assertIn("--energy-card-strong: var(--bg-strong);", energy_text)
        self.assertIn("--energy-surface: var(--bg-surface);", energy_text)
        self.assertIn("var(--state-danger-bg)", energy_text)
        self.assertNotIn("--energy-card: rgba(19, 29, 50, 0.76);", energy_text)

    def test_primary_sidebar_keeps_compact_header_and_nav_layout(self):
        shell_text = (ROOT / "frontend/src/components/app/AppPrimarySidebar.vue").read_text(encoding="utf-8")
        nav_text = (ROOT / "frontend/src/components/app/SidebarNavRail.vue").read_text(encoding="utf-8")
        self.assertIn("grid-template-rows: auto minmax(0, 1fr) auto;", shell_text)
        self.assertIn("app-primary-sidebar__nav", shell_text)
        self.assertIn("app-primary-sidebar__footer", shell_text)
        self.assertIn("app-primary-nav-rail", nav_text)
        self.assertIn("app-primary-nav__scroll", nav_text)
        self.assertNotIn("overflow-y: auto", nav_text)

    def test_primary_sidebar_avoids_nested_scroll_for_six_entry_layout(self):
        console_text = (ROOT / "frontend/src/views/ConsoleShell.vue").read_text(encoding="utf-8")
        nav_text = (ROOT / "frontend/src/components/app/SidebarNavRail.vue").read_text(encoding="utf-8")

        self.assertNotRegex(console_text, r"\.app-sidebar\s*\{[^}]*overflow-y:\s*auto;")
        self.assertIn("overflow: visible;", nav_text)
        self.assertNotIn("max-height: 100%;", nav_text)

    def test_primary_sidebar_is_split_into_specialized_components(self):
        for rel in [
            "frontend/src/components/app/SidebarBrandCard.vue",
            "frontend/src/components/app/SidebarNavRail.vue",
        ]:
            self.assertTrue((ROOT / rel).exists(), rel)
        text = (ROOT / "frontend/src/components/app/AppPrimarySidebar.vue").read_text(encoding="utf-8")
        self.assertIn("SidebarBrandCard", text)
        self.assertIn("SidebarNavRail", text)
        self.assertNotIn("SidebarInfoDock", text)

    def test_primary_sidebar_uses_static_section_titles_for_navigation(self):
        shell_text = (ROOT / "frontend/src/composables/useConsoleShell.js").read_text(encoding="utf-8")
        nav_text = (ROOT / "frontend/src/components/app/SidebarNavRail.vue").read_text(encoding="utf-8")
        self.assertIn("group: 'governance'", shell_text)
        self.assertIn("group: 'analysis'", shell_text)
        self.assertIn("group: 'support'", shell_text)
        self.assertNotIn("const NAV_GROUPS", nav_text)
        self.assertNotIn("activeGroup", nav_text)
        self.assertNotIn("app-primary-nav__group", nav_text)
        self.assertIn("app-primary-nav__section-title", nav_text)
        self.assertIn('v-if="isActive(item)"', nav_text)

    def test_primary_sidebar_uses_compact_summary_header(self):
        brand_text = (ROOT / "frontend/src/components/app/SidebarBrandCard.vue").read_text(encoding="utf-8")
        sidebar_text = (ROOT / "frontend/src/components/app/AppPrimarySidebar.vue").read_text(encoding="utf-8")
        self.assertIn("summary", brand_text)
        self.assertIn("app-sidebar-brand-card__summary", brand_text)
        self.assertIn("app-sidebar-brand-card__crest", brand_text)
        self.assertIn("app-sidebar-brand-card__logo", brand_text)
        self.assertIn("app-sidebar-brand-card__copy--collapsed", brand_text)
        self.assertIn("app-sidebar-brand-card__switch-mark--hidden", brand_text)
        self.assertNotIn('v-if="props.collapsed" class="app-sidebar-brand-card__switch-mark"', brand_text)
        self.assertIn("切换服务器", brand_text)
        self.assertNotIn("app-sidebar-brand-card__pill", brand_text)
        self.assertNotIn("app-sidebar-brand-card__detail", brand_text)
        self.assertNotIn("current-time", sidebar_text)
        self.assertNotIn("telemetry", sidebar_text)

    def test_primary_sidebar_supports_collapsed_desktop_mode(self):
        sidebar_text = (ROOT / "frontend/src/components/app/AppPrimarySidebar.vue").read_text(encoding="utf-8")
        brand_text = (ROOT / "frontend/src/components/app/SidebarBrandCard.vue").read_text(encoding="utf-8")
        nav_text = (ROOT / "frontend/src/components/app/SidebarNavRail.vue").read_text(encoding="utf-8")
        app_text = (ROOT / "frontend/src/App.vue").read_text(encoding="utf-8")

        self.assertIn("collapsed", sidebar_text)
        self.assertIn("toggle-collapse", sidebar_text)
        self.assertIn("app-primary-sidebar--collapsed", sidebar_text)
        self.assertIn("app-primary-sidebar__footer", sidebar_text)
        self.assertIn("app-primary-sidebar__collapse-toggle", sidebar_text)
        self.assertIn("app-primary-sidebar__collapse-icon--hidden", sidebar_text)
        self.assertIn("app-primary-sidebar__collapse-label--collapsed", sidebar_text)
        self.assertIn("props.collapsed", brand_text)
        self.assertNotIn("app-sidebar-brand-card__toggle", brand_text)
        self.assertIn("app-sidebar-brand-card__switch--icon", brand_text)
        self.assertIn("props.collapsed", nav_text)
        self.assertIn("app-primary-nav__seal--hidden", nav_text)
        self.assertIn("app-primary-nav__body--collapsed", nav_text)
        self.assertNotIn('v-if="props.collapsed" class="app-primary-nav__seal"', nav_text)
        self.assertIn("app-primary-nav__item--collapsed", nav_text)
        self.assertIn(".app-primary-sidebar__collapse-toggle", app_text)

    def test_console_shell_uses_smooth_sidebar_transition_curve(self):
        console_text = (ROOT / "frontend/src/views/ConsoleShell.vue").read_text(encoding="utf-8")
        sidebar_text = (ROOT / "frontend/src/components/app/AppPrimarySidebar.vue").read_text(encoding="utf-8")
        brand_text = (ROOT / "frontend/src/components/app/SidebarBrandCard.vue").read_text(encoding="utf-8")
        nav_text = (ROOT / "frontend/src/components/app/SidebarNavRail.vue").read_text(encoding="utf-8")

        self.assertIn("cubic-bezier(0.22, 1, 0.36, 1)", console_text)
        self.assertIn("will-change: grid-template-columns;", console_text)
        self.assertIn("cubic-bezier(0.22, 1, 0.36, 1)", sidebar_text)
        self.assertIn("min-width: 0;", console_text)
        self.assertIn("overflow-x: hidden;", sidebar_text)
        self.assertIn("max-width: 100%;", brand_text)
        self.assertIn("max-width: 100%;", nav_text)

    def test_console_shell_exposes_switch_server_action(self):
        shell_text = (ROOT / "frontend/src/composables/useConsoleShell.js").read_text(encoding="utf-8")
        console_text = (ROOT / "frontend/src/views/ConsoleShell.vue").read_text(encoding="utf-8")
        self.assertIn("resetImportContext", shell_text)
        self.assertIn("switchServer", shell_text)
        self.assertIn("router.replace(IMPORT_ROUTE)", shell_text)
        self.assertIn(":switch-server-busy", console_text)
        self.assertIn("@switch-server", console_text)

    def test_console_shell_sidebar_wiring_is_trimmed(self):
        shell_text = (ROOT / "frontend/src/composables/useConsoleShell.js").read_text(encoding="utf-8")
        console_text = (ROOT / "frontend/src/views/ConsoleShell.vue").read_text(encoding="utf-8")
        app_text = (ROOT / "frontend/src/App.vue").read_text(encoding="utf-8")
        style_text = (ROOT / "frontend/src/style.css").read_text(encoding="utf-8")

        self.assertNotIn(":current-time", console_text)
        self.assertNotIn(":telemetry", console_text)
        self.assertNotIn("currentTime = ref('')", shell_text)
        self.assertNotIn("sidebarTelemetry", shell_text)
        self.assertNotIn(".app-primary-nav__group", app_text)
        self.assertNotIn(".app-primary-nav__group", style_text)

    def test_console_shell_uses_transient_sidebar_collapse_state(self):
        shell_text = (ROOT / "frontend/src/composables/useConsoleShell.js").read_text(encoding="utf-8")
        console_text = (ROOT / "frontend/src/views/ConsoleShell.vue").read_text(encoding="utf-8")

        self.assertIn("const sidebarCollapsed = ref(false)", shell_text)
        self.assertIn("function toggleSidebarCollapsed()", shell_text)
        self.assertIn("sidebarCollapsed", shell_text)
        self.assertIn("toggleSidebarCollapsed", shell_text)
        self.assertNotIn("localStorage", shell_text)
        self.assertIn("app-shell--sidebar-collapsed", console_text)
        self.assertIn(":collapsed=\"shell.sidebarCollapsed\"", console_text)
        self.assertIn("@toggle-collapse=\"shell.toggleSidebarCollapsed\"", console_text)

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
        self.assertIn("activeTab === 'live'", text)
        self.assertIn("liveSummary", text)

    def test_dashboard_overview_collapses_actions_into_single_main_card(self):
        text = (ROOT / "frontend/src/views/Dashboard.vue").read_text(encoding="utf-8")
        self.assertIn("DashboardOverviewTab", text)
        self.assertIn("overviewModel", text)
        self.assertNotIn("工作入口", text)
        self.assertNotIn("signal-grid", text)

    def test_dashboard_summary_meta_uses_horizontal_badge_group(self):
        text = (ROOT / "frontend/src/views/Dashboard.vue").read_text(encoding="utf-8")
        self.assertIn("dashboard-summary__meta", text)
        self.assertNotIn("governance-hero__side", text)

    def test_monitor_center_no_longer_hosts_replay_tab(self):
        text = (ROOT / "frontend/src/views/MonitorCenter.vue").read_text(encoding="utf-8")
        self.assertNotIn("{ key: 'replay'", text)
        self.assertNotIn("activeTab === 'replay'", text)

    def test_ai_assistant_executes_real_actions_without_rehearsal_copy(self):
        text = (ROOT / "frontend/src/views/AIAssistant.vue").read_text(encoding="utf-8")
        self.assertIn("执行控制台", text)
        self.assertNotIn("执行演练", text)
        self.assertNotIn("先演练后执行", text)
        self.assertNotIn("dry_run: true", text)

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

    def test_monitor_center_timeline_uses_compact_ledger_layout(self):
        text = (ROOT / "frontend/src/views/MonitorCenter.vue").read_text(encoding="utf-8")

        self.assertIn("timeline-toolbar", text)
        self.assertIn("timeline-range-chips", text)
        self.assertIn("timeline-ledger-list", text)
        self.assertIn("timeline-ledger-item", text)
        self.assertIn("timeline-ledger-item__meta", text)
        self.assertIn("timeline-ledger-item__command", text)
        self.assertNotIn("<table class=\"data-table\">", text)

    def test_views_do_not_use_ellipsis_to_hide_text(self):
        for rel in [
            "frontend/src/views/MonitorCenter.vue",
            "frontend/src/views/TaskManager.vue",
            "frontend/src/views/Dashboard.vue",
        ]:
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertNotIn("text-overflow: ellipsis", text, rel)

    def test_user_rule_cards_keep_graphical_action_buttons(self):
        text = (ROOT / "frontend/src/components/tasks/UserRuleCard.vue").read_text(encoding="utf-8")

        self.assertIn("action-card", text)
        self.assertIn("编辑规则", text)
        self.assertIn("恢复默认", text)

    def test_policy_console_exposes_pending_badges_and_inline_risk_banner(self):
        text = (ROOT / "frontend/src/components/governance/PolicyBudgetConsole.vue").read_text(encoding="utf-8")
        dock_text = (ROOT / "frontend/src/components/governance/PolicyActionDock.vue").read_text(encoding="utf-8")

        self.assertIn("待应用", text)
        self.assertIn("policy-budget-console__badge", text)
        self.assertIn("execution-banner", dock_text)
        self.assertIn("execution-banner--", dock_text)

    def test_policies_console_uses_switch_first_control_language(self):
        text = (ROOT / "frontend/src/components/governance/PolicyBudgetConsole.vue").read_text(encoding="utf-8")

        self.assertIn("policy-switch", text)
        self.assertIn("action-card", text)
        self.assertIn("待应用", text)

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

    def test_alert_archive_metrics_use_dark_surface_tokens(self):
        text = (ROOT / "frontend/src/components/alerts/AlertArchiveBoard.vue").read_text(encoding="utf-8")

        self.assertIn("archive-detail__metric", text)
        self.assertIn("background: rgba(255, 255, 255, 0.03);", text)
        self.assertIn("border: 1px solid var(--border-color);", text)
        self.assertNotIn("background: rgba(250, 246, 239, 0.9);", text)

    def test_ai_assistant_uses_runtime_session_api(self):
        text = (ROOT / "frontend/src/views/AIAssistant.vue").read_text(encoding="utf-8")
        api_text = (ROOT / "frontend/src/services/api.js").read_text(encoding="utf-8")

        self.assertIn("startAgentRuntimeSession", api_text)
        self.assertIn("approveAgentRuntimeSession", api_text)
        self.assertNotIn("aiControlPlan", api_text)
        self.assertNotIn("aiControlExecute", api_text)
        self.assertIn("AgentControlDock", text)
        self.assertIn("AgentExecutionLedger", text)
        self.assertNotIn("aiControlPlan(", text)

    def test_ai_assistant_uses_execution_ledger_components(self):
        text = (ROOT / "frontend/src/views/AIAssistant.vue").read_text(encoding="utf-8")

        self.assertIn("AgentControlDock", text)
        self.assertIn("AgentExecutionLedger", text)
        self.assertNotIn("AgentSessionTimeline", text)

        for rel in [
            "frontend/src/components/agent/AgentControlDock.vue",
            "frontend/src/components/agent/AgentExecutionLedger.vue",
            "frontend/src/components/agent/AgentRunOverviewBar.vue",
            "frontend/src/components/agent/AgentLedgerRound.vue",
            "frontend/src/components/agent/AgentLedgerEventCard.vue",
        ]:
            self.assertTrue((ROOT / rel).exists(), rel)

    def test_ai_workbench_component_files_exist(self):
        for rel in [
            "frontend/src/components/agent/AgentWorkbench.vue",
            "frontend/src/components/agent/AgentSessionRail.vue",
            "frontend/src/components/agent/AgentWorkbenchTopbar.vue",
            "frontend/src/components/agent/AgentThread.vue",
            "frontend/src/components/agent/AgentThreadRouteConfirmCard.vue",
            "frontend/src/components/agent/AgentComposer.vue",
        ]:
            self.assertTrue((ROOT / rel).exists(), rel)

    def test_ai_assistant_uses_streaming_live_panel_and_stream_apis(self):
        text = (ROOT / "frontend/src/views/AIAssistant.vue").read_text(encoding="utf-8")
        api_text = (ROOT / "frontend/src/services/api.js").read_text(encoding="utf-8")

        self.assertIn("PlannerLivePanel", text)
        self.assertIn("openAiChatStream", api_text)
        self.assertIn("openAgentRuntimeSessionStream", api_text)

    def test_ai_chat_pane_uses_dedicated_markdown_message_body(self):
        pane_text = (
            ROOT / "frontend/src/components/agent/AgentChatPane.vue"
        ).read_text(encoding="utf-8")
        body_text = (
            ROOT / "frontend/src/components/agent/AgentChatMessageBody.vue"
        ).read_text(encoding="utf-8")

        self.assertIn("AgentChatMessageBody", pane_text)
        self.assertIn("renderAssistantMarkdown", body_text)
        self.assertIn("v-html", body_text)
if __name__ == "__main__":
    unittest.main()
