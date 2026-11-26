"""Seed and synchronize Firebase Firestore with the admissions dataset and benchmark logs.

Usage:
    python -m scripts.seed_firebase
"""
import json
import logging
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from db.firestore_db import FirestoreDB, is_firebase_configured
from engine.inference_engine import load_kb

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("seed_firebase")


def seed_firestore():
    if not is_firebase_configured():
        logger.error("Firebase is not configured! Please set FIREBASE_PROJECT_ID or FIREBASE_SERVICE_ACCOUNT_PATH.")
        return False

    db = FirestoreDB()
    kb = load_kb()

    # 1. Seed Knowledge Base collections
    logger.info("Uploading Knowledge Base to Firestore 'knowledge_base' collection...")
    for section in ["programmes", "scholarships", "hostel", "eligibility_general", "documents", "admission_process", "meta", "topics"]:
        if section in kb:
            db.upsert_dataset_collection("knowledge_base", section, kb[section])
            logger.info("  -> Saved section '%s'", section)

    # 2. Seed Admissions Dataset chunks for AI RAG retrieval
    logger.info("Uploading structured dataset records to 'admissions_dataset'...")
    for prog_id, p in kb.get("programmes", {}).items():
        doc_data = {
            "id": f"prog_{prog_id}",
            "category": "programmes",
            "title": f"{p.get('name')} Admission Details",
            "programme_id": prog_id,
            "name": p.get("name"),
            "fee_per_sem": p.get("fee_per_sem"),
            "duration_years": p.get("duration_years"),
            "semesters": p.get("semesters"),
            "eligibility": p.get("eligibility", {}),
            "content": f"{p.get('name')}: Duration {p.get('duration_years')} years, Fee INR {p.get('fee_per_sem'):,}/semester, Eligibility: {p.get('eligibility', {}).get('min_aggregate', 60)}%."
        }
        db.upsert_dataset_collection("admissions_dataset", doc_data["id"], doc_data)

    logger.info("Firebase Firestore seeding completed successfully!")
    return True


if __name__ == "__main__":
    seed_firestore()
