# -*- coding: utf-8 -*-
"""
后端单元测试 - 会话查询接口 GET /api/session/{session_id}

feature/session-query-endpoint 子功能测试。

测试目标：
    1. 存在的会话返回 200 及完整信息
    2. 不存在的会话返回 404 SESSION_NOT_FOUND
    3. is_expired 字段正确计算
    4. 响应字段符合 SessionQueryResponse 契约
    5. 过期会话可查询但 is_expired=true
"""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

import main
from main import app, _SESSION_STORE


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_session_store():
    """每个测试前清空会话存储，保证隔离性"""
    _SESSION_STORE.clear()
    yield
    _SESSION_STORE.clear()


def _create_session(
    session_id: str = "test-session-001",
    patient_id: str = "P20261104001",
    department: str = "老年医学科",
    ttl_hours: int = 72,
) -> str:
    """辅助方法：向会话存储中写入一条测试会话"""
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=ttl_hours)
    _SESSION_STORE[session_id] = {
        "session_id": session_id,
        "patient_id": patient_id,
        "department": department,
        "consent_given": True,
        "callback_url": None,
        "status": "active",
        "started_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
    }
    return session_id


class TestSessionQuerySuccess:
    """会话查询成功场景"""

    def test_existing_session_returns_200(self, client: TestClient):
        """存在的会话应返回 200"""
        sid = _create_session()
        resp = client.get(f"/api/session/{sid}")
        assert resp.status_code == 200

    def test_response_contains_all_fields(self, client: TestClient):
        """响应应包含所有必要字段"""
        sid = _create_session()
        resp = client.get(f"/api/session/{sid}")
        data = resp.json()
        required_fields = {
            "session_id", "patient_id", "department", "consent_given",
            "callback_url", "status", "started_at", "expires_at", "is_expired",
        }
        assert required_fields.issubset(set(data.keys()))

    def test_echoes_session_data(self, client: TestClient):
        """响应应原样回传会话数据"""
        sid = _create_session(
            session_id="sid-123",
            patient_id="P-TEST-001",
            department="康复科",
        )
        resp = client.get(f"/api/session/{sid}")
        data = resp.json()
        assert data["session_id"] == "sid-123"
        assert data["patient_id"] == "P-TEST-001"
        assert data["department"] == "康复科"
        assert data["consent_given"] is True
        assert data["status"] == "active"

    def test_active_session_is_expired_false(self, client: TestClient):
        """未过期会话的 is_expired 应为 false"""
        sid = _create_session(ttl_hours=72)
        resp = client.get(f"/api/session/{sid}")
        assert resp.json()["is_expired"] is False


class TestSessionQueryExpired:
    """过期会话查询场景"""

    def test_expired_session_is_expired_true(self, client: TestClient):
        """已过期会话的 is_expired 应为 true"""
        sid = _create_session(ttl_hours=-1)  # 已过期
        resp = client.get(f"/api/session/{sid}")
        assert resp.json()["is_expired"] is True

    def test_expired_session_still_queryable(self, client: TestClient):
        """过期会话仍可查询（不返回 404）"""
        sid = _create_session(ttl_hours=-1)
        resp = client.get(f"/api/session/{sid}")
        assert resp.status_code == 200


class TestSessionQueryNotFound:
    """会话不存在场景"""

    def test_nonexistent_session_returns_404(self, client: TestClient):
        """不存在的会话应返回 404"""
        resp = client.get("/api/session/nonexistent-session-id")
        assert resp.status_code == 404

    def test_not_found_has_code(self, client: TestClient):
        """404 响应应包含 SESSION_NOT_FOUND 错误码"""
        resp = client.get("/api/session/nonexistent-session-id")
        data = resp.json()
        assert data.get("code") == "SESSION_NOT_FOUND"

    def test_not_found_message_contains_session_id(self, client: TestClient):
        """404 消息应包含请求的 session_id"""
        resp = client.get("/api/session/my-test-id")
        data = resp.json()
        assert "my-test-id" in data.get("message", "")


class TestSessionQueryContract:
    """响应契约验证"""

    def test_no_extra_fields(self, client: TestClient):
        """响应不应包含多余字段（严格契约）"""
        sid = _create_session()
        resp = client.get(f"/api/session/{sid}")
        data = resp.json()
        allowed_fields = {
            "session_id", "patient_id", "department", "consent_given",
            "callback_url", "status", "started_at", "expires_at", "is_expired",
        }
        assert set(data.keys()) == allowed_fields

    def test_callback_url_none_when_not_set(self, client: TestClient):
        """未设置 callback_url 时响应应为 null"""
        sid = _create_session()
        resp = client.get(f"/api/session/{sid}")
        assert resp.json()["callback_url"] is None

    def test_callback_url_echoed_when_set(self, client: TestClient):
        """设置了 callback_url 时应原样回传"""
        sid = "sid-with-callback"
        now = datetime.now(timezone.utc)
        _SESSION_STORE[sid] = {
            "session_id": sid,
            "patient_id": "P001",
            "department": "老年医学科",
            "consent_given": True,
            "callback_url": "https://example.com/callback",
            "status": "active",
            "started_at": now.isoformat(),
            "expires_at": (now + timedelta(hours=72)).isoformat(),
        }
        resp = client.get(f"/api/session/{sid}")
        assert resp.json()["callback_url"] == "https://example.com/callback"
