from app.services.workspace_context import (
    PUBLIC_WORKSPACE_KEY,
    build_workspace_key,
    current_workspace_key,
    set_workspace_key,
    reset_workspace_key,
)


def test_build_workspace_key_prefers_user_id():
    assert build_workspace_key({"id": 7}, role="admin") == "user:7"


def test_build_workspace_key_falls_back_to_role():
    assert build_workspace_key(None, role="observer") == "role:observer"


def test_workspace_key_context_round_trip():
    token = set_workspace_key("user:9")
    try:
        assert current_workspace_key() == "user:9"
    finally:
        reset_workspace_key(token)

    assert current_workspace_key() == PUBLIC_WORKSPACE_KEY
