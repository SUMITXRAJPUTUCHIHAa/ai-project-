"""Firestore Database Layer for LPU Admission Intelligence.

Provides full CRUD operations for:
- conversation_logs
- custom_rules
- session_state
- escalations
- knowledge_base
"""
import json
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_firestore_client = None
_firebase_initialized = False


def utcnow_iso():
    return datetime.now(timezone.utc).isoformat()


def is_firebase_configured():
    """Check if Firebase credentials are fully available in the environment."""
    sa_path = (
        os.environ.get("FIREBASE_CREDENTIALS_PATH")
        or os.environ.get("FIREBASE_SERVICE_ACCOUNT_PATH")
        or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    )
    if sa_path and os.path.exists(sa_path):
        return True
    if os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON"):
        return True
    return False


def get_firestore_client():
    """Initialize Firebase Admin SDK and return Firestore client singleton."""
    global _firestore_client, _firebase_initialized
    if _firestore_client is not None:
        return _firestore_client

    import firebase_admin
    from firebase_admin import credentials, firestore

    if not firebase_admin._apps:
        cred = None
        sa_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")
        sa_path = os.environ.get("FIREBASE_SERVICE_ACCOUNT_PATH") or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        project_id = os.environ.get("FIREBASE_PROJECT_ID") or os.environ.get("GCP_PROJECT")

        if sa_json:
            try:
                cert_dict = json.loads(sa_json)
                cred = credentials.Certificate(cert_dict)
            except Exception as e:
                logger.error("Failed to parse FIREBASE_SERVICE_ACCOUNT_JSON: %s", e)
        elif sa_path and os.path.exists(sa_path):
            cred = credentials.Certificate(sa_path)
        elif project_id:
            try:
                cred = credentials.ApplicationDefault()
            except Exception:
                cred = None

        options = {"projectId": project_id} if project_id else {}
        if cred:
            firebase_admin.initialize_app(cred, options)
        else:
            firebase_admin.initialize_app(options=options)
        _firebase_initialized = True

    _firestore_client = firestore.client()
    return _firestore_client


