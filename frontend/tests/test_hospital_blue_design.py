# -*- coding: utf-8 -*-
"""
医院蓝多设备适配设计系统 — 单元测试

测试目标：
    1. 设计令牌（颜色变量）符合医院蓝规范
    2. 移除 Google Fonts 外链
    3. 自助机触控目标 ≥ 60px
    4. 响应式断点存在且完整
    5. 关键 CSS 类已定义（cga-screen / cga-field / cga-interaction / cga-touch-link）

运行方式：
    cd c:\\大学\\网络编程技术
    py -m pytest frontend/tests/test_hospital_blue_design.py -v
"""

import re
from pathlib import Path

import pytest

# 设计系统 CSS 文件路径
CSS_PATH = Path(__file__).resolve().parent.parent / "hospital-blue.css"


@pytest.fixture(scope="module")
def css_text() -> str:
    """读取 CSS 文件内容"""
    assert CSS_PATH.exists(), f"设计系统 CSS 文件不存在: {CSS_PATH}"
    return CSS_PATH.read_text(encoding="utf-8")


# ============================================================================
# 1. 颜色令牌验证
# ============================================================================

class TestColorTokens:
    """验证医院蓝设计令牌"""

    def test_primary_color_is_hospital_blue(self, css_text: str):
        """主色必须为医院蓝 #1856a3"""
        assert "--primary: #1856a3" in css_text, "主色应为医院蓝 #1856a3"

    def test_primary_hover_color(self, css_text: str):
        """主色悬停态应为更深的蓝色 #123c78"""
        assert "--primary-hover: #123c78" in css_text

    def test_primary_tint_color(self, css_text: str):
        """主色浅色背景应为 #deebfd"""
        assert "--primary-tint: #deebfd" in css_text

    def test_background_color(self, css_text: str):
        """背景色应为 #f3f7fc"""
        assert "--background: #f3f7fc" in css_text

    def test_foreground_color(self, css_text: str):
        """前景文字色应为 #142843"""
        assert "--foreground: #142843" in css_text

    def test_all_required_colors_defined(self, css_text: str):
        """所有必需颜色变量均已定义"""
        required = [
            "--background", "--surface", "--surface-secondary",
            "--foreground", "--foreground-muted", "--foreground-placeholder",
            "--border", "--field-border",
            "--primary", "--primary-hover", "--primary-tint",
            "--success", "--warning", "--danger", "--info",
        ]
        for var in required:
            assert f"{var}:" in css_text, f"缺少颜色变量: {var}"


# ============================================================================
# 2. 字体与外链验证
# ============================================================================

class TestFontsAndExternalLinks:
    """验证字体使用系统中文字体，无外部字体依赖"""

    def test_no_google_fonts_import(self, css_text: str):
        """不得引用 Google Fonts 外链"""
        assert "fonts.googleapis.com" not in css_text, "禁止使用 Google Fonts 外链"
        assert "@import url" not in css_text, "禁止使用 @import 外链字体"

    def test_uses_system_chinese_fonts(self, css_text: str):
        """应使用系统中文字体（PingFang SC / Microsoft YaHei / Noto Sans CJK SC）"""
        chinese_fonts = ["PingFang SC", "Microsoft YaHei", "Noto Sans CJK SC"]
        assert any(f in css_text for f in chinese_fonts), "应使用系统中文字体"

    def test_font_sans_defined(self, css_text: str):
        """--font-sans 变量应定义"""
        assert "--font-sans:" in css_text

    def test_font_serif_defined(self, css_text: str):
        """--font-serif 变量应定义"""
        assert "--font-serif:" in css_text


# ============================================================================
# 3. 自助机触控目标验证
# ============================================================================

class TestKioskTouchTargets:
    """验证自助机模式下触控目标 ≥ 60px"""

    def test_kiosk_media_query_exists(self, css_text: str):
        """应存在自助机媒体查询：min-width:1000px 且 pointer:coarse"""
        assert "@media (min-width: 1000px) and (pointer: coarse)" in css_text

    def test_kiosk_touch_target_min_height(self, css_text: str):
        """自助机模式下关键触控目标最小高度应为 3.75rem (60px)"""
        assert "min-height: 3.75rem" in css_text, "自助机触控目标应 ≥ 60px (3.75rem)"

    def test_kiosk_font_size_enlarged(self, css_text: str):
        """自助机模式下字号应放大至 1.125rem (18px)"""
        assert "font-size: 1.125rem" in css_text


# ============================================================================
# 4. 响应式断点验证
# ============================================================================

class TestResponsiveBreakpoints:
    """验证响应式断点完整"""

    def test_tablet_breakpoint(self, css_text: str):
        """平板断点 ≥ 640px 应存在"""
        assert "@media (min-width: 640px)" in css_text

    def test_desktop_breakpoint(self, css_text: str):
        """电脑断点 ≥ 1024px 应存在"""
        assert "@media (min-width: 1024px)" in css_text

    def test_mobile_responsive_table(self, css_text: str):
        """窄屏表格响应式应存在（max-width:767px）"""
        assert "@media (max-width: 767px)" in css_text


# ============================================================================
# 5. 关键 CSS 类验证
# ============================================================================

class TestCoreCssClasses:
    """验证核心设计系统类已定义"""

    @pytest.mark.parametrize("class_name", [
        "cga-screen", "cga-field", "cga-interaction",
        "cga-touch-link", "cga-btn", "cga-card",
        "cga-alert", "cga-topbar", "cga-table",
    ])
    def test_core_class_defined(self, css_text: str, class_name: str):
        f"核心类 .{class_name} 应已定义"
        # 匹配 .class-name { 或 .class-name, 或 .class-name:
        pattern = rf"\.{re.escape(class_name)}[\s,:{{]"
        assert re.search(pattern, css_text), f"缺少核心 CSS 类: .{class_name}"

    def test_cga_field_has_min_height(self, css_text: str):
        """输入框应有最小高度 3rem (48px)"""
        assert ".cga-field" in css_text
        assert "min-height: 3rem" in css_text

    def test_focus_visible_uses_primary(self, css_text: str):
        """焦点样式应使用主色"""
        assert "outline: 2px solid var(--primary)" in css_text


# ============================================================================
# 6. 集成验证：CSS 文件可被浏览器解析（基础语法检查）
# ============================================================================

class TestCssSyntax:
    """CSS 基础语法完整性检查"""

    def test_braces_balanced(self, css_text: str):
        """大括号应成对出现"""
        open_count = css_text.count("{")
        close_count = css_text.count("}")
        assert open_count == close_count, (
            f"大括号不匹配：{{ {open_count} 个，}} {close_count} 个"
        )

    def test_no_unterminated_strings(self, css_text: str):
        """不应有未闭合的字符串（简单检查单双引号配对）"""
        # 移除注释后检查
        clean = re.sub(r"/\*.*?\*/", "", css_text, flags=re.DOTALL)
        single_quotes = clean.count("'")
        double_quotes = clean.count('"')
        assert single_quotes % 2 == 0, f"单引号未配对: {single_quotes}"
        assert double_quotes % 2 == 0, f"双引号未配对: {double_quotes}"

    def test_file_not_empty(self, css_text: str):
        """CSS 文件不应为空"""
        assert len(css_text.strip()) > 1000, "CSS 文件内容过短"
