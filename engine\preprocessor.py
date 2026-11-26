"""NLP preprocessing: normalisation, alias mapping, tokenisation, lemmatisation, entity cues.

Uses NLTK's WordNetLemmatizer when available and its data is installed; otherwise a
deterministic regex/suffix lemmatiser is used so the engine has no heavy dependencies.
"""
import re

try:  # optional
    from nltk.stem import WordNetLemmatizer
    _WN = WordNetLemmatizer()
    _WN.lemmatize("tests")  # raises LookupError if corpus is missing
except Exception:  # pragma: no cover
    _WN = None

# Canonical alias mapping. Baseline v1.0 only knew programme names; v2.4 added colloquial terms.
ALIASES_V10 = [
    (r"\bb\.?\s?tech\b|\bengineering\b", "btech"),
    (r"\bm\.?\s?b\.?\s?a\b|\bpgdm\b", "mba"),
    (r"\bb\.?\s?c\.?\s?a\b", "bca"),
    (r"\bb\.?\s?arch\b|\barchitecture\b", "barch"),
    (r"\bcse\b|\bcomp(uter)?\s?sci(ence)?\b", "cse"),
    (r"\blpu\s?nest\b|\bnest\b", "lpunest"),
]
ALIASES_V24_EXTRA = [
    (r"\bai\s?(/|and|&)?\s?ml\b|\baiml\b|\bartificial intelligence\b|\bmachine learning\b", "aiml"),
    (r"\bhostels\b|\bdorm(itory)?\b|\baccommodation\b|\bboarding\b|\bresidential\b", "hostel"),
    (r"\bpapers\b|\bdmc\b|\bmark ?sheets?\b|\btranscripts?\b|\bcertificates?\b", "document"),
    (r"\bpaisa\b|\bkharcha\b|\bkharch\b|\bexpenses?\b|\bbudget\b|\bkitn[ai]\b", "fee"),
    (r"\bwaiver\b|\bconcession\b|\bfinancial aid\b|\bbursary\b", "scholarship"),
    (r"\bstudent portal\b|\berp\b", "ums"),
    (r"\bdiploma holders?\b|\blateral\b|\bdirect 2nd year\b|\bdirect second year\b", "lateral"),
    (r"\bnri\b|\bforeign(er)?\b|\boverseas\b|\binternational\b", "international"),
]

_IRREGULAR = {"criteria": "criteria", "analytics": "analytics", "ums": "ums", "mess": "mess",
              "lpunest": "lpunest", "bonafide": "bonafide", "his": "his", "has": "has", "is": "is",
              "was": "was", "this": "this", "us": "us", "class": "class", "address": "address",
              "process": "process", "business": "business", "fees": "fee", "cs": "cs", "ac": "ac"}
STOP = {"a","an","the","is","are","am","to","of","for","in","on","at","and","or","please","pls","me","i","my",
        "you","your","can","could","would","do","does","did","there","tell","about","what","whats","which",
        "how","kindly","want","need","know","give","show","it","be","by","with","any","get","have","has"}


def lemmatize(tok: str) -> str:
    if tok in _IRREGULAR:
        return _IRREGULAR[tok]
    if _WN is not None and tok.isalpha() and len(tok) > 3:
        return _WN.lemmatize(tok)
    if len(tok) > 4 and tok.endswith("ies"):
        return tok[:-3] + "y"
    if len(tok) > 4 and tok.endswith("sses"):
        return tok[:-2]
    if len(tok) > 3 and tok.endswith("s") and not tok.endswith(("ss", "us", "is")):
        return tok[:-1]
    return tok


class Preprocessor:
    def __init__(self, version: str = "2.4"):
        self.version = version
        al = list(ALIASES_V10)
        if version != "1.0":
            al = ALIASES_V24_EXTRA + al
        self.aliases = [(re.compile(p), c) for p, c in al]

    def normalise(self, text: str) -> str:
        t = (text or "").lower().strip()
        t = t.replace("&", " and ")
        t = re.sub(r"[^a-z0-9+/.\s'%]", " ", t)
        t = re.sub(r"\s+", " ", t).strip()
        return t

    def tokenize(self, text: str):
        return re.findall(r"[a-z0-9]+(?:'[a-z]+)?", text)

    def run(self, text: str) -> dict:
        norm = self.normalise(text)
        mapped = norm
        hits = []
        for rx, canon in self.aliases:
            if rx.search(mapped):
                hits.append(canon)
                mapped = rx.sub(canon, mapped)
        tokens = self.tokenize(mapped)
        lemmas = [lemmatize(t) for t in tokens]
        content = [l for l in lemmas if l not in STOP]
        return {"raw": text, "normalised": norm, "mapped": mapped, "tokens": tokens,
                "lemmas": lemmas, "content": content, "text": " ".join(lemmas), "alias_hits": hits}
