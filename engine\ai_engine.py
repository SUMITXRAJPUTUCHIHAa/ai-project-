"""AI Knowledge Retrieval & Grounded Generation Engine.

Integrates admissions datasets with structured retrieval (RAG) and LLM grounding.
Enforces that responses are strictly anchored in verified dataset facts.
"""
import json
import logging
import math
import os
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

def _load_dotenv_if_needed():
    """Lightweight loader to read .env file into os.environ if present."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env_path = os.path.join(root, ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip("'\"")
                        if k and k not in os.environ:
                            os.environ[k] = v
        except Exception:
            pass

_load_dotenv_if_needed()

# Default prompt template for dataset-grounded generation
SYSTEM_PROMPT = """You are the official LPU Admission Intelligence Assistant.
Your mission is to provide accurate, helpful, and transparent guidance to prospective students.

CRITICAL GROUNDING RULES:
1. Base your answer STRICTLY on the Grounding Facts provided below from the official admissions dataset.
2. DO NOT fabricate, assume, or extrapolate any figures, fees, dates, or eligibility cut-offs not present in the facts.
3. If the user's question cannot be answered from the provided facts, state clearly:
   "This detail is not present in our current verified admissions dataset. Would you like me to connect you with an admissions counsellor?"
4. Keep the tone professional, friendly, and structured. Use Markdown bolding for key numbers/dates and bullet points for steps or requirements.
5. Always quote monetary amounts with 'INR' and standard Indian formatting (e.g., INR 1,60,000 / semester).

Grounding Facts:
{context}

