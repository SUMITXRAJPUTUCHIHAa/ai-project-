"""Intent pattern library + entity extraction (Unit II production-system conditions)."""
import re

# Each rule: id, intent, priority, patterns (v1.0 baseline), patterns_v24 (added in v2.4),
# guards (v1.0 only: baseline declined these edge topics), since.
RULES = [
 {"id": "R01", "intent": "greeting", "priority": 1, "since": "1.0",
  "patterns": [r"^(hi|hello|hey|namaste|hii+|good (morning|afternoon|evening))\b"],
  "patterns_v24": [r"^(yo|hola|sup|namaskar|sat sri akal)\b", r"\bhow are you\b"]},
 {"id": "R02", "intent": "thanks_bye", "priority": 2, "since": "1.0",
  "patterns": [r"\b(thank|thanks|thx|bye|goodbye)\b"], "patterns_v24": [r"\b(ok(ay)?|great|got it|cool)\b$", r"\bsee you\b"]},
 {"id": "R03", "intent": "programmes", "priority": 20, "since": "1.0",
  "patterns": [r"\b(programme|program|course|curriculum|syllabus|specialisation|specialization|branch|degree)\b",
               r"\bwhat .*(offer|study|available)\b"],
  "patterns_v24": [r"\bwhich stream\b", r"\bsubject\b", r"\bduration\b", r"\bhow many (year|semester)\b", r"\bwhat can i (study|do)\b", r"\bdepartment\b"]},
 {"id": "R04", "intent": "fees", "priority": 30, "since": "1.0",
  "patterns": [r"\b(fee|tuition|cost|price)\b", r"\bhow much\b.*\b(fee|cost|pay)\b"],
  "patterns_v24": [r"\bhow much\b", r"\bper semester\b", r"\btotal (payment|amount|cost)\b", r"\binstal+ment\b", r"\bpayment (mode|option|plan)\b",
                   r"\bkitn[aie]\b", r"\bexam(ination)? fee\b", r"\bkharc?h?a\b", r"\bemi\b"],
  "guards": [r"\b(lateral|international|loan|refund|nri)\b", r"\bhostel\b", r"\bscholarship\b"]},
 {"id": "R05", "intent": "eligibility", "priority": 40, "since": "1.0",
  "patterns": [r"\b(eligib\w*|criteria|qualification|minimum marks|cut ?off|requirement)\b", r"\bwho can apply\b"],
  "patterns_v24": [r"\bmarks required\b", r"\bpcm\b", r"\bage limit\b", r"\bcan i (get|apply|take) admission\b", r"\bpercentage\b", r"\b12th\b.*\b(marks|percent)\b",
                   r"\bbackup\b|\bgap year\b", r"\bjee main\b.*\baccept\b", r"\b(cat|xat|mat|cmat|cuet|nata|gate)\b", r"\bscore needed\b|\bwhich exam\b"],
  "guards": [r"\b(lateral|international|loan|refund|nri)\b", r"\bdocument\b"]},
 {"id": "R06", "intent": "scholarship", "priority": 50, "since": "1.0",
  "patterns": [r"\bscholarship\b", r"\blpunest\b.*\b(slab|cut ?off|phase|score)\b", r"\bwaiver\b"],
  "patterns_v24": [r"\bfree education\b", r"\b100 ?%\b", r"\bsports quota\b", r"\bfemale\b.*\b(discount|scholarship)\b", r"\bfee waiver\b",
                   r"\blpu rise\b", r"\bmerit\b", r"\bdiscount\b", r"\blpunest\b.*\b(score|rank|result)\b"]},
 {"id": "R07", "intent": "hostel", "priority": 50, "since": "1.0",
  "patterns": [r"\bhostel\b", r"\bmess\b", r"\b(room|seater)\b", r"\bnon ?ac\b|\bac room\b"],
  "patterns_v24": [r"\blaundry\b", r"\bwifi\b|\bwi ?fi\b", r"\bcurfew\b", r"\bwhere will i (live|stay)\b", r"\bfood\b", r"\bwarden\b", r"\bapartment\b",
                   r"\bearly decision\b|\bedb\b", r"\belectricity\b"],
  "guards": [r"\b(international|nri|foreign)\b"]},
 {"id": "R08", "intent": "admission", "priority": 40, "since": "1.0",
  "patterns": [r"\badmission\b", r"\bapply\b|\bapplication\b", r"\bprocedure\b|\bprocess\b", r"\bregist\w+\b"],
  "patterns_v24": [r"\bstep\b", r"\bhow to join\b", r"\bbooking\b", r"\bslot\b", r"\binterview\b", r"\bcounsel+ing\b", r"\bseat\b",
                   r"\benrol+\b", r"\bdirect admission\b", r"\bhow do i get in\b", r"\bjoin lpu\b"],
  "guards": [r"\b(lateral|international|refund|loan|nri)\b", r"\bdocument\b"]},
 {"id": "R09", "intent": "deadlines", "priority": 55, "since": "1.0",
  "patterns": [r"\b(deadline|last date|due date|closing date)\b", r"\bphase (i{1,3}|[123])\b"],
  "patterns_v24": [r"\bexam date\b|\blpunest date\b", r"\bwhen (does|do|is|will)\b.*\b(start|begin|apply|exam|open|close|session)\b", r"\bsession start\b",
                   r"\bimportant date\b", r"\bcommence\b", r"\bwhen can i apply\b", r"\blast day\b", r"\bschedule\b", r"\bkab\b", r"\bwhat date\b", r"\bregistration (open|close)\b"]},
 {"id": "R10", "intent": "documents", "priority": 60, "since": "1.0",
  "patterns": [r"\bdocument\b", r"\b(marksheet|certificate|id proof|aadhaar|photo)\b", r"\bverification\b", r"\bchecklist\b"],
  "patterns_v24": [r"\bwhat to (carry|bring|submit)\b", r"\bpapers\b", r"\battested\b", r"\baffidavit\b", r"\bmigration\b", r"\boriginals?\b", r"\bcharacter certificate\b"]},
 {"id": "R11", "intent": "ums", "priority": 70, "since": "1.0",
  "patterns": [r"\bums\b", r"\bstudent portal\b", r"\b(login|log in|password)\b"],
  "patterns_v24": [r"\bcan'?t log ?in\b|\bcannot log ?in\b", r"\breset password\b|\bforgot\b", r"\bregistration (number|no)\b", r"\bportal\b", r"\battendance\b",
                   r"\btimetable\b|\btime table\b", r"\bgrade card\b|\bresult\b"]},
 {"id": "R12", "intent": "compare", "priority": 65, "since": "1.0",
  "patterns": [r"\b(compare|vs|versus|difference between)\b"],
  "patterns_v24": [r"\bbetter than\b", r"\bor\b.*\bwhich (is|one)\b", r"\bwhich (is|one) (better|cheaper)\b", r"\bcheaper\b"]},
 # ---- rules introduced in v2.4 after unanswered-query analysis ----
 {"id": "R13", "intent": "lateral_entry", "priority": 90, "since": "2.4",
  "patterns": [r"\blateral\b", r"\bdirect (2nd|second) year\b", r"\bdiploma\b"]},
 {"id": "R14", "intent": "international_hostel", "priority": 90, "since": "2.4",
  "patterns": [r"\b(international|nri|foreign|overseas)\b"]},
 {"id": "R15", "intent": "education_loan", "priority": 90, "since": "2.4",
  "patterns": [r"\b(loan|bonafide|bona fide|sanction letter|bank)\b", r"\bfee (certificate|structure letter)\b"]},
 {"id": "R16", "intent": "refund", "priority": 90, "since": "2.4",
  "patterns": [r"\brefund\b", r"\bmoney back\b", r"\b(cancel|withdraw)\w*\b.*\badmission\b", r"\bsecurity deposit\b"]},
 {"id": "R17", "intent": "contact", "priority": 35, "since": "2.4",
  "patterns": [r"\b(contact|helpline|phone|call|email|counsel+or|toll ?free)\b", r"\bspeak to\b", r"\bhuman\b"]},
]

