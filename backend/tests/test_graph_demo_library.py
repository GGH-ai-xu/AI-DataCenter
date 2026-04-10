import pytest

from app.services.graph_demo_library import get_graph_demo_payload, list_graph_demo_kinds


def test_graph_demo_library_exposes_supported_kinds():
    assert list_graph_demo_kinds() == ["paper", "optimization"]


@pytest.mark.parametrize(
    ("kind", "expected_mode", "expected_source"),
    [
        ("paper", "paper", "paper"),
        ("optimization", "optimization", "optimization"),
    ],
)
def test_graph_demo_payloads_are_non_empty(kind, expected_mode, expected_source):
    payload = get_graph_demo_payload(kind)

    assert payload["mode"] == expected_mode
    assert payload["source"] == expected_source
    assert payload["title"]
    assert len(payload["nodes"]) > 0
    assert len(payload["relations"]) > 0


def test_graph_demo_payload_rejects_unknown_kind():
    with pytest.raises(ValueError, match="unsupported graph demo kind"):
        get_graph_demo_payload("unknown")
