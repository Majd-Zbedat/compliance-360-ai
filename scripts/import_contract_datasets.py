"""Import and normalize Excel contract datasets (bank/cybersecurity/ai).

Builds model-ready JSONL from structured contract tables by constructing a
canonical natural-language contract profile text per row.
"""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "contract_datasets" / "raw"
NORM_DIR = ROOT / "data" / "contract_datasets" / "normalized"
SPLIT_DIR = ROOT / "data" / "contract_datasets" / "splits"

FILE_TO_CATEGORY = {
    "bank_contracts.xlsx": "bank",
    "cybersecurity_contracts.xlsx": "cybersecurity",
    "ai_contracts.xlsx": "ai",
}

SUMMARY_SHEET_HINTS = {"summary", "portfolio summary"}

ID_CANDIDATES = ["contract_id", "id", "doc_id", "agreement_id", "record_id"]
TITLE_CANDIDATES = ["title", "name", "contract_name", "agreement_name", "supplier_name"]


@dataclass
class Record:
    uid: str
    category: str
    source_file: str
    sheet_name: str
    text: str
    title: str | None
    external_id: str | None
    metadata: dict[str, Any]


def _normalize_col_name(name: str) -> str:
    return str(name).strip().lower().replace(" ", "_")


def _pick_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    cols = {_normalize_col_name(c): c for c in df.columns}
    for c in candidates:
        if c in cols:
            return cols[c]
    return None


def _clean(value: Any) -> str:
    if pd.isna(value):
        return ""
    return " ".join(str(value).strip().split())


def _is_summary_sheet(sheet_name: str, df: pd.DataFrame) -> bool:
    s = sheet_name.lower()
    if any(h in s for h in SUMMARY_SHEET_HINTS):
        return True
    # If most values are NaN and only 2 columns, likely summary/report sheet.
    if df.shape[1] <= 2 and float(df.isna().mean().mean()) > 0.7:
        return True
    return False


def _row_to_text(row: dict[str, Any]) -> str:
    # Build rich, deterministic text from tabular fields.
    parts = []
    contract_id = _clean(row.get("Contract ID") or row.get("contract_id"))
    supplier = _clean(row.get("Supplier Name") or row.get("supplier_name"))
    category = _clean(row.get("Category") or row.get("category"))
    start = _clean(row.get("Start Date") or row.get("start_date"))
    end = _clean(row.get("End Date") or row.get("end_date"))
    value = _clean(row.get("Total Contract Value ($)") or row.get("total_contract_value"))
    payment = _clean(row.get("Payment Terms") or row.get("payment_terms"))
    status = _clean(row.get("Status") or row.get("status"))
    risk = _clean(row.get("Risk Level") or row.get("risk_level"))
    manager = _clean(row.get("Contract Manager") or row.get("contract_manager"))
    sla = _clean(row.get("SLA Uptime (%)") or row.get("sla_uptime"))
    renewal = _clean(row.get("Renewal Option") or row.get("renewal_option"))
    auto = _clean(row.get("Auto-Renew") or row.get("auto_renew"))
    penalty = _clean(row.get("Penalty Clause") or row.get("penalty_clause"))
    classification = _clean(row.get("Data Classification") or row.get("data_classification"))
    standard = _clean(row.get("Compliance Standard") or row.get("compliance_standard"))
    notes = _clean(row.get("Notes") or row.get("notes"))

    if contract_id:
        parts.append(f"Contract ID: {contract_id}.")
    if supplier:
        parts.append(f"Supplier: {supplier}.")
    if category:
        parts.append(f"Category: {category}.")
    if start or end:
        parts.append(f"Term: {start or 'unknown'} to {end or 'unknown'}.")
    if value:
        parts.append(f"Total contract value: {value} USD.")
    if payment:
        parts.append(f"Payment terms: {payment}.")
    if status:
        parts.append(f"Status: {status}.")
    if risk:
        parts.append(f"Risk level: {risk}.")
    if manager:
        parts.append(f"Contract manager: {manager}.")
    if sla:
        parts.append(f"SLA uptime target: {sla}%.")
    if renewal:
        parts.append(f"Renewal option: {renewal}.")
    if auto:
        parts.append(f"Auto-renew: {auto}.")
    if penalty:
        parts.append(f"Penalty clause: {penalty}.")
    if classification:
        parts.append(f"Data classification: {classification}.")
    if standard:
        parts.append(f"Compliance standard: {standard}.")
    if notes:
        parts.append(f"Notes: {notes}.")

    return " ".join(parts).strip()


