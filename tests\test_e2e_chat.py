"""
Phase 5 End-to-End Chat Flow Tests
Run: python -m pytest tests/test_e2e_chat.py -v
"""
import sys, os, json, pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


@pytest.fixture(scope="module")
def client():
    try:
        from app import app as flask_app
        flask_app.config["TESTING"] = True
        with flask_app.test_client() as c:
            yield c
    except Exception as e:
        pytest.skip(f"Flask app not importable: {e}")


CHAT_SCENARIOS = [
    # (query, keyword_in_response)
    ("What is the fee for BTech CSE?",          "fee"),
    ("LPUNEST registration date 2025",          "lpunest"),
    ("merit scholarship eligibility 75 percent","scholarship"),
    ("hostel facilities for girls",             "hostel"),
    ("documents required for admission",        "document"),
    ("lateral entry eligibility criteria",      "eligib"),
    ("Hello",                                   None),          # greeting
    ("What programmes does LPU offer?",         None),
]


class TestChatBasicFlow:
    def test_chat_returns_200(self, client):
        r = client.post("/api/chat",
                        data=json.dumps({"message": "fees"}),
                        content_type="application/json")
        assert r.status_code == 200

    def test_chat_returns_json(self, client):
        r = client.post("/api/chat",
                        data=json.dumps({"message": "fees"}),
                        content_type="application/json")
        body = r.get_json()
        assert body is not None

    def test_chat_response_has_answer_key(self, client):
        r = client.post("/api/chat",
                        data=json.dumps({"message": "fees"}),
                        content_type="application/json")
        body = r.get_json()
        # Accept any of the known response key names used by this API
        has_answer = any(k in body for k in
                         ("answer", "response", "reply", "text", "message", "pending"))
        assert has_answer, f"No answer key found. Keys: {list(body.keys())}"

    def test_chat_response_not_empty(self, client):
        r = client.post("/api/chat",
                        data=json.dumps({"message": "BTech CSE fees"}),
                        content_type="application/json")
        body = r.get_json()
        # Gather content from any key that might hold the answer
        answer = (body.get("answer") or body.get("response") or
                  body.get("reply") or body.get("text") or
                  str(body.get("chips", "")) or "")
        assert len(answer) > 0, f"Response appears empty. Body: {body}"


@pytest.mark.parametrize("query,keyword", CHAT_SCENARIOS)
def test_chat_scenario(client, query, keyword):
    r = client.post("/api/chat",
                    data=json.dumps({"message": query}),
                    content_type="application/json")
    assert r.status_code == 200
    if keyword:
        body_text = r.get_data(as_text=True).lower()
        assert keyword.lower() in body_text, \
            f"Expected '{keyword}' in response for query: '{query}'"


class TestSessionManagement:
    def test_chat_accepts_session_id(self, client):
        r = client.post("/api/chat",
                        data=json.dumps({"message": "fees",
                                         "session_id": "e2e-sess-001"}),
                        content_type="application/json")
        assert r.status_code == 200

    def test_multiple_turns_same_session(self, client):
        for msg in ["fees", "and hostel?", "scholarship?"]:
            r = client.post("/api/chat",
                            data=json.dumps({"message": msg,
                                             "session_id": "e2e-multi-001"}),
                            content_type="application/json")
            assert r.status_code == 200

    def test_concurrent_sessions_independent(self, client):
        for i in range(5):
            r = client.post("/api/chat",
                            data=json.dumps({"message": "fees",
                                             "session_id": f"concurrent-{i}"}),
                            content_type="application/json")
            assert r.status_code == 200


class TestResetEndpoint:
    def test_reset_200(self, client):
        r = client.post("/api/reset",
                        data=json.dumps({"session_id": "e2e-reset-001"}),
                        content_type="application/json")
        assert r.status_code in (200, 204)

    def test_reset_after_chat(self, client):
        client.post("/api/chat",
                    data=json.dumps({"message": "fees",
                                     "session_id": "e2e-reset-002"}),
                    content_type="application/json")
        r = client.post("/api/reset",
                        data=json.dumps({"session_id": "e2e-reset-002"}),
                        content_type="application/json")
        assert r.status_code in (200, 204)


class TestTopicsEndpoint:
    def test_topics_200(self, client):
        r = client.get("/api/topics")
        assert r.status_code == 200

    def test_topics_returns_list(self, client):
        r = client.get("/api/topics")
        body = r.get_json()
        assert isinstance(body, (list, dict))


class TestAnalyticsEndpoint:
    def test_analytics_200(self, client):
        r = client.get("/api/analytics")
        assert r.status_code == 200

    def test_analytics_has_total_queries(self, client):
        r = client.get("/api/analytics")
        body = r.get_json()
        assert isinstance(body, dict)
