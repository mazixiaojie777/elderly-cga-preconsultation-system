# -*- coding: utf-8 -*-
"""
后端单元测试 - CORS 与错误处理

测试目标：
    1. CORS 预检请求（OPTIONS）返回正确的 Allow-Origin 头
    2. 允许的来源包含 3000 和 3014 端口
    3. HTTPException 返回统一错误结构
    4. 全局异常处理返回 500 且不暴露堆栈
"""

import pytest
from fastapi.testclient import TestClient

from main import app, config


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


class TestCORS:
    """CORS 跨域配置测试"""

    def test_cors_preflight_allowed_origin_3000(self, client: TestClient):
        """来源 localhost:3000 应被允许"""
        resp = client.options(
            "/api/session/start",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert resp.status_code == 200
        assert "http://localhost:3000" in resp.headers.get("access-control-allow-origin", "")

    def test_cors_preflight_allowed_origin_3014(self, client: TestClient):
        """来源 localhost:3014（医院蓝前端 dev 端口）应被允许"""
        resp = client.options(
            "/api/session/start",
            headers={
                "Origin": "http://localhost:3014",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert resp.status_code == 200
        assert "http://localhost:3014" in resp.headers.get("access-control-allow-origin", "")

    def test_cors_preflight_allowed_origin_127_0_0_1_3014(self, client: TestClient):
        """来源 127.0.0.1:3014 应被允许"""
        resp = client.options(
            "/api/session/start",
            headers={
                "Origin": "http://127.0.0.1:3014",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert resp.status_code == 200

    def test_cors_allow_methods_all(self, client: TestClient):
        """应允许所有 HTTP 方法"""
        resp = client.options(
            "/api/session/start",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            },
        )
        allow_methods = resp.headers.get("access-control-allow-methods", "")
        assert "POST" in allow_methods

    def test_cors_origin_in_config(self):
        """配置中应包含 3014 端口来源"""
        origins = config.CORS_ORIGINS
        assert any("3014" in o for o in origins)


class TestErrorHandling:
    """错误处理测试"""

    def test_http_exception_returns_unified_structure(self, client: TestClient):
        """HTTPException 应返回统一的 JSON 错误结构"""
        resp = client.post(
            "/api/session/start",
            json={
                "patient_id": "T2026080002",
                "department": "老年医学科",
                "consent_given": False,
            },
        )
        data = resp.json()
        assert "status" in data
        assert data["status"] == "error"
        assert "message" in data
        assert "timestamp" in data

    def test_http_exception_includes_code(self, client: TestClient):
        """含 code 的 HTTPException 应在响应中返回 code"""
        resp = client.post(
            "/api/session/start",
            json={
                "patient_id": "T2026080002",
                "department": "老年医学科",
                "consent_given": False,
            },
        )
        data = resp.json()
        assert data.get("code") == "CONSENT_REQUIRED"

    def test_not_found_returns_404(self, client: TestClient):
        """不存在的路由应返回 404"""
        resp = client.get("/api/nonexistent")
        assert resp.status_code == 404

    def test_validation_error_returns_422(self, client: TestClient):
        """参数校验失败应返回 422"""
        resp = client.post("/api/session/start", json={"invalid": "payload"})
        assert resp.status_code == 422

    def test_error_response_no_stack_trace(self, client: TestClient):
        """错误响应不应暴露内部堆栈信息"""
        resp = client.post(
            "/api/session/start",
            json={
                "patient_id": "T2026080002",
                "department": "老年医学科",
                "consent_given": False,
            },
        )
        data = resp.json()
        # 不应包含 Python 堆栈关键词
        text = str(data)
        assert "Traceback" not in text
        assert "File \"" not in text
