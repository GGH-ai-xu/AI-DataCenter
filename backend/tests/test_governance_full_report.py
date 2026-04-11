import asyncio
import logging

from app.api import governance as governance_api


class _DummyImportContext:
    @staticmethod
    def filter_gpus(gpus):
        return gpus


class _DummyStore:
    async def get_power_summary(self, hours, gpu_indexes=None):
        return {"hours": hours, "gpu_indexes": gpu_indexes or []}

    async def get_alerts(self, limit=10, gpu_indexes=None):
        return [{"severity": "warning", "gpu_indexes": gpu_indexes or [], "limit": limit}]


class _DummyAgent:
    async def get_all_gpus(self):
        return [{"index": 0, "name": "GPU 0"}]


class _SuccessLlm:
    async def generate_report(self, summary, alerts):
        assert summary["hours"] == 24
        assert alerts[0]["limit"] == 10
        return "AI 段落已生成"


class _SlowLlm:
    async def generate_report(self, summary, alerts):
        await asyncio.sleep(0.05)
        return "slow"


class _DummyAppState:
    def __init__(self, llm):
        self.llm = llm
        self.agent = _DummyAgent()
        self.store = _DummyStore()
        self.import_context = _DummyImportContext()


def test_build_full_report_ai_section_returns_ai_content(monkeypatch):
    monkeypatch.setattr(governance_api, "FULL_REPORT_AI_TIMEOUT_SECONDS", 0.1)
    app_state = _DummyAppState(_SuccessLlm())

    section = asyncio.run(
        governance_api._build_full_report_ai_section(
            app_state,
            hours=24,
            gpu_indexes=[0],
            logger=logging.getLogger("test"),
        )
    )

    assert section == [
        "## 五、AI 分析报告\n",
        "AI 段落已生成",
        "",
    ]


def test_build_full_report_ai_section_falls_back_on_timeout(monkeypatch):
    monkeypatch.setattr(governance_api, "FULL_REPORT_AI_TIMEOUT_SECONDS", 0.01)
    app_state = _DummyAppState(_SlowLlm())

    section = asyncio.run(
        governance_api._build_full_report_ai_section(
            app_state,
            hours=24,
            gpu_indexes=[0],
            logger=logging.getLogger("test"),
        )
    )

    assert len(section) == 1
    assert "AI 分析生成超时" in section[0]