def load_records(min_chars: int = 40) -> list[Record]:
    records: list[Record] = []

    for filename, category in FILE_TO_CATEGORY.items():
        path = RAW_DIR / filename
        if not path.exists():
            print(f"[import] WARN missing file: {path}")
            continue

        xls = pd.ExcelFile(path)
        for sheet_name in xls.sheet_names:
            df = pd.read_excel(path, sheet_name=sheet_name)
            if df.empty or _is_summary_sheet(sheet_name, df):
                continue

            id_col = _pick_column(df, ID_CANDIDATES)
            title_col = _pick_column(df, TITLE_CANDIDATES)

            for i, row in df.iterrows():
                row_dict = row.to_dict()
                text = _row_to_text(row_dict)
                if len(text) < min_chars:
                    continue

                ext_id = _clean(row_dict.get(id_col)) if id_col else None
                title = _clean(row_dict.get(title_col)) if title_col else None
                uid = ext_id or f"{category}_{sheet_name}_{i}"

                raw_dict = {
                    str(k): (None if pd.isna(v) else (v.item() if hasattr(v, "item") else v))
                    for k, v in row_dict.items()
                }

                records.append(
                    Record(
                        uid=str(uid),
                        category=category,
                        source_file=filename,
                        sheet_name=sheet_name,
                        text=text,
                        title=title or None,
                        external_id=ext_id or None,
                        metadata={
                            "raw": raw_dict,
                            "id_column": str(id_col) if id_col else None,
                            "title_column": str(title_col) if title_col else None,
                        },
                    )
                )

    return records


def write_jsonl(path: Path, items: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


def to_dict(r: Record) -> dict[str, Any]:
    return {
        "id": r.uid,
        "category": r.category,
        "source_file": r.source_file,
        "sheet_name": r.sheet_name,
        "text": r.text,
        "title": r.title,
        "external_id": r.external_id,
        "metadata": r.metadata,
    }


def split_records(items: list[dict], seed: int, train: float, val: float):
    random.seed(seed)
    shuffled = items[:]
    random.shuffle(shuffled)

    n = len(shuffled)
    n_train = int(n * train)
    n_val = int(n * val)

    train_items = shuffled[:n_train]
    val_items = shuffled[n_train : n_train + n_val]
    test_items = shuffled[n_train + n_val :]
    return train_items, val_items, test_items


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-chars", type=int, default=40)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--train", type=float, default=0.8)
    parser.add_argument("--val", type=float, default=0.1)
    args = parser.parse_args()

    if args.train + args.val >= 1.0:
        raise SystemExit("train + val must be < 1.0")

    records = load_records(min_chars=args.min_chars)
    items = [to_dict(r) for r in records]

    if not items:
        raise SystemExit("No usable records found. Check your xlsx files/content.")

    write_jsonl(NORM_DIR / "contracts_all.jsonl", items)

    for category in sorted({i["category"] for i in items}):
        write_jsonl(
            NORM_DIR / f"contracts_{category}.jsonl",
            [i for i in items if i["category"] == category],
        )

    train_items, val_items, test_items = split_records(
        items,
        seed=args.seed,
        train=args.train,
        val=args.val,
    )
    write_jsonl(SPLIT_DIR / "train.jsonl", train_items)
    write_jsonl(SPLIT_DIR / "val.jsonl", val_items)
    write_jsonl(SPLIT_DIR / "test.jsonl", test_items)

    print("[import] done")
    print(f"[import] total: {len(items)}")
    print(f"[import] train/val/test: {len(train_items)}/{len(val_items)}/{len(test_items)}")
    for category in sorted({i['category'] for i in items}):
        c = sum(1 for i in items if i["category"] == category)
        print(f"[import] {category}: {c}")


if __name__ == "__main__":
    main()
