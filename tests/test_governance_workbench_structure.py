import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class GovernanceWorkbenchStructureTests(unittest.TestCase):
    def test_main_router_registers_governance_parent_and_subroutes(self):
        text = (ROOT / "frontend/src/main.js").read_text(encoding="utf-8")

        self.assertIn("path: 'governance'", text)
        self.assertIn("name: 'GovernanceActions'", text)
        self.assertIn("name: 'GovernancePolicies'", text)
        self.assertIn("name: 'GovernanceReview'", text)
        self.assertIn("{ path: 'tasks', redirect: '/governance/actions' }", text)
        self.assertIn("{ path: 'scheduler', redirect: '/governance/policies' }", text)

    def test_console_shell_collapses_to_single_governance_entry(self):
        text = (ROOT / "frontend/src/composables/useConsoleShell.js").read_text(encoding="utf-8")

        self.assertIn("path: '/governance/actions'", text)
        self.assertIn("label: '治理'", text)
        self.assertNotIn("path: '/tasks'", text)
        self.assertNotIn("path: '/scheduler'", text)

    def test_governance_shell_files_exist(self):
        for rel in [
            "frontend/src/views/GovernanceLayout.vue",
            "frontend/src/views/GovernanceActionsView.vue",
            "frontend/src/views/GovernancePoliciesView.vue",
            "frontend/src/views/GovernanceReviewView.vue",
        ]:
            self.assertTrue((ROOT / rel).exists(), rel)

    def test_governance_data_uses_section_scoped_refresh(self):
        text = (ROOT / "frontend/src/composables/useGovernanceData.js").read_text(encoding="utf-8")

        self.assertIn("section: 'governance'", text)
        self.assertIn("key: 'actions'", text)
        self.assertIn("key: 'policies'", text)
        self.assertIn("key: 'review'", text)
        self.assertNotIn("section: 'tasks'", text)
        self.assertNotIn("section: 'scheduler'", text)

    def test_governance_layout_creates_shared_execution_context_once(self):
        text = (ROOT / "frontend/src/views/GovernanceLayout.vue").read_text(encoding="utf-8")

        self.assertEqual(text.count("useExecutionMode()"), 1)
        self.assertEqual(text.count("useActionFeedback()"), 1)
        self.assertIn("<router-view v-slot", text)
        self.assertIn("buildGovernanceHeaderModel", text)

    def test_actions_view_only_hosts_object_actions_and_fairness_summary(self):
        text = (ROOT / "frontend/src/views/GovernanceActionsView.vue").read_text(encoding="utf-8")

        self.assertIn("TaskProcessLedger", text)
        self.assertIn("候选让路任务", text)
        self.assertIn("公平摘要", text)
        self.assertNotIn("保存预算", text)
        self.assertNotIn("runScheduleOnce", text)

    def test_policies_view_hosts_only_strategy_controls(self):
        text = (ROOT / "frontend/src/views/GovernancePoliciesView.vue").read_text(encoding="utf-8")

        self.assertIn("总功率预算治理", text)
        self.assertIn("碳预算治理", text)
        self.assertIn("高级策略", text)
        self.assertIn("UserRulesGrid", text)
        self.assertNotIn("TaskProcessLedger", text)
        self.assertNotIn("pauseTask", text)
        self.assertNotIn("resumeTask", text)
        self.assertNotIn("terminateTask", text)

    def test_policies_view_routes_mutations_through_control_plane_only(self):
        text = (ROOT / "frontend/src/views/GovernancePoliciesView.vue").read_text(encoding="utf-8")

        self.assertIn("submitBuiltinCommand", text)
        self.assertNotIn("setCarbonBudget", text)
        self.assertNotIn("toggleAutoSchedule", text)
        self.assertNotIn("saveGovernanceRule", text)
        self.assertNotIn("deleteGovernanceRule", text)

    def test_policies_workspace_keeps_budget_first_and_action_dock_split(self):
        text = (ROOT / "frontend/src/components/governance/GovernancePoliciesWorkspace.vue").read_text(encoding="utf-8")

        self.assertIn("PolicyBudgetConsole", text)
        self.assertIn("PolicyActionDock", text)
        self.assertIn("budget-card-state", text)
        self.assertIn("carbon-card-state", text)

    def test_policies_view_uses_inline_execution_banner(self):
        text = (ROOT / "frontend/src/views/GovernancePoliciesView.vue").read_text(encoding="utf-8")

        self.assertIn("buildExecutionBannerModel", text)
        self.assertIn("executionBanner", text)

    def test_advanced_panel_stays_folded_outside_budget_console(self):
        text = (ROOT / "frontend/src/components/governance/PolicyAdvancedPanel.vue").read_text(encoding="utf-8")

        self.assertIn("GPU 限功率", text)
        self.assertIn("用户额度规则", text)
        self.assertNotIn("执行一次调度", text)

    def test_user_rules_grid_renders_rule_cards(self):
        text = (ROOT / "frontend/src/components/tasks/UserRulesGrid.vue").read_text(encoding="utf-8")

        self.assertIn("UserRuleCard", text)
        self.assertIn("rules-grid", text)

    def test_cluster_job_ledger_exposes_manual_lifecycle_actions(self):
        ledger_text = (ROOT / "frontend/src/components/cluster/ClusterJobLedger.vue").read_text(encoding="utf-8")
        action_text = (ROOT / "frontend/src/lib/clusterConsoleActions.js").read_text(encoding="utf-8")
        view_text = (ROOT / "frontend/src/views/ClusterJobs.vue").read_text(encoding="utf-8")

        self.assertIn("availableJobActions", ledger_text)
        self.assertIn("pause", action_text)
        self.assertIn("resume", action_text)
        self.assertIn("cancel", action_text)
        self.assertIn("submitBuiltinCommand", view_text)

    def test_governance_task_ledger_uses_compact_rows_with_inline_details(self):
        parent_text = (ROOT / "frontend/src/components/tasks/TaskProcessLedger.vue").read_text(encoding="utf-8")
        row_text = (ROOT / "frontend/src/components/tasks/TaskProcessLedgerRow.vue").read_text(encoding="utf-8")

        self.assertIn("TaskProcessLedgerRow", parent_text)
        self.assertIn("expandedPid", parent_text)
        self.assertIn("syncExpandedPid", parent_text)
        self.assertIn("toggleExpandedPid", parent_text)
        self.assertIn("查看详情", row_text)
        self.assertIn("收起详情", row_text)
        self.assertIn("task-process-ledger-row__summary", row_text)
        self.assertIn("task-process-ledger-row__details", row_text)
        self.assertIn("task-process-ledger-row__readonly", row_text)
        self.assertNotIn("task-process-ledger__governance", row_text)
        self.assertNotIn("task-process-ledger__actions", row_text)

    def test_capability_drawer_supports_typed_forms_before_raw_json(self):
        text = (ROOT / "frontend/src/components/governance/CapabilityCommandDrawer.vue").read_text(encoding="utf-8")

        self.assertIn("buildCapabilityFormDraft", text)
        self.assertIn("buildCapabilityFormArguments", text)
        self.assertIn("当前能力未定义结构化表单", text)
        self.assertIn("参数预览", text)

    def test_control_command_ledger_supports_filters_and_detail_toggle(self):
        text = (ROOT / "frontend/src/components/governance/ControlCommandLedger.vue").read_text(encoding="utf-8")

        self.assertIn("statusFilter", text)
        self.assertIn("approvalFilter", text)
        self.assertIn("展开详情", text)
        self.assertIn("argumentSummary", text)


if __name__ == "__main__":
    unittest.main()
