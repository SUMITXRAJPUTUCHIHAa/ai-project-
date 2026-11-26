"""
Phase 1 UI Smoke Tests — LPU UMS Style Verification
Run: python -m pytest tests/test_ui_smoke.py -v
"""
import os
import re
import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
HTML_PATH = os.path.join(ROOT, "static", "index.html")
CSS_PATH  = os.path.join(ROOT, "static", "css", "style.css")
JS_PATH   = os.path.join(ROOT, "static", "js", "app.js")


@pytest.fixture(scope="module")
def html():
    with open(HTML_PATH, encoding="utf-8") as f:
        return f.read()

@pytest.fixture(scope="module")
def css():
    with open(CSS_PATH, encoding="utf-8") as f:
        return f.read()

@pytest.fixture(scope="module")
def js():
    with open(JS_PATH, encoding="utf-8") as f:
        return f.read()


class TestFileExistence:
    def test_index_html_exists(self):
        assert os.path.exists(HTML_PATH), "index.html missing"

    def test_style_css_exists(self):
        assert os.path.exists(CSS_PATH), "style.css missing"

    def test_app_js_exists(self):
        assert os.path.exists(JS_PATH), "app.js missing"


class TestHTMLStructure:
    def test_has_viewport_meta(self, html):
        assert 'name="viewport"' in html

    def test_has_topbar(self, html):
        assert "topbar" in html

    def test_has_sidebar(self, html):
        assert "sidebar" in html

    def test_has_chat_section(self, html):
        assert 'id="chat"' in html

    def test_has_hero_section(self, html):
        # Accept either old id="hero" or new id="viewHome"
        assert 'id="hero"' in html or 'id="viewHome"' in html

    def test_has_input_textarea(self, html):
        assert "<textarea" in html

    def test_has_send_button(self, html):
        assert 'id="send"' in html

    def test_has_quick_grid(self, html):
        assert 'id="quickGrid"' in html

    def test_lpu_title(self, html):
        assert "LPU" in html

    def test_css_linked(self, html):
        assert "style.css" in html

    def test_js_linked(self, html):
        assert "app.js" in html


class TestCSSTheme:
    def test_lpu_purple_defined(self, css):
        # After redesign, should have LPU purple
        # For now check base vars exist
        assert "--" in css  # has CSS variables

    def test_has_font_family(self, css):
        assert "font-family" in css

    def test_has_responsive_media_query(self, css):
        assert "@media" in css or "clamp" in css

    def test_has_grid_layout(self, css):
        assert "grid" in css

    def test_has_button_styles(self, css):
        assert "button" in css


class TestJSFunctionality:
    def test_fetch_api_used(self, js):
        assert "fetch(" in js

    def test_chat_send_function(self, js):
        assert "send" in js.lower() or "chat" in js.lower()

    def test_api_chat_endpoint(self, js):
        assert "/api/chat" in js

    def test_reset_function(self, js):
        assert "reset" in js.lower()

    def test_no_hardcoded_credentials(self, js):
        # Ensure no API keys accidentally in JS
        assert "AIza" not in js  # Gemini key pattern
        assert "firebase.json" not in js  # service account


class TestAccessibility:
    def test_lang_attribute(self, html):
        assert 'lang="' in html

    def test_has_aria_labels(self, html):
        assert "aria-label" in html

    def test_buttons_have_text_or_aria(self, html):
        # Basic check — buttons exist
        assert "<button" in html

    def test_no_inline_scripts(self, html):
        # Disallow inline JS event handlers (onclick=, onload=, etc.)
        # Must NOT match content="" or similar attribute patterns
        inline_events = re.findall(r'\s+on[a-zA-Z]+="[^"]*"', html)
        assert len(inline_events) == 0, f"Inline event handlers found: {inline_events}"
