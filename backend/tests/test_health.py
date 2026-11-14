# -*- coding: utf-8 -*-
"""
后端单元测试 - 健康检查接口

测试目标：
    1. GET /health 返回 200 且 status=ok
    2. timestamp 字段为 ISO 8601 格式
    3. 响应结构符合 HealthResponse 模型
"""

import re
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    """创建测试客户端"""
    return TestClient(app)


class TestHealthEndpoint:
    """健康检查接口测试"""

    def test_health_returns_200(self, client: TestClient):
        """GET /health 应返回 200"""
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_status_ok(self, client: TestClient):
        """响应 status 字段应为 ok"""
        resp = client.get("/health")
        data = resp.json()
        assert data["status"] == "ok"

    def test_health_has_timestamp(self, client: TestClient):
        """响应应包含 timestamp 字段"""
        resp = client.get("/health")
        data = resp.json()
        assert "timestamp" in data
        assert isinstance(data["timestamp"], str)
        assert len(data["timestamp"]) > 0

    def test_health_timestamp_is_iso8601(self, client: TestClient):
        """timestamp 应为 ISO 8601 格式"""
        resp = client.get("/health")
        data = resp.json()
        # 尝试解析为 ISO 8601 时间
        try:
            datetime.fromisoformat(data["timestamp"])
        except ValueError:
            pytest.fail(f"timestamp 不是有效的 ISO 8601 格式: {data['timestamp']}")

    def test_health_no_extra_fields(self, client: TestClient):
        """响应不应包含多余字段（严格契约）"""
        resp = client.get("/health")
        data = resp.json()
        assert set(data.keys()) == {"status", "timestamp"}