PROGRAMME_RX = [  # order matters: most specific first
    ("btech_aiml", re.compile(r"\baiml\b|\bai\b|\bmachine learning\b|\bartificial intelligence\b|\bai/ml\b")),
    ("btech_cse", re.compile(r"\bcse\b|\bcomputer science\b|\bit branch\b|\binformation technology\b")),
    ("mba", re.compile(r"\bmba\b")),
    ("bca", re.compile(r"\bbca\b|\bcomputer application\b")),
    ("barch", re.compile(r"\bbarch\b")),
    ("btech", re.compile(r"\bbtech\b")),
]
FLAG_RX = {"lateral": re.compile(r"\blateral\b|\bdiploma\b"), "international": re.compile(r"\binternational\b|\bnri\b|\bforeign\b|\boverseas\b"),
           "ac": re.compile(r"\bac\b(?! ?room non)"), "nonac": re.compile(r"\bnon ?ac\b")}
SEATER_RX = re.compile(r"\b([1-4]|one|two|three|four)[ -]?seater\b")
NUMWORD = {"one": 1, "two": 2, "three": 3, "four": 4}


def extract_entities(mapped_text: str) -> dict:
    ent = {}
    progs = []
    for key, rx in PROGRAMME_RX:
        if rx.search(mapped_text) and key not in progs:
            progs.append(key)
    # 'btech' generic is redundant if a specific btech branch was found
    if len(progs) > 1 and "btech" in progs and any(p.startswith("btech_") for p in progs):
        progs.remove("btech")
    if progs:
        ent["programme"] = progs[0]
        ent["programmes"] = progs
    for name, rx in FLAG_RX.items():
        if rx.search(mapped_text):
            ent[name] = True
    m = SEATER_RX.search(mapped_text)
    if m:
        g = m.group(1)
        ent["seater"] = int(g) if g.isdigit() else NUMWORD[g]
    return ent


