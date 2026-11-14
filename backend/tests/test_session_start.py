# -*- coding: utf-8 -*-
"""
后端单元测试 - 会话启动接口 POST /api/session/start

遵循 AGENT.md 8.1 领域契约。

测试目标：
    1. consent_given=true 时成功创建会话，返回 201
    2. consent_given=false 时返回 400 CONSENT_REQUIRED
    3. 缺失必填字段返回 422
    4. department 枚举值校验
    5. 响应字段符合 SessionStartResponse 契约
    6. 会话有效期为 72 小时
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

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


class TestSessionStartSuccess:
    """会话启动成功场景"""

    def test_start_session_returns_201(self, client: TestClient):
        """consent_given=true 应返回 201"""
        payload = {
            "patient_id": "T2026080002",
            "department": "老年医学科",
            "consent_given": True,
        }
        resp = client.post("/api/session/start", json=payload)
        assert resp.status_code == 201

    def test_start_session_returns_session_id(self, client: TestClient):
        """响应应包含有效的 UUID session_id"""
        payload = {
            "patient_id": "T2026080002",
            "department": "老年医学科",
            "consent_given": True,
        }
        resp = client.post("/api/session/start", json=payload)
        data = resp.json()
        assert "session_id" in data
        # 验证为 UUID 格式
        uuid.UUID(data["session_id"])

    def test_start_session_echoes_fields(self, client: TestClient):
        """响应应原样回传 patient_id、department、consent_given"""
        payload = {
            "patient_id": "T2026080002",
            "department": "康复科",
            "consent_given": True,
        }
        resp = client.post("/api/session/start", json=payload)
        data = resp.json()
        assert data["patient_id"] == "T2026080002"
        assert data["department"] == "康复科"
        assert data["consent_given"] is True

    def test_start_session_status_active(self, client: TestClient):
        """新会话状态应为 active"""
        payload = {
            "patient_id": "T2026080002",
            "department": "老年医学科",
            "consent_given": True,
        }
        resp = client.post("/api/session/start", json=payload)
        data = resp.json()
        assert data["status"] == "active"

    def test_start_session_ttl_72_hours(self, client: TestClient):
        """会话过期时间应为启动时间 + 72 小时"""
        payload = {
            "patient_id": "T2026080002",
            "department": "老年医学科",
            "consent_given": True,
        }
        before = datetime.now(timezone.utc)
        resp = client.post("/api/session/start", json=payload)
        after = datetime.now(timezone.utc)

        data = resp.json()
        started = datetime.fromisoformat(data["started_at"])
        expires = datetime.fromisoformat(data["expires_at"])

        # 过期时间 - 启动时间 应约为 72 小时
        delta = expires - started
        assert timedelta(hours=71, minutes=59) < delta < timedelta(hours=72, minutes=1)

        # started_at 应在请求前后时间范围内
        assert before <= started <= after

    def test_start_session_with_callback_url(self, client: TestClient):
        """带 callback_url 的请求应原样回传"""
        payload = {
            "patient_id": "T2026080002",
            "department": "老年医学科",
            "consent_given": True,
            "callback_url": "https://hospital.example.com/api/callback",
        }
        resp = client.post("/api/session/start", json=payload)
        data = resp.json()
        assert data["callback_url"] == "https://hospital.example.com/api/callback"

    def test_start_session_without_callback_url(self, client: TestClient):
        """不带 callback_url 时响应应为 null"""
        payload = {
            "patient_id": "T2026080002",
            "department": "老年医学科",
            "consent_given": True,
        }
        resp = client.post("/api/session/start", json=payload)
        data = resp.json()
        assert data["callback_url"] is None

    def test_start_session_stored_in_memory(self, client: TestClient):
        """创建的会话应存入内存存储"""
        payload = {
            "patient_id": "T2026080002",
            "department": "老年医学科",
            "consent_given": True,
        }
        resp = client.post("/api/session/start", json=payload)
        session_id = resp.json()["session_id"]
        assert session_id in _SESSION_STORE
        assert _SESSION_STORE[session_id]["patient_id"] == "T2026080002"


class TestSessionStartValidation:
    """会话启动校验失败场景"""

    def test_consent_required_returns_400(self, client: TestClient):
        """consent_given=false 应返回 400 CONSENT_REQUIRED"""
        payload = {
            "patient_id": "T2026080002",
            "department": "老年医学科",
            "consent_given": False,
        }
        resp = client.post("/api/session/start", json=payload)
        assert resp.status_code == 400
        data = resp.json()
        assert data["code"] == "CONSENT_REQUIRED"

    def test_missing_patient_id_returns_422(self, client: TestClient):
        """缺失 patient_id 应返回 422"""
        payload = {
            "department": "老年医学科",
            "consent_given": True,
        }
        resp = client.post("/api/session/start", json=payload)
        assert resp.status_code == 422

    def test_missing_department_returns_422(self, client: TestClient):
        """缺失 department 应返回 422"""
        payload = {
            "patient_id": "T2026080002",
            "consent_given": True,
        }
        resp = client.post("/api/session/start", json=payload)
        assert resp.status_code == 422

    def test_missing_consent_returns_422(self, client: TestClient):
        """缺失 consent_given 应返回 422"""
        payload = {
            "patient_id": "T2026080002",
            "department": "老年医学科",
        }
        resp = client.post("/api/session/start", json=payload)
        assert resp.status_code == 422

    def test_invalid_department_returns_422(self, client: TestClient):
        """department 不在枚举范围内应返回 422"""
        payload = {
            "patient_id": "T2026080002",
            "department": "心内科",
            "consent_given": True,
        }
        resp = client.post("/api/session/start", json=payload)
        assert resp.status_code == 422

    def test_extra_field_rejected(self, client: TestClient):
        """多余字段应被拒绝（extra=forbid）"""
        payload = {
            "patient_id": "T2026080002",
            "department": "老年医学科",
            "consent_given": True,
            "extra_field": "should_be_rejected",
        }
        resp = client.post("/api/session/start", json=payload)
        assert resp.status_code == 422

    def test_empty_patient_id_returns_422(self, client: TestClient):
        """空 patient_id 应返回 422（min_length=1）"""
        payload = {
            "patient_id": "",
            "department": "老年医学科",
            "consent_given": True,
        }
        resp = client.post("/api/session/start", json=payload)
        assert resp.status_code == 422
