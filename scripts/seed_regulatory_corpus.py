"""Seed the RAG service's ChromaDB `regulations` collection.

Reads every `*.json` file from `data/regulatory_corpus/`, validates each entry
against `RegulatoryClause`, and either calls the running RAG service's
`/upsert` endpoint, or — if the service is unreachable — writes directly to
ChromaDB locally.

Usage:
    python scripts/seed_regulatory_corpus.py
    python scripts/seed_regulatory_corpus.py --remote http://localhost:8001
    python scripts/seed_regulatory_corpus.py --reset
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
CORPUS_DIR = ROOT / "data" / "regulatory_corpus"


def _load_items() -> list[dict]:
    items: list[dict] = []
    for path in sorted(CORPUS_DIR.glob("*.json")):
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
            if not isinstance(data, list):
                print(f"[seed] WARN: {path.name} is not a JSON array, skipping")
                continue
            items.extend(data)
            print(f"[seed] loaded {len(data):>3} entries from {path.name}")
    return items


def _upsert_remote(base_url: str, items: list[dict], reset: bool) -> None:
    url = base_url.rstrip("/") + "/upsert"
    payload = {"reset": reset, "items": items}
    with httpx.Client(timeout=60.0) as client:
        r = client.post(url, json=payload)
        r.raise_for_status()
        body = r.json()
        print(
            f"[seed] remote upsert ok: upserted={body.get('upserted')} "
            f"total={body.get('total')}"
        )


def _upsert_local(items: list[dict], reset: bool) -> None:
    sys.path.insert(0, str(ROOT))
    from services.rag_service.app.store import get_store

    store = get_store()
    if reset:
        store.reset_regulations()
    ids = [it["id"] for it in items]
    docs = [it["text"] for it in items]
    metas = [
        {
            "source": it["source"],
            "article": it["article"],
            "title": it.get("title") or "",
            "tags": ",".join(it.get("tags", [])),
        }
        for it in items
    ]
    store.upsert_regulations(ids=ids, documents=docs, metadatas=metas)
    print(
        f"[seed] local upsert ok: upserted={len(ids)} "
        f"total={store.regulations_count()}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the regulatory corpus into ChromaDB.")
    parser.add_argument(
        "--remote",
        default=None,
        help="If set, POST to the running rag-service /upsert endpoint at this URL.",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop and recreate the regulations collection before seeding.",
    )
    args = parser.parse_args()

    items = _load_items()
    if not items:
        print("[seed] no corpus files found, nothing to seed", file=sys.stderr)
        sys.exit(1)
    print(f"[seed] total entries: {len(items)}")

    if args.remote:
        try:
            _upsert_remote(args.remote, items, args.reset)
            return
        except Exception as exc:
            print(f"[seed] remote upsert failed ({exc!r}); falling back to local")

    _upsert_local(items, args.reset)


if __name__ == "__main__":
    main()
