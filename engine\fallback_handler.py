"""Graceful failure: closest topic chips + escalation to a human counsellor."""
import re

ESCALATE_TEXT = "Escalate to Counsellor"


def closest_topics(lemmas, topics, k=3):
    scored = []
    toks = set(lemmas)
    for t in topics:
        kw = set(t["keywords"])
        overlap = len(toks & kw) + sum(0.5 for w in toks for k_ in kw if len(w) > 3 and (w in k_ or k_ in w) and w != k_)
        scored.append((overlap, t))
    scored.sort(key=lambda x: -x[0])
    if scored[0][0] == 0:  # nothing close: popular defaults
        defaults = ["fees", "scholarship", "admission"]
        return [t for t in topics if t["id"] in defaults][:k]
    return [t for _, t in scored[:k]]


def build_fallback(pre: dict, kb: dict) -> dict:
    chips = closest_topics(pre["lemmas"], kb["topics"])
    text = ("I'm not able to answer that one confidently yet, and I'd rather not guess. "
            "I've logged your question so the admissions team can add a rule for it. "
            "These topics are closest to what you asked, or you can talk to a counsellor directly on "
            + kb["meta"]["contact"]["phone"] + ".")
    return {"reply": text, "chips": [{"label": t["label"], "prompt": t["prompt"]} for t in chips],
            "escalate": True, "escalate_label": ESCALATE_TEXT}
