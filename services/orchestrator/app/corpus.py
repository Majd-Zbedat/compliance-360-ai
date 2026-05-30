"""Local read/write access to the seeded regulatory corpus.

Used by the `/regulations` endpoints so the dashboard can render and extend the
regulator library without round-tripping through ChromaDB. User-uploaded
regulations are appended to `_uploaded.json` so they persist and re-seed.
"""

from __future__ import annotations

import json
import threading
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CORPUS_DIR = ROOT / "data" / "regulatory_corpus"
UPLOADED_FILE = CORPUS_DIR / "_uploaded.json"

_write_lock = threading.Lock()


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


def _read_uploaded() -> list[dict]:
    if not UPLOADED_FILE.exists():
        return []
    try:
        with UPLOADED_FILE.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def append_uploaded(items: list[dict]) -> int:
    """Append regulation items to the uploaded corpus file and refresh cache.

    Returns the new total number of uploaded items.
    """
    if not items:
        return len(_read_uploaded())
    with _write_lock:
        CORPUS_DIR.mkdir(parents=True, exist_ok=True)
        existing = _read_uploaded()
        existing.extend(items)
        with UPLOADED_FILE.open("w", encoding="utf-8") as fh:
            json.dump(existing, fh, indent=2, ensure_ascii=False)
        load_corpus.cache_clear()
        return len(existing)