User Query:
{query}
"""


class DatasetChunk:
    """Represents an atomic knowledge chunk from the dataset."""

    def __init__(self, chunk_id: str, category: str, title: str, content: str, metadata: Optional[Dict[str, Any]] = None):
        self.chunk_id = chunk_id
        self.category = category
        self.title = title
        self.content = content
        self.metadata = metadata or {}
        # Pre-tokenized terms for fast lexical BM25 matching
        self.tokens = self._tokenize(f"{title} {category} {content}")

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        return re.findall(r"\b[a-z0-9_]{2,}\b", (text or "").lower())


class DatasetRetriever:
    """Indexes and retrieves dataset chunks using BM25-style lexical scoring."""

    def __init__(self):
        self.chunks: List[DatasetChunk] = []
        self.doc_freq: Dict[str, int] = {}
        self.avg_dl: float = 0.0

    def index_chunks(self, chunks: List[DatasetChunk]):
        self.chunks = chunks
        self.doc_freq = {}
        total_tokens = 0
        for chunk in chunks:
            seen = set(chunk.tokens)
            for t in seen:
                self.doc_freq[t] = self.doc_freq.get(t, 0) + 1
            total_tokens += len(chunk.tokens)
        self.avg_dl = (total_tokens / len(chunks)) if chunks else 1.0

    def search(self, query: str, top_k: int = 4) -> List[Tuple[DatasetChunk, float]]:
        if not self.chunks:
            return []
        q_tokens = re.findall(r"\b[a-z0-9_]{2,}\b", (query or "").lower())
        if not q_tokens:
            return []

        n_docs = len(self.chunks)
        k1 = 1.5
        b = 0.75
        scores: List[Tuple[DatasetChunk, float]] = []

        for chunk in self.chunks:
            score = 0.0
            doc_len = len(chunk.tokens)
            token_counts = {}
            for t in chunk.tokens:
                token_counts[t] = token_counts.get(t, 0) + 1

            for qt in q_tokens:
                if qt in token_counts:
                    df = self.doc_freq.get(qt, 1)
                    idf = math.log((n_docs - df + 0.5) / (df + 0.5) + 1.0)
                    tf = token_counts[qt]
                    denom = tf + k1 * (1 - b + b * (doc_len / self.avg_dl))
                    score += idf * ((tf * (k1 + 1)) / denom)

            # Boost if query mentions chunk title directly
            title_lower = chunk.title.lower()
            if any(term in title_lower for term in q_tokens):
                score += 2.0

            if score > 0:
                scores.append((chunk, round(score, 3)))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]


class AIAssistantEngine:
    """Coordinates dataset retrieval, prompt composition, and LLM generation."""

    def __init__(self, kb_data: Optional[Dict[str, Any]] = None):
        _load_dotenv_if_needed()
        self.retriever = DatasetRetriever()
        self.api_key = os.environ.get("GROQ_API_KEY") or os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENAI_API_KEY")
        self.kb_data = kb_data or {}
        self.build_index_from_kb(self.kb_data)

    def build_index_from_kb(self, kb: Dict[str, Any]):
        """Convert structured knowledge base into searchable dataset chunks."""
        chunks: List[DatasetChunk] = []

        # 1. Programmes
        programmes = kb.get("programmes", {})
        for pid, p in programmes.items():
            name = p.get("name", pid)
            duration = f"{p.get('duration_years', 4)} years ({p.get('semesters', 8)} semesters)"
            fee_sem = f"INR {p.get('fee_per_sem', 0):,}"
            exam_fee = f"INR {p.get('exam_fee', 0):,}"
            elig = p.get("eligibility", {})
            elig_text = f"{elig.get('min_aggregate', 60)}% in {', '.join(elig.get('subjects', []))}. LPUNEST: {elig.get('lpunest', 'Mandatory')}."
            notes = "; ".join(p.get("notes", []))

            content = (
                f"Programme: {name} (code: {pid})\n"
                f"Duration: {duration}\n"
                f"Tuition fee: {fee_sem} per semester\n"
                f"Examination fee: {exam_fee} per semester\n"
                f"Eligibility criteria: {elig_text}\n"
                f"Notes: {notes}"
            )
            chunks.append(DatasetChunk(
                chunk_id=f"prog_{pid}",
                category="programmes",
                title=f"{name} Admissions & Fees",
                content=content,
                metadata={"programme_id": pid, "fee": p.get("fee_per_sem")}
            ))

        # 2. Scholarships
        scholarships = kb.get("scholarship") or kb.get("scholarships") or {}
        slab_lines = []
        slabs_data = scholarships.get("slabs", {})
        if isinstance(slabs_data, dict):
            for prog_type, s_list in slabs_data.items():
                slab_lines.append(f"\n{prog_type.upper()} Scholarship Slabs:")
                for s in s_list:
                    slab_lines.append(f"- Cutoff {s.get('cutoff')}: {s.get('pct')}% tuition fee waiver")
        elif isinstance(slabs_data, list):
            for s in slabs_data:
                slab_lines.append(f"- Bracket {s.get('bracket')}: {s.get('percentage')}% waiver")

        phases_lines = [f"- {p.get('phase')}: {p.get('note')}" for p in scholarships.get("lpunest_phases", [])]
        other_lines = [f"- {o}" for o in scholarships.get("other", [])]

        chunks.append(DatasetChunk(
            chunk_id="scholarships_overview",
            category="scholarships",
            title="Scholarship Slabs and LPUNEST Cut-offs",
            content=(
                "LPU Performance-Based Scholarships (LPUNEST / Board / JEE):\n" +
                "\n".join(slab_lines) +
                "\n\nLPUNEST Exam Phases:\n" + "\n".join(phases_lines) +
                "\n\nOther Scholarship Schemes:\n" + "\n".join(other_lines) +
                f"\n\nNote: {scholarships.get('note', '')}"
            ),
            metadata={"type": "scholarship"}
        ))

        # 3. Hostels & Mess
        hostel = kb.get("hostel", {})
        tiers = hostel.get("tiers", [])
        tier_lines = [f"- {t.get('type')}, {t.get('seater')}-seater, {'AC' if t.get('ac') else 'Non-AC'}: INR {t.get('annual', 0):,}/yr" for t in tiers if t.get("annual")]
        mess = hostel.get("mess", {})
        std_mess = mess.get("standard", {}).get("annual", 40000)
        chunks.append(DatasetChunk(
            chunk_id="hostel_accommodation",
            category="hostel",
            title="Hostel Accommodation and Mess Charges",
            content=(
                f"Hostel room options and annual fees (EDB applicable):\n" + "\n".join(tier_lines) +
                f"\n\nEarly Decision Discount: INR {hostel.get('early_decision_discount', 10000):,} off if booked early."
                f"\nMess charges: Standard plan at INR {std_mess:,}/year ({mess.get('months', '10 months')})."
                f"\nElectricity: {hostel.get('free_electricity', '')}"
                f"\nExtras: {hostel.get('extras', '')}"
            ),
            metadata={"type": "hostel"}
        ))

        # 4. Admission Process & Deadlines
        adm = kb.get("admission") or kb.get("admission_process") or {}
        steps = adm.get("steps", [])
        step_lines = [f"{i+1}. {st}" for i, st in enumerate(steps)]
        chunks.append(DatasetChunk(
            chunk_id="admission_steps_and_process",
            category="admissions",
            title="Admission Procedure and Steps",
            content=(
                f"Step-by-step admission procedure (Booking fee: INR {adm.get('booking_fee', 10000):,}):\n" +
                "\n".join(step_lines) +
                f"\n\nImportant Deadlines & Dates: {adm.get('deadlines', '')}"
            ),
            metadata={"type": "process"}
        ))

        # 5. Documents Required
        docs_data = kb.get("documents", {})
        ug_docs = [f"- {d}" for d in docs_data.get("ug", [])]
        pg_docs = [f"- {d}" for d in docs_data.get("pg", [])]
        chunks.append(DatasetChunk(
            chunk_id="documents_required",
            category="documents",
            title="Mandatory Documents for Admission Verification",
            content=(
                "Undergraduate (UG) Documents:\n" + "\n".join(ug_docs) +
                "\n\nPostgraduate (PG) Documents:\n" + "\n".join(pg_docs) +
                f"\n\nVerification Note: {docs_data.get('note', '')}"
            ),
            metadata={"type": "documents"}
        ))

        # 6. Special Admission Categories (Lateral, International, Loan, Refund)
        special = kb.get("special", {})
        if "lateral" in special:
            lat = special["lateral"]
            chunks.append(DatasetChunk(
                chunk_id="special_lateral_entry",
                category="lateral",
                title="Lateral Entry Admissions and Fees",
                content=f"Lateral Entry: Direct 2nd-year admission into B.Tech.\nEligibility: {lat.get('eligibility', '')}\nFees: {lat.get('fees', '')}\nNote: {lat.get('note', '')}",
                metadata={"type": "lateral"}
            ))
        if "loan" in special:
            loan = special["loan"]
            chunks.append(DatasetChunk(
                chunk_id="special_education_loan",
                category="financial",
                title="Education Loan Assistance and Bonafide Letter",
                content=f"Education Loan Guidance:\n{loan.get('text', '')}",
                metadata={"type": "loan"}
            ))
        if "refund" in special:
            ref = special["refund"]
            chunks.append(DatasetChunk(
                chunk_id="special_refund_policy",
                category="financial",
                title="Fee Refund Policy and Cancellation",
                content=f"Fee Refund Policy:\n{ref.get('text', '')}",
                metadata={"type": "refund"}
            ))

        self.retriever.index_chunks(chunks)
        logger.info("Indexed %d knowledge chunks into AI retriever", len(chunks))

    def ingest_custom_dataset(self, dataset_items: List[Dict[str, Any]]):
        """Allows dynamic injection of external dataset records into the retriever."""
        new_chunks = list(self.retriever.chunks)
        for idx, item in enumerate(dataset_items):
            cid = item.get("id") or f"custom_{idx}"
            cat = item.get("category", "general")
            title = item.get("title") or item.get("question") or f"Topic {idx+1}"
            content = item.get("content") or item.get("answer") or str(item)
            new_chunks.append(DatasetChunk(
                chunk_id=cid,
                category=cat,
                title=title,
                content=content,
                metadata=item
            ))
        self.retriever.index_chunks(new_chunks)
        logger.info("Updated index with custom dataset: total %d chunks", len(new_chunks))

    def generate_grounded_response(self, query: str) -> Dict[str, Any]:
        """Retrieve relevant dataset chunks and generate a grounded answer."""
        results = self.retriever.search(query, top_k=3)
        if not results:
            return {
                "reply": "I could not find matching information in the official admissions dataset. Would you like to escalate this question to an admissions counsellor?",
                "confidence": 0.2,
                "grounded": False,
                "sources": [],
                "escalate": True
            }

        top_chunk, top_score = results[0]
        context_blocks = [f"[{i+1}] {c.title}:\n{c.content}" for i, (c, _) in enumerate(results)]
        context_str = "\n\n".join(context_blocks)
        sources = [c.title for c, _ in results]

        # 1. Check for Groq API Key (Primary - openai/gpt-oss-120b)
        groq_key = os.environ.get("GROQ_API_KEY") or os.environ.get("OPENAI_API_KEY")
        if groq_key:
            llm_reply = self._call_groq(groq_key, query, context_str)
            if llm_reply:
                return {
                    "reply": llm_reply,
                    "confidence": min(0.96, round(0.5 + (top_score / 20.0), 2)),
                    "grounded": True,
                    "sources": sources,
                    "escalate": False,
                    "model": os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b"),
                    "provider": "groq"
                }

        # 2. Check for Gemini API Key (Fallback)
        gemini_key = os.environ.get("GEMINI_API_KEY")
        if gemini_key:
            llm_reply = self._call_gemini(gemini_key, query, context_str)
            if llm_reply:
                return {
                    "reply": llm_reply,
                    "confidence": min(0.95, round(0.5 + (top_score / 20.0), 2)),
                    "grounded": True,
                    "sources": sources,
                    "escalate": False,
                    "model": "gemini-1.5-flash",
                    "provider": "gemini"
                }

        # Extractive deterministic fallback grounded directly in the top matching chunk
        fallback_reply = (
            f"Based on the official admissions records for **{top_chunk.title}**:\n\n"
            f"{top_chunk.content}\n\n"
            f"> *Source: LPU Admissions Knowledge Base ({top_chunk.category})*"
        )
        return {
            "reply": fallback_reply,
            "confidence": min(0.90, round(0.5 + (top_score / 20.0), 2)),
            "grounded": True,
            "sources": sources,
            "escalate": False
        }

    # ── Test-compatible adapter methods ───────────────────────────────────────

    @property
    def doc_count(self) -> int:
        """Return number of indexed documents."""
        return len(self.retriever.chunks)

    def index_documents(self, docs: List[Dict[str, Any]]):
        """Adapter: index a list of plain dicts (test-friendly interface).

        Each dict may have keys: id, topic, content, category, keywords.
        Delegates to ingest_custom_dataset internally.
        """
        normalised = []
        for d in docs:
            normalised.append({
                "id": d.get("id", ""),
                "category": d.get("category", "general"),
                "title": d.get("topic", d.get("title", "")),
                "content": d.get("content", ""),
                "metadata": {"keywords": d.get("keywords", [])}
            })
        # Build fresh DatasetChunk list from scratch for test isolation
        chunks = [
            DatasetChunk(
                chunk_id=item["id"],
                category=item["category"],
                title=item["title"],
                content=item["content"],
                metadata=item["metadata"]
            )
            for item in normalised
        ]
        self.retriever.index_chunks(chunks)
        logger.info("index_documents: indexed %d docs", len(chunks))

    def retrieve(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Adapter: retrieve top-k docs as plain dicts for test assertions."""
        results = self.retriever.search(query, top_k=top_k)
        return [
            {
                "id": c.chunk_id,
                "topic": c.title,
                "content": c.content,
                "category": c.category,
                "score": score
            }
            for c, score in results
        ]

    def build_grounding_prompt(
        self,
        query: str,
        context_docs: List[Dict[str, Any]],
        history: Optional[List[Dict]] = None
    ) -> str:
        """Build the full grounding prompt string (no unfilled placeholders)."""
        history = history or []
        context_blocks = []
        for i, doc in enumerate(context_docs):
            title = doc.get("topic", doc.get("title", f"Source {i+1}"))
            content = doc.get("content", "")
            context_blocks.append(f"[{i+1}] {title}:\n{content}")
        context_str = "\n\n".join(context_blocks) if context_blocks else "(No context available)"

        history_lines = []
        for turn in history[-3:]:
            role = turn.get("role", "user")
            msg = turn.get("content", "")
            history_lines.append(f"{role.upper()}: {msg}")
        history_str = "\n".join(history_lines) if history_lines else "(No prior conversation)"

        return (
            "You are the official LPU Admission Intelligence assistant.\n"
            "Answer ONLY using the provided context. Do not fabricate information.\n"
            "If the answer is not in the context, say: \"I don't have that information. "
            "Please contact LPU Admissions at admissions@lpu.in.\"\n\n"
            f"CONTEXT:\n{context_str}\n\n"
            f"CONVERSATION HISTORY:\n{history_str}\n\n"
            f"USER QUESTION: {query}\n\n"
            "RULES:\n"
            "- Be concise (max 150 words)\n"
            "- Use bullet points for lists\n"
            "- Always mention if information might be outdated\n"
            "- Never invent fees, dates, or eligibility criteria\n"
        )

    # ─────────────────────────────────────────────────────────────────────────

    def _call_groq(self, api_key: str, query: str, context: str) -> Optional[str]:
        """Call Groq Cloud API with openai/gpt-oss-120b and strict grounding prompt."""
        try:
            import requests
            model = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "LPU-Admission-Intelligence/2.4"
            }
            system_instruction = SYSTEM_PROMPT.format(context=context, query="")
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": query}
                ],
                "max_tokens": 512,
                "temperature": 0.2
            }
            try:
                resp = requests.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=20
                )
            except Exception:
                # SSL verification retry (Windows embedded python self-signed root chain safety)
                resp = requests.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=20,
                    verify=False
                )

            if resp.status_code == 200:
                data = resp.json()
                choices = data.get("choices", [])
                if choices:
                    content = choices[0].get("message", {}).get("content", "")
                    if content:
                        return content.strip()
            else:
                logger.warning("Groq API error (%d): %s", resp.status_code, resp.text)
        except Exception as e:
            logger.warning("Groq API call failed (%s); falling back to direct context extraction", e)
        return None

    def _call_gemini(self, api_key: str, query: str, context: str) -> Optional[str]:
        """Call Google Gemini API with strict dataset grounding prompt."""
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-1.5-flash")
            prompt = SYSTEM_PROMPT.format(context=context, query=query)
            resp = model.generate_content(prompt)
            if resp and resp.text:
                return resp.text.strip()
        except Exception as e:
            logger.warning("Gemini API call failed (%s); falling back to direct context extraction", e)
        return None
