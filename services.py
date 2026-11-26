"""Glue layer: engine + dialogue-state persistence + Firebase Firestore + AI grounding."""
import json
import logging
import os
import uuid
from datetime import datetime, timezone

from db.firestore_db import FirestoreDB, is_firebase_configured
from db.models import ConversationLog, CustomRule, SessionState
from engine.ai_engine import AIAssistantEngine
from engine.context_manager import DialogueContext
from engine.inference_engine import InferenceEngine, load_kb

logger = logging.getLogger(__name__)


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ChatService:
    def __init__(self):
        self.kb = load_kb()
        self.engines = {"2.4": InferenceEngine("2.4", self.kb), "1.0": InferenceEngine("1.0", self.kb)}
        self.ai_engine = AIAssistantEngine(self.kb)
        self.firestore = None
        if is_firebase_configured():
            try:
                self.firestore = FirestoreDB()
                logger.info("Firebase Firestore initialized as primary database")
            except Exception as e:
                logger.warning("Could not initialize Firestore (%s); falling back to SQL", e)

    # ---- rule base
    def reload_rules(self, db=None):
        rules_map = {}
        # 1. Load from SQL if db provided
        if db:
            for r in db.query(CustomRule).filter(CustomRule.active.is_(True)).all():
                rules_map[r.rule_id] = {"rule_id": r.rule_id, "label": r.label, "pattern": r.pattern, "response": r.response}

        # 2. Load from Firestore if configured
        if self.firestore:
            try:
                fs_rules = self.firestore.get_custom_rules(active_only=True)
                for r in fs_rules:
                    rules_map[r["rule_id"]] = {
                        "rule_id": r.get("rule_id"),
                        "label": r.get("label", "custom"),
                        "pattern": r.get("pattern", ""),
                        "response": r.get("response", "")
                    }
            except Exception as e:
                logger.warning("Failed to load rules from Firestore: %s", e)

        rules = list(rules_map.values())
        self.engines["2.4"].reload(rules)
        return len(rules)

    # ---- dialogue state
    def load_ctx(self, db, session_id):
        # 1. Try Firestore first
        if self.firestore:
            try:
                state_data = self.firestore.get_session_state(session_id)
                if state_data:
                    return DialogueContext.from_dict(state_data)
            except Exception as e:
                logger.debug("Firestore session load: %s", e)

        # 2. Try SQL database
        if db:
            row = db.get(SessionState, session_id)
            if row:
                try:
                    return DialogueContext.from_dict(json.loads(row.state_json))
                except Exception:
                    pass

        return DialogueContext(session_id=session_id)

    def save_ctx(self, db, ctx):
        state_dict = ctx.to_dict()
        # 1. Save to Firestore
        if self.firestore:
            try:
                self.firestore.save_session_state(ctx.session_id, state_dict)
            except Exception as e:
                logger.warning("Firestore session save failed: %s", e)

        # 2. Save to SQL database
        if db:
            row = db.get(SessionState, ctx.session_id)
            payload = json.dumps(state_dict)
            if row:
                row.state_json = payload
            else:
                db.add(SessionState(session_id=ctx.session_id, state_json=payload))

    def reset(self, db, session_id):
        if self.firestore:
            try:
                self.firestore.delete_session_state(session_id)
            except Exception as e:
                logger.debug("Firestore session reset: %s", e)

        if db:
            row = db.get(SessionState, session_id)
            if row:
                db.delete(row)

    # ---- main entry
    def chat(self, db, session_id, text, version="2.4", is_seed=False, ts=None, ctx=None):
        session_id = session_id or uuid.uuid4().hex[:12]
        engine = self.engines.get(version, self.engines["2.4"])
        persist = ctx is None
        ctx = ctx or self.load_ctx(db, session_id)

        # 1. Execute deterministic rule-based engine first
        out = engine.process(text, ctx)
        m = out["meta"]

        # 2. If rule engine didn't answer and version is 2.4, use AI RAG Grounded Engine
        if (not m.get("is_answered") or m.get("confidence", 0) < 0.5) and version == "2.4":
            ai_res = self.ai_engine.generate_grounded_response(text)
            if ai_res.get("grounded"):
                out["reply"] = ai_res["reply"]
                out["escalate"] = ai_res.get("escalate", False)
                m["rule_id"] = "AI_GROUNDED"
                m["intent"] = "ai_dataset_retrieval"
                m["confidence"] = ai_res.get("confidence", 0.85)
                m["is_answered"] = True
                m["sources"] = ai_res.get("sources", [])
                if ai_res.get("sources"):
                    existing_chips = out.get("chips") or []
                    for src in ai_res["sources"][:2]:
                        existing_chips.append({"label": src, "prompt": f"Tell me more about {src}"})
                    out["chips"] = existing_chips

        # 3. Save conversation log to Firestore
        if self.firestore:
            try:
                self.firestore.add_log(
                    session_id=session_id,
                    user_query=text,
                    detected_intent=m.get("intent"),
                    slots=m.get("slots", {}),
                    rule_id=m.get("rule_id"),
                    is_answered=m.get("is_answered", True),
                    confidence=m.get("confidence", 0.0),
                    version=engine.version,
                    is_seed=is_seed,
                    timestamp=ts or utcnow()
                )
            except Exception as e:
                logger.warning("Firestore log failed: %s", e)

        # 4. Save to SQL database
        if db:
            db.add(ConversationLog(
                session_id=session_id,
                user_query=text,
                detected_intent=m.get("intent"),
                slots=json.dumps(m.get("slots", {})),
                rule_id=m.get("rule_id"),
                is_answered=m.get("is_answered", True),
                confidence=m.get("confidence", 0.0),
                version=engine.version,
                is_seed=is_seed,
                timestamp=ts or utcnow()
            ))

        if persist:
            self.save_ctx(db, ctx)
        out["session_id"] = session_id
        return out
