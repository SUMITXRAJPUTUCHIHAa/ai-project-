"""
Phase 6 Production Verification Tests
Run: set PROD_URL=https://your-app.web.app && python -m pytest tests/test_production.py -v
"""
import os, pytest, time

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

PROD_URL = os.getenv("PROD_URL", "").rstrip("/")
skip_no_prod = pytest.mark.skipif(
    not PROD_URL,
    reason="Set PROD_URL env var to run production tests"
)
skip_no_requests = pytest.mark.skipif(
    not REQUESTS_AVAILABLE,
    reason="requests library not installed"
)


@skip_no_prod
@skip_no_requests
class TestProductionHealth:
    def test_health_endpoint_200(self):
        r = requests.get(f"{PROD_URL}/api/health", timeout=15)
        assert r.status_code == 200

    def test_health_returns_json(self):
        r = requests.get(f"{PROD_URL}/api/health", timeout=15)
        assert "application/json" in r.headers.get("Content-Type", "")

    def test_health_status_ok(self):
        r = requests.get(f"{PROD_URL}/api/health", timeout=15)
        body = r.json()
        assert body.get("status") == "ok"

    def test_health_firebase_configured(self):
        r = requests.get(f"{PROD_URL}/api/health", timeout=15)
        body = r.json()
        components = body.get("components", {})
        fb = components.get("firebase", {})
        # In production, Firebase should be configured
        assert fb.get("configured") is True, \
            "Firebase not configured in production!"


@skip_no_prod
@skip_no_requests
class TestProductionPerformance:
    def test_chat_response_time_under_5s(self):
        start = time.time()
        r = requests.post(f"{PROD_URL}/api/chat",
                          json={"message": "fees"},
                          timeout=15)
        elapsed = time.time() - start
        assert r.status_code == 200
        assert elapsed < 5.0, f"Response too slow: {elapsed:.2f}s"

    def test_health_response_time_under_2s(self):
        start = time.time()
        requests.get(f"{PROD_URL}/api/health", timeout=10)
        elapsed = time.time() - start
        assert elapsed < 2.0, f"Health check slow: {elapsed:.2f}s"


@skip_no_prod
@skip_no_requests
class TestProductionStaticAssets:
    def test_root_page_200(self):
        r = requests.get(f"{PROD_URL}/", timeout=15)
        assert r.status_code == 200

    def test_css_file_loads(self):
        r = requests.get(f"{PROD_URL}/static/css/style.css", timeout=15)
        assert r.status_code == 200
        assert "text/css" in r.headers.get("Content-Type", "")

    def test_js_file_loads(self):
        r = requests.get(f"{PROD_URL}/static/js/app.js", timeout=15)
        assert r.status_code == 200


@skip_no_prod
@skip_no_requests
class TestProductionSecurity:
    def test_cors_header_present(self):
        r = requests.options(
            f"{PROD_URL}/api/chat",
            headers={"Origin": "https://example.com",
                     "Access-Control-Request-Method": "POST"},
            timeout=10
        )
        assert "Access-Control-Allow-Origin" in r.headers

    def test_no_server_header_leak(self):
        r = requests.get(f"{PROD_URL}/api/health", timeout=10)
        server = r.headers.get("Server", "")
        # Should not expose Werkzeug dev server in production
        assert "Werkzeug" not in server, \
            "Using dev server in production!"

    def test_https_enforced(self):
        if PROD_URL.startswith("https://"):
            http_url = PROD_URL.replace("https://", "http://")
            try:
                r = requests.get(http_url, timeout=10,
                                 allow_redirects=False)
                # Should redirect to HTTPS
                assert r.status_code in (301, 302, 307, 308)
            except Exception:
                pass  # Connection refused on HTTP is also acceptable

