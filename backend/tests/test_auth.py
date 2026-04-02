"""Token 认证中间件单元测试"""

import pytest
from app.middleware.auth import (
    _extract_token,
    _is_local_request,
    _resolve_role,
    ADMIN_TOKEN,
    OBSERVER_TOKEN,
)


class FakeRequest:
    """模拟 FastAPI Request 对象"""
    def __init__(self, headers=None, query_params=None, client_host=None):
        self.headers = headers or {}
        self.query_params = query_params or {}
        self.client = type("Client", (), {"host": client_host})() if client_host else None


class TestExtractToken:
    def test_bearer_header(self):
        req = FakeRequest(headers={"authorization": f"Bearer {ADMIN_TOKEN}"})
        assert _extract_token(req) == ADMIN_TOKEN

    def test_bearer_case_insensitive(self):
        req = FakeRequest(headers={"authorization": f"bearer {OBSERVER_TOKEN}"})
        assert _extract_token(req) == OBSERVER_TOKEN

    def test_query_param_fallback(self):
        req = FakeRequest(query_params={"token": "my-token"})
        assert _extract_token(req) == "my-token"

    def test_no_token(self):
        req = FakeRequest()
        assert _extract_token(req) is None

    def test_empty_header(self):
        req = FakeRequest(headers={"authorization": ""})
        assert _extract_token(req) is None


class TestResolveRole:
    def test_admin(self):
        assert _resolve_role(ADMIN_TOKEN) == "admin"

    def test_observer(self):
        assert _resolve_role(OBSERVER_TOKEN) == "observer"

    def test_invalid(self):
        assert _resolve_role("bad-token") is None

    def test_none(self):
        assert _resolve_role(None) is None


class TestLocalRequest:
    def test_localhost_is_trusted(self):
        req = FakeRequest(client_host="127.0.0.1")
        assert _is_local_request(req) is True

    def test_ipv6_localhost_is_trusted(self):
        req = FakeRequest(client_host="::1")
        assert _is_local_request(req) is True

    def test_remote_host_is_not_trusted(self):
        req = FakeRequest(client_host="10.0.0.8")
        assert _is_local_request(req) is False
