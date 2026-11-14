# -*- coding: utf-8 -*-
"""
前端集成测试 - patient-verify.html 患者身份核验页

对接医院蓝多设备适配后端的集成测试。

测试目标：
    1. API_BASE 常量正确定义，可通过 window.__API_BASE__ 覆盖
    2. 请求超时 REQUEST_TIMEOUT_MS = 5000ms
    3. 控制台日志使用 [LANTAO] 前缀
    4. 扫码令牌表单存在，token minlength=24
    5. 联调演示身份（开发环境）功能存在
    6. 调用 POST /api/session/start 和 POST /api/session/verify-token
    7. 错误处理函数存在（showError / hideError / showSuccess）
    8. 页面使用医院蓝设计系统核心类
"""

import re
from pathlib import Path

import pytest

# 页面文件路径
HTML_PATH = Path(__file__).resolve().parent.parent / "patient-verify.html"


@pytest.fixture(scope="module")
def html_text() -> str:
    """读取 HTML 文件内容"""
    assert HTML_PATH.exists(), f"页面文件不存在: {HTML_PATH}"
    return HTML_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def script_text(html_text: str) -> str:
    """提取 <script> 标签内的 JavaScript 代码"""
    match = re.search(r"<script>(.*?)</script>", html_text, re.DOTALL)
    assert match, "未找到 <script> 标签"
    return match.group(1)


# ============================================================================
# 1. API 配置验证
# ============================================================================

class TestApiConfig:
    """验证 API 配置常量"""

    def test_api_base_defined(self, script_text: str):
        """API_BASE 常量应定义"""
        assert "API_BASE" in script_text, "应定义 API_BASE 常量"

    def test_api_base_default_port(self, script_text: str):
        """API_BASE 默认端口应为 8766（与后端对齐）"""
        assert "8766" in script_text, "API_BASE 默认应指向 8766 端口"

    def test_api_base_overrideable(self, script_text: str):
        """API_BASE 应支持通过 window.__API_BASE__ 覆盖"""
        assert "window.__API_BASE__" in script_text, "应支持 window.__API_BASE__ 覆盖"

    def test_request_timeout_5000ms(self, script_text: str):
        """请求超时应为 5000ms"""
        assert "REQUEST_TIMEOUT_MS" in script_text
        assert "5000" in script_text, "请求超时应为 5000ms"

    def test_timeout_abort_mechanism(self, script_text: str):
        """应使用 AbortController 实现超时"""
        assert "AbortController" in script_text, "应使用 AbortController 实现请求超时"
        assert "controller.abort()" in script_text

    def test_abort_error_message(self, script_text: str):
        """超时时应提示检查后端服务"""
        assert "网络请求超时" in script_text, "超时应有友好提示"


# ============================================================================
# 2. 日志规范验证
# ============================================================================

class TestLoggingConvention:
    """验证 [LANTAO] 日志前缀规范"""

    def test_lantao_log_prefix_used(self, script_text: str):
        """控制台日志应使用 [LANTAO] 前缀"""
        assert "[LANTAO]" in script_text, "应使用 [LANTAO] 日志前缀"

    def test_session_creation_log(self, script_text: str):
        """会话创建成功应有日志"""
        assert "会话已创建" in script_text

    def test_scan_token_log(self, script_text: str):
        """扫码令牌核验成功应有日志"""
        assert "扫码令牌核验成功" in script_text


# ============================================================================
# 3. 扫码令牌功能验证
# ============================================================================

class TestScanTokenFeature:
    """验证扫码令牌核验功能"""

    def test_scan_token_form_exists(self, html_text: str):
        """页面应包含扫码令牌表单"""
        assert "scanToken" in html_text, "应包含扫码令牌输入框"
        assert "scanForm" in html_text

    def test_scan_token_minlength_24(self, html_text: str):
        """扫码令牌输入框 minlength 应为 24"""
        assert 'minlength="24"' in html_text, "扫码令牌 minlength 应为 24"

    def test_scan_token_verify_api_called(self, script_text: str):
        """应调用 /api/session/verify-token 接口"""
        assert "/api/session/verify-token" in script_text

    def test_scan_token_toggle_button(self, html_text: str):
        """应有扫码令牌展开/收起按钮"""
        assert "scanToggle" in html_text
        assert "使用扫码令牌" in html_text

    def test_scan_token_one_time_hint(self, html_text: str):
        """应提示令牌过期后重新生成"""
        assert "重新生成" in html_text

    def test_scan_token_length_validation(self, script_text: str):
        """应校验令牌长度不足 24"""
        assert "token.length < 24" in script_text


# ============================================================================
# 4. 会话启动接口验证
# ============================================================================

