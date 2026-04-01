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


if __name__ == "__main__":
    unittest.main()