class FirestoreDB:
    """High-level CRUD operations for Firestore collections."""

    def __init__(self, client=None):
        self._client = client

    @property
    def client(self):
        if self._client is None:
            self._client = get_firestore_client()
        return self._client

    # ==========================================
    # 1. Conversation Logs CRUD
    # ==========================================
    def add_log(self, session_id, user_query, detected_intent, slots, rule_id,
                is_answered, confidence, version="2.4", is_seed=False, timestamp=None):
        """Create a new conversation log document."""
        col = self.client.collection("conversation_logs")
        ts = timestamp.isoformat() if isinstance(timestamp, datetime) else (timestamp or utcnow_iso())
        slots_data = slots if isinstance(slots, dict) else json.loads(slots or "{}")
        doc_data = {
            "session_id": session_id,
            "user_query": user_query,
            "detected_intent": detected_intent,
            "slots": slots_data,
            "rule_id": rule_id,
            "is_answered": bool(is_answered),
            "confidence": float(confidence),
            "version": str(version),
            "is_seed": bool(is_seed),
            "timestamp": ts,
        }
        ref = col.document()
        ref.set(doc_data)
        doc_data["id"] = ref.id
        return doc_data

    def get_logs(self, session_id=None, is_seed=None, limit=100):
        """Read conversation logs with optional filters."""
        query = self.client.collection("conversation_logs")
        if session_id:
            query = query.where("session_id", "==", session_id)
        if is_seed is not None:
            query = query.where("is_seed", "==", is_seed)
        docs = query.order_by("timestamp", direction="DESCENDING").limit(limit).stream()
        results = []
        for d in docs:
            item = d.to_dict()
            item["id"] = d.id
            results.append(item)
        return results

    def get_log_stats(self, is_seed=None):
        """Compute aggregated analytics on conversation logs."""
        query = self.client.collection("conversation_logs")
        if is_seed is not None:
            query = query.where("is_seed", "==", is_seed)
        docs = list(query.stream())
        total = len(docs)
        if total == 0:
            return {"total": 0, "answered": 0, "recognition_rate": 0.0}
        answered = sum(1 for d in docs if d.to_dict().get("is_answered", False))
        return {
            "total": total,
            "answered": answered,
            "recognition_rate": round(100.0 * answered / total, 1),
        }

    # ==========================================
    # 2. Custom Rules CRUD
    # ==========================================
    def create_custom_rule(self, rule_id, label, pattern, response, active=True):
        """Create a new custom rule document."""
        col = self.client.collection("custom_rules")
        doc_data = {
            "rule_id": rule_id,
            "label": label,
            "pattern": pattern,
            "response": response,
            "active": active,
            "created_at": utcnow_iso(),
        }
        col.document(rule_id).set(doc_data)
        return doc_data

    def get_custom_rules(self, active_only=True):
        """Read all custom rules."""
        query = self.client.collection("custom_rules")
        if active_only:
            query = query.where("active", "==", True)
        docs = query.stream()
        return [d.to_dict() for d in docs]

    def get_custom_rule(self, rule_id):
        """Read a single custom rule by rule_id."""
        doc = self.client.collection("custom_rules").document(rule_id).get()
        return doc.to_dict() if doc.exists else None

    def update_custom_rule(self, rule_id, updates):
        """Update fields of an existing custom rule."""
        doc_ref = self.client.collection("custom_rules").document(rule_id)
        if not doc_ref.get().exists:
            return None
        updates["updated_at"] = utcnow_iso()
        doc_ref.update(updates)
        return doc_ref.get().to_dict()

    def delete_custom_rule(self, rule_id):
        """Delete a custom rule by rule_id."""
        doc_ref = self.client.collection("custom_rules").document(rule_id)
        if doc_ref.get().exists:
            doc_ref.delete()
            return True
        return False

    # ==========================================
    # 3. Session State CRUD
    # ==========================================
    def save_session_state(self, session_id, state_dict):
        """Create or update dialogue session context."""
        payload = state_dict if isinstance(state_dict, dict) else json.loads(state_dict or "{}")
        doc_data = {
            "session_id": session_id,
            "state_data": payload,
            "updated_at": utcnow_iso(),
        }
        self.client.collection("session_state").document(session_id).set(doc_data)
        return doc_data

    def get_session_state(self, session_id):
        """Read session state by session_id."""
        doc = self.client.collection("session_state").document(session_id).get()
        if doc.exists:
            data = doc.to_dict()
            return data.get("state_data", {})
        return None

    def delete_session_state(self, session_id):
        """Delete session state upon reset."""
        doc_ref = self.client.collection("session_state").document(session_id)
        if doc_ref.get().exists:
            doc_ref.delete()
            return True
        return False

    # ==========================================
    # 4. Escalations CRUD
    # ==========================================
    def create_escalation(self, session_id, user_query, contact=""):
        """Create a new counsellor escalation request."""
        col = self.client.collection("escalations")
        doc_data = {
            "session_id": session_id,
            "user_query": user_query,
            "contact": contact,
            "status": "pending",
            "created_at": utcnow_iso(),
        }
        ref = col.document()
        ref.set(doc_data)
        doc_data["id"] = ref.id
        return doc_data

    def get_escalations(self, limit=50):
        """Read recent escalations."""
        docs = self.client.collection("escalations").order_by("created_at", direction="DESCENDING").limit(limit).stream()
        results = []
        for d in docs:
            item = d.to_dict()
            item["id"] = d.id
            results.append(item)
        return results

    def update_escalation(self, escalation_id, status="resolved"):
        """Update the status of an escalation."""
        doc_ref = self.client.collection("escalations").document(escalation_id)
        if doc_ref.get().exists:
            doc_ref.update({"status": status, "updated_at": utcnow_iso()})
            return True
        return False

    # ==========================================
    # 5. Knowledge Base & Dataset CRUD
    # ==========================================
    def upsert_dataset_collection(self, collection_name, document_id, data):
        """Store structured dataset documents (programmes, fees, scholarships, hostels, etc.)."""
        self.client.collection(collection_name).document(document_id).set(data)
        return True

    def get_dataset_collection(self, collection_name):
        """Retrieve all documents in a dataset collection."""
        docs = self.client.collection(collection_name).stream()
        return {d.id: d.to_dict() for d in docs}
