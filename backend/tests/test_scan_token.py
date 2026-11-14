# -*- coding: utf-8 -*-
"""
后端单元测试 - 扫码令牌核验接口 POST /api/session/verify-token

医院蓝多设备适配新增接口。

测试目标：
    1. 有效令牌核验成功，返回 session_id 和 patient_id
    2. 不存在的令牌返回 valid=false
    3. 已使用的令牌返回 valid=false
    4. 过期的令牌返回 valid=false
    5. 令牌长度校验（min_length=24）
    6. 令牌一次性使用
"""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

import main
from main import app, _SCAN_TOKEN_STORE


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_token_store():
    """每个测试前清空令牌存储"""
    _SCAN_TOKEN_STORE.clear()
    yield
    _SCAN_TOKEN_STORE.clear()


def _create_token(
    token: str = "a" * 32,
    patient_id: str = "P20261104001",
    session_id: str = "S20261104001",
    expires_minutes: int = 10,
    used: bool = False,
) -> str:
    """辅助方法：向令牌存储中写入一条测试令牌"""
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)).isoformat()
    _SCAN_TOKEN_STORE[token] = {
        "patient_id": patient_id,
        "session_id": session_id,
        "expires_at": expires_at,
        "used": used,
    }
    return token


class TestScanTokenSuccess:
    """扫码令牌核验成功场景"""

    def test_valid_token_returns_valid_true(self, client: TestClient):
        """有效令牌应返回 valid=true"""
        token = _create_token()
        resp = client.post("/api/session/verify-token", json={"token": token})
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is True

    def test_valid_token_returns_session_id(self, client: TestClient):
        """有效令牌应返回关联的 session_id"""
        token = _create_token(session_id="S-TEST-001")
        resp = client.post("/api/session/verify-token", json={"token": token})
        data = resp.json()
        assert data["session_id"] == "S-TEST-001"

    def test_valid_token_returns_patient_id(self, client: TestClient):
        """有效令牌应返回关联的 patient_id"""
        token = _create_token(patient_id="P-TEST-001")
        resp = client.post("/api/session/verify-token", json={"token": token})
        data = resp.json()
        assert data["patient_id"] == "P-TEST-001"

    def test_token_marked_as_used_after_verify(self, client: TestClient):
        """令牌核验成功后应被标记为已使用（一次性）"""
        token = _create_token()
        client.post("/api/session/verify-token", json={"token": token})
        assert _SCAN_TOKEN_STORE[token]["used"] is True


class TestScanTokenFailure:
    """扫码令牌核验失败场景"""

    def test_nonexistent_token_returns_valid_false(self, client: TestClient):
        """不存在的令牌应返回 valid=false"""
        resp = client.post("/api/session/verify-token", json={"token": "z" * 32})
        data = resp.json()
        assert data["valid"] is False
        assert "不存在" in data["message"]

    def test_already_used_token_returns_valid_false(self, client: TestClient):
        """已使用的令牌应返回 valid=false"""
        token = _create_token(used=True)
        resp = client.post("/api/session/verify-token", json={"token": token})
        data = resp.json()
        assert data["valid"] is False
        assert "已被使用" in data["message"]

    def test_expired_token_returns_valid_false(self, client: TestClient):
        """过期的令牌应返回 valid=false"""
        token = _create_token(expires_minutes=-1)  # 已过期
        resp = client.post("/api/session/verify-token", json={"token": token})
        data = resp.json()
        assert data["valid"] is False
        assert "过期" in data["message"]

    def test_token_one_time_use(self, client: TestClient):
        """同一令牌第二次核验应失败"""
        token = _create_token()
        # 第一次成功
        resp1 = client.post("/api/session/verify-token", json={"token": token})
        assert resp1.json()["valid"] is True
        # 第二次失败
        resp2 = client.post("/api/session/verify-token", json={"token": token})
        assert resp2.json()["valid"] is False


class TestScanTokenValidation:
    """扫码令牌请求校验"""

    def test_missing_token_returns_422(self, client: TestClient):
        """缺失 token 字段应返回 422"""
        resp = client.post("/api/session/verify-token", json={})
        assert resp.status_code == 422

    def test_token_too_short_returns_422(self, client: TestClient):
        """token 长度不足 24 应返回 422"""
        resp = client.post("/api/session/verify-token", json={"token": "short"})
        assert resp.status_code == 422

    def test_token_min_length_boundary(self, client: TestClient):
        """token 长度恰好 24 应通过校验"""
        token = "a" * 24
        _create_token(token=token)
        resp = client.post("/api/session/verify-token", json={"token": token})
        # 长度通过，进入业务逻辑，返回 valid=false（因为新写入的令牌有效）
        assert resp.status_code == 200
        assert resp.json()["valid"] is True

    def test_extra_field_rejected(self, client: TestClient):
        """多余字段应被拒绝"""
        token = _create_token()
        resp = client.post(
            "/api/session/verify-token",
            json={"token": token, "extra": "field"},
        )
        assert resp.status_code == 422
