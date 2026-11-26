# LPU Admission Intelligence (Rule-Based Engine v2.4)

**PROJECT 01: Rule-Based College Enquiry & Admission Helpdesk Chatbot**
A deterministic production-system chatbot (Unit II): intents are detected with keyword and regular-expression
patterns, and answers are produced by IF-THEN rules over a structured JSON/YAML knowledge base. No LLM is used at runtime.

## Quick start
```bash
./run_local.sh                    # creates .venv, installs deps, serves http://localhost:8080
# or manually
pip install -r requirements.txt && python app.py
python -m unittest discover -s tests   # engine tests (no DB needed)
python -m db.seed_evidence             # (re)load the 25-session benchmark
```
Without `DATABASE_URL` the app uses local SQLite (`admissions.db`). For PostgreSQL (Neon / Supabase / Cloud SQL):
```bash
export DATABASE_URL="postgresql://user:pass@host:5432/dbname"
```
Tables are created automatically on start (`db/models.py`). `db/schema.sql` is the equivalent hand-run migration.
On first start with an empty log table the benchmark seed is loaded (disable with `AUTO_SEED=0`).

## Architecture
| Layer | File | Role |
|---|---|---|
| Knowledge base | `data/knowledge_base.json` / `.yaml` | programmes, fees, scholarship slabs, hostel tiers, eligibility, documents, admission steps, UMS |
| Preprocessor | `engine/preprocessor.py` | normalisation, canonical alias mapping, tokenisation, lemmatisation (NLTK if installed, else regex fallback) |
| Intent and entities | `engine/intent_matcher.py` | regex pattern library, keyword weighting, programme/seater/flag extraction |
| Inference | `engine/inference_engine.py` | forward chaining: match, resolve conflicts by priority + hits, fire handler, return `rule_id`, `matched_regex`, `confidence`, `extracted_entities` |
| Dialogue state | `engine/context_manager.py` | `current_intent`, `pending_slots`, `slots`, `turn_history`; persisted per session in the DB |
| Fallback | `engine/fallback_handler.py` | low-confidence catch, 3 closest topic chips, Escalate to Counsellor |
| Logging and analytics | `services.py`, `db/analytics.py` | every turn logged (`session_id, user_query, detected_intent, slots, rule_id, is_answered, version, timestamp`) |
| API | `app.py` | Flask REST + static UI |

Set `KB_PATH=data/knowledge_base.yaml` to load the YAML copy instead of JSON.

### REST API
`POST /api/chat`, `GET /api/health`, `GET /api/analytics`, `POST /api/expand-rule`, `POST /api/reset`; extras:
`POST /api/test-rule`, `GET /api/rules`, `GET /api/slot-state`, `GET /api/topics`, `POST /api/calc-fee`,
`POST /api/escalate`, `GET /api/export/json|csv`, `POST /api/seed` (protect with `ADMIN_TOKEN`).

## Evidence module (the syllabus deliverable)
1. Real users chat with the bot; every turn is logged with `is_seed = false`.
2. Open **Analytics & QA**: the dashboard clusters unanswered queries and compares Baseline v1.0 vs Expanded v2.4.
3. In **Rule Expansion Studio** pick an unanswered query, write/test a regex, add the IF-THEN response, and hot-reload.
4. Download `evaluation_report.json` / `.csv` for submission.

**Important honesty note:** the bundled 25-session benchmark is *synthetic demonstration data* (scripted, realistic questions
replayed through both rule-base versions, so the 69.1% -> 97.5% figures are real computations on scripted input). The assignment
asks for at least 20 *real* users: collect their logs and re-run the dashboard on them. Seed rows are flagged `is_seed = true`.
Baseline v1.0 is the frozen first rule set: narrower patterns, no colloquial aliases and no rules for lateral entry, international
hostel tiers, education-loan Bonafide, refunds or contact details, so those questions fall back by design.

## Data provenance and limits
Fees, slabs and hostel tiers were compiled from lpu.in pages and public education portals (2026-27 session) and portals
disagree in places (for example AI/ML fee INR 1.6L vs 2L per semester). Hostel tiers with no published figure are shown as
"confirm with LPU". The refund and loan answers are general guidance (`verified: false` in the KB). **Always verify on lpu.in
or the helpline 01824-404404 before paying any fee.** Edit `data/knowledge_base.json` and restart to update facts.

## Deploy: Firebase Hosting + Cloud Run
```bash
export DATABASE_URL="postgresql://..."      # strongly recommended on Cloud Run
./deploy_firebase.sh <gcp-project-id>
```
This builds the `Dockerfile` on Cloud Run (service `lpu-admission-intelligence`) and fronts it with Firebase Hosting rewrites
(`firebase.json`). Cloud Run SQLite lives in `/tmp` and is lost on restart, so use PostgreSQL for real logs.

## Syllabus mapping
Intent Pattern Library (`intent_matcher.py`) | Knowledge Base Design (`data/`) | Keyword and Regex Matching | IF-THEN Response Rules
(`inference_engine.py`) | Slot-Filling Dialogue and Context Management (`context_manager.py`) | Fallback Handling | Conversation Logging
and Unanswered Query Analysis (`db/`) | Rule Base Expansion and Answer Rate Measurement (Analytics & QA) | Chat Interface (`static/`) | Deployment (Firebase).
