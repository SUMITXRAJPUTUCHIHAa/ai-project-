"""Automated tests for all API endpoints."""
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import app


class TestAPIEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.app.config["TESTING"] = True
        cls.client = app.app.test_client()

    def test_01_health(self):
        res = self.client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["status"], "ok")
        self.assertTrue("database" in data)
        self.assertTrue(data.get("ai_rag_enabled"))

    def test_02_topics(self):
        res = self.client.get("/api/topics")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue("topics" in data)
        self.assertTrue("programmes" in data)

    def test_03_chat_flow(self):
        res = self.client.post("/api/chat", json={"message": "What is the fee for B.Tech CSE?"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue("reply" in data)
        self.assertTrue("1,60,000" in data["reply"] or "160000" in data["reply"])
        self.assertTrue(data["meta"]["is_answered"])

    def test_04_calc_fee(self):
        res = self.client.post("/api/calc-fee", json={
            "programme": "btech_cse",
            "scholarship_pct": 30,
            "hostel_index": 0,
            "mess": True
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["grand_total"] > 0)
        self.assertIn("B.Tech CSE", data["programme"])

    def test_05_hostel_tiers(self):
        res = self.client.get("/api/hostel-tiers")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(isinstance(data, list))
        self.assertTrue(len(data) > 0)

    def test_06_test_rule(self):
        res = self.client.post("/api/test-rule", json={
            "pattern": r"\b(gym|fitness)\b",
            "queries": ["Is there a gym on campus?"]
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["match_count"], 1)

    def test_07_custom_rules_crud(self):
        # 1. Create rule
        create_res = self.client.post("/api/custom-rules", json={
            "label": "swimming_pool",
            "pattern": r"\b(swimming pool|aquatic)\b",
            "response": "Yes, LPU has an Olympic-size indoor swimming pool."
        })
        self.assertEqual(create_res.status_code, 200)
        rule_data = create_res.get_json()
        rid = rule_data["rule_id"]

        # 2. Read list
        list_res = self.client.get("/api/custom-rules")
        self.assertEqual(list_res.status_code, 200)
        rules = list_res.get_json()
        self.assertTrue(any(r["rule_id"] == rid for r in rules))

        # 3. Read single
        get_res = self.client.get(f"/api/custom-rules/{rid}")
        self.assertEqual(get_res.status_code, 200)
        self.assertEqual(get_res.get_json()["label"], "swimming_pool")

        # 4. Test chat triggers the new rule
        chat_res = self.client.post("/api/chat", json={"message": "Does campus have a swimming pool?"})
        self.assertEqual(chat_res.status_code, 200)
        self.assertIn("Olympic-size", chat_res.get_json()["reply"])

        # 5. Delete rule
        del_res = self.client.delete(f"/api/custom-rules/{rid}")
        self.assertEqual(del_res.status_code, 200)

    def test_08_escalation_flow(self):
        res = self.client.post("/api/escalate", json={
            "session_id": "test_sess_01",
            "query": "Special case admission transfer inquiry",
            "contact": "student@example.com"
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("ok"))

        # Verify escalation is listed
        list_res = self.client.get("/api/escalations")
        self.assertEqual(list_res.status_code, 200)
        escalations = list_res.get_json()
        self.assertTrue(any(e["user_query"] == "Special case admission transfer inquiry" for e in escalations))

    def test_09_ai_dataset_search(self):
        res = self.client.post("/api/dataset/search", json={"query": "scholarship cut off marks"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(len(data.get("matches", [])) > 0)

    def test_10_dataset_ingest(self):
        custom_items = [
            {
                "id": "faq_robotics_club",
                "category": "clubs",
                "title": "Robotics Club and Makerspace",
                "content": "The LPU Robotics and Automation Club operates 24/7 with 3D printers and laser cutters."
            }
        ]
        res = self.client.post("/api/dataset/ingest", json={"items": custom_items})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["items_ingested"], 1)

        # Verify chat answers via AI retrieval
        chat_res = self.client.post("/api/chat", json={"message": "Tell me about the robotics club"})
        self.assertEqual(chat_res.status_code, 200)
        chat_json = chat_res.get_json()
        self.assertIn("Robotics and Automation Club", chat_json["reply"])


if __name__ == "__main__":
    unittest.main()
