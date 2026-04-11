import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ImportLayerStructureTests(unittest.TestCase):
    def test_import_route_and_view_exist(self):
        main_text = (ROOT / "frontend/src/main.js").read_text(encoding="utf-8")

        self.assertIn("ImportWorkspace", main_text)
        self.assertIn("path: '/import'", main_text)
        self.assertTrue((ROOT / "frontend/src/views/ImportWorkspace.vue").exists())

    def test_import_components_and_helpers_exist(self):
        for rel in [
            "frontend/src/components/import/ImportSourcePanel.vue",
            "frontend/src/components/import/ImportHardwareSummary.vue",
            "frontend/src/components/import/ImportGpuGrid.vue",
            "frontend/src/lib/importContext.js",
            "frontend/src/lib/importContext.test.js",
        ]:
            self.assertTrue((ROOT / rel).exists(), rel)

    def test_api_and_store_expose_import_context_contract(self):
        api_text = (ROOT / "frontend/src/services/api.js").read_text(encoding="utf-8")
        store_text = (ROOT / "frontend/src/stores/app.js").read_text(encoding="utf-8")

        for name in [
            "getImportContext",
            "scanImportContext",
            "commitImportContext",
            "resetImportContext",
        ]:
            self.assertIn(f"export const {name}", api_text)

        self.assertIn("importContext", store_text)
        self.assertIn("setImportContext", store_text)

    def test_app_redirects_locked_workspace_to_import_route(self):
        main_text = (ROOT / "frontend/src/main.js").read_text(encoding="utf-8")
        route_text = (ROOT / "frontend/src/lib/routeAccess.js").read_text(encoding="utf-8")

        self.assertIn("router.beforeEach", main_text)
        self.assertIn("bootstrapWorkspaceState", main_text)
        self.assertIn("path: '/import'", main_text)
        self.assertIn("const IMPORT_PATH = '/import'", route_text)
        self.assertIn("redirect(IMPORT_PATH)", route_text)
        self.assertIn("const LOGIN_PATH = '/login'", route_text)
        self.assertIn("const CHANGE_PASSWORD_PATH = '/change-password'", route_text)

    def test_import_view_is_standalone_entry_page(self):
        import_text = (ROOT / "frontend/src/views/ImportWorkspace.vue").read_text(encoding="utf-8")

        self.assertNotIn("WorkspaceSummary", import_text)
        self.assertNotIn("WorkspacePaneLayout", import_text)
        self.assertIn("import-prep-layout", import_text)
        self.assertIn("ImportPrepSidebar", import_text)
        self.assertIn("ImportPrepWorkbench", import_text)
        self.assertIn("proxyRefs", import_text)
        self.assertIn("proxyRefs(useImportWorkspace())", import_text)
        self.assertIn("providerType", import_text)
        self.assertIn("authType", import_text)
        self.assertIn("sudoEnabled", import_text)
        self.assertIn("privateKey", import_text)

    def test_import_stage_components_and_tabs_exist(self):
        for rel in [
            "frontend/src/components/import/ImportPrepSidebar.vue",
            "frontend/src/components/import/ImportPrepWorkbench.vue",
            "frontend/src/components/import/ImportPrepTabs.vue",
            "frontend/src/components/import/ImportSavedHostsStage.vue",
            "frontend/src/components/import/ImportConnectionStage.vue",
            "frontend/src/components/import/ImportHardwareStage.vue",
            "frontend/src/components/import/ImportSelectionStage.vue",
            "frontend/src/composables/useSavedHosts.js",
            "frontend/src/composables/useSavedHosts.test.js",
        ]:
            self.assertTrue((ROOT / rel).exists(), rel)

        tabs_text = (ROOT / "frontend/src/components/import/ImportPrepTabs.vue").read_text(encoding="utf-8")
        self.assertIn("已保存主机", tabs_text)
        self.assertIn("连接来源", tabs_text)
        self.assertIn("硬件概览", tabs_text)
        self.assertIn("选卡导入", tabs_text)

    def test_import_sidebar_branding_uses_new_product_name(self):
        sidebar_text = (ROOT / "frontend/src/components/import/ImportPrepSidebar.vue").read_text(encoding="utf-8")

        self.assertIn("智算中心优化代码生成系统", sidebar_text)
        self.assertNotIn("GPU GOVERNANCE SETUP", sidebar_text)

    def test_import_view_recomposes_stage_components_instead_of_flat_panels(self):
        text = (ROOT / "frontend/src/views/ImportWorkspace.vue").read_text(encoding="utf-8")

        self.assertIn("ImportSavedHostsStage", text)
        self.assertIn("ImportConnectionStage", text)
        self.assertIn("ImportHardwareStage", text)
        self.assertIn("ImportSelectionStage", text)
        self.assertNotIn("<ImportSourcePanel", text)
        self.assertNotIn("<ImportHardwareSummary", text)
        self.assertNotIn("<ImportGpuGrid", text)

    def test_saved_host_stage_uses_saved_host_api_contract(self):
        api_text = (ROOT / "frontend/src/services/api.js").read_text(encoding="utf-8")
        helper_text = (ROOT / "frontend/src/lib/importWorkbench.js").read_text(encoding="utf-8")
        logic_text = (ROOT / "frontend/src/composables/createImportWorkspaceController.js").read_text(encoding="utf-8")
        wrapper_text = (ROOT / "frontend/src/composables/useImportWorkspace.js").read_text(encoding="utf-8")
        stage_text = (ROOT / "frontend/src/components/import/ImportSavedHostsStage.vue").read_text(encoding="utf-8")

        self.assertIn("export const getSavedHosts", api_text)
        self.assertIn("export const deleteSavedHost", api_text)
        self.assertIn("{ key: 'saved'", helper_text)
        self.assertIn("saved_host_id", logic_text)
        self.assertIn("activeStage: ref('saved')", logic_text)
        self.assertIn("handleSavedHostEdit", logic_text)
        self.assertIn("createImportWorkspaceController", wrapper_text)
        self.assertIn("@edit=\"workspace.handleSavedHostEdit\"", (ROOT / "frontend/src/views/ImportWorkspace.vue").read_text(encoding="utf-8"))
        self.assertIn("编辑连接", stage_text)

    def test_saved_host_scan_continue_ui_is_wired_through_hardware_and_selection(self):
        saved_stage = (ROOT / "frontend/src/components/import/ImportSavedHostsStage.vue").read_text(encoding="utf-8")
        hardware_stage = (ROOT / "frontend/src/components/import/ImportHardwareStage.vue").read_text(encoding="utf-8")
        selection_stage = (ROOT / "frontend/src/components/import/ImportSelectionStage.vue").read_text(encoding="utf-8")
        workspace_view = (ROOT / "frontend/src/views/ImportWorkspace.vue").read_text(encoding="utf-8")
        summary_bar = (ROOT / "frontend/src/components/import/ImportSavedHostSummaryBar.vue")

        self.assertTrue(summary_bar.exists())
        self.assertIn("扫描并继续", saved_stage)
        self.assertIn("ImportSavedHostSummaryBar", hardware_stage)
        self.assertIn("ImportSavedHostSummaryBar", selection_stage)
        self.assertIn(':saved-host-summary="workspace.savedHostSummary"', workspace_view)
        self.assertIn(':feedback="workspace.feedback"', workspace_view)
        self.assertIn("当前复用主机", summary_bar.read_text(encoding="utf-8"))

    def test_import_workbench_keeps_tabs_body_and_footer_isolated(self):
        text = (ROOT / "frontend/src/components/import/ImportPrepWorkbench.vue").read_text(encoding="utf-8")

        self.assertIn("import-prep-workbench__body", text)
        self.assertIn("import-prep-workbench__footer", text)
        self.assertIn("grid-template-rows: auto minmax(0, 1fr) auto;", text)
        self.assertIn("overflow-y: auto", text)

    def test_connection_stage_owns_mode_switch_and_scan_status(self):
        stage_text = (ROOT / "frontend/src/components/import/ImportConnectionStage.vue").read_text(encoding="utf-8")
        panel_text = (ROOT / "frontend/src/components/import/ImportSourcePanel.vue").read_text(encoding="utf-8")

        self.assertIn("本机 Agent", stage_text)
        self.assertIn("远程 Agent", stage_text)
        self.assertIn("SSH Linux", stage_text)
        self.assertIn("扫描硬件", stage_text)
        self.assertNotIn("扫描硬件", panel_text)
        self.assertNotIn("已选", panel_text)

    def test_hardware_and_selection_stages_expose_secondary_views(self):
        hardware_text = (ROOT / "frontend/src/components/import/ImportHardwareStage.vue").read_text(encoding="utf-8")
        selection_text = (ROOT / "frontend/src/components/import/ImportSelectionStage.vue").read_text(encoding="utf-8")

        self.assertIn("卡片视图", hardware_text)
        self.assertIn("摘要视图", hardware_text)
        self.assertIn("全部候选", selection_text)
        self.assertIn("已选清单", selection_text)
        self.assertIn("ImportGpuGrid", selection_text)
        self.assertIn("import-selection-stage__feedback", selection_text)
        self.assertIn("未选择 GPU 也可提交，控制台将以空作用域运行", selection_text)
        self.assertIn("import-selection-stage__grid-shell", selection_text)
        self.assertIn("overflow-y: auto", selection_text)

    def test_import_workbench_files_do_not_hide_copy_with_ellipsis(self):
        for rel in [
            "frontend/src/views/ImportWorkspace.vue",
            "frontend/src/components/import/ImportPrepSidebar.vue",
            "frontend/src/components/import/ImportPrepWorkbench.vue",
            "frontend/src/components/import/ImportConnectionStage.vue",
            "frontend/src/components/import/ImportHardwareStage.vue",
            "frontend/src/components/import/ImportSelectionStage.vue",
        ]:
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertNotIn("text-overflow: ellipsis", text, rel)

    def test_dashboard_no_longer_hosts_connection_center(self):
        dashboard_text = (ROOT / "frontend/src/views/Dashboard.vue").read_text(encoding="utf-8")

        self.assertNotIn("getConnectionConfig", dashboard_text)
        self.assertNotIn("testConnectionConfig", dashboard_text)
        self.assertNotIn("updateConnectionConfig", dashboard_text)
        self.assertNotIn("connectionForm", dashboard_text)
        self.assertNotIn("saveConnection", dashboard_text)
        self.assertNotIn("testConnection", dashboard_text)


if __name__ == "__main__":
    unittest.main()
