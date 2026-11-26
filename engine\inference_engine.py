"""Forward-chaining IF-THEN inference engine over the structured knowledge base.

WORKING MEMORY : preprocessed text, extracted entities, dialogue context (slots)
PRODUCTION RULES: engine/intent_matcher.py RULES (+ hot-reloadable custom rules)
CONFLICT RESOLUTION: highest (priority + 3 * pattern hits); confidence gates the firing
ACTION         : response handler reads facts from data/knowledge_base.json|yaml
"""
import json
import os
import time

from .context_manager import DialogueContext
from .fallback_handler import build_fallback
from .intent_matcher import IntentMatcher, RULES, extract_entities
from .preprocessor import Preprocessor

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONF_THRESHOLD = 0.6
SLOT_INTENTS = {"fees": "programme", "eligibility": "programme"}
RULE_ID_BY_INTENT = {r["intent"]: r["id"] for r in RULES}


def inr(n):
    s = str(int(n))
    if len(s) <= 3:
        return "INR " + s
    head, tail = s[:-3], s[-3:]
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    return "INR " + ",".join(parts + [tail])


def load_kb(path=None):
    path = path or os.environ.get("KB_PATH") or os.path.join(BASE, "data", "knowledge_base.json")
    if path.endswith((".yaml", ".yml")):
        import yaml
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class InferenceEngine:
    def __init__(self, version="2.4", kb=None, custom_rules=None):
        self.version = version
        self.kb = kb or load_kb()
        self.pre = Preprocessor(version)
        self.reload(custom_rules or [])

    def reload(self, custom_rules):
        """Hot-reload the rule base (used by the Rule Expansion Studio)."""
        self.custom_rules = list(custom_rules)
        self.matcher = IntentMatcher(self.version, self.custom_rules)

    # ------------------------------------------------------------------ public
    def analyse(self, text):
        pre = self.pre.run(text)
        ent = extract_entities(pre["mapped"])
        cands = self.matcher.match(pre["text"], ent)
        return pre, ent, cands

    def can_answer(self, text) -> bool:
        pre, ent, cands = self.analyse(text)
        return bool(cands and cands[0]["confidence"] >= CONF_THRESHOLD)

    def process(self, text, ctx: DialogueContext) -> dict:
        t0 = time.perf_counter()
        pre, ent, cands = self.analyse(text)
        best = cands[0] if cands else None
        if not best and self.version != "1.0" and ent.get("programme") and len(pre["content"]) <= 5 and not ctx.pending_slots:
            # entity-only utterance such as "BCA" or "tell me about B.Arch": treat as a programme enquiry
            best = {"rule_id": "R03", "intent": "programmes", "matched_regex": "(entity-only) programme mention", "hits": 1,
                    "confidence": 0.72, "custom": False, "response": None}
        slot_resolved = False
        out = None

        # --- slot filling: resolve a pending question with the user's answer
        if ctx.pending_slots:
            slot = ctx.pending_slots[0]
            if slot == "programme" and ent.get("programme"):
                strong_new = best and best["intent"] not in ("fees", "eligibility", "programmes", "greeting", "thanks_bye") and best["score"] >= 50
                ctx.fill("programme", ent["programme"])
                ctx.slots["_asked"] = 0
                if not strong_new:
                    intent = ctx.current_intent
                    best = {"rule_id": RULE_ID_BY_INTENT.get(intent, "R-SLOT"), "intent": intent, "matched_regex": "(slot-fill) programme entity",
                            "hits": 1, "confidence": 0.9, "custom": False, "response": None}
                    slot_resolved = True
            elif slot == "programme_b" and ent.get("programmes"):
                a = ctx.slots.get("programme")
                others = [p for p in ent["programmes"] if p != a]
                if others:
                    ctx.fill("programme_b", others[0])
                    best = {"rule_id": "R12", "intent": "compare", "matched_regex": "(slot-fill) programme_b entity", "hits": 1,
                            "confidence": 0.9, "custom": False, "response": None}
                    slot_resolved = True
            elif not best or best["confidence"] < CONF_THRESHOLD:
                ctx.slots["_asked"] = ctx.slots.get("_asked", 0) + 1
                if ctx.slots["_asked"] < 2:
                    out = self._ask_programme(ctx.current_intent, ctx, again=True)
                    best = {"rule_id": "R-SLOT", "intent": ctx.current_intent, "matched_regex": "(slot-reprompt)", "hits": 0, "confidence": 0.7, "custom": False, "response": None}
                else:
                    ctx.clear_pending()
            if out is None and best and not slot_resolved:
                ctx.clear_pending()  # user changed topic

        answered = bool(best and best["confidence"] >= CONF_THRESHOLD)
        if answered and out is None:
            out = self._fire(best, ent, ctx, pre)
        if not answered or out is None:
            fb = build_fallback(pre, self.kb)
            out = fb
            answered = False
            best = best or {"rule_id": "R-FALLBACK", "intent": "unanswered", "matched_regex": "", "confidence": 0.0}
            best = dict(best, rule_id="R-FALLBACK", intent="unanswered")
        if out.get("pending"):
            answered = True
        if ent.get("programme") and best["intent"] not in ("unanswered",):
            ctx.slots["programme"] = ent["programme"] if not out.get("keep_programme") else ctx.slots.get("programme", ent["programme"])
        if not out.get("pending") and not slot_resolved:
            ctx.current_intent = best["intent"]
        ctx.add_turn(text, best["intent"], best["rule_id"], answered)
        slots_view = {k: v for k, v in ctx.slots.items() if not k.startswith("_")}
        out["meta"] = {"rule_id": best["rule_id"], "intent": best["intent"], "matched_regex": best.get("matched_regex", ""),
                       "confidence": best.get("confidence", 0.0), "extracted_entities": {k: v for k, v in ent.items() if k != "programmes"},
                       "slots": slots_view, "pending_slots": list(ctx.pending_slots), "is_answered": answered, "slot_resolved": slot_resolved,
                       "version": self.version, "normalised": pre["text"], "alias_hits": pre["alias_hits"],
                       "latency_ms": round((time.perf_counter() - t0) * 1000, 2)}
        out.setdefault("chips", [])
        return out

    # ----------------------------------------------------------------- firing
    def _fire(self, best, ent, ctx, pre):
        intent = best["intent"]
        if best.get("custom"):
            return {"reply": best["response"], "chips": self._chips("fees", "admission", "scholarship")}
        prog = ent.get("programme")
        if intent in SLOT_INTENTS:
            prog = prog or ctx.slots.get("programme")
            if not prog:
                return self._ask_programme(intent, ctx)
        fn = getattr(self, "_h_" + intent, None)
        if fn is None:
            return None
        return fn(prog, ent, ctx)

    def _ask_programme(self, intent, ctx, again=False):
        ctx.ask_for(intent, "programme")
        verb = {"fees": "the fee", "eligibility": "eligibility"}.get(intent, "this")
        pre = "I still need to know which programme to look up. " if again else ""
        return {"reply": pre + "Which programme are you enquiring about for %s? For example, B.Tech CSE, MBA or BCA." % verb,
                "chips": [{"label": p["name"], "prompt": p["name"]} for k, p in self.kb["programmes"].items() if k != "btech"][:5],
                "pending": True}

    def _chips(self, *topic_ids):
        by = {t["id"]: t for t in self.kb["topics"]}
        return [{"label": by[i]["label"], "prompt": by[i]["prompt"]} for i in topic_ids if i in by]

    def _total(self, p):
        exam_sems = p["semesters"] - (p["exam_from_sem"] - 1)
        return p["fee_per_sem"] * p["semesters"], p["exam_fee"] * exam_sems

    # --------------------------------------------------------------- handlers
    def _h_greeting(self, prog, ent, ctx):
        return {"reply": "Hello! I'm the LPU Admission Intelligence assistant. Ask me about programmes, fees, eligibility, scholarships, hostels, documents, deadlines or UMS.",
                "chips": self._chips("fees", "scholarship", "hostel", "documents")}

    def _h_thanks_bye(self, prog, ent, ctx):
        return {"reply": "You're welcome! If anything else comes up, I'm here. Admission helpline: %s." % self.kb["meta"]["contact"]["phone"],
                "chips": self._chips("admission", "fees")}

    def _h_contact(self, prog, ent, ctx):
        c = self.kb["meta"]["contact"]
        return {"reply": "You can reach LPU admissions on **%s** or at %s. For anything I can't resolve, use the Escalate to Counsellor option." % (c["phone"], c["website"]),
                "chips": self._chips("admission", "documents"), "escalate": True, "escalate_label": "Escalate to Counsellor"}

    def _h_programmes(self, prog, ent, ctx):
        P = self.kb["programmes"]
        if prog and prog in P:
            p = P[prog]
            return {"reply": "**%s** (%s, %d years / %d semesters)\n%s\n%s" % (p["name"], p["level"], p["duration_years"], p["semesters"], p["curriculum"], p["highlights"]),
                    "chips": [{"label": "Fee for " + p["name"], "prompt": "What is the fee for %s?" % p["name"]},
                              {"label": "Eligibility", "prompt": "Eligibility criteria for %s" % p["name"]}]}
        rows = [[p["name"], p["level"], "%d yrs" % p["duration_years"], inr(p["fee_per_sem"])] for p in P.values()]
        return {"reply": "LPU offers these programmes among others. Tell me one for details on curriculum, fees and eligibility.\n",
                "table": {"headers": ["Programme", "Level", "Duration", "Fee / semester"], "rows": rows}, "chips": self._chips("fees", "eligibility")}

    def _h_fees(self, prog, ent, ctx):
        P = self.kb["programmes"]
        if prog == "btech":
            rows = [[P[k]["name"], inr(P[k]["fee_per_sem"])] for k in ("btech", "btech_cse", "btech_aiml")]
            return {"reply": "B.Tech fees depend on the branch (programme fee per semester, before scholarship):\n",
                    "table": {"headers": ["Branch", "Per semester"], "rows": rows},
                    "chips": self._chips("scholarship", "hostel"), "keep_programme": False}
        p = P[prog]
        total, exam = self._total(p)
        top = self.kb["scholarship"]["slabs"][p["scholarship_family"]][0]
        after = p["fee_per_sem"] * (100 - top["pct"]) // 100
        txt = ("**%s**: programme fee **%s per semester** (about %s over %d semesters before scholarship).\n"
               "Examination fee: %s per semester. Hostel and mess are separate.\n"
               "Example: at LPUNEST cut-off %s (%d%% scholarship) the programme fee drops to about **%s per semester**."
               % (p["name"], inr(p["fee_per_sem"]), inr(total), p["semesters"], inr(p["exam_fee"]), top["cutoff"], top["pct"], inr(after)))
        return {"reply": txt, "chips": self._chips("scholarship", "hostel", "eligibility")}

    def _h_eligibility(self, prog, ent, ctx):
        P = self.kb["programmes"]
        p = P[prog]
        e = p["eligibility"]
        txt = ("**%s eligibility**\n- Qualification: %s\n- Minimum marks: about %d%% aggregate\n- Entrance: %s\n%s" %
               (p["name"], e["qualification"], e["min_percent"], e["entrance"], e["note"]))
        return {"reply": txt, "chips": [{"label": "Fee", "prompt": "What is the fee for %s?" % p["name"]}] + self._chips("documents", "scholarship")}

    def _h_scholarship(self, prog, ent, ctx):
        S = self.kb["scholarship"]
        fam = self.kb["programmes"][prog]["scholarship_family"] if prog in self.kb["programmes"] else "btech"
        rows = [["Cut-off " + s["cutoff"], "%d%% of programme fee" % s["pct"]] for s in S["slabs"][fam]]
        phases = "; ".join(p["phase"] for p in S["lpunest_phases"])
        txt = ("Scholarships are mainly based on your **LPUNEST** score (cut-offs A to D), or JEE Main / qualifying marks for some routes. LPUNEST runs in phases (%s). %s\n\n%s\n\n%s" %
               (phases, S["note"], "Other awards:\n- " + "\n- ".join(S["other"]), "Slabs shown for: " + ("B.Tech" if fam == "btech" else "UG/PG programmes") + "."))
        return {"reply": txt, "table": {"headers": ["LPUNEST score band", "Scholarship"], "rows": rows}, "chips": self._chips("fees", "admission")}

    def _h_hostel(self, prog, ent, ctx):
        H = self.kb["hostel"]
        tiers = H["tiers"]
        if ent.get("seater"):
            tiers = [t for t in tiers if t["seater"] == ent["seater"]]
        if ent.get("nonac"):
            tiers = [t for t in tiers if not t["ac"]]
        elif ent.get("ac"):
            tiers = [t for t in tiers if t["ac"]]
        rows = [[t["type"], "%d-seater" % t["seater"], "AC" if t["ac"] else "Non-AC", inr(t["annual"]) + " / yr" if t["annual"] else "Confirm with LPU"] for t in tiers]
        m = H["mess"]
        txt = ("Hostel charges range **%s**. %s\n**Mess**: %s about %s per year (%s); %s plans %s.\n%s\n%s" %
               (H["overall_range"], H["early_decision_note"], m["standard"]["name"], inr(m["standard"]["annual"]), m["months"], m["special"]["name"],
                m["special"]["annual_range"], H["free_electricity"], H["tier_note"]))
        return {"reply": txt, "table": {"headers": ["Room type", "Occupancy", "AC", "Annual fee"], "rows": rows or [["No tier matched", "-", "-", "Ask the helpdesk"]]},
                "chips": self._chips("fees", "admission")}

    def _h_admission(self, prog, ent, ctx):
        A = self.kb["admission"]
        steps = "\n".join("%d. %s" % (i + 1, s) for i, s in enumerate(A["steps"]))
        return {"reply": "**Admission procedure**\n%s\n\nBooking amount: %s, adjusted against your first-semester fee." % (steps, inr(A["booking_fee"])),
                "chips": self._chips("documents", "scholarship", "deadlines" if False else "admission")}

    def _h_deadlines(self, prog, ent, ctx):
        A, S = self.kb["admission"], self.kb["scholarship"]
        ph = "\n".join("- **%s**: %s" % (p["phase"], p["note"]) for p in S["lpunest_phases"])
        return {"reply": "**Dates and deadlines**\n%s\n\n%s" % (ph, A["deadlines"]), "chips": self._chips("admission", "scholarship")}

    def _h_documents(self, prog, ent, ctx):
        D = self.kb["documents"]
        key = "international" if ent.get("international") else "lateral" if ent.get("lateral") else ("pg" if prog == "mba" else "ug")
        lbl = {"ug": "undergraduate", "pg": "postgraduate (MBA)", "lateral": "lateral entry", "international": "international"}[key]
        return {"reply": "**Documents for %s admission**\n- %s\n%s" % (lbl, "\n- ".join(D[key]), D["note"]),
                "chips": self._chips("admission", "eligibility")}

    def _h_ums(self, prog, ent, ctx):
        U = self.kb["ums"]
        return {"reply": "**UMS (University Management System)**: %s\n- Login: %s\n- Forgot password: %s\n- You can use it for: %s." %
                (U["portal"], U["login"], U["forgot"], ", ".join(U["features"]).lower()), "chips": self._chips("admission", "documents")}

    def _h_compare(self, prog, ent, ctx):
        progs = ent.get("programmes", [])
        P = self.kb["programmes"]
        if len(progs) < 2:
            first = progs[0] if progs else ctx.slots.get("programme")
            if first:
                ctx.fill("programme", first)
                ctx.ask_for("compare", "programme_b")
                return {"reply": "Sure. What would you like to compare **%s** with?" % P[first]["name"],
                        "chips": [{"label": p["name"], "prompt": p["name"]} for k, p in P.items() if k != first][:4], "pending": True}
            ctx.ask_for("compare", "programme")
            return {"reply": "Which two programmes should I compare? Name the first one, for example B.Tech CSE.",
                    "chips": [{"label": p["name"], "prompt": p["name"]} for p in P.values()][:4], "pending": True}
        a, b = P[progs[0]], P[progs[1]]
        ctx.slots["programme"] = progs[0]
        ctx.clear_pending()
        rows = [["Fee per semester", inr(a["fee_per_sem"]), inr(b["fee_per_sem"])], ["Duration", "%d yrs" % a["duration_years"], "%d yrs" % b["duration_years"]],
                ["Total programme fee", inr(self._total(a)[0]), inr(self._total(b)[0])], ["Minimum marks", "%d%%" % a["eligibility"]["min_percent"], "%d%%" % b["eligibility"]["min_percent"]],
                ["Entrance", a["eligibility"]["entrance"], b["eligibility"]["entrance"]]]
        return {"reply": "Here is a side-by-side comparison (programme fees before scholarship):", "table": {"headers": ["", a["name"], b["name"]], "rows": rows},
                "chips": self._chips("scholarship", "hostel"), "keep_programme": True}

    def _h_lateral_entry(self, prog, ent, ctx):
        L = self.kb["special"]["lateral"]
        rows = [[k, inr(v) + " / sem"] for k, v in L["fees"].items()]
        return {"reply": "**Lateral entry**\n%s\n%s" % (L["eligibility"], L["note"]), "table": {"headers": ["Programme", "Fee"], "rows": rows},
                "chips": self._chips("documents", "admission")}

    def _h_international_hostel(self, prog, ent, ctx):
        I = self.kb["special"]["international"]
        rows = [[k, v] for k, v in I["fees"].items()]
        return {"reply": "**International applicants**\n%s\n%s" % (I["note"], I["hostel"]), "table": {"headers": ["Item", "Amount"], "rows": rows},
                "chips": self._chips("hostel", "documents")}

    def _h_education_loan(self, prog, ent, ctx):
        return {"reply": "**Education loan and Bonafide certificate**\n" + self.kb["special"]["loan"]["text"], "chips": self._chips("fees", "documents"),
                "escalate": True, "escalate_label": "Escalate to Counsellor"}

    def _h_refund(self, prog, ent, ctx):
        return {"reply": "**Refund and withdrawal**\n" + self.kb["special"]["refund"]["text"], "chips": self._chips("fees", "admission"),
                "escalate": True, "escalate_label": "Escalate to Counsellor"}
