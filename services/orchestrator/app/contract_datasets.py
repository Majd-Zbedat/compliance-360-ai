"""Load normalized contract datasets and category → regulation mappings."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[3]
DATASET_DIR = ROOT / "data" / "contract_datasets"
CONFIG_PATH = DATASET_DIR / "category_regulations.json"
NORM_DIR = DATASET_DIR / "normalized"


@lru_cache(maxsize=1)
def load_category_config() -> dict[str, dict[str, Any]]:
    if not CONFIG_PATH.exists():
        return {}
    with CONFIG_PATH.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    return data if isinstance(data, dict) else {}


@lru_cache(maxsize=4)
def load_contracts(category: str) -> list[dict[str, Any]]:
    path = NORM_DIR / f"contracts_{category}.jsonl"
    if not path.exists():
        return []
    items: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return items


def list_categories() -> list[dict[str, Any]]:
    cfg = load_category_config()
    out: list[dict[str, Any]] = []
    for key in ("bank", "cybersecurity", "ai"):
        if key not in cfg:
            continue
        meta = cfg[key]
        count = len(load_contracts(key))
        out.append(
            {
                "id": key,
                "label": meta.get("label", key),
                "description": meta.get("description", ""),
                "source_file": meta.get("source_file", ""),
                "contract_count": count,
                "industry_sector": meta.get("industry_sector"),
                "regulatory_focus": meta.get("regulatory_focus"),
                "default_jurisdiction": meta.get("default_jurisdiction"),
                "default_contract_type": meta.get("default_contract_type"),
                "regulations": meta.get("regulations", []),
                "regulation_sources": [
                    r["source"] for r in meta.get("regulations", []) if r.get("source")
                ],
            }
        )
    return out


def get_contract(category: str, contract_id: str) -> Optional[dict[str, Any]]:
    for item in load_contracts(category):
        if item.get("id") == contract_id or item.get("external_id") == contract_id:
            return item
    return None


def list_contract_summaries(
    category: str,
    *,
    limit: int = 200,
    offset: int = 0,
    q: Optional[str] = None,
) -> tuple[list[dict[str, Any]], int]:
    items = load_contracts(category)
    if q:
        needle = q.lower()
        items = [
            it
            for it in items
            if needle in (it.get("text") or "").lower()
            or needle in (it.get("title") or "").lower()
            or needle in str(it.get("id") or "").lower()
        ]
    total = len(items)
    page = items[offset : offset + limit]
    summaries = [
        {
            "id": it.get("id"),
            "external_id": it.get("external_id"),
            "category": it.get("category"),
            "title": it.get("title"),
            "source_file": it.get("source_file"),
            "risk_level": _risk_from_metadata(it),
            "compliance_standard": _compliance_from_metadata(it),
            "preview": (it.get("text") or "")[:220],
        }
        for it in page
    ]
    return summaries, total


def _raw_field(item: dict[str, Any], *keys: str) -> str:
    raw = (item.get("metadata") or {}).get("raw") or {}
    for k in keys:
        v = raw.get(k)
        if v is not None and str(v).strip():
            return str(v).strip()
    return ""


def _risk_from_metadata(item: dict[str, Any]) -> Optional[str]:
    return _raw_field(item, "Risk Level", "risk_level") or None


def _compliance_from_metadata(item: dict[str, Any]) -> Optional[str]:
    return _raw_field(item, "Compliance Standard", "compliance_standard") or None


def category_defaults(category: str) -> dict[str, Any]:
    cfg = load_category_config().get(category, {})
    return {
        "industry_sector": cfg.get("industry_sector"),
        "regulatory_focus": cfg.get("regulatory_focus"),
        "default_jurisdiction": cfg.get("default_jurisdiction"),
        "default_contract_type": cfg.get("default_contract_type"),
        "regulation_sources": [
            r["source"] for r in cfg.get("regulations", []) if r.get("source")
        ],
    }