class TestSessionStartApi:
    """验证会话启动接口调用"""

    def test_session_start_api_called(self, script_text: str):
        """应调用 /api/session/start 接口"""
        assert "/api/session/start" in script_text

    def test_session_start_payload(self, script_text: str):
        """请求 payload 应包含 patient_id、department、consent_given"""
        assert "patient_id" in script_text
        assert "department" in script_text
        assert "consent_given" in script_text
        assert "老年医学科" in script_text

    def test_department_default(self, script_text: str):
        """默认科室应为老年医学科"""
        assert "'老年医学科'" in script_text or '"老年医学科"' in script_text


# ============================================================================
# 5. 演示账号与联调身份验证
# ============================================================================

class TestDemoAccounts:
    """验证演示账号与联调演示身份"""

    def test_mock_demo_accounts_exist(self, script_text: str):
        """应存在 mock 模式演示账号"""
        assert "DEMO_ACCOUNTS" in script_text
        assert "T2026080002" in script_text  # 传统问卷任务
        assert "T2026080001" in script_text  # AI 对话任务

    def test_demo_buttons_exist(self, html_text: str):
        """应有传统问卷任务和 AI 对话任务按钮"""
        assert "传统问卷任务" in html_text
        assert "AI 对话任务" in html_text

    def test_dev_demo_accounts_exist(self, script_text: str):
        """应存在联调演示身份（开发环境）"""
        assert "DEV_DEMO_ACCOUNTS" in script_text

    def test_dev_mode_detection(self, script_text: str):
        """应检测开发环境（localhost / 127.0.0.1）"""
        assert "IS_DEV" in script_text
        assert "localhost" in script_text or "127.0.0.1" in script_text


# ============================================================================
# 6. 错误处理验证
# ============================================================================

class TestErrorHandling:
    """验证错误处理机制"""

    def test_show_error_function(self, script_text: str):
        """应定义 showError 函数"""
        assert "function showError" in script_text or "showError =" in script_text

    def test_hide_error_function(self, script_text: str):
        """应定义 hideError 函数"""
        assert "function hideError" in script_text or "hideError =" in script_text

    def test_show_success_function(self, script_text: str):
        """应定义 showSuccess 函数"""
        assert "function showSuccess" in script_text or "showSuccess =" in script_text

    def test_error_alert_class_used(self, html_text: str):
        """应使用 cga-alert--error 类"""
        assert "cga-alert--error" in html_text

    def test_success_alert_class_used(self, script_text: str):
        """应使用 cga-alert--success 类"""
        assert "cga-alert--success" in script_text

    def test_response_error_parsing(self, script_text: str):
        """应解析后端统一错误结构的 message 字段"""
        assert "data?.message" in script_text or "data.message" in script_text


# ============================================================================
# 7. 设计系统类使用验证
# ============================================================================

class TestDesignSystemUsage:
    """验证页面使用医院蓝设计系统核心类"""

    def test_uses_cga_screen(self, html_text: str):
        """应使用 cga-screen 顶层容器"""
        assert "cga-screen" in html_text

    def test_uses_cga_field(self, html_text: str):
        """输入框应使用 cga-field 类"""
        assert "cga-field" in html_text

    def test_uses_cga_btn(self, html_text: str):
        """按钮应使用 cga-btn 类"""
        assert "cga-btn" in html_text

    def test_uses_cga_card(self, html_text: str):
        """应使用 cga-card 卡片类"""
        assert "cga-card" in html_text

    def test_uses_cga_touch_link(self, html_text: str):
        """应使用 cga-touch-link 触控链接类"""
        assert "cga-touch-link" in html_text

    def test_links_hospital_blue_css(self, html_text: str):
        """应引入 hospital-blue.css"""
        assert "hospital-blue.css" in html_text


# ============================================================================
# 8. HTML 结构完整性
# ============================================================================

class TestHtmlStructure:
    """验证 HTML 结构完整性"""

    def test_has_doctype(self, html_text: str):
        """应有 DOCTYPE 声明"""
        assert html_text.strip().startswith("<!DOCTYPE html>")

    def test_has_charset_utf8(self, html_text: str):
        """应设置 UTF-8 编码"""
        assert 'charset="UTF-8"' in html_text

    def test_has_viewport(self, html_text: str):
        """应设置 viewport（响应式）"""
        assert "viewport" in html_text

    def test_has_form_with_id(self, html_text: str):
        """应有主核验表单"""
        assert 'id="verifyForm"' in html_text

    def test_has_submit_button(self, html_text: str):
        """应有提交按钮"""
        assert 'type="submit"' in html_text

    def test_has_back_link(self, html_text: str):
        """应有返回首页链接"""
        assert "index.html" in html_text

    def test_html_lang_zh_cn(self, html_text: str):
        """lang 属性应为 zh-CN"""
        assert 'lang="zh-CN"' in html_text
