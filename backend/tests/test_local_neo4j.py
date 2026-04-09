import asyncio
from pathlib import Path

from app.services.local_neo4j import LocalNeo4jService


def _make_service(tmp_path: Path) -> LocalNeo4jService:
    script = tmp_path / "scripts" / "start-local-neo4j.ps1"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text("Write-Output 'ok'\n", encoding="utf-8")
    return LocalNeo4jService(repo_root=str(tmp_path))


def test_local_neo4j_capability_accepts_windows_loopback(monkeypatch, tmp_path):
    service = _make_service(tmp_path)
    monkeypatch.setattr("app.services.local_neo4j.os.name", "nt", raising=False)

    capability = service.capability("bolt://127.0.0.1:7687")

    assert capability["local_start_available"] is True
    assert "127.0.0.1:7687" in capability["local_start_message"]


def test_local_neo4j_capability_rejects_remote_uri(monkeypatch, tmp_path):
    service = _make_service(tmp_path)
    monkeypatch.setattr("app.services.local_neo4j.os.name", "nt", raising=False)

    capability = service.capability("bolt://10.0.0.8:7687")

    assert capability["local_start_available"] is False
    assert "远程图库" in capability["local_start_message"]


def test_local_neo4j_ensure_running_short_circuits_when_port_is_open(monkeypatch, tmp_path):
    service = _make_service(tmp_path)
    monkeypatch.setattr("app.services.local_neo4j.os.name", "nt", raising=False)
    monkeypatch.setattr(service, "_is_port_open", lambda host, port: True)

    result = asyncio.run(service.ensure_running("bolt://127.0.0.1:7687"))

    assert result["ok"] is True
    assert result["started"] is False
    assert "已在运行" in result["message"]
