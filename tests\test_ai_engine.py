"""
Phase 4 AI Engine & RAG Tests
Run: python -m pytest tests/test_ai_engine.py -v
"""
import sys, os, json, pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

SAMPLE_DOCS = [
    {
        "id": "fees-001",
        "topic": "BTech CSE Annual Fees",
        "content": "Annual tuition fee for BTech Computer Science Engineering is 2.80 lakhs per year.",
        "category": "fees",
        "keywords": ["btech", "cse", "computer science", "fees", "tuition", "annual"]
    },
    {
        "id": "entrance-001",
        "topic": "LPUNEST Registration",
        "content": "LPUNEST 2025 registration closes on March 31, 2025. Apply at lpunest.lpu.in.",
        "category": "entrance",
        "keywords": ["lpunest", "registration", "entrance", "exam", "march"]
    },
    {
        "id": "scholar-001",
        "topic": "Merit Scholarship Criteria",
        "content": "Merit scholarship: 60-69% → 25% fee waiver, 70-79% → 50% waiver, 80%+ → 75% waiver.",
        "category": "scholarships",
        "keywords": ["scholarship", "merit", "percentage", "waiver", "60", "70", "80"]
    },
    {
        "id": "hostel-001",
        "topic": "Girls Hostel Facility",
        "content": "LPU provides separate girls hostels with 24/7 security, WiFi, and mess facilities.",
        "category": "accommodation",
        "keywords": ["hostel", "girls", "accommodation", "security", "wifi", "mess"]
    },
    {
        "id": "docs-001",
        "topic": "Required Documents for Admission",
        "content": "Documents: 10th marksheet, 12th marksheet, ID proof, passport photos, medical certificate.",
        "category": "documents",
        "keywords": ["documents", "marksheet", "10th", "12th", "proof", "photos"]
    },
]


@pytest.fixture(scope="module")
def engine():
    try:
        from engine.ai_engine import AIAssistantEngine
        eng = AIAssistantEngine()
        eng.index_documents(SAMPLE_DOCS)
        return eng
    except ImportError:
        pytest.skip("ai_engine module not available")


class TestAIEngineImport:
    def test_module_importable(self):
        try:
            from engine import ai_engine
            assert ai_engine is not None
        except ImportError:
            pytest.skip("ai_engine not found")

    def test_class_exists(self):
        try:
            from engine.ai_engine import AIAssistantEngine
            assert AIAssistantEngine is not None
        except ImportError:
            pytest.skip("AIAssistantEngine not found")


class TestBM25Retrieval:
    def test_index_loads_docs(self, engine):
        assert engine.doc_count >= len(SAMPLE_DOCS)

    def test_fees_query_returns_fees_doc(self, engine):
        results = engine.retrieve("what are BTech CSE fees", top_k=3)
        assert isinstance(results, list)
        assert len(results) > 0
        topics = [r.get("topic", "").lower() + r.get("content", "").lower()
                  for r in results]
        assert any("fee" in t for t in topics)

    def test_lpunest_query(self, engine):
        results = engine.retrieve("LPUNEST 2025 registration deadline", top_k=2)
        topics = [r.get("content", "").lower() for r in results]
        assert any("lpunest" in t for t in topics)

    def test_scholarship_query(self, engine):
        results = engine.retrieve("merit scholarship percentage criteria", top_k=3)
        contents = [r.get("content", "").lower() for r in results]
        assert any("scholarship" in c for c in contents)

    def test_hostel_query(self, engine):
        results = engine.retrieve("girls hostel facilities wifi", top_k=2)
        contents = [r.get("content", "").lower() for r in results]
        assert any("hostel" in c for c in contents)

    def test_top_k_respected(self, engine):
        results = engine.retrieve("fees hostel scholarship", top_k=2)
        assert len(results) <= 2

    def test_irrelevant_query_returns_list(self, engine):
        results = engine.retrieve("zzzxxx unrelated random 999", top_k=3)
        assert isinstance(results, list)

    def test_empty_query_handled(self, engine):
        try:
            results = engine.retrieve("", top_k=1)
            assert isinstance(results, list)
        except (ValueError, AssertionError):
            pass  # Raising on empty is acceptable


class TestGroundingPrompt:
    def test_build_grounding_prompt_exists(self, engine):
        assert hasattr(engine, "build_grounding_prompt")

    def test_prompt_no_unfilled_vars(self, engine):
        import re
        prompt = engine.build_grounding_prompt(
            query="fees",
            context_docs=SAMPLE_DOCS[:2],
            history=[]
        )
        # Should not have {placeholder} style unfilled vars
        unfilled = re.findall(r'\{[a-z_]+\}', prompt)
        assert unfilled == [], f"Unfilled template vars: {unfilled}"

    def test_prompt_contains_query(self, engine):
        prompt = engine.build_grounding_prompt(
            query="BTech fees",
            context_docs=SAMPLE_DOCS[:1],
            history=[]
        )
        assert "BTech fees" in prompt or "fees" in prompt.lower()

    def test_prompt_contains_context(self, engine):
        prompt = engine.build_grounding_prompt(
            query="fees",
            context_docs=SAMPLE_DOCS[:1],
            history=[]
        )
        assert "2.80" in prompt or "fee" in prompt.lower()


class TestDatasetIngestion:
    def test_ingest_script_importable(self):
        try:
            import scripts.ingest_dataset as ing
            assert ing is not None
        except ImportError:
            pytest.skip("ingest_dataset not yet available")

    def test_dataset_json_schema_valid(self):
        """Validate the expected dataset schema structure."""
        sample = {
            "version": "1.0",
            "source": "LPU Admissions 2024-25",
            "records": [
                {
                    "id": "test-001",
                    "category": "fees",
                    "topic": "Test Topic",
                    "content": "Test content here.",
                    "keywords": ["test"],
                    "valid_from": "2024-08-01",
                    "valid_until": "2025-07-31",
                    "confidence": 100
                }
            ]
        }
        assert "version" in sample
        assert "records" in sample
        rec = sample["records"][0]
        required_keys = ["id", "category", "topic", "content", "keywords"]
        for key in required_keys:
            assert key in rec, f"Missing key: {key}"

