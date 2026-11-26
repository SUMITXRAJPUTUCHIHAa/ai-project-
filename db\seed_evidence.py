"""Pre-seeded 25-session benchmark: the SAME scripted sessions are replayed through Baseline v1.0 and Expanded v2.4.

IMPORTANT: this is SYNTHETIC demonstration data built from realistic student/parent questions.
For the academic submission, collect >= 20 REAL users, store their logs (is_seed = false) and
re-run the Analytics & QA dashboard on those logs. Seed rows are flagged is_seed = true.

Run:  python -m db.seed_evidence
"""
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SESSIONS = [
    ("student", ["hi", "What is the fee for B.Tech CSE?", "Eligibility criteria for MBA", "thanks"]),
    ("student", ["fees", "BCA", "what scholarships are available?", "hostel charges for 2 seater"]),
    ("parent", ["What documents are required for admission?", "step by step admission procedure", "last date to apply"]),
    ("student", ["lateral entry fees for B.Tech CSE", "documents for lateral entry", "diploma holder eligibility"]),
    ("student", ["I am an NRI, hostel fees for international students", "international student fee for B.Tech", "visa documents needed"]),
    ("parent", ["education loan bonafide certificate", "need bonafide letter for bank loan", "what is the fee for MBA"]),
    ("parent", ["refund timeline if I cancel admission", "how do I withdraw my admission and get money back"]),
    ("student", ["kitna paisa lagega CSE mein", "hostel mein rehne ka kharcha", "nest exam kab hai"]),
    ("student", ["AI ML branch fees", "eligibility", "B.Tech AI", "mess food charges"]),
    ("student", ["compare btech cse and mba fee", "which is cheaper bca or btech cse"]),
    ("student", ["Hostel room and mess charges", "ac room 4 seater", "laundry and wifi in hostel", "is there a curfew"]),
    ("parent", ["what is UMS", "I forgot my UMS password", "I can't login to UMS portal"]),
    ("student", ["LPUNEST phase 3 date", "can i get admission with 58% in 12th", "is there a 100% free education scholarship"]),
    ("parent", ["how can I contact a counsellor", "phone number of admission office", "tell me about B.Arch"]),
    ("student", ["what courses can I study after 12th", "BCA syllabus", "B.Tech CSE fee", "scholarship for B.Tech CSE"]),
    ("student", ["is interview needed for AI and data engineering", "documents to carry for verification", "what to bring on first day"]),
    ("parent", ["total expenses for 4 years of btech", "installment payment option for fees", "exam fee per semester"]),
    ("student", ["does LPU give placement in Google", "what is the fee for MBA", "hostel fees"]),
    ("student", ["MBA eligibility", "CAT score needed?", "MBA scholarship details"]),
    ("parent", ["hello", "I want admission for my son in B.Tech Mechanical", "fee for B.Tech", "any discount for girls"]),
    ("student", ["education loan documents for LPU", "bank wants fee structure certificate", "lateral entry diploma fees"]),
    ("student", ["international student documents", "foreign student hostel and mess tiers", "how to join LPU", "bus route from Delhi to LPU campus"]),
    ("parent", ["is ragging allowed in hostel", "single seater room cost", "hostel early decision benefit"]),
    ("student", ["difference between btech cse and ai ml", "fee", "BCA", "thanks bye"]),
    ("student", ["what is my cutoff for 50% scholarship", "when does the session start", "refund of booking amount"]),
]


def _chat_all(svc, db, n_sessions=None):
    base = datetime.utcnow() - timedelta(days=9)
    total = 0
    for i, (role, queries) in enumerate(SESSIONS[:n_sessions]):
        for ver in ("1.0", "2.4"):
            from engine.context_manager import DialogueContext
            sid = "seed-%02d" % (i + 1)
            ctx = DialogueContext(sid)
            ts = base + timedelta(hours=7 * i + (0 if ver == "1.0" else 1))
            for j, q in enumerate(queries):
                svc.chat(db, sid, q, version=ver, is_seed=True, ts=ts + timedelta(minutes=2 * j), ctx=ctx)
                total += 1
    return total


def seed(reset=True):
    from db.database import init_db, session_scope
    from db.models import ConversationLog
    from services import ChatService
    init_db()
    svc = ChatService()
    with session_scope() as db:
        if reset:
            db.query(ConversationLog).filter(ConversationLog.is_seed.is_(True)).delete(synchronize_session=False)
        n = _chat_all(svc, db)
    return n


if __name__ == "__main__":
    print("Seeded %d benchmark turns (25 sessions x 2 engine versions)." % seed())
