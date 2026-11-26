"""LPU Admission Intelligence - Flask REST API + static single-page UI.

Endpoints:
- Core Chat: /api/chat, /api/health, /api/analytics, /api/reset, /api/topics, /api/slot-state, /api/rules
- Fee Calculator & Hostels: /api/calc-fee, /api/hostel-tiers
- Rule Studio & Expansion: /api/expand-rule, /api/test-rule, /api/custom-rules (CRUD)
- Escalation & Support: /api/escalate, /api/escalations
- AI & Dataset Integration: /api/dataset/ingest, /api/dataset/search
- Exports & Evidence: /api/export/<json|csv>, /api/seed
"""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Auto-load .env configuration into environment
_env_path = os.path.join(ROOT, ".env")
if os.path.exists(_env_path):
    try:
        with open(_env_path, "r", encoding="utf-8") as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith("#") and "=" in _line:
                    _k, _v = _line.split("=", 1)
                    _k = _k.strip()
                    _v = _v.strip().strip("'\"")
                    if _k and _k not in os.environ:
                        os.environ[_k] = _v
    except Exception:
        pass

import re
import uuid

from flask import Flask, Response, jsonify, request, send_from_directory

from db import analytics
from db.database import DATABASE_URL, backend_name, init_db, session_scope
from db.models import CustomRule, Escalation
from services import ChatService

app = Flask(__name__, static_folder=os.path.join(ROOT, "static"), static_url_path="/static")
app.config["JSON_SORT_KEYS"] = False

init_db()
svc = ChatService()
with session_scope() as _db:
    svc.reload_rules(_db)
    if os.environ.get("AUTO_SEED", "1") == "1" and analytics.version_stats(_db, is_seed=True) == {}:
        from db.seed_evidence import _chat_all
        _chat_all(svc, _db)


def err(msg, code=400):
    return jsonify({"error": msg}), code


