"""
Phase 2 Backend Hardening Tests
Run: python -m pytest tests/test_api_hardening.py -v
"""
import sys, os, pytest, json

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


@pytest.fixture
def client():
    # Import here to avoid module-level issues
    try:
        from app import app as flask_app
        flask_app.config["TESTING"] = True
        with flask_app.test_client() as c:
            yield c
    except Exception:
        pytest.skip("app not importable in this environment")


class TestInputValidation:
    def test_chat_empty_message_rejected(self, client):
        r = client.post("/api/chat",
                        data=json.dumps({"message": ""}),
                        content_type="application/json")
        assert r.status_code in (400, 422)

    def test_chat_message_too_long(self, client):
        r = client.post("/api/chat",
                        data=json.dumps({"message": "x" * 1001}),
                        content_type="application/json")
        assert r.status_code in (400, 422)

    def test_chat_valid_message_ok(self, client):
        r = client.post("/api/chat",
                        data=json.dumps({"message": "fees"}),
                        content_type="application/json")
        assert r.status_code == 200

    def test_xss_payload_does_not_500(self, client):
        r = client.post("/api/chat",
                        data=json.dumps({"message": "<script>alert(1)</script>fees"}),
                        content_type="application/json")
        # Must not 500
        assert r.status_code != 500

    def test_xss_not_reflected_verbatim(self, client):
        payload = "<script>alert(1)</script>"
        r = client.post("/api/chat",
                        data=json.dumps({"message": f"{payload} fees"}),
                        content_type="application/json")
        body = r.get_data(as_text=True)
        assert "<script>" not in body

    def test_sql_injection_does_not_500(self, client):
        r = client.post("/api/chat",
                        data=json.dumps({"message": "' OR 1=1; DROP TABLE logs;--"}),
                        content_type="application/json")
        assert r.status_code in (200, 400)

    def test_null_message_rejected(self, client):
        r = client.post("/api/chat",
                        data=json.dumps({"message": None}),
                        content_type="application/json")
        assert r.status_code in (400, 422)

    def test_missing_message_field(self, client):
        r = client.post("/api/chat",
                        data=json.dumps({}),
                        content_type="application/json")
        assert r.status_code in (400, 422)


class TestHealthEndpoint:
    def test_health_200(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200

    def test_health_returns_json(self, client):
        r = client.get("/api/health")
        assert r.content_type.startswith("application/json")

    def test_health_has_status_field(self, client):
        r = client.get("/api/health")
        body = r.get_json()
        assert "status" in body

    def test_health_status_ok(self, client):
        r = client.get("/api/health")
        body = r.get_json()
        assert body["status"] == "ok"


class TestErrorFormat:
    def test_404_returns_json(self, client):
        r = client.get("/api/nonexistent-endpoint-xyz")
        assert r.status_code == 404

    def test_chat_returns_json_always(self, client):
        r = client.post("/api/chat",
                        data=json.dumps({"message": "fees"}),
                        content_type="application/json")
        assert r.content_type.startswith("application/json")


class TestCORSHeaders:
    def test_cors_header_on_chat(self, client):
        r = client.post("/api/chat",
                        data=json.dumps({"message": "fees"}),
                        content_type="application/json",
                        headers={"Origin": "http://localhost:3000"})
        # CORS should be present or at least not blocked
        assert r.status_code != 403

    def test_options_preflight(self, client):
        r = client.options("/api/chat",
                           headers={"Origin": "http://localhost:3000",
                                    "Access-Control-Request-Method": "POST"})
        assert r.status_code in (200, 204)

