"""Index bank / cybersecurity / AI contract datasets into RAG ChromaDB.

Run after import_contract_datasets.py so normalized jsonl exists.

Usage:
    python scripts/seed_contract_corpus.py
    python scripts/seed_contract_corpus.py --remote http://localhost:8001
    python scripts/seed_contract_corpus.py --reset
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.orchestrator.app.rag_contracts import build_portfolio_upsert_items  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed portfolio contracts into RAG.")
    parser.add_argument("--remote", default="http://localhost:8001", help="RAG service base URL")
    parser.add_argument("--reset", action="store_true", help="Clear portfolio rows before upsert")
    args = parser.parse_args()

    items = build_portfolio_upsert_items()
    if not items:
        print("[seed-contracts] No contracts in normalized jsonl. Run import_contract_datasets.py first.")
        return

    url = args.remote.rstrip("/") + "/upsert/contracts"
    with httpx.Client(timeout=300.0) as client:
        r = client.post(url, json={"items": items, "reset_portfolio": args.reset})
        r.raise_for_status()
        body = r.json()
    print(
        f"[seed-contracts] ok: upserted={body.get('upserted')} "
        f"total_in_index={body.get('total')} (from {len(items)} jsonl rows)"
    )


if __name__ == "__main__":
    main()
