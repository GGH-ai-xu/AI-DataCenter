import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FrontendPerformanceStructureTests(unittest.TestCase):
    def test_monitor_center_refreshes_only_active_tab(self):
        text = (ROOT / "frontend/src/views/MonitorCenter.vue").read_text(encoding="utf-8")

        self.assertIn("refreshActiveTab", text)
        self.assertNotIn("tasks.push(loadTraining())", text)
        self.assertNotIn("tasks.push(loadUsers())", text)
        self.assertNotIn("tasks.push(loadTimeline())", text)

    def test_task_manager_uses_normalized_process_summary(self):
        text = (ROOT / "frontend/src/views/TaskManager.vue").read_text(encoding="utf-8")

        self.assertIn("normalizedProcesses", text)
        self.assertIn("processSummary", text)
        self.assertNotIn("new Set(manageableProcesses.value.map", text)

    def test_power_trend_chart_updates_without_interval_rebuild(self):
        text = (ROOT / "frontend/src/components/charts/PowerTrendChart.vue").read_text(encoding="utf-8")

        self.assertIn("updateChartOption", text)
        self.assertNotIn("setInterval(updateChart, 1000)", text)
        self.assertNotIn("onMounted(() => { timer = setInterval", text)

    def test_gpu_detail_precomputes_chart_ready_history(self):
        text = (ROOT / "frontend/src/views/GpuDetail.vue").read_text(encoding="utf-8")

        self.assertIn("processedHistory", text)
        self.assertNotIn("history.value.map(d => d.temperature)", text)

    def test_app_page_transition_avoids_blur_filters(self):
        text = (ROOT / "frontend/src/App.vue").read_text(encoding="utf-8")

        self.assertNotIn('mode="out-in"', text)
        self.assertNotIn("filter: blur(3px)", text)
        self.assertNotIn("cloud-appear", text)

    def test_main_router_warms_heavy_views_after_boot(self):
        text = (ROOT / "frontend/src/main.js").read_text(encoding="utf-8")

        self.assertIn("loadEnergyOptimizationView", text)
        self.assertIn("loadMonitorCenterView", text)
        self.assertIn("warmRouteModules", text)
        self.assertIn("requestIdleCallback", text)

    def test_energy_page_uses_modular_echarts_imports(self):
        text = (ROOT / "frontend/src/views/EnergyOptimization.vue").read_text(encoding="utf-8")

        self.assertIn("from 'echarts/core'", text)
        self.assertNotIn("import * as echarts from 'echarts'", text)

    def test_global_styles_use_stable_ui_text_rendering(self):
        text = (ROOT / "frontend/src/style.css").read_text(encoding="utf-8")

        self.assertIn("--font-ui", text)
        self.assertIn("font-family: var(--font-ui)", text)
        self.assertNotIn("text-rendering: optimizeLegibility", text)
        self.assertNotIn("backdrop-filter: blur(18px)", text)

    def test_energy_page_does_not_import_remote_fonts(self):
        text = (ROOT / "frontend/src/views/EnergyOptimization.vue").read_text(encoding="utf-8")

        self.assertNotIn("fonts.googleapis.com", text)
        self.assertNotIn("@import url(", text)


if __name__ == "__main__":
    unittest.main()