@app.after_request
def headers(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Cache-Control"] = "no-store" if request.path.startswith("/api/") else "public, max-age=300"
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Admin-Token"
    return resp


@app.route("/", methods=["GET"])
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/health")
def health():
    with session_scope() as db:
        h = analytics.live_health(db)
        db_type = "firebase" if svc.firestore else backend_name()
        return jsonify({
            "status": "ok",
            "engine_version": "2.4",
            "database": db_type,
            "kb_version": svc.kb["meta"]["kb_version"],
            "custom_rules": len(svc.engines["2.4"].custom_rules),
            "queries_logged": h["queries_logged"],
            "recognition_rate": h["recognition_rate"],
            "unresolved": analytics.unresolved_live(db, svc),
            "ai_rag_enabled": True,
            "ai_chunks_indexed": len(svc.ai_engine.retriever.chunks),
            "ai_provider": "groq" if os.environ.get("GROQ_API_KEY") else ("gemini" if os.environ.get("GEMINI_API_KEY") else "local_bm25"),
            "ai_model": os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b"),
            "ai_configured": bool(os.environ.get("GROQ_API_KEY") or os.environ.get("GEMINI_API_KEY")),
            "firebase_connected": bool(svc.firestore)
        })


@app.route("/api/topics")
def topics():
    return jsonify({
        "topics": svc.kb["topics"],
        "programmes": {k: v["name"] for k, v in svc.kb["programmes"].items()},
        "contact": svc.kb["meta"]["contact"]
    })


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    msg = (data.get("message") or "").strip()
    if not msg:
        return err("message is required")
    if len(msg) > 500:
        return err("message too long (max 500 characters)")
    sid = (data.get("session_id") or uuid.uuid4().hex[:12])[:64]
    version = "1.0" if str(data.get("version")) == "1.0" else "2.4"
    with session_scope() as db:
        out = svc.chat(db, sid, msg, version=version)
        out["health"] = analytics.live_health(db)
        out["unresolved"] = analytics.unresolved_live(db, svc)
    return jsonify(out)


@app.route("/api/reset", methods=["POST"])
def reset():
    data = request.get_json(silent=True) or {}
    sid = data.get("session_id") or ""
    with session_scope() as db:
        svc.reset(db, sid)
    return jsonify({"ok": True, "session_id": sid})


@app.route("/api/slot-state")
def slot_state():
    sid = request.args.get("session_id", "")
    with session_scope() as db:
        return jsonify(svc.load_ctx(db, sid).to_dict())


@app.route("/api/analytics")
def analytics_api():
    with session_scope() as db:
        rep = analytics.full_report(db, svc)
        rep["unresolved"] = analytics.unresolved_live(db, svc)
        rep["open_queries"] = [r for r in analytics.top_unanswered(db, svc, n=40) if not r["covered_now"]]
        return jsonify(rep)


@app.route("/api/rules")
def rules():
    from engine.intent_matcher import RULES
    base = [{"rule_id": r["id"], "intent": r["intent"], "since": r["since"], "priority": r["priority"],
             "patterns": r["patterns"] + r.get("patterns_v24", [])} for r in RULES]
    return jsonify({"rules": base, "custom": svc.engines["2.4"].custom_rules})


def _check_pattern(pattern):
    if not pattern or len(pattern) > 200:
        return None, "pattern is required (max 200 characters)"
    try:
        rx = re.compile(pattern, re.I)
    except re.error as e:
        return None, "invalid regular expression: %s" % e
    if rx.search("") or rx.search("hello there") or rx.search("zzz"):
        return None, "pattern is too broad - it matches generic text; make it more specific"
    return rx, None


@app.route("/api/test-rule", methods=["POST"])
def test_rule():
    data = request.get_json(silent=True) or {}
    rx, e = _check_pattern(data.get("pattern", ""))
    if e:
        return err(e)
    engine = svc.engines["2.4"]
    samples = [s for s in (data.get("queries") or []) if isinstance(s, str)][:20]
    with session_scope() as db:
        logged = [r["query"] for r in analytics.top_unanswered(db, svc, n=200)]
    results = []
    for q in samples + logged:
        norm = engine.pre.run(q)["text"]
        if rx.search(norm):
            results.append({"query": q, "currently_answered": engine.can_answer(q)})
    return jsonify({"pattern": data["pattern"], "matches": results, "match_count": len(results), "tested_text_form": "lemmatised, alias-mapped lowercase"})


@app.route("/api/expand-rule", methods=["POST"])
def expand_rule():
    data = request.get_json(silent=True) or {}
    pattern, response = data.get("pattern", ""), (data.get("response") or "").strip()
    rx, e = _check_pattern(pattern)
    if e:
        return err(e)
    if not response or len(response) > 2000:
        return err("response is required (max 2000 characters)")
    label = (data.get("label") or "custom")[:80]
    with session_scope() as db:
        n = db.query(CustomRule).count() + 1
        rid = (data.get("rule_id") or "C%03d" % n)[:60]
        while db.query(CustomRule).filter(CustomRule.rule_id == rid).first():
            n += 1
            rid = "C%03d" % n
        db.add(CustomRule(rule_id=rid, label=label, pattern=pattern, response=response))
        db.flush()

        # Save to Firebase Firestore if connected
        if svc.firestore:
            try:
                svc.firestore.create_custom_rule(rid, label, pattern, response)
            except Exception as ex:
                app.logger.warning("Firestore create_custom_rule failed: %s", ex)

        count = svc.reload_rules(db)
        before = analytics.unresolved_live(db, svc)
    return jsonify({"ok": True, "rule_id": rid, "active_custom_rules": count, "unresolved": before, "message": "Rule saved and hot-reloaded."})


# Full CRUD for Custom Rules
@app.route("/api/custom-rules", methods=["GET", "POST"])
def custom_rules_collection():
    if request.method == "GET":
        with session_scope() as db:
            rows = db.query(CustomRule).all()
            return jsonify([{"rule_id": r.rule_id, "label": r.label, "pattern": r.pattern, "response": r.response, "active": r.active} for r in rows])

    # POST create
    return expand_rule()


@app.route("/api/custom-rules/<rule_id>", methods=["GET", "PUT", "DELETE"])
def custom_rule_item(rule_id):
    with session_scope() as db:
        rule = db.query(CustomRule).filter(CustomRule.rule_id == rule_id).first()
        if not rule:
            return err("rule not found", 404)

        if request.method == "GET":
            return jsonify({"rule_id": rule.rule_id, "label": rule.label, "pattern": rule.pattern, "response": rule.response, "active": rule.active})

        if request.method == "PUT":
            data = request.get_json(silent=True) or {}
            if "label" in data:
                rule.label = str(data["label"])[:80]
            if "pattern" in data:
                rx, e = _check_pattern(data["pattern"])
                if e:
                    return err(e)
                rule.pattern = data["pattern"]
            if "response" in data:
                rule.response = str(data["response"])[:2000]
            if "active" in data:
                rule.active = bool(data["active"])
            db.flush()
            if svc.firestore:
                svc.firestore.update_custom_rule(rule_id, data)
            svc.reload_rules(db)
            return jsonify({"ok": True, "rule_id": rule_id, "message": "Rule updated."})

        if request.method == "DELETE":
            db.delete(rule)
            db.flush()
            if svc.firestore:
                svc.firestore.delete_custom_rule(rule_id)
            svc.reload_rules(db)
            return jsonify({"ok": True, "rule_id": rule_id, "message": "Rule deleted."})


@app.route("/api/calc-fee", methods=["POST"])
def calc_fee():
    d = request.get_json(silent=True) or {}
    P, H = svc.kb["programmes"], svc.kb["hostel"]
    p = P.get(d.get("programme"))
    if not p:
        return err("unknown programme")
    pct = max(0, min(100, float(d.get("scholarship_pct") or 0)))
    years = p["duration_years"]
    fee_sem = p["fee_per_sem"] * (100 - pct) / 100.0
    prog_total = fee_sem * p["semesters"]
    exam_total = p["exam_fee"] * (p["semesters"] - (p["exam_from_sem"] - 1))
    hostel_annual = 0
    tiers = [t for t in H["tiers"] if t["annual"]]
    idx = d.get("hostel_index")
    if idx not in (None, "", -1) and 0 <= int(idx) < len(tiers):
        hostel_annual = tiers[int(idx)]["annual"]
    mess_annual = H["mess"]["standard"]["annual"] if d.get("mess") else 0
    total = prog_total + exam_total + (hostel_annual + mess_annual) * years
    return jsonify({
        "programme": p["name"], "scholarship_pct": pct, "programme_fee_per_semester": round(fee_sem),
        "programme_total": round(prog_total), "exam_total": exam_total, "hostel_per_year": hostel_annual,
        "mess_per_year": mess_annual, "years": years, "grand_total": round(total),
        "note": "Estimate only. Hostel figures include the Early Decision Benefit where applicable; confirm on lpu.in."
    })


@app.route("/api/hostel-tiers")
def hostel_tiers():
    return jsonify([
        {"index": i, "label": "%s, %d-seater, %s" % (t["type"], t["seater"], "AC" if t["ac"] else "Non-AC"), "annual": t["annual"]}
        for i, t in enumerate([t for t in svc.kb["hostel"]["tiers"] if t["annual"]])
    ])


@app.route("/api/escalate", methods=["POST"])
def escalate():
    d = request.get_json(silent=True) or {}
    sid = (d.get("session_id") or "")[:64]
    query = (d.get("query") or "")[:500]
    contact = (d.get("contact") or "")[:160]

    with session_scope() as db:
        db.add(Escalation(session_id=sid, user_query=query, contact=contact))

    if svc.firestore:
        try:
            svc.firestore.create_escalation(sid, query, contact)
        except Exception as ex:
            app.logger.warning("Firestore escalation logging failed: %s", ex)

    c = svc.kb["meta"]["contact"]
    return jsonify({"ok": True, "message": "Your request is logged for a counsellor. You can also call %s." % c["phone"]})


@app.route("/api/escalations")
def list_escalations():
    if svc.firestore:
        try:
            return jsonify(svc.firestore.get_escalations(limit=100))
        except Exception:
            pass
    with session_scope() as db:
        rows = db.query(Escalation).order_by(Escalation.created_at.desc()).limit(100).all()
        return jsonify([{"id": r.id, "session_id": r.session_id, "user_query": r.user_query, "contact": r.contact, "created_at": r.created_at.isoformat()} for r in rows])


# AI & Dataset Ingestion Endpoints
@app.route("/api/dataset/ingest", methods=["POST"])
def ingest_dataset():
    """Ingest external dataset items into the AI RAG retriever and Firebase."""
    data = request.get_json(silent=True) or {}
    items = data.get("items") or []
    if not items or not isinstance(items, list):
        return err("items list is required")

    # 1. Update live AI retrieval index
    svc.ai_engine.ingest_custom_dataset(items)

    # 2. Store in Firestore collection if connected
    if svc.firestore:
        for idx, item in enumerate(items):
            doc_id = item.get("id") or f"doc_{idx}"
            svc.firestore.upsert_dataset_collection("admissions_dataset", doc_id, item)

    return jsonify({
        "ok": True,
        "items_ingested": len(items),
        "total_chunks_indexed": len(svc.ai_engine.retriever.chunks),
        "message": f"Successfully ingested {len(items)} dataset records into AI Grounding Engine."
    })


@app.route("/api/dataset/search", methods=["POST"])
def search_dataset():
    """Test AI retrieval scoring on any query."""
    data = request.get_json(silent=True) or {}
    q = (data.get("query") or "").strip()
    if not q:
        return err("query is required")
    results = svc.ai_engine.retriever.search(q, top_k=5)
    return jsonify({
        "query": q,
        "matches": [{"chunk_id": c.chunk_id, "title": c.title, "category": c.category, "score": score, "preview": c.content[:160]} for c, score in results]
    })


@app.route("/api/export/<fmt>")
def export(fmt):
    with session_scope() as db:
        rep = analytics.full_report(db, svc)
    if fmt == "json":
        return Response(analytics.report_json(rep), mimetype="application/json", headers={"Content-Disposition": "attachment; filename=evaluation_report.json"})
    if fmt == "csv":
        return Response(analytics.report_csv(rep), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=evaluation_report.csv"})
    return err("format must be json or csv", 404)


@app.route("/api/seed", methods=["POST"])
def seed():
    token = os.environ.get("ADMIN_TOKEN")
    if token and request.headers.get("X-Admin-Token") != token:
        return err("forbidden", 403)
    from db.seed_evidence import seed as run_seed
    return jsonify({"ok": True, "turns": run_seed()})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), debug=os.environ.get("FLASK_DEBUG") == "1")
