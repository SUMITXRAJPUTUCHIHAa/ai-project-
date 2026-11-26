"""Dataset Ingestion & AI Grounding Tool.

Parses external datasets (JSON or CSV), validates their structure,
chunks them for semantic AI retrieval, and syncs them to Firebase Firestore.

Usage:
    python -m scripts.ingest_dataset <path-to-dataset.json-or-csv>
"""
import csv
import json
import logging
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from db.firestore_db import FirestoreDB, is_firebase_configured

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ingest_dataset")


def load_dataset_file(filepath: str):
    """Load and normalize records from JSON or CSV."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Dataset file not found: {filepath}")

    ext = os.path.splitext(filepath)[1].lower()
    items = []

    if ext == ".json":
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                # Check common keys like "data", "records", "items", "faq"
                for k in ["data", "records", "items", "faq", "questions"]:
                    if k in data and isinstance(data[k], list):
                        items = data[k]
                        break
                if not items:
                    items = [data]

    elif ext in [".csv", ".tsv"]:
        delimiter = "\t" if ext == ".tsv" else ","
        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter=delimiter)
            items = list(reader)
    else:
        raise ValueError(f"Unsupported format '{ext}'. Please supply a .json or .csv dataset.")

    normalized = []
    for idx, raw in enumerate(items):
        title = raw.get("title") or raw.get("question") or raw.get("topic") or raw.get("programme") or f"Record #{idx+1}"
        content = raw.get("content") or raw.get("answer") or raw.get("description") or raw.get("text")
        if not content:
            # build content string from dictionary fields
            content = " | ".join(f"{k}: {v}" for k, v in raw.items() if v)

        category = raw.get("category") or raw.get("intent") or "general"
        doc_id = str(raw.get("id") or f"dataset_{idx+1}")

        normalized.append({
            "id": doc_id,
            "category": str(category),
            "title": str(title),
            "content": str(content),
            "raw": raw
        })

    return normalized


def ingest(filepath: str):
    logger.info("Reading dataset from: %s", filepath)
    records = load_dataset_file(filepath)
    logger.info("Parsed %d structured records.", len(records))

    # Save to local knowledge cache
    cache_path = os.path.join(ROOT, "data", "uploaded_dataset.json")
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)
    logger.info("Saved local cache to: %s", cache_path)

    # If Firebase is configured, sync to Firestore
    if is_firebase_configured():
        logger.info("Syncing records to Firebase Firestore collection 'admissions_dataset'...")
        db = FirestoreDB()
        for r in records:
            db.upsert_dataset_collection("admissions_dataset", r["id"], r)
        logger.info("Successfully synced all %d records to Firestore!", len(records))
    else:
        logger.info("Firebase not configured in environment. Stored in local JSON cache for AI retriever.")

    return records


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m scripts.ingest_dataset <path-to-dataset.json-or-csv>")
        sys.exit(1)
    ingest(sys.argv[1])
