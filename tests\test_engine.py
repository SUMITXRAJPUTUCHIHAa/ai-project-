"""Engine unit tests (no database needed).  Run: python -m unittest discover -s tests"""
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.context_manager import DialogueContext
from engine.inference_engine import InferenceEngine


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.e = InferenceEngine("2.4")
        self.ctx = DialogueContext("t")

    def ask(self, q, e=None):
        return (e or self.e).process(q, self.ctx)

    def test_fee_with_programme(self):
        r = self.ask("What is the fee for B.Tech CSE?")
        self.assertEqual(r["meta"]["rule_id"], "R04")
        self.assertIn("1,60,000", r["reply"])

    def test_slot_filling_two_turns(self):
        r = self.ask("What is the fee?")
        self.assertEqual(r["meta"]["pending_slots"], ["programme"])
        self.assertIn("Which programme", r["reply"])
        r = self.ask("MBA")
        self.assertTrue(r["meta"]["slot_resolved"])
        self.assertIn("2,00,000", r["reply"])
        self.assertEqual(self.ctx.pending_slots, [])

    def test_context_carries_programme(self):
        self.ask("fee for BCA")
        r = self.ask("and eligibility?")
        self.assertEqual(r["meta"]["intent"], "eligibility")
        self.assertIn("BCA", r["reply"])

    def test_fallback_logs_unanswered(self):
        r = self.ask("zxqv blorp")
        self.assertFalse(r["meta"]["is_answered"])
        self.assertTrue(r["escalate"])
        self.assertEqual(len(r["chips"]), 3)

    def test_v24_rules_absent_in_baseline(self):
        base = InferenceEngine("1.0")
        self.assertFalse(base.can_answer("refund timeline if I cancel admission"))
        self.assertTrue(self.e.can_answer("refund timeline if I cancel admission"))

    def test_hot_reload_custom_rule(self):
        q = "does LPU give placement in Google"
        self.assertFalse(self.e.can_answer(q))
        self.e.reload([{"rule_id": "C001", "label": "placements", "pattern": r"\bplacement\b", "response": "Placement details are on lpu.in/placements."}])
        r = self.ask(q)
        self.assertEqual(r["meta"]["rule_id"], "C001")
        self.e.reload([])

    def test_comparison(self):
        r = self.ask("compare btech cse vs mba")
        self.assertIn("table", r)

    def test_metadata_fields(self):
        m = self.ask("hostel 3 seater ac")["meta"]
        for k in ("rule_id", "matched_regex", "confidence", "extracted_entities"):
            self.assertIn(k, m)
        self.assertEqual(m["extracted_entities"].get("seater"), 3)


if __name__ == "__main__":
    unittest.main()