class IntentMatcher:
    def __init__(self, version: str = "2.4", custom_rules=None):
        self.version = version
        self.rules = []
        for r in RULES:
            if version == "1.0" and r["since"] != "1.0":
                continue
            pats = list(r["patterns"]) + ([] if version == "1.0" else r.get("patterns_v24", []))
            self.rules.append({"id": r["id"], "intent": r["intent"], "priority": r["priority"],
                               "compiled": [(p, re.compile(p)) for p in pats],
                               "guards": [re.compile(g) for g in r.get("guards", [])] if version == "1.0" else []})
        self.custom = []
        if version != "1.0":
            for c in custom_rules or []:
                try:
                    self.custom.append({"id": c["rule_id"], "intent": c.get("label") or "custom", "priority": 100,
                                        "compiled": [(c["pattern"], re.compile(c["pattern"], re.I))], "response": c["response"], "guards": []})
                except re.error:
                    continue

    def match(self, text: str, entities: dict):
        """Return candidate list (best first): each has rule_id, intent, matched_regex, hits, confidence."""
        cands = []
        for rule in self.custom + self.rules:
            if any(g.search(text) for g in rule["guards"]):
                continue
            hit_pats = [p for p, rx in rule["compiled"] if rx.search(text)]
            if not hit_pats:
                continue
            hits = len(hit_pats)
            if rule["intent"] in ("greeting", "thanks_bye") and len(text.split()) > 6:
                continue
            score = rule["priority"] + 3 * hits
            conf = 0.55 + 0.12 * min(hits, 3) + (0.06 if entities.get("programme") else 0.0)
            if rule["priority"] >= 90:
                conf += 0.05
            cands.append({"rule_id": rule["id"], "intent": rule["intent"], "matched_regex": hit_pats[0], "hits": hits,
                          "score": score, "confidence": round(min(conf, 0.99), 2), "custom": "response" in rule,
                          "response": rule.get("response")})
        cands.sort(key=lambda c: c["score"], reverse=True)
        return cands
