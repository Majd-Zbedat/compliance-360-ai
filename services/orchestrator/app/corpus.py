"""Local read-only access to the seeded regulatory corpus.

Used by the `/regulations` endpoint so the dashboard can render the
regulator library without round-tripping through ChromaDB.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CORPUS_DIR = ROOT / "data" / "regulatory_corpus"


@lru_cache(maxsize=1)
def load_corpus() -> list[dict]:
    items: list[dict] = []
    if not CORPUS_DIR.exists():
        return items
    for path in sorted(CORPUS_DIR.glob("*.json")):
        try:
            with path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
                if isinstance(data, list):
                    items.extend(data)
        except Exception:
            continue
    return items
