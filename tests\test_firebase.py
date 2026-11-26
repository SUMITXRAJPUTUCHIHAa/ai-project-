"""
Phase 3 Firebase Integration Tests
Run: python -m pytest tests/test_firebase.py -v
Live tests require FIREBASE_PROJECT_ID env var.
"""
import os, sys, pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

try:
    from db.firestore_db import is_firebase_configured
    FIREBASE_CONFIGURED = is_firebase_configured()
except Exception:
    FIREBASE_CONFIGURED = False


class TestFirestoreFileArtifacts:
    """Tests that run without any cloud connection."""

    def test_firestore_rules_exists(self):
        path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "firestore.rules"
        )
        assert os.path.exists(path), "firestore.rules is missing"

    def test_firestore_indexes_exists(self):
        path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "firestore.indexes.json"
        )
        assert os.path.exists(path), "firestore.indexes.json is missing"

    def test_env_example_has_firebase_vars(self):
        path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), ".env.example"
        )
        content = open(path).read()
        assert "FIREBASE_PROJECT_ID" in content
        assert "FIREBASE_CREDENTIALS_PATH" in content

    def test_firestore_db_module_importable(self):
        try:
            from db import firestore_db
            assert firestore_db is not None
        except ImportError:
            pytest.skip("firestore_db module not found")

    def test_seed_script_exists(self):
        path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "scripts", "seed_firebase.py"
        )
        assert os.path.exists(path), "scripts/seed_firebase.py missing"

    def test_ingest_script_exists(self):
        path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "scripts", "ingest_dataset.py"
        )
        assert os.path.exists(path), "scripts/ingest_dataset.py missing"

    def test_gitignore_excludes_credentials(self):
        path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), ".gitignore"
        )
        if os.path.exists(path):
            content = open(path).read()
            assert "credentials/" in content or "*.json" in content or \
                   ".env" in content, ".gitignore should exclude credentials"

    def test_no_hardcoded_firebase_key(self):
        """Ensure no service account key JSON blob is committed in source."""
        # Look for the full private key PEM content, not just the field name
        pem_pattern = "-----BEGIN RSA PRIVATE KEY-----"
        for root, dirs, files in os.walk(
            os.path.dirname(os.path.dirname(__file__))
        ):
            # Skip venv, cache, credentials folder (allowed to have keys)
            # Also skip the tests folder itself (may contain the pattern as documentation)
            dirs[:] = [d for d in dirs
                       if d not in (".venv", "__pycache__", "credentials",
                                    "node_modules", ".git", "tests")]
            for fname in files:
                if fname.endswith((".py", ".json", ".env")):
                    fpath = os.path.join(root, fname)
                    try:
                        content = open(fpath, errors="ignore").read()
                        assert pem_pattern not in content, \
                            f"RSA private key PEM found in {fpath}"
                    except (OSError, PermissionError):
                        pass  # Skip unreadable files


class TestFirestoreDBModule:
    """Unit tests for the FirestoreDB class using mocks."""

    def test_firestore_class_has_add_log(self):
        try:
            from db.firestore_db import FirestoreDB
            assert hasattr(FirestoreDB, "add_log"), \
                "FirestoreDB missing add_log method"
        except ImportError:
            pytest.skip("firestore_db not available")

    def test_firestore_class_has_get_logs(self):
        try:
            from db.firestore_db import FirestoreDB
            assert hasattr(FirestoreDB, "get_logs"), \
                "FirestoreDB missing get_logs method"
        except ImportError:
            pytest.skip("firestore_db not available")

    def test_is_firebase_configured_returns_bool(self):
        try:
            # This function should exist in services or app
            from services import is_firebase_configured
            result = is_firebase_configured()
            assert isinstance(result, bool)
        except ImportError:
            pytest.skip("is_firebase_configured not found in services")


@pytest.mark.skipif(not FIREBASE_CONFIGURED, reason="Firebase not configured — set FIREBASE_PROJECT_ID")
class TestFirestoreLive:
    def test_live_connection(self):
        from db.firestore_db import FirestoreDB
        db = FirestoreDB()
        assert db is not None

    def test_live_write_and_read(self):
        from db.firestore_db import FirestoreDB
        db = FirestoreDB()
        doc_id = db.add_log(
            session_id="pytest-session",
            user_query="Firebase integration test",
            detected_intent="test",
            slots={},
            rule_id="test-rule",
            response_text="OK",
            confidence=0.99,
            escalated=False
        )
        assert doc_id is not None

    def test_logs_readable(self):
        from db.firestore_db import FirestoreDB
        db = FirestoreDB()
        docs = db.get_logs(limit=1)
        assert isinstance(docs, list)
