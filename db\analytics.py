"""Before/after analytics, unanswered-query clustering and report export."""
import csv
import io
import json
import re
from collections import Counter, defaultdict

from sqlalchemy import case, func

from .models import ConversationLog

# Topic clusters used to label the most common unanswered questions
CLUSTERS = [
    ("Lateral entry fees / eligibility", r"lateral|diploma|direct (2nd|second) year"),
    ("International student hostel & fees", r"international|nri|foreign|overseas|visa"),
    ("Education loan / Bonafide certificate", r"loan|bonafide|bona fide|bank"),
    ("Refund & withdrawal timelines", r"refund|money back|withdraw|cancel"),
    ("Hinglish / colloquial phrasing", r"kitn|paisa|kharch|kab\b|mein\b|hai\b"),
    ("Counsellor / contact details", r"contact|phone|counsel|helpline|call"),
    ("Bare programme names & follow-ups", r"^(b\.?tech|bca|mba|b\.?arch)\b"),
    ("Entrance exams / interview / dates", r"interview|cat\b|score|session start|when does"),
    ("Hostel life details", r"curfew|laundry|wifi|early decision"),
]


def cluster_of(q):
    ql = q.lower()
    for name, rx in CLUSTERS:
        if re.search(rx, ql):
            return name
    return "Other / out of scope (placement, transport, ...)"


def _rate(a, t):
    return round(100.0 * a / t, 1) if t else None


def version_stats(db, is_seed=None):
    q = db.query(ConversationLog.version, func.count(ConversationLog.id),
                 func.sum(case((ConversationLog.is_answered.is_(True), 1), else_=0)))
    if is_seed is not None:
        q = q.filter(ConversationLog.is_seed.is_(is_seed))
    out = {}
    for ver, total, answered in q.group_by(ConversationLog.version).all():
        answered = int(answered or 0)
        out[ver] = {"total": total, "answered": answered, "unanswered": total - answered, "recognition_rate": _rate(answered, total)}
    return out


def live_health(db):
    q = db.query(ConversationLog).filter(ConversationLog.is_seed.is_(False))
    total = q.count()
    ans = q.filter(ConversationLog.is_answered.is_(True)).count()
    return {"queries_logged": total, "recognition_rate": _rate(ans, total) if total else 100.0}


def unanswered_rows(db, is_seed=None, version=None, limit=2000):
    q = db.query(ConversationLog).filter(ConversationLog.is_answered.is_(False))
    if is_seed is not None:
        q = q.filter(ConversationLog.is_seed.is_(is_seed))
    if version:
        q = q.filter(ConversationLog.version == version)
    return q.order_by(ConversationLog.id.desc()).limit(limit).all()


def top_unanswered(db, svc, is_seed=None, version=None, n=15):
    """Distinct unanswered queries with counts, flagged by whether the CURRENT engine can now answer them."""
    cnt = Counter()
    for r in unanswered_rows(db, is_seed, version):
        cnt[r.user_query.strip()] += 1
    engine = svc.engines["2.4"]
    rows = [{"query": qy, "count": c, "cluster": cluster_of(qy), "covered_now": engine.can_answer(qy)} for qy, c in cnt.most_common(n)]
    return rows


def unresolved_live(db, svc):
    engine = svc.engines["2.4"]
    seen = set()
    for r in unanswered_rows(db, is_seed=False, limit=500):
        k = r.user_query.strip().lower()
        if k not in seen and not engine.can_answer(r.user_query):
            seen.add(k)
    return len(seen)


def cluster_breakdown(db, version="1.0", is_seed=True):
    c = Counter(cluster_of(r.user_query) for r in unanswered_rows(db, is_seed=is_seed, version=version))
    return [{"cluster": k, "count": v} for k, v in c.most_common()]


def intent_distribution(db, version="2.4"):
    rows = db.query(ConversationLog.detected_intent, func.count(ConversationLog.id)).filter(ConversationLog.version == version) \
        .group_by(ConversationLog.detected_intent).order_by(func.count(ConversationLog.id).desc()).all()
    return [{"intent": i or "-", "count": c} for i, c in rows]


def full_report(db, svc):
    seed = version_stats(db, is_seed=True)
    live = version_stats(db, is_seed=False)
    v1, v24 = seed.get("1.0", {}), seed.get("2.4", {})
    delta = round((v24.get("recognition_rate") or 0) - (v1.get("recognition_rate") or 0), 1) if v1 and v24 else None
    return {
        "title": "LPU Admission Intelligence - Evaluation Report",
        "benchmark": {"description": "25 scripted student/parent sessions replayed through each rule-base version (SYNTHETIC seed data; replace with real-user logs for submission).",
                      "baseline_v1_0": v1, "expanded_v2_4": v24, "improvement_points": delta},
        "live_traffic": live, "live_health": live_health(db),
        "baseline_unanswered_clusters": cluster_breakdown(db, "1.0", True),
        "top_unanswered_baseline": top_unanswered(db, svc, is_seed=True, version="1.0"),
        "top_unanswered_live": top_unanswered(db, svc, is_seed=False),
        "intent_distribution_v2_4": intent_distribution(db, "2.4"),
        "custom_rules_active": len(svc.engines["2.4"].custom_rules)}


def report_csv(rep):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["section", "metric", "value"])
    b = rep["benchmark"]
    for lbl, key in (("baseline_v1.0", "baseline_v1_0"), ("expanded_v2.4", "expanded_v2_4")):
        for k, v in (b.get(key) or {}).items():
            w.writerow(["benchmark", "%s.%s" % (lbl, k), v])
    w.writerow(["benchmark", "improvement_points", b.get("improvement_points")])
    w.writerow([]); w.writerow(["baseline_unanswered_cluster", "queries", ""])
    for c in rep["baseline_unanswered_clusters"]:
        w.writerow(["cluster", c["cluster"], c["count"]])
    w.writerow([]); w.writerow(["top_unanswered_query", "count", "cluster", "covered_by_v2.4"])
    for r in rep["top_unanswered_baseline"] + rep["top_unanswered_live"]:
        w.writerow(["query", r["query"], r["count"], r["cluster"], r["covered_now"]])
    return buf.getvalue()


def report_json(rep):
    return json.dumps(rep, indent=2)
